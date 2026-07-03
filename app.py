import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path

import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="OpsPilot | AI 工单助手", page_icon="🧭", layout="wide")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
FEEDBACK_FILE = DATA_DIR / "feedback.csv"

KNOWLEDGE_BASE = [
    {
        "title": "退款政策",
        "source": "退款政策.md｜第 1–4 条",
        "keywords": ["退款", "退货", "退款金额", "退款没到账", "退款流程", "退款申请"],
        "content": ""
        "1. 商品签收后 7 天内可申请无理由退货，商品需保持完整。\n"
        "2. 因质量问题申请退款，需要提供订单号、问题描述和照片或视频。\n"
        "3. 退款金额超过 500 元、涉及重复退款或补偿诉求时，必须由人工审核。\n"
        "4. 退款原路退回，审核通过后通常在 3–7 个工作日到账。",
    },
    {
        "title": "蓝牙耳机连接 FAQ",
        "source": "蓝牙连接 FAQ.md｜第 1–5 条",
        "keywords": ["蓝牙", "耳机", "连接", "配对", "连不上", "无法连接", "断开"],
        "content": ""
        "1. 请先确认耳机和手机电量充足，并关闭附近其他已配对设备的蓝牙。\n"
        "2. 在手机蓝牙列表中忽略该设备，然后长按耳机配对键 5 秒重新配对。\n"
        "3. 若仍无法连接，可尝试重启手机并将耳机恢复出厂设置。\n"
        "4. 若完成上述步骤仍失败，请收集订单号、设备型号和故障视频，转技术售后处理。\n"
        "5. 请勿承诺直接退款，需依据退款政策判断。",
    },
    {
        "title": "物流与发货规则",
        "source": "物流与发货规则.md｜第 1–4 条",
        "keywords": ["物流", "发货", "快递", "订单", "延迟", "没收到", "配送", "运输"],
        "content": ""
        "1. 现货订单通常在 48 小时内发货，节假日可能顺延。\n"
        "2. 物流超过 7 天未更新时，应向物流团队发起查询。\n"
        "3. 用户未收到货且物流显示已签收时，必须人工核验签收信息。\n"
        "4. 不要在未核验前承诺补发或退款。",
    },
    {
        "title": "隐私与投诉处理规范",
        "source": "隐私与投诉处理规范.md｜第 1–5 条",
        "keywords": ["隐私", "删除", "个人信息", "投诉", "举报", "律师", "起诉", "曝光", "威胁", "媒体"],
        "content": ""
        "1. 涉及个人信息删除、数据导出、账号安全的问题，必须转交隐私与合规团队。\n"
        "2. 不得在对话中索取身份证号、银行卡号等敏感信息。\n"
        "3. 用户提及投诉、媒体曝光、律师函、起诉或人身安全威胁时，必须人工审核并升级处理。\n"
        "4. 回复应保持中性、礼貌，不作法律结论或责任认定。\n"
        "5. 记录工单原文和处理时间，便于后续复盘。",
    },
]

CATEGORIES = ["物流", "售后", "退款", "技术问题", "隐私与合规", "投诉与升级", "其他"]


