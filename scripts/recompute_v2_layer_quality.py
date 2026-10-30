# -*- coding: utf-8 -*-
"""把历史 V2 schedule_outcome 从整跑 quality 重算为层局部质量。

只读 packed 的 views/quality.layers；写前备份 v2_events.jsonl。
层局部分数是确定性启发式（layer_signals_v1），必须保留 quality_overall。
"""
from __future__ import annotations
import argparse, json, shutil, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "dgtf_memory" / "v2_events.jsonl"
OUTPUTS = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "dgtf_engine"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="只读一致性：对比盘上层质量与重算值，有差异 exit 1（不写）")
    args = ap.parse_args()
    from dgtf_v2.bridge import _layer_quality
    packs = {}
    for fp in sorted(OUTPUTS.glob("*.packed.json"), key=lambda x: x.stat().st_mtime):
        try:
            d = json.loads(fp.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        rid = str(d.get("id") or "").strip()
        if rid:
            packs[rid] = d
    rows = []
    changed = 0
    diff = []
    for ln in EVENTS.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(ln)
        except Exception:
            continue
        if isinstance(e, dict) and str(e.get("kind")) == "schedule_outcome":
            pl = e.get("payload") if isinstance(e.get("payload"), dict) else {}
            rid = str(e.get("run_id") or "")
            tmpl = str(pl.get("template") or "")
            d = packs.get(rid)
            if d and tmpl.startswith(("0:r", "1:r", "both:r", "all:r")):
                entry = tmpl.split(":", 1)[0]
                try:
                    _qbase = float(pl.get("quality_overall")
                                   if pl.get("quality_overall") is not None
                                   else (pl.get("quality") or 0))
                    q_local, extra = _layer_quality(d, entry, _qbase)
                except Exception:
                    q_local, extra = None, {}
                if q_local is not None:
                    pl["quality"] = q_local
                    for k, v in extra.items():
                        pl.setdefault(k, v)
                    changed += 1
                    if args.check and str(pl.get("quality")) != str(q_local):
                        diff.append((rid, tmpl, pl.get("quality"), q_local))
        rows.append(e)
    print("outcomes_changed", changed, "rows", len(rows), "dry_run", args.dry_run,
          "check", args.check, "diff", len(diff))
    if args.check:
        for _d in diff[:10]:
            print("DIFF", _d)
        return 0 if not diff else 1
    if args.dry_run or not changed:
        return 0
    bak = EVENTS.with_name("v2_events.jsonl.bak_requal_" + time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(EVENTS, bak)
    tmp = EVENTS.with_suffix(".jsonl.tmp")
    tmp.write_text(chr(10).join(json.dumps(e, ensure_ascii=False) for e in rows) + chr(10), encoding="utf-8")
    tmp.replace(EVENTS)
    print("backup", bak)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
