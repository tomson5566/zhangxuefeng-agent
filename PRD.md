# 张雪峰高考志愿 Agent — 产品需求文档 (PRD v1.0)

> 你（qwen_code）将作为开发，基于这份 PRD 实现一个**最小可运行**的 Web 应用。
> 后续 PM（我）会基于你产出的代码做集成、调试和优化。

---

## 1. 项目目标

把 `~/.copaw/workspaces/default/skills/zhangxuefeng-perspective` 这份 **纯文本 Skill 文档**（809 行 SKILL.md + 3 份福建高考研究报告 + 10 份 PDF），变成一个**用户能直接对话**的 Web Agent。

**MVP 范围（本次交付）**：
- 用户打开网页 → 看到聊天框
- 用户问高考志愿问题 → Agent 以「张雪峰」口吻回答
- 单轮对话即可（先不搞多轮记忆）
- **流式输出**（一个字一个字地打字，符合 ui-ux-design 规范）

**非 MVP（本轮不实现）**：
- 多轮对话状态管理
- 持久化历史记录
- 用户登录
- PDF 向量化 RAG（直接让 LLM 读 references/ 下的 markdown 即可，数据量小）

---

## 2. 技术栈（强制）

- **后端**：Python 3.11+ / FastAPI / uvicorn
- **Agent 框架**：**langchain** （langchain-core + langchain-community + langchain-openai）
- **LLM**：通过 `langchain_openai.ChatOpenAI` 接 **MiniMax 兼容接口**
  - base_url: `https://api.minimaxi.com/v1`
  - model: `MiniMax-M3`
  - api_key: 从环境变量 `OPENAI_API_KEY` 读取
  - 已确认环境变量在 PM 启动时已经设置好
- **依赖管理**：**uv**（项目根目录用 `uv init` + `uv add` 管依赖）
- **前端**：**纯 HTML + CSS + 原生 JS**（**禁止**用 React/Vue 框架）
  - 单文件 `index.html` + 一个 `app.js` + 一个 `style.css`
  - 不用打包器、不用 npm
- **流式协议**：Server-Sent Events (SSE) — 后端用 FastAPI `StreamingResponse`，前端用 `EventSource` 或 `fetch` 读流

---

## 3. 目录结构（必须这样建）

```
/home/tangzhiang/.copaw/workspaces/coding-agent/workspaces/zhangxuefeng-agent/
├── pyproject.toml          # uv 管理
├── README.md               # 启动说明
├── .env.example            # OPENAI_API_KEY 模板
├── .env                    # 实际 key (PM 会填充)
├── .gitignore
├── backend/
│   ├── __init__.py
│   ├── main.py             # FastAPI app + 路由
│   ├── agent.py            # LangChain agent 核心逻辑
│   ├── prompt.py           # System prompt 加载（从 SKILL.md 提炼）
│   └── config.py           # 读取 .env, 构造 LLM client
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
└── scripts/
    └── start.sh            # uv run 后端 + python -m http.server 前端
```

---

## 4. 后端详细规格

### 4.1 `backend/config.py`

读取环境变量，返回一个 `Settings` dataclass：

```python
@dataclass
class Settings:
    openai_api_key: str
    openai_base_url: str = "https://api.minimaxi.com/v1"
    model_name: str = "MiniMax-M3"
    skill_dir: Path  # 默认 ~/.copaw/workspaces/default/skills/zhangxuefeng-perspective
```

启动时校验 key 存在，否则 raise 友好错误。

### 4.2 `backend/prompt.py`

负责把 SKILL.md 切成三段，塞进 system message：

```python
SYSTEM_PROMPT_TEMPLATE = """你是张雪峰，以下是关于你的核心设定：
{skill_core}

【当前数据快照：2026 福建高考】
{data_snapshot}

【回答规则】
{answer_rules}
"""
```

**三个变量的来源**（都从 SKILL.md 切片，不要复制原文件全文 — 太长，浪费 token）：

- `skill_core`：SKILL.md 的「身份卡」+「核心心智模型」+「决策启发式」+「表达DNA」段落（约 200-300 行）
- `data_snapshot`：「2026 福建高考数据基准」+「张雪峰 2026 福建选科铁律」+「2025 院校投档线」段落
- `answer_rules`：「回答工作流」+「角色扮演规则」+「红线」段落

实现方式：用 `Path.read_text()`，用 `"\n## "` 切分，按标题匹配段落。**不要**写死行号，这样 SKILL.md 以后改动不会破。

### 4.3 `backend/agent.py`

核心：构造一个 LangChain LCEL chain，流式输出。

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

def build_chain():
    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.model_name,
        streaming=True,
        temperature=0.8,  # 张雪峰要有脾气
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", build_system_prompt()),
        ("user", "{question}"),
    ])
    return prompt | llm | StrOutputParser()

