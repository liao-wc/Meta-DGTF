# -*- coding: utf-8 -*-
"""ab_results.jsonl 旧 schema 成本字段回填（Round 132）。

历史 97/145 行缺 cost_window_cny；为保持 schema 可消费，统一补
`cost_window_cny: null` / `cost_attribution: "legacy_not_recorded"` / `cost_note`。
先备份到 _audit_tmp/ab_results_backup_<ts>.jsonl；默认 dry-run。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "ab_results.jsonl"


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    lines = SRC.read_text(encoding="utf-8").splitlines()
    out, added = [], 0
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:  # noqa: BLE001
            out.append(ln)
            continue
        changed = False
        if "cost_window_cny" not in r:
            r["cost_window_cny"] = None
            changed = True
        if "cost_attribution" not in r:
            r["cost_attribution"] = "legacy_not_recorded"
            changed = True
        if "cost_note" not in r:
            r["cost_note"] = ("Round 132 回填：旧行无余额窗口记录，"
                             "成本不可归因/不可求和")
            changed = True
        if changed:
            added += 1
        out.append(json.dumps(r, ensure_ascii=False))
    print("rows=%d backfilled=%d" % (len(out), added))
    if args.apply:
        bak_dir = ROOT / "_audit_tmp"
        bak_dir.mkdir(exist_ok=True)
        bak = bak_dir / ("ab_results_backup_%s.jsonl" % time.strftime("%Y%m%d_%H%M%S"))
        bak.write_text("\n".join(lines) + "\n", encoding="utf-8")
        SRC.write_text("\n".join(out) + "\n", encoding="utf-8")
        print("applied；备份 ->", bak)
    else:
        print("dry-run（--apply 写盘）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
