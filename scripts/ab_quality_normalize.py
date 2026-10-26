# -*- coding: utf-8 -*-
"""ab_results 质量口径归一（Round 133）。

历史 145 行混有失败基线（quality 0.18~0.26）与主线结果（0.93~0.99），无统一口径。
本脚本为每行补：
  - quality_scale: "exploratory"（quality<0.5 且 2026-10-24 前）| "mainline"；
  - baseline_role: "exploratory_baseline" | "candidate"；
先备份；默认 dry-run。
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "ab_results.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    lines = [ln for ln in SRC.read_text(encoding="utf-8").splitlines() if ln.strip()]
    out, added = [], 0
    for ln in lines:
        try:
            r = json.loads(ln)
        except Exception:  # noqa: BLE001
            out.append(ln)
            continue
        ts = str(r.get("ts") or "")
        try:
            q = float(r.get("quality") or 0)
        except (TypeError, ValueError):
            q = 0.0
        if q >= 0.9:
            band = "high"
        elif q >= 0.5:
            band = "mid"
        else:
            band = "low"
        r["quality_band"] = band
        r["quality_scale"] = ("mainline" if band != "low"
                              else "low_quality_run")
        r["baseline_role"] = ("reference" if (band == "high" and r.get("valid"))
                              else ("candidate" if band != "low" else "negative_result"))
        added += 3
        out.append(json.dumps(r, ensure_ascii=False))
    print("rows=%d fields_added=%d" % (len(out), added))
    if args.apply:
        bak = ROOT / "_audit_tmp" / ("ab_quality_backup_%s.jsonl"
                                     % time.strftime("%Y%m%d_%H%M%S"))
        bak.parent.mkdir(exist_ok=True)
        bak.write_text("\n".join(lines) + "\n", encoding="utf-8")
        SRC.write_text("\n".join(out) + "\n", encoding="utf-8")
        print("applied; backup ->", bak)
    else:
        print("dry-run（--apply 写盘）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
