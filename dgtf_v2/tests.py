# -*- coding: utf-8 -*-
"""V2 参考内核判据（无外部依赖、无 API、确定性）。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.contracts import (Budget, ContractViolation, LAYER_CONTRACTS,
                               LayerResult, LayerState, legal_actions,
                               validate_result)
from dgtf_v2.memory import MemoryLake
from dgtf_v2.orchestrator import MockLayerExecutor, Orchestrator
from dgtf_v2.scheduler import Action, Scheduler, WorldState

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name
          + ((" — " + str(detail)) if detail and not cond else ""))


def _result(entry: str, art: dict) -> LayerResult:
    return LayerResult(entry=entry, artifacts=art,
                       state=LayerState(entry), calls=1, tokens=10,
                       provenance=["test"])


def main() -> int:
    # ── 契约 ────────────────────────────────────────────────
    check("契约：四层齐全", set(LAYER_CONTRACTS) == {"0", "1", "both", "all"})
    bad = _result("0", {"answer": "x", "aspect_map": [1], "suspensions": [],
                        "probe_queue": [], "novelty_curve": []})
    try:
        validate_result(LAYER_CONTRACTS["0"], bad)
        check("契约：0 层越权给 answer 必须判红", False)
    except ContractViolation:
        check("契约：0 层越权给 answer 必须判红", True)

    bad1 = _result("1", {"answer_set": [
        {"label": "decidable", "citations": []}],
        "abstentions": [], "coverage": 0.5, "citations": [], "debt_set": []})
    try:
        validate_result(LAYER_CONTRACTS["1"], bad1)
        check("契约：1 层 decidable 无引用必须判红", False)
    except ContractViolation:
        check("契约：1 层 decidable 无引用必须判红", True)

    bad_both = _result("both", {"synthesis": "s", "argument_graph": {},
                                "tension_set": [], "defeated_claims": []})
    try:
        validate_result(LAYER_CONTRACTS["both"], bad_both)
        check("契约：both 必须保留 defeated/undecided", False)
    except ContractViolation:
        check("契约：both 必须保留 defeated/undecided", True)

    bad_all = _result("all", {"decision": "d", "actions": [{"owner": "a"}],
                              "not_do": ["x"], "residual_risks": ["r"],
                              "provenance": ["p"], "confidence": 0.5})
    try:
        validate_result(LAYER_CONTRACTS["all"], bad_all)
        check("契约：all 动作缺回退必须判红", False)
    except ContractViolation:
        check("契约：all 动作缺回退必须判红", True)

    # 合法 mock 结果
    executor = MockLayerExecutor()
    st = WorldState("q", {e: LayerState(e) for e in ("0", "1", "both", "all")},
                    Budget(100000, 100, 100))
    r0 = executor.execute(Action("run_layer", "0", 1), st)
    validate_result(LAYER_CONTRACTS["0"], r0)
    check("契约：合法 0 层结果通过", True)

    # 依赖：1 不能先于 0；both 不能先于 0/1；all 不能先于 both
    states = {e: LayerState(e) for e in ("0", "1", "both", "all")}
    acts = legal_actions(states, Budget(100000, 100, 100))
    check("依赖：初始只允许 0 层",
          {a for a, _ in acts} == {"0"}, acts)
    states["0"].status = "done"
    states["0"].rounds = 3
    acts2 = legal_actions(states, Budget(100000, 100, 100))
    check("依赖：0 完成后才允许 1", "1" in [a for a, _ in acts2], acts2)
    check("依赖：both 仍被 1 阻断", "both" not in [a for a, _ in acts2], acts2)

    # ── EML v2 ──────────────────────────────────────────────
    mem = MemoryLake()
    mem.append(run_id="r1", plane="semantic", layer="1", kind="claim",
               key="k", payload={"v": 1}, provenance=["A1"])
    t1 = mem.now()
    mem.revise("k", {"v": 2}, run_id="r2", layer="1", reason="new evidence")
    check("双时态：revision 前读到 v1", mem.beliefs(as_of=t1)["k"].payload["v"] == 1)
    check("双时态：当前读到 v2", mem.beliefs()["k"].payload["v"] == 2)
    mem.defeat("k", "counter", reason="反例", run_id="r3")
    check("论证：defeated 默认不召回", "k" not in mem.beliefs())
    check("论证：defeated 仍保留在盘", "k" in mem.beliefs(include_defeated=True))
    check("论证：行数只增不删", len(mem.events) == 3)

    mem2 = MemoryLake()
    mem2.append(run_id="r", plane="semantic", layer="1", kind="claim",
                key="alpha", payload={"text": "alpha beta", "tier": 1},
                provenance=["A1"], confidence=0.8)
    mem2.append(run_id="r", plane="semantic", layer="1", kind="claim",
                key="gamma", payload={"text": "gamma delta", "tier": 4},
                provenance=["A2"], confidence=0.3)
    hits = mem2.retrieve("alpha", k=2)
    check("检索：相关项排第一", hits and hits[0]["key"] == "alpha", hits)
    check("检索：结果带 provenance", all("provenance" in h for h in hits))

    mem2.append(run_id="r", plane="episodic", layer="1", kind="obs",
                key="ep", payload={"text": "alpha observed"})
    made = mem2.consolidate("r", min_support=1)
    check("巩固：micro→macro 生成 semantic", len(made) >= 1, len(made))

    mem2.record_outcome(run_id="r", template="1:r1", quality=0.8,
                        calls=2, tokens=300, success=True)
    pri = mem2.scheduler_priors()
    check("EML：先验有模板", "1:r1" in pri["templates"], pri)
    check("EML：先验不含内容", pri["contains_content"] is False)
    blob = str(pri)
    check("EML：先验不透出答案文本", "alpha" not in blob and "gamma" not in blob)

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "mem.jsonl"
        mem2.save(path)
        mem3 = MemoryLake(path)
        check("持久化：save/load 事件数一致", len(mem3.events) == len(mem2.events))
        check("持久化：load 后先验仍在", "1:r1" in mem3.scheduler_priors()["templates"])

    old = MemoryLake()
    old.append(run_id="r", plane="semantic", layer="1", kind="claim",
               key="old", payload={"v": 1})
    old.tick(5000)
    faded = old.forget(half_life=100)
    check("遗忘：老条目 retention 下降", bool(faded) and faded[0]["retention"] < 0.35, faded)

    # ── 调度 v2 ─────────────────────────────────────────────
    smem = MemoryLake()
    sched = Scheduler(smem, target_coverage=0.8)
    b = Budget(100000, 100, 100)
    st0 = {e: LayerState(e) for e in ("0", "1", "both", "all")}
    ws = WorldState("q", st0, b)
    d0 = sched.plan(ws)
    check("调度：初始选 0（无 1 依赖）", d0 is not None and d0.action.entry == "0",
          d0.action.template() if d0 else None)
    ws.layers["0"] = LayerState("0", rounds=3, status="done", novelty=0.8)
    d1 = sched.plan(ws)
    check("调度：0 完成后选 1", d1 is not None and d1.action.entry == "1",
          d1.action.template() if d1 else None)
    ws.layers["1"] = LayerState("1", rounds=2, status="done", coverage=1.0)
    ws.conflicts = [{"id": "T1"}, {"id": "T2"}]
    d2 = sched.plan(ws)
    check("调度：有张力时选 both", d2 is not None and d2.action.entry == "both",
          d2.action.template() if d2 else None)
    ws.layers["both"] = LayerState("both", rounds=2, status="done")
    d3 = sched.plan(ws)
    check("调度：前三层完成后选 all", d3 is not None and d3.action.entry == "all",
          d3.action.template() if d3 else None)
    zero = WorldState("q", {e: LayerState(e) for e in ("0", "1", "both", "all")},
                      Budget(0, 0, 0))
    check("调度：零预算不动作", sched.plan(zero) is None)

    # ── 端到端 ──────────────────────────────────────────────
    omem = MemoryLake()
    orch = Orchestrator(omem)
    rep = orch.run("测试问题：如何把不确定性变成可执行动作？",
                   max_tokens=20000, max_calls=12, max_rounds=12)
    check("端到端：四层都完成",
          all(rep.trace.final_state.layers[e].status == "done"
              for e in ("0", "1", "both", "all")),
          rep.trace.stop_reason)
    check("端到端：有决策", bool(rep.closure.get("decision")))
    check("端到端：动作四字段齐",
          all(all(a.get(f) for f in ("owner", "deadline", "acceptance", "rollback"))
              for a in rep.closure.get("actions", [])))
    check("端到端：not_do/风险/来源齐",
          bool(rep.closure.get("not_do")) and bool(rep.closure.get("residual_risks"))
          and bool(rep.closure.get("provenance")))
    check("端到端：质量 > 0", rep.trace.quality > 0, rep.trace.quality)
    check("端到端：有调度轨迹", len(rep.trace.decisions) >= 4, len(rep.trace.decisions))
    check("端到端：markdown 有 Closure", "## Closure" in rep.markdown)
    check("端到端：记忆已记 outcomes",
          bool(omem.scheduler_priors()["templates"]),
          omem.scheduler_priors())

    # ── Phase 2/3/4 适配 ─────────────────────────────────────
    from dgtf_v2.bridge import V2MemoryBridge
    from dgtf_v2.shadow import V2Shadow

    packed = {
        "id": "20261019_000000", "question": "q", "route": ["0", "1", "both", "all"],
        "rounds": {"0": 1, "1": 1, "both": 1, "all": 1},
        "llm_calls": 8, "llm_tokens": 4000,
        "views": {
            "0": {"candidates": [{"desc": "x"}], "amps": [], "threads": [],
                  "suspensions": [], "probes": []},
            "1": {"entry": "1"},
            "both": {"manifest": "s", "adjudications": [], "threads": []},
            "all": {"decidable_product": "d", "suspensions": [], "threads": []},
        },
        "pools": {"1": {"sub_questions": [
            {"id": "Q1", "decidability": "decidable", "citations": []}]}},
        "quality": {"coverage": 0.5, "tri_ratio": 0.5,
                    "answered": 1, "answerable_total": 2},
    }
    with tempfile.TemporaryDirectory() as td:
        bp = Path(td) / "v2.jsonl"
        bridge = V2MemoryBridge(bp)
        rec = bridge.record_packed(packed)
        check("双写：结构+outcome 落盘", rec.get("events", 0) >= 8, rec)
        check("双写：先验可读", bool(bridge.priors()["templates"]))
        cr = bridge.contract_report(packed, "warn")
        check("契约：warn 抓到 1 层/all 层缺口",
              "1" in cr["violations"] and "all" in cr["violations"], cr)
        anon = V2MemoryBridge(Path(td) / "anon.jsonl", allow_anon=False)
        rec2 = anon.record_packed({"id": "", "views": {}})
        check("双写：匿名不写生产记忆", rec2.get("skipped") == "anon", rec2)
        s = V2Shadow("q", ["0", "1", "both", "all"],
                     {"0": 3, "1": 2, "both": 2, "all": 1}, "serial",
                     {"max_tokens": 200000},
                     eml_path=str(Path(td) / "v2_shadow.jsonl"))
        pol = s.propose()
        check("Phase 4：提案覆盖四层",
              set(pol["order"]) == {"0", "1", "both", "all"}, pol)

    # ── 输出 ────────────────────────────────────────────────
    print("\nPASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print("  - " + f)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