async def stream_answer(question: str) -> AsyncIterator[str]:
    chain = build_chain()
    async for chunk in chain.astream({"question": question}):
        yield chunk
```

### 4.4 `backend/main.py`

FastAPI app：

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from backend.agent import stream_answer

app = FastAPI(title="张雪峰高考志愿 Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP 阶段先放开
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/chat")
async def chat(q: str):
    """流式聊天端点 — 用 SSE 协议"""
    async def event_generator():
        async for token in stream_answer(q):
            # SSE 格式：data: <token>\n\n
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**关键点**：
- 用 GET + query string，简化 CORS（POST 也行，GET 更简单，前端可以用 EventSource 直接连）
- `text/event-stream` 媒体类型
- 关闭 nginx 缓冲（MVP 阶段没 nginx，但加上保险）

### 4.5 启动脚本 `scripts/start.sh`

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")/.."

# 启动后端
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 启动前端 HTTP server（纯静态）
cd frontend
python3 -m http.server 3000 &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
echo "后端 PID $BACKEND_PID 端口 8000"
echo "前端 PID $FRONTEND_PID 端口 3000"
echo "打开 http://localhost:3000"
wait
```

---

## 5. 前端详细规格

### 5.1 UI/UX 设计要求（必须遵守，这是 PM 的硬要求）

**基调**：张雪峰是 41 岁去世的东北大哥，讲话直接、接地气、不装。**UI 也别装**。
- **不要**用渐变色、玻璃拟态、霓虹效果、AI 套版紫蓝渐变
- **不要**用 Inter / Roboto / 系统默认字体 — 选**思源黑体**（Source Han Sans / Noto Sans SC）的**粗体**作为标题
- **配色**（用 OKLCH，这是 ui-ux-design skill 的硬性要求）：
  - 主背景：`oklch(98% 0.005 80)` — 暖白（微微泛黄，像打印纸）
  - 主文字：`oklch(20% 0.01 60)` — 深褐（不是纯黑，带点温度）
  - 强调色：`oklch(55% 0.18 25)` — 砖红（张雪峰风格，不是科技蓝）
  - 用户消息气泡：`oklch(92% 0.01 250)` — 冷灰
  - Agent 消息气泡：透明 + 左边框 `oklch(55% 0.18 25)` 3px
- **字体**：
  - 标题：`'Noto Sans SC', 'Source Han Sans CN', sans-serif` 700
  - 正文：同上 400
  - 等宽数字：`font-variant-numeric: tabular-nums`
- **布局**：
  - 居中聊天框，最大宽 720px
  - **不要**用卡片包一切，头部用一条粗的左边框线 + 标题文字就够了
  - 输入框固定在底部，聊天气泡向上滚动
  - 移动端友好（响应式）
- **动效**：
  - 气泡出现：200ms `ease-out`，只动 `transform: translateY(8px → 0)` + `opacity: 0 → 1`
  - **不要**弹跳、弹性缓动
  - 流式打字时，光标闪烁 — 用一个 `▍` 字符，1s 一次 opacity 切换
- **空状态**：不要"暂无内容"。写一句张雪峰味的话，比如「我跟你说，先把你分数和选科告诉我，别上来就问「学什么好」」

### 5.2 `frontend/index.html`

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>张雪峰 · 高考志愿咨询</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;700;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <main class="chat-container">
        <header class="chat-header">
            <h1>张雪峰</h1>
            <p class="subtitle">高考志愿 · 选科 · 择校 · 用就业倒推法给你说实话</p>
        </header>
        <div id="messages" class="messages" aria-live="polite"></div>
        <form id="chat-form" class="chat-input-bar">
            <textarea
                id="question-input"
                placeholder="说说你多少分、选的什么科、想去哪..."
                rows="1"
                autocomplete="off"
            ></textarea>
            <button type="submit" id="send-btn">问</button>
        </form>
    </main>
    <script src="app.js"></script>
</body>
</html>
```

### 5.3 `frontend/app.js`

核心逻辑（用 `fetch` + `ReadableStream` 读 SSE）：

```javascript
const form = document.getElementById('chat-form');
const input = document.getElementById('question-input');
const messages = document.getElementById('messages');
const sendBtn = document.getElementById('send-btn');

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;

    // 1. 渲染用户消息
    appendMessage('user', q);
    input.value = '';
    sendBtn.disabled = true;

    // 2. 创建空 agent 消息（流式填充）
    const agentBubble = appendMessage('agent', '');
    agentBubble.classList.add('streaming');

    // 3. fetch 流式读取
    try {
        const resp = await fetch(`/api/chat?q=${encodeURIComponent(q)}`);
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            // SSE 解析：data: <token>\n\n
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // 留下不完整的最后一段
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const token = line.slice(6);
                    if (token === '[DONE]') {
                        agentBubble.classList.remove('streaming');
                        continue;
                    }
                    agentBubble.textContent += token;
                    messages.scrollTop = messages.scrollHeight;
                }
            }
        }
    } catch (err) {
        agentBubble.textContent += `\n[出错了: ${err.message}]`;
        agentBubble.classList.remove('streaming');
    } finally {
        sendBtn.disabled = false;
    }
});

