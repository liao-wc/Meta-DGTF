# -*- coding: utf-8 -*-
"""研究层 verdict 空的 19 个包：settle 为什么是 None？
元层 crystallize 的值分布：是不是只有 0.5/1.0 两档（零区分度）？
"""
from __future__ import annotations

import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
packs = sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json")))
r1_empty, meta_vals = [], []
for f in packs:
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        continue
    views = d.get("views") or {}
    v1 = views.get("1") or {}
    if v1 and not str(v1.get("goal_verdict") or "").strip():
        r1_empty.append({
            "f": Path(f).name[:40],
            "settlement": bool(v1.get("settlement")),
            "covered_answer": bool(v1.get("covered_answer")),
            "cov_aspects": len(v1.get("covered_aspects") or []),
            "uncov_aspects": len(v1.get("uncovered_aspects") or []),
            "belief_counts": bool(v1.get("belief_status_counts")),
            "conv": str(((v1.get("divergence") or {}).get("state")) or "")[:8],
        })
    va = views.get("all") or {}
    gv = str(va.get("goal_verdict") or "")
    m = re.search(r"=\s*([0-9.]+)", gv)
    if m:
        meta_vals.append(round(float(m.group(1)), 3))

print("研究层 verdict 空的包 =", len(r1_empty))
for r in r1_empty[:12]:
    print("  settle依据: settlement=%-5s covered_answer=%-5s cov=%d uncov=%d "
          "belief=%-5s conv=%r | %s"
          % (r["settlement"], r["covered_answer"], r["cov_aspects"],
             r["uncov_aspects"], r["belief_counts"], r["conv"], r["f"]))
print()
from collections import Counter
print("元层 crystallize 值分布:", dict(Counter(meta_vals)))
