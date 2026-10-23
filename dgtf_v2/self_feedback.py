# -*- coding: utf-8 -*-
"""both/all 自反馈 -> EML 候选（确定性，不调 LLM/网络）。"""
from __future__ import annotations
import json


def _v(packed, layer):
    return ((packed.get("views") or {}).get(layer) or {})


def collect_feedback(packed: dict) -> dict:
    b = _v(packed, "both")
    a = _v(packed, "all")
    bt = b.get("threads") or []
    ba = b.get("adjudications") or []
    du = b.get("duel_suspensions") or []
    unstable = [x for x in du if str(x.get("status") or "")                 not in ("stable", "resolved", "closed")]
    mc = a.get("meta_closure") or {}
    flags = list((packed.get("quality") or {}).get("flags") or [])
    layers = {}
    for _e in ("0", "1", "both", "all"):
        _v0 = _v(packed, _e)
        _cites = 0
        for _sq in (_v0.get("sub_questions") or []):
            _cites += len(_sq.get("citations") or _sq.get("evidence") or [])
        _cites += len(_v0.get("provenance") or [])
        layers[_e] = {
            "entered": bool(_v0),
            "candidates": len(_v0.get("candidates") or []),
            "amps": len(_v0.get("amps") or []),
            "threads": len(_v0.get("threads") or []),
            "citations": _cites,
            "duty": ((_v0.get("duty") or {}).get("S")
                     if isinstance(_v0.get("duty"), dict) else None),
            "actions": len(_v0.get("actions") or []),
            "flags": list(_v0.get("quality_flags") or []),
        }
    _content = sum(v["candidates"] + v["amps"] for v in layers.values())
    _context = (sum(v["citations"] for v in layers.values())
                + len((packed.get("pools") or {}).get("1", {}).get("web_results") or []))
    _self_flags = [f for f in flags if any(k in f for k in (
        "rephrase", "self", "duty", "stagnation", "drift", "probe"))]
    channels = {"content": {"score": _content, "weak": _content < 2},
                "context": {"score": _context, "weak": _context < 1},
                "self": {"score": len(_self_flags),
                         "noisy": len(_self_flags) > 0,
                         "flags": _self_flags[:8]}}
    return {
        "both": {
            "threads": len(bt), "adjudications": len(ba),
            "third": bool(b.get("collision") or b.get("manifest")),
            "duel_suspensions": len(du), "unstable_suspensions": len(unstable),
            "structural_saturation": "结构饱和" in str(
                b.get("stop_primary") or b.get("stop_reason") or ""),
        },
        "all": {
            "clean": bool(mc.get("clean")),
            "leftover": int(mc.get("leftover") or 0),
            "residual": len(a.get("residual_risks") or []),
            "provenance": len(a.get("provenance") or []),
            "actions": len(a.get("actions") or []),
            "decision": bool(str(a.get("decision") or "").strip()),
            "closure_gap": "all_closure_gaps" in flags,
            "core_gap": "core_audit_gaps" in flags,
        },
        "flags": flags,
        "layers": layers,
        "channels": channels,
        "research_audit": dict(packed.get("decidability_audit") or {}),
        "facets": dict(((packed.get("process_ledger") or {}).get(
            "soul") or {}).get("facets") or {}),
        "recall_n": int(((packed.get("recall") or {}).get("n") or 0)),
        "process_standard": bool((packed.get("process_ledger") or {}).get(
            "standard_all")),
        "process_ledger": dict(packed.get("process_ledger") or {}),
        "api_usage": dict(packed.get("api_usage") or {}),
        "knowledge": dict((packed.get("knowledge_echo") or {}).get("stats")
                          or {}),
    }


