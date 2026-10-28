# -*- coding: utf-8 -*-
"""诊断 12 个「两处都无 reason」的包：状态组合是什么，能不能推出可指认的原因。"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
packs = sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json")))
rows = []
for f in packs:
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        continue
    q = d.get("quality") or {}
    dt = d.get("decision_trace") or {}
    if q.get("answer_ready") is not False:
        continue
    if str(dt.get("answer_ready_reason") or "").strip():
        continue
    rows.append({
        "f": os.path.basename(f)[:46],
        "qt": dt.get("question_type"),
        "raw": dt.get("raw_answer_ready"),
        "proc": dt.get("process_ready"),
        "aq": dt.get("answer_quality"),
        "card": (dt.get("fact_card") or {}).get("status"),
        "off": len((dt.get("fact_card") or {}).get("official_evidence_ids") or []),
        "stop": str(dt.get("stop_reason") or "")[:30],
        "ans": str((dt.get("answer_summary") or {}).get("answer") or "")[:20],
    })
print("两处都无 reason 的包 =", len(rows))
for r in rows:
    print("  qt=%-10s raw=%-5s proc=%-5s aq=%-14s card=%-10s off=%d ans=%r | %s"
          % (r["qt"], r["raw"], r["proc"], r["aq"], r["card"], r["off"], r["ans"], r["f"]))
