# -*- coding: utf-8 -*-
"""两向对账：answer_ready_reason 到底在 decision_trace 还是 quality？

护栏读的是 quality。若引擎只写进 decision_trace ⇒ 是「判据读错位置」，
不是产品缺陷。零成本只读。
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
packs = sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json")))
stat = {"both": 0, "dt_only": 0, "q_only": 0, "none": 0, "ready_false": 0}
dt_only_samples = []
for f in packs:
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        continue
    q = d.get("quality") or {}
    dt = d.get("decision_trace") or {}
    if q.get("answer_ready") is False:
        stat["ready_false"] += 1
        rq = str(q.get("answer_ready_reason") or "").strip()
        rd = str(dt.get("answer_ready_reason") or "").strip()
        if rq and rd:
            stat["both"] += 1
        elif rd:
            stat["dt_only"] += 1
            if len(dt_only_samples) < 5:
                dt_only_samples.append((os.path.basename(f), rd[:70], rq))
        elif rq:
            stat["q_only"] += 1
        else:
            stat["none"] += 1
print("answer_ready=False 的包：", stat)
print("\n只在 decision_trace 有 reason 的样例：")
for s in dt_only_samples:
    print("  ", s)
