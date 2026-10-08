#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成双盲评测评分空表 eval_scorecard_template.csv

结构：3 位评审 x 60 份产物 = 180 行
  60 份 = 20 题(赛道X 10 + 赛道Y 10) x 3 个系统
system_label 列留空，由第三方在封存映射表后填写；评审只看到 product_id 与随机标签
"""
import csv
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "eval_scorecard_template.csv")

REVIEWERS = ["R1", "R2", "R3"]
SESSION_SIZE = 5  # 每 session 5 份 x 20 分钟 = 100 分钟上限内的保守值

items = [("X%02d" % i, "X") for i in range(1, 11)] + \
        [("Y%02d" % i, "Y") for i in range(1, 11)]

# 60 份产物：题目 x 系统槽位(3)。编号连续，与系统无对应关系
products = []
pid = 0
for item_id, track in items:
    for slot in range(3):
        pid += 1
        products.append(("P%03d" % pid, item_id, track))

FIELDS = [
    "reviewer_id", "session_no", "product_id", "item_id", "track",
    "system_label", "chars", "read_pct", "fatigue",
    "claims_sampled", "checkable_facts",
    "errors_found", "errors_unflagged", "claims_total", "g2_recalled",
    "g1_hit", "tensions_proposed", "tensions_fabricated",
    "decision_usable", "guess_system", "notes",
]

rows = []
for rv in REVIEWERS:
    # 顺序由评审侧随机化脚本打乱；这里按 product_id 顺序铺，仅为骨架
    for idx, (prod, item_id, track) in enumerate(products):
        rows.append({
            "reviewer_id": rv,
            "session_no": idx // SESSION_SIZE + 1,
            "product_id": prod,
            "item_id": item_id,
            "track": track,
            "system_label": "",
            "chars": "", "read_pct": "", "fatigue": "",
            "claims_sampled": "", "checkable_facts": "",
            "errors_found": "", "errors_unflagged": "",
            "claims_total": "", "g2_recalled": "",
            "g1_hit": "", "tensions_proposed": "", "tensions_fabricated": "",
            "decision_usable": "", "guess_system": "", "notes": "",
        })

with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)

print("written: %s (%d rows)" % (OUT, len(rows)))
