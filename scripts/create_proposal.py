# -*- coding: utf-8 -*-
"""DSH 守护通用人工确认提案写入（幂等）。

用法：
  python scripts/create_proposal.py --title "..." --detail "..." --plan-file plan.md
  python scripts/create_proposal.py --title "..." --detail "..." --plan "步骤..."
"""
from __future__ import annotations
import argparse, hashlib, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDIR = ROOT / "dgtf_memory" / "dsh_proposals"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--detail", default="")
    ap.add_argument("--plan", default="")
    ap.add_argument("--plan-file", default="")
    ap.add_argument("--severity", default="med", choices=["high", "med", "low"])
    ap.add_argument("--category", default="quality_flag")
    ap.add_argument("--source", default="dsh_guard")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    plan = args.plan
    if args.plan_file:
        plan = (ROOT / args.plan_file).read_text(encoding="utf-8")
    plan = str(plan or "").strip()
    if len(plan) < 20:
        print("ERROR plan 至少 20 字")
        return 2
    h = hashlib.sha256((args.title + "|" + args.source).encode("utf-8")).hexdigest()[:10]
    pid = "prop-manual-" + h
    rec = {"id": pid, "ts": time.time(),
           "task": {"kind": args.category, "severity": args.severity,
                    "title": args.title[:200], "detail": args.detail[:4000],
                    "source_run": args.source},
           "plan": plan[:8000], "plan_gap": False, "session_id": "",
           "conversation_id": "", "status": "pending", "approver": "",
           "events": [], "human_required": True}
    if args.dry_run:
        print(json.dumps(rec, ensure_ascii=False, indent=1)[:2000])
        return 0
    PDIR.mkdir(parents=True, exist_ok=True)
    p = PDIR / (pid + ".json")
    if p.exists():
        print("EXISTS", pid)
        return 0
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)
    print("CREATED", pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
