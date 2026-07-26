"""中考志愿 agent — 调 predict.py CLI 返志愿方案。"""
from __future__ import annotations
import asyncio
import json
import logging
import re
import subprocess
from pathlib import Path
from typing import AsyncIterator

log = logging.getLogger(__name__)

_AGENT_DIR = Path(__file__).resolve().parent
# 用 sys.executable 自适应(开发机/目标机/venv 不一致都 OK)
import sys as _sys
_PYTHON_BIN = Path(_sys.executable)
_PREDICT_SCRIPT = _AGENT_DIR / "_skill_src" / "scripts" / "predict.py"


async def stream_answer(question: str, session_id: str = "default-session") -> AsyncIterator[str]:
    """Stream 中考志愿方案。

    简化:用正则从用户问句中提取 3 个数字(erjian_rank / erjian_score / zhongkao_estimate)。
    提取不到就反问(死命令 #3)。
    """
    numbers = re.findall(r"\d+(?:\.\d+)?", question)
    if len(numbers) < 3:
        async for chunk in _ask_for_params():
            yield chunk
        return

    erjian_rank = int(float(numbers[0]))
    erjian_score = float(numbers[1])
    zhongkao_estimate = float(numbers[2])

    result = await asyncio.to_thread(
        _run_predict, erjian_rank, erjian_score, zhongkao_estimate
    )

    if "error" in result:
        yield f"\n\n[错误] {result['error']}\n\n"
        return

    for line in _format_result(result, erjian_rank, erjian_score, zhongkao_estimate):
        yield line + "\n"


def _run_predict(rank: int, score: float, estimate: float) -> dict:
    """同步调 predict.py subprocess。"""
    try:
        proc = subprocess.run(
            [
                str(_PYTHON_BIN),
                str(_PREDICT_SCRIPT),
                "--erjian-rank", str(rank),
                "--erjian-score", str(score),
                "--zhongkao-estimate", str(estimate),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            return {"error": f"predict.py 退出码 {proc.returncode}: {proc.stderr[:500]}"}
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        return {"error": "predict.py 超时(>30s)"}
    except json.JSONDecodeError as e:
        return {"error": f"predict.py 输出不是 JSON: {e}"}
    except Exception as e:
        return {"error": f"predict.py 调用失败: {e}"}


def _format_result(result: dict, rank: int, score: float, estimate: float) -> list[str]:
    """把 predict.py JSON 拼成人类可读文本(逐行返,模拟流式)。"""
    lines = []
    lines.append(f"\n# 福州中考志愿方案(基于二检排名 {rank} / 二检分数 {score} / 中考估分 {estimate})\n")
    plan = result.get("recommended_plan", {})
    schools = plan.get("volunteers", [])
    if not schools:
        lines.append("(未生成志愿方案, 请检查输入参数)\n")
        return lines

    lines.append(f"\n## {plan.get('label', '推荐方案')}\n")
    for i, v in enumerate(schools, 1):
        name = v.get("name", "?")
        label = v.get("label", "?")
        icon = v.get("icon", "")
        score = v.get("vol1_score", "?")
        gap = v.get("rank_gap", "?")
        boarding = v.get("boarding", "?")
        district = v.get("district", "?")
        tier = v.get("tier", "?")
        lines.append(f"{i}. {icon} **{name}** ({label})")
        lines.append(f"   - 2025 一志愿线: {score} | 排位间距: {gap}")
        lines.append(f"   - 区域: {district} | 住宿: {boarding} | 档次: {tier}\n")
    return lines


async def _ask_for_params() -> AsyncIterator[str]:
    """流式反问 3 个关键参数。"""
    msg = (
        "\n\n你听我说,福州中考志愿方案必须基于 3 个数据:\n"
        "1. **二检排名**(必需)\n"
        "2. **二检分数**(必需)\n"
        "3. **中考估分**(必需)\n"
        "\n"
        "请告诉我这 3 个数字,格式不限,比如:\n"
        "- \"二检排名 8000, 二检分数 480, 中考估分 520\"\n"
        "- \"我二检 2 万名,考了 450, 估分 480\"\n"
        "\n"
        "另外:\n"
        "- 家庭住址(可选) — 用于估算通勤距离\n"
    )
    for char in msg:
        yield char
        await asyncio.sleep(0.01)


def warmup() -> None:
    if not _PREDICT_SCRIPT.is_file():
        log.warning(f"predict.py not found at {_PREDICT_SCRIPT}")
        return
    log.info(f"predict.py ready: {_PREDICT_SCRIPT}")
