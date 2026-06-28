"""LLM 模块 — 抽象 + MiniMax-OpenAI 兼容实现。"""
from backend.modules.llm.openai_compat import get_llm

__all__ = ["get_llm"]
