from __future__ import annotations

import logging
import re
from typing import AsyncIterator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from backend.config import settings
from backend.prompt import build_system_prompt

log = logging.getLogger(__name__)

_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.model_name,
            streaming=True,
            temperature=0.8,
            timeout=60,
        )
    return _llm


def build_chain():
    """Build an LCEL chain: prompt -> llm -> str."""
    llm = _get_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", build_system_prompt()),
            ("user", "{question}"),
        ]
    )
    return prompt | llm | StrOutputParser()


# Match <think>...</think> blocks (some chat models expose reasoning as XML tags).
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
# Some MiniMax-compatible endpoints prefix every SSE chunk with literal "data: ".
_DATA_PREFIX_RE = re.compile(r"^(?:data:\s*)+", re.MULTILINE)


def _sanitize_token(token: str) -> str:
    """Strip reasoning tags and accidental SSE protocol leakage from a single token."""
    if not token:
        return ""
    cleaned = _THINK_RE.sub("", token)
    cleaned = _DATA_PREFIX_RE.sub("", cleaned)
    return cleaned


async def stream_answer(question: str, session_id: str = "default-session") -> AsyncIterator[str]:
    """Stream tokens for a single user question. Yields sanitized string chunks.

    每次无条件先做联网搜索(5min 缓存);取 session 记忆拼接历史;
    流式结束后 fire-and-forget 写记忆(不让 [DONE] 等写完)。
    """
    import asyncio
    from backend.search import search_fresh_data
    from backend.memory import add_exchange, build_history_context

    # 1. 联网搜索 — 失败/空结果降级,LLM 仍能继续工作
    fresh = search_fresh_data(question)

    # 2. 取历史上下文
    history_ctx = build_history_context(session_id)

    # 3. 拼 enriched
    enriched = (
        f"{question}\n\n"
        f"【以下是联网搜索到的实时信息(来自 mmx search,可能滞后,不一定权威)】\n"
        f"{fresh}\n\n"
        f"【使用规则】\n"
        f"1. 引用上述搜索结果中的事实时,**必须**用「据搜索结果显示」「我刚查了下资料」「网上说」等措辞明确标出处\n"
        f"2. 如果搜索结果跟问题无关(比如空结果、降级提示),**忽略它**,用你 SKILL.md 里的本地知识回答\n"
        f"3. 不要把搜索结果说成「我自己的判断」「我亲身经历」——你不是气象局,也不是教育部官员,你是做高考咨询的"
    )
    if history_ctx:
        enriched += f"\n\n【历史对话上下文(来自 session 记忆)】\n{history_ctx}"

    # 4. 走 LCEL chain, 收集完整 answer
    chain = build_chain()
    full_answer_parts: list[str] = []
    try:
        async for chunk in chain.astream({"question": enriched}):
            clean = _sanitize_token(chunk)
            if clean:
                full_answer_parts.append(clean)
                yield clean
    except Exception as e:  # noqa: BLE001
        log.exception("stream_answer failed")
        yield f"\n\n[后端错误: {type(e).__name__}: {e}]"
        return  # 失败不写回记忆

    # 5. 流式结束 — fire-and-forget 写记忆(create_task)
    # 这样 [DONE] 立刻发,记忆写在后台跑(不阻塞 SSE 关闭)
    # 风险:进程崩了记忆丢 — 但 in-memory dict 本来就不持久,可接受
    full_answer = "".join(full_answer_parts)
    if full_answer:

        async def _write_memory() -> None:
            try:
                await asyncio.to_thread(add_exchange, session_id, question, full_answer)
                log.info(
                    "memory add session=%s answer_len=%d",
                    session_id[:24], len(full_answer),
                )
            except Exception as e:  # noqa: BLE001
                log.warning("add_exchange failed (non-fatal): %s", e)

        # create_task 在 event loop 里 schedule,不阻塞当前 generator return
        try:
            asyncio.create_task(_write_memory())
        except RuntimeError:
            # 兜底:没 event loop 时同步写(MVP 不应发生,防御性)
            log.warning("no event loop for create_task, sync write")
            try:
                add_exchange(session_id, question, full_answer)
            except Exception as e:  # noqa: BLE001
                log.warning("sync add_exchange failed: %s", e)
