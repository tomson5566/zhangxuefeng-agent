"""Skill 注册表 — 通过加载 SKILL.md 文件实现"换 skill = 换角色"。

设计:
- Skill = 一个目录,含 SKILL.md (frontmatter name + description + body Markdown)
- SkillRegistry.load(name) 读 SKILL.md,返回 Skill dataclass
- 未来扩展:可从 ~/.copaw/workspaces/.../skills/<name>/ 或 ./skills/<name>/ 加载
- 关键 API:list_available() 返回所有可用 skill 名(让前端 / 用户能选)
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path
    version: str = "1.0"

    def to_system_prompt_section(self) -> str:
        """拼成 system prompt 的一段(供 deepagents system_prompt 注入)"""
        return (
            f"# 当前角色: {self.name}\n"
            f"{self.description}\n\n"
            f"{self.body}\n"
        )


_DEFAULT_SEARCH_PATHS = [
    Path.home() / ".copaw/workspaces/default/skills",
    Path.home() / ".copaw/workspaces/coding-agent/skills",
    Path(__file__).resolve().parents[2] / "skills",
]


class SkillRegistry:
    """全局单例 skill 注册表。"""

    _skills: dict[str, Skill] = {}
    _loaded = False

    @classmethod
    def discover(cls, extra_paths: list[Path] | None = None) -> None:
        """扫所有搜索路径,加载 SKILL.md 进 _skills"""
        if cls._loaded:
            return
        paths = list(_DEFAULT_SEARCH_PATHS)
        if extra_paths:
            paths.extend(extra_paths)
        for p in paths:
            if not p.exists() or not p.is_dir():
                continue
            for skill_dir in p.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue
                cls._parse_one(skill_md)
        cls._loaded = True

    @classmethod
    def _parse_one(cls, path: Path) -> None:
        """解析单个 SKILL.md(简单 frontmatter:---name/description---body)"""
        text = path.read_text(encoding="utf-8")
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end > 0:
                fm = text[3:end].strip()
                body = text[end + 4:].lstrip("\n")
                name = ""
                desc = ""
                for line in fm.splitlines():
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip().strip('"')
                if not name:
                    name = path.parent.name
                cls._skills[name] = Skill(name=name, description=desc, body=body, path=path.parent)

    @classmethod
    def list_available(cls) -> list[str]:
        cls.discover()
        return sorted(cls._skills.keys())

    @classmethod
    def load(cls, name: str) -> Skill:
        cls.discover()
        if name not in cls._skills:
            raise KeyError(f"Skill not found: {name}. Available: {cls.list_available()}")
        return cls._skills[name]
