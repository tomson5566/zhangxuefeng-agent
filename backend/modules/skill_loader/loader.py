"""加载 SKILL.md 文件,把内容拼成 system prompt 段。

设计:
- 用 backend.core.skill_registry.SkillRegistry(已在阶段 1 建好)做底层
- 暴露 load_skill_prompt(name) 返 system prompt 字符串(供 deepagents 用)
- 暴露 list_skills() 返 [{name, description, path}, ...](给前端 /api/skills 列表用)
- 暴露 SkillLoader 类,future:可缓存 + 热加载
"""
from __future__ import annotations
import logging
import time
from typing import TypedDict

from backend.core.skill_registry import SkillRegistry

log = logging.getLogger(__name__)


class SkillInfo(TypedDict):
    name: str
    description: str
    path: str


def list_skills() -> list[SkillInfo]:
    """列出所有可用 skill(给前端选择用)"""
    SkillRegistry.discover()
    return [
        SkillInfo(name=s.name, description=s.description, path=str(s.path))
        for s in (SkillRegistry._skills[n] for n in SkillRegistry.list_available())
    ]


def load_skill_prompt(name: str) -> str:
    """加载 skill 的 system prompt 段。

    - name="default" 或不传:返回空字符串(交给上层用基础 prompt)
    - name 存在:返回 Skill.to_system_prompt_section()
    - name 不存在:log warning,返回空字符串(降级,不抛)
    """
    if not name or name == "default":
        return ""
    try:
        skill = SkillRegistry.load(name)
        return skill.to_system_prompt_section()
    except KeyError as e:
        log.warning(f"Skill not found, falling back to empty: {e}")
        return ""


class SkillLoader:
    """Skill 加载器(可扩展缓存、热加载等)。"""

    def __init__(self, cache_ttl_sec: int = 0):
        self.cache_ttl_sec = cache_ttl_sec
        self._cache: dict[str, tuple[float, str]] = {}

    def load(self, name: str) -> str:
        if not self.cache_ttl_sec:
            return load_skill_prompt(name)
        cached = self._cache.get(name)
        if cached and (time.time() - cached[0]) < self.cache_ttl_sec:
            return cached[1]
        prompt = load_skill_prompt(name)
        self._cache[name] = (time.time(), prompt)
        return prompt

    def list(self) -> list[SkillInfo]:
        return list_skills()
