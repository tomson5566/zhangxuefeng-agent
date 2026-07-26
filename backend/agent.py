"""[DEPRECATED 兼容 shim] 真实实现已搬到 backend.agents.zhangxuefeng.agent。

本 shim 保留旧 import 路径以防新路径挂了还能 fallback。
新代码应直接用: from backend.agents.zhangxuefeng.agent import stream_answer
"""
from backend.agents.zhangxuefeng.agent import stream_answer
__all__ = ["stream_answer"]
