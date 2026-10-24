# -*- coding: utf-8 -*-
"""M4 质量预测器：用历史 packed 训练轻量 ridge 回归，减少级联触发。

纯 Python 实现（项目主环境无 numpy/sklearn）：
  · 特征：问题结构特征 + route 层数 + 平均圈数 + web + 模式 one-hot；
  · 标签：pareto_flow 的 quality 综合分（0..1）；
  · 训练：标准化 + ridge 闭式解（高斯消元）；
  · 推理：加载 dgtf_memory/quality_predictor.json，clamp 到 0..1。
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

FEATURES = ["len", "blank", "why", "fact", "meta", "multi", "choice",
            "how", "what", "short", "route_n", "rounds_avg", "web",
            "hist_calls_med", "hist_tokens_k", "hist_tri_rate", "hist_cut_rate",
            "mode_B", "mode_serial", "mode_fast", "mode_web", "mode_other"]
MODEL_PATH_DEFAULT = "dgtf_memory/quality_predictor.json"


def _f(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def mode_bucket(mode: str) -> str:
    m = str(mode or "").strip().upper()
    if m == "B":
        return "B"
    if m == "SERIAL" or m == "":
        return "serial"
    if m == "FAST":
        return "fast"
    if m in ("WEB", "SERIAL+WEB"):
        return "web"
    return "other"


def question_features(question: str) -> dict:
    """从题面抽与 _auto_features 同口径的特征（轻量近似，供 App/M4 预测）。"""
    q = str(question or "").strip()
    why = any(k in q for k in ("为什么", "为何", "原因", "机制"))
    meta = any(k in q for k in ("本身", "自身", "递归", "元", "整体", "到底"))
    fact = bool(q) and (not why) and (not any(
        k in q for k in ("应该", "如何", "怎么", "怎样", "是否", "还是",
                         "选择", "决定", "方案", "建议", "为什么")))
    return {
        "len": len(q),
        "blank": not q,
        "why": why,
        "fact": fact,
        "meta": meta,
        "multi": (q.count("，") + q.count(",")) >= 3,
        "choice": ("或" in q) or ("还是" in q),
        "how": any(k in q for k in ("如何", "怎样", "怎么")),
        "what": any(k in q for k in ("是什么", "为什么")),
        "short": 0 < len(q) <= 40,
    }


def featurize(features: dict, route_n: int = 4, rounds_avg: float = 2.0,
              web: bool = False, mode: str = "other",
              history: Optional[dict] = None) -> Dict[str, float]:
    f = features or {}
    h = history or {}
    mb = mode_bucket(mode)
    out = {
        "len": _f(f.get("len")),
        "blank": _f(f.get("blank")),
        "why": _f(f.get("why")),
        "fact": _f(f.get("fact")),
        "meta": _f(f.get("meta")),
        "multi": _f(f.get("multi")),
        "choice": _f(f.get("choice")),
        "how": _f(f.get("how")),
        "what": _f(f.get("what")),
        "short": _f(f.get("short")),
        "hist_calls_med": _f(h.get("calls_med")),
        "hist_tokens_k": _f(h.get("tokens_med")) / 1000.0,
        "hist_tri_rate": _f(h.get("tri_rate")),
        "hist_cut_rate": _f(h.get("cut_rate")),
        "route_n": _f(route_n, 4),
        "rounds_avg": _f(rounds_avg, 2),
        "web": 1.0 if web else 0.0,
        "mode_B": 1.0 if mb == "B" else 0.0,
        "mode_serial": 1.0 if mb == "serial" else 0.0,
        "mode_fast": 1.0 if mb == "fast" else 0.0,
        "mode_web": 1.0 if mb == "web" else 0.0,
        "mode_other": 1.0 if mb == "other" else 0.0,
    }
    return out


def _standardize(rows: List[Dict[str, float]], stats=None):
    if stats is None:
        stats = {}
        for k in FEATURES:
            vals = [_f(r.get(k)) for r in rows]
            mu = sum(vals) / len(vals) if vals else 0.0
            var = sum((v - mu) ** 2 for v in vals) / len(vals) if vals else 0.0
            stats[k] = (mu, math.sqrt(var) or 1.0)
    X = []
    for r in rows:
        X.append([(_f(r.get(k)) - stats[k][0]) / stats[k][1] for k in FEATURES])
    return X, stats


def _solve(A, b):
    """高斯消元解 A x = b（A 需可逆；带 ridge 保证）。"""
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            continue
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= pv
        for r in range(n):
            if r == col:
                continue
            fac = M[r][col]
            if fac:
                for j in range(col, n + 1):
                    M[r][j] -= fac * M[col][j]
    return [M[i][n] for i in range(n)]


def fit(rows: List[dict], y: List[float], lam: float = 1.0) -> dict:
    feat_rows = []
    for r in rows:
        if isinstance(r, dict) and ("_features" in r or "_route_n" in r):
            feat_rows.append(featurize(
                r.get("_features") or {},
                int(_f(r.get("_route_n"), 4)),
                _f(r.get("_rounds_avg"), 2),
                bool(r.get("_web")),
                str(r.get("_mode") or "other"),
                r.get("_history") or {}))
        else:
            feat_rows.append(r or {})
    Xs, stats = _standardize(feat_rows)
    n = len(FEATURES) + 1
    A = [[0.0] * n for _ in range(n)]
    b = [0.0] * n
    for x, t in zip(Xs, y):
        xx = [1.0] + x
        for i in range(n):
            b[i] += xx[i] * t
            for j in range(n):
                A[i][j] += xx[i] * xx[j]
    for i in range(1, n):
        A[i][i] += lam
    coef = _solve(A, b)
    return {"features": FEATURES,
            "mean": {k: stats[k][0] for k in FEATURES},
            "std": {k: stats[k][1] for k in FEATURES},
            "coef": coef[1:],
            "intercept": coef[0],
            "lambda": lam}


def predict(model: dict, features: dict, route_n=4, rounds_avg=2.0,
            web=False, mode="other", history=None) -> float:
    f = featurize(features, route_n, rounds_avg, web, mode, history)
    z = _f(model.get("intercept"))
    coef = model.get("coef") or []
    mean = model.get("mean") or {}
    std = model.get("std") or {}
    for i, k in enumerate(model.get("features") or FEATURES):
        if i >= len(coef):
            break
        v = (_f(f.get(k)) - _f(mean.get(k))) / (_f(std.get(k), 1.0) or 1.0)
        z += coef[i] * v
    return max(0.0, min(1.0, z))


def evaluate(model: dict, rows: List[dict], y: List[float]) -> dict:
    preds = [predict(model, r.get("_features") or {},
                     int(r.get("_route_n") or 4),
                     _f(r.get("_rounds_avg"), 2),
                     bool(r.get("_web")),
                     str(r.get("_mode") or "other"),
                     r.get("_history") or {}) for r in rows]
    n = len(y)
    if not n:
        return {"n": 0}
    mae = sum(abs(p - t) for p, t in zip(preds, y)) / n
    mu = sum(y) / n
    ss_tot = sum((t - mu) ** 2 for t in y) or 1e-9
    ss_res = sum((t - p) ** 2 for p, t in zip(preds, y))
    return {"n": n, "mae": round(mae, 4),
            "r2": round(1.0 - ss_res / ss_tot, 4),
            "pred_min": round(min(preds), 3),
            "pred_max": round(max(preds), 3)}


def load_model(path: str) -> Optional[dict]:
    try:
        p = Path(path)
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
        # 回退到仓库内随代码分发的模型（dgtf_memory 不入库时可复现）
        alt = Path(__file__).with_name("quality_predictor_model.json")
        if alt.is_file():
            return json.loads(alt.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def save_model(model: dict, path: str) -> bool:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(model, ensure_ascii=False, indent=1),
                     encoding="utf-8")
        return True
    except Exception:
        return False
