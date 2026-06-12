#!/usr/bin/env bash
# 启动后端 (uvicorn :8000) + 前端静态服务 (python -m http.server :3000)
# 用法: bash scripts/start.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# 检查 .env
if [[ ! -f .env ]]; then
    echo "[warn] .env 不存在，复制 .env.example 模板（请把 OPENAI_API_KEY 填上）"
    cp .env.example .env
fi

# 端口探测
check_port() {
    local port="$1"
    if ss -tln 2>/dev/null | grep -q ":$port "; then
        echo "[warn] 端口 $port 已被占用"
        return 1
    fi
    return 0
}

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

check_port "$BACKEND_PORT" || BACKEND_PORT=8001
check_port "$FRONTEND_PORT" || FRONTEND_PORT=3001

mkdir -p logs

# 启后端
echo "==> 启动后端 :$BACKEND_PORT"
nohup setsid uv run uvicorn backend.main:app \
    --host 0.0.0.0 --port "$BACKEND_PORT" \
    --no-access-log \
    > logs/backend.log 2>&1 < /dev/null &
BACKEND_PID=$!
disown
echo "    backend pid=$BACKEND_PID 日志: $ROOT/logs/backend.log"

# 启前端
echo "==> 启动前端 :$FRONTEND_PORT"
cd "$ROOT/frontend"
nohup setsid python3 -m http.server "$FRONTEND_PORT" \
    > "$ROOT/logs/frontend.log" 2>&1 < /dev/null &
FRONTEND_PID=$!
disown
cd "$ROOT"
echo "    frontend pid=$FRONTEND_PID 日志: $ROOT/logs/frontend.log"

# 等几秒看后端起来没
sleep 3
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "[error] 后端进程挂了，看 logs/backend.log"
    tail -20 logs/backend.log
    exit 1
fi

echo
echo "=========================================="
echo "  后端: http://localhost:$BACKEND_PORT  (健康检查: /health)"
echo "  前端: http://localhost:$FRONTEND_PORT"
echo "=========================================="
echo "  停服: kill $BACKEND_PID $FRONTEND_PID"
echo "  或:  pkill -f 'uvicorn backend.main'"
echo "=========================================="
