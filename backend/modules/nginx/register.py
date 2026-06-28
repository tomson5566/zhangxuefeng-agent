"""Nginx 模块注册。"""
from __future__ import annotations
import logging
from backend.modules.nginx import (
    DEFAULT_PORT,
    generate_nginx_config,
    render_to_file,
)

log = logging.getLogger(__name__)


def register(registry) -> None:
    registry.register("nginx_generator", generate_nginx_config)
    registry.register("nginx_render_to_file", render_to_file)
    registry.register("nginx_default_port", DEFAULT_PORT)
    log.debug("nginx module registered")
