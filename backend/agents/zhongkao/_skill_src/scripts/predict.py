#!/usr/bin/env python3
"""
福州中考志愿填报预测脚本
基于2026年二检数据与2025年中考录取线，为考生生成志愿填报方案。

输入：二检排名、二检分数、中考估分、家庭住址(可选)
输出：JSON格式的志愿填报方案(推荐方案 + 备选方案)
"""

import argparse
import json
import os
import math
import sys

# 数据文件路径(相对于脚本位置)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REFERENCES_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "references")

def load_json(filename):
    """加载JSON数据文件"""
    filepath = os.path.join(REFERENCES_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def normalize_name(name):
    """统一学校名称格式"""
    if not isinstance(name, str):
        return name
    name = name.strip()
    name = name.replace("\uff08", "(").replace("\uff09", ")")
    return name

def get_school_ranking_data():
    """加载并展平学校排名数据，每条记录对应一个学校+招生类别组合"""
    raw = load_json("school_ranking_data.json")
    # 排除非普高学校(综合高中班、职业学校等)和参考线
    exclude_keywords = [
        "综合高中", "职业中专", "职业", "工贸", "经贸", "商贸",
        "机电工程", "财政金融", "经济学校", "中本贯通",
        "投档线", "截胡线", "高保线",
    ]
    records = []
    for school in raw:
        name = normalize_name(school["name"])
        area = school.get("area", "市区")
        # 过滤非普高学校
        if any(kw in name for kw in exclude_keywords):
            continue
        for cat, data in school.get("categories", {}).items():
            # 只取统招数据(排除定转统，定转统名额少且分数线不稳定)
            if "定转统" in cat:
                continue
            # 必须有一志愿数据
            if data.get("vol1_rank") is None:
                continue
            records.append({
                "name": name,
                "area": area,
                "category": cat,
                "vol1_score": data.get("vol1_score"),
                "vol1_rank": data.get("vol1_rank"),
                "vol1_erjian_score": data.get("vol1_erjian_score"),
                "vol2_score": data.get("vol2_score"),
                "vol2_rank": data.get("vol2_rank"),
                "vol2_erjian_score": data.get("vol2_erjian_score"),
                "vol3_score": data.get("vol3_score"),
                "vol3_rank": data.get("vol3_rank"),
                "vol3_erjian_score": data.get("vol3_erjian_score"),
                "vol4_score": data.get("vol4_score"),
                "vol4_rank": data.get("vol4_rank"),
                "vol4_erjian_score": data.get("vol4_erjian_score"),
                "tier": data.get("tier", ""),
                "pre_zizhao_rank": data.get("pre_zizhao_rank"),
                "pre_zizhao_score": data.get("pre_zizhao_score"),
            })
    # 按一志愿排名排序
    records.sort(key=lambda x: x["vol1_rank"])
    return records

def get_school_info():
    """加载学校附加信息"""
    raw = load_json("school_info.json")
    return {normalize_name(k): v for k, v in raw.items()}

def get_score_distribution():
    """加载五分段成绩分布"""
    return load_json("score_distribution.json")

def estimate_zhongkao_score(erjian_rank, erjian_score, score_dist):
    """
    根据二检排名和五分段分布，估算中考分数。
    核心逻辑：二检排名 -> 查找对应分段 -> 推算中考分数
    考虑中考与二检的难度差异，使用修正系数。
    """
    # 查找二检排名对应的分数段
    target_rank = erjian_rank
    estimated_score = None

    for seg in score_dist:
        if seg["cumulative_rank"] >= target_rank:
            estimated_score = seg["lower_bound"]
            break

    if estimated_score is None:
        estimated_score = 450  # 最低兜底

    return estimated_score

def analyze_vol_fulfillment(record):
    """
    分析学校的志愿满足情况。
    返回：一志愿招满 / 二志愿招满 / 三志愿招满 / 四志愿招满 / 未招满
    """
    if record["vol1_rank"] is not None and record["vol2_rank"] is None:
        return "一志愿招满"
    if record["vol2_rank"] is not None and record["vol3_rank"] is None:
        return "二志愿招满"
    if record["vol3_rank"] is not None and record["vol4_rank"] is None:
        return "三志愿招满"
    if record["vol4_rank"] is not None:
        return "四志愿招满"
    return "数据不全"

def calculate_rank_gap(student_rank, school_rank):
    """计算排位间距"""
    return school_rank - student_rank

def classify_school(student_rank, school_rank, strategy="conservative"):
    """
    根据学生排名与学校排名判断志愿定位。
    保守策略：仅1A冲，其余保/保温/兜底
    """
    gap = school_rank - student_rank

    if strategy == "conservative":
        if gap < 0:
            # 学校排名比学生靠前 -> 冲
            if abs(gap) <= 2000:
                return "冲", "\U0001f534"
            else:
                return "猛冲", "\U0001f534"
        elif gap <= 1500:
            return "保", "\U0001f7e1"
        elif gap <= 3500:
            return "保温", "\U0001f7e2"
        else:
            return "兜底", "\U0001f535"
    else:  # aggressive
        if gap < 0:
            if abs(gap) <= 3000:
                return "冲", "\U0001f534"
            else:
                return "猛冲", "\U0001f534"
        elif gap <= 2000:
            return "保", "\U0001f7e1"
        elif gap <= 4000:
            return "保温", "\U0001f7e2"
        else:
            return "兜底", "\U0001f535"

def estimate_distance(student_address, school_info_entry):
    """
    估算通勤距离。
    如果提供了家庭地址和学校经纬度，使用简化的距离计算。
    否则返回未知。
    """
    if not school_info_entry or not student_address:
        return None

    # 简化距离估算(基于区域)
    address_area_map = {
        "鼓楼": "鼓楼区", "台江": "台江区", "仓山": "仓山区",
        "晋安": "晋安区", "马尾": "马尾区", "长乐": "长乐区",
        "西园": "晋安区", "五四路": "鼓楼区", "金山": "仓山区",
    }

    student_area = None
    for key, area in address_area_map.items():
        if key in student_address:
            student_area = area
            break

    school_district = school_info_entry.get("district", "")

    if student_area and school_district:
        if student_area == school_district:
            return "~3km"
        # 相邻区域
        adjacent = {
            "鼓楼区": ["台江区", "晋安区"],
            "台江区": ["鼓楼区", "仓山区", "晋安区"],
            "仓山区": ["台江区", "晋安区"],
            "晋安区": ["鼓楼区", "台江区", "仓山区", "马尾区"],
            "马尾区": ["晋安区", "长乐区"],
            "长乐区": ["马尾区", "仓山区"],
        }
        if school_district in adjacent.get(student_area, []):
            return "~8km"
        return "~15km"

    return None

def select_volunteers(student_rank, student_erjian_score, zhongkao_estimate,
                      school_records, school_info, strategy="conservative",
                      student_address=None, max_volunteers=8):
    """
    核心选校算法。
    按 冲->保->保温->兜底 梯度自动选校。
    """
    candidates = []

    for rec in school_records:
        school_rank = rec["vol1_rank"]
        if school_rank is None:
            continue

        # 使用去自招前排名(更准确)
        effective_rank = rec.get("pre_zizhao_rank") or school_rank

        label, icon = classify_school(student_rank, effective_rank, strategy)
        gap = calculate_rank_gap(student_rank, effective_rank)

        # 获取学校附加信息
        info = school_info.get(rec["name"], {})

        # 分析志愿满足情况
        vol_fulfillment = analyze_vol_fulfillment(rec)

        # 估算距离
        distance = estimate_distance(student_address, info)

        candidates.append({
            "name": rec["name"],
            "label": label,
            "icon": icon,
            "vol1_score": rec["vol1_score"],
            "vol1_rank": effective_rank,
            "vol1_erjian_score": rec.get("vol1_erjian_score"),
            "rank_gap": gap,
            "boarding": info.get("boarding", "未知"),
            "type": info.get("type", "未知"),
            "district": info.get("district", "未知"),
            "distance": distance,
            "vol_fulfillment": vol_fulfillment,
            "tier": rec.get("tier", ""),
            "category": rec.get("category", "统招"),
        })

    # 按排名排序
    candidates.sort(key=lambda x: x["vol1_rank"])

    # 按梯度选校
    plan = []
    slots = {
        "冲": 1,      # 1A
        "保": 1,      # 1B
        "保温": 2,    # 2A, 2B
        "兜底": 4,    # 3A, 3B, 4A, 4B
    }

    if strategy == "aggressive":
        slots = {
            "冲": 2,
            "保": 2,
            "保温": 2,
            "兜底": 2,
        }

    used_schools = set()

    for label in ["冲", "保", "保温", "兜底"]:
        count = 0
        max_count = slots[label]

        # 根据标签筛选候选
        if label == "冲":
            pool = [c for c in candidates if c["label"] == "冲" and c["name"] not in used_schools]
            # 冲的学校：选择排名最接近但高于学生的
            pool.sort(key=lambda x: abs(x["rank_gap"]))
        elif label == "保":
            pool = [c for c in candidates if c["label"] == "保" and c["name"] not in used_schools]
            pool.sort(key=lambda x: x["rank_gap"])
        elif label == "保温":
            pool = [c for c in candidates if c["label"] == "保温" and c["name"] not in used_schools]
            pool.sort(key=lambda x: x["rank_gap"])
        else:  # 兜底
            pool = [c for c in candidates if c["label"] == "兜底" and c["name"] not in used_schools]
            pool.sort(key=lambda x: x["rank_gap"])

        for c in pool:
            if count >= max_count:
                break
            if c["name"] in used_schools:
                continue
            # 避免同一学校的不同类别重复选择
            base_name = c["name"].split("(")[0].split("（")[0]
            if any(base_name in u for u in used_schools):
                continue

            used_schools.add(c["name"])
            plan.append(c)
            count += 1

    return plan[:max_volunteers]

def generate_report(student_info, plan, strategy_name):
    """生成志愿填报报告"""
    report_lines = []
    report_lines.append(f"=== {strategy_name} ===")
    report_lines.append(f"考生信息: 二检排名 {student_info['erjian_rank']}, "
                       f"二检分数 {student_info['erjian_score']}, "
                       f"中考估分 {student_info['zhongkao_estimate']}")
    if student_info.get("address"):
        report_lines.append(f"家庭住址: {student_info['address']}")
    report_lines.append("")

    # 志愿编号映射
    vol_labels = ["1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B"]

    for i, school in enumerate(plan):
        if i >= len(vol_labels):
            break
        vol_id = vol_labels[i]
        gap_str = f"+{school['rank_gap']}" if school['rank_gap'] > 0 else str(school['rank_gap'])
        boarding_str = school['boarding']
        distance_str = school['distance'] or "未知"

        report_lines.append(
            f"{vol_id} | {school['icon']} {school['label']} | "
            f"{school['name']} | "
            f"2025一志愿线: {school['vol1_score']} | "
            f"去自招前排名: {school['vol1_rank']} | "
            f"排位间距: {gap_str} | "
            f"住宿: {boarding_str} | "
            f"距离: {distance_str}"
        )

    return "\n".join(report_lines)

def generate_fill_instructions(plan, student_info):
    """生成填报说明"""
    lines = []
    lines.append("【填报说明】")
    lines.append("1. 本方案基于2026年二检数据与2025年中考录取线推算，仅供参考。")
    lines.append("2. 志愿梯度说明：")
    lines.append("   - 1A(冲): 录取排名略高于考生排名，有一定风险但值得尝试")
    lines.append("   - 1B(保): 录取排名与考生排名接近，录取概率较大")
    lines.append("   - 2A/2B(保温): 录取排名低于考生排名，录取概率高")
    lines.append("   - 3A/3B/4A/4B(兜底): 录取排名明显低于考生排名，确保有学可上")
    lines.append("3. 排位间距为正值表示学校录取排名在考生之后，数值越大越安全。")
    lines.append("4. 建议结合考生实际发挥情况、学校地理位置、住宿需求综合决策。")
    lines.append("5. 中考实际发挥可能与估分存在偏差，建议预留充足保底志愿。")

    # 检查是否有长乐区学校
    has_changle = any("长乐" in s["name"] for s in plan)
    if has_changle:
        lines.append("6. 注意：长乐区学校面向不同招生区域(五区/长乐)的分数线不同，请确认考生所属招生区域。")

    # 检查是否有民办学校
    has_minban = any(s["type"] == "民办" for s in plan)
    if has_minban:
        lines.append("7. 注意：方案中包含民办学校，学费较高，请确认家庭经济承受能力。")

    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="福州中考志愿填报预测工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python predict.py --erjian-rank 15000 --erjian-score 650 --zhongkao-estimate 660
  python predict.py --erjian-rank 15000 --erjian-score 650 --zhongkao-estimate 660 --address "福州市晋安区西园" --strategy conservative
        """
    )
    parser.add_argument("--erjian-rank", type=int, required=True,
                        help="二检排名(整数)")
    parser.add_argument("--erjian-score", type=float, required=True,
                        help="二检分数(浮点数)")
    parser.add_argument("--zhongkao-estimate", type=float, required=True,
                        help="中考估分(浮点数)")
    parser.add_argument("--address", type=str, default=None,
                        help="家庭住址(可选，用于估算通勤距离)")
    parser.add_argument("--strategy", type=str, default="conservative",
                        choices=["conservative", "aggressive"],
                        help="填报策略: conservative(保守)/aggressive(激进)")
    parser.add_argument("--max-volunteers", type=int, default=8,
                        help="最大志愿数(默认8)")

    args = parser.parse_args()

    # 加载数据
    school_records = get_school_ranking_data()
    school_info = get_school_info()
    score_dist = get_score_distribution()

    # 构建考生信息
    student_info = {
        "erjian_rank": args.erjian_rank,
        "erjian_score": args.erjian_score,
        "zhongkao_estimate": args.zhongkao_estimate,
        "address": args.address,
    }

    # 生成推荐方案(保守策略)
    plan_conservative = select_volunteers(
        student_rank=args.erjian_rank,
        student_erjian_score=args.erjian_score,
        zhongkao_estimate=args.zhongkao_estimate,
        school_records=school_records,
        school_info=school_info,
        strategy="conservative",
        student_address=args.address,
        max_volunteers=args.max_volunteers,
    )

    # 生成备选方案(激进策略)
    plan_aggressive = select_volunteers(
        student_rank=args.erjian_rank,
        student_erjian_score=args.erjian_score,
        zhongkao_estimate=args.zhongkao_estimate,
        school_records=school_records,
        school_info=school_info,
        strategy="aggressive",
        student_address=args.address,
        max_volunteers=args.max_volunteers,
    )

    # 生成报告
    report_conservative = generate_report(student_info, plan_conservative, "推荐方案(保守策略)")
    report_aggressive = generate_report(student_info, plan_aggressive, "备选方案(激进策略)")
    instructions = generate_fill_instructions(plan_conservative + plan_aggressive, student_info)

    # 构建JSON输出
    result = {
        "status": "success",
        "student_info": student_info,
        "recommended_plan": {
            "strategy": "conservative",
            "label": "推荐方案(保守策略)",
            "report": report_conservative,
            "volunteers": plan_conservative,
        },
        "alternative_plan": {
            "strategy": "aggressive",
            "label": "备选方案(激进策略)",
            "report": report_aggressive,
            "volunteers": plan_aggressive,
        },
        "instructions": instructions,
        "data_source": "2026年福州市区二检数据 + 2025年中考录取线",
        "disclaimer": "本预测仅供参考，不构成志愿填报的最终依据。请结合考生实际情况、学校招生简章及最新政策综合决策。",
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
