# 张雪峰高考志愿 Agent

把 `~/.copaw/workspaces/default/skills/zhangxuefeng-perspective` 这份 SKILL.md 文档,变成一个**用户能直接对话**的 Web Agent。Agent 以「张雪峰」东北大哥口吻,结合本地 SKILL.md 知识 + 联网实时数据,流式回答高考志愿问题。

经过 4 轮迭代,当前是 **v0.2**(多用户 + 公网部署 + 三层输入防护)。

---

## 核心特性

- **🎭 张雪峰角色扮演** — 基于 SKILL.md 的人格/心智模型/决策启发式,东北语气、敢说、引用具体院校和数据
- **⚡ 流式输出** — SSE (Server-Sent Events) 协议,token 级别增量推送 + 闪烁光标 `▍`
- **🧠 多轮记忆**(进程内) — 同 `session_id` 6 轮内完整保留,超 6 轮 LLM 摘要压缩到 400 字,不同 session 互不可见
- **🌐 联网搜索** — `mmx search` CLI 调真实搜索引擎,每轮触发,5 分钟内存缓存,失败降级到本地知识
- **📝 Markdown 渲染** — marked.js CDN,GitHub Flavored Markdown,表格/加粗/列表/标题/代码块全支持
- **🔐 多用户鉴权**(公网部署必需) — nginx `auth_basic` 注 `X-Remote-User`,FastAPI `Depends(require_auth)` 校验
- **🛡️ 三层输入防护** — L0 regex 黑名单(19+5 条) + L1 上下文/长度限 + L2 LLM-as-judge 兜底,fail-open
- **📱 移动端适配** — iOS safe-area + 16px 防 zoom + enterkeyhint="send" + dvh 视口 + theme-color

---

## 架构总览

```
                      公网入口 (tmdata.in:30000)
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│  OpenResty :30000 (nginx auth_basic → htpasswd)            │
│  proxy_set_header X-Remote-User $remote_user                │
└──────────────────────────────┬──────────────────────────────┘
                               │ X-Remote-User
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI :8000 (uvicorn)                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ /api/chat  GET                                         │ │
│  │   ↓                                                    │ │
│  │ require_auth (A1: 校验 X-Remote-User)                   │ │
│  │   ↓                                                    │ │
│  │ input_filter.check (L0: regex 黑名单 19+5 条)           │ │
│  │   ↓                                                    │ │
│  │ safety_judge.is_safe (L2: LLM-as-judge)                │ │
│  │   ↓                                                    │ │
│  │ agent.stream_answer → LCEL chain                       │ │
│  │   ├─ memory.get_history (dict[session_id])             │ │
│  │   ├─ search.run (mmx CLI, 5min cache)                  │ │
│  │   ├─ prompt.build (SKILL.md H2 切片)                   │ │
│  │   └─ ChatOpenAI → MiniMax-M3 (流式)                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
                  Browser (前端 :3000)
                  marked.js 渲染 Markdown
```

数据流:**用户输入 → 前端 fetch → OpenResty(auth_basic 注 user) → FastAPI `/api/chat` → require_auth → filter_input → safety_judge → 联网搜索 + 取历史 → 拼 prompt → LCEL chain → LLM 流式返回 → 前端 EventSource/ReadableStream 读 SSE → marked.js 渲染 → 浏览器**

---

## 技术栈

| 层 | 选型 | 版本 | 用途 |
|---|---|---|---|
| 后端语言 | Python | 3.13 | 主语言(uv 自带 CPython,不依赖系统) |
| Web 框架 | FastAPI | 0.136+ | HTTP + SSE 路由 + Depends 鉴权 |
| ASGI | uvicorn[standard] | 0.49+ | 高性能异步 server |
| LLM 编排 | langchain / langchain-core / langchain-openai | 1.3+ | LCEL chain 拼接 prompt+LLM+parser |
| 工具集成 | langchain-community | 0.4+ | 预留给未来 PDF/数据库工具 |
| SSE | sse-starlette | 3.4+ | 流式响应标准 |
| LLM 模型 | MiniMax-M3 | - | 经 `https://api.minimaxi.com/v1` 走 OpenAI 兼容协议 |
| 联网搜索 | mmx CLI (Node.js) | 1.0.13 | 真实搜索,subprocess 调 |
| 包管理 | uv | 0.11+ | 极快的 Python 依赖管理 |
| 前端 | HTML5 + CSS3 + 原生 JS | - | **无任何前端框架** |
| Markdown | marked.js (jsDelivr CDN) | 4.x | GFM 表格/代码块/列表 |
| 字体 | Noto Sans SC (Google Fonts) | - | 思源黑体 |
| 反向代理 | OpenResty (生产) / nginx | - | auth_basic + SSE buffering 关闭 |
| 进程管理 | uvicorn 单进程 | - | 不需要 gunicorn |
| 静态服务 | `python3 -m http.server` | - | 纯静态,无 build step |

