# -*- coding: utf-8 -*-
"""层间依赖与过程账本：每层输入来自哪里、产物是什么、是否达标。"""
from __future__ import annotations
from collections import Counter

LAYERS = ("0", "1", "both", "all")
DEPS = {"0": ["external_facets"], "1": ["0", "external_facets"],
        "both": ["0", "1"], "all": ["0", "1", "both"]}


def _v(views, e):
    return (views or {}).get(e) or {}


def _evidence(pools):
    out = []
    for p in (pools or {}).values():
        _res = (p.get("web_results") if isinstance(p, dict)
                else getattr(p, "web_results", None)) or []
        for w in _res:
            if isinstance(w, dict):
                out.append(w)
    return out


def build_ledger(packed: dict) -> dict:
    views = packed.get("views") or {}
    pools = packed.get("pools") or {}
    evs = _evidence(pools)
    ev_ids = [str(x.get("id") or "") for x in evs if x.get("id")]
    facet_n = Counter(str(x.get("facet") or "") for x in evs
                      if x.get("facet"))
    official = sum(1 for x in evs if x.get("used_as") == "evidence"
                   or x.get("official"))
    refs = [x for x in evs if str(x.get("tier") or "") == "reference"
            or str(x.get("used_as") or "") == "reference"]
    layers = {}
    for e in LAYERS:
        v = _v(views, e)
        fc = (packed.get("fact_contract") or {}).get("layers", {}).get(e) or {}
        dp = v.get("decidable_product") or {}
        cites = 0
        for sq in (v.get("sub_questions") or []):
            cites += len(sq.get("citations") or sq.get("evidence") or [])
        if e == "0":
            product = str(v.get("manifest") or "")
            ok = bool(product) and bool(fc.get("ok", True))
            if facet_n and not any(facet_n.get(k) for k in
                                   ("history", "changes", "features", "naming")):
                ok = False
        elif e == "1":
            product = str(dp.get("answer") or v.get("manifest") or "")
            _aud = v.get("decidability_audit") or {}
            _aud_ok = ((not _aud) or (
                _aud.get("status") in ("verified", "mixed")
                and int(_aud.get("bad") or 0) == 0))
            ok = bool(product) and bool(fc.get("ok", True)) and (
                cites > 0 or not evs or bool(ev_ids)) and _aud_ok
        elif e == "both":
            product = str(v.get("collision") or v.get("manifest") or "")
            ok = bool(product) and bool(fc.get("ok", True))
        else:
            product = str(v.get("decision") or v.get("summary")
                          or v.get("manifest") or "")
            mc = v.get("meta_closure") or {}
            ok = bool(product) and bool(fc.get("ok", True)) and bool(
                mc.get("clean", True))
        layers[e] = {
            "rounds": int(v.get("rounds_run") or 0),
            "product_chars": len(product),
            "product": product[:300],
            "standard_ok": bool(ok),
            "fact_ok": bool(fc.get("ok", True)),
            "citations": cites,
            "decidability": (v.get("decidability_audit") or {}).get("status"),
            "decidability_bad": int((v.get("decidability_audit") or {}).get(
                "bad") or 0),
            "external_refs": len(ev_ids) if e in ("0", "1") else 0,
            "external_reference": len([x for x in evs if str(
                x.get("tier") or "") == "reference"]) if e in ("0", "1") else 0,
            "evidence_ids": ev_ids[:8] if e in ("0", "1") else [],
            "deps": list(DEPS[e]),
            "inputs": ["external_facets"] if e == "0" else list(DEPS[e]),
        }
    soul = {
        "identity": "元DGTF",
        "spiral": {e: layers[e]["rounds"] for e in LAYERS},
        "dependencies": {e: list(DEPS[e]) for e in LAYERS},
        "input_shape": {"question": str(packed.get("question") or ""),
                        "route": packed.get("route"),
                        "evidence_n": len(evs)},
        "output_shape": {"layers": list(LAYERS),
                         "answer_ready": bool(
                             (packed.get("decision_trace") or {}).get(
                                 "answer_ready"))},
        "standard_all": all(x["standard_ok"] for x in layers.values()),
        "facets": dict(facet_n),
        "external_official": official,
        "external_reference": len(refs),
        "external_confidence_avg": round(
            sum(float(x.get("confidence") or 0) for x in evs)
            / max(1, len(evs)), 4),
    }
    return {"layers": layers, "soul": soul,
            "standard_all": soul["standard_all"]}


__all__ = ["build_ledger", "LAYERS", "DEPS"]
