"""模块加载器 — 自动发现 modules/<name>/register.py 并调用 register()。

设计:
- 每个可插拔模块放在 backend/modules/<name>/ 下
- 模块必须有 register.py,里面定义 register(registry: ModuleRegistry) 函数
- ModuleRegistry 是简单的容器,存 llm/filter/skill_loader/mmx_search/... 等子模块引用
- 主程序启动时调 ModuleLoader.load_all(),把模块挂到 registry
"""
from __future__ import annotations
import importlib
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class ModuleRegistry:
    """可插拔模块的中央注册表。"""

    def __init__(self):
        self.components: dict[str, object] = {}

    def register(self, key: str, component: object) -> None:
        if key in self.components:
            log.warning(f"Module key '{key}' already registered, overwriting")
        self.components[key] = component
        log.info(f"Module registered: {key} = {type(component).__name__}")

    def get(self, key: str) -> object | None:
        return self.components.get(key)

    def keys(self) -> list[str]:
        return sorted(self.components.keys())


class ModuleLoader:
    """自动加载 backend/modules/<name>/register.py。"""

    MODULES_DIR = Path(__file__).resolve().parents[1] / "modules"

    @classmethod
    def load_all(cls, registry: ModuleRegistry) -> list[str]:
        """扫 modules/ 下所有 register.py,调 register(registry)。返已加载模块名列表。"""
        loaded = []
        if not cls.MODULES_DIR.exists():
            log.warning(f"Modules dir not found: {cls.MODULES_DIR}")
            return loaded
        for entry in sorted(cls.MODULES_DIR.iterdir()):
            if not entry.is_dir():
                continue
            register_py = entry / "register.py"
            if not register_py.exists():
                continue
            module_name = f"backend.modules.{entry.name}.register"
            try:
                mod = importlib.import_module(module_name)
                if hasattr(mod, "register"):
                    mod.register(registry)
                    loaded.append(entry.name)
                    log.info(f"Loaded module: {entry.name}")
                else:
                    log.warning(f"Module {entry.name} has no register() function")
            except Exception as e:
                log.error(f"Failed to load module {entry.name}: {e}")
        return loaded


default_registry = ModuleRegistry()
