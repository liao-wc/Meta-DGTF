# -*- coding: utf-8 -*-
"""四层事实契约：已确认事实必须进入每层产物，0/1 不得装未知。"""
from __future__ import annotations
import re

_LAYERS = ("0", "1", "both", "all")
_UNKNOWN = ("未显形", "未确定", "不知道", "无记录", "无法确定", "未核实")


def _norm(s: str) -> str:
    return (str(s or "").replace("年", "-").replace("月", "-")
            .replace("日", ""))


def _texts(layer: str, view: dict) -> list:
    v = view or {}
    out = [str(v.get("manifest") or "")]
    if layer == "1":
        out.append(str((v.get("decidable_product") or {}).get("answer") or ""))
    if layer == "both":
        out.append(str(v.get("collision") or ""))
    if layer == "all":
        out.append(str(v.get("decision") or ""))
        out.append(str(v.get("summary") or ""))
    return [x for x in out if x.strip()]


def check_layer(layer: str, view: dict, ledger: dict) -> dict:
    ans = str((ledger or {}).get("answer") or "")
    if not (ledger or {}).get("known") or not ans:
        return {"layer": layer, "ok": True, "reason": "no_ledger"}
    blob = " ".join(_texts(layer, view))
    norm = _norm(blob)
    a = _norm(ans)
    hit = a and a in norm
    if not hit and re.match(r"\d{4}-\d{1,2}-\d{1,2}", a):
        y, m, d = a.split("-")[:3]
        hit = (y in norm and int(m) == int(m) and
               ("%s-%s" % (m, d)) in norm)
    unknown = [w for w in _UNKNOWN if w in blob]
    return {"layer": layer, "ok": bool(hit),
            "answer": ans, "answer_hit": bool(hit),
            "unknown_markers": unknown[:4],
            "chars": len(blob),
            "reason": "fact_present" if hit else "fact_missing"}


def repair_layer(layer: str, view: dict, ledger: dict) -> dict:
    ans = str((ledger or {}).get("answer") or "")
    q = str((ledger or {}).get("question") or "")
    hint = "【已核实事实】%s：%s（官方源）。这是已知事实，不是未确定。" % (q, ans)
    v = view if isinstance(view, dict) else {}
    if layer in ("0", "both", "all"):
        v["manifest"] = hint + "\n\n" + str(v.get("manifest") or "")
    if layer == "1":
        dp = v.get("decidable_product")
        if not isinstance(dp, dict):
            dp = {}
        dp["answer"] = hint + " " + str(dp.get("answer") or "")
        v["decidable_product"] = dp
        v["manifest"] = hint + "\n\n" + str(v.get("manifest") or "")
    if layer == "all" and not str(v.get("decision") or "").strip():
        v["decision"] = hint
    v.setdefault("fact_contract", {})
    v["fact_contract"] = {"repaired": True, "answer": ans}
    return v


def run_contract(views: dict, ledger: dict) -> dict:
    layers = {}
    ok_all = True
    for e in _LAYERS:
        v = (views or {}).get(e) or {}
        r = check_layer(e, v, ledger)
        if not r.get("ok"):
            repair_layer(e, v, ledger)
            r2 = check_layer(e, v, ledger)
            r2["repaired"] = True
            r = r2
        if not r.get("ok"):
            ok_all = False
        layers[e] = r
    return {"ok_all": bool(ok_all), "layers": layers,
            "ledger": dict(ledger or {})}


__all__ = ["check_layer", "repair_layer", "run_contract"]
