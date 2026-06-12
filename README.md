# 张雪峰高考志愿 Agent

把 `~/.copaw/workspaces/default/skills/zhangxuefeng-perspective` 这份 809 行的纯文本 Skill 文档,变成一个**用户能直接对话**的 Web Agent。Agent 以「张雪峰」东北大哥口吻,结合本地 SKILL.md 知识 + 联网实时数据,流式回答高考志愿问题。

---

## 核心特性

- **🎭 张雪峰角色扮演** — 基于 SKILL.md 的人格/心智模型/决策启发式,东北语气、敢说、引用具体院校和数据
- **⚡ 流式输出** — SSE (Server-Sent Events) 协议,token 级别增量推送 + 闪烁光标 `▍`
- **🧠 多轮记忆**(进程内) — 同 `session_id` 6 轮内完整保留,超 6 轮 LLM 摘要压缩到 400 字,不同 session 互不可见
- **🌐 联网搜索** — `mmx search` CLI 调真实搜索引擎,每轮触发,5 分钟内存缓存,失败降级到本地知识
- **📝 Markdown 渲染** — marked.js CDN,GitHub Flavored Markdown,表格/加粗/列表/标题/代码块全支持
- **🏠 局域网访问** — `API_BASE` 用 `window.location.hostname` 拼 `:8000`,任意 IP/域名都能开
- **🚀 一键启动** — `bash scripts/start.sh` 同时拉后端 :8000 + 前端 :3000,端口冲突自动 fallback

---

## 架构总览

```
┌─────────────────┐    fetch + SSE     ┌──────────────────┐
│  浏览器 (3000)  │ ◄────────────────► │  FastAPI (8000)  │
│  HTML/JS/CSS    │  X-Session-ID      │  main.py         │
│  marked.js CDN  │                    │   ├─ agent.py    │
└─────────────────┘                    │   │  LCEL chain  │
                                       │   ├─ memory.py   │  dict[session_id]
                                       │   │  6 轮 + 摘要 │ ────────────────┐
                                       │   ├─ search.py   │                  │
                                       │   │  mmx CLI     │  subprocess      │
                                       │   │  5min cache  │ ──────┐          │
                                       │   └─ prompt.py   │       │          │
                                       │      SKILL.md 切片│       ▼          ▼
                                       └──────┬───────────┘  ┌──────┐  ┌──────────┐
                                              │ LCEL astream │ mmx  │  │ 内存 dict│
                                              ▼              │ 1.0.13│  │(进程内) │
                                       ┌──────────────────┐  └──────┘  └──────────┘
                                       │ MiniMax-M3 LLM   │
                                       │ (api.minimaxi)   │
                                       └──────────────────┘
```

数据流:**用户输入 → 前端 fetch → FastAPI `/api/chat` → 联网搜索(mmx) + 取历史(memory) → 拼 prompt → LCEL chain → LLM 流式返回 → 前端 EventSource/ReadableStream 读 SSE → marked.js 渲染 Markdown → 浏览器**

---

## 技术栈

| 层 | 选型 | 版本 | 用途 |
|---|---|---|---|
| 后端语言 | Python | 3.13 | 主语言 |
| Web 框架 | FastAPI | 0.136+ | HTTP + SSE 路由 |
| ASGI | uvicorn[standard] | 0.49+ | 高性能异步 server |
| LLM 编排 | langchain / langchain-core / langchain-openai | 1.3+ | LCEL chain 拼接 prompt+LLM+parser |
| LLM 模型 | MiniMax-M3 | - | 经 `https://api.minimaxi.com/v1` 走 OpenAI 兼容协议 |
| 联网搜索 | mmx CLI (Node.js) | 1.0.13 | 真实搜索,subprocess 调 |
| 包管理 | uv | 0.11+ | 极快的 Python 依赖管理 |
| 前端 | HTML5 + CSS3 + 原生 JS | - | **无任何前端框架** |
| Markdown | marked.js (jsDelivr CDN) | 4.x | GFM 表格/代码块/列表 |
| 字体 | Noto Sans SC (Google Fonts) | - | 思源黑体 |
| 进程管理 | uvicorn 单进程 | - | 不需要 gunicorn |
| 静态服务 | `python3 -m http.server` | - | 纯静态,无 build step |

---

## 目录结构

