# -*- coding: utf-8 -*-
"""调度 v2：MAPE-K + 有限视界 MPC + EVOI，在契约/预算约束下选下一动作。

控制面只决定「跑哪层、几圈、何时停」，不生成内容；
知识面（EML）只喂数值先验，执行面（四层）只按契约交产物。
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Optional

from .contracts import (Budget, ENTRY_ORDER, LAYER_CONTRACTS, LayerResult,
                        LayerState, validate_result)
from .memory import MemoryLake


@dataclass(frozen=True)
class Action:
    kind: str                  # run_layer / stop
    entry: Optional[str]
    rounds: int
    reason: str = ""

    def template(self) -> str:
        return "%s:r%d" % (self.entry, self.rounds) if self.entry else "stop"


@dataclass
class Decision:
    action: Action
    score: float
    evoi: float
    cost: float
    reason: str
    alternatives: list[dict] = field(default_factory=list)


@dataclass
class WorldState:
    question: str
    layers: dict[str, LayerState]
    budget: Budget
    aspects: list = field(default_factory=list)
    answers: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    argument_graph: dict = field(default_factory=dict)
    closure: dict = field(default_factory=dict)
    results: list[LayerResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def clone(self) -> "WorldState":
        return copy.deepcopy(self)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "layers": {k: v.to_dict() for k, v in self.layers.items()},
            "budget": self.budget.to_dict(),
            "aspects_n": len(self.aspects),
            "answers_n": len(self.answers),
            "conflicts_n": len(self.conflicts),
            "closure": dict(self.closure),
            "notes": list(self.notes),
        }


@dataclass
class ScheduleTrace:
    decisions: list[Decision] = field(default_factory=list)
    results: list[LayerResult] = field(default_factory=list)
    stop_reason: str = ""
    quality: float = 0.0
    priors: dict = field(default_factory=dict)
    final_state: Optional[WorldState] = None

    def to_dict(self) -> dict:
        return {
            "decisions": [
                {"action": d.action.template(), "kind": d.action.kind,
                 "entry": d.action.entry, "rounds": d.action.rounds,
                 "score": round(d.score, 5), "evoi": round(d.evoi, 5),
                 "cost": round(d.cost, 5), "reason": d.reason}
                for d in self.decisions],
            "results": [r.to_dict() for r in self.results],
            "stop_reason": self.stop_reason,
            "quality": round(self.quality, 4),
            "priors": self.priors,
            "final_state": self.final_state.to_dict() if self.final_state else {},
        }

    def to_markdown(self) -> str:
        lines = ["## V2 调度轨迹", ""]
        for i, d in enumerate(self.decisions, 1):
            lines.append("%d. **%s**  score=%.3f  evoi=%.3f  cost=%.3f  — %s"
                         % (i, d.action.template(), d.score, d.evoi,
                            d.cost, d.reason))
        lines += ["", "**停止**：%s" % (self.stop_reason or "—"),
                  "**质量**：%.3f" % self.quality]
        return "\n".join(lines)


class Scheduler:
    """有限视界控制器；策略参数全部可解释、可回放。"""

    VALUES = {"0": 0.9, "1": 1.3, "both": 1.5, "all": 1.8}
    FALLBACK_TOKENS = {"0": 900, "1": 1500, "both": 1200, "all": 900}

    def __init__(self, memory: MemoryLake, *, target_coverage: float = 0.8,
                 horizon: int = 2, seed: int = 7):
        self.memory = memory
        self.target_coverage = float(target_coverage)
        self.horizon = int(horizon)
        self.seed = int(seed)
        self._rng = __import__("random").Random(self.seed)

    # ── Monitor / Analyze ────────────────────────────────────
    def monitor(self, state: WorldState) -> dict:
        l0 = state.layers["0"]
        l1 = state.layers["1"]
        both = state.layers["both"]
        return {
            "novelty": l0.novelty,
            "coverage": l1.coverage,
            "coverage_gap": max(0.0, self.target_coverage - l1.coverage),
            "conflicts_open": len(state.conflicts),
            "debt": l1.debt,
            "closure_ready": bool(state.closure),
            "budget_ratio": (state.budget.spent_tokens /
                             max(1, state.budget.max_tokens)),
            "both_rounds": both.rounds,
        }

    def analyze(self, state: WorldState) -> list[str]:
        m = self.monitor(state)
        flags: list[str] = []
        if m["novelty"] < 0.25 and state.layers["0"].status != "done":
            flags.append("novelty_stall")
        if m["coverage_gap"] > 0.05 and state.layers["1"].status != "done":
            flags.append("coverage_gap")
        if m["conflicts_open"] > 0 and state.layers["both"].status != "done":
            flags.append("open_conflict")
        if state.layers["both"].status == "done" and not state.closure:
            flags.append("closure_missing")
        if m["budget_ratio"] > 0.85:
            flags.append("budget_low")
        return flags

    # ── Plan ─────────────────────────────────────────────────
    def _priors(self, entry: str, rounds: int) -> dict:
        key = "%s:r%d" % (entry, rounds)
        return (self.memory.scheduler_priors().get("templates") or {}).get(key, {})

    def _cost(self, entry: str, rounds: int) -> float:
        p = self._priors(entry, rounds)
        tok = float(p.get("mean_tokens") or self.FALLBACK_TOKENS.get(entry, 1000))
        return max(0.1, tok * max(1, rounds) / 1000.0)

    def _p_change(self, entry: str, state: WorldState) -> float:
        if entry == "0":
            st = state.layers["0"]
            return max(0.0, min(1.0, (0.55 - st.novelty) * 1.8))
        if entry == "1":
            st = state.layers["1"]
            gap = max(0.0, self.target_coverage - st.coverage)
            debt = min(1.0, st.debt / 4.0)
            return max(0.0, min(1.0, gap * 1.5 + debt * 0.5))
        if entry == "both":
            return min(1.0, len(state.conflicts) / 3.0)
        if entry == "all":
            return 1.0 if not state.closure else 0.0
        return 0.0

    def _explore(self, entry: str, rounds: int) -> float:
        p = self._priors(entry, rounds)
        n = int(p.get("n") or 0)
        return 0.18 / math.sqrt(n + 1.0)

    def _score(self, action: Action, state: WorldState) -> tuple[float, float, float]:
        entry = action.entry or ""
        if action.kind == "stop" or not entry:
            return 0.0, 0.0, 0.0
        p = self._p_change(entry, state)
        v = self.VALUES.get(entry, 1.0)
        cost = self._cost(entry, action.rounds)
        evoi = p * v
        score = evoi / (cost + 0.2) + self._explore(entry, action.rounds)
        return score, evoi, cost

    def _legal(self, state: WorldState) -> list[Action]:
        out: list[Action] = []
        for entry in ENTRY_ORDER:
            st = state.layers[entry]
            if st.status == "done":
                continue
            # 依赖：1 至少要吃到一个 0 圈；both 要 0/1 都完成；all 要 both 完成。
            if entry == "1" and state.layers["0"].rounds < 1:
                continue
            if entry == "both":
                if state.layers["0"].status != "done" or state.layers["1"].status != "done":
                    continue
            if entry == "all" and state.layers["both"].status != "done":
                continue
            for r in (1, 2):
                if st.rounds + r > 4:
                    continue
                if not state.budget.can(1, int(self._cost(entry, r) * 1000), r):
                    continue
                out.append(Action("run_layer", entry, r, ""))
        return out

    def _simulate(self, state: WorldState, action: Action) -> WorldState:
        s = state.clone()
        e = action.entry or ""
        st = s.layers[e]
        st.rounds += action.rounds
        if e == "0":
            st.novelty = min(1.0, st.novelty + 0.22 * action.rounds)
            st.status = "done" if st.rounds >= 3 else "running"
        elif e == "1":
            st.coverage = min(1.0, st.coverage + 0.28 * action.rounds)
            st.debt = max(0, st.debt - action.rounds)
            st.status = "done" if st.coverage >= self.target_coverage else "running"
        elif e == "both":
            st.conflicts_open = max(0, st.conflicts_open - action.rounds)
            st.status = "done" if st.rounds >= 2 else "running"
        elif e == "all":
            st.status = "done"
            s.closure = {"decision": "simulated", "actions": [],
                         "not_do": [], "residual_risks": [],
                         "provenance": ["simulated"]}
        return s

    def _mpc(self, state: WorldState, action: Action, depth: int) -> float:
        score, _evoi, _cost = self._score(action, state)
        if depth <= 1:
            return score
        s2 = self._simulate(state, action)
        best_next = 0.0
        for a2 in self._legal(s2):
            best_next = max(best_next, self._score(a2, s2)[0])
        return score + 0.75 * best_next

    def plan(self, state: WorldState) -> Optional[Decision]:
        legal = self._legal(state)
        if not legal:
            return None
        scored = []
        for a in legal:
            score, evoi, cost = self._score(a, state)
            mpc = self._mpc(state, a, self.horizon)
            scored.append((mpc, score, evoi, cost, a))
        scored.sort(key=lambda x: (-x[0], x[4].template()))
        best = scored[0]
        alts = [{"action": x[4].template(), "score": round(x[0], 4),
                 "evoi": round(x[2], 4)} for x in scored[:4]]
        reasons = []
        if best[4].entry == "0":
            reasons.append("novelty/方面覆盖不足")
        elif best[4].entry == "1":
            reasons.append("覆盖率缺口/债务")
        elif best[4].entry == "both":
            reasons.append("存在未裁决张力")
        elif best[4].entry == "all":
            reasons.append("前三层已可闭合")
        if state.budget.spent_tokens:
            reasons.append("EVOI/成本")
        return Decision(best[4], best[0], best[2], best[3],
                        "；".join(reasons), alts)

    # ── Execute / Learn ──────────────────────────────────────
    def _absorb(self, state: WorldState, result: LayerResult) -> None:
        a = result.artifacts or {}
        e = result.entry
        state.layers[e] = result.state
        if e == "0":
            state.aspects = list(a.get("aspect_map") or [])
        elif e == "1":
            state.answers = list(a.get("answer_set") or [])
            t = a.get("tension_set") or []
            if t:
                state.conflicts = list(t)
        elif e == "both":
            state.argument_graph = dict(a.get("argument_graph") or {})
            state.conflicts = list(a.get("tension_set") or [])
        elif e == "all":
            state.closure = dict(a)
        state.results.append(result)

    def quality(self, state: WorldState) -> float:
        cov = float(state.layers["1"].coverage)
        total = max(1, len(state.conflicts))
        open_n = int(state.layers["both"].conflicts_open)
        conflict = 1.0 - min(1.0, open_n / total)
        closure = 1.0 if (state.closure.get("decision")
                          and state.closure.get("actions")
                          and state.closure.get("not_do")
                          and state.closure.get("residual_risks")
                          and state.closure.get("provenance")) else 0.0
        flags = sum(len(s.flags) for s in state.layers.values())
        q = 0.5 * cov + 0.2 * conflict + 0.3 * closure - 0.02 * flags
        return max(0.0, min(1.0, q))

    def run(self, executor, question: str, budget: Budget,
            max_steps: int = 12, run_id: str = "v2-run") -> ScheduleTrace:
        states = {e: LayerState(e) for e in ENTRY_ORDER}
        state = WorldState(question=question, layers=states, budget=budget)
        trace = ScheduleTrace(priors=self.memory.scheduler_priors())
        stop = ""
        for _ in range(max_steps):
            flags = self.analyze(state)
            if flags:
                state.notes = flags
            decision = self.plan(state)
            if decision is None:
                if all(state.layers[e].status == "done" for e in ENTRY_ORDER):
                    stop = "四层均已完成"
                else:
                    stop = "无合法动作（依赖/预算/层状态阻断）"
                break
            action = decision.action
            trace.decisions.append(decision)
            result = executor.execute(action, state)
            validate_result(LAYER_CONTRACTS[action.entry], result)
            if not state.budget.can(result.calls, result.tokens, action.rounds):
                stop = "预算不足，拒绝执行：" + action.template()
                break
            state.budget.spend(result.calls, result.tokens, action.rounds)
            self._absorb(state, result)
            trace.results.append(result)
            q = self.quality(state)
            self.memory.record_outcome(
                run_id=run_id,
                template=action.template(), quality=q,
                calls=result.calls, tokens=result.tokens,
                success=(state.layers[action.entry].status == "done"))
            if all(state.layers[e].status == "done" for e in ENTRY_ORDER):
                stop = "四层均已完成"
                break
            if state.budget.remaining()["calls"] <= 0:
                stop = "调用预算耗尽"
                break
        trace.stop_reason = stop or "达到步数上限"
        trace.quality = self.quality(state)
        trace.final_state = state
        trace.priors = self.memory.scheduler_priors()
        return trace
