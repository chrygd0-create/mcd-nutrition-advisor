# -*- coding: utf-8 -*-
"""开发自测脚本：验证配餐引擎在多种目标与模式下的输出是否合理。

无需 Token 与网络，使用 assets/nutrition_fallback.json 降级数据跑。
输出写入项目根目录 test_report.txt。
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(HERE, "scripts", "nutrition_calculator.py")
NUTRITION = os.path.join(HERE, "assets", "nutrition_fallback.json")
COUPONS = os.path.join(HERE, "assets", "coupons_sample.json")
DEALS = os.path.join(HERE, "assets", "deals_sample.json")


def run(*args):
    p = subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True, text=True, encoding="utf-8",
    )
    if p.returncode != 0:
        return None, p.stderr.strip()[:300]
    return json.loads(p.stdout), p.stderr.strip()


lines = []
fails = []

# ---------- 1. plan 模式：三种目标 ----------
lines.append("== 1. plan 模式（营养目标配餐）==")
for goal, budget in [("lose", 500), ("lose", 700), ("keep", 800), ("keep", 1200), ("gain", 900)]:
    d, err = run("--goal", goal, "--budget-kcal", str(budget),
                 "--nutrition-json", NUTRITION, "--mode", "plan")
    if d is None:
        fails.append(f"plan {goal}/{budget}: {err}")
        continue
    names = " + ".join(x["name"] for x in d["combo"])
    t = d["combo_total"]
    singles = "、".join(f'{s["name"]}({s["kcal"]:.0f})' for s in d["singles"])
    lines.append(
        f'{goal:5s} {budget:>4}kcal -> {names}\n'
        f'              合计 {t["kcal"]:.0f}kcal / 蛋白 {t["p"]:.1f}g / ¥{t["price"]:.0f}'
        f' / 预算利用率 {t["kcal"]/budget*100:.0f}%\n'
        f'              单品榜: {singles}'
    )
    if t["kcal"] > budget:
        fails.append(f"plan {goal}/{budget}: 组合热量 {t['kcal']} 超预算！")

# ---------- 2. calc 模式 ----------
lines.append("\n== 2. calc 模式（指定组合算营养）==")
d, err = run("--nutrition-json", NUTRITION, "--items", "m1,d1", "--mode", "calc")
if d is None:
    fails.append(f"calc: {err}")
else:
    lines.append(f'巨无霸 + 可乐(中) -> {d["total"]["kcal"]:.0f}kcal / 蛋白 {d["total"]["p"]}g / ¥{d["total"]["price"]:.0f}')

# ---------- 3. savings 模式 ----------
lines.append("\n== 3. savings 模式（指定组合叠加券）==")
d, err = run("--nutrition-json", NUTRITION, "--items", "m1,d1,s1",
             "--coupons", COUPONS, "--mode", "savings")
if d is None:
    fails.append(f"savings: {err}")
else:
    pr = d["price"]
    lines.append(f'巨无霸+可乐+薯条: 原价 ¥{pr["original"]} -> 券后 ¥{pr["final"]}（{pr["best_coupon"]}）')

# ---------- 4. value 模式：三种优先级 ----------
lines.append("\n== 4. value 模式（热量 + 优惠券联合优化）==")
for prio in ("economy", "balanced", "protein"):
    d, err = run("--goal", "keep", "--budget-kcal", "700",
                 "--nutrition-json", NUTRITION, "--coupons", COUPONS,
                 "--mode", "value", "--priority", prio)
    if d is None:
        fails.append(f"value/{prio}: {err}")
        continue
    lines.append(f"[priority={prio}]")
    for i, o in enumerate(d["options"], 1):
        names = " + ".join(x["name"] for x in o["items"])
        pr = o["price"]
        lines.append(
            f'  方案{i}: {names}\n'
            f'          {o["total"]["kcal"]:.0f}kcal / 蛋白 {o["total"]["p"]:.0f}g'
            f' / 原价¥{pr["raw"]} -> 实付¥{pr["final"]}（{pr["channel"]}）'
            f' / 每10元换{o["p_per_10yuan"]}g蛋白'
        )
    for tip in d["coupon_tips"]:
        lines.append(
            f'  凑单提示: 加「{tip["add_item"]}」({tip["add_kcal"]:.0f}kcal/¥{tip["add_price"]})'
            f' 用「{tip["coupon"]}」后实付 ¥{tip["before_final"]} -> ¥{tip["after_final"]}，'
            f'反而省 ¥{tip["save"]}'
        )

# ---------- 5. value 模式：减脂 + 最便宜 ----------
lines.append("\n== 5. value 模式（减脂 500kcal，只要最便宜）==")
d, err = run("--goal", "lose", "--budget-kcal", "500",
             "--nutrition-json", NUTRITION, "--coupons", COUPONS,
             "--mode", "value", "--priority", "economy")
if d is None:
    fails.append(f"value-lose: {err}")
else:
    o = d["options"][0]
    names = " + ".join(x["name"] for x in o["items"])
    pr = o["price"]
    lines.append(
        f'最便宜方案: {names}\n'
        f'  {o["total"]["kcal"]:.0f}kcal / 蛋白 {o["total"]["p"]:.0f}g'
        f' / 原价¥{pr["raw"]} -> 实付¥{pr["final"]}（{pr["channel"]}）'
    )
    if o["total"]["kcal"] > 500:
        fails.append("value lose: 超预算")
    if o["total"]["p"] < d["protein_floor"] and not d["protein_floor_relaxed"]:
        fails.append("value lose: 蛋白低于下限")

# ---------- 6. 无券降级 ----------
lines.append("\n== 6. value 模式（不提供券文件）==")
d, err = run("--goal", "lose", "--budget-kcal", "500",
             "--nutrition-json", NUTRITION, "--mode", "value")
if d is None:
    fails.append(f"value-nocoupon: {err}")
else:
    lines.append(f'正常返回 {len(d["options"])} 个方案，价格不含券优惠（符合预期）')

# ---------- 7. 团购比价 ----------
lines.append("\n== 7. value 模式（团购 + 官方券 跨渠道比价）==")
for prio in ("economy", "protein"):
    d, err = run("--goal", "keep", "--budget-kcal", "700",
                 "--nutrition-json", NUTRITION, "--coupons", COUPONS,
                 "--deals", DEALS, "--mode", "value", "--priority", prio)
    if d is None:
        fails.append(f"value-deals/{prio}: {err}")
        continue
    lines.append(f"[priority={prio}] has_deals={d['has_deals']}")
    for i, o in enumerate(d["options"], 1):
        names = " + ".join(x["name"] for x in o["items"])
        pr = o["price"]
        lines.append(
            f'  方案{i}: {names}\n'
            f'          {o["total"]["kcal"]:.0f}kcal / 蛋白 {o["total"]["p"]:.0f}g'
            f' / 原价¥{pr["raw"]} -> 最优¥{pr["final"]}（{pr["channel"]}）'
            f' / 官方渠道¥{pr["official_final"]}'
            + (f' / 团购省¥{pr["deal_saving_vs_official"]}' if pr["deal_saving_vs_official"] > 0 else '')
        )
        for p in o["payment_paths"]:
            mark = " ⚠需确认" if p.get("needs_confirmation") else ""
            lines.append(f'            路径: {p["channel"]} = ¥{p["final"]}{mark}（{p["detail"]}）')
            if p.get("confirm_hint"):
                lines.append(f'            确认提示: {p["confirm_hint"]}')
    # 校验 1：每个方案的 final 必须等于所有路径中最低价
    for o in d["options"]:
        min_path = min(p["final"] for p in o["payment_paths"])
        if abs(o["price"]["final"] - min_path) > 0.001:
            fails.append(f"value-deals: 方案 final {o['price']['final']} != 最低路径 {min_path}")
    # 校验 2：路径上的热量必须等于组合总热量（团购整套买，营养不缩水）
    for o in d["options"]:
        for p in o["payment_paths"]:
            if abs(p["kcal"] - o["total"]["kcal"]) > 0.1:
                fails.append(f"value-deals: 路径热量 {p['kcal']} != 组合热量 {o['total']['kcal']}")
    if prio == "protein":
        win = d["options"][0]["price"]["channel"]
        lines.append(f'  （protein 最优渠道: {win}）')

report = "\n".join(lines)
if fails:
    report += "\n\n== 失败项 ==\n" + "\n".join(fails)
else:
    report += "\n\n全部通过 ✓"

with open(os.path.join(ROOT, "test_report.txt"), "w", encoding="utf-8") as f:
    f.write(report)
print(f"fails={len(fails)}")