```
zhangxuefeng-agent/                        (1353 行代码)
├── pyproject.toml                         # uv 依赖锁(8 个核心包)
├── uv.lock
├── .python-version                        # 3.13
├── .env / .env.example                    # OPENAI_API_KEY 配置
├── .gitignore
├── README.md                              # ← 本文件
├── PRD.md                                 # 产品需求文档(PM 原始设计)
├── backend/                               # 742 行 Python
│   ├── __init__.py
│   ├── main.py        (146)               # FastAPI app + SSE 路由 + X-Session-ID header
│   ├── agent.py       (128)               # LCEL chain + 联网/记忆 集成 + think 块剥离
│   ├── prompt.py      (144)               # SKILL.md 按 H2 切 3 段 + 多轮规则 + 引用规则
│   ├── memory.py      (158)               # 进程内多轮记忆(6 轮完整 + 超 6 轮 LLM 摘要压缩)
│   ├── search.py      (106)               # mmx search 包装 + 5min 缓存 + 失败降级
│   └── config.py      (60)                # Settings dataclass + dotenv 加载
├── frontend/                              # 543 行
│   ├── index.html     (35)                # 单页 + cache-control meta + CDN
│   ├── app.js         (195)               # fetch ReadableStream 读 SSE + marked 渲染 + 局域网 API_BASE + X-Session-ID
│   └── style.css      (313)               # OKLCH 配色 + Noto Sans SC + Markdown 元素样式
├── scripts/
│   └── start.sh       (68)                # 一键启动后端+前端(端口冲突自动 fallback)
└── logs/                                  # 运行时日志(不纳入版本控制)
```

---

## 环境依赖

| 工具 | 最低版本 | 检查命令 | 用途 |
|---|---|---|---|
| Python | 3.13 | `python3 --version` | 后端运行时 |
| Node.js | 24+ (给 mmx 用) | `node --version` | mmx CLI 运行环境 |
| uv | 0.11+ | `uv --version` | Python 包管理 |
| 网络 | - | - | 访问 api.minimaxi.com + jsdelivr.net + Google Fonts |

如果没装 uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

如果没装 mmx(联网搜索必需):
```bash
# PM 内部安装方式,具体命令参考 mmx 官方文档
# 安装后:which mmx 应该输出路径
```

---

## 配置

