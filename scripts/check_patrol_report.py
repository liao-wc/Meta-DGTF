# -*- coding: utf-8 -*-
"""确定性巡检报告门禁：报告存在、关键段落齐全、patrol_history 有对应记录。"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "docs" / "reports"
HISTORY = ROOT / "dgtf_memory" / "patrol_history.jsonl"
NEEDLES = ["真跑", "检查项", "修复", "验证", "风险"]


def latest_report() -> Path | None:
    files = sorted(REPORTS.glob("patrol_*.md"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default="")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rp = Path(args.report) if args.report else latest_report()
    bad = []
    if rp is None or not rp.is_file():
        print("FAIL 报告不存在")
        return 1
    text = rp.read_text(encoding="utf-8", errors="replace")
    for n in NEEDLES:
        if n not in text:
            bad.append("缺少段落:" + n)
    events = []
    if HISTORY.is_file():
        for ln in HISTORY.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                events.append(json.loads(ln))
            except Exception:
                pass
    done = [e for e in events if str(e.get("status") or "").startswith("completed") and str(e.get("report") or "").strip()]
    if not events:
        bad.append("patrol_history.jsonl 无记录")
    elif not done:
        bad.append("patrol_history.jsonl 无 completed 记录")
    else:
        last = done[-1]
        for k in ("status", "domain", "question", "report"):
            if not str(last.get(k) or "").strip():
                bad.append("history 缺字段:" + k)
    print("REPORT", rp)
    print("CHECK", "PASS" if not bad else "FAIL", "; ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
