# -*- coding: utf-8 -*-
"""V2 参考编排器：用确定性 mock 层执行器跑通三平面。

mock 只用于验证契约/调度/记忆闭环，不调用 LLM；生产接入时用
ExistingEngineAdapter 把真实 View/Pool 映射成同样的 LayerResult。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import (Budget, ENTRY_ORDER, LAYER_CONTRACTS, LayerResult,
                        LayerState)
from .memory import MemoryLake
from .scheduler import Action, ScheduleTrace, Scheduler, WorldState


class MockLayerExecutor:
    """确定性四层执行器：每层只交自己契约允许的产物。"""

    def execute(self, action: Action, state: WorldState) -> LayerResult:
        e = action.entry or ""
        st = state.layers[e]
        r = st.rounds + action.rounds
        if e == "0":
            return self._l0(st, r, action)
        if e == "1":
            return self._l1(st, r, action, state)
        if e == "both":
            return self._both(st, r, action, state)
        if e == "all":
            return self._all(st, r, action, state)
        raise ValueError("未知层：" + e)

    def _l0(self, st: LayerState, r: int, action: Action) -> LayerResult:
        n = min(7, 4 + r)
        aspects = [{"id": "A%d" % i, "aspect": "aspect-%d" % i,
                    "polarity": "阴" if i % 2 else "阳",
                    "novelty": round(max(0.05, 0.75 - 0.1 * i), 3),
                    "evidence": "probe-%d" % i}
                   for i in range(1, n + 1)]
        new = LayerState("0", rounds=r, novelty=min(1.0, 0.18 + 0.2 * r),
                         status=("done" if r >= 3 else "running"),
                         cost_tokens=st.cost_tokens + 900)
        return LayerResult(
            entry="0", calls=1, tokens=900,
            state=new,
            artifacts={
                "aspect_map": aspects,
                "suspensions": [
                    {"target": "A%d" % (i + 1), "reason": "结构张力，暂不消解",
                     "status": "active"} for i in range(min(2, r))
                ],
                "probe_queue": [
                    {"question": "A%d 的反面是什么？" % i} for i in range(1, 4)
                ],
                "novelty_curve": [round(0.18 + 0.2 * i, 3) for i in range(1, r + 1)],
            },
            flags=[],
            provenance=["mock:0:%d" % r],
        )

    def _l1(self, st: LayerState, r: int, action: Action,
            state: WorldState) -> LayerResult:
        answered = min(4, r * 2)
        answers = []
        for i in range(1, 5):
            if i > answered:
                break
            label = "decidable" if i <= 2 else ("partial" if i == 3 else "undecidable")
            answers.append({
                "id": "Q%d" % i,
                "question": "子问题 %d" % i,
                "label": label,
                "answer": "答案 %d（带条件）" % i,
                "citations": ["A1", "W1"] if label != "undecidable" else [],
                "confidence": 0.8 if label == "decidable" else 0.55,
            })
        coverage = answered / 4.0
        new = LayerState("1", rounds=r, coverage=coverage,
                         debt=4 - answered,
                         status=("done" if coverage >= 0.8 or r >= 2 else "running"),
                         cost_tokens=st.cost_tokens + 1500)
        tensions = [
            {"id": "T1", "claim_a": "Q1 的强结论", "claim_b": "A2 的反例",
             "severity": 0.7, "status": "open"},
            {"id": "T2", "claim_a": "Q2 的边界", "claim_b": "A5 的例外",
             "severity": 0.5, "status": "open"},
        ]
        return LayerResult(
            entry="1", calls=1, tokens=1500, state=new,
            artifacts={
                "answer_set": answers,
                "abstentions": [a for a in answers if a["label"] == "undecidable"],
                "coverage": coverage,
                "citations": [c for a in answers for c in a.get("citations", [])],
                "debt_set": [{"id": "Q%d" % i} for i in range(answered + 1, 5)],
                "tension_set": tensions,
            },
            flags=[] if coverage >= 0.8 else ["coverage_gap"],
            provenance=["mock:1:%d" % r, "anchor:A1"],
        )

    def _both(self, st: LayerState, r: int, action: Action,
              state: WorldState) -> LayerResult:
        resolved = min(2, r)
        graph = {
            "claims": [
                {"id": "C1", "text": "Q1 的强结论", "support": ["A1"]},
                {"id": "C2", "text": "A2 的反例", "support": ["A2"]},
                {"id": "C3", "text": "条件化综合", "support": ["C1", "C2"]},
            ],
            "attacks": [{"from": "C2", "to": "C1", "kind": "rebut"}],
            "defeated": ["C1"] if resolved >= 1 else [],
            "undecided": ["C2"] if resolved < 2 else [],
            "synthesis": "在条件 X 下 C1 成立；离开 X 时 C2 的反例成立。",
        }
        new = LayerState("both", rounds=r, conflicts_open=max(0, 2 - resolved),
                         status=("done" if r >= 2 else "running"),
                         cost_tokens=st.cost_tokens + 1200)
        return LayerResult(
            entry="both", calls=1, tokens=1200, state=new,
            artifacts={
                "synthesis": graph["synthesis"],
                "argument_graph": graph,
                "tension_set": [{"id": "T2", "status": "undecided"}]
                if resolved < 2 else [],
                "defeated_claims": graph["defeated"],
            },
            flags=[] if resolved >= 2 else ["open_conflict"],
            provenance=["mock:both:%d" % r, "C1", "C2"],
        )

    def _all(self, st: LayerState, r: int, action: Action,
             state: WorldState) -> LayerResult:
        closure = {
            "decision": "在条件 X 下执行方案 A；否则保留 B 作为回退。",
            "actions": [
                {"owner": "研究", "deadline": "T+1", "acceptance": "覆盖 Q1/Q2",
                 "rollback": "回到上一版答案"},
                {"owner": "对撞", "deadline": "T+1", "acceptance": "T1/T2 均有标签",
                 "rollback": "保留 undecided"},
            ],
            "not_do": ["不在证据不足时宣称确定", "不删除败方论证"],
            "residual_risks": ["A5 的例外仍未闭环"],
            "provenance": ["mock:0", "mock:1", "mock:both"],
            "confidence": 0.72,
            "what_would_change_my_mind": "出现 tier<=2 的反例锚点",
        }
        new = LayerState("all", rounds=r, status="done",
                         confidence=0.72, cost_tokens=st.cost_tokens + 900)
        return LayerResult(
            entry="all", calls=1, tokens=900, state=new,
            artifacts=closure, flags=[], provenance=closure["provenance"],
        )


@dataclass
class RunReport:
    question: str
    trace: ScheduleTrace
    closure: dict
    memory_stats: dict
    markdown: str = ""

    def to_dict(self) -> dict:
        return {"question": self.question, "trace": self.trace.to_dict(),
                "closure": self.closure, "memory": self.memory_stats}


class Orchestrator:
    def __init__(self, memory: MemoryLake | None = None,
                 executor: MockLayerExecutor | None = None,
                 scheduler: Scheduler | None = None):
        self.memory = memory or MemoryLake()
        self.executor = executor or MockLayerExecutor()
        self.scheduler = scheduler or Scheduler(self.memory)

    def run(self, question: str, *, max_tokens: int = 20000,
            max_calls: int = 12, max_rounds: int = 12) -> RunReport:
        budget = Budget(max_tokens=max_tokens, max_calls=max_calls,
                        max_rounds=max_rounds)
        trace = self.scheduler.run(self.executor, question, budget,
                                   run_id="v2-final")
        state = trace.final_state
        closure = dict(state.closure) if state else {}
        self.memory.consolidate("v2-final", min_support=2)
        md = self._markdown(question, trace, closure)
        return RunReport(question=question, trace=trace, closure=closure,
                         memory_stats=self.memory.stats(), markdown=md)

    def _markdown(self, question: str, trace: ScheduleTrace,
                  closure: dict) -> str:
        lines = ["# V2 参考运行", "", "**问题**：" + question, "",
                 trace.to_markdown(), "", "## Closure",
                 "- 决策：" + str(closure.get("decision", "（未闭合）")),
                 "- 动作：" + str(len(closure.get("actions") or [])),
                 "- 不做：" + "；".join(closure.get("not_do") or []),
                 "- 残余风险：" + "；".join(closure.get("residual_risks") or []),
                 "- 置信：" + str(closure.get("confidence", "—"))]
        return "\n".join(lines)
