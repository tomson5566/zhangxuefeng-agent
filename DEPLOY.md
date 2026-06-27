# 部署文档：zhangxuefeng-agent（192.168.0.129）

> 📅 最近部署：2026-06-14（v0.2 公网部署）
> 🖥️ 目标机器：**192.168.0.129** (`129.tmsj.nas`，CentOS Linux 7 x86_64)
> 🌐 网络：局域网 192.168.0.0/24 + 公网 tmdata.in:30000（OpenResty 反代）

## 0. 一句话总结

张雪峰高考志愿 Agent 服务已部署到 `129.tmsj.nas`，**三层架构**：

| 入口 | 地址 | 走法 |
|---|---|---|
| 前端（聊天界面） | http://tmdata.in:30000/ | 公网 → OpenResty :30000 → FastAPI :3000 |
| 前端（内网） | http://192.168.0.129:3000 | 直连 :3000（python http.server） |
| 后端 API | http://192.168.0.129:8000/api/chat | 直连 :8000（uvicorn，需鉴权头） |
| 健康检查 | http://192.168.0.129:8000/health | 不需鉴权，只返 status |

打开浏览器访问 `http://tmdata.in:30000/`（公网）或 `http://192.168.0.129:3000/`（内网）即可使用，浏览器会自动按当前域名/IP 拼 `:8000` 后端地址。

---

## 1. 部署架构

```
                                  公网 tmdata.in:30000
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────┐
│  OpenResty :30000 (nginx + lua,带 auth_basic)               │
│  ├─ 静态 / → proxy_pass 192.168.0.129:3000                  │
│  ├─ /api/ → proxy_pass 192.168.0.129:8000                   │
│  │           proxy_set_header X-Remote-User $remote_user    │
│  │           proxy_buffering off  ← SSE 必须关 buffering     │
│  └─ htpasswd 文件:/etc/openresty/htpasswd (用户: agent)     │
└──────────────────────────────┬──────────────────────────────┘
                               │ X-Remote-User
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  192.168.0.129 (CentOS 7.9, 7.8G RAM, 30G 可用)             │
│                                                             │
│  /opt/zhangxuefeng-agent/                                   │
│  ├── backend/        # FastAPI 应用（uvicorn）               │
│  │   ├── main.py     # /api/chat + /health + 三层防护串联  │
│  │   ├── auth.py     # require_auth (校验 X-Remote-User)   │
│  │   ├── input_filter.py  # L0 regex 黑名单               │
│  │   ├── safety_judge.py  # L2 LLM-as-judge               │
│  │   └── ...                                              │
│  ├── frontend/       # 静态 HTML/CSS/JS（python http.server）│
│  │   ├── index.html                                         │
│  │   ├── style.css                                          │
│  │   └── app.js     # 前端聊天逻辑 + X-Session-ID         │
│  ├── skills/                                             │
│  │   └── zhangxuefeng-perspective/  # SKILL.md 文档       │
│  ├── .venv/          # 独立虚拟环境（uv 管理，CPython 3.13） │
│  ├── logs/           # 运行日志                              │
│  ├── .env            # 运行时配置（含 OPENAI_API_KEY + AUTH_USER）│
│  └── scripts/                                            │
│      └── start.sh    # start|stop|restart 三子命令       │
└─────────────────────────────────────────────────────────────┘
```

**关键设计**：
- 依赖**完全隔离**在 `.venv/` 里，跟系统 Python 互不影响（CentOS 7 根本没有系统 Python 3）
- 不依赖 `/opt/halo/.env` 或本机任何配置文件
- 前端 `app.js` 用 `window.location.hostname` 拼后端地址 → 任意主机名/IP 都能正确访问
- **公网入口走 OpenResty auth_basic**（复用已有 htpasswd 体系），后端 `require_auth` 依赖 nginx 注的 `X-Remote-User` header（不解析 Authorization）
- 后端 `require_auth` 在 `AUTH_USER` 为空时**关闭鉴权**（向后兼容，仅本地开发用）

---

## 2. 前置条件

### 2.1 目标机器需要具备

| 项 | 要求 | 当前状态 |
|---|---|---|
| 操作系统 | Linux x86_64（CentOS 7 / RHEL 7 / 类似） | ✅ CentOS 7.9 |
| 网络 | 能访问 `api.minimaxi.com`（模型 API） | ✅ |
| SSH | root 账号（已配免密） | ✅ |
| 磁盘 | 至少 1GB 可用 | ✅ 30GB |
| 内存 | 至少 2GB | ✅ 6.5GB |
| OpenResty | 公网入口用，本地开发不需要 | ✅ 已装（用户自管） |
| htpasswd | 公网入口用 | ✅ 用户 `agent` 已配 |

### 2.2 源端（本机）需要具备

