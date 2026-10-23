# -*- coding: utf-8 -*-
"""V2 影子调度器：只观察，不改变 V1 执行。

在一个真实 Meta-DGTF 跑次开始/结束时，把当前层状态映射成 V2 WorldState，
记录：
  · at_start：V2 会先选哪层；与 V1 实际首层是否一致；
  · at_end：V2 在结束时还会不会继续；
  · hypothetical：用同一问题/预算在 mock 层上跑一遍 V2 参考策略；
  · priors：EML 先验（只数值，不含内容）。
"""
from __future__ import annotations

from typing import Any

from .bridge import V2MemoryBridge
from .unified_memory import UnifiedMemory
from .contracts import Budget, LayerState
from .orchestrator import MockLayerExecutor, Orchestrator
from .scheduler import Scheduler, WorldState


class _PriorsOnly:
    """只读先验：让 V2 Scheduler 读统一记忆，但绝不写回。"""

    def __init__(self, priors: dict):
        self._priors = dict(priors or {})

    def scheduler_priors(self) -> dict:
        return dict(self._priors)

    def record_outcome(self, **kwargs) -> dict:
        return {"enabled": True, "recorded": False,
                "reason": "shadow/propose 只读先验，不写记忆"}


class V2Shadow:
    def __init__(self, question: str, route: list[str], rounds: dict,
                 mode: str, config: dict, eml_path: str | None = None,
                 contract_gate: str = "warn",
                 allow_anon: bool | None = None):
        self.question = str(question or "")
        self.route = [str(x) for x in (route or [])]
        self.rounds = dict(rounds or {})
        self.mode = str(mode or "serial")
        self.config = dict(config or {})
        self.contract_gate = str(contract_gate or "warn").lower()
        # Phase 2：与 V1 的 episodes/playbook 双写；V2 只追加结构/outcome。
        _anon = (bool((config.get("scheduler") or {}).get("v2", {}).get(
            "allow_anon", False)) if allow_anon is None else bool(allow_anon))
        self.bridge = V2MemoryBridge(eml_path, enabled=True, allow_anon=_anon)
        self.memory = self.bridge.memory
        # ★ 统一记忆读路径：V1 playbook + V2 events，只读先验；写仍走 bridge。
        try:
            _pb = str(Path(self.bridge.path).parent / "playbook.jsonl")
        except Exception:
            _pb = None
        self.unified = UnifiedMemory(
            v2_events_path=self.bridge.path, playbook_path=_pb,
            allow_anon=_anon)
        cap = int((self.config.get("max_tokens") or 0) or 2_000_000)
        max_rounds = sum(int(self.rounds.get(e, 1) or 1)
                         for e in self.route) or 12
        self.start_budget = Budget(max_tokens=cap, max_calls=240,
                                   max_rounds=max(12, max_rounds))
        self.scheduler = Scheduler(_PriorsOnly(self.unified.read_priors()))
        self.at_start: dict = {}
        self.start_state: WorldState | None = None

    def _initial_state(self) -> WorldState:
        layers = {e: LayerState(e) for e in ("0", "1", "both", "all")}
        for e in self.route:
            layers[e] = LayerState(e)
        return WorldState(question=self.question, layers=layers,
                          budget=self.start_budget)

    def start(self) -> dict:
        self.start_state = self._initial_state()
        d = self.scheduler.plan(self.start_state)
        actual = self.route[0] if self.route else ""
        self.at_start = {
            "actual_first": actual,
            "v2_first": (d.action.entry if d else None),
            "agreement": bool(d and d.action.entry == actual),
            "score": round(d.score, 4) if d else None,
            "alternatives": (d.alternatives if d else []),
        }
        return self.at_start

    def _state_from_packed(self, packed: dict) -> WorldState:
        views = packed.get("views") or {}
        quality = packed.get("quality") or {}
        rounds = packed.get("rounds") or {}
        cov = quality.get("coverage")
        answered = int(quality.get("answered") or 0)
        total = int(quality.get("answerable_total") or 0)
        layers: dict[str, LayerState] = {}
        for e in ("0", "1", "both", "all"):
            v = views.get(e) or {}
            r = int(rounds.get(e, 0) or 0)
            flags = list((v.get("quality_flags") or []))
            if e == "0":
                n = len(v.get("candidates") or []) + len(v.get("amps") or [])
                st = LayerState("0", rounds=r,
                                novelty=min(1.0, n / 20.0),
                                status=("done" if v else "idle"),
                                cost_tokens=0, flags=flags)
            elif e == "1":
                st = LayerState("1", rounds=r,
                                coverage=float(cov or 0.0),
                                debt=max(0, total - answered),
                                status=("done" if v else "idle"),
                                flags=flags)
            elif e == "both":
                st = LayerState("both", rounds=r,
                                conflicts_open=len(v.get("threads") or []),
                                status=("done" if v else "idle"),
                                flags=flags)
            else:
                acts = int(quality.get("decision_actions") or 0)
                nd = int(quality.get("not_do") or 0)
                st = LayerState("all", rounds=r,
                                confidence=float(quality.get("tri_ratio") or 0.0),
                                status=("done" if v else "idle"),
                                flags=flags)
            layers[e] = st
        closure = {}
        if (int(quality.get("decision_actions") or 0) > 0
                and int(quality.get("not_do") or 0) > 0):
            closure = {"decision": "（V1 已给出动作）",
                       "actions": [{}] * int(quality.get("decision_actions") or 0),
                       "not_do": [""] * int(quality.get("not_do") or 0),
                       "residual_risks": ["（见 V1 产物）"],
                       "provenance": ["v1:packed"]}
        return WorldState(
            question=self.question, layers=layers,
            budget=Budget(max_tokens=max(1, int(packed.get("llm_tokens") or 0)),
                          max_calls=max(1, int(packed.get("llm_calls") or 0)),
                          max_rounds=max(12, sum(int(rounds.get(e, 0) or 0)
                                                 for e in ("0", "1", "both", "all")))),
            closure=closure,
        )

    def propose(self) -> dict:
        """Phase 4 的「初始串行排程」提案（不写记忆、不改执行）。

        用空记忆 + mock 层跑一遍 scheduler，得到 order/rounds；真实引擎只有在
        scheduler.v2.takeover=true 时才采用它。它不替代层内算法（Phase 5）。
        """
        from .memory import MemoryLake
        from .orchestrator import MockLayerExecutor
        from .scheduler import Scheduler
        st = self._initial_state()
        # ★ 统一记忆：V2 提案必须使用同一份 EML/V2 记忆，而不是空 MemoryLake。
        sched = Scheduler(_PriorsOnly(self.unified.read_priors()))
        tr = sched.run(MockLayerExecutor(), self.question, st.budget,
                       max_steps=12, run_id="v2-propose")
        order: list[str] = []
        rounds: dict[str, int] = {}
        for d in tr.decisions:
            e = d.action.entry
            if not e or e not in self.route:
                continue
            if e not in order:
                order.append(e)
            rounds[e] = rounds.get(e, 0) + int(d.action.rounds)
        for e in self.route:
            if e not in order:
                order.append(e)
                rounds.setdefault(e, 1)
        return {
            "order": order,
            "rounds": rounds,
            "decisions": [d.action.template() for d in tr.decisions],
            "stop": tr.stop_reason,
            "quality": round(tr.quality, 4),
            "note": "mock 初始排程；takeover 才采用，层内算法仍是 V1",
        }

    def finish(self, packed: dict, results: dict | None = None) -> dict:
        out: dict[str, Any] = {"enabled": True, "mode": self.mode,
                               "at_start": self.at_start}
        try:
            st = self._state_from_packed(packed)
            d = self.scheduler.plan(st)
            out["at_end"] = {
                "v2_next": (d.action.entry if d else None),
                "score": round(d.score, 4) if d else None,
                "reason": (d.reason if d else "已闭合/无合法动作"),
            }
        except Exception as e:
            out["at_end"] = {"error": "%s: %s" % (type(e).__name__, e)}

        # Phase 2：双写结构/outcome（只数值），再跑一次 mock 参考策略。
        try:
            out["eml"] = self.bridge.record_packed(packed)
        except Exception as e:
            out["eml"] = {"enabled": True,
                          "error": "%s: %s" % (type(e).__name__, e)}
        out["priors"] = self.unified.read_priors()
        try:
            from .core_duty import audit_packed
            out["core"] = audit_packed(packed)
        except Exception as e:
            out["core"] = {"error": "%s: %s" % (type(e).__name__, e)}
        try:
            out["contracts"] = self.bridge.contract_report(
                packed, gate=self.contract_gate)
        except Exception as e:
            out["contracts"] = {"gate": self.contract_gate,
                                "error": "%s: %s" % (type(e).__name__, e)}
        rounds = packed.get("rounds") or {}
        try:
            # hypothetical 用**副本**记忆，避免 mock 轨迹写回生产 EML。
            from .memory import MemoryLake
            _hyp_mem = MemoryLake()
            _hyp_mem.events = list(self.memory.events)
            _hyp_mem._clock = self.memory.now()
            orch = Orchestrator(_hyp_mem, MockLayerExecutor(),
                                Scheduler(_hyp_mem))
            rep = orch.run(self.question,
                           max_tokens=max(1, int(packed.get("llm_tokens") or 2_000_000)),
                           max_calls=max(1, int(packed.get("llm_calls") or 20)),
                           max_rounds=max(12, sum(int(rounds.get(e, 1) or 1)
                                                  for e in ("0", "1", "both", "all"))))
            out["hypothetical"] = {
                "decisions": [d.action.template() for d in rep.trace.decisions],
                "stop": rep.trace.stop_reason,
                "quality": round(rep.trace.quality, 4),
                "closure": bool(rep.closure.get("decision")),
                "note": "mock 参考轨迹；不是真实输出质量",
            }
        except Exception as e:
            out["hypothetical"] = {"error": "%s: %s" % (type(e).__name__, e)}
        out["note"] = "影子模式：未改变 V1 执行；hypothetical 为 mock 参考"
        return out
