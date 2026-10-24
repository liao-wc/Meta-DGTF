# -*- coding: utf-8 -*-
"""全流程帕累托最优先行模块（V2.2.2 第一版）。

目标：把「质量 / 成本 / 时延」统一成可比较的流程读数，并给出非支配前沿。
当前数据源：outputs/*.packed.json（真跑产物）。后续扩展：
  · app 组件：端点时延、静态资源、一次任务端到端耗时；
  · 本地模型：BGE/LLM 时延、命中率、失败率；
  · 三者联动：route/rounds/web/thinking/effort 与总质量、总成本、总时延的联合前沿。

指标口径（全部来自产物，不猜）：
  quality     0..1 综合（answer_ready / verified / standard_all / coverage / flags）
  tokens      llm_tokens（成本代理）
  calls       llm_calls（时延/成本代理）
  elapsed     产物若有 elapsed_seconds 则用之，否则 None（不插值）
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
    dt = (packed or {}).get("decision_trace") or {}
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
            # 缺失值不参与支配判断（保守：视为不可比）
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
        dominated = False
        for j, other in enumerate(rows):
            if i == j:
                continue
            if dominates(other, r, objectives):
                dominated = True
                break
        if not dominated:
            front.append(r)
    return front


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


def report(rows: List[dict]) -> dict:
    """前沿报告：前沿行 + 全局最优读数 + 推荐配置。"""
    rows = list(rows or [])
    front = pareto_frontier(rows)
    best_quality = max(rows, key=lambda r: r.get("quality", 0), default=None)
    chepeast = min(rows, key=lambda r: (r.get("tokens", 0) or 0), default=None)
    return {
        "n": len(rows),
        "frontier": [r.get("id") for r in front],
        "best_quality": best_quality,
        "cheapest": chepeast,
        "rows": rows,
        "frontier_rows": front,
    }
