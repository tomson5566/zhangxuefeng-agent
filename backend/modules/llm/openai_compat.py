"""LLM 实现:MiniMax M3 走 OpenAI 兼容协议。

设计:
- 单例 ChatOpenAI,带 lazy 初始化
- 不在这里 import settings — 让调用方注入(更易测)
- timeout=60 / streaming=True / temperature=0.8(沿用原值)
"""
from __future__ import annotations
from langchain_openai import ChatOpenAI


_llm: ChatOpenAI | None = None


def get_llm(
    *,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float = 0.8,
    timeout: int = 60,
    streaming: bool = True,
) -> ChatOpenAI:
    """Get or create singleton ChatOpenAI. MiniMax 走 OpenAI 兼容协议。"""
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model,
            streaming=streaming,
            temperature=temperature,
            timeout=timeout,
        )
    return _llm


def reset_for_test() -> None:
    """测试用:重置 singleton"""
    global _llm
    _llm = None
