from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from backend.config import settings


_HEADING_RE = re.compile(r"(?m)^#{1,6}\s+(?P<title>.+?)\s*$")


def _split_by_h2(text: str) -> list[tuple[str, str]]:
    """Split markdown text on level-2 headings. Returns [(title, body), ...].

    Uses `\n## ` as the natural split point (PRD 4.2) so SKILL.md edits
    don't break as long as the section titles stay stable.
    """
    parts: list[tuple[str, str]] = []
    # Use level-2 headings as top-level sections
    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        parts.append((title, body))
    # Anything before the first H2 (front matter)
    if matches:
        pre = text[: matches[0].start()].strip()
        if pre:
            parts.insert(0, ("__preamble__", pre))
    else:
        parts.append(("__raw__", text.strip()))
    return parts


def _grab(sections: list[tuple[str, str]], keywords: list[str]) -> str:
    """Return concatenated bodies of sections whose title contains any keyword (Chinese substring match)."""
    chunks: list[str] = []
    for title, body in sections:
        if any(k in title for k in keywords):
            chunks.append(f"## {title}\n\n{body}")
    return "\n\n".join(chunks) if chunks else ""


@lru_cache(maxsize=1)
def _load_skill_text() -> str:
    skill_md = settings.skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return ""
    return skill_md.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def build_system_prompt() -> str:
    """Compose the system prompt by slicing SKILL.md into three logical buckets.

    Falls back to a hand-written persona block if the skill file is missing
    or any bucket comes back empty (so the server still boots).
    """
    text = _load_skill_text()
    sections = _split_by_h2(text) if text else []

    skill_core = _grab(
        sections,
        ["身份卡", "核心心智", "决策启发式", "表达 DNA", "表达DNA", "心智模型"],
    )
    data_snapshot = _grab(
        sections,
        ["2026 福建", "福建", "选科铁律", "投档线", "数据基准", "院校"],
    )
    answer_rules = _grab(
        sections,
        ["回答工作流", "角色扮演", "红线", "回答规则"],
    )

    # Personality anchor (always present, even if SKILL.md is missing)
    persona_anchor = (
        "你是张雪峰，41 岁的东北人，峰学蔚来创始人，做了十几年高考志愿咨询。\n"
        "你讲话直接、接地气、不装，习惯用「你听我说」「我跟你说」「我告诉你」开头，\n"
        "喜欢举具体例子、具体学校、具体专业、具体数据，\n"
        "用「就业倒推法」看专业——先看这个专业能不能找到工作、工资多少，\n"
        "不看兴趣、不看梦想、不看985的名头。\n"
        "你反对「生化环材」「新闻」「工商管理」这种红牌专业，敢直接劝退。\n"
        "你支持计算机、电气、临床医学、警校军校、师范等就业导向的专业。\n"
        "你的语气像哥们聊天，不是老师讲课，也不端着。\n"
        "\n"
        "【称呼规则】\n"
        "对用户不要使用带性别倾向的称呼,比如「某某哥」「某某姐」之类的叫法。\n"
        "无论用户报什么姓、什么身份,默认用「您」「这位家长」「你」就行。\n"
        "只有用户明确说「我是孩子妈」「我是孩子爸」「我是考生本人」这种身份,才能在那一轮用对应称呼,\n"
        "而且要等用户自己说,你不要替用户决定。"
    )

    # Fallback rules
    fallback_rules = (
        "1. 上来先问清分数、选科、想去的省份/城市，再给建议。\n"
        "2. 用具体院校名、位次、专业、就业去向说话，不要空谈。\n"
        "3. 回答不超过 400 字，除非用户明确要长答案。\n"
        "4. 不要用「这是一个好问题」「非常好的思考」这种 AI 套话。\n"
        "5. 不要列一堆选项让用户自己挑——直接说「你就报 XX」「我建议你选 XX」。\n"
        "6. 【硬性】不要调用任何工具/函数/搜索——你没有这些能力。"
        " 不要在回答里出现 `{\"query\": ...}` 或 `<tool_call>` 这种伪工具调用结构。"
        " 你只能用纯文本回答，所有事实必须基于上面 SKILL.md 切片里给到的数据。"
    )

    template = """{persona}

以下是关于你的核心设定（来自 SKILL.md 切片）：
{skill_core}

【当前数据快照：2026 福建高考】
{data_snapshot}

【回答规则】
{answer_rules}

【输出格式硬性约束】
- 纯中文/英文文本回答，不要 JSON / 不要 Markdown 代码块（普通 Markdown 强调可以）。
- 任何涉及「查数据」「搜资料」的意图，直接在回答里给结论，不要假装调用工具。
"""

    multi_turn_rule = (
        "\n【多轮记忆规则】\n"
        "你正在和同一个用户连续对话。用户在前面几轮告诉过你的信息(分数、选科、姓名、"
        "**称呼/性别/身份是家长还是考生**、家庭条件、之前问过什么)要记住,后续回答不要反复问。\n"
        "已经被修正的信息以最新一轮为准。\n"
        "**称呼再次强调**:不要根据「她」「他」去推断孩子的性别、再回头推断用户性别——"
        "这条推断链太脆弱,容易翻车(用户一开始说「她」可能指女儿,后来说「他」可能改了主意)。\n"
        "如果「历史对话上下文」里没告诉你分数等关键信息,再按你 SKILL 里的问卷流程走。\n"
    )

    return template.format(
        persona=persona_anchor,
        skill_core=skill_core or "（SKILL.md 未加载或切片失败，凭上面的人格直接答）",
        data_snapshot=data_snapshot or "（数据快照缺失，凭通识和上面的人格直接答）",
        answer_rules=answer_rules or fallback_rules,
    ) + multi_turn_rule


def warmup() -> None:
    """Eagerly build the prompt at startup so failures show up early."""
    build_system_prompt()
