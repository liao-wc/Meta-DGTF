# -*- coding: utf-8 -*-
"""四层核心职责审计 + 可靠修复。

核心原则：
- 不凭空补内容；只做“已有产物搬到正确层”和“证据字段回退映射”。
- 修不了就记 gap，不把 gap 伪装成通过。
"""
from __future__ import annotations

import copy
from typing import Any


def _v(packed: dict, entry: str) -> dict:
    return copy.deepcopy(((packed.get("views") or {}).get(entry) or {}))


def _p(packed: dict, entry: str) -> dict:
    return ((packed.get("pools") or {}).get(entry) or {})


def _l1_actions(packed: dict) -> list:
    v = _v(packed, "1")
    dp = v.get("decidable_product") or {}
    return list(v.get("_actions") or dp.get("actions") or [])


def _l1_not_do(packed: dict) -> list:
    v = _v(packed, "1")
    dp = v.get("decidable_product") or {}
    return list(v.get("_not_do") or dp.get("not_do") or [])


def repair_packed(packed: dict) -> tuple[dict, list[str]]:
    """返回 (修复副本, 修复记录)。不改原 packed。"""
    d = copy.deepcopy(packed)
    views = d.setdefault("views", {})
    repairs: list[str] = []

    # 1) 研究层：decidable 的 evidence 回退为 citations（不是新证据，是换字段）
    v1 = views.get("1") or {}
    for s in (_p(d, "1").get("sub_questions") or []):
        if not s.get("citations") and s.get("evidence"):
            s["citations"] = list(s.get("evidence") or [])
            repairs.append("1.citations<-evidence:%s" % s.get("id"))

    # 2) 研究层行动迁移到 all：契约禁止 1 层 action_plan
    acts = _l1_actions(d)
    notes = _l1_not_do(d)
    if acts:
        v1["_actions_migrated"] = len(acts)
        v1["_actions"] = []
        dp = v1.setdefault("decidable_product", {})
        dp["actions"] = []
        repairs.append("1.actions->all:%d" % len(acts))

    # 3) all 层：只为“实际存在的 all view”补四件套；
    #    没跑 all 的跑次不创建空 all、不伪造 provenance。
    va = views.get("all")
    if not isinstance(va, dict) or not va:
        d["views"] = views
        return d, repairs
    if not va.get("actions"):
        va["actions"] = acts
        if acts:
            va["actions_source"] = "migrated_from_1"
            repairs.append("all.actions<-1")
    if not va.get("not_do"):
        va["not_do"] = notes
        if notes:
            va["not_do_source"] = "migrated_from_1"
            repairs.append("all.not_do<-1")
    if not va.get("decision"):
        dp = va.get("decidable_product") or {}
        if isinstance(dp, dict):
            va["decision"] = str(dp.get("answer") or va.get("manifest") or "")[:400]
        else:
            va["decision"] = str(dp or va.get("manifest") or "")[:400]
        if va["decision"]:
            repairs.append("all.decision<-manifest/product")
    if not va.get("residual_risks"):
        va["residual_risks"] = [str(x.get("desc") or x)[:120]
                                for x in (va.get("threads") or [])]
        if va["residual_risks"]:
            repairs.append("all.residual<-threads")
    prov = list(va.get("provenance") or [])
    if "v1:packed" not in prov:
        prov.append("v1:packed")
    if acts and "actions:migrated:1" not in prov:
        prov.append("actions:migrated:1")
    if not va.get("provenance"):
        repairs.append("all.provenance<-v1:packed")
    va["provenance"] = prov
    if not va.get("confidence"):
        q = d.get("quality") or {}
        va["confidence"] = float(q.get("tri_ratio") or 0.0)
    d["views"] = views
    return d, repairs


