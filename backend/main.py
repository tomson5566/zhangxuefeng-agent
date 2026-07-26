# PUBLIC_FIX_v1 - public deployment fix (auto-applied; do not edit by hand)
from __future__ import annotations

import asyncio  # SAFETY_JUDGE_v1
import logging

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from backend.agents.zhangxuefeng.agent import stream_answer as stream_zx
from backend.agents.zhongkao.agent import stream_answer as stream_zk
from backend.auth import require_auth
# INPUT_FILTER_v1
from backend.input_filter import check as filter_input, FilterResult
from backend.modules.doc_loader import ALLOWED_EXT, list_uploaded, save_upload
from backend.modules.volunteer_plan import generate_plan
from backend.safety_judge import is_safe  # SAFETY_JUDGE_v1
from backend.config import settings
from backend.agents.zhangxuefeng.prompt import warmup

from pydantic import BaseModel


class VolunteerPlanRequest(BaseModel):
    score: int
    rank: int
    subject: str = "物理类"
    province: str = "福建"
    family_bg: str | None = None
    interests: list[str] | None = None

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
    try:
        from backend.agents.zhongkao import warmup as zk_warmup
        zk_warmup()
        log.info("Zhongkao agent ready")
    except Exception as e:  # noqa: BLE001
        log.warning("zhongkao warmup failed (non-fatal): %s", e)
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


@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    session_id: str = "default",
):
    """上传文档(txt/md/docx/xlsx/pdf/pptx),返回 metadata。

    - 文件存到 uploads/<session_id>/
    - metadata 存 .meta.json
    - 全文解析后存 .content.txt(避免 deepagents 重复解析)
    """
    ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {sorted(ALLOWED_EXT)}",
        )

    content = await file.read()
    try:
        meta = await save_upload(content, file.filename, session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "ok",
        "filename": meta["filename"],
        "size": meta["size"],
        "ext": meta["ext"],
        "saved_path": meta["path"],
        "content_preview": meta["content_preview"],
        "content_full_len": meta["content_full_len"],
    }


@app.post("/api/volunteer-plan")
async def volunteer_plan(req: VolunteerPlanRequest):
    """志愿方案生成器 — 输入分数+位次+省份,输出冲/稳/保 3 档。"""
    result = generate_plan(
        score=req.score,
        rank=req.rank,
        subject=req.subject,
        province=req.province,
        family_bg=req.family_bg,
        interests=req.interests,
    )
    if "error" in result:
        return {"status": "error", "message": result["error"]}
    return {"status": "ok", "plan": result}


@app.post("/api/volunteer-list")
async def upload_volunteer_list(
    file: UploadFile = File(...),
    session_id: str = Query("default"),
):
    """上传用户的"目标院校清单" xlsx (2 列: 学校名 + 是否必选),存到 session,后续 chat 自动带。

    期望 xlsx 格式:
    | 学校名称 | 是否必选 |
    |---------|---------|
    | 厦门大学 | 是 |
    | 福州大学 | 否 |
    """
    from backend.modules.doc_loader import save_upload
    from pathlib import Path

    # 后缀检查
    ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext != ".xlsx":
        raise HTTPException(400, f"仅支持 .xlsx,得到: {ext}")

    content = await file.read()
    try:
        meta = await save_upload(content, file.filename, session_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # 解析 xlsx 抽学校名 + 是否必选,存到 metadata
    import openpyxl
    try:
        wb = openpyxl.load_workbook(__import__("io").BytesIO(content), data_only=True, read_only=True)
        schools = []
        for ws in wb.worksheets:
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i == 0: continue  # 跳表头
                if not row[0]: continue
                sch = str(row[0]).strip()
                if len(sch) < 2: continue
                required = "是" in str(row[1]) if len(row) > 1 and row[1] else False
                schools.append({"school": sch, "required": required})
        wb.close()
    except Exception as e:
        raise HTTPException(400, f"xlsx 解析失败: {e}")

    # 存到 doc 的 metadata 里(覆盖原 meta)
    import json
    meta_path = Path(meta["path"] + ".meta.json")
    meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
    meta_data["type"] = "volunteer_list"
    meta_data["schools"] = schools
    meta_path.write_text(json.dumps(meta_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "status": "ok",
        "filename": meta["filename"],
        "schools_count": len(schools),
        "schools": schools,
    }


@app.get("/api/agents")
async def list_agents():
    """列出可用 agent。供前端下拉按钮用。"""
    return {
        "agents": [
            {
                "name": "zhangxuefeng",
                "display_name": "张雪峰",
                "description": "高考志愿咨询,东北大哥,敢说敢骂",
                "available": True,
            },
            {
                "name": "zhongkao",
                "display_name": "福州中考",
                "description": "福州市区普高分流,二检排名定位",
                "available": True,
            },
        ]
    }


@app.get("/api/uploads/{session_id}")
async def list_uploads(session_id: str):
    """列已上传的文件。"""
    paths = list_uploaded(session_id)
    return {"session_id": session_id, "files": paths, "count": len(paths)}


@app.get("/api/chat")
async def chat(
    q: str = Query(..., min_length=1, max_length=2000, description="用户问题"),
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
    x_agent_name: str | None = Header(None, alias="X-Agent-Name"),
    _: None = Depends(require_auth),
):
    """流式聊天端点 — SSE 协议（GET + query string，最简单）。

    多轮记忆:读 X-Session-ID header,缺失直接 400 — 不再走共享 default 桶,
    避免跨用户串扰与无界内存增长。
    """
    if x_agent_name == "zhongkao":
        stream_fn = stream_zk
    elif x_agent_name in (None, "", "zhangxuefeng"):
        stream_fn = stream_zx
    else:
        raise HTTPException(400, f"Unknown agent: {x_agent_name}. Available: zhangxuefeng, zhongkao")

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
            async for token in stream_fn(q, session_id):
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
