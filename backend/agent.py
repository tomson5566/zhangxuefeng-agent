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

    # 2. 取历史上下文(await — 持 per-session 锁)
    history_ctx = await build_history_context(session_id)

    # 3. 拼 enriched
    # 3.0 死命令(优先级最高,放在 question 之前让 LLM 先读到)
    dead_commands = (
        "\n【死命令 — 优先级最高,违反任何一条都算回答失败】\n"
        "1. **只准推荐数据快照里有的学校**,不准编造学校名/分数线/位次\n"
        "2. **没数据时直说\"我没把握\"**,不准用训练知识填空\n"
        "3. **引用数据必须带具体数字**(分/位次/年份),不准用\"差不多\"\"还行\"\n"
        "4. **禁止假装联网或调用工具**——你已拿到的数据就是全部\n"
        "5. **必须先问清楚关键信息**(分/选科/省份/家庭背景/想去哪)再给建议,一次只问 2-3 个,不要一上来就问一长串\n"
        "6. **多轮对话要记住用户已说的**(分数/选科/家庭背景),不要重复问\n"
        "7. **每条建议必须给行动项**,不准用\"具体看你自己\"这种废话收尾\n"
    )
    enriched = (
        dead_commands
        + f"\n【用户当前问题】\n{question}\n\n"
        f"【以下是联网搜索到的实时信息(来自 mmx search,可能滞后,不一定权威)】\n"
        f"{fresh}\n\n"
        f"【使用规则】\n"
        f"1. 引用上述搜索结果中的事实时,**必须**用「据搜索结果显示」「我刚查了下资料」「网上说」等措辞明确标出处\n"
        f"2. 如果搜索结果跟问题无关(比如空结果、降级提示),**忽略它**,用你 SKILL.md 里的本地知识回答\n"
        f"3. 不要把搜索结果说成「我自己的判断」「我亲身经历」——你不是气象局,也不是教育部官员,你是做高考咨询的"
    )
    if history_ctx:
        enriched += f"\n\n【历史对话上下文(来自 session 记忆)】\n{history_ctx}"

    # 3.5 读 session 的志愿清单(如果有)
    volunteer_list_ctx = ""
    try:
        from pathlib import Path
        from backend.config import settings as _settings
        # uploads 目录在项目根 uploads/<session_id>/
        # backend/agent.py 的 parents[2] = 项目根
        upload_dir = Path(__file__).resolve().parents[2] / "uploads" / session_id
        if upload_dir.exists():
            for meta_path in upload_dir.glob("*.meta.json"):
                try:
                    import json as _json
                    meta = _json.loads(meta_path.read_text(encoding="utf-8"))
                    if meta.get("type") == "volunteer_list" and meta.get("schools"):
                        schools_lines = "\n".join([
                            f"{i+1}. {s['school']} ({'必选' if s['required'] else '备选'})"
                            for i, s in enumerate(meta["schools"])
                        ])
                        volunteer_list_ctx = (
                            f"\n\n【用户目标院校清单】(用户已上传,必须围绕这份清单给建议)\n"
                            f"{schools_lines}"
                        )
                        break  # 只用第一个
                except Exception:
                    pass
    except Exception:
        pass

    if volunteer_list_ctx:
        enriched += volunteer_list_ctx

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
    # 注:add_exchange 现在是 async(持 per-session 锁),直接 await 即可,
    # 不再需要 asyncio.to_thread 包一层。
    full_answer = "".join(full_answer_parts)
    if full_answer:

        async def _write_memory() -> None:
            try:
                await add_exchange(session_id, question, full_answer)
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
            # add_exchange 已是 async,无 event loop 时无法调用 — 仅记日志
            log.warning(
                "no event loop; skipping memory write for session=%s",
                session_id[:24],
            )
