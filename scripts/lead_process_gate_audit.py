# -*- coding: utf-8 -*-
"""离线过程门审计（零 API）：用已存 pack 统计 process_ledger 阻断来源与豁免占比。

用途：
  · 有多少 fact 跑次因元层张力被豁免（closure_waived）而放行；
  · 未豁免时到底哪层不达标（layer/why）；
  · 审计 repaired/unrepaired 分布；
  · 为「短事实题探针纪律」提供数据依据。
输出 docs/process_gate_audit_20261025.json。
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))

from dgtf_v2.process_ledger import build_ledger  # noqa: E402

OUT = ROOT / "docs" / "process_gate_audit_20261025.json"


def main() -> int:
    rows = []
    for f in sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json")),
                    key=os.path.getmtime):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8",
                                             errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        dt = d.get("decision_trace") or {}
        if not dt.get("question_type"):
            continue
        try:
            led = build_ledger(d)
        except Exception as e:  # noqa: BLE001
            rows.append({"file": os.path.basename(f), "error": str(e)})
            continue
        views = d.get("views") or {}
        aud = ((views.get("1") or {}).get("decidability_audit") or {})
        rows.append({
            "file": os.path.basename(f),
            "qtype": dt.get("question_type"),
            "standard_all": led.get("standard_all"),
            "notes": led.get("notes") or {},
            "layers_fail": [k for k, v in (led.get("layers") or {}).items()
                            if not v.get("standard_ok")],
            "audit_bad": int(aud.get("bad") or 0),
            "audit_repaired": sum(1 for r in (aud.get("rows") or [])
                                  if isinstance(r, dict) and r.get("issue")
                                  and str(r.get("after")) != str(r.get("before"))),
        })
    fact = [r for r in rows if r.get("qtype") == "fact" and "error" not in r]
    summary = {
        "n_packs_with_trace": len(rows),
        "n_fact": len(fact),
        "all_standard_true": sum(1 for r in fact
                                 if r.get("standard_all") is True),
        "waived_runs": sum(1 for r in fact
                           if (r.get("notes") or {}).get("closure_waived")),
        "waived_unsettled": dict(Counter(
            int((r.get("notes") or {}).get("closure_unsettled") or 0)
            for r in fact if (r.get("notes") or {}).get("closure_waived"))),
        "fact_fail_layers": dict(Counter(
            l for r in fact if r.get("standard_all") is not True
            for l in (r.get("layers_fail") or []))),
        "audit_repaired_rows": sum(r.get("audit_repaired") or 0 for r in fact),
        "audit_unrepaired_rows": sum(max(0, int(r.get("audit_bad") or 0)
                                         - int(r.get("audit_repaired") or 0))
                                     for r in fact),
        "rows": rows,
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("packs with trace:", summary["n_packs_with_trace"],
          "| fact:", summary["n_fact"])
    print("fact standard_all True:", summary["all_standard_true"],
          "| waived runs:", summary["waived_runs"],
          "| waived unsettled:", summary["waived_unsettled"])
    print("fact fail layers:", summary["fact_fail_layers"])
    print("audit repaired/unrepaired rows:",
          summary["audit_repaired_rows"], "/",
          summary["audit_unrepaired_rows"])
    print("→", OUT)
    # ★ [Round 70] 过程门护栏：未修复行必须为 0；standard 比例不降
    _ratio = (summary["all_standard_true"] / summary["n_fact"]
              if summary["n_fact"] else 0.0)
    _checks = [
        ("fact packs >= 80", summary["n_fact"] >= 80),
        ("audit unrepaired == 0", summary["audit_unrepaired_rows"] == 0),
        ("standard_all ratio >= 0.75", _ratio >= 0.75),
        ("waived runs <= 12", int(summary["waived_runs"]) <= 12),
    ]
    for _n, _ok in _checks:
        print(("PASS " if _ok else "FAIL ") + "guard: " + _n)
    if any(not ok for _n, ok in _checks):
        print("PROCESS GATE GUARD FAILED:",
              [n for n, ok in _checks if not ok])
        return 1
    print("PROCESS GATE GUARD PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
