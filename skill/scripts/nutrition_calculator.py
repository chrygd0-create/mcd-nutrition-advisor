#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦麦营养顾问 - 营养预算与套餐计算引擎

纯标准库实现，无第三方依赖。
热量数据唯一来源是麦当劳 MCP 的 list-nutrition-foods 工具返回值，
本脚本只做计算，不内置任何编造的营养数值。

用法:
  # 生成配餐方案
  python nutrition_calculator.py --goal lose --budget-kcal 500 \
      --nutrition-json nutrition.json --coupons coupons.json --mode plan

  # 只算一个组合的热量
  python nutrition_calculator.py --nutrition-json nutrition.json \
      --items m1,d2,s1 --mode calc

  # 评估某组合叠加优惠券后的实际价格
  python nutrition_calculator.py --nutrition-json nutrition.json \
      --items m1,d2,s1 --coupons coupons.json --mode savings
"""

import argparse
import json
import os
import sys
from itertools import combinations

# ---------- 目标模型 ----------
GOALS = {
    "lose": {
        "label": "减脂",
        "kcal_rate": 0.75,
        "protein_rate": 1.6,
        "prefer": ["零卡", "低卡", "高蛋白"],
        "avoid": ["高热量", "高糖", "含糖"],
        "note": "优先零卡饮品 + 高蛋白单品，避免油炸主食叠加",
    },
    "keep": {
        "label": "维持",
        "kcal_rate": 1.0,
        "protein_rate": 1.2,
        "prefer": ["经典"],
        "avoid": ["高糖"],
        "note": "均衡即可，注意蛋白质与蔬菜搭配",
    },
    "gain": {
        "label": "增肌",
        "kcal_rate": 1.15,
        "protein_rate": 2.0,
        "prefer": ["经典", "高蛋白"],
        "avoid": ["零卡"],
        "note": "加份量、加蛋白，训练后 2 小时内吃完",
    },
}

DEFAULT_PROTEIN_BASE = 70.0   # kg 体重对应的参考蛋白摄入，按 1.0 系数
KCAL_PER_G = {"p": 4, "f": 9, "c": 4}


# ---------- 数据装载 ----------
def parse_mcd_table(text):
    """解析 list-nutrition-foods 的真实返回格式。

    官方接口的 data 字段是字符串形式的自定义表格：
        [160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
          猪柳麦满分,null,1288,308,16,16,24,781,213
          ...
    第一行的 [N] 是行数，{} 内是列名，每行逗号分隔（null 表示空值）。
    """
    rows = []
    cols = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if cols is None:
            if "{" in line and "}" in line:
                inner = line[line.index("{") + 1:line.index("}")]
                cols = [c.strip() for c in inner.split(",")]
                continue
            else:
                continue            # 头部说明文字，跳过
        parts = line.split(",")
        if len(parts) < len(cols):
            continue
        row = {}
        for i, c in enumerate(cols):
            v = parts[i].strip()
            row[c] = None if v.lower() == "null" else v
        rows.append(row)
    return rows


MCD_FIELD_MAP = {
    "name": ("productName", "foodName", "name"),
    "kcal": ("energyKcal", "kcal", "energy"),
    "kj": ("energyKj",),
    "p": ("protein",),
    "f": ("fat",),
    "c": ("carbohydrate",),
    "sodium": ("sodium",),
    "calcium": ("calcium",),
    "cat": ("category",),
    "price": ("price",),
}


def load_nutrition(path):
    """加载 list-nutrition-foods 的返回。

    兼容三种结构:
      1. 标准数组 / {"foods": [...]} / {"data": {"foods": [...]}}
      2. 官方真实格式: {"data": "[160]{productName,...}:\n 猪柳麦满分,null,..."}
      3. 其他 dict 包裹形式，取 data 后递归尝试
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # mcd_client 保存的可能是「markdown 说明 + 原始 JSON」混合文本，
    # 此时整个文件 load 出来是 str：提取最外层 JSON 再来一次
    if isinstance(raw, str):
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                raw = json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass

    foods = raw
    if isinstance(raw, dict):
        for key in ("foods", "items", "list", "nutritionFoods"):
            if isinstance(raw.get(key), list):
                foods = raw[key]
                break
        else:
            data = raw.get("data", [])
            if isinstance(data, str) and "{" in data:
                # 官方真实格式：data 是自定义表格字符串
                foods = parse_mcd_table(data)
            elif isinstance(data, dict):
                foods = data.get("foods", [])
            elif isinstance(data, list):
                foods = data

    out = []
    for idx, it in enumerate(foods):
        if not isinstance(it, dict):
            continue
        name = pick(it, "name", "foodName", "food_name", "餐品名称", "名称", "productName")
        if not name:
            continue
        out.append({
            "id": pick(it, "id", "foodId", "code", "餐品编码") or f"f{idx}",
            "name": str(name),
            "kcal": num(pick(it, "energy", "kcal", "calories", "热量", "能量", "energyKcal")),
            "p": num(pick(it, "protein", "蛋白质")),
            "f": num(pick(it, "fat", "脂肪")),
            "c": num(pick(it, "carbohydrate", "carbs", "碳水化合物", "碳水")),
            "sodium": num(pick(it, "sodium", "钠")),
            "calcium": num(pick(it, "calcium", "钙")),
            "cat": pick(it, "category", "分类", "cat") or classify_food(str(name)),
            "price": num(pick(it, "price", "价格", "amount")) or 0.0,
            "tags": tags_of(it),
        })
    return out


def pick(d, *keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def num(v):
    try:
        return float(str(v).replace("kcal", "").replace("千卡", "").strip())
    except (TypeError, ValueError):
        return 0.0


def tags_of(it):
    t = pick(it, "tags", "标签", "tag")
    if isinstance(t, list):
        return [str(x) for x in t]
    if isinstance(t, str):
        return [x.strip() for x in t.replace("，", ",").split(",") if x.strip()]
    return []


# 官方营养接口不返回分类与价格，分类按名称推断（枚举套餐必需）。
_DRINK_WORDS = ("可乐", "雪碧", "咖啡", "奶茶", "奶昔", "果汁", "柠檬", "茶", "矿泉水", "纯水", "零度")
_DESSERT_WORDS = ("新地", "旋风", "圆筒", "圣代", "冰淇淋")
_SIDE_WORDS = ("薯条", "麦乐鸡", "鸡翅", "鸡块", "薯饼", "脆薯饼", "玉米杯", "派", "沙拉", "鸡排")
_MAIN_WORDS = ("堡", "麦满分", "卷", "饭")


def classify_food(name):
    if any(w in name for w in _DESSERT_WORDS):
        return "甜品"
    if any(w in name for w in _DRINK_WORDS):
        return "饮品"
    if any(w in name for w in _SIDE_WORDS):
        return "小食"
    if any(w in name for w in _MAIN_WORDS):
        return "汉堡"
    return "未分类"


def load_coupons(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    items = raw
    if isinstance(raw, dict):
        for key in ("coupons", "items", "list", "data"):
            if isinstance(raw.get(key), list):
                items = raw[key]
                break
    out = []
    for c in items:
        if not isinstance(c, dict):
            continue
        out.append({
            "name": pick(c, "name", "couponName", "券名称", "title") or "未命名券",
            "amount": num(pick(c, "amount", "discount", "优惠金额", "value", "面额")),
            "threshold": num(pick(c, "threshold", "minAmount", "满减门槛", "useThreshold")),
            "expire": pick(c, "expireTime", "expire", "有效期") or "",
            "id": pick(c, "id", "couponId") or "",
        })
    return out


def load_deals(path):
    """加载团购数据（抖音/美团等第三方渠道的套餐券）。

    麦当劳 MCP 目前不提供团购工具，团购价需从第三方平台获取：
    短期手动维护 JSON，长期接美团/抖音开放平台（需企业资质）。
    文件格式见 assets/deals_sample.json。
    """
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    items = raw
    if isinstance(raw, dict):
        for key in ("deals", "items", "list", "data"):
            if isinstance(raw.get(key), list):
                items = raw[key]
                break
    out = []
    for d in items:
        if not isinstance(d, dict):
            continue
        ids = pick(d, "items", "itemIds", "餐品编码", "包含餐品")
        if isinstance(ids, str):
            ids = [x.strip() for x in ids.split(",") if x.strip()]
        if not ids:
            continue
        out.append({
            "id": pick(d, "id", "dealId") or "",
            "channel": pick(d, "channel", "platform", "渠道") or "团购",
            "name": pick(d, "name", "dealName", "团购名称", "title") or "未命名团购",
            "items": [str(x) for x in ids],
            "price": num(pick(d, "price", "团购价", "dealPrice")),
            "original_price": num(pick(d, "originalPrice", "original_price", "原价", "门市价")),
            "per_person_limit": num(pick(d, "perPersonLimit", "限购", "per_person_limit")) or 0,
            "expire": pick(d, "expire", "expireTime", "有效期") or "",
            "url": pick(d, "url", "link", "链接") or "",
            "note": pick(d, "note", "备注") or "",
        })
    return out


def payment_paths(group, coupons, deals):
    """为一个组合枚举所有支付路径，返回按实付价升序的路径列表。

    路径 1（官方渠道）：原价 - 最优可用官方券。
    路径 2+（团购渠道）：每个「套餐整体 ⊆ 组合」的团购券是一条路径，
      实付 = 团购价 + 组合中团购外单品按原价补齐。
      团购券现实中整套出售、不可拆用、也不可与官方券叠加，
      所以部分覆盖（组合只含团购套餐的一半）不生成路径，且团购路径不叠官方券。
    """
    raw = totals(group)["price"]
    t = totals(group)
    paths = []

    def nutrition_line():
        return (f'{t["kcal"]:.0f} kcal / 蛋白 {t["p"]:.0f}g / 钠 {t["sodium"]:.0f}mg')

    _, disc, coupon = apply_coupons(raw, coupons, [f["id"] for f in group])
    paths.append({
        "channel": "官方渠道" + (f"·{coupon['name']}" if coupon else ""),
        "final": round(raw - disc, 2),
        "kcal": round(t["kcal"], 1),
        "protein": round(t["p"], 1),
        "needs_confirmation": False,
        "detail": f"原价 ¥{raw:.2f}" + (f" - 券 ¥{disc:.2f}" if disc else "") + "（估算，以 calculate-price 为准）",
    })

    group_ids = {f["id"] for f in group}
    price_by_id = {f["id"]: f["price"] for f in group}
    name_by_id = {f["id"]: f["name"] for f in group}
    for d in deals:
        deal_ids = set(d["items"])
        if not deal_ids.issubset(group_ids):
            continue                      # 团购套餐没凑齐，整条路径不成立
        uncovered_price = sum(price_by_id[i] for i in group_ids - deal_ids)
        final = d["price"] + uncovered_price
        paths.append({
            "channel": f"{d['channel']}·{d['name']}",
            "final": round(final, 2),
            "kcal": round(t["kcal"], 1),
            "protein": round(t["p"], 1),
            "needs_confirmation": True,   # 第三方渠道，购买前必须让用户确认
            "detail": (f"团购 ¥{d['price']:.2f} 整套含 {'、'.join(name_by_id[i] for i in deal_ids)}"
                       + (f" + 组合内其他单品 ¥{uncovered_price:.2f}" if uncovered_price else "")
                       + f"；该组合合计 {nutrition_line()}"
                       + (f"，限购{int(d['per_person_limit'])}份" if d["per_person_limit"] else "")),
            "confirm_hint": (f"这是 {d['channel']} 的第三方团购券（非麦当劳官方渠道），"
                             f"整套包含 {'、'.join(name_by_id[i] for i in deal_ids)}，"
                             f"合计 {nutrition_line()}。确认热量没问题再买；"
                             "团购价可能与平台实时价有差异，以平台页面为准。"),
        })

    paths.sort(key=lambda p: p["final"])
    return paths


# ---------- 计算 ----------
def totals(foods):
    t = {"kcal": 0.0, "p": 0.0, "f": 0.0, "c": 0.0, "sodium": 0.0, "price": 0.0}
    for f in foods:
        for k in t:
            t[k] += f.get(k, 0.0)
    return t


def score(food, goal_key, budget_kcal, protein_target):
    """为单个餐品打适配分。分数越高越适合当前目标。"""
    g = GOALS[goal_key]
    s = 0.0

    # 热量必须塞得下预算，这是硬门槛
    if food["kcal"] <= budget_kcal * 0.45:
        s += 45
    elif food["kcal"] <= budget_kcal:
        s += 25
    else:
        over = (food["kcal"] - budget_kcal) / max(budget_kcal, 1)
        s -= 60 * over + 15          # 超预算重罚

    # 蛋白密度：每 100 kcal 有多少克蛋白
    if food["kcal"] > 0:
        density = food["p"] * 100 / food["kcal"]
        s += min(density * 1.6, 30)

    # 目标倾向
    for t in g["prefer"]:
        if t in food["tags"]:
            s += 26
    for t in g["avoid"]:
        if t in food["tags"]:
            s -= 22

    if goal_key == "lose":
        if food["f"] > 25:
            s -= (food["f"] - 25) * 0.8
        if food["sodium"] > 800:
            s -= (food["sodium"] - 800) * 0.02
    if goal_key == "gain":
        if food["kcal"] >= 450:
            s += 22

    return s


def plan(foods, goal_key, budget_kcal, daily_kcal):
    g = GOALS[goal_key]
    protein_target = DEFAULT_PROTEIN_BASE * g["protein_rate"]
    daily_target = daily_kcal * g["kcal_rate"]

    ranked = sorted(
        foods,
        key=lambda f: score(f, goal_key, budget_kcal, protein_target),
        reverse=True
    )

    # 单品推荐：评分过阈值且热量在预算内
    singles = [
        f for f in ranked
        if f["kcal"] <= budget_kcal
        and score(f, goal_key, budget_kcal, protein_target) > 30
    ][:5]

    # 单品榜不要被零卡饮料霸榜：零卡饮品确实"能吃"，但对用户没有决策价值。
    # 只在正餐候选足够时保留一杯饮料，且排在正餐之后。
    drink_ids = {f["id"] for f in ranked if f["cat"] in ("饮品", "饮料", "咖啡")}
    meals = [f for f in singles if f["id"] not in drink_ids]
    if len(meals) >= 2:
        best_drink = next((f for f in singles if f["id"] in drink_ids), None)
        singles = meals[:4] + ([best_drink] if best_drink else [])

        # 套餐组合：主食必选，小食与饮品为可选槽位（枚举逻辑见 enumerate_combos）。
    combo, best = None, None
    for group, t in enumerate_combos(ranked, goal_key, budget_kcal):
        # 排序原则：以蛋白收益为主，但对"预算没用满"扣分。
        # 纯按蛋白排会让减脂预算下塞进过多热饮/小食；
        # 纯按蛋白密度排又会让维持预算大量闲置（485/800 白扔 315 大卡）。
        unused = max(0.0, budget_kcal - t["kcal"])
        val = (round(t["p"] - unused * 0.05, 3), -t["price"])
        if best is None or val > best[0]:
            best = (val, group)

    if best:
        combo = best[1]
    else:
        # 预算过紧，连"主食+饮品"都塞不下。
        # 此时取预算内评分最高的正餐单品，再补一杯饮品；
        # 绝不能直接退化成"热量最低"，否则减脂时会返回一杯零卡可乐。
        affordable = [f for f in ranked if f["kcal"] <= budget_kcal]
        meal_pool = [f for f in affordable if f["cat"] not in ("饮品", "饮料", "咖啡")]
        if meal_pool:
            combo = [meal_pool[0]]
            rest = budget_kcal - combo[0]["kcal"]
            drink_pool2 = sorted(
                (f for f in ranked
                 if f["cat"] in ("饮品", "饮料", "咖啡") and f["kcal"] <= rest),
                key=lambda f: f["kcal"])
            if drink_pool2:
                combo.append(drink_pool2[0])
        elif affordable:
            combo = [affordable[0]]

    return {
        "goal": goal_key,
        "goal_label": g["label"],
        "daily_target_kcal": round(daily_target),
        "budget_kcal": budget_kcal,
        "protein_target": round(protein_target),
        "singles": [{"name": f["name"], "kcal": f["kcal"], "p": f["p"],
                     "score": round(score(f, goal_key, budget_kcal, protein_target), 1)}
                    for f in singles],
        "combo": combo,
        "combo_total": totals(combo),
        "note": g["note"],
    }


def enumerate_combos(ranked, goal_key, budget_kcal):
    """生成候选套餐组合（生成器），产出 (group, totals) 二元组。

    主食必选，小食与饮品为可选槽位：
    强制每餐都塞小食是错的 —— 预算紧张时，"汉堡 + 零卡饮" 才是正确答案，
    所以这里枚举槽位的所有取舍组合（主食 / +小食 / +饮品 / +两者）。
    热量超预算的组合直接跳过。
    """
    mains = [f for f in ranked if f["cat"] in ("汉堡", "主餐", "早餐")]
    sides = [f for f in ranked if f["cat"] in ("小食", "配餐", "甜品")]
    drinks = [f for f in ranked if f["cat"] in ("饮品", "饮料", "咖啡")]

    # 没有任何主食分类时，用非饮品类最高分兜底，绝不用饮品当主食
    if not mains:
        mains = [f for f in ranked if f["cat"] not in ("饮品", "饮料", "咖啡")][:1]

    # 增肌目标下，碳水有助训练表现，优先选含糖饮品而非零卡/黑咖
    drink_pool = drinks[:6]
    if goal_key == "gain":
        drink_pool = sorted(
            drink_pool,
            key=lambda f: (0 if ("含糖" in f["tags"] or "高糖" in f["tags"]) else 1)
        )[:6]

    for m in (mains[:6] or ranked[:1]):
        for s_ in sides[:6] + [None]:
            for d in drink_pool[:6] + [None]:
                group = [m]
                if s_ and s_["id"] != m["id"]:
                    group.append(s_)
                if d and d["id"] not in [x["id"] for x in group]:
                    group.append(d)
                t = totals(group)
                if t["kcal"] > budget_kcal:
                    continue
                yield group, t


def value_plan(foods, goal_key, budget_kcal, daily_kcal, coupons,
               priority="balanced", min_protein=None, top_n=3, deals=None):
    """性价比联合优化：热量预算 + 真实优惠价一起算。

    与 plan() 的区别：plan 只看营养适配，价格仅作展示；
    value_plan 把「实付价」放进目标函数，回答的是——
    "同样的热量预算下，怎么点最便宜 / 最值"。

    priority:
      economy  —— 实付价最低优先，蛋白作并列裁决
      protein  —— 蛋白最高优先，价格作并列裁决
      balanced —— 每 10 元换多少克蛋白（蛋白性价比）优先

    deals: 团购数据（load_deals 加载）。每个组合会枚举「官方券路径」和
    「团购路径」两条支付方式，取实付最低者参与排序，全部路径附在输出里。
    团购券现实中不可与官方券叠加，因此团购路径不再叠官方券。
    """
    g = GOALS[goal_key]
    protein_target = DEFAULT_PROTEIN_BASE * g["protein_rate"]
    floor = min_protein if min_protein else protein_target * 0.5

    ranked = sorted(foods, key=lambda f: score(f, goal_key, budget_kcal, protein_target),
                    reverse=True)

    def make_option(group, t):
        paths = payment_paths(group, coupons, deals)
        best = paths[0]
        return {
            "group": group,
            "totals": t,
            "price": {"raw": round(t["price"], 2),
                      "final": best["final"],
                      "channel": best["channel"],
                      "official_final": next(
                          (p["final"] for p in paths if p["channel"].startswith("官方")),
                          best["final"]),
                      "payment_paths": paths},
            "p_per_yuan": t["p"] / best["final"] if best["final"] > 0 else 0.0,
        }

    options = []
    for group, t in enumerate_combos(ranked, goal_key, budget_kcal):
        if t["p"] < floor:
            continue
        options.append(make_option(group, t))

    relaxed = False
    if not options:
        # 蛋白下限过高导致无解（预算太紧 / 菜单太素），降级到不限蛋白再试一次
        relaxed = True
        for group, t in enumerate_combos(ranked, goal_key, budget_kcal):
            options.append(make_option(group, t))

    if priority == "economy":
        key = lambda o: (o["price"]["final"], -o["totals"]["p"])
    elif priority == "protein":
        # 蛋白按克取整分桶后再比价：为 0.3g 蛋白多花 10 元，用户不会买账
        key = lambda o: (-round(o["totals"]["p"]), o["price"]["final"])
    else:  # balanced：每元蛋白含量为主
        key = lambda o: (-round(o["p_per_yuan"], 4), o["price"]["final"])
    options.sort(key=key)
    top = options[:top_n]

    # 凑单建议：有没有"加点东西反而更便宜"的组合。
    # 场景：差 2 元到满减门槛，加一份小食后用券，实付反而比不加低。
    tips = []
    if coupons and top:
        base = top[0]
        base_final = base["price"]["final"]
        base_kcal = base["totals"]["kcal"]
        base_ids = {f["id"] for f in base["group"]}
        for c in coupons:
            if c["amount"] <= 0 or c["threshold"] <= base["price"]["raw"]:
                continue
            room = budget_kcal - base_kcal
            for add in ranked:
                if add["id"] in base_ids or add["kcal"] > room:
                    continue
                new_raw = base["price"]["raw"] + add["price"]
                if new_raw < c["threshold"]:
                    continue
                new_final = new_raw - min(c["amount"], new_raw)
                if new_final < base_final:
                    tips.append({
                        "reason": "凑单后实付更低",
                        "add_item": add["name"],
                        "add_kcal": add["kcal"],
                        "add_price": add["price"],
                        "coupon": c["name"],
                        "before_final": base_final,
                        "after_final": round(new_final, 2),
                        "save": round(base_final - new_final, 2),
                    })
        tips.sort(key=lambda x: -x["save"])
        tips = tips[:2]

    return {
        "mode": "value",
        "goal": goal_key,
        "goal_label": g["label"],
        "budget_kcal": budget_kcal,
        "protein_floor": round(floor, 1),
        "protein_floor_relaxed": relaxed,
        "priority": priority,
        "has_deals": bool(deals),
        "options": [
            {
                "items": [{"name": f["name"], "kcal": f["kcal"], "p": f["p"],
                           "price": f["price"]} for f in o["group"]],
                "total": {k: round(v, 1) for k, v in o["totals"].items()},
                "price": {"raw": o["price"]["raw"],
                          "final": o["price"]["final"],
                          "channel": o["price"]["channel"],
                          "official_final": o["price"]["official_final"],
                          "deal_saving_vs_official": round(
                              o["price"]["official_final"] - o["price"]["final"], 2)},
                "payment_paths": o["price"]["payment_paths"],
                "p_per_yuan": round(o["p_per_yuan"], 3),
                "p_per_10yuan": round(o["p_per_yuan"] * 10, 1),
            } for o in top
        ],
        "coupon_tips": tips,
        "note": g["note"],
    }


def pick_by_ids(foods, ids):
    idx = {f["id"]: f for f in foods}
    picked = [idx[i] for i in ids if i in idx]
    missing = [i for i in ids if i not in idx]
    if missing:
        print(f"[warn] 以下编码未在营养数据中找到，已跳过: {missing}", file=sys.stderr)
    return picked


def apply_coupons(price, coupons, ids):
    """筛出对该组合可用的券，返回 (原价, 最优优惠, 最优券)。"""
    usable = []
    for c in coupons:
        if c["threshold"] <= 0 or price >= c["threshold"]:
            if c["amount"] > 0:
                usable.append(c)
    if not usable:
        return price, 0.0, None
    best = max(usable, key=lambda c: c["amount"])
    return price, min(best["amount"], price), best


# ---------- 输出 ----------
def emit(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(description="麦麦营养顾问计算引擎")
    ap.add_argument("--nutrition-json", required=True,
                    help="list-nutrition-foods 工具返回保存的 JSON 文件")
    ap.add_argument("--coupons", help="available-coupons 工具返回保存的 JSON 文件")
    ap.add_argument("--deals", help="团购数据 JSON 文件（抖音/美团等渠道，格式见 assets/deals_sample.json）")
    ap.add_argument("--mode", choices=["plan", "calc", "savings", "value"], default="plan")
    ap.add_argument("--goal", choices=list(GOALS), default="lose")
    ap.add_argument("--budget-kcal", type=float, default=500)
    ap.add_argument("--daily-kcal", type=float, default=2000)
    ap.add_argument("--items", help="逗号分隔的餐品编码，用于 calc / savings 模式")
    ap.add_argument("--priority", choices=["economy", "protein", "balanced"],
                    default="balanced",
                    help="value 模式的排序优先级：economy 最便宜 / protein 蛋白最高 / balanced 性价比")
    ap.add_argument("--min-protein", type=float, default=None,
                    help="value 模式的蛋白下限（克），默认取目标蛋白的一半")
    a = ap.parse_args()

    foods = load_nutrition(a.nutrition_json)
    if not foods:
        print("[error] 营养数据为空或结构无法解析，请检查 list-nutrition-foods 的返回格式。",
              file=sys.stderr)
        sys.exit(2)

    if a.mode in ("calc", "savings"):
        ids = [x.strip() for x in (a.items or "").split(",") if x.strip()]
        if not ids:
            print("[error] --mode calc/savings 需要 --items 指定餐品编码", file=sys.stderr)
            sys.exit(2)
        group = pick_by_ids(foods, ids)
        t = totals(group)
        out = {
            "mode": a.mode,
            "items": [{"name": f["name"], "kcal": f["kcal"], "p": f["p"],
                       "f": f["f"], "c": f["c"], "sodium": f["sodium"]} for f in group],
            "total": {k: round(v, 1) for k, v in t.items()},
        }
        if a.mode == "savings":
            coupons = load_coupons(a.coupons)
            original = t["price"]
            _, disc, best = apply_coupons(original, coupons, ids)
            out["price"] = {
                "original": round(original, 2),
                "discount": round(disc, 2),
                "final": round(original - disc, 2),
                "best_coupon": best["name"] if best else None,
            }
            print("提示: 真实应付价请以 calculate-price 工具返回为准，本地估算仅供对比。",
                  file=sys.stderr)
        emit(out)
        return

    if a.mode == "value":
        coupons = load_coupons(a.coupons)
        deals = load_deals(a.deals)
        out = value_plan(foods, a.goal, a.budget_kcal, a.daily_kcal, coupons,
                         priority=a.priority, min_protein=a.min_protein, deals=deals)
        if deals:
            print("提示: 团购价为导入数据，可能与平台实时价有差异；下单前以平台页面为准。",
                  file=sys.stderr)
        if coupons:
            print("提示: 金额为本地估算（券面额叠加），真实应付价以 calculate-price 工具返回为准。",
                  file=sys.stderr)
        else:
            print("提示: 未提供优惠券文件（--coupons），官方渠道价格不含券优惠。",
                  file=sys.stderr)
        emit(out)
        return

    emit(plan(foods, a.goal, a.budget_kcal, a.daily_kcal))


if __name__ == "__main__":
    main()