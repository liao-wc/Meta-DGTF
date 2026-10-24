# -*- coding: utf-8 -*-
"""模式级 Pareto 选档 / M4 auto-fused 规划。

用法：
  python scripts/mode_fusion.py
  python scripts/mode_fusion.py --min-quality 0.95 --max-wall 1200 --json
  python scripts/mode_fusion.py --require-web
  python scripts/mode_fusion.py --cascade
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))

from dgtf_v2.mode_fusion import MODES, fused_plan, scenario_table, select_mode  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-quality", type=float, default=None)
    ap.add_argument("--max-wall", type=float, default=None)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--require-web", action="store_true")
    ap.add_argument("--prefer", default="quality", choices=("quality", "wall", "tokens"))
    ap.add_argument("--cascade", action="store_true")
    ap.add_argument("--scenarios", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.scenarios:
        out = {"modes": MODES, "scenarios": scenario_table()}
    elif args.cascade:
        out = fused_plan(min_quality=args.min_quality, max_wall=args.max_wall,
                         max_tokens=args.max_tokens,
                         require_web=args.require_web, cascade=True)
    else:
        out = select_mode(min_quality=args.min_quality, max_wall=args.max_wall,
                          max_tokens=args.max_tokens,
                          require_web=args.require_web, prefer=args.prefer)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    if args.scenarios:
        print("保留模式：", "、".join("%s(%s)" % (k, MODES[k]["name"]) for k in ("B", "serial", "fast")))
        print("场景选择：")
        for r in out["scenarios"]:
            print("  %-10s -> %-6s quality=%s tokens=%s wall=%s  (%s)" % (
                r["scenario"], r["mode"], r["quality"], r["tokens"],
                r["wall"], r["reason"]))
        return 0
    if args.cascade:
        print("M4 auto-fused：", json.dumps(out.get("policy"), ensure_ascii=False))
        print("首选：", (out.get("first") or {}).get("mode"),
              (out.get("first") or {}).get("reason"))
        if out.get("cascade"):
            print("级联：", json.dumps(out["cascade"], ensure_ascii=False))
        return 0
    print("选中模式：", out.get("mode"))
    print("原因：", out.get("reason"))
    print("读数：", json.dumps(out.get("info") or {}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
