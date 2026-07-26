"""[DEPRECATED 兼容 shim] 真实实现已搬到 backend.agents.zhangxuefeng.memory。"""
from backend.agents.zhangxuefeng.memory import (
    add_exchange,
    build_history_context,
)
__all__ = ["add_exchange", "build_history_context"]
