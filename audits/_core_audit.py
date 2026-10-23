# -*- coding: utf-8 -*-
"""core-audit 工具：对 packed 跑 core_duty.audit_packed + bridge.contract_report。

用法（在仓库根执行）：
  python audits/_core_audit.py hist  --out audits/core_duty_20_latest.json [--n 20] [--cutoff <epoch>]
  python audits/_core_audit.py one   --packed <path> --out audits/core_duty_new_packed.json

只读 packed；只写 --out 指定文件。不改 outputs/ 与源码。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dgtf_v2.core_duty import audit_packed  # noqa: E402
from dgtf_v2.bridge import V2MemoryBridge  # noqa: E402


def _iso_ts(mtime: float) -> str:
    return datetime.fromtimestamp(mtime).astimezone().isoformat(timespec="seconds")


def _len(x) -> int:
    return len(x) if isinstance(x, (list, tuple)) else 0


def _raw_facts(packed: dict) -> dict:
    views = packed.get("views") or {}
    v0 = views.get("0") or {}
    v1 = views.get("1") or {}
    vb = views.get("both") or {}
    va = views.get("all") or {}
    dp = v1.get("decidable_product") or {}
    if not isinstance(dp, dict):
        dp = {}
    shadow = packed.get("v2_shadow") or {}
    core = shadow.get("core") if isinstance(shadow, dict) else None
    if not isinstance(core, dict):
        core = {}
    return {
        "top_keys": sorted(packed.keys()),
        "route": [str(x) for x in (packed.get("route") or [])],
        "rounds": dict(packed.get("rounds") or {}),
        "run_id": str(packed.get("id") or packed.get("run_id") or ""),
        "question": str(packed.get("question") or "")[:80],
        "llm_calls": packed.get("llm_calls"),
        "llm_tokens": packed.get("llm_tokens"),
        "quality": {
            "coverage": (packed.get("quality") or {}).get("coverage"),
            "tri_ratio": (packed.get("quality") or {}).get("tri_ratio"),
            "answered": (packed.get("quality") or {}).get("answered"),
            "answerable_total": (packed.get("quality") or {}).get("answerable_total"),
        },
        "views_keys": sorted(views.keys()),
        "view0": {
            "candidates": _len(v0.get("candidates")),
            "amps": _len(v0.get("amps")),
            "probes": _len(v0.get("probes")),
            "suspensions": _len(v0.get("suspensions")),
        },
        "view1": {
            "_actions_len": _len(v1.get("_actions")),
            "has__actions": bool(v1.get("_actions")),
            "_not_do_len": _len(v1.get("_not_do")),
            "dp_actions_len": _len(dp.get("actions")),
            "dp_keys": sorted(dp.keys()),
            "dp_evidence_len": _len(dp.get("evidence")),
        },
        "view_both": {
            "adjudications": _len(vb.get("adjudications")),
            "threads": _len(vb.get("threads")),
            "has_manifest": bool(vb.get("manifest")),
        },
        "view_all": {
            "keys": sorted(va.keys()),
            "actions_len": _len(va.get("actions")),
            "not_do_len": _len(va.get("not_do")),
            "decision_len": len(str(va.get("decision") or "").strip()),
            "residual_risks_len": _len(va.get("residual_risks")),
            "provenance_len": _len(va.get("provenance")),
            "confidence": va.get("confidence"),
            "decidable_product_present": bool(va.get("decidable_product")),
        },
        "root_actions_len": _len(packed.get("actions")),
        "root_not_do_len": _len(packed.get("not_do")),
        "v2_shadow": {
            "present": bool(shadow),
            "mode": shadow.get("mode") if isinstance(shadow, dict) else None,
            "core_present": bool(core),
            "core_ok": core.get("ok"),
            "core_gaps": core.get("gaps"),
            "core_overreach": core.get("overreach"),
            "core_error": core.get("error"),
            "contracts_ok": ((shadow.get("contracts") or {})
                            .get("ok") if isinstance(shadow, dict) else None),
        },
    }


def _audit_one(packed: dict) -> dict:
    raw = _raw_facts(packed)
    audit = audit_packed(packed)
    facts = {
        "file": None,
        "mtime": None,
        "size": None,
        "raw": raw,
        "audit": audit,
    }
    return facts


def _contract(packed: dict) -> dict:
    try:
        rep = V2MemoryBridge().contract_report(packed, gate="warn")
        return {"ok": rep.get("ok"), "checked": rep.get("checked"),
                "violations": rep.get("violations")}
    except Exception as e:  # 只读体检，失败也记录不抛
        return {"ok": None, "error": "%s: %s" % (type(e).__name__, e)}


def _row(path: Path, packed: dict) -> dict:
    r = _audit_one(packed)
    st = path.stat()
    r["file"] = path.name
    r["path"] = str(path.relative_to(ROOT))
    r["mtime"] = _iso_ts(st.st_mtime)
    r["mtime_epoch"] = round(st.st_mtime, 3)
    r["size"] = st.st_size
    r["contract"] = _contract(packed)
    return r


def _summarize(rows: list[dict]) -> dict:
    ok = sum(1 for r in rows if r["audit"].get("ok"))
    over_files = [r["file"] for r in rows if r["audit"].get("overreach")]
    gap_files = [r["file"] for r in rows if r["audit"].get("gaps")]
    over_kinds: dict[str, int] = {}
    gap_kinds: dict[str, int] = {}
    repair_kinds: dict[str, int] = {}
    layer_ok = {"0": 0, "1": 0, "both": 0, "all": 0}
    for r in rows:
        for k in r["audit"].get("overreach") or []:
            over_kinds[k] = over_kinds.get(k, 0) + 1
        for k in r["audit"].get("gaps") or []:
            gap_kinds[k] = gap_kinds.get(k, 0) + 1
        for rep in r["audit"].get("repairs") or []:
            key = rep.split(":")[0]
            repair_kinds[key] = repair_kinds.get(key, 0) + 1
        for e, lay in (r["audit"].get("layers") or {}).items():
            if lay.get("ok"):
                layer_ok[e] = layer_ok.get(e, 0) + 1
    return {
        "runs": len(rows),
        "ok": ok,
        "not_ok": len(rows) - ok,
        "overreach_files": len(over_files),
        "overreach_kinds": dict(sorted(over_kinds.items())),
        "gap_files": len(gap_files),
        "gap_kinds": dict(sorted(gap_kinds.items())),
        "repair_kinds": dict(sorted(repair_kinds.items())),
        "layer_ok": layer_ok,
        "raw_view1_has__actions_files": sum(
            1 for r in rows if r["raw"]["view1"]["has__actions"]),
        "raw_all_actions_nonempty_files": sum(
            1 for r in rows if r["raw"]["view_all"]["actions_len"] > 0),
        "raw_all_not_do_nonempty_files": sum(
            1 for r in rows if r["raw"]["view_all"]["not_do_len"] > 0),
        "raw_all_decision_nonempty_files": sum(
            1 for r in rows if r["raw"]["view_all"]["decision_len"] > 0),
        "raw_all_residual_nonempty_files": sum(
            1 for r in rows if r["raw"]["view_all"]["residual_risks_len"] > 0),
        "v2_shadow_core_present_files": sum(
            1 for r in rows if r["raw"]["v2_shadow"]["core_present"]),
        "v2_shadow_core_ok_files": sum(
            1 for r in rows if r["raw"]["v2_shadow"]["core_ok"] is True),
        "contract_ok_files": sum(
            1 for r in rows if (r.get("contract") or {}).get("ok") is True),
    }


def cmd_hist(args) -> None:
    packed_files = sorted(
        (ROOT / "outputs").glob("*.packed.json"),
        key=lambda p: p.stat().st_mtime)
    if args.cutoff is not None:
        packed_files = [p for p in packed_files
                        if p.stat().st_mtime <= float(args.cutoff)]
    picked = packed_files[-int(args.n):]
    rows = []
    for p in picked:
        with p.open("r", encoding="utf-8") as f:
            packed = json.load(f)
        rows.append(_row(p, packed))
    out = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_by": "core-audit · task-2",
        "engine": {"audit": "dgtf_v2/core_duty.py:audit_packed",
                   "contract": "dgtf_v2/bridge.py:V2MemoryBridge.contract_report"},
        "selection": {
            "rule": "outputs/*.packed.json 按 mtime 升序取最后 %d 份" % args.n,
            "cutoff_epoch": args.cutoff,
            "count": len(rows),
            "oldest": rows[0]["file"] if rows else None,
            "oldest_mtime": rows[0]["mtime"] if rows else None,
            "newest": rows[-1]["file"] if rows else None,
            "newest_mtime": rows[-1]["mtime"] if rows else None,
        },
        "summary": _summarize(rows),
        "rows": rows,
    }
    outp = Path(args.out)
    if not outp.is_absolute():
        outp = ROOT / outp
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({"out": str(outp), "summary": out["summary"]},
                     ensure_ascii=False, indent=2))


def cmd_one(args) -> None:
    p = Path(args.packed)
    if not p.is_absolute():
        p = ROOT / p
    with p.open("r", encoding="utf-8") as f:
        packed = json.load(f)
    row = _row(p, packed)
    out = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_by": "core-audit · task-2",
        "engine": {"audit": "dgtf_v2/core_duty.py:audit_packed",
                   "contract": "dgtf_v2/bridge.py:V2MemoryBridge.contract_report"},
        "row": row,
    }
    outp = Path(args.out)
    if not outp.is_absolute():
        outp = ROOT / outp
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    brief = {
        "file": row["file"], "mtime": row["mtime"],
        "view1_has__actions": row["raw"]["view1"]["has__actions"],
        "view1__actions_len": row["raw"]["view1"]["_actions_len"],
        "view1_dp_actions_len": row["raw"]["view1"]["dp_actions_len"],
        "all_actions_len": row["raw"]["view_all"]["actions_len"],
        "all_not_do_len": row["raw"]["view_all"]["not_do_len"],
        "all_decision_len": row["raw"]["view_all"]["decision_len"],
        "all_residual_len": row["raw"]["view_all"]["residual_risks_len"],
        "v2_shadow_core": row["raw"]["v2_shadow"],
        "audit_ok": row["audit"].get("ok"),
        "audit_gaps": row["audit"].get("gaps"),
        "audit_overreach": row["audit"].get("overreach"),
        "audit_repairs": row["audit"].get("repairs"),
        "contract": row["contract"],
        "out": str(outp),
    }
    print(json.dumps(brief, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hist")
    h.add_argument("--out", required=True)
    h.add_argument("--n", type=int, default=20)
    h.add_argument("--cutoff", type=float, default=None,
                   help="只取 mtime <= cutoff(epoch) 的 packed（用于排除新跑）")
    o = sub.add_parser("one")
    o.add_argument("--packed", required=True)
    o.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.cmd == "hist":
        cmd_hist(args)
    else:
        cmd_one(args)


if __name__ == "__main__":
    main()
