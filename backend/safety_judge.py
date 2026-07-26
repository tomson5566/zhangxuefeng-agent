"""[DEPRECATED 兼容 shim] 真实实现已搬到 backend.modules.filter。

新代码应直接用:from backend.modules.filter import is_safe
旧用法:is_safe(q) / judge_input(q) — 两个名字都保留以兼容老 main.py
"""
from backend.modules.filter.llm_judge import is_safe as is_safe
from backend.modules.filter.llm_judge import is_safe as judge_input

__all__ = ["is_safe", "judge_input"]
