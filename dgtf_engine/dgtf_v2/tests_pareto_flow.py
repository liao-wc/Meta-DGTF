# -*- coding: utf-8 -*-
"""全流程帕累托先行模块判据（第一版）：指标抽取 / 支配关系 / 前沿。"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dgtf_v2.pareto_flow import (dominates, extract_flow_metrics, joint_snapshot,
                                 load_packed_runs, pareto_frontier, recommend, report)

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if info and not ok else ""))


def _pack(quality, tokens, calls, coverage=0.5, flags=None):
    return {
        "id": "r-%s-%s" % (quality, tokens),
        "question": "q",
        "route": ["0", "1", "both", "all"],
        "rounds": {"0": 2, "1": 2, "both": 2, "all": 2},
        "quality": {"answer_ready": True, "process_ready": True,
                    "answer_quality": quality, "coverage": coverage,
                    "flags": list(flags or [])},
        "decision_trace": {"answer_ready": True, "process_ready": True,
                           "answer_quality": quality},
        "process_ledger": {"standard_all": True},
        "llm_tokens": tokens, "llm_calls": calls,
        "api_usage": {"web_enabled": True, "tools_calls": 2},
    }


def main():
    good = extract_flow_metrics(_pack("verified", 100000, 100))
    ck("verified 质量分 >0.8", good["quality"] > 0.8, good)
    ck("成本字段抽取", good["tokens"] == 100000 and good["calls"] == 100, good)
    ck("standard_all 抽取", good["standard_all"] is True)
    ck("flags 惩罚", extract_flow_metrics(_pack("verified", 1, 1, flags=["a", "b"]))["quality"]
       < good["quality"])

    low = extract_flow_metrics({**_pack("", 100000, 100),
                                "quality": {"flags": []},
                                "decision_trace": {"answer_ready": False,
                                                   "answer_quality": ""}})
    ck("未就绪质量分低", low["quality"] < 0.5, low["quality"])

    a = {"id": "A", "quality": 1.0, "tokens": 100, "calls": 10}
    b = {"id": "B", "quality": 0.8, "tokens": 100, "calls": 10}
    c = {"id": "C", "quality": 0.9, "tokens": 50, "calls": 5}
    d = {"id": "D", "quality": 1.0, "tokens": 200, "calls": 20}
    ck("A 支配 B", dominates(a, b) is True)
    ck("C 不被 A 支配", dominates(a, c) is False)
    front = [r["id"] for r in pareto_frontier([a, b, c, d])]
    ck("前沿 = A,C", front == ["A", "C"], front)
    ck("非支配集合保留输入顺序", front == ["A", "C"])

    miss = {"id": "M", "quality": 1.0, "tokens": None, "calls": None}
    ck("缺失成本不参与支配", dominates(miss, a) is False and dominates(a, miss) is False)

    with tempfile.TemporaryDirectory() as td:
        p1 = Path(td) / "a.packed.json"
        p2 = Path(td) / "b.packed.json"
        p1.write_text(json.dumps(_pack("verified", 100000, 100)), encoding="utf-8")
        p2.write_text(json.dumps(_pack("unverified", 50000, 50)), encoding="utf-8")
        rows = load_packed_runs([p1, p2])
        ck("load 2 份", len(rows) == 2, len(rows))
        rep = report(rows)
        ck("report 前沿非空", len(rep["frontier"]) >= 1, rep["frontier"])
        ck("best_quality 存在", rep["best_quality"] is not None)

    # ── 预算选档（Round 2）──
    runs = [
        {"id": "cost", "quality": 0.83, "tokens": 478000, "calls": 80},
        {"id": "low", "quality": 0.86, "tokens": 512000, "calls": 82},
        {"id": "balanced", "quality": 0.917, "tokens": 671000, "calls": 83},
        {"id": "quality", "quality": 0.959, "tokens": 1295000, "calls": 117},
    ]
    r1 = recommend(runs, budget_tokens=800000, min_quality=0.9)
    ck("预算内满足质量选均衡档", (r1.get("row") or {}).get("id") == "balanced", r1)
    r2 = recommend(runs, budget_tokens=600000)
    ck("预算内质量最高", (r2.get("row") or {}).get("id") == "low", r2)
    r3 = recommend(runs, min_quality=0.95)
    ck("质量下限选质量档", (r3.get("row") or {}).get("id") == "quality", r3)
    r4 = recommend(runs, budget_tokens=600000, min_quality=0.9)
    ck("无可行候选退为满足质量最便宜", (r4.get("row") or {}).get("id") == "balanced"
       and "最便宜" in str(r4.get("reason")), r4)
    r5 = recommend(runs, min_quality=0.999)
    ck("质量不可能时退全局最高", (r5.get("row") or {}).get("id") == "quality", r5)
    r6 = recommend([], budget_tokens=100)
    ck("空表不崩", r6.get("row") is None)

    js = joint_snapshot({"n": 1, "frontier": ["x"], "recommend": {"row": runs[0]}},
                        app={"health": {"p50_ms": 15}}, local={"bge": {"p50_ms": 3}})
    ck("联动快照含三组件", set(js.keys()) >= {"engine", "app", "local", "note"}, js)

    print()
    print("PASS %d / FAIL %d" % (len(P), len(F)))
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