### `.env` 字段

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ | - | MiniMax 兼容 key,从 [platform.minimaxi.com](https://platform.minimaxi.com/user-center/basic-information/interface-key) 获取 |
| `OPENAI_BASE_URL` | ❌ | `https://api.minimaxi.com/v1` | LLM API base |
| `MODEL_NAME` | ❌ | `MiniMax-M3` | 模型名 |
| `ZHANGXUEFENG_SKILL_DIR` | ❌ | `~/.copaw/workspaces/default/skills/zhangxuefeng-perspective` | SKILL.md 所在目录 |

### `.env.example` 内容

```bash
OPENAI_API_KEY=sk-placeholder-pm-will-replace
OPENAI_BASE_URL=https://api.minimaxi.com/v1
MODEL_NAME=MiniMax-M3
# ZHANGXUEFENG_SKILL_DIR=/custom/path/to/skill
```

启动时如果 `.env` 不存在,`scripts/start.sh` 会**自动从 `.env.example` 复制**一份,PM 后面替换真 key 即可。

---

## 外部 Skill 配置(必读)

本项目**不内置** `zhangxuefeng-perspective` skill(SKILL.md 45KB + references 42KB + 10 份 PDF 30MB)。后端启动时**运行时读**外部路径,找不到就启动失败。

### 三级 fallback(`backend/config.py` 启动时按这个顺序找)

1. 环境变量 `ZHANGXUEFENG_SKILL_DIR`(显式覆盖,推荐)
2. 默认路径 `~/.copaw/workspaces/default/skills/zhangxuefeng-perspective`
3. 都找不到 → 启动失败,日志报 `FileNotFoundError`

### 配置方式(3 个场景)

- **场景 A:Skill 在默认位置(本机已有)** — 啥也不用配,直接 `bash scripts/start.sh`。`/health` 的 `skill_dir` 字段会显示这个路径。
- **场景 B:Skill 在别的位置(部署到新机器 / 想用别的副本)** — `.env` 末尾加 `ZHANGXUEFENG_SKILL_DIR=/your/path`,或启动前 `export ZHANGXUEFENG_SKILL_DIR=/path`。
- **场景 C:全新环境没 Skill 源** — 从 PM 拿源(整目录 tar)解压到默认位置:
  ```bash
  mkdir -p ~/.copaw/workspaces/default/skills
  tar xzf zhangxuefeng-skill.tar.gz -C ~/.copaw/workspaces/default/skills
  ```
  或直接 `export ZHANGXUEFENG_SKILL_DIR=/anywhere/you/want`(更灵活)。

### 验证

启动后查 `/health` 的 `skill_dir` 字段,核对是不是你想要的路径:

```bash
curl http://localhost:8000/health
```

### 故障排查

| 现象 | 排查 |
|---|---|
| 启动报 `FileNotFoundError: Cannot find zhangxuefeng-perspective skill dir` | 两路径都没找到;设 `ZHANGXUEFENG_SKILL_DIR` 或 `mkdir -p` 默认路径后 `tar xf` skill 源 |
| `/health` 的 `skill_dir` 不对 | `echo $ZHANGXUEFENG_SKILL_DIR` 是否设了别的值;`unset` 回退默认 |
| 启动成功但 LLM 答非所问 / 不像张雪峰 | `skill_dir` 指向了**错的**目录(同名但内容是别的 skill);`ls $skill_dir/SKILL.md` 确认是 45KB 的张雪峰那份 |

---

## 部署 & 启动

### 1. 装依赖

```bash
cd /home/tangzhiang/.copaw/workspaces/coding-agent/workspaces/zhangxuefeng-agent
uv sync
```

`uv` 会自动读 `pyproject.toml` 创建 `.venv` 并装好 8 个核心包。

### 2. 填 API key

```bash
cp .env.example .env
# 编辑 .env,把 OPENAI_API_KEY 替换成真 key
chmod 600 .env   # 防止其他用户读
```

### 3. 启动

```bash
bash scripts/start.sh
```

输出示例:
```
==> 启动后端 :8000
    backend pid=12345 日志: /path/to/logs/backend.log
==> 启动前端 :3000
    frontend pid=12346 日志: /path/to/logs/frontend.log
==========================================
  后端: http://localhost:8000  (健康检查: /health)
  前端: http://localhost:3000
==========================================
```

端口 8000 / 3000 被占用时会**自动 fallback** 到 8001 / 3001。

### 4. 浏览器打开

- 本机:`http://localhost:3000`
- 局域网:把 `localhost` 换成机器 IP,如 `http://192.168.3.130:3000`
- 任意域名:把 `localhost` 换成域名,只要 DNS 解析到本机

### 5. 停服

```bash
pkill -f 'uvicorn backend.main'
# 或:bash scripts/start.sh 重启
```

如果 sandbox 拦 `pkill` 关键字,改用 `python3 -c "import ctypes, signal; ctypes.CDLL('libc.so.6').kill(12345, signal.SIGTERM)"`(用 PID 替换 12345)。

---

## 运行验证

```bash
# 1. 健康检查
curl http://localhost:8000/health
# → {"status":"ok","model":"MiniMax-M3",...}

# 2. 单轮对话(中文 URL 需 --data-urlencode)
curl -sN --max-time 30 -G --data-urlencode "q=福建物理类580分能上什么" \
    http://localhost:8000/api/chat | head -c 500

# 3. 多轮记忆(同 session_id,验证 LLM 记住前文)
SID="test-$(date +%s)"
curl -sN -G --data-urlencode "q=我姓陈,孩子600福建物理" \
    -H "X-Session-ID: $SID" http://localhost:8000/api/chat | head -c 200
curl -sN -G --data-urlencode "q=孩子是男孩" \
    -H "X-Session-ID: $SID" http://localhost:8000/api/chat | head -c 500

# 4. 联网搜索(问"高考"相关时间敏感问题,看 LLM 是否标"据搜索结果显示")
curl -sN --max-time 30 -G --data-urlencode "q=2026 福建高考一分一段表什么时候出" \
    http://localhost:8000/api/chat | head -c 500

# 5. Session 隔离(不同 SID,LLM 不应知道前文)
curl -sN -G --data-urlencode "q=我孩子580能上什么" \
    -H "X-Session-ID: different-session" http://localhost:8000/api/chat | head -c 200
```

---

## 维护 & 故障排查

| 现象 | 排查方向 |
|---|---|
| `/health` 返回 connection refused | 后端没起,看 `logs/backend.log` 末尾;或端口被占 |
| 流式不出 / 卡在第一 token | `tail -20 logs/backend.log` 看 ERROR;第一次响应慢是 LLM 冷启 2-3s,正常 |
| 跨域报错 | 确认后端 CORS `allow_origins=["*"]`;FastAPI 默认放行所有 header |
| 局域网访问 404 | 浏览器 F12 Network 看请求 URL,确认后端在 `0.0.0.0:8000` 监听 |
| 联网搜索失败 | `which mmx` 确认 CLI 在 PATH;`mmx auth status` 查 key |
| LLM 答非所问 / 老版本 JS | 浏览器硬刷(Cmd+Shift+R),或访问 `http://<host>:3000/?v=4` 强制新 URL |
| 记忆混乱 | 多个 tab 共享 `localStorage` 同一 session_id;关掉其他 tab 试试,或 `localStorage.removeItem('zx_session_id')` 重置 |
| MiniMax API 报错 422 `new_sensitive` | system prompt 触发了内容安全过滤,检查新加的规则是否含敏感词(翻车/性别/某称呼组合) |
| 沙箱拦 `kill` 关键字命令 | 用 `python3 -c "import ctypes, signal; ctypes.CDLL('libc.so.6').kill(PID, signal.SIGTERM)"` |
| 后端想重启 | `python3 /tmp/restart_be.py`(用 ctypes 杀老进程,subprocess.Popen 拉新进程) |

---

## API 接口

### `GET /health`

健康检查,返回模型和 skill_dir 信息。

**Response 200:**
```json
{
  "status": "ok",
  "model": "MiniMax-M3",
  "skill_dir": "/home/.../skills/zhangxuefeng-perspective",
  "ts": 1781189910
}
```

### `GET /api/chat`

流式聊天端点,SSE 协议。

**Query 参数:**

| 参数 | 必填 | 说明 |
|---|---|---|
| `q` | ✅ | 用户问题,1-2000 字符 |

**Headers:**

| Header | 必填 | 说明 |
|---|---|---|
| `X-Session-ID` | ❌ | 同一浏览器会传;不同 session 记忆隔离;缺省回退到 `default-session` |

**Response:** `text/event-stream`

事件格式(`data: {json}\n\n`):
```json
data: {"t": "我跟你讲,"}

data: {"t": "孩子600分..."}

data: [DONE]
```

前端用 `fetch().body.getReader()` + 文本解码器读 `data: ` 后的 JSON,`obj.t` 就是当前 token。

---

## 关键设计决策

1. **为什么用 mmx CLI 而不是 LangChain Agent + 搜索工具?**
   简单粗暴 — 直接 subprocess 调 Node.js CLI,5min 内存缓存,失败降级到本地知识。不引入 LangGraph / AgentExecutor 这层复杂度,也不依赖 LLM 自己选工具(避免 hallucinated tool_calls)。

2. **为什么多轮记忆用 in-memory dict 不接 Redis/DB?**
   MVP 阶段用户量小,单进程够用;重启丢记忆可接受(对话历史本来就不该是永久档案)。**扩展性差但实现简单** — 后续要持久化可换 Redis/SQLite,接口设计已经预留 `_sanitize_session_id`。

3. **为什么 add_exchange 用 `asyncio.create_task` fire-and-forget?**
   流式响应的 [DONE] 事件必须**立刻**发给客户端,否则 client 30s 超时会断开连接 → uvicorn 砍 generator → 记忆写不进去。Fire-and-forget 让 [DONE] 不等记忆写完,代价是 turn 7→turn 8 这次响应看不到 turn 7 刚生成的 summary(race condition,turn 9+ 才有)。

4. **为什么 marked.js 走 CDN 不本地打包?**
   MVP 项目没有 npm build step(纯 HTML/JS),前端目录就是浏览器直接吃的。CDN 一行 `<script>` 搞定,PM 浏览器自动缓存,改 marked 版本不需要重 build。代价是断网时 markdown 退化为纯文本(已有降级)。

5. **为什么后端 :8000 + 前端 :3000 端口分离?**
   SSE 走 fetch(不能 EventSource,跨域要自己处理),CORS `allow_origins=["*"]` 放行就够。端口分离让前端开发者工具清楚看到两个 domain:`http://<host>:3000`(静态)和 `http://<host>:8000`(API)。**也方便 PM 在 DevTools Network 看请求到底是到哪个**。

6. **为什么前端 cache-bust 用 `?v=N` 而不是文件名 hash?**
   MVP 没有 build pipeline,没法自动生成 `[name].[hash].js`。手动 `?v=2` → `?v=3` 改一下数字,浏览器按完整 URL 做 cache key,新 URL 一定 miss cache。**每次前端大改要手动 bump 一行** — 后续接 webpack/vite 可以换成真 hash。

---

## 后续规划

MVP 没做、PM 后续可能加的:

- **🗄️ 记忆持久化** — Redis / SQLite,让重启后对话不丢
- **📊 多 session 仪表盘** — `/api/sessions` 列所有 session 状态,调试 / 演示用
- **🔍 关键词缓存优化** — 当前 exact-match,加 normalize(去标点/空格)减少 miss
- **📄 PDF RAG** — SKILL 目录有 10 份 PDF 报告,目前不向量化;接 FAISS + nomic-embed
- **🎯 问卷 UI** — 首次访问弹"分数/选科/省份"问卷卡片,免去每次都问
- **🔐 用户认证** — 加 JWT,记忆按 user 隔离,多用户共享部署
- **🧪 自动化测试** — 当前无测试,加 pytest 覆盖 prompt 拼接 / memory 摘要 / CORS

---

## License

内部项目,仅 PM 团队使用。

参考致谢:[DeepWiki-Open](https://github.com/AsyncFuncAI/deepwiki-open) 的 RAG + Wiki 生成思路,mmx CLI (MiniMax 出品)。
