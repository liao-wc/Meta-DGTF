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


def fit_knn(rows: List[dict], y: List[float], k: int = 5,
            weights: Optional[List[float]] = None) -> dict:
    """k 近邻回归（纯 Python，小样本更稳；与 ridge 同特征）。"""
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
    return {"kind": "knn", "k": int(k), "features": FEATURES,
            "mean": {k: stats[k][0] for k in FEATURES},
            "std": {k: stats[k][1] for k in FEATURES},
            "X": Xs, "y": [float(v) for v in y],
            "w": [float(w) for w in (weights or [1.0] * len(y))]}


def _z_vector(model: dict, f: dict, history) -> List[float]:
    """标准化特征向量（kNN 与 ridge 共用）。

    [Round 4] 两处工程护栏，防止 OOD 输入把预测带塌：
      ① hist_* 缺失（history 为空）⇒ 用训练均值填补（z=0），而不是当 0 值；
      ② z 截断到 ±3 温莎化 —— App 侧历史读数口径与训练分布的
         `_auto_dispatch._history` 不同（实测 tokens_med/cut_rate 的 z 可达 ±20），
         不截断时 kNN 会挑到最远邻居、把预测拉到 0.1（2026-10-25 实测）。
    """
    mean = model.get("mean") or {}
    std = model.get("std") or {}
    hist_missing = not history
    zs: List[float] = []
    for k in model.get("features") or FEATURES:
        v = _f(f.get(k))
        zz = (v - _f(mean.get(k))) / (_f(std.get(k), 1.0) or 1.0)
        if hist_missing and str(k).startswith("hist_"):
            zz = 0.0
        # OOD（|z|>3）按均值填补，而不是截断到边界 —— 截断到 ±3 仍会把邻居
        # 拉到分布极端（实测仍塌到 0.1）；拒绝外推才是稳健做法。
        if abs(zz) > 3.0:
            zz = 0.0
        zs.append(zz)
    return zs


def predict_knn(model: dict, features: dict, route_n=4, rounds_avg=2.0,
                web=False, mode="other", history=None) -> float:
    f = featurize(features, route_n, rounds_avg, web, mode, history)
    x = _z_vector(model, f, history)
    X = model.get("X") or []
    y = model.get("y") or []
    if not X:
        return 0.0
    ds = []
    for i, row in enumerate(X):
        d = 0.0
        for a, b in zip(x, row):
            d += (a - b) ** 2
        ds.append((d, i))
    ds.sort(key=lambda z: z[0])
    kk = max(1, min(int(model.get("k") or 5), len(ds)))
    near = ds[:kk]
    ws = model.get("w") or []
    wsum = 0.0
    acc = 0.0
    for d, i in near:
        w = (float(ws[i]) if i < len(ws) else 1.0) / (1.0 + d)
        acc += w * y[i]
        wsum += w
    return max(0.0, min(1.0, acc / wsum)) if wsum else 0.0


def predict(model: dict, features: dict, route_n=4, rounds_avg=2.0,
            web=False, mode="other", history=None) -> float:
    if model.get("kind") == "knn":
        return predict_knn(model, features, route_n, rounds_avg, web, mode, history)
    f = featurize(features, route_n, rounds_avg, web, mode, history)
    z = _f(model.get("intercept"))
    coef = model.get("coef") or []
    x = _z_vector(model, f, history)
    for i, k in enumerate(model.get("features") or FEATURES):
        if i >= len(coef):
            break
        z += coef[i] * x[i]
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


