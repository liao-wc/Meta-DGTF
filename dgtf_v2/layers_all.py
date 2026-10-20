# -*- coding: utf-8 -*-
"""F2 · all 元层 ClosurePackage。

all 的职责是闭合，不是生成新内容：
- decision/actions/not_do/residual_risks/provenance/confidence 六件套；
- 动作四字段 owner/deadline/acceptance/rollback；
- 允许从 1 层继承 actions/not_do，但必须标 origin，不能冒充 all 原生；
- 缺项记 gap，不补空话。
"""
from __future__ import annotations

from dataclasses import dataclass, field

ACTION_FIELDS = ("owner", "deadline", "acceptance", "rollback")
SIX = ("decision", "actions", "not_do", "residual_risks",
       "provenance", "confidence")


@dataclass
class ClosurePackage:
    decision: str = ""
    actions: list = field(default_factory=list)
    not_do: list = field(default_factory=list)
    residual_risks: list = field(default_factory=list)
    provenance: list = field(default_factory=list)
    confidence: float = 0.0
    confidence_source: str = ""
    orientation: str = ""
    actions_expected: bool = True
    actions_origin: str = "all"
    not_do_origin: str = "all"
    gaps: list = field(default_factory=list)
    action_quality: dict = field(default_factory=dict)
    closure_completeness: float = 0.0
    risk_transparency: float = 0.0
    ok: bool = False

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "actions": self.actions,
            "not_do": self.not_do,
            "residual_risks": self.residual_risks,
            "provenance": self.provenance,
            "confidence": round(float(self.confidence), 4),
            "confidence_source": self.confidence_source,
            "orientation": self.orientation,
            "actions_expected": self.actions_expected,
            "actions_origin": self.actions_origin,
            "not_do_origin": self.not_do_origin,
            "gaps": self.gaps,
            "action_quality": self.action_quality,
            "closure_completeness": round(float(self.closure_completeness), 4),
            "risk_transparency": round(float(self.risk_transparency), 4),
            "ok": self.ok,
        }


def _norm_actions(raw: list) -> list:
    out = []
    for a in raw or []:
        if not isinstance(a, dict):
            continue
        b = dict(a)
        b.setdefault("owner", a.get("owner_role") or a.get("owner") or "")
        b.setdefault("deadline", a.get("deadline_hint") or a.get("deadline") or "")
        b.setdefault("rollback", a.get("fallback") or a.get("rollback") or "")
        b.setdefault("acceptance", a.get("acceptance") or "")
        out.append(b)
    return out


def assemble_closure(all_view: dict, research_view: dict | None = None,
                     quality: dict | None = None,
                     orientation: str | None = None) -> ClosurePackage:
    """从已有 all/1 产物组装闭合包；不生成新句子。

    boundary profile：边界题不要求行动闭环，actions/not_do 可为空；
    decision/未知取向仍按六件套要求。
    """
    av = all_view or {}
    rv = research_view or {}
    q = quality or {}
    pkg = ClosurePackage()
    pkg.orientation = str(orientation or q.get("orientation") or "").lower()
    pkg.actions_expected = pkg.orientation != "boundary"

    pkg.decision = str(av.get("decision") or "").strip()
    if not pkg.decision:
        dp = av.get("decidable_product")
        if isinstance(dp, dict):
            pkg.decision = str(dp.get("answer") or "").strip()
        elif dp:
            pkg.decision = str(dp).strip()
    if not pkg.decision:
        pkg.decision = str(av.get("manifest") or "").strip()[:400]

    pkg.actions = _norm_actions(av.get("actions") or [])
    if not pkg.actions:
        rdp = rv.get("decidable_product")
        r_acts = (rv.get("_actions")
                  or (rdp.get("actions") if isinstance(rdp, dict) else None)
                  or [])
        pkg.actions = _norm_actions(r_acts)
        if pkg.actions:
            pkg.actions_origin = "1"

    pkg.not_do = list(av.get("not_do") or [])
    if not pkg.not_do:
        rdp = rv.get("decidable_product")
        pkg.not_do = list(rv.get("_not_do")
                          or (rdp.get("not_do") if isinstance(rdp, dict) else None)
                          or [])
        if pkg.not_do:
            pkg.not_do_origin = "1"

    pkg.residual_risks = [(str(x.get("desc") or "") if isinstance(x, dict)
                          else str(x))
                          for x in (av.get("residual_risks")
                                    or av.get("threads") or [])]
    pkg.provenance = list(av.get("provenance") or ["v1:packed"])
    # 置信：优先 all 自带；三态可靠时用 tri；不可靠时用 coverage 代理并标源。
    if av.get("confidence"):
        pkg.confidence = float(av.get("confidence"))
        pkg.confidence_source = "all"
    elif q.get("tri_reliable") and q.get("tri_ratio"):
        pkg.confidence = float(q.get("tri_ratio"))
        pkg.confidence_source = "tri_alpha_reliable"
    elif q.get("coverage"):
        pkg.confidence = float(q.get("coverage"))
        pkg.confidence_source = "coverage_proxy"
    else:
        pkg.confidence = 0.0
        pkg.confidence_source = "none"

    # 动作四字段
    good_actions = 0
    missing_fields = {}
    for i, a in enumerate(pkg.actions):
        miss = [f for f in ACTION_FIELDS if not str(a.get(f) or "").strip()]
        if miss:
            missing_fields["A%d" % (i + 1)] = miss
        else:
            good_actions += 1
    pkg.action_quality = {
        "total": len(pkg.actions),
        "complete": good_actions,
        "missing": missing_fields,
    }

    present = 0
    _denom = 0
    for k in SIX:
        if not pkg.actions_expected and k in ("actions", "not_do"):
            continue
        _denom += 1
        v = getattr(pkg, k)
        if k == "confidence":
            if float(v or 0) > 0:
                present += 1
        elif v:
            present += 1
    pkg.closure_completeness = present / float(_denom or 1)
    if pkg.actions_expected:
        pkg.risk_transparency = (1.0 if pkg.not_do and pkg.residual_risks
                                 else 0.5 if (pkg.not_do or pkg.residual_risks)
                                 else 0.0)
    else:
        pkg.risk_transparency = (1.0 if pkg.residual_risks
                                 else 0.0)

    if not pkg.decision:
        pkg.gaps.append("缺 decision")
    if pkg.actions_expected:
        if not pkg.actions:
            pkg.gaps.append("缺 actions")
        elif good_actions != len(pkg.actions):
            pkg.gaps.append("动作四字段不全 %d/%d" % (good_actions,
                                                    len(pkg.actions)))
        if not pkg.not_do:
            pkg.gaps.append("缺 not_do")
    if not pkg.residual_risks:
        pkg.gaps.append("缺 residual_risks")
    if not pkg.provenance:
        pkg.gaps.append("缺 provenance")
    if float(pkg.confidence or 0) <= 0:
        pkg.gaps.append("缺 confidence")
    if pkg.closure_completeness < 1.0:
        pkg.gaps.append("六件套不全 %.2f" % pkg.closure_completeness)
    pkg.ok = not pkg.gaps
    return pkg


def validate_closure(pkg: ClosurePackage) -> None:
    if not pkg.ok:
        raise ValueError("ClosurePackage 不合规：" + "；".join(pkg.gaps))
