# -*- coding: utf-8 -*-
"""全流程帕累托先行模块判据（第一版）：指标抽取 / 支配关系 / 前沿。"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dgtf_v2.pareto_flow import (dominates, extract_flow_metrics, load_packed_runs,
                                 pareto_frontier, report)

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

    print()
    print("PASS %d / FAIL %d" % (len(P), len(F)))
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
