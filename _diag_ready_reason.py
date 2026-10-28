# -*- coding: utf-8 -*-
"""普查：所有包里 answer_ready=False 时有没有写 reason。零成本只读。"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
packs = sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json")))
tot = no_ready = no_ready_no_reason = 0
samples = []
for f in packs:
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        continue
    q = d.get("quality") or {}
    ready = q.get("answer_ready")
    tot += 1
    if ready is False:
        no_ready += 1
        reason = str(q.get("answer_ready_reason") or q.get("repair_note") or "").strip()
        if not reason:
            no_ready_no_reason += 1
            if len(samples) < 8:
                samples.append(os.path.basename(f))
print("packs=%d | ready=False: %d | 其中无 reason: %d" % (tot, no_ready, no_ready_no_reason))
print("样例:", samples)
