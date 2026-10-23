# -*- coding: utf-8 -*-
"""逐 claim 证据缺口循环（确定性、注入 search，不直接联网）。"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .evidence import (EvidenceBudget, EvidenceReport, from_search_hits,
                       dedup_evidence, apply_budget, is_official_source)

_TOKEN_RE = re.compile(r"\d{4}|20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}")


@dataclass
class Claim:
    claim_id: str
    layer: str
    text: str
    citations: list = field(default_factory=list)
    status: str = "open"       # open|resolved|unresolved|skipped
    reason: str = ""

    def to_dict(self) -> dict:
        return {"claim_id": self.claim_id, "layer": self.layer,
                "text": str(self.text)[:300], "citations": list(self.citations),
                "status": self.status, "reason": self.reason}


def _text(v: Any) -> str:
    return str(v or "").strip()


def extract_claims(views: dict, pools: dict | None = None) -> list:
    """从四层产物抽 claim；只挑「需要外部证据」的，不把纯结构当 claim。"""
    out: list[Claim] = []
    seen: set[str] = set()
    n = 0

    def add(layer: str, text: str, cites=None, sid: str = "") -> None:
        nonlocal n
        t = _text(text)
        if not t or len(t) < 2:
            return
        key = t[:120]
        if key in seen:
            return
        seen.add(key)
        n += 1
        out.append(Claim(claim_id=sid or ("C%d" % n), layer=layer,
                         text=t, citations=list(cites or [])))

    v1 = views.get("1") or {}
    for sq in (v1.get("sub_questions") or []):
        add("1", sq.get("question") or sq.get("answer") or "",
            cites=sq.get("citations") or sq.get("evidence") or [],
            sid=str(sq.get("id") or ""))
    dp = v1.get("decidable_product") or {}
    if dp.get("answer"):
        add("1", dp.get("answer"), cites=dp.get("evidence") or [],
            sid="DP")
    va = views.get("all") or {}
    for x in (va.get("actions") or []):
        if isinstance(x, dict):
            add("all", x.get("desc") or x.get("action") or "")
    for x in (va.get("residual_risks") or []):
        add("all", x if isinstance(x, str) else str(x))
    vb = views.get("both") or {}
    for x in (vb.get("threads") or []):
        add("both", x.get("desc") if isinstance(x, dict) else x)
    v0 = views.get("0") or {}
    for x in (v0.get("candidates") or [])[:20]:
        add("0", x.get("desc") if isinstance(x, dict) else x)
    return out


def _needs_evidence(c: Claim) -> bool:
    if c.citations:
        return False
    t = c.text
    if _TOKEN_RE.search(t):
        return True
    return any(k in t for k in ("官方", "发布", "时间", "日期", "版本",
                                "是否", "存在", "多少", "什么时候"))


def run_claim_gap_loop(claims: list, search: Callable | None,
                       *, max_per_layer: int = 3,
                       max_queries: int = 2,
                       budget: EvidenceBudget | None = None) -> dict:
    """逐 claim 检测 -> 补检索 -> 绑定 -> resolve/unresolved 留痕。"""
    b = budget or EvidenceBudget(max_items=4, max_per_domain=2,
                                 max_total_chars=2000)
    trace, used = [], {}
    if not callable(search):
        for c in claims:
            if _needs_evidence(c):
                c.status, c.reason = "skipped", "search_unavailable"
                trace.append(c.to_dict())
        return {"claims": [c.to_dict() for c in claims],
                "trace": trace, "searches": 0,
                "resolved": 0, "unresolved": 0, "skipped": len(trace)}
    for c in claims:
        if not _needs_evidence(c):
            c.status = "skipped"
            c.reason = "has_citations_or_not_external"
            trace.append(c.to_dict())
            continue
        cnt = int(used.get(c.layer, 0))
        if cnt >= int(max_per_layer):
            c.status, c.reason = "unresolved", "layer_budget"
            trace.append(c.to_dict())
            continue
        t = c.text[:120]
        token = _TOKEN_RE.search(t)
        q = t
        if token and "deepseek" in t.lower():
            q = "%s site:api-docs.deepseek.com" % token.group(0)
        hits = search(q)
        hits = list(hits or [])[:max(1, int(max_queries))]
        evs = from_search_hits(hits)
        evs, _ = dedup_evidence(evs)
        evs, _ = apply_budget(evs, b)
        off = [e for e in evs if e.official]
        used[c.layer] = cnt + 1
        if off:
            c.citations = [e.evidence_id for e in off[:2]]
            c.status, c.reason = "resolved", "official_evidence"
        elif evs:
            c.citations = [e.evidence_id for e in evs[:2]]
            c.status, c.reason = "unresolved", "third_party_only"
        else:
            c.status, c.reason = "unresolved", "no_evidence"
        trace.append(c.to_dict())
    return {"claims": [c.to_dict() for c in claims], "trace": trace,
            "searches": sum(used.values()),
            "resolved": sum(1 for c in claims if c.status == "resolved"),
            "unresolved": sum(1 for c in claims if c.status == "unresolved"),
            "skipped": sum(1 for c in claims if c.status == "skipped")}