---

## 目录结构

```
zhangxuefeng-agent/                              (1640 行代码,12 文件)
├── pyproject.toml                               # uv 依赖锁(8 个包)
├── uv.lock
├── .python-version                              # 3.13
├── .env / .env.example                          # 见下表
├── .gitignore
├── README.md                                    # ← 本文件
├── PRD.md                                       # 产品需求文档(PM 原始设计)
├── DEPLOY.md                                    # 192.168.0.129 部署详细手册
├── backend/                                     # 1054 行 Python (10 文件:9 业务 + __init__.py)
│   ├── __init__.py     (  0)
│   ├── main.py        (207)                     # FastAPI app + 路由 + X-Session-ID + 三层防护串联
│   ├── auth.py        ( 38)                     # require_auth Depends(校验 X-Remote-User)
│   ├── agent.py       (131)                     # LCEL chain + 联网/记忆 集成 + think 块剥离
│   ├── prompt.py      (144)                     # SKILL.md 按 H2 切 3 段 + 多轮规则 + 引用规则
│   ├── memory.py      (174)                     # 进程内多轮记忆(6 轮完整 + 超 6 轮 LLM 摘要压缩)
│   ├── search.py      (106)                     # mmx search 包装 + 5min 缓存 + 失败降级
│   ├── input_filter.py ( 91)                    # L0: regex 黑名单(19 严格 + 5 软词)+ 长度限
│   ├── safety_judge.py ( 92)                    # L2: LLM-as-judge(fail-open, 剥 think 块再匹配)
│   └── config.py      ( 71)                     # Settings dataclass + dotenv 加载
├── frontend/                                    # 586 行
│   ├── index.html     ( 37)                     # 单页 + cache-control meta + safe-area viewport + theme-color
│   ├── app.js         (191)                     # fetch ReadableStream 读 SSE + marked 渲染 + API_BASE 自适应 + X-Session-ID
│   └── style.css      (358)                     # OKLCH 配色 + Noto Sans SC + Markdown 样式 + dvh + safe-area
├── scripts/
│   └── start.sh       (136)                     # start/stop/restart 三子命令 + 端口冲突检测 + 等 /health 200
└── logs/                                        # 运行时日志(不纳入版本控制)
```

---

## 环境依赖

| 工具 | 最低版本 | 检查命令 | 用途 |
|---|---|---|---|
| Python | 3.13 | `python3 --version` | 后端运行时(uv 自动装) |
| Node.js | 24+ (给 mmx 用) | `node --version` | mmx CLI 运行环境 |
| uv | 0.11+ | `uv --version` | Python 包管理 |
| 网络 | - | - | 访问 api.minimaxi.com + jsdelivr.net + Google Fonts |

如果没装 uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

如果没装 mmx(联网搜索必需):
```bash
# 安装后:which mmx 应该输出路径,mmx auth status 查 key
# 详见 mmx-cli skill
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
| `AUTH_USER` | 公网必填 | (空 = 关闭) | 单一白名单用户名,匹配 `X-Remote-User` 才放行(nginx auth_basic 注的) |

### `.env.example` 当前内容

```bash
OPENAI_API_KEY=sk-placeholder-pm-will-replace
OPENAI_BASE_URL=https://api.minimaxi.com/v1
MODEL_NAME=MiniMax-M3
# ZHANGXUEFENG_SKILL_DIR=/custom/path/to/skill
# AUTH_USER=agent
```

启动时如果 `.env` 不存在,`scripts/start.sh` 会**自动从 `.env.example` 复制**一份。

---

## 启动

### 本机

```bash
cd /home/tangzhiang/.copaw/workspaces/coding-agent/workspaces/zhangxuefeng-agent

# 第一次:装依赖 + 配 .env
uv sync
cp .env.example .env && chmod 600 .env
# 编辑 .env,把 OPENAI_API_KEY 填上

