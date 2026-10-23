# -*- coding: utf-8 -*-
"""V2 层契约：四层各做什么、不许做什么、何时算完成。

这是 V2 三平面架构里「执行面」的接口定义。它不依赖 LLM，也不改 V1 引擎；
生产接入时由 adapter 把现有 View/Pool 映射成 LayerResult。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ContractViolation(Exception):
    """层交出的产物违反职责契约。"""


@dataclass(frozen=True)
class LayerContract:
    entry: str
    name: str
    objective: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    forbidden: tuple[str, ...]
    exit_tests: tuple[str, ...]
    quality_metrics: tuple[str, ...]
    handoff: str


LAYER_CONTRACTS: dict[str, LayerContract] = {
    "0": LayerContract(
        entry="0",
        name="修行 · 发散",
        objective="把问题的潜在方面摊开；不回答、不裁决、不闭合。",
        inputs=("question", "anchor", "aspect_priors"),
        outputs=("aspect_map", "suspensions", "probe_queue", "novelty_curve"),
        forbidden=("answer", "decision", "closure", "final_claim"),
        exit_tests=("novelty_stall", "heaps_saturation", "budget_exhausted"),
        quality_metrics=("aspect_coverage", "novelty_rate", "suspension_quality"),
        handoff="把 aspect_map / suspensions 交给 1 与 both；不得替它们下结论。",
    ),
    "1": LayerContract(
        entry="1",
        name="研究 · 收敛",
        objective="对可判定子问题给出带不确定性的答案；弃权合法，不许编证据。",
        inputs=("question", "anchor", "aspect_map", "evidence"),
        outputs=("answer_set", "abstentions", "coverage", "citations", "debt_set"),
        forbidden=("closure", "action_plan", "final_decision", "fabricated_citation"),
        exit_tests=("coverage_target", "all_answerable_resolved", "budget_exhausted"),
        quality_metrics=("coverage", "tri_state_calibration", "citation_precision"),
        handoff="把 answer_set / abstentions / debt_set 交给 both；冲突不许自行抹平。",
    ),
    "both": LayerContract(
        entry="both",
        name="对撞 · 辩证",
        objective="把 0 的方面与 1 的答案放在同一论证场里，消解或明确保留张力。",
        inputs=("aspect_map", "answer_set", "conflict_set", "anchor"),
        outputs=("synthesis", "argument_graph", "tension_set", "defeated_claims"),
        forbidden=("final_decision", "action_plan", "delete_defeated", "forced_winner"),
        exit_tests=("all_conflicts_labeled", "synthesis_cites_both_sides", "budget_exhausted"),
        quality_metrics=("conflict_resolution", "argument_groundedness", "synthesis_novelty"),
        handoff="把 synthesis / argument_graph（含 defeated/undecided）交给 all；败方不删。",
    ),
    "all": LayerContract(
        entry="all",
        name="元 · 闭合",
        objective="做决策级闭合：决策、行动、不做、残余风险、来源与置信；不重写前层内容。",
        inputs=("aspect_map", "answer_set", "argument_graph", "synthesis", "quality_readings"),
        outputs=("decision", "actions", "not_do", "residual_risks", "provenance", "confidence"),
        forbidden=("new_content", "rewrite_layers", "delete_flags", "fabricate_closure"),
        exit_tests=("four_artifacts_present", "high_flags_resolved_or_accepted", "budget_exhausted"),
        quality_metrics=("closure_completeness", "action_quality", "risk_transparency"),
        handoff="交付 ClosurePackage；缺项写 undecided，不补空话。",
    ),
}

ENTRY_ORDER = ("0", "1", "both", "all")


@dataclass
class LayerState:
    entry: str
    rounds: int = 0
    novelty: float = 0.0
    coverage: float = 0.0
    conflicts_open: int = 0
    debt: int = 0
    confidence: float = 0.0
    cost_tokens: int = 0
    status: str = "idle"          # idle / running / done / blocked
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entry": self.entry,
            "rounds": self.rounds,
            "novelty": round(float(self.novelty), 4),
            "coverage": round(float(self.coverage), 4),
            "conflicts_open": int(self.conflicts_open),
            "debt": int(self.debt),
            "confidence": round(float(self.confidence), 4),
            "cost_tokens": int(self.cost_tokens),
            "status": self.status,
            "flags": list(self.flags),
        }


@dataclass
class Budget:
    max_tokens: int
    max_calls: int
    max_rounds: int
    spent_tokens: int = 0
    spent_calls: int = 0
    spent_rounds: int = 0

    def can(self, calls: int = 1, tokens: int = 1, rounds: int = 1) -> bool:
        return (self.spent_calls + calls <= self.max_calls
                and self.spent_tokens + tokens <= self.max_tokens
                and self.spent_rounds + rounds <= self.max_rounds)

    def spend(self, calls: int, tokens: int, rounds: int) -> None:
        self.spent_calls += int(calls)
        self.spent_tokens += int(tokens)
        self.spent_rounds += int(rounds)

    def remaining(self) -> dict:
        return {
            "calls": max(0, self.max_calls - self.spent_calls),
            "tokens": max(0, self.max_tokens - self.spent_tokens),
            "rounds": max(0, self.max_rounds - self.spent_rounds),
        }

    def to_dict(self) -> dict:
        return {
            "max_tokens": self.max_tokens,
            "max_calls": self.max_calls,
            "max_rounds": self.max_rounds,
            "spent_tokens": self.spent_tokens,
            "spent_calls": self.spent_calls,
            "spent_rounds": self.spent_rounds,
            "remaining": self.remaining(),
        }


@dataclass
class LayerResult:
    entry: str
    artifacts: dict
    state: LayerState
    calls: int
    tokens: int
    flags: list[str] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entry": self.entry,
            "artifacts": self.artifacts,
            "state": self.state.to_dict(),
            "calls": int(self.calls),
            "tokens": int(self.tokens),
            "flags": list(self.flags),
            "provenance": list(self.provenance),
        }


def _has(obj: dict, path: str) -> bool:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return cur is not None


def validate_result(contract: LayerContract, result: LayerResult) -> None:
    """执行面的硬闸：缺输出、越权、删败方、空闭合都判 ContractViolation。"""
    if result.entry != contract.entry:
        raise ContractViolation(f"entry 不符：{result.entry} != {contract.entry}")
    art = result.artifacts or {}
    for key in contract.outputs:
        if key not in art:
            raise ContractViolation(f"{contract.name} 缺输出：{key}")
    for key in contract.forbidden:
        if key in art:
            raise ContractViolation(f"{contract.name} 越权输出：{key}")
    if contract.entry == "0":
        if not isinstance(art.get("aspect_map"), list) or not art["aspect_map"]:
            raise ContractViolation("0 层的 aspect_map 不能为空")
        if art.get("answer") or art.get("decision"):
            raise ContractViolation("0 层不许给答案/决策")
    elif contract.entry == "1":
        answers = art.get("answer_set") or []
        if not isinstance(answers, list):
            raise ContractViolation("1 层的 answer_set 必须是列表")
        for a in answers:
            if a.get("label") == "decidable" and not a.get("citations"):
                raise ContractViolation("1 层 decidable 答案必须带 citations")
            if a.get("label") not in ("decidable", "partial", "undecidable"):
                raise ContractViolation("1 层三态标签非法：%r" % (a.get("label"),))
        if "coverage" not in art or not (0.0 <= float(art["coverage"]) <= 1.0):
            raise ContractViolation("1 层 coverage 必须在 [0,1]")
    elif contract.entry == "both":
        graph = art.get("argument_graph") or {}
        if "defeated" not in graph or "undecided" not in graph:
            raise ContractViolation("both 层论证图必须显式保留 defeated/undecided")
        if not art.get("synthesis"):
            raise ContractViolation("both 层缺 synthesis")
    elif contract.entry == "all":
        acts = art.get("actions") or []
        if not acts:
            raise ContractViolation("all 层 actions 不能为空")
        for a in acts:
            for f in ("owner", "deadline", "acceptance", "rollback"):
                if not a.get(f):
                    raise ContractViolation(f"all 层动作缺 {f}：{a!r}")
        if not art.get("not_do"):
            raise ContractViolation("all 层必须显式写 not_do")
        if not art.get("residual_risks"):
            raise ContractViolation("all 层必须显式写 residual_risks")
        if not art.get("provenance"):
            raise ContractViolation("all 层必须带 provenance")


def legal_actions(states: dict[str, LayerState], budget: Budget,
                  max_rounds_per_layer: int = 4) -> list[tuple[str, int]]:
    """返回 (entry, rounds) 的合法动作；只做契约/预算/依赖检查。"""
    out: list[tuple[str, int]] = []
    for entry in ENTRY_ORDER:
        st = states.get(entry) or LayerState(entry)
        if st.status == "done":
            continue
        if entry == "1":
            if (states.get("0") or LayerState("0")).rounds < 1:
                continue
        if entry == "both":
            if (states.get("0") or LayerState("0")).status != "done":
                continue
            if (states.get("1") or LayerState("1")).status != "done":
                continue
        if entry == "all":
            if (states.get("both") or LayerState("both")).status != "done":
                continue
        for r in (1, 2):
            if st.rounds + r <= max_rounds_per_layer and budget.can(1, 1, r):
                out.append((entry, r))
    return out
