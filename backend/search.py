"""[DEPRECATED 兼容 shim] 真实实现已搬到 backend.modules.mmx_search。

新代码应直接用:from backend.modules.mmx_search import search_fresh_data
"""
from backend.modules.mmx_search.search import search_fresh_data

__all__ = ["search_fresh_data"]
