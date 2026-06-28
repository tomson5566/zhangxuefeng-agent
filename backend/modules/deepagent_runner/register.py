"""DeepAgent Runner 模块注册。"""
from __future__ import annotations
import logging
from backend.modules.deepagent_runner import build_agent, stream_deep

log = logging.getLogger(__name__)


def register(registry) -> None:
    registry.register("deepagent_factory", build_agent)
    registry.register("deepagent_stream", stream_deep)
    log.debug("deepagent_runner module registered")
