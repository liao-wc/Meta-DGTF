# -*- coding: utf-8 -*-
"""模式级 Pareto 与融合模式（M4 auto-fused）。

背景：引擎并行模式 serial / A~H / auto。同题实测：
  · serial（run7）：quality 0.990 / tokens 997,457 / wall 1920.6s
  · B（run14）：quality 1.000 / tokens 1,269,082 / wall 1064.3s（质量/墙钟双优）
  · A（run13）：质量门失败（0.220）→ 不保留
  · C–H：暂无同题实测，不纳入保留模式
保留三种底层模式：B（质量/墙钟）、serial（低 tokens）、fast（thinking off 时间档）。
M4 auto-fused = 在三种模式间按质量/墙钟/tokens/联网约束自适应选择；
必要时可级联：先跑 fast，实测质量低于目标再升级到 B。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

MODES: Dict[str, dict] = {
    "B": {"name": "模式B·动态规划", "quality": 1.0, "quality_low": 0.9592,
          "tokens": 1269082, "wall": 1064.3, "wall_high": 1064.3,
          "web": False, "run": "20261024_205018",
          "strength": "质量/墙钟双优（方差 0.959–1.000）"},
    "serial": {"name": "serial·低tokens", "quality": 0.99, "quality_low": 0.99,
               "tokens": 997457, "wall": 1920.6, "wall_high": 1920.6,
               "web": False, "run": "20261024_163455",
               "strength": "质量高且 tokens 最低"},
    "fast": {"name": "thinking off·时间档", "quality": 0.93, "quality_low": 0.93,
             "tokens": 816983, "wall": 782.6, "wall_high": 782.6,
             "web": False, "run": "20261024_193452",
             "strength": "墙钟/tokens 最低"},
    "web": {"name": "B + 官方联网", "quality": 0.933, "quality_low": 0.933,
            "tokens": 1062012, "wall": 1073.3, "wall_high": 1073.3,
            "web": True, "run": "20261024_215545",
            "strength": "必须联网场景（质量/墙钟最佳联网档）"},
}

KEPT = ("B", "serial", "fast")


def select_mode(min_quality: Optional[float] = None,
                max_wall: Optional[float] = None,
                max_tokens: Optional[int] = None,
                require_web: bool = False,
                prefer: str = "quality") -> dict:
    """在保留模式中按约束选档；返回 mode + 原因（不可行时给回退）。"""
    pool = [k for k in KEPT if k in MODES]
    if require_web:
        pool = ["web"]
    rows = [(k, MODES[k]) for k in pool]
    if not rows:
        return {"mode": None, "reason": "无可用模式"}
    ok = []
    for k, m in rows:
        if min_quality is not None and m["quality"] < min_quality:
            continue
        if max_wall is not None and m["wall"] > max_wall:
            continue
        if max_tokens is not None and m["tokens"] > max_tokens:
            continue
        ok.append((k, m))
    if ok:
        if prefer == "wall":
            k, m = min(ok, key=lambda x: (x[1]["wall"], -x[1]["quality"]))
        elif prefer == "tokens":
            k, m = min(ok, key=lambda x: (x[1]["tokens"], -x[1]["quality"]))
        else:
            k, m = max(ok, key=lambda x: (x[1]["quality"], -x[1]["wall"]))
        return {"mode": k, "info": dict(m), "reason": "满足全部约束（prefer=%s）" % prefer}
    # 回退：质量可行者里墙钟最短 / 约束最接近
    above = [(k, m) for k, m in rows
             if min_quality is None or m["quality"] >= min_quality]
    if above:
        k, m = min(above, key=lambda x: (x[1]["wall"], x[1]["tokens"]))
        return {"mode": k, "info": dict(m),
                "reason": "无完全可行模式，退为满足质量下限中墙钟最短"}
    k, m = max(rows, key=lambda x: (x[1]["quality"], -x[1]["wall"]))
    return {"mode": k, "info": dict(m),
            "reason": "无满足质量下限模式，退为质量最高"}


def fused_plan(min_quality: Optional[float] = None,
               max_wall: Optional[float] = None,
               max_tokens: Optional[int] = None,
               require_web: bool = False,
               cascade: bool = True,
               features: Optional[dict] = None,
               history: Optional[dict] = None,
               model_path: str = "dgtf_memory/quality_predictor.json") -> dict:
    """M4 auto-fused：先选首选模式；cascade=True 给 fast→B 的升级路径。"""
    first = select_mode(min_quality=min_quality, max_wall=max_wall,
                        max_tokens=max_tokens, require_web=require_web,
                        prefer="quality")
    plan = {"first": first, "cascade": None,
            "policy": "B/serial/fast 三模式按约束自适应；quality 优先默认 B"}
    # 质量预测守卫：只在模型可用且特征已给时启用；预测 fast 不达标则直接选 B，
    # 避免“先跑 fast 再升级”的级联浪费。
    if features:
        try:
            from dgtf_v2.quality_predictor import load_model, predict
            model = load_model(str((Path(__file__).resolve().parents[2]
                                    / model_path))) if not Path(model_path).is_absolute() else load_model(model_path)
            if model:
                pred_raw = {
                    m: predict(model, features, route_n=4, rounds_avg=2.0,
                               web=bool(require_web), mode=m,
                               history=history or {})
                    for m in ("fast", "B", "serial")
                }
                # 模式先验校准：用实测模式下界做锚（B 有 0.959–1.000 方差），
                # 并把结果限制在该模式历史区间内，避免过度自信。
                pred = {}
                for k, v in pred_raw.items():
                    _lo = float(MODES[k].get("quality_low",
                                             MODES[k]["quality"]))
                    _hi = float(MODES[k]["quality"])
                    _cal = 0.5 * v + 0.5 * _lo
                    pred[k] = round(max(_lo, min(_hi, _cal)), 4)
                plan["quality_prediction_raw"] = {k: round(v, 4)
                                                  for k, v in pred_raw.items()}
                plan["quality_prediction"] = pred
                plan["quality_prediction_kind"] = "ridge+mode_prior(0.5/0.5)"
                # ── [Round 2] 保形下界：把「点预测」升级为「带风险保证的下界」 ──
                #   模型 JSON 若带 conformal 段（scripts/train_quality_predictor.py
                #   生成），则用 K-fold 交叉保形下界做更保守的切档；没有该段时
                #   完全保持旧行为（零行为差）。
                _lower: dict = {}
                try:
                    from dgtf_v2.quality_predictor import predict_lower
                    for _m in ("fast", "B", "serial"):
                        _lv = predict_lower(model, features, route_n=4,
                                            rounds_avg=2.0,
                                            web=bool(require_web), mode=_m,
                                            history=history or {})
                        if _lv is not None:
                            _lower[_m] = round(float(_lv), 4)
                    if _lower:
                        _conf = model.get("conformal") or {}
                        plan["quality_prediction_lower"] = _lower
                        plan["conformal"] = {
                            "alpha": _conf.get("alpha"),
                            "q_global": _conf.get("q_global"),
                            "coverage_oof": _conf.get("coverage_oof"),
                        }
                except Exception as _ce:  # noqa: BLE001
                    plan["conformal_error"] = str(_ce)
                _first_mode = (first or {}).get("mode")
                _conf_handled = False
                if (_lower and min_quality is not None
                        and max(_lower.values()) < min_quality):
                    plan["quality_guard"] = (
                        "conformal abstain：所有模式保形下界 < 目标 %.2f，"
                        "保留点预测选择并标记弃权" % min_quality)
                    plan["conformal"]["decision"] = "abstain"
                    _conf_handled = True
                elif (_lower and _first_mode == "fast" and min_quality is not None
                        and _lower.get("fast", 1.0) < min_quality
                        and _lower.get("B", 0.0) >= min_quality):
                    plan["first"] = {
                        "mode": "B", "info": dict(MODES["B"]),
                        "reason": "保形下界：fast %.3f < %.2f ≤ B %.3f，直接选 B"
                                  % (_lower.get("fast", 0.0), min_quality,
                                     _lower.get("B", 0.0))}
                    plan["cascade"] = None
                    plan["quality_guard"] = "fast→B by conformal lower"
                    _conf_handled = True
                elif (_lower and _first_mode == "fast" and min_quality is not None
                      and _lower.get("fast", 0.0) >= min_quality):
                    plan["quality_guard"] = "conformal lower: fast meets target"
                    _conf_handled = True
                if not _conf_handled and (_first_mode == "fast"
                                         and min_quality is not None
                                         and pred["fast"] < min_quality
                                         and pred["B"] >= min_quality):
                    plan["first"] = {"mode": "B", "info": dict(MODES["B"]),
                                     "reason": "质量预测：fast 预测 %.3f < %.2f，直接选 B"
                                               % (pred["fast"], min_quality)}
                    plan["cascade"] = None
                    plan["quality_guard"] = "fast→B by predictor"
                elif (not _conf_handled and _first_mode == "fast"
                      and min_quality is not None
                      and pred["fast"] >= min_quality):
                    plan["quality_guard"] = "predict fast meets target"
        except Exception as exc:  # noqa: BLE001
            plan["quality_prediction_error"] = str(exc)
    if cascade and not require_web and (plan.get("first") or {}).get("mode") == "fast":
        plan["cascade"] = {
            "on_quality_below": min_quality,
            "upgrade_to": "B",
            "why": "fast 先跑；实测质量低于目标再升级 B（用时间换质量）",
        }
    return plan


def scenario_table() -> List[dict]:
    """不同场景下的选择（用于文档/App 展示）。"""
    scenarios = [
        ("质量/墙钟优先", {"min_quality": 0.99, "prefer": "quality"}),
        ("墙钟 <=900s", {"min_quality": 0.9, "max_wall": 900, "prefer": "quality"}),
        ("tokens <=1.0M", {"min_quality": 0.95, "max_tokens": 1000000,
                           "prefer": "quality"}),
        ("必须联网", {"min_quality": 0.9, "require_web": True}),
        ("最快", {"min_quality": 0.9, "prefer": "wall"}),
    ]
    out = []
    for name, kw in scenarios:
        r = select_mode(**kw)
        out.append({"scenario": name, "mode": r.get("mode"),
                    "reason": r.get("reason"),
                    "quality": (r.get("info") or {}).get("quality"),
                    "tokens": (r.get("info") or {}).get("tokens"),
                    "wall": (r.get("info") or {}).get("wall")})
    return out
