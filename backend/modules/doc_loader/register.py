"""文档加载模块注册。"""
from __future__ import annotations
import logging
from backend.core.module_loader import ModuleRegistry

log = logging.getLogger(__name__)


def register(registry: ModuleRegistry) -> None:
    from backend.modules.doc_loader.loader import (
        load_file, save_upload, list_uploaded, ALLOWED_EXT,
    )
    registry.register("doc_loader", load_file)
    registry.register("doc_loader.load_file", load_file)
    registry.register("doc_loader.save_upload", save_upload)
    registry.register("doc_loader.list_uploaded", list_uploaded)
    registry.register("doc_extensions", ALLOWED_EXT)
    log.debug("doc_loader module registered")
