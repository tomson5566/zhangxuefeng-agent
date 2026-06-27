#!/usr/bin/env bash
# 启动 / 重启 后端 (uvicorn :8000) + 前端 (python http.server :3000)
#
# 用法:
#   bash scripts/start.sh           # 启动(端口被占就报错退出,不自动换端口)
#   bash scripts/start.sh restart   # 先 kill 旧进程,再启动
#   bash scripts/start.sh stop      # 只停,不起
#
# 行为:
#   - 默认端口被占 → 报错退出(不再静默换 8001/3001,避免下次部署时端口漂移)
#   - 加 restart 子命令后,先 pkill 旧 uvicorn + http.server,再起新的
#   - 起后等 /health 返 200 才算成功(最多等 15s)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ---------- 颜色(可选)----------
if [[ -t 1 ]]; then
    C_RED='\033[0;31m'; C_GRN='\033[0;32m'; C_YEL='\033[0;33m'; C_RST='\033[0m'
else
    C_RED=''; C_GRN=''; C_YEL=''; C_RST=''
fi
info()  { echo -e "${C_GRN}[ok]${C_RST} $*"; }
warn()  { echo -e "${C_YEL}[warn]${C_RST} $*"; }
err()   { echo -e "${C_RED}[error]${C_RST} $*" >&2; }

# ---------- 子命令: stop ----------
do_stop() {
    echo "==> 停止后端 + 前端"
    # pkill 找不到进程返非 0,|| true 避免 set -e 退出
    pkill -f 'uvicorn backend.main'           2>/dev/null || true
    pkill -f 'http.server'                    2>/dev/null || true
    sleep 1
    # 兜底:还有残留就强杀
    pkill -9 -f 'uvicorn backend.main'       2>/dev/null || true
    pkill -9 -f 'http.server'                 2>/dev/null || true
    info "已 stop"
}

# ---------- 检查 .env ----------
if [[ ! -f .env ]]; then
    warn ".env 不存在,复制 .env.example 模板(请把 OPENAI_API_KEY 填上)"
    cp .env.example .env
fi

# ---------- 子命令分发 ----------
ACTION="${1:-start}"
case "$ACTION" in
    stop)    do_stop; exit 0 ;;
    restart) do_stop; echo ;;
    start)   ;;  # 继续往下走
    *)       err "未知子命令: $ACTION(支持: start|stop|restart)"; exit 1 ;;
esac

# ---------- 端口探测(只 start 跑,stop/restart 跳过)----------
check_port() {
    local port="$1"
    if ss -tln 2>/dev/null | grep -q ":$port "; then
        return 1  # 被占
    fi
    return 0
}

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# 默认端口被占 → 报错退出(不再静默换端口)
if ! check_port "$BACKEND_PORT"; then
    err "后端端口 $BACKEND_PORT 已被占用"
    err "→ 如果是要重启,改用: bash scripts/start.sh restart"
    err "→ 或手动停: pkill -f 'uvicorn backend.main'"
    exit 1
fi
if ! check_port "$FRONTEND_PORT"; then
    err "前端端口 $FRONTEND_PORT 已被占用"
    err "→ 如果是要重启,改用: bash scripts/start.sh restart"
    exit 1
fi

# ---------- 启后端 ----------
mkdir -p logs
echo "==> 启动后端 :$BACKEND_PORT"
VENV_UVICORN="$ROOT/.venv/bin/uvicorn"
VENV_PY="$ROOT/.venv/bin/python"
if [[ ! -x "$VENV_UVICORN" ]]; then
    err "$VENV_UVICORN 不存在,请先 uv sync 创建 .venv"
    exit 1
fi
nohup setsid "$VENV_UVICORN" backend.main:app \
    --host 0.0.0.0 --port "$BACKEND_PORT" \
    --no-access-log \
    > logs/backend.log 2>&1 < /dev/null &
BACKEND_PID=$!
disown
echo "    backend pid=$BACKEND_PID 日志: $ROOT/logs/backend.log"

# ---------- 启前端 ----------
echo "==> 启动前端 :$FRONTEND_PORT"
cd "$ROOT/frontend"
nohup setsid "$VENV_PY" -m http.server "$FRONTEND_PORT" \
    > "$ROOT/logs/frontend.log" 2>&1 < /dev/null &
FRONTEND_PID=$!
disown
cd "$ROOT"
echo "    frontend pid=$FRONTEND_PID 日志: $ROOT/logs/frontend.log"

# ---------- 等后端就绪(最多 15s,看 /health 返 200)----------
echo "==> 等后端就绪..."
for i in {1..15}; do
    if curl -sS -o /dev/null -w "" --max-time 1 "http://localhost:$BACKEND_PORT/health" 2>/dev/null; then
        # 进一步确认返的是 200
        if curl -sS -o /dev/null -w "%{http_code}" --max-time 1 "http://localhost:$BACKEND_PORT/health" 2>/dev/null | grep -q "^200$"; then
            info "后端 /health 返 200,启动成功(等 ${i}s)"
            break
        fi
    fi
    sleep 1
    if [[ $i -eq 15 ]]; then
        err "后端 15s 内未就绪,看 logs/backend.log"
        tail -20 logs/backend.log
        exit 1
    fi
done

echo
echo "=========================================="
echo "  后端: http://localhost:$BACKEND_PORT  (健康检查: /health)"
echo "  前端: http://localhost:$FRONTEND_PORT"
echo "=========================================="
echo "  停服:   bash scripts/start.sh stop"
echo "  重启:   bash scripts/start.sh restart"
echo "  或:     kill $BACKEND_PID $FRONTEND_PID"
echo "=========================================="