def audit_packed(packed: dict) -> dict:
    # 先看“修复前”的越权，修复只用于后续缺口判定。
    pre = packed.get("views") or {}
    pre_over: list[str] = []
    p0 = pre.get("0") or {}
    p1 = pre.get("1") or {}
    pb = pre.get("both") or {}
    if p0.get("_actions") or (p0.get("decidable_product") or {}).get("actions"):
        pre_over.append("0: 出现 action_plan（越权）")
    if p1.get("_actions") or (p1.get("decidable_product") or {}).get("actions"):
        pre_over.append("1: 出现 action_plan（越权）")
    if pb.get("actions") or (pb.get("decidable_product") or {}).get("actions"):
        pre_over.append("both: 出现 action_plan（越权）")
    d, repairs = repair_packed(packed)
    views = d.get("views") or {}
    out: dict[str, Any] = {"layers": {}, "gaps": [],
                           "overreach": list(pre_over), "repairs": repairs}
    route = {str(x) for x in (d.get("route") or [])}

    # 0：必须有 aspect_map / probe_queue，且不得有 action/decision
    v0 = views.get("0") or {}
    if "0" in route:
        a0 = len(v0.get("candidates") or []) + len(v0.get("amps") or [])
        p0 = len(v0.get("probes") or [])
        s0 = len(v0.get("suspensions") or [])
        ok0 = a0 > 0 and (p0 > 0 or s0 > 0)
        out["layers"]["0"] = {"ok": ok0, "aspects": a0, "probes": p0,
                              "suspensions": s0}
        if not ok0:
            out["gaps"].append("0: aspect/probe/suspension 核心不足")
        # 越权在“修复前”已统一记录，这里不重复。
    else:
        out["layers"]["0"] = {"ok": True, "skipped": "not_in_route"}

    # 1：子问题/答案/引用；不得有 action_plan
    v1 = views.get("1") or {}
    if "1" in route:
        subs = list(_p(d, "1").get("sub_questions") or [])
        dec = [s for s in subs if str(s.get("decidability") or "") == "decidable"]
        cited = [s for s in dec if (s.get("citations") or s.get("evidence"))]
        dp = v1.get("decidable_product") or {}
        dp_evidence = list(dp.get("evidence") or [])
        ok1 = bool(subs) and (bool(dp_evidence) or len(cited) == len(dec))
        out["layers"]["1"] = {"ok": ok1, "subs": len(subs),
                              "decidable": len(dec), "cited": len(cited),
                              "layer_evidence": len(dp_evidence)}
        if not subs:
            out["gaps"].append("1: 无子问题")
        if not dp_evidence and len(cited) != len(dec):
            out["gaps"].append("1: decidable 无证据 %d/%d"
                               % (len(dec) - len(cited), len(dec)))
        # 越权在“修复前”已统一记录，这里不重复。
    else:
        out["layers"]["1"] = {"ok": True, "skipped": "not_in_route"}

    # both：综合/张力；不得有 final_decision/action_plan
    vb = views.get("both") or {}
    if "both" in route:
        okb = bool(vb.get("manifest") or vb.get("collision")
                   or vb.get("threads") or vb.get("amps"))
        out["layers"]["both"] = {"ok": okb,
                                 "adjudications": len(vb.get("adjudications") or []),
                                 "threads": len(vb.get("threads") or [])}
        if not okb:
            out["gaps"].append("both: 无综合/张力")
        # 越权在“修复前”已统一记录，这里不重复。
    else:
        out["layers"]["both"] = {"ok": True, "skipped": "not_in_route"}

    # all：决策/行动/不做/残余风险/来源
    # ★ boundary profile：边界题不要求行动闭环；只要求决策/残余/来源。
    _orient = str(packed.get("orientation") or "").lower()
    _want_actions = _orient != "boundary"
    va = views.get("all") or {}
    if "all" in route:
        req = {"decision": bool(str(va.get("decision") or "").strip()),
               "residual_risks": bool(va.get("residual_risks")),
               "provenance": bool(va.get("provenance"))}
        if _want_actions:
            req["actions"] = bool(va.get("actions"))
            req["not_do"] = bool(va.get("not_do"))
        oka = all(req.values())
        out["layers"]["all"] = {"ok": oka, "required": req,
                                "actions_expected": _want_actions,
                                "actions": len(va.get("actions") or []),
                                "not_do": len(va.get("not_do") or [])}
        for k, ok in req.items():
            if not ok:
                out["gaps"].append("all: 缺 %s" % k)
    else:
        # ★ all_v2 默认开时，all 是契约必需层：不能把“没跑”当成通过。
        _acts = (packed.get("_config") or {}).get("actions") or {}
        _allv2 = bool(_acts.get("all_v2", False))
        if _allv2:
            out["layers"]["all"] = {"ok": False, "skipped": "not_in_route",
                                    "required_by": "actions.all_v2"}
            out["gaps"].append("all: actions.all_v2=true 但 all 未执行")
            if str(packed.get("actions_source") or "") == "1":
                out["gaps"].append("all: actions 从 1 层兜底（actions_source=1）")
        else:
            out["layers"]["all"] = {"ok": True, "skipped": "not_in_route"}

    out["ok"] = (not out["gaps"] and not out["overreach"]
                 and not repairs)
    return out
