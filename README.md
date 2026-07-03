## 在线 Demo
Demo: https://ops-pilot-ai-ticket-assistant-chrvzfz2ycuq6hqccmjwaz.streamlit.app/

# 🧭 OpsPilot｜AI 工单分流与知识库回复助手

一个面向客服 / 运营场景的 AI 工具作品集项目。用户输入客户工单后，系统会输出：

- 工单分类、优先级、建议负责团队
- 基于内部知识库的处理依据
- 可编辑的客服回复草稿
- 高风险问题的人工审核建议
- 人工反馈记录，用于后续优化 Prompt 与规则

> **定位：** 求职作品集 MVP，而不是生产系统。知识库为虚构示例；不可用于真实客户决策。

## 1. 为什么做它

真实的 AI 工具不应该只是“一个聊天框”。本项目把大模型放入一个清晰的业务流程：

```text
客户工单 → 知识库检索 → LLM 结构化判断 → 回复草稿 → 人工审核 → 反馈记录
```

它用于展示：Prompt 约束、轻量检索、结构化输出、风险兜底与人机协作设计。

## 2. 核心功能

| 模块 | 说明 |
|---|---|
| 工单分类 | 将问题划分为物流、售后、退款、技术问题、隐私与合规、投诉与升级等类别 |
| 知识检索 | 用关键词从虚构政策库中检索最相关条目（MVP 版本，不冒充向量数据库） |
| 结构化输出 | 要求模型只输出 JSON，便于前端显示和后续接入工作流 |
| 风险审核 | 对隐私、投诉、法律、媒体、金额较大退款等情况强制建议人工审核 |
| 反馈闭环 | 记录“可用 / 需要修改 / 高风险漏判”，为后续 Prompt 和规则优化保留数据 |

## 3. 技术栈

- Python
- Streamlit
- OpenAI Python SDK / Responses API
- 本地 Markdown 知识库（关键词检索）
- CSV 反馈记录

## 4. 本地运行

### 前置条件

- Python 3.10+
- 一个可用的 OpenAI API Key（没有也可打开本地演示模式）

### 安装并启动

```bash
python -m venv .venv
```

macOS / Linux：

```bash
source .venv/bin/activate
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
```

安装依赖：

```bash
pip install -r requirements.txt
```

设置 API Key（二选一）：

```bash
# macOS / Linux
export OPENAI_API_KEY="你的_API_Key"
```

```powershell
# Windows PowerShell
$env:OPENAI_API_KEY="你的_API_Key"
```

启动：

```bash
streamlit run app.py
```

## 5. 部署到 Streamlit Community Cloud

1. 将代码推送到 GitHub；不要上传 `.streamlit/secrets.toml` 或 `.env`。
2. 在 Streamlit Community Cloud 中创建 App，选择仓库和 `app.py`。
3. 在 **Advanced settings → Secrets** 中粘贴：

```toml
OPENAI_API_KEY = "你的_API_Key"
```

4. 部署完成后，将公开链接放到简历和 README。

## 6. 测试方式

`data/test_cases.csv` 提供 10 条手工测试案例。对于每条案例，记录：

- 分类是否正确
- 是否正确触发人工审核
- 知识库引用是否相关
- 回复草稿是否需要较大改写

不要编造百分比。测试 10 条后，如实写“已完成 10 条人工测试，其中 X 条分类正确”。

## 7. 当前局限与下一步

- 当前是关键词检索，下一版可升级为 embedding + 向量数据库。
- 当前反馈写入本地 CSV，云端生产版应接入数据库。
- 当前的审核逻辑为 Prompt + 页面提示；生产环境应增加独立规则引擎、权限控制、日志与监控。

## 8. 简历描述（请按你的真实测试结果修改）

- 设计并开发 AI 工单分流与知识库回复助手，实现工单分类、优先级识别、政策依据检索和回复草稿生成。
- 通过强约束 Prompt 要求模型输出 JSON，将生成结果映射为可操作的业务字段。
- 设计隐私、投诉、法律及高金额退款的人工审核规则，降低高风险自动化决策。
- 使用 Streamlit 搭建交互式 Demo，并保留人工反馈记录以支持后续 Prompt 与规则迭代。
