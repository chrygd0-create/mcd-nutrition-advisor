# -*- coding: utf-8 -*-
"""真实数据冒烟测试：用 MCP 拉回的官方营养数据跑三种目标，写报告到 live_report.txt。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(HERE, "scripts", "nutrition_calculator.py")
LIVE = os.path.join(HERE, "assets", "nutrition_live.json")

lines = [f"数据源: list-nutrition-foods 官方实时返回 ({os.path.getsize(LIVE)} bytes)", ""]
for goal, budget in [("lose", 500), ("keep", 700), ("gain", 900)]:
    p = subprocess.run(
        [sys.executable, SCRIPT, "--goal", goal, "--budget-kcal", str(budget),
         "--nutrition-json", LIVE, "--mode", "plan"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if p.returncode != 0:
        lines.append(f"{goal} {budget}kcal -> FAILED: {p.stderr[:200]}")
        continue
    d = json.loads(p.stdout)
    names = " + ".join(x["name"] for x in d["combo"])
    t = d["combo_total"]
    singles = "、".join(f'{s["name"]}({s["kcal"]:.0f})' for s in d["singles"])
    lines.append(
        f'{goal:5s} {budget:>4}kcal -> {names}\n'
        f'              合计 {t["kcal"]:.0f}kcal / 蛋白 {t["p"]:.1f}g / 钠 {t["sodium"]:.0f}mg'
        f' / 预算利用率 {t["kcal"]/budget*100:.0f}%\n'
        f'              单品榜: {singles}'
    )

with open(os.path.join(ROOT, "live_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("ok")