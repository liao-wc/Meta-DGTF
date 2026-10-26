# -*- coding: utf-8 -*-
"""外汇题时间锚定回放判据（Round 129，零成本，离线 replay）。

复现：2024年末外汇储备题首跑 unverified（conflict 32024 vs 32659 + uncovered），
A86 锚定修复后离线重放应 answered / display=32024亿美元 / gaps=[]。
"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "dgtf_engine") not in sys.path:
    sys.path.insert(0, str(ROOT / "dgtf_engine"))
sys.path.insert(0, str(ROOT))

from dgtf_v2.evidence import (EvidenceBudget, EvidenceReport, apply_budget,
                              dedup_evidence, from_search_hits)
from dgtf_v2.fact_flow import build_fact_card


def main() -> int:
    fs = sorted(glob.glob(str(ROOT / "outputs" / "*外汇储备余额*.packed.json")),
                key=os.path.getmtime, reverse=True)
    if not fs:
        print("SKIP: 找不到外汇题 packed（历史包缺失）")
        return 0
    d = json.loads(Path(fs[0]).read_text(encoding="utf-8"))
    question = str(d.get("question") or "")
    web = []
    for _pk, p in (d.get("pools") or {}).items():
        for w in (p.get("web_results") or []):
            if isinstance(w, dict):
                web.append(w)
    hits = [{"title": str(x.get("query") or ""),
             "url": str(x.get("url") or ""),
             "snippet": str(x.get("claim") or "")} for x in web]
    evs = from_search_hits(hits)
    evs, _dd = dedup_evidence(evs)
    evs, _bd = apply_budget(evs, EvidenceBudget())
    rep = EvidenceReport(question=question, queries=["q"], searches=len(web),
                         items=list(evs), dropped=list(_dd) + list(_bd),
                         official_count=sum(1 for e in evs if e.official),
                         domains=sorted({e.domain for e in evs if e.domain}))
    card = build_fact_card(question, rep)
    cd = card.to_dict()
    display = str(cd.get("answer_display") or "")
    ok = (card.status == "answered" and "32024" in display
          and not any(str(g) == "conflict_unresolved"
                      or str(g).startswith("uncovered:") for g in card.gaps))
    print("FX replay: %s | display=%s | gaps=%s | evidence=%d"
          % (card.status, display, card.gaps, len(evs)))
    print("FX ANCHOR %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
