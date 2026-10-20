# -*- coding: utf-8 -*-
"""历史回声：从既往 packed 产物中找回可回到的问题/事实，带来源。"""
from __future__ import annotations
import json
import re
from pathlib import Path

_TOK = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{2,}|[\u4e00-\u9fff]{2,}")


def _tokens(s):
    return {t.lower() for t in _TOK.findall(str(s or ""))}


def recall_prior(question: str, outputs_dir="outputs", limit: int = 3,
                 max_files: int = 12) -> list:
    q = _tokens(question)
    if not q:
        return []
    d = Path(outputs_dir)
    if not d.is_dir():
        return []
    files = sorted(d.glob("*.packed.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:int(max_files)]
    out = []
    for p in files:
        try:
            if p.stat().st_size > 12 * 1024 * 1024:
                continue
            d0 = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(d0, dict):
                continue
            pq = str(d0.get("question") or "")
            pt = _tokens(pq)
            if not pt:
                continue
            inter = q & pt
            if not inter:
                continue
            dt = (d0.get("decision_trace") or {})
            fc = dt.get("fact_card") or {}
            ans = fc.get("answer") or dt.get("answer") or ""
            score = len(inter) / float(len(q | pt) or 1)
            if pq.strip() == str(question or "").strip():
                score += 1.0
            if fc.get("status") == "answered":
                score += 0.5
            out.append({
                "source": "prior_run",
                "run_id": str(d0.get("id") or p.stem),
                "file": p.name,
                "question": pq,
                "answer": str(ans)[:300],
                "fact_status": fc.get("status") or "",
                "score": round(score, 4),
                "tokens": sorted(inter)[:6],
            })
        except Exception:
            continue
    out.sort(key=lambda x: -x["score"])
    return out[:int(limit)]


def prompt_hint(hits: list) -> str:
    if not hits:
        return ""
    bits = []
    for h in hits[:3]:
        bits.append("%s（run=%s）" % (h.get("answer") or h.get("fact_status")
                                      or "历史产物", h.get("run_id")))
    return "【历史回声】" + "；".join(bits) + "。可回到，但不得直接照抄，需重新核实。"


__all__ = ["recall_prior", "prompt_hint"]
