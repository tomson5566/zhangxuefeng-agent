"""DeepAgent Runner — 用 langchain deepagents 替代 LCEL chain。

对外暴露:
- DeepAgent:AgentBase 子类,封装 create_deep_agent
- build_agent(skill_name):DeepAgent 实例(走 AgentBase 单例)
- build_agent_direct(...):直接构造,支持注入 LLM 参数
- stream_deep / stream_chat:async 流式
- FilterMiddleware:中间件
"""
from backend.modules.deepagent_runner.runner import (
    DeepAgent,
    FilterMiddleware,
    build_agent,
    build_agent_direct,
    stream_chat,
    stream_deep,
)

__all__ = [
    "DeepAgent",
    "FilterMiddleware",
    "build_agent",
    "build_agent_direct",
    "stream_chat",
    "stream_deep",
]
