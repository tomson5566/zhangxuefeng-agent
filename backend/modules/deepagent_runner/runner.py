"""deepagents 主 agent — 替代旧的 LCEL chain。

设计:
- 用 deepagents.create_deep_agent(0.6.12) 包装 llm_factory + tools + middleware
- 内置工具:web_search(联网,来自 modules.mmx_search)
- 中间件链:FilterMiddleware(L0/L1 输入过滤)
- 流式输出用 astream_events(version="v2") + on_chat_model_stream
- skill 注入走 deepagents 内置 skills=[] 参数(0.6.12 特性),不再手动拼 system_prompt
"""
from __future__ import annotations
import logging
from typing import AsyncIterator

from langchain_core.tools import tool
from langchain.agents.middleware import AgentMiddleware

from backend.config import settings
from backend.core.agent_base import AgentBase
from backend.modules.llm import get_llm
from backend.modules.mmx_search import search_fresh_data
from backend.modules.skill_loader import load_skill_prompt

log = logging.getLogger(__name__)

_BASE_SYSTEM_PROMPT = """你是张雪峰,东北人,敢说、敢骂、敢直接,讲高考志愿讲到了骨子里。

回答要求:
- 直接给结论,不要绕弯
- 引用具体院校 / 数据 / 政策
- 通俗易懂,不要学究腔
"""


@tool
def web_search(query: str) -> str:
    """联网搜索实时信息(query 用用户原话,不要改写)。返回简短的搜索摘要文本。"""
    return search_fresh_data(query)


class FilterMiddleware(AgentMiddleware):
    """L0/L1 输入过滤中间件 — 拦截 user 消息,硬黑名单命中就拒绝回答。"""

    def before_agent(self, state, runtime):
        try:
            from backend.modules.filter import check_input
        except Exception as e:  # noqa: BLE001
            log.warning("FilterMiddleware import failed (skip): %s", e)
            return None
        msgs = state.get("messages", []) if isinstance(state, dict) else []
        if not msgs:
            return None
        last = msgs[-1]
        content = getattr(last, "content", None)
        if content is None and isinstance(last, dict):
            content = last.get("content")
        if not content:
            return None
        user_text = content if isinstance(content, str) else str(content)
        try:
            result = check_input(user_text)
        except Exception as e:  # noqa: BLE001
            log.warning("FilterMiddleware check failed (allow): %s", e)
            return None
        if getattr(result, "blocked", False):
            reply = getattr(result, "reply", "已被过滤")
            return {
                "messages": [
                    {"role": "assistant", "content": f"[拒绝回答] {reply}"}
                ]
            }
        return None


class DeepAgent(AgentBase):
    name = "deepagent"
    description = "deepagents-based 张雪峰 agent,支持 skill 切换 + 联网搜索 + 输入过滤"

    def __init__(self, skill_name: str = "zhangxuefeng-perspective"):
        self.skill_name = skill_name

    def _build_internal(self):
        from deepagents import create_deep_agent

        llm = get_llm(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.model_name,
        )
        skill_section = load_skill_prompt(self.skill_name)
        system_prompt = _BASE_SYSTEM_PROMPT + ("\n\n" + skill_section if skill_section else "")

        return create_deep_agent(
            model=llm,
            tools=[web_search],
            system_prompt=system_prompt,
            middleware=[FilterMiddleware()],
        )


def build_agent(skill_name: str = "zhangxuefeng-perspective") -> DeepAgent:
    """工厂:返回 DeepAgent 实例(AgentBase.build_agent 会 lazy 调 _build_internal)。"""
    return DeepAgent(skill_name=skill_name)


def build_agent_direct(
    *,
    skill_name: str = "zhangxuefeng-perspective",
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
):
    """直接构造(不走 AgentBase 单例缓存)— 适用于需要注入自定义 LLM 参数的场景(测试、admin)。"""
    from deepagents import create_deep_agent

    llm = get_llm(
        api_key=api_key or settings.openai_api_key,
        base_url=base_url or settings.openai_base_url,
        model=model or settings.model_name,
    )
    skill_section = load_skill_prompt(skill_name)
    system_prompt = _BASE_SYSTEM_PROMPT + ("\n\n" + skill_section if skill_section else "")

    return create_deep_agent(
        model=llm,
        tools=[web_search],
        system_prompt=system_prompt,
        middleware=[FilterMiddleware()],
    )


async def stream_deep(
    question: str,
    session_id: str = "default",
    skill_name: str = "zhangxuefeng-perspective",
) -> AsyncIterator[str]:
    """异步流式生成器,产出 token 字符串。

    走 AgentBase.stream 默认实现(deepagents astream_events)。
    """
    agent_wrapper = build_agent(skill_name=skill_name)
    async for chunk in agent_wrapper.stream(question, session_id):
        yield chunk


async def stream_chat(
    agent,
    question: str,
    session_id: str = "default",
) -> AsyncIterator[str]:
    """对已构造 agent 流式调用(供 main.py 改造时使用,绕开 AgentBase 单例)。"""
    async for event in agent.astream_events(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": session_id}},
        version="v2",
    ):
        kind = event.get("event")
        if kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and getattr(chunk, "content", None):
                content = chunk.content
                if isinstance(content, str):
                    yield content
                else:
                    yield str(content)
