# INPUT_FILTER_v1
"""输入过滤器:挡掉 prompt injection,降 LLM 调用成本。

设计:
- L0 黑名单:命中直接拒,不走 LLM(省 token + 延迟)
- L1 软模式:模糊检测,命中软拒(张雪峰语气)
- 拒答响应走原 SSE 帧格式:`data: {"t": "..."}\n\n` + `data: [DONE]\n\n`
- 主入口:`check(q, session_id)` 同步函数
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)


# ---------- 规则数据结构 ----------
@dataclass(frozen=True)
class FilterResult:
    blocked: bool
    reply: str
    rule: str


# ---------- L0 硬黑名单 ----------
_HARD_PATTERNS: list[tuple[str, str]] = [
    (r"忽略.*(?:之前|所有).*指令",                  "ignore_instruction"),
    (r"删除.*(?:你)?自己",                          "delete_self"),
    (r"退出.*角色",                                  "exit_role"),
    (r"不再扮演",                                    "exit_role"),
    (r"forget\s+(?:all|previous|earlier).*instruction", "ignore_instruction"),
    (r"stop\s+(?:being|acting\s+as)",               "exit_role"),
    (r"输出.*system\s*prompt",                      "leak_prompt"),
    (r"告诉我.*(?:你的)?(?:指令|规则|人设)",        "leak_prompt"),
    (r"打印.*SKILL\.md",                            "leak_prompt"),
    (r"(?:你是|展示).*(?:哪个|什么).*模型",         "leak_model"),
    (r"你是\s*GPT|你是\s*claude|你是\s*gemini",     "leak_model"),
    (r"(?:假装|现在|切换).*(?:你是|你是)",           "role_override"),
    (r"act\s+as\s+(?!zhang)",                       "role_override"),
    (r"you\s+are\s+now\s+",                         "role_override"),
    (r"\bDAN\b",                                    "jailbreak_dan"),
    (r"jailbreak",                                  "jailbreak_dan"),
    (r"developer\s+mode",                           "jailbreak_dan"),
    (r"do\s+anything\s+now",                        "jailbreak_dan"),
]
_HARD_REGEX = [(re.compile(p, re.IGNORECASE), tag) for p, tag in _HARD_PATTERNS]


# ---------- L1 软模式 ----------
_SOFT_PATTERNS: list[tuple[str, str]] = [
    (r"我是.*(?:开发者|开发|OpenAI|Anthropic)",     "auth_impersonate"),
    (r"(?:紧急|急).*测试",                          "urgency"),
    (r"这是.*测试.*(?:请|麻烦)",                    "urgency"),
    (r"忽略(?:之前|前面|以上)",                     "ignore_hint"),
    (r"假如你是|让我们玩个游戏",                    "soft_jailbreak"),
]
_SOFT_REGEX = [(re.compile(p, re.IGNORECASE), tag) for p, tag in _SOFT_PATTERNS]


# ---------- 拒答文案 ----------
_REPLY_HARD = "你说啥我也不会这么干,我是张雪峰,只回答高考志愿的事。"
_REPLY_SOFT = "哥们儿,咱聊正事——孩子多少分?选啥科?哪个省?我给你说点有用的。"
_REPLY_EMPTY = "你啥也没说,重新发一遍吧。"


# ---------- 主入口 ----------
def check(q: str, session_id: str | None = None) -> FilterResult:
    """过滤用户输入。同步函数(纯字符串处理,不调 LLM)。"""
    text = (q or "").strip()
    if not text:
        return FilterResult(blocked=True, reply=_REPLY_EMPTY, rule="empty")

    for regex, tag in _HARD_REGEX:
        if regex.search(text):
            log.warning(
                "input filtered HARD: rule=%s session=%s q=%r",
                tag, (session_id or "")[:32], text[:80],
            )
            return FilterResult(blocked=True, reply=_REPLY_HARD, rule=tag)

    for regex, tag in _SOFT_REGEX:
        if regex.search(text):
            log.warning(
                "input filtered SOFT: rule=%s session=%s q=%r",
                tag, (session_id or "")[:32], text[:80],
            )
            return FilterResult(blocked=True, reply=_REPLY_SOFT, rule=tag)

    return FilterResult(blocked=False, reply="", rule="")
