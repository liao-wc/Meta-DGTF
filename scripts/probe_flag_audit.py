# -*- coding: utf-8 -*-
"""probe 纪律审计（Round 90，零成本）：统计 probe_no_target_covered 对质量分的影响面。

输出 docs/probe_flag_audit_20261026.json；不修改引擎/门禁。
"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "probe_flag_audit_20261026.json"


def main() -> int:
    rows = []
    for f in glob.glob(str(ROOT / "outputs" / "*.packed.json")):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8",
                                             errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        q = d.get("quality") or {}
        if not q:
            continue
        flags = q.get("flags") or []
        rows.append({
            "file": os.path.basename(f),
            "question": str(d.get("question") or "")[:40],
            "qtype": (q.get("answer_summary") or {}).get("question_type"),
            "aq": q.get("answer_quality"),
            "ready": q.get("answer_ready"),
            "flags": flags,
            "probe_flag": "probe_no_target_covered" in flags,
        })
    n = len(rows)
    flagged = [r for r in rows if r["probe_flag"]]
    verified = [r for r in rows if r["aq"] == "verified"]
    verified_flagged = [r for r in verified if r["probe_flag"]]
    by_type = {}
    for r in flagged:
        k = str(r.get("qtype") or "?")
        by_type[k] = int(by_type.get(k, 0)) + 1
    summary = {
        "n_packs": n,
        "n_probe_flagged": len(flagged),
        "probe_flag_ratio": round(len(flagged) / n, 4) if n else 0.0,
        "n_verified": len(verified),
        "n_verified_and_flagged": len(verified_flagged),
        "verified_flagged_ratio": (round(len(verified_flagged) / len(verified), 4)
                                   if verified else 0.0),
        "flagged_by_qtype": by_type,
        "note": ("probe_no_target_covered 由引擎探针覆盖判定产生；verified 答案也可能被"
                 "打上该 flag 并压低 quality 分（引擎文件当前被并发会话占用，"
                 "按约定不编辑；此处仅量化影响面）。"),
        "rows": rows,
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("packs:", n, "| probe flagged:", len(flagged),
          "(%.1f%%)" % (100 * summary["probe_flag_ratio"]))
    print("verified:", len(verified), "| verified&flagged:",
          len(verified_flagged),
          "(%.1f%%)" % (100 * summary["verified_flagged_ratio"]))
    print("by qtype:", by_type)
    print("->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
