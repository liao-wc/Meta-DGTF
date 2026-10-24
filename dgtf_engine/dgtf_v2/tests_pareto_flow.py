# -*- coding: utf-8 -*-
"""全流程帕累托先行模块判据（第一版）：指标抽取 / 支配关系 / 前沿。"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dgtf_v2.pareto_flow import (dominates, extract_flow_metrics, joint_snapshot,
                                 load_packed_runs, pareto_frontier, recommend, report,
                                 select_joint)
from dgtf_v2.mode_fusion import fused_plan, scenario_table, select_mode

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

    # ── 三组件联动选档（Round 5）──
    web = [
        {"id": "webcost", "quality": 0.909, "tokens": 969376, "calls": 89,
         "web_enabled": True},
        {"id": "nowebcost", "quality": 0.990, "tokens": 997457, "calls": 107,
         "web_enabled": False},
    ]
    j1 = select_joint(web, app={"health": {"p50_ms": 15}},
                      local={"bge": {"texts_per_s": 451}},
                      budget_tokens=1000000, min_quality=0.9)
    ck("联动选档优先高质量无网档", (j1.get("row") or {}).get("id") == "nowebcost", j1)
    j2 = select_joint(web, budget_tokens=1000000, min_quality=0.9, require_web=True)
    ck("要求联网时选官方联网档", (j2.get("row") or {}).get("id") == "webcost", j2)
    j3 = select_joint(web, budget_tokens=980000, min_quality=0.95)
    ck("预算不足时给出回退原因", (j3.get("row") or {}).get("id") == "nowebcost"
       and "退为" in str(j3.get("reason")), j3)
    j4 = select_joint(web, budget_tokens=980000, min_quality=0.9, require_web=True)
    ck("联网档超预算回退", (j4.get("row") or {}).get("id") == "webcost", j4)
    # ── 墙钟（Round 10）──
    lat = [
        {"id": "fast", "quality": 0.909, "tokens": 969376, "calls": 89,
         "elapsed": 1889.7, "web_enabled": True},
        {"id": "slow", "quality": 0.990, "tokens": 997457, "calls": 107,
         "elapsed": 1920.6, "web_enabled": False},
    ]
    j5 = select_joint(lat, budget_tokens=1000000, min_quality=0.9,
                      max_wall_seconds=1900)
    ck("墙钟约束选低时延档", (j5.get("row") or {}).get("id") == "fast", j5)
    j6 = select_joint(lat, budget_tokens=1000000, min_quality=0.9,
                      max_wall_seconds=1930)
    ck("墙钟放宽选高质量档", (j6.get("row") or {}).get("id") == "slow", j6)
    # ── 模式级 Pareto / M4 auto-fused（Round 14）──
    m1 = select_mode(min_quality=0.99)
    ck("质量优先选模式 B", m1.get("mode") == "B", m1)
    m2 = select_mode(min_quality=0.9, max_wall=900)
    ck("墙钟约束选 fast", m2.get("mode") == "fast", m2)
    m3 = select_mode(min_quality=0.95, max_tokens=1000000)
    ck("tokens 约束选 serial", m3.get("mode") == "serial", m3)
    m4 = select_mode(min_quality=0.9, require_web=True)
    ck("必须联网选 web", m4.get("mode") == "web", m4)
    m5 = select_mode(min_quality=0.999)
    ck("质量不可行退最高质量", m5.get("mode") == "B", m5)
    fp = fused_plan(min_quality=0.9, max_wall=900, cascade=True)
    ck("M4 级联 fast→B", (fp.get("first") or {}).get("mode") == "fast"
       and (fp.get("cascade") or {}).get("upgrade_to") == "B", fp)
    ck("场景表 5 项", len(scenario_table()) == 5)
    with tempfile.TemporaryDirectory() as td2:
        pp = Path(td2) / "x.packed.json"
        pp.write_text(json.dumps(_pack("verified", 100000, 100)), encoding="utf-8")
        merged = load_packed_runs([pp], {"r-verified-100000": 1234.5})
    ck("侧车墙钟合并", bool(merged) and merged[0].get("elapsed") == 1234.5, merged)

    print()
    print("PASS %d / FAIL %d" % (len(P), len(F)))
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
