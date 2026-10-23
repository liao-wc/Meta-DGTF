# -*- coding: utf-8 -*-
"""前沿机制的可离线实现：反馈质量闸、对比经验、学分分配、记忆检索权重。

参考（只取机制，不照搬实现）：
- ExpeL: 经验/洞见抽取与跨任务检索；
- Self-Refine 的警告：自反循环不是自动有益，先筛反馈质量；
- Generative Agents: recency/importance/relevance 的记忆检索权重。
"""
from __future__ import annotations
import math

_ISSUE_W = {
    "all_closure_gap": 0.9, "both_unresolved": 0.85,
    "all_residual": 0.8, "layer0_duty_short": 0.75,
    "layer1_duty_short": 0.75, "layer0_yield_low": 0.7,
    "layer1_citation_low": 0.75, "context_channel_weak": 0.8,
    "content_channel_weak": 0.6, "self_channel_noisy": 0.55,
    "both_tension_high": 0.7,
}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def score_candidate(c: dict) -> float:
    """反馈质量分：问题严重度 × 证据强度 × 来源可靠度（0..1）。"""
    c = c or {}
    issue = str((c.get("cond") or {}).get("issue") or "")
    sev = _ISSUE_W.get(issue, 0.45)
    before = (c.get("readings") or {}).get("before") or {}
    ev = 0.0
    for v in before.values():
        if isinstance(v, (int, float)):
            ev += min(1.0, abs(float(v)) / 4.0)
        elif isinstance(v, (list, tuple)):
            ev += min(1.0, len(v) / 4.0)
        elif isinstance(v, str) and v.strip():
            ev += 0.3
    ev = min(1.0, ev / 3.0) if before else 0.0
    if not before:
        return 0.0
    src = 0.85 if str(c.get("source") or "").startswith("llm") else 1.0
    act = 0.7 if (c.get("action") or {}).get("key") in (
        "rounds_delta", "carve_first") else 0.9
    return round(max(0.0, min(1.0, sev * (0.45 + 0.55 * ev) * src * act)), 4)


def rank_candidates(cands, top_k: int | None = None) -> list:
    """按质量分排序，并做 issue 去重（同一问题只留最高分一条）。"""
    scored = []
    for c in (cands or []):
        c = dict(c)
        c["confidence"] = score_candidate(c)
        scored.append(c)
    scored.sort(key=lambda x: (-float(x.get("confidence") or 0.0),
                               str((x.get("cond") or {}).get("issue") or "")))
    seen, out = set(), []
    for c in scored:
        iss = str((c.get("cond") or {}).get("issue") or "")
        if iss and iss in seen:
            continue
        seen.add(iss)
        out.append(c)
    return out[:int(top_k) if top_k else len(out)]


def retrieval_weight(recency_days: float, importance: float,
                    relevance: float, half_life: float = 14.0) -> float:
    """Generative Agents 三因子检索权重的确定性版本。"""
    rec = 0.5 ** (max(0.0, _num(recency_days)) / max(1e-6, float(half_life)))
    return round((0.4 * rec + 0.35 * min(1.0, max(0.0, _num(importance)))
                  + 0.25 * min(1.0, max(0.0, _num(relevance)))), 4)


def credit_assignment(layers: dict) -> dict:
    """把缺口按层归一成学分：缺得越多，下一轮越该补。"""
    vals = {}
    for k, v in (layers or {}).items():
        try:
            s = float(v)
        except (TypeError, ValueError):
            continue
        vals[str(k)] = round(max(0.0, 1.0 - s), 4)
    tot = sum(vals.values())
    if tot <= 0:
        return {k: 0.0 for k in vals}
    return {k: round(v / tot, 4) for k, v in vals.items()}


def process_reward(success: bool, quality: float, cost: float,
                   cost_weight: float = 0.2) -> float:
    """过程/结果混合奖励：成功与质量为主，成本只罚过量。"""
    return round((1.0 if success else 0.0) * 0.5
                 + max(0.0, min(1.0, _num(quality))) * 0.5
                 - max(0.0, _num(cost)) * float(cost_weight), 4)


__all__ = ["score_candidate", "rank_candidates", "retrieval_weight",
           "credit_assignment", "process_reward"]
