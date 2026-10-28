# -*- coding: utf-8 -*-
"""从历史 packed 回填 V2 schedule_outcome/structure 事件。

默认只回填 v2_events.jsonl 中尚不存在的 run_id；写前备份。
用法：
  python scripts/backfill_v2_events.py --dry-run
  python scripts/backfill_v2_events.py
"""
from __future__ import annotations
import argparse, json, shutil, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"
EVENTS = ROOT / "dgtf_memory" / "v2_events.jsonl"


def existing_ids() -> set:
    ids = set()
    if EVENTS.is_file():
        for ln in EVENTS.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                d = json.loads(ln)
            except Exception:
                continue
            rid = str(d.get("run_id") or "")
            if rid:
                ids.add(rid)
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    sys.path.insert(0, str(ROOT / "dgtf_engine"))
    try:
        from dgtf_v2.bridge import V2MemoryBridge
    except Exception as exc:
        print("FAIL import bridge:", exc)
        return 1
    known = existing_ids()
    files = sorted(OUTPUTS.glob("*.packed.json"), key=lambda x: x.stat().st_mtime)
    items = []
    for fp in files:
        try:
            d = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        rid = str(d.get("id") or "").strip()
        if not rid or rid in known:
            continue
        views = d.get("views") or {}
        if not any((views.get(k) or {}) for k in ("0", "1", "both", "all")):
            continue
        items.append((fp, d, rid))
    # 同一 run_id 可能对应多个 pack 副本，只回填一次，避免重复 outcome。
    _uniq = {}
    for _fp, _d, _rid in items:
        _uniq.setdefault(_rid, (_fp, _d, _rid))
    items = list(_uniq.values())
    if args.limit:
        items = items[:args.limit]
    print("existing_run_ids", len(known), "missing_packs", len(items),
          "dry_run", bool(args.dry_run))
    if args.dry_run:
        for fp, d, rid in items[-8:]:
            print("would_add", rid, fp.name[:60])
        return 0
    if not items:
        return 0
    if EVENTS.is_file():
        bak = EVENTS.with_name("v2_events.jsonl.bak_" + time.strftime("%Y%m%d_%H%M%S"))
        shutil.copy2(EVENTS, bak)
        print("backup", bak)
    bridge = V2MemoryBridge(EVENTS, enabled=True, allow_anon=False)
    added_runs = added_events = skipped = 0
    for fp, d, rid in items:
        try:
            out = bridge.record_packed(d) or {}
            ev = int(out.get("events") or 0)
            if ev:
                added_runs += 1
                added_events += ev
                print("added", rid, ev)
            else:
                skipped += 1
        except Exception as exc:
            print("skip", rid, type(exc).__name__, str(exc)[:120])
            skipped += 1
    print(json.dumps({"ok": True, "runs": added_runs, "events": added_events,
                      "skipped": skipped, "total": len(items)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
