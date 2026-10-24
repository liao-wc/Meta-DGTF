# -*- coding: utf-8 -*-
"""全流程帕累托最优先行模块（V2.2.2 第一版；Round 2 扩展预算选档与联动快照）。

目标：把「质量 / 成本 / 时延」统一成可比较的流程读数，并给出非支配前沿。
数据源：outputs/*.packed.json（引擎真跑）+ 本机 App/BGE 端点读数（组件快照）。

指标口径（产物直读，不猜）：
  quality     0..1 综合（answer_ready / verified / standard_all / coverage / flags）
  tokens      llm_tokens（成本代理）；calls llm_calls（时延/成本代理）
  elapsed     产物有 elapsed_seconds 才用，否则 None。

预算选档：
  recommend(rows, budget_tokens=..., min_quality=...)
    · 满足质量下限且成本不超预算的行里，选质量最高（同质量选 tokens 更少）；
    · 无满足项时：先退「满足质量的最便宜」，再退「预算内质量最高」，最后全局最佳；
    · 返回原因，便于审计（不静默换算法）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

#: 目标：质量越大越好；tokens/calls 越小越好。
OBJECTIVES = (("quality", "max"), ("tokens", "min"), ("calls", "min"))


def _as_float(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _quality_score(packed: dict, metrics: dict) -> float:
    q = (packed or {}).get("quality") or {}
    answer_ready = bool(metrics.get("answer_ready"))
    quality = str(metrics.get("answer_quality") or "")
    standard_all = bool(metrics.get("standard_all"))
    coverage = metrics.get("coverage")
    flags = metrics.get("flags") or []
    score = 0.0
    score += 0.35 if answer_ready else 0.0
    score += 0.25 if quality == "verified" else (0.10 if quality else 0.0)
    score += 0.20 if standard_all else 0.0
    if isinstance(coverage, (int, float)):
        score += 0.10 * max(0.0, min(1.0, float(coverage)))
    score += 0.10 * max(0.0, 1.0 - 0.10 * len(flags))
    return round(min(1.0, score), 4)


def extract_flow_metrics(packed: dict) -> dict:
    """从单个 packed 产物抽流程指标（幂等、只读）。"""
    p = packed or {}
    q = p.get("quality") or {}
    dt = p.get("decision_trace") or {}
    led = p.get("process_ledger") or {}
    rounds = p.get("rounds") or {}
    api = p.get("api_usage") or {}
    m = {
        "id": str(p.get("id") or ""),
        "question": str(p.get("question") or "")[:80],
        "route": list(p.get("route") or []),
        "rounds": dict(rounds) if isinstance(rounds, dict) else {},
        "answer_ready": bool(dt.get("answer_ready") if "answer_ready" in dt
                             else q.get("answer_ready")),
        "process_ready": bool(dt.get("process_ready") if "process_ready" in dt
                              else q.get("process_ready")),
        "answer_quality": str(dt.get("answer_quality")
                              or q.get("answer_quality") or ""),
        "coverage": q.get("coverage") if isinstance(q.get("coverage"), (int, float)) else None,
        "standard_all": bool(led.get("standard_all")),
        "flags": list(q.get("flags") or []),
        "tokens": int(p.get("llm_tokens") or 0),
        "calls": int(p.get("llm_calls") or 0),
        "web_enabled": bool(api.get("web_enabled")),
        "tools_calls": int(api.get("tools_calls") or 0),
        "elapsed": _as_float(p.get("elapsed_seconds"), None)
        if p.get("elapsed_seconds") is not None else None,
    }
    m["quality"] = _quality_score(p, m)
    return m


def dominates(a: dict, b: dict, objectives=OBJECTIVES) -> bool:
    """a 支配 b：所有目标不差，且至少一个严格更好。"""
    better = False
    for key, direction in objectives:
        av = a.get(key)
        bv = b.get(key)
        if av is None or bv is None:
            if av is None and bv is None:
                continue
            return False
        if direction == "max":
            if av < bv:
                return False
            if av > bv:
                better = True
        else:
            if av > bv:
                return False
            if av < bv:
                better = True
    return better


def pareto_frontier(rows: Iterable[dict], objectives=OBJECTIVES) -> List[dict]:
    """返回非支配行（保留输入顺序）。"""
    rows = [r for r in (rows or []) if r]
    front = []
    for i, r in enumerate(rows):
        if not any(dominates(other, r, objectives)
                   for j, other in enumerate(rows) if i != j):
            front.append(r)
    return front


def recommend(rows: Iterable[dict], budget_tokens: Optional[int] = None,
              min_quality: Optional[float] = None) -> dict:
    """预算/质量约束下的选档（返回 row + reason）。"""
    rows = [r for r in (rows or []) if r]
    if not rows:
        return {"row": None, "reason": "无可用真跑行"}
    budget = None if budget_tokens in (None, 0, "") else int(budget_tokens)
    qmin = None if min_quality in (None, "") else float(min_quality)

    def _ok(r):
        return ((budget is None or int(r.get("tokens") or 0) <= budget)
                and (qmin is None or float(r.get("quality") or 0) >= qmin))

    feasible = [r for r in rows if _ok(r)]
    if feasible:
        best = max(feasible, key=lambda r: (float(r.get("quality") or 0),
                                            -int(r.get("tokens") or 0)))
        return {"row": best, "reason": "满足预算与质量下限，质量最高"}
    if qmin is not None:
        above = [r for r in rows if float(r.get("quality") or 0) >= qmin]
        if above:
            best = min(above, key=lambda r: (int(r.get("tokens") or 0),
                                             -float(r.get("quality") or 0)))
            return {"row": best, "reason": "无满足预算候选，退为满足质量下限的最便宜档"}
        best = max(rows, key=lambda r: float(r.get("quality") or 0))
        return {"row": best, "reason": "无满足质量下限候选，退为全局质量最高档"}
    if budget is not None:
        under = [r for r in rows if int(r.get("tokens") or 0) <= budget]
        if under:
            best = max(under, key=lambda r: float(r.get("quality") or 0))
            return {"row": best, "reason": "预算内质量最高档"}
        best = min(rows, key=lambda r: int(r.get("tokens") or 0))
        return {"row": best, "reason": "无预算内候选，退为最便宜档"}
    best = max(rows, key=lambda r: float(r.get("quality") or 0))
    return {"row": best, "reason": "无约束：质量最高档"}


def load_packed_runs(paths: Iterable) -> List[dict]:
    """读取 packed 文件列表，返回指标行（坏文件跳过）。"""
    out = []
    for p in paths or []:
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(d, dict):
            row = extract_flow_metrics(d)
            if not row.get("id"):
                row["id"] = Path(p).stem
            out.append(row)
    return out


def report(rows: List[dict], budget_tokens: Optional[int] = None,
           min_quality: Optional[float] = None) -> dict:
    """前沿报告：前沿行 + 全局最优读数 + 预算推荐。"""
    rows = list(rows or [])
    front = pareto_frontier(rows)
    best_quality = max(rows, key=lambda r: r.get("quality", 0), default=None)
    cheapest = min(rows, key=lambda r: (r.get("tokens", 0) or 0), default=None)
    rec = recommend(rows, budget_tokens=budget_tokens, min_quality=min_quality)
    return {
        "n": len(rows),
        "frontier": [r.get("id") for r in front],
        "best_quality": best_quality,
        "cheapest": cheapest,
        "recommend": rec,
        "rows": rows,
        "frontier_rows": front,
    }


def joint_snapshot(engine_report: dict, app: Optional[dict] = None,
                   local: Optional[dict] = None) -> dict:
    """三组件联动快照：引擎前沿 + App/本地模型端点读数（只读，不猜）。"""
    return {
        "engine": {
            "n": engine_report.get("n"),
            "frontier": engine_report.get("frontier"),
            "recommend": engine_report.get("recommend"),
        },
        "app": app or {},
        "local": local or {},
        "note": "app/local 为单实例快照；联合前沿需同一配置下的多轮 A/B 才可排序",
    }