function appendMessage(role, text) {
    const div = document.createElement('div');
    div.className = `message message-${role}`;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
}

// 自动撑高 textarea
input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
});
```

### 5.4 `frontend/style.css`

按上面 5.1 的设计要求实现。要点：
- 顶部 header：左边框 4px 砖红，标题用粗体 Noto Sans SC
- 消息气泡：左对齐，不居中，每条消息之间 16px gap
- 用户消息：背景 `oklch(92% 0.01 250)`，内边距 12px 16px，圆角 8px，**靠右对齐**
- Agent 消息：**不**用背景，左边框 3px 砖红，内边距 4px 0 4px 16px，**靠左对齐**
- 流式光标：在 .streaming 的 ::after 伪元素加 ▍
- 输入栏：固定在底部，sticky，不遮消息
- **焦点环**：`outline: none` 绝对禁止，要用 `:focus-visible` 加可见的 outline

---

## 6. 启动流程（PM 视角，你自己跑通就行）

```bash
cd /home/tangzhiang/.copaw/workspaces/coding-agent/workspaces/zhangxuefeng-agent

# 1. uv 初始化
uv init --no-readme --no-workspace .
# （如果 uv init 失败，手动写 pyproject.toml 也行）

# 2. 加依赖
uv add fastapi uvicorn[standard] langchain langchain-core langchain-openai langchain-community sse-starlette python-dotenv

# 3. 写 .env（PM 提供 OPENAI_API_KEY，你自己 echo 进去也行）
echo "OPENAI_API_KEY=sk-cp-xxxx" > .env

# 4. 实现代码（按上面 4.x 和 5.x）

# 5. 启动并自测
bash scripts/start.sh
# 然后另开一个终端： curl "http://localhost:8000/api/chat?q=我考了580分" 应该看到流式输出
```

---

## 7. 验收标准（PM 会按这个验收）

- [ ] `uv sync && bash scripts/start.sh` 一键启动
- [ ] 打开 http://localhost:3000 看到聊天界面
- [ ] 输入「福建物理类 580 分能上什么」能流式打字
- [ ] 回答里**至少有 1 处**提到具体院校/位次/数据（说明 system prompt 真的在生效）
- [ ] 回答口吻是张雪峰（直接、东北味、敢说）
- [ ] UI 不是 AI 套版 — 字体、配色、布局都符合 5.1
- [ ] 没有控制台报错
- [ ] `curl http://localhost:8000/health` 返回 `{"status":"ok"}`

---

## 8. 边界 — 不要做的事

- ❌ 不要写测试用例（MVP 阶段不写）
- ❌ 不要做用户登录/注册
- ❌ 不要做对话历史持久化
- ❌ 不要做 PDF RAG 向量化（让 LLM 直接读 markdown 切片就行）
- ❌ 不要用 React/Vue/任何前端框架
- ❌ 不要用 npm/yarn
- ❌ 不要把 SKILL.md 全文塞 prompt（浪费 token，按 4.2 切三段）
- ❌ 不要写 README 超过 50 行（PM 后面会自己重写）

---

## 9. 风险 & 提示

1. **MiniMax 兼容性问题**：`langchain_openai` 默认假设 OpenAI 格式，`MiniMax-M3` 大部分兼容但偶有 `tool_calls` 字段差异 — 我们**不用** function calling，纯文本对话，没问题。
2. **SSE 跨域**：后端 CORS 已经放开，前端直接 fetch 同源（后端在 8000，前端在 3000，**这是跨域**）— 后端要允许 `http://localhost:3000` 跨域（`allow_origins=["http://localhost:3000"]` 更严格，不要用 `*`，因为前端要带 cookie 时 `*` 不行 — 但 MVP 没 cookie，`*` 也 OK，你看着办）。
3. **流式响应卡顿**：如果 LLM 返回很慢，前端要禁用发送按钮（代码里已经有）。
4. **环境变量**：PM 已经把 `OPENAI_API_KEY` 写在 `~/.bashrc` 里。**优先从环境变量读**（`os.getenv`），再 fallback 到 `.env` 文件（`python-dotenv` 加载）。

---

**写完后，把以下信息回报给 PM**：
1. 项目目录树（`find . -type f -not -path './.venv/*' -not -path './.git/*'`）
2. `uv run uvicorn backend.main:app` 是否能启动（贴最后 5 行）
3. `curl "http://localhost:8000/api/chat?q=你好"` 的输出（前 200 字符）
4. 你觉得哪里设计有问题、需要 PM 决策的点

**开干吧。**
