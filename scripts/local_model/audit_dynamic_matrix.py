# -*- coding: utf-8 -*-
"""[V2.2.74] 动态配置决策矩阵审计（纯函数，零 API）。

枚举 余额 × 题型，调用 daosheng_mode.build_plan，记录最终 plan 关键字段，
并检查硬约束（fact 必须 web on、预算越紧不能越贵、tier/engine_mode 一致等）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dgtf_engine"))
sys.path.insert(0, str(ROOT / "dgtf_app"))

import daosheng_mode as DS  # noqa: E402

QUESTIONS = {
    "fact": "HTTP 404 状态码表示什么？",
    "reasoning": "为什么城市热岛效应在夜间比白天更明显？",
    "choice": "以下哪项属于可再生能源？A. 煤炭 B. 太阳能 C. 石油 D. 天然气",
    "project": "Meta-DGTF 道生三阶模型的项目当前状态如何？",
}
BALANCES = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 8.0, 20.0, 50.0]


def one(kind: str, q: str, bal: float) -> dict:
    p = DS.build_plan(q, {}, requested="daosheng", is_mock=False,
                      balance_cny=float(bal))
    bg = p.get("budget_guard") or {}
    dyn = p.get("dynamic_opt") or {}
    return {
        "kind": kind,
        "balance": bal,
        "tier": p.get("tier"),
        "engine_mode": p.get("engine_mode"),
        "rounds": p.get("rounds"),
        "web": p.get("web"),
        "parallel": p.get("parallel"),
        "thinking": p.get("thinking"),
        "effort": p.get("effort"),
        "budget_level": bg.get("budget_level"),
        "budget_decision": bg.get("decision"),
        "est_cost_cny": bg.get("est_cost_cny"),
        "dynamic_fallback": bool(dyn.get("fallback")),
        "dynamic_applied": dyn.get("applied") or {},
        "tier_advice": (p.get("quality_retry") or {}).get("tier_advice"),
        "prefer_cost": p.get("prefer_cost_when_unverified"),
        "cache": p.get("cache") or {},
        "budget_forecast": p.get("budget_forecast") or {},
    }


def detect_violations(rows) -> list:
    bad = []
    for r in rows:
        if r.get("error"):
            bad.append(r)
            continue
        if r["kind"] in ("fact", "choice") and r.get("web") != "on":
            bad.append({"kind": r["kind"], "balance": r["balance"],
                        "why": "%s web != on" % r["kind"], "row": r})
        if r.get("tier") == "quality" and r.get("engine_mode") == "fast":
            bad.append({"kind": r["kind"], "balance": r["balance"],
                        "why": "tier=quality but engine_mode=fast", "row": r})
        if r.get("tier") == "fast" and r.get("engine_mode") not in ("fast", None):
            bad.append({"kind": r["kind"], "balance": r["balance"],
                        "why": "tier=fast but engine_mode!=fast", "row": r})
        # ★ [V2.2.84] 预算层级 ↔ tier：紧预算必须降 fast；ok 默认 quality（除非 opt-in）
        _lvl = str(r.get("budget_level") or "")
        if _lvl in ("warn", "degrade", "critical") and r.get("tier") != "fast":
            bad.append({"kind": r["kind"], "balance": r["balance"],
                        "why": "紧预算未降 fast", "row": r})
        if (_lvl == "ok" and r.get("tier") == "fast"
                and not r.get("prefer_cost")):
            bad.append({"kind": r["kind"], "balance": r["balance"],
                        "why": "ok 未用 quality（未 opt-in prefer_cost）", "row": r})
    return bad


def self_test() -> None:
    cases = [
        ([{"kind": "fact", "balance": 50.0, "web": "off",
           "tier": "quality", "engine_mode": "B"}], "fact web != on"),
        ([{"kind": "reasoning", "balance": 50.0, "web": "auto",
           "tier": "quality", "engine_mode": "fast"}],
         "tier=quality but engine_mode=fast"),
        ([{"kind": "choice", "balance": 4.0, "web": "off",
           "tier": "fast", "engine_mode": "B"}],
         "choice web != on"),
        ([{"kind": "fact", "balance": 4.0, "web": "on",
           "tier": "quality", "engine_mode": "B",
           "budget_level": "degrade"}],
         "紧预算未降 fast"),
        ([{"kind": "reasoning", "balance": 50.0, "web": "auto",
           "tier": "fast", "engine_mode": "fast",
           "budget_level": "ok", "prefer_cost": False}],
         "ok 未用 quality"),
    ]
    for rows, why in cases:
        got = detect_violations(rows)
        assert any(why in (b.get("why") or "") for b in got), why
    print("self-test: detector has teeth (5/5 mutants caught)")

def main() -> int:
    self_test()
    rows = []
    for kind, q in QUESTIONS.items():
        for bal in BALANCES:
            try:
                rows.append(one(kind, q, bal))
            except Exception as e:  # noqa: BLE001
                rows.append({"kind": kind, "balance": bal,
                             "error": "%s: %s" % (type(e).__name__, e)})
    bad = detect_violations(rows)
    out = {"schema": "metadgtf.dynamic_matrix_audit.v1",
           "rows": rows, "violations": bad,
           "n": len(rows), "n_bad": len(bad)}
    ev = ROOT / "docs" / "dynamic_matrix_audit_20261030.json"
    ev.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                  encoding="utf-8")
    print("%-9s %6s %8s %8s %5s %5s %-9s" % (
        "kind", "bal", "tier", "engine", "web", "cache", "budget"))
    for r in rows:
        cp = r.get("cache_prediction") or {}
        print("%-9s %6s %8s %8s %5s %5s %-9s" % (
            r.get("kind"), r.get("balance"), r.get("tier"),
            r.get("engine_mode"), r.get("web"),
            str(cp.get("hit")), r.get("budget_decision")))
    print("violations:", len(bad))
    for b in bad[:5]:
        print("  ", b.get("why") or b.get("error"))
    print("evidence ->", ev.relative_to(ROOT))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
