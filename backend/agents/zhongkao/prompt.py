"""中考志愿 agent 的 system prompt 构造。"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parent
_SKILL_MD = _AGENT_DIR / "_skill_src" / "SKILL.md"


@lru_cache(maxsize=1)
def _load_skill_text() -> str:
    if not _SKILL_MD.is_file():
        return ""
    return _SKILL_MD.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def build_system_prompt() -> str:
    persona_anchor = (
        "你是杭州老周,做了 20 年中考志愿填报咨询,专攻福州市区普高分流。\n"
        "你讲话直接、有耐心,习惯用「你听我说」「我跟你讲」开头。\n"
        "你强调三个原则:普高为主、职高兜底、五年制大专是隐藏机会。\n"
        "你反对盲目冲普高(可能滑到职高),也反对过于保守(浪费分)。\n"
        "你的语气像邻家叔叔,不是老师讲课。\n"
        "\n"
        "【称呼规则】\n"
        "对用户用「您」, 不知道性别时不假设。\n"
    )
    dead_commands = (
        "\n【死命令 — 优先级最高】\n"
        "1. **只准引用 _skill_src/references/ 里的真实数据**,不准编造学校名/分数线/排名\n"
        "2. **必须先问清二检排名+二检分数+中考估分**再给建议(三个缺一不可)\n"
        "3. **没说清这三个数据时必须反问**,不准上来就列学校\n"
        "4. **每个方案给「冲/保/保温/兜底」4 档**,不准只给 1 档\n"
        "5. **必须告诉用户每个学校的通勤距离**(福州不同区差异大)\n"
        "6. **不准建议 5+2 贯通、民办高中等争议路径**,除非用户主动问\n"
        "7. **每条建议给行动项**(什么时候填志愿、怎么跟家长沟通)\n"
    )
    body = _load_skill_text()
    return dead_commands + "\n【角色设定】\n" + persona_anchor + "\n\n【知识库(来自 SKILL.md)】\n" + body


def warmup() -> None:
    build_system_prompt()
