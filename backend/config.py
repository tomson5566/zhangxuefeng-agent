# PUBLIC_FIX_v1 - public deployment fix (auto-applied; do not edit by hand)
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


def _find_skill_dir() -> Path:
    """Locate the zhangxuefeng-perspective skill directory.

    Resolution order:
    1. ZHANGXUEFENG_SKILL_DIR env var (explicit override)
    2. ~/.copaw/workspaces/default/skills/zhangxuefeng-perspective (the canonical install)
    """
    env = os.getenv("ZHANGXUEFENG_SKILL_DIR")
    if env:
        p = Path(env).expanduser()
        if p.is_dir():
            return p
    default = Path.home() / ".copaw/workspaces/default/skills/zhangxuefeng-perspective"
    if default.is_dir():
        return default
    raise FileNotFoundError(
        f"Cannot find zhangxuefeng-perspective skill dir. "
        f"Tried ZHANGXUEFENG_SKILL_DIR and {default}"
    )


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_base_url: str = "https://api.minimaxi.com/v1"
    model_name: str = "MiniMax-M3"
    auth_token: str = ""  # 空 = 关闭鉴权(向后兼容);生产务必设置
    # nginx auth_basic 用的用户名(空 = 关闭鉴权)。与 nginx htpasswd 用户对应
    auth_user: str = ""
    skill_dir: Path = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is empty. Set it in .env or export it in your shell."
            )
        if not self.auth_user:
            import logging
            logging.getLogger(__name__).warning(
                "AUTH_USER is empty - nginx auth_basic is DISABLED. Set AUTH_USER env to enable."
            )
        if self.skill_dir is None:
            object.__setattr__(self, "skill_dir", _find_skill_dir())


def load_settings() -> Settings:
    # Load .env from project root if present (override=False so real env wins if set)
    from dotenv import load_dotenv

    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env", override=False)

    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.minimaxi.com/v1").strip(),
        model_name=os.getenv("MODEL_NAME", "MiniMax-M3").strip(),
        auth_token=os.getenv("AUTH_TOKEN", "").strip(),
        auth_user=os.getenv("AUTH_USER", "").strip(),
    )


settings: Settings = load_settings()