# ── Conformal 保形下界（2026-10-25，Round 2）────────────────────────────
# 动机：M4 的 point prediction 只能排序，不能回答「切这一档会不会掉质量」。
# 做法：K-fold 交叉验证残差 residual = actual - oof_pred；取 alpha 分位数为
#       单侧修正量 q；下界 = clip(point_pred + q, 0, 1)。
# 语义（交叉保形 CV+ 近似）：在可交换性假设下，新样本真实质量有约 1-alpha
#       的概率不小于该下界；有限样本实测覆盖率见 calibrate_conformal()。
# 约束：纯 Python / 无随机性（folds 按 idx % folds 固定划分，可复现）。
def _quantile(vals: List[float], q: float) -> float:
    """线性插值分位数（q∈[0,1]）。空列表返回 0.0。"""
    xs = sorted(float(v) for v in (vals or []))
    if not xs:
        return 0.0
    q = max(0.0, min(1.0, float(q)))
    if len(xs) == 1:
        return xs[0]
    pos = q * (len(xs) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    w = pos - lo
    return xs[lo] * (1.0 - w) + xs[hi] * w


def predict_row(model: dict, row: dict) -> float:
    """对训练器/校准器的 dict 行做预测（口径与 predict() 完全一致）。"""
    r = row or {}
    return predict(model, r.get("_features") or {},
                   int(_f(r.get("_route_n"), 4)),
                   _f(r.get("_rounds_avg"), 2),
                   bool(r.get("_web")),
                   str(r.get("_mode") or "other"),
                   r.get("_history") or {})


def _subfit(model: dict, rows: List[dict], y: List[float]) -> dict:
    if str(model.get("kind")) == "knn":
        return fit_knn(rows, y, k=int(model.get("k") or 5))
    return fit(rows, y, lam=float(model.get("lambda") or 2.0))


def calibrate_conformal(model: dict, rows: List[dict], y: List[float],
                        alpha: float = 0.2, folds: int = 5) -> dict:
    """K-fold 交叉残差 → 单侧保形下界修正量与实测覆盖率。

    返回 dict（写入 model["conformal"]）：
      {alpha, folds, n, q_global, q_by_mode, coverage_oof, mae_oof,
       residual_q10/q50/q90, kind}
    """
    n = min(len(rows), len(y))
    rows, y = list(rows[:n]), [float(v) for v in y[:n]]
    if n < 8:
        return {"alpha": float(alpha), "folds": 0, "n": n, "q_global": 0.0,
                "q_by_mode": {}, "coverage_oof": None, "mae_oof": None,
                "note": "样本不足 8，不校准"}
    folds = max(2, min(int(folds or 5), n))
    oof: List[Optional[float]] = [None] * n
    for f in range(folds):
        test_idx = [i for i in range(n) if i % folds == f]
        train_idx = [i for i in range(n) if i % folds != f]
        if len(train_idx) < 4 or not test_idx:
            continue
        sub = _subfit(model, [rows[i] for i in train_idx],
                      [y[i] for i in train_idx])
        for i in test_idx:
            oof[i] = predict_row(sub, rows[i])
    pairs = [(float(y[i]), float(oof[i])) for i in range(n)
             if oof[i] is not None]
    if not pairs:
        return {"alpha": float(alpha), "folds": folds, "n": n,
                "q_global": 0.0, "q_by_mode": {}, "coverage_oof": None,
                "mae_oof": None, "note": "交叉验证无有效预测"}
    resid = [a - p for a, p in pairs]
    q_global = _quantile(resid, alpha)
    by_mode: Dict[str, List[float]] = {}
    for i in range(n):
        if oof[i] is None:
            continue
        mb = mode_bucket(str(rows[i].get("_mode") or "other"))
        by_mode.setdefault(mb, []).append(float(y[i]) - float(oof[i]))
    # 每模式至少 15 条残差才单独给分位数，且与全局值偏离 ≤0.15 才采用；
    # 否则回落到全局（少量样本的模式分位数会在小样本上过度保守，例：B 桶
    # 21 条算出 -0.47 的极端下界，会让切档永远弃权）。这是工程护栏，
    # 说明见 docs/quality_conformal_20261025.md。
    q_by_mode = {}
    for k, v in by_mode.items():
        if len(v) < 15:
            continue
        _qk = _quantile(v, alpha)
        if abs(_qk - q_global) <= 0.15:
            q_by_mode[k] = round(_qk, 4)
    covered = sum(1 for a, p in pairs if a >= p + q_global)
    mae = sum(abs(a - p) for a, p in pairs) / len(pairs)
    return {
        "alpha": round(float(alpha), 4),
        "folds": folds,
        "n": n,
        "kind": str(model.get("kind") or "ridge"),
        "q_global": round(q_global, 4),
        "q_by_mode": q_by_mode,
        "coverage_oof": round(covered / len(pairs), 4),
        "mae_oof": round(mae, 4),
        "residual_q10": round(_quantile(resid, 0.10), 4),
        "residual_q50": round(_quantile(resid, 0.50), 4),
        "residual_q90": round(_quantile(resid, 0.90), 4),
        "note": "K-fold 交叉保形下界；coverage_oof≈1-alpha 时可用",
    }


def predict_lower(model: Optional[dict], features: dict, route_n=4,
                  rounds_avg=2.0, web=False, mode="other",
                  history=None) -> Optional[float]:
    """保形下界（无 conformal 段时返回 None ⇒ 调用方保持旧行为）。"""
    if not isinstance(model, dict):
        return None
    conf = model.get("conformal") or {}
    if conf.get("alpha") is None or conf.get("q_global") is None:
        return None
    p = predict(model, features, route_n, rounds_avg, web, mode, history)
    mb = mode_bucket(str(mode or "other"))
    q = (conf.get("q_by_mode") or {}).get(mb, conf.get("q_global") or 0.0)
    return max(0.0, min(1.0, float(p) + float(q)))


def predict_lower_row(model: Optional[dict], row: dict) -> Optional[float]:
    """对训练器/校准器的 dict 行做「保形下界」预测（口径同 predict_row）。"""
    r = row or {}
    return predict_lower(model, r.get("_features") or {},
                         int(_f(r.get("_route_n"), 4)),
                         _f(r.get("_rounds_avg"), 2),
                         bool(r.get("_web")),
                         str(r.get("_mode") or "other"),
                         r.get("_history") or {})


# ── 训练样本有效性（Round 4）────────────────────────────────────────────
# 背景：A/B/探针的部分跑（route 单层、预算硬顶截断、未走答案门）会以低质量
# 标签进入训练集；「近期加权 kNN」的邻居被这些残次样本污染后，M4 对新题
# 会预测塌到 0.1~0.3（2026-10-25 实测：道生模式查询原始下界仅 0.06）。
# 口径：只收「四层齐全 + 非预算硬顶 + 有决策轨迹与圈数」的完整跑。
def training_sample_ok(packed: dict) -> Tuple[bool, str]:
    """判断一条 packed 是否可作为 M4 训练样本；返回 (ok, 原因)。"""
    p = packed or {}
    route = p.get("route") or []
    try:
        route_set = {str(x) for x in route}
    except Exception:  # noqa: BLE001
        route_set = set()
    if not {"0", "1", "both", "all"}.issubset(route_set):
        return False, "partial_route"
    budget = p.get("budget") or {}
    if bool(budget.get("hard_hit")):
        return False, "budget_hard_hit"
    rounds = p.get("rounds") or {}
    if not isinstance(rounds, dict) or not rounds:
        return False, "no_rounds"
    dt = p.get("decision_trace") or {}
    q = p.get("quality") or {}
    if not isinstance(dt, dict) or not dt:
        return False, "no_decision_trace"
    if "answer_ready" not in dt and "answer_ready" not in q:
        return False, "no_answer_gate"
    depth = q.get("depth") or {}
    try:
        _chars = int(depth.get("structured_chars") or 0)
    except (TypeError, ValueError):
        _chars = 0
    if _chars and _chars < 200:
        return False, "too_short_product"
    return True, "ok"


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


def normalize_flags(flags) -> list:
    """[Round 129] 把动态 flag（如 `probe_link_dangling(3)`）归一为稳定 code。

    规则：取第一个 `(` 前的部分并去空白；保留顺序与去重。
    使 `duty_short`/`probe_link_dangling` 等可被聚合统计。
    """
    out: list = []
    for f in (flags or []):
        s = str(f or "").strip()
        if not s:
            continue
        base = s.split("(", 1)[0].strip()
        if base and base not in out:
            out.append(base)
    return out


#: [Round 130] process 类 flag：过程合同/流程告警，不等于答案质量结论。
_PROCESS_FLAG_CODES = frozenset({
    "duty_short", "probe_failed", "probe_return_empty",
    "candidates_overlap_pool", "ing_has_boilerplate",
    "ing_empty_with_candidates", "probe_skipped",
})


def classify_flags(flags) -> dict:
    """把 flags 分为 process / coverage / other 三组（只读分类，不改变原 flags）。

    - process：duty_short 等过程合同告警（可与 verified 并存，消费方应区别看待）；
    - coverage：probe_* / closure / uncovered 类覆盖告警；
    - other：其余（如 polarity / core_audit_gaps / too_many_*）。
    """
    out = {"process": [], "coverage": [], "other": []}
    for f in (flags or []):
        s = str(f or "").strip()
        if not s:
            continue
        code = s.split("(", 1)[0].strip()
        if code in _PROCESS_FLAG_CODES:
            out["process"].append(code)
        elif ("probe" in code or "closure" in code or "uncovered" in code):
            out["coverage"].append(code)
        else:
            out["other"].append(code)
    for k in out:
        seen, uniq = set(), []
        for x in out[k]:
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        out[k] = uniq
    return out


def verification_semantics(question_type: str, answer_quality: str,
                           process_ready: bool, has_official_evidence: bool,
                           has_answer_text: bool) -> dict:
    """[Round 132] 拆分 verified 语义（事实正确性 vs 过程合同），避免同名误解。"""
    aq = str(answer_quality or "")
    qt = str(question_type or "")
    is_fact = (qt == "fact")
    correctness = bool(is_fact and aq == "verified" and has_official_evidence
                       and has_answer_text)
    process = bool((not is_fact) and aq == "verified" and process_ready
                   and has_answer_text)
    if correctness:
        basis = "official_evidence"
    elif process:
        basis = "process_contract"
    elif aq == "verified":
        basis = "unclassified_verified"
    else:
        basis = "none"
    return {
        "answer_correctness_verified": correctness,
        "process_contract_verified": process,
        "evidence_basis": basis,
        "note": ("事实题 verified=官方证据+答案文本；非事实题 verified=四层过程合同"
                 "（不代表事实正确性）"),
    }


def display_gate(question_type: str, answer_quality: str,
                 display_text: str):
    """[Round 132] 事实题 verified 但无可展示答案 ⇒ (False, reason)；否则 (None, "")。"""
    if (str(question_type or "") == "fact"
            and str(answer_quality or "") == "verified"
            and not str(display_text or "").strip()):
        return False, "事实题 verified 但无可展示答案（display/answer 为空）"
    return None, ""


def alert_levels(flags) -> dict:
    """[Round 132] 告警分级：process→info、coverage/other→warn、block 集合→block。"""
    info = classify_flags(flags)
    block_codes = {"core_audit_gaps"}
    out = {"block": [], "warn": [], "info": []}
    for code in info.get("process") or []:
        out["info"].append(code)
    for code in (info.get("coverage") or []) + (info.get("other") or []):
        (out["block"] if code in block_codes else out["warn"]).append(code)
    rank = {"none": 0, "info": 1, "warn": 2, "block": 3}
    max_level = "none"
    for lvl in ("info", "warn", "block"):
        if out[lvl]:
            max_level = lvl if rank[lvl] > rank[max_level] else max_level
    out["max_level"] = max_level
    return out
