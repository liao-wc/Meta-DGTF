# -*- coding: utf-8 -*-
"""LLM 辅助 EML：只读取运行摘要，输出受白名单约束的调度候选。"""
from __future__ import annotations
import json

_ALLOWED = {"rounds_delta", "carve_first", "thinking_hint", "web_hint",
            "config_hint", "action_hint", "duty_floor"}
_FORBID = ("answer", "verdict", "score", "grade", "content", "raw")


def build_digest(packed: dict) -> dict:
    p = packed or {}
    views = p.get("views") or {}
    layers = {}
    for e in ("0", "1", "both", "all"):
        v = views.get(e) or {}
        layers[e] = {"duty": (v.get("duty") or {}).get("S"),
                     "candidates": len(v.get("candidates") or []),
                     "threads": len(v.get("threads") or []),
                     "rounds": v.get("rounds_run")}
    sf = p.get("self_feedback") or {}
    cg = p.get("claim_gaps") or {}
    return {"run_id": p.get("id"), "question_type":
            ((p.get("decision_trace") or {}).get("question_type")),
            "layers": layers,
            "self_signals": sf.get("signals") or {},
            "claim_gaps": {"resolved": cg.get("resolved"),
                           "unresolved": cg.get("unresolved")},
            "quality_flags": (p.get("quality") or {}).get("flags") or [],
            "tokens": p.get("llm_tokens")}


def parse_candidates(raw, max_n: int = 3) -> list:
    try:
        d = json.loads(str(raw or "{}"))
    except Exception:
        return []
    items = d.get("candidates") if isinstance(d, dict) else d
    out = []
    for c in (items or [])[:int(max_n)]:
        if not isinstance(c, dict):
            continue
        a = c.get("action") or {}
        if str(a.get("key") or "") not in _ALLOWED:
            continue
        blob = json.dumps(a, ensure_ascii=False).lower()
        if any(k in blob for k in _FORBID):
            continue
        if not isinstance(c.get("readings"), dict) or not c["readings"].get("before"):
            continue
        c = dict(c)
        c["source"] = "llm"
        out.append(c)
    return out


SYSTEM = ("你是元DGTF的调度复盘器。只输出 JSON："
          '{"candidates":[{"kind":"schedule|probe|guard",'
          '"cond":{"issue":"..."},"action":{"key":"rounds_delta|carve_first|'
          'thinking_hint|web_hint|config_hint|action_hint","..."},'
          '"readings":{"before":{},"after":{}},"why":"..."}]}。'
          "禁止输出答案正文、评分、裁决；最多 3 条；无把握返回空数组。")


def propose(llm, packed: dict, *, max_n: int = 3) -> dict:
    if llm is None:
        return {"enabled": False, "candidates": [], "error": "no_llm"}
    digest = build_digest(packed)
    user = "运行摘要：\n" + json.dumps(digest, ensure_ascii=False)[:4000]
    try:
        raw = llm.call(SYSTEM, user, 0.2, 1200, json_mode=True,
                       stage="playbook_llm_feedback")
    except Exception as e:
        return {"enabled": True, "candidates": [], "error": "%s: %s" % (type(e).__name__, e)}
    cs = parse_candidates(raw, max_n=max_n)
    return {"enabled": True, "candidates": cs, "n": len(cs),
            "digest": digest, "raw_len": len(str(raw or ""))}


__all__ = ["build_digest", "parse_candidates", "propose"]
