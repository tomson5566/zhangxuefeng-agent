"""LLM 模块注册 — 把 LLM 工厂挂到 registry[llm_factory]。"""
from __future__ import annotations
import logging
from backend.modules.llm import get_llm

log = logging.getLogger(__name__)


def register(registry) -> None:
    """注册 LLM 工厂。

    registry 接口(backend.core.module_loader.ModuleRegistry):
    - registry.register(key, component) — 挂一个组件
    - registry.get(key) — 取组件
    """
    registry.register("llm_factory", get_llm)
    log.debug("LLM module registered: llm_factory -> get_llm")
