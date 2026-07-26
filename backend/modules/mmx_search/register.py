"""联网搜索模块注册。"""
from __future__ import annotations
import logging
from backend.modules.mmx_search import search_fresh_data

log = logging.getLogger(__name__)


def register(registry) -> None:
    registry.register("mmx_search", search_fresh_data)
    log.debug("mmx_search module registered")
