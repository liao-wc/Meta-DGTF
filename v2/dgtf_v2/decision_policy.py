# -*- coding: utf-8 -*-
"""V1/V2 决策仲裁（控制面策略）+ 回滚与事故留痕。

纯确定性：不调 LLM、不联网、不读系统时钟、不用随机数。
只仲裁「层顺序 / 圈数 / 停止」，不改层内算法与产物内容。

四种模式：
  shadow   V2 提案只记录，执行 = V1 原样（零行为差）。
  advisory V2 提案作为非绑定建议附在 packed，执行 = V1 原样。
  takeover V2 提案通过四层硬约束 + 安全否决后接管 order/rounds；
           被否决 ⇒ 回退 V1，事故留痕；连续否决达阈值 ⇒ 粘性回滚 V1 auto_plan。
  joint    V2 只能在 V1 计划内收紧：order 取 V2（不合法则 V1）、
           rounds 取 min(V1, V2)、stop 取先到者；不触发粘性回滚。

四层硬约束（对 V2 提案与接管后的生效计划成立）：
  H1 层集合不可改：order 必须是 route 的排列（禁止增层/删层/重复/未知层）。
  H2 依赖顺序    ：先决层必须排在前面（0 → 1 → both → all）。
  H3 圈数边界    ：每层 1..cap，总圈数 ≤ max_total_rounds。
  H4 边界停止    ：stop 只允许层/跑次边界代码（不做逐圈 replan）。
  H5 无内容接管  ：提案/元数据不得携带答案正文类字段（answer/decision/rendered/...）。
安全否决：
  anon_v2（测试或匿名 run 不得接管）、contract_block（执行面契约未过不接控制面）、
  budget_exhausted / budget_guard（预算已尽或预计超支）。
V1 是权威基线：任何模式都不静默改 V1 计划；V1 自身违规只留痕（v1_noncanonical）。
回滚保真：回滚后 effective 逐字等于 V1 提案。

packed 可序列化：Policy.to_packed() 只含 primitives，可 json.dumps；
Policy.from_packed() 可恢复回滚状态与事故记录（回滚演练可复现）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

ENTRY_ORDER = ("0", "1", "both", "all")
PREREQ = {"0": (), "1": ("0",), "both": ("0", "1"), "all": ("both",)}
MODES = ("shadow", "advisory", "takeover", "joint")
ALLOWED_STOP_CODES = ("", "four_layers_done", "budget_low",
                      "budget_exhausted", "no_legal_action", "closed")
STOP_ALIASES = {
    "四层均已完成": "four_layers_done",
    "无合法动作（依赖/预算/层状态阻断）": "no_legal_action",
    "预算不足": "budget_low",
    "预算耗尽": "budget_exhausted",
    "已闭合/无合法动作": "closed",
}
CONTENT_KEYS = frozenset({
    "answer", "answer_text", "final_answer", "decision", "decision_text",
    "rendered", "output", "output_text", "claim", "claims", "content",
    "text", "text_body", "manifest", "manifest_text", "synthesis",
})
TEST_RUN_PREFIXES = ("E2E_", "test", "smoke", "pytest", "v2-", "probe", "anon")
TOKENS_PER_ROUND = {"0": 12000, "1": 14000, "both": 12000, "all": 11000}
CALLS_PER_ROUND = 8
HARD_CODES = ("H1_", "H2_", "H3_", "H4_", "H5_")


# ── 数据结构 ────────────────────────────────────────────────
@dataclass(frozen=True)
class Proposal:
    """一个平面给出的排程提案（只含控制面字段）。"""
    source: str
    order: tuple = ()
    rounds: dict = field(default_factory=dict)
    stop: str = ""
    quality: float = 0.0
    run_id: str = ""
    decisions: tuple = ()
    meta: dict = field(default_factory=dict)
    content_keys: tuple = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", str(self.source or ""))
        object.__setattr__(self, "order",
                           tuple(str(x) for x in (self.order or ())))
        object.__setattr__(self, "rounds",
                           {str(k): v for k, v in dict(self.rounds or {}).items()})
        object.__setattr__(self, "decisions",
                           tuple(str(x)[:80] for x in (self.decisions or ())))
        object.__setattr__(self, "meta", dict(self.meta or {}))
        object.__setattr__(self, "content_keys",
                           tuple(str(x) for x in (self.content_keys or ())))

    @property
    def content_free(self) -> bool:
        return not self.content_keys

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "order": list(self.order),
            "rounds": dict(self.rounds),
            "stop": self.stop,
            "quality": round(float(self.quality or 0.0), 4),
            "run_id": self.run_id,
            "decisions": list(self.decisions),
            "meta": dict(self.meta),
            "content_free": self.content_free,
            "content_keys": list(self.content_keys),
        }


def _scan_content(obj: Any, path: str = "") -> list[str]:
    """递归找「答案正文类」键；只认键名，不猜内容。返回点路径列表。"""
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = ("%s.%s" % (path, k)) if path else str(k)
            if str(k).lower() in CONTENT_KEYS:
                found.append(p)
            found.extend(_scan_content(v, p))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            found.extend(_scan_content(v, "%s[%d]" % (path, i)))
    return found


def proposal_from_engine(*, order, rounds, stop: str = "", quality: float = 0.0,
                         run_id: str = "", source: str = "v1",
                         decisions=(), meta: Optional[dict] = None) -> Proposal:
    """由引擎的 order/rounds（或 V2Shadow.propose 的返回）构造提案。"""
    return Proposal(source=source, order=tuple(order or ()),
                    rounds=dict(rounds or {}), stop=str(stop or ""),
                    quality=float(quality or 0.0), run_id=str(run_id or ""),
                    decisions=tuple(decisions or ()), meta=dict(meta or {}))


def _as_proposal(x: Any, source: str) -> Proposal:
    if isinstance(x, Proposal):
        return x
    if not isinstance(x, dict):
        raise TypeError("提案必须是 Proposal 或 dict，收到 %r" % (type(x).__name__,))
    raw = dict(x)
    removed = _scan_content(raw, "")
    clean = _strip_content(raw)
    known = ("order", "rounds", "stop", "quality", "run_id",
             "decisions", "meta")
    meta = dict(clean.get("meta") or {})
    for k, v in clean.items():
        if k not in known and isinstance(v, (int, float, str, bool)):
            meta.setdefault(k, v)
    return Proposal(source=str(clean.get("source") or source),
                    order=tuple(clean.get("order") or ()),
                    rounds=dict(clean.get("rounds") or {}),
                    stop=str(clean.get("stop") or ""),
                    quality=float(clean.get("quality") or 0.0),
                    run_id=str(clean.get("run_id") or ""),
                    decisions=tuple(clean.get("decisions") or ()),
                    meta=meta, content_keys=tuple(removed))


def _strip_content(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_content(v) for k, v in obj.items()
                if str(k).lower() not in CONTENT_KEYS}
    if isinstance(obj, (list, tuple)):
        return [_strip_content(v) for v in obj]
    return obj


@dataclass(frozen=True)
class Veto:
    code: str
    detail: str = ""
    severity: str = "hard"

    def to_dict(self) -> dict:
        return {"code": self.code, "detail": self.detail,
                "severity": self.severity}


@dataclass
class Incident:
    """一次裁决的留痕（只存代码与读数，不存任何正文）。"""
    seq: int
    mode: str
    policy: str
    action: str
    reason: str
    veto_codes: tuple
    order: tuple
    rounds: dict
    stop: str
    ts: Optional[float] = None

    def to_dict(self) -> dict:
        return {"seq": self.seq, "mode": self.mode, "policy": self.policy,
                "action": self.action, "reason": str(self.reason)[:200],
                "veto_codes": list(self.veto_codes), "order": list(self.order),
                "rounds": dict(self.rounds), "stop": self.stop,
                "ts": self.ts}


# ── 硬约束（H1–H5）──────────────────────────────────────────
def normalize_stop(stop: Any) -> str:
    s = str(stop or "").strip()
    if not s:
        return ""
    if s in ALLOWED_STOP_CODES:
        return s
    if s in STOP_ALIASES:
        return STOP_ALIASES[s]
    return ""


def check_hard_constraints(prop: Proposal, *, route, rounds_cap: Optional[dict] = None,
                           max_total_rounds: Optional[int] = None) -> list[Veto]:
    """H1–H5。返回 hard veto 列表（空 = 通过）。"""
    out: list[Veto] = []
    route = tuple(str(x) for x in (route or ENTRY_ORDER))
    order = list(prop.order)
    rounds = dict(prop.rounds or {})

    # H1 层集合不可改
    if not order:
        out.append(Veto("H1_empty_order", "order 为空"))
    seen: set = set()
    dups: list = []
    unknown: list = []
    for e in order:
        if e not in ENTRY_ORDER:
            unknown.append(e)
        if e in seen:
            dups.append(e)
        seen.add(e)
    if unknown:
        out.append(Veto("H1_unknown_layer", ",".join(unknown[:4])))
    if dups:
        out.append(Veto("H1_duplicate_layer", ",".join(dups[:4])))
    if set(order) != set(route):
        missing = [e for e in route if e not in seen]
        extra = [e for e in order if e not in route]
        out.append(Veto("H1_route_mismatch",
                        "missing=%s extra=%s" % (missing, extra)))

    # H2 依赖顺序
    idx = {}
    for i, e in enumerate(order):
        idx.setdefault(e, i)
    for e in order:
        for p in PREREQ.get(e, ()):
            if p in route and p in idx and idx[p] > idx.get(e, len(order)):
                out.append(Veto("H2_dependency_order", "%s 必须早于 %s" % (p, e)))

    # H3 圈数边界
    caps = dict(rounds_cap or {})
    total = 0
    bad = False
    for e in route:
        if e not in rounds:
            out.append(Veto("H3_missing_rounds", e))
            bad = True
            continue
        r = rounds[e]
        if isinstance(r, bool) or not isinstance(r, (int, float)) or int(r) != r:
            out.append(Veto("H3_bad_rounds", "%s=%r" % (e, r)))
            bad = True
            continue
        ri = int(r)
        if ri < 1:
            out.append(Veto("H3_rounds_below_1", "%s=%d" % (e, ri)))
            bad = True
        elif e in caps and ri > int(caps[e]):
            out.append(Veto("H3_rounds_over_cap",
                            "%s=%d>%d" % (e, ri, int(caps[e]))))
            bad = True
        total += ri
    for e in rounds:
        if e not in route:
            out.append(Veto("H3_rounds_extra_layer", e))
            bad = True
    if (not bad and max_total_rounds is not None
            and total > int(max_total_rounds)):
        out.append(Veto("H3_total_rounds_over",
                        "%d>%d" % (total, int(max_total_rounds))))

    # H4 边界停止（只查接管模式会采纳的代码；自由文本按 soft 处理）
    raw_stop = str(prop.stop or "").strip()
    if raw_stop and not normalize_stop(raw_stop):
        pass  # 交 stop_soft_veto() 判 soft，不阻断 V1 基线

    # H5 无内容接管
    if not prop.content_free:
        out.append(Veto("H5_content_field", ",".join(prop.content_keys[:4])))
    return out


def stop_soft_veto(prop: Proposal) -> list[Veto]:
    raw = str(prop.stop or "").strip()
    if raw and not normalize_stop(raw):
        return [Veto("H4_stop_not_code", raw[:40], severity="soft")]
    return []


# ── 安全否决 ────────────────────────────────────────────────
def estimate_tokens(rounds: dict) -> int:
    total = 0
    for e, r in (rounds or {}).items():
        try:
            total += int(r) * int(TOKENS_PER_ROUND.get(str(e), 10000))
        except (TypeError, ValueError):
            continue
    return total


def estimate_calls(rounds: dict) -> int:
    total = 0
    for _e, r in (rounds or {}).items():
        try:
            total += int(r) * CALLS_PER_ROUND
        except (TypeError, ValueError):
            continue
    return total


def check_safety(prop: Proposal, *, state: Optional[dict] = None,
                 budget: Optional[dict] = None, allow_anon: bool = False,
                 projection: Optional[dict] = None) -> list[Veto]:
    """安全否决：匿名/测试 run、契约未过、预算闸。"""
    out: list[Veto] = []
    state = dict(state or {})
    budget = dict(budget or {})

    if not allow_anon:
        rid = str(prop.run_id or "")
        low = rid.lower()
        if (not rid) or any(low.startswith(p.lower()) for p in TEST_RUN_PREFIXES):
            out.append(Veto("safe_anon_run", "run_id=%r" % rid[:40]))

    if state.get("contract_ok") is False:
        out.append(Veto("safe_contract_block",
                        "执行面契约未过，先修执行面再动控制面"))

    if state.get("v2_failure_streak") is not None:
        try:
            if int(state.get("v2_failure_streak") or 0) >= 3:
                out.append(Veto("safe_v2_failure_streak",
                                "V2 连续失败 >=3，禁止接管"))
        except (TypeError, ValueError):
            pass

    proj_tok = (float(projection.get("tokens") or 0) if projection
                else float(estimate_tokens(prop.rounds)))
    proj_calls = (float(projection.get("calls") or 0) if projection
                  else float(estimate_calls(prop.rounds)))
    max_tok = float(budget.get("max_tokens") or 0)
    spent_tok = float(budget.get("spent_tokens") or 0)
    max_calls = float(budget.get("max_calls") or 0)
    spent_calls = float(budget.get("spent_calls") or 0)
    if max_tok > 0:
        rem = max_tok - spent_tok
        if rem <= 0:
            out.append(Veto("safe_budget_exhausted", "tokens 已用尽"))
        elif proj_tok > rem * 0.95:
            out.append(Veto("safe_budget_guard",
                            "预计 %d > 剩余 %d×0.95" % (int(proj_tok), int(rem))))
    if max_calls > 0:
        rem = max_calls - spent_calls
        if rem <= 0:
            out.append(Veto("safe_budget_exhausted_calls", "calls 已用尽"))
        elif proj_calls > rem * 0.95:
            out.append(Veto("safe_budget_guard_calls",
                            "预计 %d > 剩余 %d×0.95" % (int(proj_calls), int(rem))))
    return out


# ── 策略 ────────────────────────────────────────────────────
class DecisionPolicy:
    """确定性的 V1/V2 仲裁器。一个实例 = 一个跑次（或一条实验链）的策略状态。"""

    VERSION = "decision_policy/v1"

    def __init__(self, mode: str = "shadow", *, route=None,
                 rounds_cap: Optional[dict] = None,
                 max_total_rounds: Optional[int] = None,
                 allow_anon: bool = False, fallback_limit: int = 2,
                 token_budget: Optional[int] = None,
                 calls_budget: Optional[int] = None):
        m = str(mode or "shadow").lower()
        if m not in MODES:
            raise ValueError("未知模式 %r，可选 %s" % (mode, MODES))
        self.mode = m
        self.route = tuple(str(x) for x in (route or ENTRY_ORDER))
        self.rounds_cap = {str(k): int(v) for k, v in (rounds_cap or {}).items()}
        self.max_total_rounds = (int(max_total_rounds)
                                 if max_total_rounds is not None else None)
        self.allow_anon = bool(allow_anon)
        self.fallback_limit = max(1, int(fallback_limit))
        self.token_budget = (int(token_budget)
                             if token_budget is not None else None)
        self.calls_budget = (int(calls_budget)
                             if calls_budget is not None else None)
        self._incidents: list[Incident] = []
        self._seq = 0
        self._fallback_streak = 0
        self._rolled_back = False

    # ── 只读状态 ────────────────────────────────────────────
    @property
    def rolled_back(self) -> bool:
        return bool(self._rolled_back)

    @property
    def fallback_streak(self) -> int:
        return int(self._fallback_streak)

    def default_budget(self) -> dict:
        return {"max_tokens": self.token_budget or 0, "spent_tokens": 0,
                "max_calls": self.calls_budget or 0, "spent_calls": 0}

    def incidences(self) -> list[dict]:
        return [i.to_dict() for i in self._incidents]

    def stats(self) -> dict:
        by_action: dict[str, int] = {}
        for i in self._incidents:
            by_action[i.action] = by_action.get(i.action, 0) + 1
        return {"decisions": len(self._incidents),
                "by_action": dict(sorted(by_action.items())),
                "fallbacks": int(by_action.get("fallback_v1", 0)
                                 + by_action.get("joint_fallback_v1", 0)),
                "rollbacks": int(by_action.get("rollback", 0)),
                "rolled_back": self.rolled_back,
                "fallback_streak": self.fallback_streak}

    # ── 裁决 ────────────────────────────────────────────────
    def decide(self, v1: Any, v2: Any, *, state: Optional[dict] = None,
               budget: Optional[dict] = None,
               projection: Optional[dict] = None,
               ts: Optional[float] = None) -> dict:
        v1p = _as_proposal(v1, "v1")
        v2p = _as_proposal(v2, "v2")
        v1_issues = check_hard_constraints(
            v1p, route=self.route, rounds_cap=self.rounds_cap,
            max_total_rounds=self.max_total_rounds)
        v1_noncanonical = bool(v1_issues) or bool(stop_soft_veto(v1p))

        hard = check_hard_constraints(
            v2p, route=self.route, rounds_cap=self.rounds_cap,
            max_total_rounds=self.max_total_rounds)
        safety = check_safety(v2p, state=state,
                              budget=(budget if budget is not None
                                      else self.default_budget()),
                              allow_anon=self.allow_anon,
                              projection=projection)
        soft = stop_soft_veto(v2p)
        blocking = list(hard) + list(safety)
        all_vetoes = list(hard) + list(safety) + list(soft)
        advisories: list[dict] = []
        if v1_noncanonical:
            advisories.append({"code": "v1_noncanonical",
                               "detail": "V1 基线自身不满足硬约束；只留痕，不静默改",
                               "issues": [v.to_dict() for v in v1_issues]})

        effective = v1p
        action = "shadow"
        policy = "v1_with_v2_shadow"
        if self.rolled_back:
            action, policy = "rollback_hold", "v1_auto_plan_rollback"
            advisories.append({"code": "rollback_hold",
                               "detail": "已粘性回滚 V1 auto_plan；需显式 reentry"})
        elif self.mode == "shadow":
            action, policy = "shadow", "v1_with_v2_shadow"
        elif self.mode == "advisory":
            action, policy = "advisory", "v2_advisory"
            advisories.extend({"code": v.code, "detail": v.detail,
                               "severity": v.severity} for v in all_vetoes)
            advisories.append({"code": "advisory_only",
                               "detail": "V2 提案不改执行"})
        elif self.mode == "takeover":
            if blocking:
                self._fallback_streak += 1
                action, policy = "fallback_v1", "v1_auto_plan"
                if self._fallback_streak >= self.fallback_limit:
                    self._rolled_back = True
                    action, policy = "rollback", "v1_auto_plan_rollback"
            else:
                self._fallback_streak = 0
                action, policy = "takeover", "v2_takeover"
                rounds = {}
                for e in v2p.order:
                    try:
                        rounds[e] = max(1, int(v2p.rounds.get(e, 1)))
                    except (TypeError, ValueError):
                        rounds[e] = 1
                effective = Proposal(source="v2", order=tuple(v2p.order),
                                     rounds=rounds,
                                     stop=normalize_stop(v2p.stop),
                                     quality=v2p.quality, run_id=v2p.run_id,
                                     decisions=v2p.decisions, meta=v2p.meta)
        else:  # joint
            if blocking:
                action, policy = "joint_fallback_v1", "joint_v1_only"
                advisories.extend({"code": v.code, "detail": v.detail,
                                   "severity": v.severity} for v in all_vetoes)
            else:
                action, policy = "joint", "joint_v1_v2"
                rounds = {}
                for e in self.route:
                    try:
                        rv1 = max(1, int(v1p.rounds.get(e, 1)))
                    except (TypeError, ValueError):
                        rv1 = 1
                    try:
                        rv2 = max(1, int(v2p.rounds.get(e, 1)))
                    except (TypeError, ValueError):
                        rv2 = rv1
                    r = min(rv1, rv2)
                    rounds[e] = r
                    if rv2 > rv1:
                        advisories.append({"code": "joint_rounds_capped",
                                           "layer": e, "v1": rv1, "v2": rv2})
                effective = Proposal(
                    source="joint", order=tuple(v2p.order), rounds=rounds,
                    stop=(v1p.stop or normalize_stop(v2p.stop)),
                    quality=min(float(v1p.quality or 0.0),
                                float(v2p.quality or 0.0)),
                    run_id=v1p.run_id, decisions=v2p.decisions, meta={})
        changed = _differs(effective, v1p)
        reason = _reason(action, policy, blocking, soft)
        inc = self._record(mode=self.mode, policy=policy, action=action,
                           reason=reason, vetoes=all_vetoes,
                           effective=effective, ts=ts)
        return {
            "version": self.VERSION,
            "mode": self.mode,
            "policy": policy,
            "action": action,
            "effective": _plan_dict(effective),
            "changed": bool(changed),
            "v1": v1p.to_dict(),
            "v2": v2p.to_dict(),
            "hard_ok": not hard,
            "vetoes": [v.to_dict() for v in all_vetoes],
            "advisories": advisories,
            "rollback": ({"rolled_back": True, "to": "v1_auto_plan",
                          "fallback_streak": self._fallback_streak,
                          "fallback_limit": self.fallback_limit}
                         if self._rolled_back else None),
            "incident": inc.to_dict(),
            "serializable": True,
        }

    # ── 回滚 / 重入 ─────────────────────────────────────────
    def reset(self, *, reentry_ok: bool = False) -> dict:
        """回滚后重入。必须显式 reentry_ok=True（表示已重跑门禁）。"""
        if not reentry_ok:
            raise ValueError("回滚重入需显式 reentry_ok=True（需重跑 G0–G7）")
        was = self._rolled_back
        self._rolled_back = False
        self._fallback_streak = 0
        self._seq += 1
        self._incidents.append(Incident(
            seq=self._seq, mode=self.mode, policy="reentry",
            action="reentry", reason="显式重入", veto_codes=(),
            order=tuple(self.route), rounds={}, stop="", ts=None))
        return {"rolled_back": False, "was_rolled_back": was,
                "fallback_streak": 0}

    # ── 留痕 / 序列化 ───────────────────────────────────────
    def _record(self, *, mode: str, policy: str, action: str, reason: str,
                vetoes, effective: Proposal, ts: Optional[float]) -> Incident:
        self._seq += 1
        inc = Incident(seq=self._seq, mode=mode, policy=policy, action=action,
                       reason=reason,
                       veto_codes=tuple(v.code for v in vetoes),
                       order=tuple(effective.order),
                       rounds=dict(effective.rounds),
                       stop=effective.stop,
                       ts=(float(ts) if ts is not None else None))
        self._incidents.append(inc)
        return inc

    def to_packed(self) -> dict:
        """回滚状态 + 事故留痕的 packed 块（纯 primitives，json 可序列化）。"""
        return {
            "version": self.VERSION,
            "mode": self.mode,
            "route": list(self.route),
            "rounds_cap": dict(self.rounds_cap),
            "max_total_rounds": self.max_total_rounds,
            "allow_anon": self.allow_anon,
            "fallback_limit": self.fallback_limit,
            "token_budget": self.token_budget,
            "calls_budget": self.calls_budget,
            "rolled_back": self.rolled_back,
            "fallback_streak": self.fallback_streak,
            "stats": self.stats(),
            "incidents": [i.to_dict() for i in self._incidents],
            "contains_content": False,
        }

    @classmethod
    def from_packed(cls, data: dict) -> "DecisionPolicy":
        d = dict(data or {})
        pol = cls(str(d.get("mode") or "shadow"),
                  route=d.get("route") or ENTRY_ORDER,
                  rounds_cap=d.get("rounds_cap") or {},
                  max_total_rounds=d.get("max_total_rounds"),
                  allow_anon=bool(d.get("allow_anon")),
                  fallback_limit=int(d.get("fallback_limit") or 2),
                  token_budget=d.get("token_budget"),
                  calls_budget=d.get("calls_budget"))
        pol._rolled_back = bool(d.get("rolled_back"))
        pol._fallback_streak = int(d.get("fallback_streak") or 0)
        for row in d.get("incidents") or []:
            try:
                pol._incidents.append(Incident(
                    seq=int(row.get("seq") or 0),
                    mode=str(row.get("mode") or ""),
                    policy=str(row.get("policy") or ""),
                    action=str(row.get("action") or ""),
                    reason=str(row.get("reason") or ""),
                    veto_codes=tuple(row.get("veto_codes") or ()),
                    order=tuple(row.get("order") or ()),
                    rounds=dict(row.get("rounds") or {}),
                    stop=str(row.get("stop") or ""),
                    ts=row.get("ts")))
                pol._seq = max(pol._seq, int(row.get("seq") or 0))
            except (TypeError, ValueError):
                continue
        return pol


# ── 小工具 ──────────────────────────────────────────────────
def _plan_dict(p: Proposal) -> dict:
    return {"order": list(p.order), "rounds": dict(p.rounds),
            "stop": p.stop}


def _differs(a: Proposal, b: Proposal) -> bool:
    return (tuple(a.order) != tuple(b.order)
            or _rounds_cmp(a.rounds) != _rounds_cmp(b.rounds)
            or str(a.stop) != str(b.stop))


def _rounds_cmp(rounds: dict) -> dict:
    out = {}
    for k, v in (rounds or {}).items():
        try:
            out[str(k)] = int(v)
        except (TypeError, ValueError):
            out[str(k)] = v
    return out


def _reason(action: str, policy: str, blocking, soft) -> str:
    codes = ",".join(v.code for v in blocking[:4])
    if action == "takeover":
        return "V2 提案通过 H1–H5 与安全否决，接管 order/rounds"
    if action == "joint":
        return "joint：V2 order 生效，rounds 在 V1 计划内收紧"
    if action == "rollback":
        return "连续否决达阈值 ⇒ 粘性回滚 V1 auto_plan（%s）" % codes
    if action == "fallback_v1":
        return "V2 提案被否决 ⇒ 回退 V1 auto_plan（%s）" % codes
    if action == "joint_fallback_v1":
        return "V2 提案被否决 ⇒ joint 只用 V1（%s）" % codes
    if action == "advisory":
        return "V2 仅作非绑定建议；执行 = V1"
    if action == "rollback_hold":
        return "处于粘性回滚态；执行 = V1 auto_plan"
    return "V2 只记录，不改变执行"