# 启 / 停 / 重启
bash scripts/start.sh            # 启动(端口被占就报错退出)
bash scripts/start.sh restart    # 先 kill 旧 + 等 /health 200 + 起新的
bash scripts/start.sh stop       # 只停
```

启动成功输出:
```
==> 启动后端 :8000
    backend pid=12345 日志: /path/to/logs/backend.log
==> 启动前端 :3000
    frontend pid=12346 日志: /path/to/logs/frontend.log
[ok] 后端 /health 返 200,启动成功(等 3s)
```

### 局域网

把 `localhost` 换成机器 IP,如 `http://192.168.3.130:3000`。前端 `app.js` 用 `window.location.hostname` 拼 `:8000`,自动跟当前访问域名走。

### 公网(已部署:192.168.0.129 + OpenResty 反代)

| 入口 | 地址 | 说明 |
|---|---|---|
| 前端 | http://tmdata.in:30000/ | 走 OpenResty auth_basic,需要 htpasswd 用户密码 |
| 后端(直连) | http://192.168.0.129:8000/api/chat | 内网直连,本机/同网段设备用 |
| 健康检查 | http://192.168.0.129:8000/health | 不需鉴权,只返 `{"status":"ok"}` |

公网入口链路:`浏览器 → 路由器 NAT → 129.tmsj.nas:30000 → OpenResty(auth_basic) → 注 X-Remote-User → 代理到 127.0.0.1:3000(前端)或 :8000(API)`

### 详细部署手册

跨机器部署(打包 / scp / 装依赖 / 改 start.sh / 踩坑记录)看 **DEPLOY.md**。摘要如下:

