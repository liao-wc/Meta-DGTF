# -*- coding: utf-8 -*-
"""每轮巡回复核 audit 提案：更新证据；指标归零则自动关闭。"""
from __future__ import annotations
import json, time, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "docs" / "outputs_audit_latest.json"
PDIR = ROOT / "dgtf_memory" / "dsh_proposals"
REPORT = ROOT / "docs" / "proposals_reassess_latest.json"


def _load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(p: Path, rec: dict) -> None:
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def _cat(title: str) -> str:
    t = str(title or "")
    if "needs_evidence" in t or "产物库质量" in t:
        return "quality"
    if "配对" in t:
        return "pairing"
    if "重复题" in t:
        return "duplicate"
    if "异常 run" in t or "异常run" in t:
        return "run"
    return ""


def _metric(d: dict, cat: str):
    c = d.get("counts") or {}
    if cat == "quality":
        return (int(c.get("needs_evidence") or 0) + int(c.get("unverified") or 0)
                + int(c.get("missing_quality") or 0))
    if cat == "pairing":
        return int(d.get("missing_md_n") or 0) + int(d.get("missing_pack_n") or 0)
    if cat == "duplicate":
        return int(d.get("duplicate_questions") or 0)
    if cat == "run":
        r = d.get("run_status") or {}
        return int(r.get("error") or 0) + int(r.get("interrupted") or 0)
    return None


def _live_title(d: dict, cat: str, cur: int) -> str:
    c = d.get("counts") or {}
    if cat == "quality":
        return ("产物库质量问题需人工确认：needs_evidence=%s，unverified=%s，answer_ready_false=%s，missing_quality=%s"
                % (c.get("needs_evidence"), c.get("unverified"),
                   c.get("answer_ready_false"), c.get("missing_quality")))
    if cat == "pairing":
        return ("产物配对缺口需人工确认：md 无 packed=%s，packed 无 md=%s"
                % (d.get("missing_pack_n"), d.get("missing_md_n")))
    if cat == "duplicate":
        return "重复题目需人工确认：%s 组" % d.get("duplicate_questions")
    if cat == "run":
        r = d.get("run_status") or {}
        return "异常 run 需人工确认：error=%s，interrupted=%s" % (r.get("error"), r.get("interrupted"))
    return ""


def main() -> int:
    d = _load(AUDIT, {})
    if not d:
        print("no audit")
        return 1
    reviewed = updated = closed = still = skipped = 0
    details = []
    for p in sorted(PDIR.glob("prop-audit-*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(rec.get("status")) != "pending":
            skipped += 1
            continue
        cat = _cat((rec.get("task") or {}).get("title"))
        cur = _metric(d, cat)
        if cur is None:
            skipped += 1
            continue
        reviewed += 1
        prev = None
        for h in reversed(rec.get("reassessments") or []):
            if isinstance(h, dict) and h.get("metric") == cat:
                prev = h.get("current")
                break
        verdict = "resolved" if cur == 0 else ("improved" if prev is not None and cur < prev else "unchanged")
        hist = list(rec.get("reassessments") or [])
        hist.append({"ts": time.time(), "metric": cat, "previous": prev,
                     "current": cur, "verdict": verdict})
        rec["reassessments"] = hist[-12:]
        rec["reviewed_at"] = time.time()
        _lt = _live_title(d, cat, cur)
        if _lt:
            rec.setdefault("task", {})["title"] = _lt
            rec["title"] = _lt
        details.append({"id": rec.get("id"), "category": cat,
                        "previous": prev, "current": cur, "verdict": verdict})
        if cur == 0:
            rec["status"] = "superseded"
            rec["resolution_reason"] = "复核指标归零：问题已由后续运行/修复消解"
            rec["resolved_at"] = time.time()
            closed += 1
        else:
            updated += 1
        _save(p, rec)
    out = {"ok": True, "ts": time.time(), "reviewed": reviewed,
           "updated": updated, "closed": closed, "still_pending": updated,
           "skipped": skipped, "details": details}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("JSON_OUT", REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