- `uv`（[Astral uv](https://github.com/astral-sh/uv)）— 用来同步 `.venv`
- `tar` / `scp` / `ssh` — 基础工具
- 已配好 `~/.ssh/id_rsa.pub` 到 192.168.0.129 的免密登录

---

## 3. 完整部署步骤

> 适用于**全新部署**或**重新部署**（重新部署会自动覆盖代码，但 `.env` 由 `cat > EOF` 覆盖，详见坑 4）。

### 3.1 在本机打包源码

```bash
cd /home/tangzhiang/.copaw/workspaces/coding-agent/workspaces

# 打包项目（排除 .venv / logs / pyc / .git）
tar --exclude=".venv" --exclude="logs" --exclude="__pycache__" \
    --exclude="*.pyc" --exclude=".git" \
    -czf /tmp/zhangxuefeng-agent.tar.gz zhangxuefeng-agent/

# 打包 skill（24MB，含 SKILL.md 和 docs/references）
tar -czf /tmp/zhangxuefeng-perspective.tar.gz \
    -C /home/tangzhiang/.copaw/workspaces/default/skills/ \
    zhangxuefeng-perspective/
```

### 3.2 scp 到目标机

```bash
scp /tmp/zhangxuefeng-agent.tar.gz /tmp/zhangxuefeng-perspective.tar.gz \
    root@192.168.0.129:/tmp/
```

### 3.3 在 129 上装 uv

```bash
ssh root@192.168.0.129 'curl -LsSf https://astral.sh/uv/install.sh | sh'
```

> uv 会自动下载 CPython 3.13 到 `~/.local/share/uv/python/`。
> 不需要 yum 装 python3-devel / gcc / make 等系统包。

### 3.4 解压项目骨架

```bash
ssh root@192.168.0.129 '
mkdir -p /opt/zhangxuefeng-agent/skills
cd /opt/zhangxuefeng-agent
tar -xzf /tmp/zhangxuefeng-agent.tar.gz --strip-components=1
tar -xzf /tmp/zhangxuefeng-perspective.tar.gz -C /opt/zhangxuefeng-agent/skills/
'
```

### 3.5 装项目依赖（重点！）

> ⚠️ **不要直接跑 `uv sync`**，会卡在 `tiktoken==0.13.0` 源码编译（CentOS 7 没 rust）。
> 用 `--only-binary :all:` 强制只装预编译 wheel，避开 tiktoken 编译。

```bash
ssh root@192.168.0.129 'bash -s' <<'REMOTE'
export PATH=$HOME/.local/bin:$PATH
cd /opt/zhangxuefeng-agent

# 建 venv
uv venv --python 3.13 .venv

# 装主依赖（8 个包）
# langchain-openai 会自动拉兼容版 tiktoken 0.11.0
uv pip install --python .venv/bin/python --only-binary :all: \
    "fastapi>=0.136.3" \
    "langchain>=1.3.7" \
    "langchain-community>=0.4.2" \
    "langchain-core>=1.4.6" \
    "python-dotenv>=1.2.2" \
    "sse-starlette>=3.4.4" \
    "uvicorn[standard]>=0.49.0"

uv pip install --python .venv/bin/python --only-binary :all: \
    "langchain-openai>=1.3.0"
REMOTE
```

> **变更(v0.2)**：比 v0.1 多了 `langchain-community`（为未来 PDF RAG 预留）。

### 3.6 写 `.env`

```bash
ssh root@192.168.0.129 '
cat > /opt/zhangxuefeng-agent/.env <<EOF
OPENAI_API_KEY=sk-cp-sZ64ZqRUaVEI5Iu8IxvC96srw0vwemeWmc12ejJyIcVHVDz_CHJ7uuNknO9p-sCGr9oAxNUiHMJMjCYuIvSeb3MsD_o95fgm9v4-j-2-cGsohzrQCRjnCj4
OPENAI_BASE_URL=https://api.minimaxi.com/v1
MODEL_NAME=MiniMax-M3
ZHANGXUEFENG_SKILL_DIR=/opt/zhangxuefeng-agent/skills/zhangxuefeng-perspective
AUTH_USER=agent
EOF
chmod 600 /opt/zhangxuefeng-agent/.env
'
```

> ⚠️ **`OPENAI_API_KEY` 务必替换为生产 key**。当前用的是占位/测试 key。
> ⚠️ **`AUTH_USER=agent` 公网部署必填**，对应 htpasswd 文件里的用户名。后端 `require_auth` 会校验 nginx 注的 `X-Remote-User == AUTH_USER`，不匹配返 401。

### 3.7 配置 OpenResty 反代（公网入口）

> 这步**用户自管**（用户红线），不在自动化部署脚本里。仅给参考配置。

```nginx
# /usr/local/openresty/nginx/conf/conf.d/zhangxuefeng.conf
server {
    listen 30000;
    server_name tmdata.in;

    # htpasswd 鉴权（密码文件路径由用户决定）
    auth_basic "agent login";
    auth_basic_user_file /etc/openresty/htpasswd;

    # 静态前端
    location / {
        proxy_pass http://192.168.0.129:3000;
        proxy_set_header Host $host;
    }

    # API + SSE
    location /api/ {
        proxy_pass http://192.168.0.129:8000;
        proxy_buffering off;             # SSE 必须关 buffering
        proxy_cache off;
        proxy_set_header X-Accel-Buffering no;
        # 关键:把 auth_basic 通过的用户名注给后端
        proxy_set_header X-Remote-User $remote_user;
        proxy_set_header Host $host;
    }
}
```

启用：
```bash
ssh root@192.168.0.129 '/usr/local/openresty/nginx/sbin/nginx -t && /usr/local/openresty/nginx/sbin/nginx -s reload'
```

### 3.8 启动服务

```bash
ssh root@192.168.0.129 'cd /opt/zhangxuefeng-agent && bash scripts/start.sh'
```

期望输出：

```
==> 启动后端 :8000
    backend pid=10540 日志: /opt/zhangxuefeng-agent/logs/backend.log
==> 启动前端 :3000
    frontend pid=10541 日志: /opt/zhangxuefeng-agent/logs/frontend.log
[ok] 后端 /health 返 200,启动成功(等 3s)
```

`start.sh` 行为：
- 默认端口被占 → **报错退出**（不再静默换端口，避免部署漂移）
- 显式 `bash scripts/start.sh restart` → 先 kill 旧 + 等 `/health` 200 + 起新的（最多 15s）

---

## 4. 验证清单

部署完成后，按顺序跑：

### 4.1 健康检查（内网，不需鉴权）

```bash
curl -s http://192.168.0.129:8000/health
```

期望：
```json
{"status":"ok"}
```

> v0.2 变更：旧版还返 model + skill_dir + ts，**已修**：只返 status（避免泄露服务器路径/版本）。

### 4.2 前端可达（内网）

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://192.168.0.129:3000/
```

期望：`HTTP 200`

### 4.3 端到端聊天测试（内网，需要鉴权头）

```bash
# 模拟 OpenResty 注的 X-Remote-User
curl -sN -m 30 -H "X-Session-ID: test-1" \
  -H "X-Remote-User: agent" \
  "http://192.168.0.129:8000/api/chat?q=福建物理类580分能上什么" \
  | head -c 500
```

期望：流式 SSE `data: {"t": "..."}` 帧，张雪峰风格回答。

### 4.4 公网入口验证

```bash
# 公网走 OpenResty,带 basic auth
curl -s -u agent:<htpasswd-password> \
    http://tmdata.in:30000/ -o /dev/null -w "前端 HTTP %{http_code}\n"

# 公网 API 鉴权链通(看 X-Remote-User 是否被注入到后端)
curl -sN -m 30 -u agent:<htpasswd-password> \
    "http://tmdata.in:30000/api/chat?q=福建580能上啥" | head -c 300
```

期望：两个都返 200 / SSE 流。

### 4.5 鉴权失败验证

```bash
# 没注 X-Remote-User → 401
curl -sN -m 5 "http://192.168.0.129:8000/api/chat?q=hi"

# user 不匹配 → 401
curl -sN -m 5 -H "X-Remote-User: hacker" \
    "http://192.168.0.129:8000/api/chat?q=hi"
```

期望：
```json
{"detail":"X-Remote-User header missing (nginx auth_basic required)"}
```

### 4.6 L0 输入过滤验证

```bash
# 含敏感词 → 422,立即拒
curl -sN -m 5 -H "X-Remote-User: agent" \
    "http://192.168.0.129:8000/api/chat?q=我儿子高中早恋对方女生怀孕了"
```

期望：
```json
{"detail":"输入触发内容安全过滤..."}
```

### 4.7 浏览器验证

- 内网：`http://192.168.0.129:3000/`
- 公网：`http://tmdata.in:30000/`（弹 htpasswd 框，输入 agent + 密码）

看到聊天界面 + 输入问题 → 模型实时打字 = 部署成功。

---

## 5. 日常运维

### 5.1 启动 / 停止 / 重启（v0.2 推荐）

```bash
# 启动(端口被占就报错退出)
ssh root@192.168.0.129 'cd /opt/zhangxuefeng-agent && bash scripts/start.sh'

# 重启(先 kill 旧 + 等 /health 200 + 起新的,最多 15s)
ssh root@192.168.0.129 'cd /opt/zhangxuefeng-agent && bash scripts/start.sh restart'

# 停止(只停,不起)
ssh root@192.168.0.129 'cd /opt/zhangxuefeng-agent && bash scripts/start.sh stop'
```

> **变更(v0.2)**：v0.1 用 `pgrep + kill + bash start.sh` 三段拼接，v0.2 改用 `start.sh restart` 一条命令，内部已带端口检测 + `/health` 健康检查。

### 5.2 查看日志

```bash
# 后端日志（最近 50 行 + 实时）
ssh root@192.168.0.129 'tail -f /opt/zhangxuefeng-agent/logs/backend.log'

# 前端日志
ssh root@192.168.0.129 'tail -f /opt/zhangxuefeng-agent/logs/frontend.log'

# OpenResty 错误日志(如果公网 502)
ssh root@192.168.0.129 'tail -50 /usr/local/openresty/nginx/logs/error.log'
```

### 5.3 查看进程

```bash
ssh root@192.168.0.129 'ps -ef | grep -E "uvicorn|http.server" | grep -v grep'
```

期望看到：
```
root  10540  ...  /opt/zhangxuefeng-agent/.venv/bin/python /opt/zhangxuefeng-agent/.venv/bin/uvicorn ...
root  10541  ...  /opt/zhangxuefeng-agent/.venv/bin/python -m http.server 3000
```

### 5.4 查看端口

```bash
ssh root@192.168.0.129 'ss -tln | grep -E ":(3000|8000) "'

# OpenResty :30000 监听确认
ssh root@192.168.0.129 'ss -tln | grep ":30000 "'
```

### 5.5 备份部署状态（更新前必做）

```bash
ssh root@192.168.0.129 '
cd /opt/zhangxuefeng-agent
cp .env .env.bak.$(date +%Y%m%d_%H%M%S)
ls -la .env.bak.* | tail -3
'
```

---

## 6. 配置项

`/opt/zhangxuefeng-agent/.env` 当前内容（v0.2）：

| 变量 | 含义 | 默认值 | 必填 |
|---|---|---|---|
| `OPENAI_API_KEY` | MiniMax API 密钥 | **必填** | ✅ |
| `OPENAI_BASE_URL` | API base URL | `https://api.minimaxi.com/v1` | ❌ |
| `MODEL_NAME` | 模型名 | `MiniMax-M3` | ❌ |
| `ZHANGXUEFENG_SKILL_DIR` | SKILL.md 所在目录 | `~/.copaw/workspaces/default/skills/zhangxuefeng-perspective` | ❌ |
| `AUTH_USER` | 后端鉴权白名单 | **空 = 关闭鉴权（仅本地）** | 公网必填 |

### `AUTH_USER` — 后端鉴权白名单（v0.2 新增）

**设计**：
- 后端 `require_auth` 是 FastAPI Depends，校验 nginx `auth_basic` 注的 `X-Remote-User` header
- 单值字符串相等（当前是单用户部署，多用户要升级 htpasswd + 改 `require_auth` 读文件）
- 缺 header / 不匹配 → 401（**不发 WWW-Authenticate**，避免跟 nginx 的 Basic realm 冲突）

**配置示例**：
```bash
echo "AUTH_USER=agent" >> /opt/zhangxuefeng-agent/.env
```

**调用方式**（直连后端）：
```bash
curl -H "X-Remote-User: agent" \
     -H "X-Session-ID: my-session" \
     "http://192.168.0.129:8000/api/chat?q=hi" -N
```

**空值行为**：`AUTH_USER=`（空）时鉴权关闭，**仅本地开发**。生产环境看到 401 日志说明 OpenResty 没正确注 user 或 `AUTH_USER` 没设。

**不影响**：`/health` 不需要鉴权（k8s 探针/CI 健康检查）。

> **变更(v0.2)**：v0.1 用了 `AUTH_TOKEN` Bearer header 方案，**已废弃**：运维要管理 token + 前端要带 Authorization 头 + 跟 OpenResty auth_basic 重复。改成读 `X-Remote-User` 后，**复用 nginx 已有 htpasswd 体系**，职责清晰。

修改 `.env` 后必须**重启后端**才生效：`bash scripts/start.sh restart`。

---

## 7. ⚠️ 踩坑记录（v0.1+v0.2 累积 9 条）

### 坑 1：`tiktoken==0.13.0` 在 CentOS 7 编译失败（v0.1）

**症状**：
```
× Failed to build `tiktoken==0.13.0`
╰─▶ Call to `setuptools.build_meta.build_wheel` failed (exit status: 1)
...
running build_rust
rustc: command not found
```

**根因**：
- `uv.lock` 锁了 `tiktoken==0.13.0`
- 该版本没有 CPython 3.13 + glibc 2.17 的 manylinux wheel
- uv 默认会去源码编译，但 CentOS 7 没装 rust
- CentOS 7 装 rust 又涉及 glibc 版本问题，恶性循环

**解决**：
```bash
uv pip install --only-binary :all: "langchain-openai>=1.3.0"
```
这样 `langchain-openai` 会拉兼容版 `tiktoken==0.11.0`（有 manylinux wheel，**应用代码里其实根本不用 tiktoken**）。

### 坑 2：`start.sh` 用 `uv run` 触发 lock 重解析（v0.1）

**症状**：依赖装好后，`bash scripts/start.sh` 又去编译 `tiktoken==0.13.0`。

**根因**：`start.sh` 原本是 `uv run uvicorn ...`，`uv run` 会检查 `pyproject.toml` + `uv.lock`，触发完整依赖解析。

**解决**：改 `start.sh`，直接用 `.venv/bin/uvicorn` 和 `.venv/bin/python`，完全绕开 `uv run`：
```bash
VENV_UVICORN="$ROOT/.venv/bin/uvicorn"
VENV_PY="$ROOT/.venv/bin/python"
nohup setsid "$VENV_UVICORN" backend.main:app \
    --host 0.0.0.0 --port "$BACKEND_PORT" \
    --no-access-log \
    > logs/backend.log 2>&1 < /dev/null &
```

### 坑 3：CentOS 7 没有 `python3`（v0.1）

**症状**：`which python3` → `command not found`。

**根因**：CentOS 7 默认只装 Python 2.7，Python 3 需要 EPEL 或源码编译。

**解决**：用 uv 自带的 CPython 3.13，完全不依赖系统 Python。`.venv/bin/python` 是绝对路径，绕过 `python3` 命令缺失问题。

### 坑 4：tar 解压覆盖了 `.env` 追加的配置（v0.1）

**症状**：第一轮部署时手动 `echo ZHANGXUEFENG_SKILL_DIR=... >> .env`，第二轮重新 `tar -xzf` 后追加的行**没丢**（tar 默认覆盖是文件级，不是 append），但 `cat > .env <<EOF` 整体覆盖写法会清掉旧值。

**教训**：部署脚本要**幂等**地管理 `.env`，推荐用 `cat > .env <<EOF` 整体覆盖（部署脚本里写完整内容），或者用 `grep -q XXX .env || echo XXX >> .env` 追加检查。

### 坑 5：start.sh 默认端口被占 → 静默换端口导致部署漂移（v0.2）

**症状**：v0.1 `start.sh` 在 8000 被占时自动换 8001，结果 PM 改了 `start.sh` 没改 nginx upstream，部署看似成功实际跑的是 8001。

**根因**：静默端口 fallback 在并发部署场景下是反模式（部署工具不知道实际端口漂移）。

**解决**：v0.2 `start.sh` 改成端口被占**报错退出**，并提示 `bash scripts/start.sh restart`（先 kill 旧再启）。

### 坑 6：start.sh v1 部署后没 `/health` 健康检查（v0.2）

**症状**：v0.1 `start.sh` 启动后立刻打印"启动成功"，但实际 uvicorn 还在 import 阶段（首屏 2-3 秒），后续脚本以为服务可用就开始 curl。

**根因**：没等 `/health` 返 200 就认为启动完成。

**解决**：v0.2 `start.sh` 加 15s 循环轮询 `/health`：
```bash
for i in {1..15}; do
    if curl -sS ... "http://localhost:$BACKEND_PORT/health" 2>/dev/null | grep -q "^200$"; then
        info "后端 /health 返 200,启动成功(等 ${i}s)"
        break
    fi
    sleep 1
done
```

### 坑 7：公网部署鉴权方案从 `AUTH_TOKEN` 改成 `X-Remote-User`（v0.2）

**症状**：v0.1 用 `AUTH_TOKEN` Bearer header 鉴权，公网部署时前端要改 JS 带 Authorization，运维要单独管 token，且 OpenResty auth_basic 跟后端鉴权两套体系重复。

**根因**：
- `AUTH_TOKEN` 是后端**单方面**的密钥，跟 OpenResty 已有的 htpasswd 体系**不互通**
- token 跟用户名绑定 → 改密码要前后端同时改
- 前端 JS 直接读 token 有 XSS 风险

**解决**：v0.2 改成 nginx `auth_basic` 注 `X-Remote-User`，后端只校验 user 字符串是否在白名单（`AUTH_USER`）。**复用 htpasswd，职责清晰，密钥体系单点**。

### 坑 8：OpenResty 反代默认 buffering 卡 SSE（v0.2）

**症状**：公网访问 `http://tmdata.in:30000/api/chat?q=...` 返回正常但**不出流**，等 30s 后一次性返完整响应（client timeout）。

**根因**：OpenResty 默认对 HTTP 响应开 buffer（`proxy_buffering on`），SSE 长连接被缓冲，客户端一直收不到 chunk。

**解决**：在 OpenResty 的 `/api/` location 里关 buffering：
```nginx
location /api/ {
    proxy_pass http://192.168.0.129:8000;
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header X-Accel-Buffering no;
}
```

### 坑 9：L0 输入过滤误触发现象（v0.2）

**症状**：用户问"我女儿被老师性骚扰"被 L0 立即 422 拒，但问"我想了解一下这个专业"放行。

**根因**：L0 regex 19 条黑名单里有"性骚扰"组合（强语义敏感），但单字"性"不触发。

**教训**：L0 是粗粒度，L2 LLM-as-judge 是细粒度兜底。**422 不一定代表 LLM 答不了**，只是前端没区分。**用户教育**：在 README §安全模型里说清楚"422 是 L0 触发，4004 是 L2 触发"。

---

## 8. 故障排查

### 8.1 `curl /health` 返回 connection refused

```bash
# 看进程是否在
ssh root@192.168.0.129 'ps -ef | grep uvicorn | grep -v grep'

# 看端口监听
ssh root@192.168.0.129 'ss -tln | grep 8000'

# 看后端日志
ssh root@192.168.0.129 'tail -30 /opt/zhangxuefeng-agent/logs/backend.log'
```

如果是启动失败，看 log 里：
- `FileNotFoundError: Cannot find zhangxuefeng-perspective skill dir` → `ZHANGXUEFENG_SKILL_DIR` 路径错
- `ImportError: No module named ...` → `.venv` 没建好，重跑 §3.5

### 8.2 `curl /health` 返回 500 / 报错

- 检查 `/opt/zhangxuefeng-agent/.env` 的 `OPENAI_API_KEY` 是否正确（`cat .env` 看前几位确认）
- 检查 `ZHANGXUEFENG_SKILL_DIR` 指向的目录是否存在且含 `SKILL.md`：
  ```bash
  ssh root@192.168.0.129 'ls -la $ZHANGXUEFENG_SKILL_DIR/SKILL.md'
  ```
- 看后端日志的具体报错堆栈

### 8.3 聊天接口无响应 / 卡住

```bash
# 看 LLM API 是否可达
ssh root@192.168.0.129 '.venv/bin/python -c "
import urllib.request
r = urllib.request.urlopen(\"https://api.minimaxi.com/v1/models\", timeout=10)
print(r.status)
"'

# 看后端 log 有没有 httpx: HTTP Request
ssh root@192.168.0.129 'tail -50 /opt/zhangxuefeng-agent/logs/backend.log | grep -E "httpx|HTTPError|timeout"'
```

### 8.4 401 鉴权失败（v0.2 新）

```bash
# 看后端 log
ssh root@192.168.0.129 'tail -50 /opt/zhangxuefeng-agent/logs/backend.log | grep 401'
```

排查：
- 直连 `:8000` 没带 `X-Remote-User` → 加上（`-H "X-Remote-User: agent"`）
- 公网走 OpenResty → 检查 OpenResty 配置里 `proxy_set_header X-Remote-User $remote_user;` 有没有写
- 写错 user 名 → 检查 `.env` 的 `AUTH_USER` 和 htpasswd 文件里的用户名是否一致

### 8.5 422 输入过滤触发（v0.2 新）

```bash
# 触发 L0 的关键词通常包含:
# 早恋/怀孕/性骚扰/翻车/未成年人+性别组合 等
# 改下问题表述试试
curl -sN -m 5 -H "X-Remote-User: agent" \
    "http://192.168.0.129:8000/api/chat?q=请介绍下计算机专业"
```

如果正常问题也被误杀 → 找开发者调 L0 regex（`backend/input_filter.py`），但默认 fail-open 兜底。

### 8.6 公网访问卡住 / 不出流（v0.2 新）

看 OpenResty error log：
```bash
ssh root@192.168.0.129 'tail -50 /usr/local/openresty/nginx/logs/error.log'
```

如果是 `upstream sent too big header` 或 `upstream timed out` → 检查 buffering 配置（参考坑 8）。

### 8.7 tiktoken 编译错误

如果用了 `uv sync` 而不是分步 `uv pip install`，会卡在编译。修复：

```bash
ssh root@192.168.0.129 'bash -s' <<'REMOTE'
export PATH=$HOME/.local/bin:$PATH
cd /opt/zhangxuefeng-agent
rm -rf .venv
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python --only-binary :all: \
    "fastapi>=0.136.3" "langchain>=1.3.7" "langchain-community>=0.4.2" \
    "langchain-core>=1.4.6" "python-dotenv>=1.2.2" \
    "sse-starlette>=3.4.4" "uvicorn[standard]>=0.49.0" \
    "langchain-openai>=1.3.0"
REMOTE
```

### 8.8 重新部署后 `.env` 丢了（坑 4 复发）

如果用 `cat > .env <<EOF` 整体覆盖 → 老配置清掉。
**修法**：部署脚本里 grep 检查 + 备份：
```bash
ssh root@192.168.0.129 '
cd /opt/zhangxuefeng-agent
[ -f .env ] && cp .env .env.bak.$(date +%Y%m%d_%H%M%S)
cat > .env <<EOF
...完整内容...
EOF
'
```

---

## 9. 后续可选加固（v0.2 现状 + v0.3 规划）

按优先级排序：

### 9.1 systemd 守护（机器重启自动拉起）⭐ 推荐

`/etc/systemd/system/zhangxuefeng-agent.service`：

```ini
[Unit]
Description=ZhangXuefeng Agent (backend + frontend)
After=network.target

[Service]
Type=forking
User=root
WorkingDirectory=/opt/zhangxuefeng-agent
ExecStart=/opt/zhangxuefeng-agent/scripts/start.sh
ExecStop=/bin/bash -c 'bash /opt/zhangxuefeng-agent/scripts/start.sh stop'
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用：
```bash
ssh root@192.168.0.129 '
  cp /tmp/zhangxuefeng-agent.service /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now zhangxuefeng-agent
'
```

### 9.2 HTTPS 升级（v0.2 待办）

当前公网走 HTTP + auth_basic，生产应上 TLS（用户在路由器/NAS 配证书后）：
- 申请证书（Let's Encrypt 或自签）
- OpenResty 加 `listen 443 ssl;` + `ssl_certificate` + `ssl_certificate_key`
- `.env` 里 `OPENAI_BASE_URL` 不变（只改公网入口）

### 9.3 OpenResty 限流（防 CC）

```nginx
# 在 http {} 块加
limit_req_zone $binary_remote_addr zone=agent:10m rate=10r/s;

# 在 server {} 或 location /api/ 加
limit_req zone=agent burst=20 nodelay;
```

### 9.4 多用户鉴权升级

当前 `AUTH_USER` 是单值，多用户要升级：
- 改成读 htpasswd 文件动态校验（Python `passlib` 或自实现）
- 后端 `require_auth` 改读 `X-Remote-User` 后查白名单 dict
- **会话记忆按 user 隔离**（`session_id` 前缀加 user 名 → 跨用户不串）

### 9.5 密钥管理

当前 `.env` 直接明文存 root home。如果多人协作：
- 改成 Vault / 1Password / 环境变量注入
- 或至少 `chmod 600 /opt/zhangxuefeng-agent/.env`（已加）

### 9.6 监控告警

- 后端 `/health` 接 Uptime Kuma / Prometheus
- `logs/backend.log` 接 Loki + Grafana 看 fail-open 频率
- OpenResty error log 接告警（401 突增 / 502 突增）

---

## 10. 文件清单（部署后 129 上的状态）

```bash
ssh root@192.168.0.129 'find /opt/zhangxuefeng-agent -maxdepth 2 -type d | sort'
```

```
/opt/zhangxuefeng-agent
├── .venv/                  # 201MB（uv 管理，CPython 3.13 + 8 个包）
├── backend/                # FastAPI 应用（10 文件 / 1054 行）
│   ├── __init__.py
│   ├── main.py             # HTTP 入口 + 三层防护串联
│   ├── auth.py             # v0.2: A1 鉴权
│   ├── input_filter.py     # v0.2: L0 regex
│   ├── safety_judge.py     # v0.2: L2 LLM-as-judge
│   ├── agent.py            # LangChain 流式问答
│   ├── memory.py           # 会话记忆
│   ├── prompt.py           # Prompt 拼接
│   ├── search.py           # mmx CLI 包装
│   └── config.py           # Settings dataclass
├── frontend/               # 静态前端（3 文件 / 586 行）
│   ├── index.html
│   ├── style.css
│   └── app.js
├── logs/                   # 运行日志
├── scripts/
│   └── start.sh            # v0.2: start|stop|restart 三子命令
├── skills/
│   └── zhangxuefeng-perspective/   # 24MB（含 SKILL.md）
├── .env                    # v0.2: 5 字段（OPENAI_API_KEY + AUTH_USER 等）
├── PRD.md                  # 项目需求文档
├── README.md               # v0.2: 用户/开发者文档
├── DEPLOY.md               # ← 本文件
├── pyproject.toml          # 项目元数据
└── uv.lock                 # 依赖锁（仅供未来参考）
```

---

## 11. 变更记录

| 日期 | 版本 | 变更 | 操作人 |
|---|---|---|---|
| 2026-06-13 | v1.0 | 首次部署到 192.168.0.129 | coding-agent |
| | | - 安装 uv 0.11.21 | |
| | | - 创建 .venv (CPython 3.13.14) | |
| | | - 装依赖（含 tiktoken 0.11.0） | |
| | | - 部署 skill 到 skills/zhangxuefeng-perspective | |
| | | - 改 start.sh 用 .venv/bin/ 直接调用 | |
| | | - 端到端测试通过 | |
| 2026-06-13 | v1.1 | 红队测试 + F1-F4 安全修复 | coding-agent |
| | | - 错误处理不泄露 traceback | |
| | | - /health 端点只返 status | |
| | | - CORS 白名单（不再 `*`） | |
| 2026-06-13 | v1.2 | 多用户隔离（A1 鉴权 + A3 锁） | coding-agent |
| | | - 加 `backend/auth.py::require_auth` | |
| | | - 鉴权方案初版 `AUTH_TOKEN` Bearer | |
| 2026-06-14 | v2.0 | 公网部署 + 三层防护 | coding-agent |
| | | - OpenResty :30000 反代 + htpasswd 鉴权 | |
| | | - 鉴权方案改 `X-Remote-User`（废 AUTH_TOKEN）| |
| | | - `backend/input_filter.py::check` L0 regex（19+5 条）| |
| | | - `backend/safety_judge.py::is_safe` L2 LLM-judge | |
| | | - `start.sh` 加 restart/stop 子命令 + 等 /health 200 | |
| | | - 加 `langchain-community` 依赖 | |
| | | - mobile 适配 12 项（viewport + safe-area） | |
| 2026-06-15 | v2.0.1 | 文档同步 | coding-agent |
| | | - README.md 重写到 v0.2 | |
| | | - DEPLOY.md 重写到 v2.0（本文档）| |

---

## 附录 A：完整远程部署脚本（参考）

把以下内容保存为 `deploy_remote.sh`，可一键部署到任意目标：

```bash
#!/usr/bin/env bash
# 用法: ./deploy_remote.sh root@192.168.0.129
set -e
TARGET=${1:-root@192.168.0.129}

echo "=== 1. 打包 ==="
cd "$(dirname "$0")/../.."
tar --exclude=".venv" --exclude="logs" --exclude="__pycache__" \
    --exclude="*.pyc" --exclude=".git" \
    -czf /tmp/zhangxuefeng-agent.tar.gz zhangxuefeng-agent/
tar -czf /tmp/zhangxuefeng-perspective.tar.gz \
    -C ~/.copaw/workspaces/default/skills/ zhangxuefeng-perspective/

echo "=== 2. scp ==="
scp /tmp/zhangxuefeng-agent.tar.gz /tmp/zhangxuefeng-perspective.tar.gz "$TARGET:/tmp/"

echo "=== 3. 远程部署 ==="
ssh "$TARGET" 'bash -s' <<'REMOTE'
set -e
export PATH=$HOME/.local/bin:$PATH

# 装 uv
[ -x ~/.local/bin/uv ] || curl -LsSf https://astral.sh/uv/install.sh | sh

# 解压
mkdir -p /opt/zhangxuefeng-agent/skills
cd /opt/zhangxuefeng-agent
tar -xzf /tmp/zhangxuefeng-agent.tar.gz --strip-components=1
tar -xzf /tmp/zhangxuefeng-perspective.tar.gz -C /opt/zhangxuefeng-agent/skills/

# 建 venv + 装依赖（8 个包, --only-binary 绕开 tiktoken 编译）
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python --only-binary :all: \
    "fastapi>=0.136.3" "langchain>=1.3.7" "langchain-community>=0.4.2" \
    "langchain-core>=1.4.6" "python-dotenv>=1.2.2" \
    "sse-starlette>=3.4.4" "uvicorn[standard]>=0.49.0" \
    "langchain-openai>=1.3.0"

# 写 .env(完整覆盖,部署脚本要带完整 5 字段)
cat > .env <<EOF
OPENAI_API_KEY=REPLACE_ME
OPENAI_BASE_URL=https://api.minimaxi.com/v1
MODEL_NAME=MiniMax-M3
ZHANGXUEFENG_SKILL_DIR=/opt/zhangxuefeng-agent/skills/zhangxuefeng-perspective
AUTH_USER=agent
EOF
chmod 600 .env

# 启服务（用 restart 模式,即使在跑也会先 kill 旧再启）
bash scripts/start.sh restart
REMOTE

echo "=== 4. 验证 ==="
sleep 8
TARGET_IP="${TARGET#root@}"
echo "--- /health ---"
curl -s "http://$TARGET_IP:8000/health"
echo
echo "--- /api/chat (内网鉴权) ---"
curl -sN -m 10 -H "X-Remote-User: agent" \
    "http://$TARGET_IP:8000/api/chat?q=福建580能上啥" | head -c 200
echo
echo "--- /api/chat (鉴权失败) ---"
curl -s -m 5 "http://$TARGET_IP:8000/api/chat?q=hi"
```

> 💡 **v0.2 变更**：相比 v0.1 附录：
> - `.env` 加 `AUTH_USER=agent`
> - 用 `bash scripts/start.sh restart`（不再 `pgrep kill` + 单独启）
> - 加 4.x 公网鉴权 + 4.x L0 过滤验证步骤
> 
> 📌 **必读踩坑**：见 §7，特别是坑 1（tiktoken 编译）、坑 7（鉴权方案变更）、坑 8（SSE buffering）。