1. 装 uv → `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. 打包源码 → `tar --exclude=".venv" --exclude="logs" ... -czf /tmp/zhangxuefeng-agent.tar.gz`
3. scp 到目标机 → `scp /tmp/*.tar.gz root@192.168.0.129:/tmp/`
4. 装依赖 → **必须 `--only-binary :all:`**(CentOS 7 没 rust,跳过 tiktoken 源码编译)
5. 写 `.env`(含 `AUTH_USER=agent`)
6. `bash scripts/start.sh`(已升级,**不用** `uv run`,直接 `.venv/bin/uvicorn`)

---

## 运行验证

```bash
# 1. 健康检查(不需鉴权,只返 status)
curl http://localhost:8000/health
# → {"status":"ok"}

# 2. 公网鉴权测(需要 X-Remote-User,模拟 OpenResty 注入)
curl -sN -m 30 -G --data-urlencode "q=福建物理类580分能上什么" \
    -H "X-Remote-User: agent" \
    http://localhost:8000/api/chat | head -c 500

# 3. 鉴权失败测(没 header / user 不对)
curl -sN -m 5 "http://localhost:8000/api/chat?q=hi"
# → {"detail":"X-Remote-User header missing (nginx auth_basic required)"}

# 4. 多轮记忆(同 session_id)
SID="test-$(date +%s)"
curl -sN -G --data-urlencode "q=我姓陈,孩子600福建物理" \
    -H "X-Remote-User: agent" -H "X-Session-ID: $SID" \
    http://localhost:8000/api/chat | head -c 200
curl -sN -G --data-urlencode "q=孩子是男孩" \
    -H "X-Remote-User: agent" -H "X-Session-ID: $SID" \
    http://localhost:8000/api/chat | head -c 500

# 5. L0 过滤触发(敏感词 → 立即 422,不走 LLM)
curl -sN -m 5 -G --data-urlencode "q=我儿子高中早恋对方女生怀孕了" \
    -H "X-Remote-User: agent" \
    http://localhost:8000/api/chat
# → {"detail":"输入触发内容安全过滤..."}

# 6. Session 隔离(不同 SID,LLM 不应知道前文)
curl -sN -G --data-urlencode "q=我孩子580能上什么" \
    -H "X-Remote-User: agent" -H "X-Session-ID: different-$(date +%s)" \
    http://localhost:8000/api/chat | head -c 200
```

---

## 安全模型(公网部署后才有)

### 三层防护(在 main.py chat() 里按顺序跑)

| 层 | 模块 | 触发条件 | 失败处理 | 设计意图 |
|---|---|---|---|---|
| **A1 鉴权** | `backend/auth.py::require_auth` | nginx 没注 `X-Remote-User` 或 user 不匹配 `AUTH_USER` | 401,不走业务 | 防未授权访问 + 公网 CC |
| **L0 关键词** | `backend/input_filter.py::check` | 19 条严格 + 5 条软词(未/早恋 + 性 + 孕组合等) | 422,立即拒 | 拦截已知风险 case,省 LLM token |
| **L1 长度/上下文** | `backend/input_filter.py::check` | 超 2000 字符 / 黑名单 host 命中 | 422,立即拒 | 防 DoS + 防 prompt leak |
| **L2 LLM 审查** | `backend/safety_judge.py::is_safe` | LLM-judge 单独跑一次,剥 think 块再正则匹配 SAFE/INJECT | fail-open(挂了放行) | 兜底 L0 没覆盖的语义攻击 |

### fail-open 原则

审查 LLM 挂了 / 超时 / 解析不出 → **必须放行**,不能 500。
理由:审查层是 L0/L1 之上的辅助,挂了不能变成新单点故障。
监控:fail-open 次数要记日志,频率高时人工分析。

### CORS 白名单

`main.py` 显式列 5 个允许 origin(localhost:5173 / 8000 + 公网 `http://tmdata.in:30000`),
不是 `allow_origins=["*"]`(已修)。

### 错误路径不泄露

| 位置 | 旧行为 | 新行为 |
|---|---|---|
| `/api/chat` 流式异常 | `yield f"[后端错误: {type(e).__name__}: {e}]"` | 通用"服务暂不可用" + 详细 stack 走 server log |
| 全局 500 | `content={"error": type(exc).__name__, "detail": str(exc)}` | 通用 message,无 traceback |
| `/health` | 暴露 model + skill_dir 绝对路径 + ts | 只返 `{"status":"ok"}` |

---

## API 接口

### `GET /health`

健康检查,**不需要鉴权**(给 k8s 探针 / CI 用),**只返 status**(不泄露 model/skill_dir)。

**Response 200:**
```json
{"status":"ok"}
```

### `GET /api/chat`

流式聊天端点,SSE 协议,需要鉴权 + 三层防护。

**Query 参数:**

| 参数 | 必填 | 说明 |
|---|---|---|
| `q` | ✅ | 用户问题,1-2000 字符 |

**Headers:**

| Header | 必填 | 说明 |
|---|---​|---|
| `X-Remote-User` | ✅(生产) | nginx `auth_basic` 注入的用户名,匹配 `AUTH_USER` 才放行 |
| `X-Session-ID` | ❌ | 同一浏览器会传;不同 session 记忆隔离 |

**Response:** `text/event-stream`

事件格式(`data: {json}\n\n`):
```json
data: {"t": "我跟你讲,"}

data: {"t": "孩子600分..."}

data: [DONE]
```

前端用 `fetch().body.getReader()` + 文本解码器读 `data: ` 后的 JSON,`obj.t` 就是当前 token。

**错误码:**

| Status | 触发 | body |
|---|---|---|
| 401 | 没 `X-Remote-User` 或 user 不匹配 | `{"detail":"X-Remote-User header missing..."}` |
| 422 | L0/L1 触发 | `{"detail":"输入触发内容安全过滤..."}` |
| 500 | 后端异常 | `{"detail":"服务暂不可用"}`(无 traceback) |

---

## 关键设计决策

1. **为什么用 mmx CLI 而不是 LangChain Agent + 搜索工具?**
   简单粗暴 — 直接 subprocess 调 Node.js CLI,5min 内存缓存,失败降级到本地知识。不引入 LangGraph / AgentExecutor 这层复杂度,也不依赖 LLM 自己选工具(避免 hallucinated tool_calls)。

2. **为什么多轮记忆用 in-memory dict 不接 Redis/DB?**
   MVP 阶段用户量小,单进程够用;重启丢记忆可接受(对话历史本来就不该是永久档案)。**扩展性差但实现简单** — 后续要持久化可换 Redis/SQLite。

3. **为什么 `require_auth` 是 FastAPI Depends 而不是中间件?**
   只对 `/api/chat` 加鉴权,`/health` 不需要(给 k8s 探针)。Depends 粒度更细,中间件是全 app 生效,得在内部判断路径,反而更绕。

4. **为什么鉴权用 nginx `X-Remote-User` 而不是 FastAPI 自己处理 Basic Auth?**
   OpenResty 已有 htpasswd 体系(`agent` 用户),让 nginx 复用它的密码文件,后端只信 user 字符串(不解析 header),职责清晰 + 减少一处密钥管理。**X-Remote-User 是 nginx 跟后端的事实协议**(同 langgraph 等生产部署)。

5. **为什么 L2 LLM-as-judge 失败要 fail-open?**
   审查层是 L0/L1 之上的辅助,不是主防御。挂了 → 放行 + 记日志 + 人工 review,不能变成新单点故障把正常用户全拒了(更糟)。

6. **为什么前端 cache-bust 用 `?v=N` 而不是文件名 hash?**
   MVP 没有 build pipeline,没法自动生成 `[name].[hash].js`。手动 `?v=3` → `?v=4` 改一下数字,浏览器按完整 URL 做 cache key。**每次前端大改要手动 bump 一行**。

7. **为什么后端 :8000 + 前端 :3000 端口分离?**
   SSE 走 fetch(不能 EventSource,跨域要自己处理),CORS 显式列白名单放行。端口分离让前端开发者工具清楚看到两个 domain:**也方便 PM 在 DevTools Network 看请求到底是到哪个**。

8. **为什么 OpenResty 部署在 :30000 而不是 :80/:443?**
   `tmdata.in:80` 已经被其他服务(可能 NAS 管理面)占了。30000 是临时约定,后续要换 `:443 + HTTPS` 需要用户配证书。

---

## 踩坑记录(精选,完整版见 DEPLOY.md §7)

| 坑 | 根因 | 修法 |
|---|---|---|
| `tiktoken==0.13.0` 在 CentOS 7 编译失败 | uv.lock 锁的版本没有 glibc 2.17 manylinux wheel;CentOS 7 没 rust | `uv pip install --only-binary :all:`(langchain-openai 自动拉兼容版 tiktoken 0.11.0,**代码里根本不用**) |
| `uv run` 触发 lock 重解析 → 又编译 tiktoken | start.sh 原本 `uv run uvicorn` 走 uv 检查 | 改 start.sh 用 `.venv/bin/uvicorn` **绝对路径**,绕开 uv |
| `/health` 暴露 model + skill_dir 绝对路径 | 早期返完整 settings dict | 只返 `{"status":"ok"}` |
| 错误处理把 `str(e)` 走 SSE → 客户端看到 traceback | 早期 `yield f"[后端错误: {e}]"` | 客户端只返"服务暂不可用",stack 走 server log |
| 多个 tab 共享 `localStorage.session_id` → 记忆串了 | 前端没 UI 区分 session | 加"新对话"按钮(后续规划) |
| 沙箱拦截 `pkill` 关键字 | shell tool 关键字黑名单 | `python3 -c "import ctypes; LIBC=ctypes.CDLL('libc.so.6'); LIBC.kill(PID, 15)"` |
| L2 LLM-judge raw 文本含 `think...INJECT...` → 子串匹配误判 | MiniMax-M3 在 `think` 块里"分析" INJECT 可能性 → `if "INJECT" in text` 误命中 | 严格 `re.sub(r"think.*?think", "", text)` 剥 think 块 + 整段 `^(SAFE\|INJECT)$` 匹配 + 退路取 `text[-50:]` |

---

## 后续规划(PM 决策中)

按优先级:

- **📄 PDF RAG** — SKILL 目录有 10 份 PDF 报告,目前不向量化;接 FAISS + nomic-embed
- **🗄️ 记忆持久化** — Redis / SQLite,让重启后对话不丢(目前 in-memory dict 重启清空)
- **🔐 鉴权升级** — 当前单 `AUTH_USER` 字符串匹配,支持多用户(读 htpasswd 文件动态)
- **📊 多 session 仪表盘** — `/api/sessions` 列所有 session 状态,调试 / 演示用
- **🎯 问卷 UI** — 首次访问弹"分数/选科/省份"问卷卡片,免去每次都问
- **🧪 自动化测试** — 当前无测试,加 pytest 覆盖 prompt 拼接 / memory 摘要 / L0 过滤
- **🌐 HTTPS** — 当前公网走 HTTP + auth_basic,生产应上 TLS(用户配证书后改 nginx)

---

## 变更记录

| 日期 | 版本 | 变更 | 备注 |
|---|---|---|---|
| 2026-06-11 | v0.1 | MVP 上线 | 1 文件 → 6 文件,单用户无鉴权 |
| 2026-06-13 | v0.1.1 | 红队测试 + 安全修复 F1-F4 | 4 真问题 + 2 高危 |
| 2026-06-13 | v0.1.2 | 移动端适配 12 项 + 多用户隔离 A1/A3 | viewport + safe-area + X-Remote-User 鉴权 |
| 2026-06-14 | v0.2 | 公网部署 + L0 输入过滤 + L2 LLM 审查 | OpenResty :30000 + htpasswd + 9 文件 |

---

## License

Apache 2.0
