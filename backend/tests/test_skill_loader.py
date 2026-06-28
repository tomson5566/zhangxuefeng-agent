"""测试 skill_loader + SkillRegistry。"""
import pytest
from backend.core.skill_registry import SkillRegistry


def test_skill_registry_discovers_skills():
    skills = SkillRegistry.list_available()
    assert len(skills) >= 60, f"Expected ≥60 skills, got {len(skills)}"


def test_load_zhangxuefeng_prompt():
    from backend.modules.skill_loader import load_skill_prompt
    prompt = load_skill_prompt("zhangxuefeng-perspective")
    assert len(prompt) > 1000, f"prompt too short: {len(prompt)} chars"
    assert "张雪峰" in prompt or "志愿" in prompt


def test_unknown_skill_returns_empty_not_raise():
    """load_skill_prompt 设计:找不到 skill 不抛异常,返空字符串(降级)。"""
    from backend.modules.skill_loader import load_skill_prompt
    prompt = load_skill_prompt("not-a-real-skill-xyz")
    assert prompt == ""


def test_skill_registry_load_unknown_raises():
    """直接调 SkillRegistry.load 找不到会抛 KeyError(底层行为)。"""
    with pytest.raises(KeyError):
        SkillRegistry.load("not-a-real-skill-xyz")