def candidates(packed: dict) -> list:
    s = collect_feedback(packed)
    b, a = s["both"], s["all"]
    rid = str(packed.get("id") or "")
    out = []
    if b["threads"] and (b["unstable_suspensions"] or not b["third"]):
        out.append({"kind": "schedule",
                    "cond": {"issue": "both_unresolved"},
                    "action": {"key": "rounds_delta", "layer": "both",
                               "delta": 1},
                    "readings": {"before": {"both_threads": b["threads"],
                                            "unstable": b["unstable_suspensions"]},
                                 "after": {"both_threads": "期望收敛"}},
                    "why": "both 仍有未裁定张力/未稳定悬置"})
    if b["threads"] >= 3:
        out.append({"kind": "probe",
                    "cond": {"issue": "both_tension_high"},
                    "action": {"key": "thinking_hint",
                               "stages": ["ing", "adjudicate_sub_tristate"],
                               "value": "enabled"},
                    "readings": {"before": {"both_threads": b["threads"]},
                                 "after": {"tension": "期望下降"}},
                    "why": "both 张力多 ⇒ 加深对撞/裁决思考"})
    if (not a["clean"]) or a["leftover"] or a["closure_gap"]:
        out.append({"kind": "schedule",
                    "cond": {"issue": "all_closure_gap"},
                    "action": {"key": "rounds_delta", "layer": "all",
                               "delta": 1},
                    "readings": {"before": {"clean": a["clean"],
                                            "leftover": a["leftover"],
                                            "closure_gap": a["closure_gap"]},
                                 "after": {"clean": "期望 true"}},
                    "why": "all 闭环不干净/有遗留"})
    if a["residual"] or a["core_gap"]:
        out.append({"kind": "probe",
                    "cond": {"issue": "all_residual"},
                    "action": {"key": "carve_first", "layers": ["all"]},
                    "readings": {"before": {"residual": a["residual"],
                                            "core_gap": a["core_gap"]},
                                 "after": {"residual": "期望下降"}},
                    "why": "all 有残余风险/核心缺口"})
    if a["decision"] and not a["actions"]:
        out.append({"kind": "guard",
                    "cond": {"issue": "all_actions_missing"},
                    "action": {"key": "action_hint", "name": "landing_decision",
                               "value": True},
                    "readings": {"before": {"actions": 0,
                                            "decision": True},
                                 "after": {"actions": "期望 >0"}},
                    "why": "all 有决策但无动作 ⇒ 打开落地决策"})
    # 过程账本未全达标：不能只让 memory 强化，要给下一跑结构动作。
    _pl = s.get("process_ledger") or {}
    if _pl and not _pl.get("standard_all"):
        _bad_layers = [e for e, r in (_pl.get("layers") or {}).items()
                       if not (r or {}).get("standard_ok")]
        out.append({"kind": "guard",
                    "cond": {"issue": "process_standard_gap"},
                    "action": {"key": "thinking_hint",
                               "stages": ["self_check", "manifest"],
                               "value": "enabled"},
                    "readings": {"before": {"layers": _bad_layers[:4]},
                                 "after": {"standard_all": "期望 true"}},
                    "why": "过程账本有层未达标 ⇒ 加深自检/清单，先补结构"})
    # 研究审计：未证项必须进 EML，而不是只留在产物里。
    _aud = s.get("research_audit") or {}
    if _aud.get("status") == "empty":
        out.append({"kind": "probe",
                    "cond": {"issue": "research_audit_empty"},
                    "action": {"key": "thinking_hint",
                               "stages": ["decompose_normal",
                                          "assess_decidability"],
                               "value": "enabled"},
                    "readings": {"before": {"status": "empty", "n": 0},
                                 "after": {"status": "期望有可审计产物"}},
                    "why": "研究层无可审计产物 ⇒ 下一跑先做结构化分解/判定"})
    if int(_aud.get("bad") or 0) > 0:
        out.append({"kind": "guard",
                    "cond": {"issue": "research_decidability_unverified"},
                    "action": {"key": "thinking_hint",
                               "stages": ["assess_decidability",
                                          "adjudicate_sub_tristate"],
                               "value": "enabled"},
                    "readings": {"before": {"bad": int(_aud.get("bad") or 0),
                                            "n": int(_aud.get("n") or 0)},
                                 "after": {"bad": "期望下降"}},
                    "why": "研究层有未证判定 ⇒ 加深可判定性与裁决思考"})
    # 0 层侧面为空：下一跑提高 facet 检索数。
    _fc = s.get("facets") or {}
    if not _fc and (packed.get("question") if isinstance(packed, dict) else ""):
        out.append({"kind": "probe",
                    "cond": {"issue": "facet_empty"},
                    "action": {"key": "config_hint",
                               "key_name": "external_input.facet_queries",
                               "value": 4},
                    "readings": {"before": {"facets": 0},
                                 "after": {"facets": "期望 >0"}},
                    "why": "0 层侧面为空 ⇒ 下一跑提高侧面检索数"})
    ch = s.get("channels") or {}
    if (ch.get("content") or {}).get("weak"):
        out.append({"kind": "schedule",
                    "cond": {"issue": "content_channel_weak"},
                    "action": {"key": "rounds_delta", "layer": "0",
                               "delta": 1},
                    "readings": {"before": {"content_score":
                                            (ch.get("content") or {}).get("score")},
                                 "after": {"content": "期望上升"}},
                    "why": "content 通道产物过少 ⇒ 修行层多一圈"})
    if (ch.get("context") or {}).get("weak"):
        out.append({"kind": "probe",
                    "cond": {"issue": "context_channel_weak"},
                    "action": {"key": "carve_first", "layers": ["1", "all"]},
                    "readings": {"before": {"context_score":
                                            (ch.get("context") or {}).get("score")},
                                 "after": {"context": "期望上升"}},
                    "why": "context 通道无引用/证据 ⇒ 研究/元层优先补证据"})
    if (ch.get("context") or {}).get("weak"):
        out.append({"kind": "guard",
                    "cond": {"issue": "context_web_on_demand"},
                    "action": {"key": "web_hint",
                               "stages": ["research_evidence",
                                          "research_precedent",
                                          "duel_arbitration"],
                               "value": True},
                    "readings": {"before": {"context_score":
                                            (ch.get("context") or {}).get("score")},
                                 "after": {"context": "期望上升"}},
                    "why": "context 通道无证据 ⇒ 按需放开取证/先例/仲裁联网"})
    if (ch.get("self") or {}).get("noisy"):
        out.append({"kind": "guard",
                    "cond": {"issue": "self_channel_noisy"},
                    "action": {"key": "thinking_hint",
                               "stages": ["self_check", "manifest"],
                               "value": "enabled"},
                    "readings": {"before": {"self_flags":
                                            (ch.get("self") or {}).get("flags")},
                                 "after": {"flags": "期望下降"}},
                    "why": "self 通道出现复述/职责/停滞线索 ⇒ 加深自检与清单"})
    # 0/1 层显式自反馈：不靠通道聚合，按层读数给动作。
    _l0 = (s.get("layers") or {}).get("0") or {}
    _l1 = (s.get("layers") or {}).get("1") or {}
    if (_l0.get("candidates", 0) + _l0.get("amps", 0)) < 2:
        out.append({"kind": "schedule",
                    "cond": {"issue": "layer0_yield_low"},
                    "action": {"key": "rounds_delta", "layer": "0",
                               "delta": 1},
                    "readings": {"before": {"candidates": _l0.get("candidates"),
                                            "amps": _l0.get("amps")},
                                 "after": {"candidates": "期望上升"}},
                    "why": "0 层候选/& 过少 ⇒ 修行层多一圈显形"})
    if _l0.get("duty") is not None and float(_l0.get("duty")) < 0.35:
        out.append({"kind": "probe",
                    "cond": {"issue": "layer0_duty_short"},
                    "action": {"key": "carve_first", "layers": ["0"]},
                    "readings": {"before": {"duty_S": _l0.get("duty")},
                                 "after": {"duty_S": "期望上升"}},
                    "why": "0 层职责不足 ⇒ 优先雕修行层"})
    if _l0.get("flags"):
        out.append({"kind": "guard",
                    "cond": {"issue": "layer0_self_noise"},
                    "action": {"key": "thinking_hint",
                               "stages": ["self_check", "phase_probe"],
                               "value": "enabled"},
                    "readings": {"before": {"flags": _l0.get("flags")[:6]},
                                 "after": {"flags": "期望下降"}},
                    "why": "0 层自检/复述线索 ⇒ 加深自检与阶段探针"})
    if _l1.get("citations", 0) < 1:
        out.append({"kind": "probe",
                    "cond": {"issue": "layer1_citation_low"},
                    "action": {"key": "carve_first", "layers": ["1"]},
                    "readings": {"before": {"citations": _l1.get("citations")},
                                 "after": {"citations": "期望上升"}},
                    "why": "1 层子问题无引用 ⇒ 研究层优先补证"})
    if _l1.get("duty") is not None and float(_l1.get("duty")) < 0.35:
        out.append({"kind": "schedule",
                    "cond": {"issue": "layer1_duty_short"},
                    "action": {"key": "rounds_delta", "layer": "1",
                               "delta": 1},
                    "readings": {"before": {"duty_S": _l1.get("duty")},
                                 "after": {"duty_S": "期望上升"}},
                    "why": "1 层职责不足 ⇒ 研究层多一圈逼近"})
    if _l1.get("flags"):
        out.append({"kind": "guard",
                    "cond": {"issue": "layer1_adjudication_noise"},
                    "action": {"key": "thinking_hint",
                               "stages": ["assess_decidability",
                                          "adjudicate_sub_tristate"],
                               "value": "enabled"},
                    "readings": {"before": {"flags": _l1.get("flags")[:6]},
                                 "after": {"flags": "期望下降"}},
                    "why": "1 层裁决/可判定噪声 ⇒ 加深该环节思考"})
    try:
        from .frontier_feedback import rank_candidates
        out = rank_candidates(out)
    except Exception:
        pass
    for c in out:
        c["evidence"] = [rid] if rid else []
        c["source"] = "engine/both-all"
    return out


__all__ = ["collect_feedback", "candidates"]
