# PUBLIC_FIX_v1 - public deployment fix (auto-applied; do not edit by hand)
from __future__ import annotations

import asyncio  # SAFETY_JUDGE_v1
import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from backend.agent import stream_answer
from backend.auth import require_auth
# INPUT_FILTER_v1
from backend.input_filter import check as filter_input, FilterResult
from backend.safety_judge import is_safe  # SAFETY_JUDGE_v1
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
    # TODO(security): 生产部署前在此追加正式域名，例如 "https://your-domain.com"。
    allow_origins=[
        "http://localhost:5173",   # 前端 dev
        "http://127.0.0.1:5173",
        "http://localhost:8000",   # 同源
        "http://127.0.0.1:8000",
        "http://tmdata.in:30000",  # 公网反代 origin (nginx :30000)
    ],
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
    # 故意只返 status:避免泄漏 model 名称、skill_dir 绝对路径、服务器时间。
    return {"status": "ok"}


@app.get("/api/chat")
async def chat(
    q: str = Query(..., min_length=1, max_length=2000, description="用户问题"),
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
    _: None = Depends(require_auth),
):
    """流式聊天端点 — SSE 协议（GET + query string，最简单）。

    多轮记忆:读 X-Session-ID header,缺失直接 400 — 不再走共享 default 桶,
    避免跨用户串扰与无界内存增长。
    """
    session_id = (x_session_id or "").strip()
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="X-Session-ID header is required",
        )
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="q must not be empty")

    # INPUT_FILTER_v1
    filter_result = filter_input(q, session_id)
    if filter_result.blocked:
        log.info(
            "input filtered: rule=%s session=%s q=%r",
            filter_result.rule, session_id[:32], q[:80],
        )

        async def event_generator_blocked():
            import json as _json
            yield f"data: {_json.dumps({'t': filter_result.reply}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator_blocked(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # SAFETY_JUDGE_v1 - LLM 审查层
    is_ok, judge_raw = await asyncio.to_thread(is_safe, q)
    if not is_ok:
        log.info(
            "LLM safety judge blocked: raw=%s session=%s q=%r",
            judge_raw[:20], session_id[:32], q[:80],
        )

        async def event_generator_judged():
            import json as _json
            reply = "哥们儿,你这问题我可不接——咱聊正事,孩子多少分?选啥科?哪个省?"
            yield f"data: {_json.dumps({'t': reply}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator_judged(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

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