def get_api_key():
    """优先读取 Streamlit secrets，其次读取本机环境变量。"""
    try:
        return st.secrets.get("DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
    except Exception:
        return os.getenv("DEEPSEEK_API_KEY", "")


def retrieve_knowledge(ticket: str, top_k: int = 2):
    """最小可行的关键词检索。项目 README 会明确说明这是 MVP，不冒充向量检索。"""
    scored = []
    for article in KNOWLEDGE_BASE:
        score = sum(1 for keyword in article["keywords"] if keyword in ticket)
        scored.append((score, article))
    scored.sort(key=lambda x: x[0], reverse=True)
    relevant = [article for score, article in scored[:top_k] if score > 0]
    return relevant or [KNOWLEDGE_BASE[0]]


def source_context(articles):
    chunks = []
    for article in articles:
        chunks.append(f"【{article['title']}】\n来源：{article['source']}\n{article['content']}")
    return "\n\n".join(chunks)


def extract_json(text: str):
    """兼容模型偶尔用 Markdown 代码块包住 JSON 的情况。"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("模型没有返回 JSON 对象")
    return json.loads(text[start : end + 1])


def demo_result(ticket: str, articles):
    """没有 API Key 时也能演示页面结构；页面会明显标注为本地演示模式。"""
    text = ticket.lower()
    if any(word in text for word in ["隐私", "删除", "身份证", "银行卡", "个人信息"]):
        category, team, priority = "隐私与合规", "隐私与合规团队", "高"
    elif any(word in text for word in ["投诉", "起诉", "律师", "曝光", "威胁"]):
        category, team, priority = "投诉与升级", "客户体验与升级处理组", "高"
    elif any(word in text for word in ["蓝牙", "连接", "故障", "不能用", "断开"]):
        category, team, priority = "技术问题", "技术售后组", "中"
    elif any(word in text for word in ["物流", "发货", "快递", "配送", "没收到"]):
        category, team, priority = "物流", "物流支持组", "中"
    elif any(word in text for word in ["破损", "质量", "坏了", "瑕疵"]):
        category, team, priority = "售后", "售后支持组", "中"
    elif any(word in text for word in ["退款", "退货"]):
        category, team, priority = "退款", "售后支持组", "中"
    else:
        category, team, priority = "其他", "人工分流组", "低"

    risky = category in ["隐私与合规", "投诉与升级"] or "500" in text or "退款" in text
    source_names = [a["source"] for a in articles]
    return {
        "category": category,
        "priority": priority,
        "team": team,
        "sentiment": "负面" if any(x in text for x in ["不", "差", "投诉", "退款", "无法"]) else "中性",
        "needs_human_review": risky,
        "confidence": 0.78,
        "reason": "本地规则根据关键词识别；真实模式会由模型结合知识库上下文判断。",
        "reply_draft": "您好，抱歉给您带来不便。我们已收到您的反馈，建议先依据相关指引核对信息；如问题仍未解决，我们会协助转交对应团队进一步处理。",
        "citations": source_names,
        "mode": "本地演示模式（未调用模型）",
    }


def call_llm(ticket: str, articles: list, model: str, api_key: str):
    """通过 DeepSeek 的 OpenAI 兼容 Chat Completions API 调用模型。"""
    context = source_context(articles)
    instructions = """
你是企业客服运营团队的 AI 工单分流助手。你的任务是根据用户工单和提供的内部知识库，生成一个可供客服人员审核的结构化建议。

严格遵守以下规则：
1. 只能使用给定的知识库作为政策依据；没有依据时明确说明，并建议人工审核。
2. 不得承诺退款、补发或法律结论。
3. 出现隐私、个人信息、投诉、威胁、法律、媒体曝光、退款金额超过 500 元、低把握或知识库无依据时，needs_human_review 必须为 true。
4. 回复草稿须中文、礼貌、简洁，不超过 120 字。
5. 只返回一个合法 JSON 对象，不要 Markdown，不要额外解释。

JSON 必须具有以下字段：
{
  "category": "物流|售后|退款|技术问题|隐私与合规|投诉与升级|其他",
  "priority": "低|中|高",
  "team": "建议负责团队",
  "sentiment": "正面|中性|负面",
  "needs_human_review": true,
  "confidence": 0.0,
  "reason": "判断依据，50字以内",
  "reply_draft": "给用户的回复草稿",
  "citations": ["知识来源标题或条款"]
}
""".strip()

    user_message = f"""客户工单：
{ticket}

内部知识库：
{context}
"""

    # DeepSeek 兼容 OpenAI Python SDK，但使用它自己的 API 地址和 Chat Completions 接口。
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content or ""
    result = extract_json(content)
    result["mode"] = f"真实 DeepSeek 模式｜模型：{model}"
    return result


def save_feedback(ticket, result, feedback):
    DATA_DIR.mkdir(exist_ok=True)
    new_file = not FEEDBACK_FILE.exists()
    with FEEDBACK_FILE.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["timestamp", "ticket", "category", "priority", "needs_human_review", "feedback"],
        )
        if new_file:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "ticket": ticket,
                "category": result.get("category", ""),
                "priority": result.get("priority", ""),
                "needs_human_review": result.get("needs_human_review", ""),
                "feedback": feedback,
            }
        )


# -------- UI --------
st.title("🧭 OpsPilot｜AI 工单分流与知识库回复助手")
st.caption("把客户工单转成：分类、优先级、负责团队、可引用依据、回复草稿与人工审核建议。")

with st.sidebar:
    st.header("运行设置")
    api_key = get_api_key()
    model = st.text_input("模型名称", value="deepseek-v4-flash", help="填入你账户可用的 DeepSeek 模型名称。")
    st.divider()
    if api_key:
        st.success("已检测到 DeepSeek API Key：将调用真实模型")
    else:
        st.warning("未检测到 API Key：将运行本地演示模式")
        st.caption("本地可设置环境变量 DEEPSEEK_API_KEY；部署时填写 Streamlit Secrets。")
    st.divider()
    st.markdown("**高风险自动转人工**")
    st.markdown("- 个人信息与隐私请求\n- 投诉、法律、威胁、媒体\n- 退款金额 > 500 元\n- 模型把握不足或知识库无依据")

sample_tickets = {
    "请选择示例或自己输入": "",
    "蓝牙耳机无法连接 + 要求退款": "客户购买的蓝牙耳机无法连接手机，已经重启过手机，仍然连不上。客户要求立即退款。",
    "物流 7 天未更新": "我的订单一周前就显示已发货，但物流 7 天没有更新，请问到底什么时候能收到？",
    "删除个人信息": "请删除我的个人信息和历史订单数据，并告诉我处理进度。",
    "投诉与法律风险": "你们再不解决，我就去平台投诉并联系律师。",
}

choice = st.selectbox("快速填入一个演示工单", list(sample_tickets.keys()))
default_text = sample_tickets[choice]
ticket = st.text_area(
    "客户工单内容",
    value=default_text,
    height=150,
    placeholder="例如：客户购买的耳机无法连接蓝牙，已尝试重启，要求退款。",
)

run = st.button("开始处理工单", type="primary", use_container_width=True)

if run:
    if not ticket.strip():
        st.warning("请先输入一条客户工单。")
        st.stop()

    articles = retrieve_knowledge(ticket)
    with st.spinner("正在检索知识库并生成处理建议…"):
        try:
            if api_key:
                result = call_llm(ticket, articles, model, api_key)
            else:
                result = demo_result(ticket, articles)
            st.session_state["result"] = result
            st.session_state["ticket"] = ticket
            st.session_state["articles"] = articles
        except Exception as e:
            st.error("模型调用失败。你仍可用本地演示模式完成页面和截图。")
            st.exception(e)

if "result" in st.session_state:
    result = st.session_state["result"]
    articles = st.session_state["articles"]
    st.divider()
    st.subheader("处理结果")
    st.caption(result.get("mode", ""))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("问题分类", result.get("category", "—"))
    c2.metric("优先级", result.get("priority", "—"))
    c3.metric("建议团队", result.get("team", "—"))
    confidence = result.get("confidence", "—")
    try:
        confidence = f"{float(confidence):.0%}"
    except Exception:
        pass
    c4.metric("模型把握度", confidence)

    if result.get("needs_human_review"):
        st.error("需要人工审核：该工单可能涉及高风险、低把握或需要进一步核验的情况。")
    else:
        st.success("可作为客服处理草稿使用；发送前仍建议人工复核。")

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown("#### 回复草稿")
        st.text_area("", value=result.get("reply_draft", ""), height=150, label_visibility="collapsed")
        st.markdown("#### 判断依据")
        st.info(result.get("reason", "未提供判断依据。"))
    with right:
        st.markdown("#### 知识库依据")
        citations = result.get("citations", [])
        if citations:
            for citation in citations:
                st.markdown(f"- {citation}")
        st.markdown("#### 本次检索到的条目")
        for article in articles:
            with st.expander(article["title"]):
                st.caption(article["source"])
                st.write(article["content"])

    st.markdown("#### 人工反馈")
    fb1, fb2, fb3 = st.columns(3)
    if fb1.button("👍 结果可用", use_container_width=True):
        save_feedback(st.session_state["ticket"], result, "useful")
        st.success("已记录“可用”反馈。")
    if fb2.button("👎 需要修改", use_container_width=True):
        save_feedback(st.session_state["ticket"], result, "needs_revision")
        st.warning("已记录“需要修改”反馈。")
    if fb3.button("⚠️ 高风险漏判", use_container_width=True):
        save_feedback(st.session_state["ticket"], result, "risk_missed")
        st.error("已记录“高风险漏判”反馈。")

st.divider()
st.markdown("### 项目说明")
st.markdown(
    "这是一个求职用 MVP：它展示了**AI 工作流设计、提示词约束、轻量知识检索、结构化输出、人工审核与反馈闭环**。"
)
st.caption("注意：示例知识库为虚构内容，仅用于作品集演示，不应用于真实客服决策。")
