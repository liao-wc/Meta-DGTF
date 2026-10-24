# -*- coding: utf-8 -*-
"""全流程帕累托基线：扫描 outputs/*.packed.json，输出质量/成本非支配前沿。

用法：
  python scripts/pareto_flow.py [--dir outputs] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))

from dgtf_v2.pareto_flow import load_packed_runs, report  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="outputs")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = ROOT / args.dir
    packs = sorted(out.glob("*.packed.json"), key=lambda p: p.stat().st_mtime)
    rows = load_packed_runs(packs)
    rep = report(rows)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 0
    print("全流程帕累托基线 · %d 次真跑 · %d 个非支配点" % (len(rows), len(rep["frontier"])))
    print("id	quality	tokens	calls	runs")
    for r in rep["rows"]:
        mark = "*" if r["id"] in rep["frontier"] else " "
        print("%s%s	%.4f	%d	%d	route=%s" % (
            mark, r["id"], r["quality"], r["tokens"], r["calls"],
            ",".join(r.get("route") or [])))
    if rep["best_quality"]:
        b = rep["best_quality"]
        print("\n最佳质量: %s (%.4f, %d tokens, %d calls)" % (
            b["id"], b["quality"], b["tokens"], b["calls"]))
    if rep["cheapest"]:
        c = rep["cheapest"]
        print("最低成本: %s (%.4f, %d tokens)" % (c["id"], c["quality"], c["tokens"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
