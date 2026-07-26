"""Skill 加载模块注册。"""
from __future__ import annotations
import logging
from backend.modules.skill_loader import (
    SkillLoader,
    list_skills,
    load_skill_prompt,
)

log = logging.getLogger(__name__)


def register(registry) -> None:
    registry.register("skill_loader", SkillLoader())
    registry.register("load_skill_prompt", load_skill_prompt)
    registry.register("list_skills", list_skills)
    log.debug("skill_loader module registered")
