from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from backend.agent import stream_answer
from backend.config import settings
from backend.prompt import warmup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("zhangxuefeng")


app = FastAPI(title="张雪峰高考志愿 Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    # PRD 9.2 提到跨域 — 前端 3000 后端 8000，需要 CORS。
    # MVP 阶段放 "*"，PM 后面要收紧再说。
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    log.info("Starting 张雪峰 Agent")
    log.info("model=%s base_url=%s", settings.model_name, settings.openai_base_url)
    log.info("skill_dir=%s", settings.skill_dir)
    try:
        warmup()
        log.info("System prompt ready")
    except Exception as e:  # noqa: BLE001
        log.warning("warmup failed (non-fatal): %s", e)
    # 预热 memory 模块(避免第一次请求的 import 开销)
    try:
        import backend.memory  # noqa: F401
        from backend.memory import _get_summary_llm
        _get_summary_llm()  # 触发 ChatOpenAI 初始化
        log.info("Memory module ready")
    except Exception as e:  # noqa: BLE001
        log.warning("memory warmup failed (non-fatal): %s", e)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": settings.model_name,
        "skill_dir": str(settings.skill_dir),
        "ts": int(time.time()),
    }


@app.get("/api/chat")
async def chat(
    q: str = Query(..., min_length=1, max_length=2000, description="用户问题"),
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
):
    """流式聊天端点 — SSE 协议（GET + query string，最简单）。

    多轮记忆:读 X-Session-ID header,缺省回退到 default-session(共享桶,仅调试用)。
    """
    session_id = (x_session_id or "default-session").strip() or "default-session"
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="q must not be empty")

    log.info(
        "chat request: session=%s q=%r (len=%d)",
        session_id[:32], q[:80], len(q),
    )

    async def event_generator():
        # 状态机：跳过 <think>...</think> reasoning 块。
        # 一些 chat 模型会流式吐推理过程（开/闭标签可能跨多个 token），用状态机最稳。
        # 关键：每个 token 单独 JSON-encode 成 SSE 帧，避免 token 里的换行/冒号污染 SSE 协议。
        THINK_OPEN = "<think>"
        THINK_CLOSE = "</think>"
        in_think = False
        buf = ""
        try:
            import json as _json
            async for token in stream_answer(q, session_id):
                if not token:
                    continue
                buf += token
                out_chunks: list[str] = []
                while buf:
                    if in_think:
                        close_idx = buf.find(THINK_CLOSE)
                        if close_idx == -1:
                            buf = ""
                            break
                        buf = buf[close_idx + len(THINK_CLOSE):]
                        in_think = False
                    else:
                        open_idx = buf.find(THINK_OPEN)
                        if open_idx == -1:
                            out_chunks.append(buf)
                            buf = ""
                            break
                        if open_idx > 0:
                            out_chunks.append(buf[:open_idx])
                        buf = buf[open_idx + len(THINK_OPEN):]
                        in_think = True
                for piece in out_chunks:
                    if not piece:
                        continue
                    # JSON-encode payload，避免 token 内部的 \n / : / data: 字面量破坏 SSE 协议
                    yield f"data: {_json.dumps({'t': piece}, ensure_ascii=False)}\n\n"
            if buf and not in_think:
                yield f"data: {_json.dumps({'t': buf}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:  # noqa: BLE001
            log.exception("stream error")
            yield f"data: [ERROR] {type(e).__name__}: {e}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 关 nginx 缓冲
            "Connection": "keep-alive",
        },
    )


@app.exception_handler(Exception)
async def _on_error(_request, exc: Exception):  # noqa: ANN001
    log.exception("unhandled error")
    return JSONResponse(
        status_code=500,
        content={"error": type(exc).__name__, "detail": str(exc)},
    )
