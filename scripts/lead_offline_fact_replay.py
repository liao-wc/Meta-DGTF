# -*- coding: utf-8 -*-
"""离线事实卡重放（零 API）：用已存 pack 的检索池重算 FactCard，量化机制改进。

用途（Round 14）：
  · 对每个 fact 跑次的 pools.web_results 重建证据（与引擎 finalize 同口径：
    from_search_hits → dedup → budget），用**当前代码**重算事实卡；
  · 对比存储卡（当轮产物）与新卡：status/gaps/official/answer/display；
  · 统计数值题答案是否含数字（验证 claim 级抽取、展示分离等机制的真实覆盖率）。
输出 docs/fact_replay_20261025.json。
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))

from dgtf_v2.evidence import (EvidenceBudget, EvidenceReport,  # noqa: E402
                             apply_budget, dedup_evidence, from_search_hits)
from dgtf_v2.fact_flow import build_fact_card  # noqa: E402

OUT = ROOT / "docs" / "fact_replay_20261025.json"
NUM_Q = ("多少", "几", "多长", "多高", "多重", "多远", "多深", "多宽",
         "多大", "多快", "千米", "公里", "%", "海拔", "速度", "面积", "重量")
_VALUE_UNIT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:多|余|约|近)?\s*(?:千米|公里|米|厘米|毫米|%|℃|吨|公斤|kg|年|小时|分钟|秒|万|元)")


def _has_value_unit(s: str) -> bool:
    return bool(_VALUE_UNIT_RE.search(str(s or "")))


def _ld(v):
    try:
        from datetime import datetime, timedelta, timezone
        dt = datetime.fromisoformat(str(v))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone(timedelta(hours=8)))
        return dt.strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return str(v or "")


def replay(question: str, wr: list[dict]):
    hits = []
    for x in wr:
        hits.append({
            "title": str(x.get("query") or ""),
            "url": str(x.get("url") or ""),
            "snippet": (("[" + _ld(x.get("date")) + "] ")
                        if x.get("date") else "") + str(x.get("claim") or ""),
        })
    evs = from_search_hits(hits)
    evs, d1 = dedup_evidence(evs)
    evs, d2 = apply_budget(evs, EvidenceBudget())
    rep = EvidenceReport(question=str(question or ""),
                         queries=[str(x.get("query") or "") for x in wr],
                         searches=len(wr), items=list(evs),
                         dropped=list(d1) + list(d2),
                         official_count=sum(1 for e in evs if e.official),
                         domains=sorted({e.domain for e in evs if e.domain}))
    return build_fact_card(str(question or ""), rep)


def main() -> int:
    rows = []
    for f in sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json")),
                    key=os.path.getmtime):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8",
                                             errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        dt = d.get("decision_trace") or {}
        if dt.get("question_type") != "fact":
            continue
        q = str(d.get("question") or "")
        wr = []
        for p in (d.get("pools") or {}).values():
            for w in (p.get("web_results") or []):
                if isinstance(w, dict):
                    wr.append(w)
        if not wr:
            continue
        stored = dt.get("fact_card") or {}
        new = replay(q, wr)
        nd = new.to_dict()
        numeric_q = any(k in q for k in NUM_Q)
        rows.append({
            "file": os.path.basename(f),
            "question": q[:40],
            "sparse": len(wr) < 3,
            "stored_status": stored.get("status"),
            "stored_gaps": list(stored.get("gaps") or []),
            "stored_official": list(stored.get("official_evidence_ids") or []),
            "stored_answer": str(stored.get("answer") or "")[:90],
            "new_status": new.status,
            "new_gaps": list(new.gaps),
            "new_official": list(new.official_evidence_ids or []),
            "new_answer": str(new.answer)[:90],
            "new_display": str(nd.get("answer_display") or "")[:90],
            "numeric_q": numeric_q,
            "stored_answer_numeric": _has_value_unit(
                str(stored.get("answer") or "")),
            "new_answer_numeric": _has_value_unit(str(new.answer)),
            "gaps_cleared": bool(stored.get("gaps")) and not new.gaps,
        })
    if not rows:
        print("无 fact pack 可重放")
        return 1
    n = len(rows)
    numeric = [r for r in rows if r["numeric_q"]]
    today = [r for r in rows if str(r["file"]).startswith("20261025")]
    summary = {
        "n_today": len(today),
        "today_answered": sum(1 for r in today if r["new_status"] == "answered"),
        "today_gaps_cleared": sum(1 for r in today if r["gaps_cleared"]),
        "today_numeric_before": sum(1 for r in today if r["numeric_q"] and r["stored_answer_numeric"]),
        "today_numeric_after": sum(1 for r in today if r["numeric_q"] and r["new_answer_numeric"]),
        "n_fact_replayed": n,
        "n_numeric": len(numeric),
        "answered_now": sum(1 for r in rows if r["new_status"] == "answered"),
        "gaps_cleared": sum(1 for r in rows if r["gaps_cleared"]),
        "numeric_answer_before": sum(1 for r in numeric
                                     if r["stored_answer_numeric"]),
        "numeric_answer_after": sum(1 for r in numeric
                                    if r["new_answer_numeric"]),
        "official_now": sum(1 for r in rows if r["new_official"]),
        "rows": rows,
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("replayed fact packs:", n, "| numeric:", len(numeric))
    print("answered:", summary["answered_now"],
          "| gaps_cleared:", summary["gaps_cleared"],
          "| official:", summary["official_now"])
    print("today packs:", summary["n_today"], "answered:", summary["today_answered"],
          "| gaps_cleared:", summary["today_gaps_cleared"],
          "| numeric before/after: %d/%d" % (summary["today_numeric_before"], summary["today_numeric_after"]))
    print("numeric answer: before %d / after %d"
          % (summary["numeric_answer_before"],
             summary["numeric_answer_after"]))
    for r in rows[:40]:
        print(" · %-40s stored=%s/%s -> new=%s/%s answer=%s"
              % (r["file"][:40], r["stored_status"], r["stored_gaps"],
                 r["new_status"], r["new_gaps"], r["new_answer"][:44]))
    print("→", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
