"""Filter 模块注册 — 把输入过滤 + LLM 审查挂到 registry。"""
from __future__ import annotations
import logging
from backend.modules.filter import check_input, llm_judge

log = logging.getLogger(__name__)


def register(registry) -> None:
    registry.register("input_filter", check_input)
    registry.register("llm_judge", llm_judge)
    log.debug("Filter module registered: input_filter, llm_judge")
