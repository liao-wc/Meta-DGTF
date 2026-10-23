#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线重放 packed 的质量门：process_ready / answer_quality / citations。

只读，不调用 API，不修改产物。
"""
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
sys_path = str(ROOT)
import sys
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from dgtf_v2.process_ledger import build_ledger


def _hard_gaps(card):
    out = []
    for g in (card.get("gaps") or []):
        gs = str(g or "")
        if (gs.startswith("uncovered:") or gs in
                ("conflict_unresolved", "insufficient_evidence",
                 "question_token_not_in_evidence", "no_query",
                 "search_error", "no_record")):
            out.append(gs)
    return out


def main():
    files = sorted(OUT.glob("*.packed.json"), key=lambda p: p.stat().st_mtime,
                   reverse=True)
    rows = []
    skipped = []
    for p in files[:128]:
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            skipped.append({"file": p.name, "error": type(exc).__name__})
            continue
        led = build_ledger(d)
        dt = d.get("decision_trace") or {}
        card = dt.get("fact_card") or {}
        process = bool(led.get("standard_all"))
        raw_ready = bool(dt.get("answer_ready"))
        hard = _hard_gaps(card)
        aq = ("verified" if (card.get("status") == "answered" and not hard
                             and card.get("official_evidence_ids"))
              else ("needs_evidence" if hard or card.get("status") == "answered"
                    else "unverified"))
        ready = raw_ready and process
        rows.append({
            "file": p.name, "question": str(d.get("question") or "")[:80],
            "tokens": d.get("llm_tokens"),
            "raw_answer_ready": raw_ready, "process_ready": process,
            "answer_ready": ready, "answer_quality": aq,
            "citations_layer1": (led.get("layers") or {}).get("1", {}).get("citations"),
            "standard_layers": {k: v.get("standard_ok")
                                for k, v in (led.get("layers") or {}).items()},
            "hard_gaps": hard,
            "flags": list((d.get("quality") or {}).get("flags") or []),
        })
    mism = [r for r in rows if r["raw_answer_ready"] and not r["process_ready"]]
    public_mism = [r for r in rows if r["answer_ready"] and not r["process_ready"]]
    verified = [r for r in rows if r["answer_quality"] == "verified"]
    out = {
        "generated_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "total_packed": len(rows), "skipped": skipped,
        "raw_ready": sum(1 for r in rows if r["raw_answer_ready"]),
        "process_ready": sum(1 for r in rows if r["process_ready"]),
        "ready": sum(1 for r in rows if r["answer_ready"]),
        "verified": len(verified),
        "historical_raw_ready_but_process_false": len(mism),
        "ready_but_process_false": len(public_mism),
        "layer1_citations_positive": sum(1 for r in rows
                                         if (r.get("citations_layer1") or 0) > 0),
        "rows": rows[:80],
    }
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "goal_quality_replay.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# 质量门离线重放", "", "- generated: " + out["generated_at"],
             "- packed: %d" % out["total_packed"],
             "- raw_answer_ready: %d" % out["raw_ready"],
             "- process_ready: %d" % out["process_ready"],
             "- both ready: %d" % out["ready"],
             "- verified: %d" % out["verified"],
             "- ready_but_process_false: %d" % out["ready_but_process_false"],
             "- historical_raw_ready_but_process_false: %d" % out["historical_raw_ready_but_process_false"],
             "- public_ready_but_process_false: %d" % out["ready_but_process_false"],
             "- layer1_citations_positive: %d" % out["layer1_citations_positive"],
             "", "| file | raw ready | process | aq | cite1 | hard gaps |",
             "|---|---:|---:|---|---:|---|"]
    for r in rows[:20]:
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            r["file"], r["raw_answer_ready"], r["process_ready"],
            r["answer_quality"], r["citations_layer1"], ",".join(r["hard_gaps"])))
    (ROOT / "reports" / "goal_quality_replay.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("total_packed", "raw_ready",
                                         "process_ready", "ready", "verified",
                                         "ready_but_process_false",
                                         "layer1_citations_positive")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
