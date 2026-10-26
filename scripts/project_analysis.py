# -*- coding: utf-8 -*-
"""产物→项目问题分析（Round 131，零成本，只读）。

从 outputs/*.packed.json + docs/ab_results.jsonl + 审计快照中提取项目级信号：
质量趋势、题型分布、过程可靠性、成本效率、产物完整度、provenance 缺失等。
输出：docs/project_analysis_20261027.json + 控制台摘要。
"""
from __future__ import annotations

import glob
import json
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "project_analysis_20261027.json"


def _pct(a, b):
    return round(100.0 * a / b, 1) if b else 0.0


def main() -> int:
    packs = sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json")),
                   key=os.path.getmtime)
    doc = {"packs": len(packs)}
    by_date = defaultdict(list)
    qtype = Counter()
    aq_by_type = defaultdict(Counter)
    disp = Counter()
    flags = Counter()
    gaps = Counter()
    stops = Counter()
    covered = []
    tri_alpha = []
    tok, calls = [], []
    missing_dispatch = 0
    md_missing = 0
    md_lens = []
    fact_ok = Counter()
    provenance_n = 0
    qhash_n = 0
    verification_n = 0
    truncated_ready = 0
    verified_no_display = 0
    for f in packs:
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        stem = os.path.basename(f)
        date = stem[:8]
        q = d.get("quality") or {}
        asum = q.get("answer_summary") or d.get("answer_summary") or {}
        qt = str(asum.get("question_type") or "unknown")
        qtype[qt] += 1
        aq_by_type[qt][str(q.get("answer_quality"))] += 1
        if float(q.get("coverage") or 0) >= 0:
            covered.append(float(q.get("coverage") or 0))
        ta = q.get("tri_alpha")
        if isinstance(ta, (int, float)):
            tri_alpha.append(float(ta))
        if d.get("llm_tokens") is not None:
            tok.append(int(d.get("llm_tokens") or 0))
        if d.get("llm_calls") is not None:
            calls.append(int(d.get("llm_calls") or 0))
        card = (d.get("decision_trace") or {}).get("fact_card") or {}
        disp["display" if card.get("answer_display") else "no_display"] += 1
        fact_ok["ok" if card.get("ok") else "not_ok"] += 1
        if d.get("provenance"):
            provenance_n += 1
        if d.get("question_hash"):
            qhash_n += 1
        if isinstance(q.get("verification"), dict):
            verification_n += 1
        if ("体力耗尽" in str(asum.get("stop_reason") or "")
                and q.get("answer_ready") is True):
            truncated_ready += 1
        if q.get("answer_quality") == "verified" and not card.get("answer_display"):
            verified_no_display += 1
        for fl in (q.get("flags") or []):
            flags[str(fl).split("(")[0]] += 1
        for g in (card.get("gaps") or q.get("gaps") or []):
            gaps[str(g).split(":")[0]] += 1
        stops[str(asum.get("stop_reason") or "")] += 1
        dp = d.get("dispatch") or {}
        if dp.get("missing") or dp.get("failed"):
            missing_dispatch += 1
        md = Path(f[:-len(".packed.json")] + ".md")
        if md.exists():
            md_lens.append(md.stat().st_size)
        else:
            md_missing += 1
        v = {
            "verified": str(q.get("answer_quality")) == "verified",
            "ready": bool(q.get("answer_ready")),
            "display": bool(card.get("answer_display")),
            "coverage": float(q.get("coverage") or 0),
            "tri_alpha": ta if isinstance(ta, (int, float)) else None,
            "tokens": int(d.get("llm_tokens") or 0),
        }
        by_date[date].append(v)

    def _agg(vals):
        n = len(vals)
        return {
            "n": n,
            "verified_pct": _pct(sum(1 for x in vals if x["verified"]), n),
            "ready_pct": _pct(sum(1 for x in vals if x["ready"]), n),
            "display_pct": _pct(sum(1 for x in vals if x["display"]), n),
            "coverage_mean": round(statistics.mean([x["coverage"] for x in vals]), 4) if vals else 0,
            "tri_alpha_mean": round(statistics.mean([x["tri_alpha"] for x in vals if x["tri_alpha"] is not None]), 3) if any(x["tri_alpha"] is not None for x in vals) else None,
            "tokens_mean": int(statistics.mean([x["tokens"] for x in vals])) if vals else 0,
        }

    doc.update({
        "question_types": dict(qtype),
        "aq_by_type": {k: dict(v) for k, v in aq_by_type.items()},
        "display": dict(disp),
        "fact_card_ok": dict(fact_ok),
        "flags_top": dict(flags.most_common(12)),
        "gaps_top": dict(gaps.most_common(10)),
        "stop_reasons": dict(stops.most_common(10)),
        "coverage": {
            "mean": round(statistics.mean(covered), 4) if covered else None,
            "lt_0_8": sum(1 for x in covered if x < 0.8),
            "lt_0_5": sum(1 for x in covered if x < 0.5),
        },
        "tri_alpha": {
            "n": len(tri_alpha),
            "mean": round(statistics.mean(tri_alpha), 4) if tri_alpha else None,
            "unreliable_lt_0667": sum(1 for x in tri_alpha if x < 0.667),
        },
        "tokens": {
            "n": len(tok),
            "mean": int(statistics.mean(tok)) if tok else 0,
            "p50": int(statistics.median(tok)) if tok else 0,
            "max": max(tok) if tok else 0,
            "calls_mean": round(statistics.mean(calls), 1) if calls else 0,
        },
        "provenance": {
            "packs_with_provenance": provenance_n,
            "packs_with_question_hash": qhash_n,
            "packs_with_verification": verification_n,
            "truncated_but_ready": truncated_ready,
            "verified_without_display": verified_no_display,
        },
        "artifact_integrity": {
            "missing_md": md_missing,
            "md_mean_bytes": int(statistics.mean(md_lens)) if md_lens else 0,
            "dispatch_incomplete": missing_dispatch,
        },
        "trend_by_date": {k: _agg(v) for k, v in sorted(by_date.items())},
    })

    # ab_results 趋势
    rows = []
    for ln in (ROOT / "docs" / "ab_results.jsonl").read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:  # noqa: BLE001
            pass
    by_tag = defaultdict(list)
    for r in rows:
        tag = str(r.get("tag") or "")
        prefix = tag.split("-")[0]
        by_tag[prefix].append(r)
    trend = {}
    for k, rs in sorted(by_tag.items()):
        qs = [float(r.get("quality") or 0) for r in rs]
        trend[k] = {
            "n": len(rs),
            "quality_mean": round(statistics.mean(qs), 4) if qs else 0,
            "verified_pct": _pct(sum(1 for r in rs
                                    if str(r.get("answer_quality")) == "verified"), len(rs)),
            "tokens_mean": int(statistics.mean([int(r.get("tokens") or 0) for r in rs])) if rs else 0,
        }
    doc["ab_trend_by_prefix"] = trend
    doc["ab_rows"] = len(rows)
    doc["ab_missing_cost"] = sum(1 for r in rows if "cost_window_cny" not in r)

    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("packs", doc["packs"])
    print("question_types", doc["question_types"])
    print("display", doc["display"], "| fact_ok", doc["fact_card_ok"])
    print("coverage", doc["coverage"], "| tri_alpha", doc["tri_alpha"])
    print("tokens", doc["tokens"], "| integrity", doc["artifact_integrity"])
    print("flags_top", doc["flags_top"])
    print("gaps_top", doc["gaps_top"])
    for k, v in doc["trend_by_date"].items():
        print("trend", k, v)
    print("->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
