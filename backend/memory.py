from __future__ import annotations

import logging
from typing import TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI

from backend.config import settings

log = logging.getLogger(__name__)

_FULL_WINDOW_TURNS = 6           # 保留最近 6 轮(12 条 message)
_SUMMARY_MAX_CHARS = 400         # 单次摘要最多 400 字
_SUMMARY_CAP_CHARS = 400 * 3     # 累计摘要超过这个就截掉头部
_SESSION_ID_MAX_LEN = 128        # 防 DoS


class _SessionState(TypedDict):
    summary: str
    recent: list[BaseMessage]


_sessions: dict[str, _SessionState] = {}
_summary_llm: ChatOpenAI | None = None


def _get_summary_llm() -> ChatOpenAI:
    global _summary_llm
    if _summary_llm is None:
        _summary_llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.model_name,
            temperature=0.3,   # 摘要要稳
            timeout=30,
        )
    return _summary_llm


def _sanitize_session_id(session_id: str) -> str:
    if not session_id:
        return "default-session"
    s = session_id.strip()
    if not s:
        return "default-session"
    return s[:_SESSION_ID_MAX_LEN]


def _get_or_init(session_id: str) -> _SessionState:
    if session_id not in _sessions:
        _sessions[session_id] = {"summary": "", "recent": []}
    return _sessions[session_id]


def _maybe_summarize(state: _SessionState) -> None:
    """如果 recent 超过 6 轮(12 条),把最早的 6 轮摘要进 summary。

    设计:
    - 用 while 循环,处理 1 轮就 break / 失败就 return
    - 摘要成功才 slice 掉原 recent — 失败保留原数据(避免 LLM 抽风导致记忆丢失)
    - summary 累计到 3x 上限就截掉头部(简单粗暴,MVP 不再二次压缩)
    """
    while len(state["recent"]) > _FULL_WINDOW_TURNS * 2:
        to_summarize = state["recent"][:_FULL_WINDOW_TURNS * 2]
        text = "\n".join(
            f"{'用户' if isinstance(m, HumanMessage) else '张雪峰'}:{(m.content or '')[:200]}"
            for m in to_summarize
        )
        prompt = (
            f"请把以下高考志愿咨询对话压缩成 {_SUMMARY_MAX_CHARS} 字内的中文摘要,"
            f"保留关键信息(分数、选科、姓名、家庭条件、之前问过什么、核心结论):\n\n"
            f"{text}\n\n"
            f"摘要:"
        )
        try:
            resp = _get_summary_llm().invoke(prompt)
            new_summary = resp.content if hasattr(resp, "content") else str(resp)
        except Exception as e:  # noqa: BLE001
            # 摘要失败保留原数据,不 slice
            log.warning("summary LLM call failed (keeping history): %s", e)
            return

        # 成功才动 recent
        state["recent"] = state["recent"][_FULL_WINDOW_TURNS * 2:]
        if state["summary"]:
            state["summary"] = state["summary"] + "\n" + new_summary
        else:
            state["summary"] = new_summary
        # 累计超长就截头部
        if len(state["summary"]) > _SUMMARY_CAP_CHARS:
            state["summary"] = state["summary"][-_SUMMARY_CAP_CHARS:]

        # 诊断 log:PM 需要直观看到摘要是否生效
        log.info(
            "[summary-updated] chars=%d recent_left=%d truncated=%s",
            len(state["summary"]),
            len(state["recent"]),
            len(state["summary"]) >= _SUMMARY_CAP_CHARS,
        )


def add_exchange(session_id: str, user_msg: str, ai_msg: str) -> None:
    """把一轮 Q&A 写入 session 记忆,触发摘要检查。

    同步函数 — 调用方应该用 asyncio.to_thread() 包一层避免阻塞 event loop。
    """
    if not user_msg or not ai_msg:
        return
    sid = _sanitize_session_id(session_id)
    state = _get_or_init(sid)
    state["recent"].append(HumanMessage(content=user_msg))
    state["recent"].append(AIMessage(content=ai_msg))
    _maybe_summarize(state)


def build_history_context(session_id: str) -> str:
    """生成历史上下文的 markdown 文本,准备拼到 enriched (user message) 里。"""
    sid = _sanitize_session_id(session_id)
    state = _get_or_init(sid)
    parts: list[str] = []
    if state["summary"]:
        parts.append(f"【老对话摘要】\n{state['summary']}")
    if state["recent"]:
        lines: list[str] = []
        for m in state["recent"]:
            role = "用户" if isinstance(m, HumanMessage) else "张雪峰"
            content = (m.content or "")[:300]
            lines.append(f"- {role}:{content}")
        parts.append("【最近的对话】\n" + "\n".join(lines))
    # 诊断 log:让 PM 能看到每轮请求 history 拼接的实际结构
    has_summary = bool(state["summary"])
    has_recent = bool(state["recent"])
    log.info(
        "[history-build] session=%s has_summary=%s summary_chars=%d recent_msgs=%d",
        sid[:24], has_summary, len(state["summary"]), len(state["recent"]),
    )
    return "\n\n".join(parts) if parts else ""


def get_session_stats() -> dict:
    """诊断用 — 返回所有 session 的统计信息。"""
    return {
        "session_count": len(_sessions),
        "sessions": {
            sid[:32]: {
                "summary_chars": len(s["summary"]),
                "recent_msgs": len(s["recent"]),
            }
            for sid, s in list(_sessions.items())[:20]  # 只返前 20 个
        },
    }


def reset_session(session_id: str) -> None:
    """清空指定 session(诊断 / 测试用)。"""
    sid = _sanitize_session_id(session_id)
    _sessions.pop(sid, None)
