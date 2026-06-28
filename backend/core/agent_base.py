"""Agent 抽象基类 — 所有具体 agent 实现继承这个。

设计:
- create() 是同步工厂方法,返回 build_agent 输出(可调用的 agent 对象)
- stream() 是异步生成器,产出 token 字符串
- 子类必须实现 _build_internal(),返回 deepagents / LCEL / 其他 runtime 的 agent 对象
"""
from __future__ import annotations
import abc
from typing import AsyncIterator


class AgentBase(abc.ABC):
    """Agent 抽象基类。"""

    name: str = "base"
    description: str = ""

    @abc.abstractmethod
    def _build_internal(self):
        """子类实现:返回底层 runtime agent(deepagents CompiledStateGraph 或 LCEL chain)"""
        raise NotImplementedError

    def build_agent(self):
        """工厂方法,带单例缓存"""
        if not hasattr(self, "_cached"):
            self._cached = self._build_internal()
        return self._cached

    async def stream(self, question: str, session_id: str = "default") -> AsyncIterator[str]:
        """默认流式接口,子类可 override"""
        agent = self.build_agent()
        async for chunk in self._default_stream(agent, question, session_id):
            yield chunk

    async def _default_stream(self, agent, question: str, session_id: str):
        """默认走 deepagents astream_events,子类可换 LCEL"""
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": question}]},
            config={"configurable": {"thread_id": session_id}},
            version="v2",
        ):
            kind = event.get("event")
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and getattr(chunk, "content", None):
                    yield chunk.content if isinstance(chunk.content, str) else str(chunk.content)
