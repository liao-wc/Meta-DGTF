# -*- coding: utf-8 -*-
"""深挖：6 条 verified+!ready(no reason) 到底缺了什么。

打印 quality 全键、answer_summary、decision_trace 关键字段、以及
引擎里 answer_ready 的赋值点线索。只读、零成本。
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
f = sorted(glob.glob(str(ROOT / "outputs" / "20261028_*心率*.packed.json")))[-1]
print("FILE:", os.path.basename(f))
d = json.loads(Path(f).read_text(encoding="utf-8"))

print("\n--- top keys ---")
print(sorted(d.keys()))

print("\n--- quality ---")
print(json.dumps(d.get("quality"), ensure_ascii=False, indent=1)[:2500])

print("\n--- answer_summary ---")
asum = d.get("answer_summary") or (d.get("quality") or {}).get("answer_summary") or {}
print(json.dumps(asum, ensure_ascii=False, indent=1)[:1500])

dt = d.get("decision_trace") or {}
print("\n--- decision_trace keys ---")
print(sorted(dt.keys()))
print("fact_card:", json.dumps(dt.get("fact_card"), ensure_ascii=False)[:800])
print("answer_ready:", dt.get("answer_ready"))

for k in ("final_answer", "answer", "conclusion", "summary"):
    if k in d:
        print("\n--- %s ---" % k, json.dumps(d[k], ensure_ascii=False)[:600])
