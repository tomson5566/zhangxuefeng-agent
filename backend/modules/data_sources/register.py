"""注册 data_sources 模块到 ModuleRegistry。"""
from __future__ import annotations
from backend.core.module_loader import ModuleRegistry


def register(registry: ModuleRegistry) -> None:
    from backend.modules.data_sources.base import make_loader
    registry.register("data.make_loader", make_loader)
    # 顺便注册各省份实例(让前端能直接列)
    for prov in ["福建", "北京", "广东"]:
        loader = make_loader(prov)
        if loader:
            registry.register(f"data.{prov}", loader)
    print(f"[data_sources] registered: make_loader + 福建/北京/广东")