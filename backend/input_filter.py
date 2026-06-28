"""[DEPRECATED 兼容 shim] 真实实现已搬到 backend.modules.filter。

新代码应直接用:from backend.modules.filter import check_input, FilterResult
"""
from backend.modules.filter.input_filter import check as check
from backend.modules.filter.input_filter import check as check_input, FilterResult

__all__ = ["check", "check_input", "FilterResult"]
