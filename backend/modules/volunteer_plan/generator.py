"""志愿方案生成器 — 输入分数+位次+省份,输出冲/稳/保 3 档学校清单。

算法:
1. 按用户位次找对应段(用 data_sources 找)
2. 冲:位次比用户高 10-20%(用户冲不冲得上)
3. 稳:位次 ±5-10%
4. 保:位次比用户低 15-25%(稳进)
5. 每档拿 3-5 个学校示例
"""
from __future__ import annotations
import logging
from typing import Any

log = logging.getLogger(__name__)


def generate_plan(
    *,
    score: int,
    rank: int,
    subject: str = "物理类",
    province: str = "福建",
    family_bg: str | None = None,
    interests: list[str] | None = None,
) -> dict[str, Any]:
    """生成志愿方案。返回 {chong, wen, bao, meta}。"""
    from backend.modules.data_sources.base import make_loader

    loader = make_loader(province)
    if not loader:
        return {
            "error": f"暂不支持省份: {province}(目前支持: 福建/北京/广东)",
            "chong": [], "wen": [], "bao": [],
        }

    # 当前段
    cur_seg = loader.get_school_by_rank(rank)
    if not cur_seg:
        return {
            "error": f"位次 {rank} 超出 {province} 数据范围",
            "chong": [], "wen": [], "bao": [],
        }

    tbl = loader.get_rank_table()

    # 找冲(位次比用户高 = 段位次上限比用户小,取上方 1-2 段)
    chong_segs = []
    for s in tbl:
        if s["rank_max"] < rank:
            chong_segs.append(s)
        else:
            break
    chong_segs = chong_segs[-2:]   # 最多取紧邻上方 2 段

    # 找稳(当前段为主 ± 紧邻段)
    wen_segs = [cur_seg] if cur_seg else []
    cur_idx = tbl.index(cur_seg) if cur_seg in tbl else -1
    if cur_idx > 0:
        wen_segs.insert(0, tbl[cur_idx - 1])
    if cur_idx >= 0 and cur_idx < len(tbl) - 1:
        wen_segs.append(tbl[cur_idx + 1])
    # 去重保顺序
    seen = set()
    wen_segs = [s for s in wen_segs if not (s["rank_min"] in seen or seen.add(s["rank_min"]))]

    # 找保(位次比用户低 = 段位次下限比用户大,取下方 1-2 段)
    bao_segs = []
    after_cur = tbl[cur_idx + 1:] if cur_idx >= 0 else tbl
    for s in after_cur:
        if s["rank_min"] > rank:
            bao_segs.append(s)
    bao_segs = bao_segs[:2]   # 最多取紧邻下方 2 段

    # 拼结果 — 每段最多 2 个学校 + 跨段去重
    def flatten(segs, max_per_seg=2):
        result = []
        seen = set()
        for s in segs:
            count = 0
            for sch in s.get("school_examples", []):
                if sch in seen:
                    continue
                seen.add(sch)
                result.append({
                    "school": sch,
                    "level": s["level"],
                    "rank_range": f"{s['rank_min']}-{s['rank_max']}",
                    "score_range": f"{s['score_min']}-{s['score_max']}",
                    "tip": s.get("tip", ""),
                })
                count += 1
                if count >= max_per_seg:
                    break
        return result

    return {
        "province": province,
        "subject": subject,
        "score": score,
        "rank": rank,
        "current_level": cur_seg["level"],
        "current_tip": cur_seg.get("tip", ""),
        "chong": flatten(chong_segs),
        "wen": flatten(wen_segs),
        "bao": flatten(bao_segs),
        "family_bg_note": _family_advice(family_bg),
        "interests_note": _interest_advice(interests),
        "key_advice": loader.get_key_advice(),
    }


def _family_advice(family_bg: str | None) -> str:
    """根据家庭背景给建议。"""
    if not family_bg:
        return ""
    bg = family_bg.lower()
    if "电网" in family_bg or "电力" in family_bg:
        return "【家庭资源】家里有电力系统资源 → 优先报电气工程及其自动化,这是最优解"
    if "银行" in family_bg or "金融" in family_bg or "证券" in family_bg:
        return "【家庭资源】家里有金融资源 → 金融/会计/经济学是稳妥选择,其他别碰"
    if "公务员" in family_bg or "政府" in family_bg or "体制" in family_bg:
        return "【家庭资源】体制内家庭 → 汉语言文学/法学/会计/计算机 都是考公万金油"
    if "普通" in family_bg or "工薪" in family_bg or "打工" in family_bg:
        return "【家庭背景】普通工薪家庭 → 选计算机/电子信息/电气(靠技术吃饭,不靠关系)"
    if "富裕" in family_bg or "做生意" in family_bg or "老板" in family_bg:
        return "【家庭资源】经济宽裕 → 选有兴趣的专业,不必只盯着就业"
    return f"【家庭背景】{family_bg} → 请告诉张雪峰更具体的资源情况(行业/职位),才能给更精准建议"


def _interest_advice(interests: list[str] | None) -> str:
    """根据兴趣给建议(只在用户主动说兴趣时输出)。"""
    if not interests:
        return ""
    advice_map = {
        "编程": "【兴趣匹配】爱编程 → 计算机/软件工程,行业对口且你能学得不累",
        "游戏": "【兴趣匹配】爱游戏 → 游戏开发/数字媒体技术,但注意行业加班严重",
        "数学": "【兴趣匹配】数学好 → 数据科学/统计/AI,数学是这些领域的基础",
        "物理": "【兴趣匹配】物理好 → 电子信息/电气/微电子,工科基础扎实",
        "化学": "【兴趣匹配】化学好 → 化工/材料/医药,但生化环材就业差慎选",
        "生物": "【兴趣匹配】生物好 → 临床医学/口腔/生物医学工程(必须读研才有出路)",
        "医学": "【兴趣匹配】想学医 → 临床医学(5+3 一体化最佳),要准备 11 年学习周期",
    }
    out = []
    for interest in interests:
        for k, v in advice_map.items():
            if k in interest:
                out.append(v)
    return "\n".join(out) if out else ""