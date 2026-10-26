# -*- coding: utf-8 -*-
"""DSH 守卫完成回执：每轮巡检最后一步写回执，守卫读取后标记完成。"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dgtf_memory" / "guard_receipt.json"


def write_receipt(dispatch_id: str, status="completed", report="", checks=None, notes="", out=None):
    rec = {
        "dispatch_id": str(dispatch_id or ""),
        "status": str(status or "completed"),
        "completed_at": time.time(),
        "completed_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "report": str(report or ""),
        "checks": list(checks or []),
        "notes": str(notes or "")[:2000],
        "agent": "dsh",
    }
    target = Path(out) if out else OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(str(tmp), str(target))
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dispatch-id", required=True)
    ap.add_argument("--status", default="completed", choices=["completed", "failed", "blocked"])
    ap.add_argument("--report", default="")
    ap.add_argument("--checks", default="")
    ap.add_argument("--notes", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    checks = [x.strip() for x in str(a.checks or "").split(",") if x.strip()]
    rec = write_receipt(a.dispatch_id, a.status, a.report, checks, a.notes, out=(a.out or None))
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    return 0 if a.status == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
