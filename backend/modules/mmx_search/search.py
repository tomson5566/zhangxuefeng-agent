from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

MMX_BIN = Path.home() / ".nvm/versions/node/v24.14.0/bin/mmx"
TTL_SEC = 300        # 5 分钟缓存
TOP_K = 3            # 取前 3 条
SUBPROC_TIMEOUT = 20  # 20s 兜底,mmx 偶尔冷启 1s

# 进程内缓存: {query: (timestamp, formatted_str)}
_cache: dict[str, tuple[float, str]] = {}


def _format_results(data: dict[str, Any], today: str) -> str:
    """把 mmx 返回的 organic 列表格式化成 markdown 文本(给 LLM 当上下文)。"""
    organic = data.get("organic") or []
    if not organic:
        return "(无相关搜索结果)"
    lines = [f"## 联网搜索结果({today},数据可能滞后)\n"]
    for i, item in enumerate(organic[:TOP_K], 1):
        title = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or "").strip()
        link = (item.get("link") or "").strip()
        # date 形如 "2025-06-25 17:18:31" — 只取日期部分
        date = (item.get("date") or "").strip()[:10]
        head = f"**{i}. {title}**"
        if date:
            head += f" ({date})"
        lines.append(head)
        if snippet:
            # 截掉过长 snippet,避免 prompt 膨胀
            lines.append(f"   {snippet[:300]}")
        if link:
            lines.append(f"   来源:{link}")
        lines.append("")  # 空行
    return "\n".join(lines)


def _call_mmx(query: str) -> dict[str, Any]:
    """调 mmx search 子进程,返回解析后的 dict。失败返回空 dict。"""
    try:
        proc = subprocess.run(
            [str(MMX_BIN), "search", "query", "--q", query,
             "--output", "json", "--quiet"],
            capture_output=True,
            text=True,
            timeout=SUBPROC_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        log.warning("mmx search timeout (>%ds) for %r", SUBPROC_TIMEOUT, query[:60])
        return {}
    except FileNotFoundError:
        log.warning("mmx binary not found at %s", MMX_BIN)
        return {}
    except Exception as e:  # noqa: BLE001
        log.warning("mmx search unexpected error: %s", e)
        return {}

    if proc.returncode != 0:
        log.warning("mmx search rc=%d stderr=%s", proc.returncode, (proc.stderr or "")[:200])
        return {}
    if not proc.stdout:
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        log.warning("mmx returned invalid JSON: %s stdout[:200]=%s",
                    e, proc.stdout[:200])
        return {}


def search_fresh_data(query: str) -> str:
    """获取联网搜索数据(5 分钟 TTL 内存缓存)。

    返回:
    - 成功:markdown 格式的 top-3 搜索结果
    - 搜索空结果:"(无相关搜索结果)"
    - 子进程失败:"(联网搜索失败,凭本地知识回答)" — 让 LLM 继续工作
    """
    if not query or not query.strip():
        return "(无搜索 query)"

    now = time.time()
    cached = _cache.get(query)
    if cached and (now - cached[0]) < TTL_SEC:
        log.debug("search cache HIT for %r (age=%.1fs)", query[:40], now - cached[0])
        return cached[1]

    log.info("mmx search MISS for %r (cache size=%d)", query[:60], len(_cache))
    data = _call_mmx(query)
    today = time.strftime("%Y-%m-%d")
    if data and data.get("organic"):
        formatted = _format_results(data, today)
    else:
        # 子进程失败 / 返回空 / 无结果
        formatted = "(联网搜索失败或无结果,凭本地知识回答)"

    _cache[query] = (now, formatted)
    return formatted
