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

# ── 实测场景矩阵（2026-10-25 Round 4，引擎 CLI 真跑）────────────────────
# 用途：把「不同场景/领域/维度」的实测最优形态写成机器可读表，供 App/M4 选档
# 与文档展示。数字全部来自 docs/ab_results.jsonl 的同题真跑（引擎 V2.2.3，
# configs/道生专属模式.yaml，web 按场景开关）。
MEASURED_SCENARIOS: Dict[str, dict] = {
    "reasoning": {
        "label": "推理/机制解释",
        "question": "为什么城市热岛效应在夜间比白天更明显？",
        "runs": {
            "auto": {"quality": 0.9465, "tokens": 723064, "calls": 97,
                     "wall": 586.2, "verified": True,
                     "config": "B parallel + thinking auto + rounds auto"},
            "serial": {"quality": 0.9456, "tokens": 644954, "calls": 89,
                       "wall": 1019.0, "verified": True,
                       "config": "serial + thinking auto + rounds auto"},
            "fast": {"quality": 0.9366, "tokens": 481050, "calls": 89,
                     "wall": 188.4, "verified": True,
                     "config": "B parallel + thinking off + rounds auto"},
            "fast_domain2": {"quality": 0.9535, "tokens": 579083, "calls": 98,
                             "wall": 282.7, "verified": True,
                             "question": "为什么冬天的静电现象比夏天更常见？",
                             "config": "B parallel + thinking off + rounds auto"},
            "fast_domain3": {"quality": 0.9687, "tokens": 588198, "calls": 98,
                             "wall": 212.0, "verified": True,
                             "question": "为什么飞机在起飞前要除冰？",
                             "config": "B parallel + thinking off + rounds auto"},
        },
        "rules": {
            "quality_first": "auto",
            "cost_first": "fast",
            "low_tokens": "fast",
            "note": ("fast 已在三个推理域验证（0.9366 / 0.9535 / 0.9687 vs auto 0.9465；"
                     "差值在单跑方差内），tokens −33%、墙钟 −68~75% ⇒ 成本档首选；"
                     "serial 只省 11% tokens 但墙钟 +74%，已被 fast/auto 支配"
                     "（仅作历史对照保留）"),
        },
    },
    "choice": {
        "label": "选择/决策",
        "question": "在城市热岛研究中，应该优先补观测还是优先统一定义？",
        "runs": {
            "auto": {"quality": 0.9487, "tokens": 842151, "calls": 98,
                     "wall": 869.3, "verified": True,
                     "config": "B parallel + thinking auto + rounds auto"},
            "fast": {"quality": 0.9481, "tokens": 593788, "calls": 97,
                     "wall": 272.8, "verified": True,
                     "config": "B parallel + thinking off + rounds auto"},
            "fast2": {"quality": 0.9497, "tokens": 672011, "calls": 109,
                      "wall": 219.6, "verified": True,
                      "question": "在选择保温材料时应该优先考虑导热系数还是防火等级？",
                      "config": "B parallel + thinking off + rounds auto"},
        },
        "rules": {"quality_first": "auto", "cost_first": "fast",
                  "note": ("fast 实测与 auto 同质量（0.9481 vs 0.9487，差值在单跑方差内），"
                           "tokens −30%、墙钟 −69% ⇒ 成本档/多数场景可用；"
                           "质量优先仍保留 auto（thinking 保留更稳）")},
    },
    "fact": {
        "label": "事实/数值",
        "question": "光在水中传播的速度是多少？",
        "runs": {
            "web_on_auto": {"quality": 0.9581, "tokens": 1154024, "calls": 108,
                            "wall": 965.7, "verified": True,
                            "config": "B parallel + thinking auto + web on"},
            "web_on_auto2": {"quality": 0.9764, "tokens": 1120591, "calls": 109,
                             "wall": 1218.5, "verified": True,
                             "question": "2024年中国GDP增速最新数据是多少？",
                             "config": "B parallel + thinking auto + web on"},
            "web_on_auto3": {"quality": 0.9062, "tokens": 992929, "calls": 101,
                             "wall": 958.0, "verified": True,
                             "question": "HTTP 404状态码表示什么？",
                             "config": "B parallel + thinking auto + web on"},
            "web_on_fast_pre_fix": {"quality": 0.4741, "tokens": 836464,
                                    "calls": 108, "wall": 316.1,
                                    "verified": False,
                                    "config": "B parallel + thinking off + web on",
                                    "answer_quality": "needs_evidence",
                                    "note": "修复前历史负结果（官方检索/审计未修时）"},
            "web_on_fast": {"quality": 0.9472, "tokens": 558195, "calls": 88,
                            "wall": 174.4, "verified": True,
                            "question": "HTTP 404状态码表示什么？",
                            "config": "B parallel + thinking off + web on"},
            "web_on_fast2": {"quality": 0.9726, "tokens": 738637, "calls": 107,
                             "wall": 202.2, "verified": True,
                             "question": "2024年中国GDP增速最新数据是多少？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast3": {"quality": 0.9532, "tokens": 690842, "calls": 98,
                             "wall": 222.5, "verified": True,
                             "question": "长江的长度是多少千米？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast4": {"quality": 0.9508, "tokens": 727103, "calls": 98,
                             "wall": 275.6, "verified": True,
                             "question": "光在水中传播的速度是多少？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast5": {"quality": 0.9633, "tokens": 746308, "calls": 101,
                             "wall": 291.1, "verified": True,
                             "question": "2024年中国GDP总量是多少亿元？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast6": {"quality": 0.9789, "tokens": 679027, "calls": 98,
                             "wall": 258.2, "verified": True,
                             "question": "中国现行宪法是哪一年颁布的？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast7": {"quality": 0.9625, "tokens": 592698, "calls": 91,
                             "wall": 238.4, "verified": True,
                             "question": "人体的正常体温是多少摄氏度？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast8": {"quality": 0.9417, "tokens": 686520, "calls": 97,
                             "wall": 281.4, "verified": True,
                             "question": "2024年中国CPI涨幅是多少？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast9": {"quality": 0.9673, "tokens": 705691, "calls": 108,
                             "wall": 263.0, "verified": True,
                             "question": "2024年中国出生人口是多少万人？",
                             "config": "B parallel + thinking off + web on"},
            "web_on_fast10": {"quality": 0.9900, "tokens": 793041, "calls": 108,
                              "wall": 272.9, "verified": True,
                              "question": "2024年中国新能源汽车产量是多少万辆？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast11": {"quality": 0.9495, "tokens": 684973, "calls": 98,
                              "wall": 271.1, "verified": True,
                              "question": "我国法定结婚年龄是多少岁？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast12": {"quality": 0.9431, "tokens": 749542, "calls": 101,
                              "wall": 283.4, "verified": True,
                              "question": "2024年中国贸易顺差是多少亿美元？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast13": {"quality": 0.9800, "tokens": 703097, "calls": 99,
                              "wall": 261.2, "verified": True,
                              "question": "中国恢复高考是哪一年？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast14": {"quality": 0.9800, "tokens": 670445, "calls": 98,
                              "wall": 260.1, "verified": True,
                              "question": "奥林匹克五环的颜色有哪几种？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast15": {"quality": 0.9460, "tokens": 649612, "calls": 97,
                              "wall": 229.9, "verified": True,
                              "question": "地球到月球的平均距离是多少千米？",
                              "config": "B parallel + thinking off + web on"},
            "web_on_fast16": {"quality": 0.9900, "tokens": 644425, "calls": 98,
                              "wall": 243.0, "verified": True,
                              "question": "联合国的总部设在哪个城市？",
                              "config": "B parallel + thinking off + web on"},
            "web_off_auto": {"quality": 0.4440, "tokens": 1015910, "calls": 111,
                             "wall": 980.3, "verified": False,
                             "config": "B parallel + thinking auto + web off",
                             "answer_quality": "unverified"},
        },
        "rules": {
            "quality_first": "web_on_auto",
            "cost_first": "web_on_fast",
            "requires_web": True,
            "forbid": ["web_off_auto", "web_on_fast_pre_fix"],
            "note": ("事实门需要官方证据（web on）；2026-10-25 修复后重测："
                     "fast + web on（thinking off）质量 0.9472/0.9726 且 verified，"
                     "tokens −34~44%、墙钟 −82% ⇒ 成本档可用。"
                     "旧 0.4741/needs_evidence 为修复前历史（保留对照）。"
                     "「事实题无 web」仍是双输档。"),
        },
    },
}

KIND_BUCKETS = ("reasoning", "choice", "fact")


def measured_matrix() -> List[dict]:
    """返回实测场景矩阵（扁平列表，便于 App/文档渲染）。"""
    out = []
    for kind, cfg in MEASURED_SCENARIOS.items():
        for mode, run in (cfg.get("runs") or {}).items():
            out.append({"scenario": kind, "label": cfg.get("label", kind),
                        "mode": mode, "question": cfg.get("question", ""),
                        "quality": run.get("quality"),
                        "verified": run.get("verified"),
                        "tokens": run.get("tokens"),
                        "calls": run.get("calls"),
                        "wall": run.get("wall"),
                        "config": run.get("config", ""),
                        "answer_quality": run.get("answer_quality", "")})
    return out


def kind_of_question(question: str) -> str:
    """题面→场景桶（轻量规则；未知返回 reasoning）。"""
    q = str(question or "")
    if not q.strip():
        return "reasoning"
    fact_markers = ("多少", "是什么", "表示什么", "什么意思", "什么含义",
                    "指什么", "哪一年", "是谁", "等于几", "速度",
                    "多少度", "几岁", "多远", "定义")
    choice_markers = ("还是", "或者", "应该", "如何取舍", "优先", "选择",
                      "方案")
    if any(k in q for k in choice_markers):
        return "choice"
    if any(k in q for k in fact_markers) and not any(
            k in q for k in ("为什么", "为何", "机制", "原因")):
        return "fact"
    return "reasoning"


def recommend_scenario(kind: str = "reasoning",
                       min_quality: Optional[float] = None,
                       max_wall: Optional[float] = None,
                       prefer: str = "quality") -> dict:
    """按实测场景矩阵给推荐档；不满足约束时回退并写入 reason。"""
    k = kind if kind in MEASURED_SCENARIOS else "reasoning"
    cfg = MEASURED_SCENARIOS[k]
    rules = cfg.get("rules") or {}
    runs = cfg.get("runs") or {}
    require_web = bool(rules.get("requires_web"))
    pool = {name: r for name, r in runs.items() if r.get("verified")}
    if not pool:
        return {"scenario": k, "mode": None, "reason": "该场景无 verified 实测档"}
    feasible = {}
    for name, r in pool.items():
        if min_quality is not None and float(r.get("quality") or 0) < min_quality:
            continue
        if max_wall is not None and float(r.get("wall") or 1e9) > max_wall:
            continue
        feasible[name] = r
    fallback = False
    if not feasible:
        feasible = pool
        fallback = True
    _qfirst = str(rules.get("quality_first") or "")
    if (prefer == "quality" and min_quality is None and max_wall is None
            and _qfirst in feasible):
        name = _qfirst
        reason = "按实测场景规则选择质量优先档（rules.quality_first）"
        return {"scenario": k, "label": cfg.get("label", k), "mode": name,
                "run": dict(feasible[name]), "require_web": require_web,
                "forbid": list(rules.get("forbid") or []), "reason": reason,
                "note": rules.get("note", "")}
    if prefer == "wall":
        name = min(feasible, key=lambda n: feasible[n].get("wall") or 1e9)
    elif prefer == "tokens":
        name = min(feasible, key=lambda n: feasible[n].get("tokens") or 1e18)
    else:
        name = max(feasible, key=lambda n: (feasible[n].get("quality") or 0,
                                            -(feasible[n].get("wall") or 1e9)))
    reason = "按实测场景矩阵选择（prefer=%s）" % prefer
    if fallback:
        reason = "无满足约束的档，回退为最接近档（prefer=%s）" % prefer
    return {"scenario": k, "label": cfg.get("label", k), "mode": name,
            "run": dict(feasible[name]), "require_web": require_web,
            "forbid": list(rules.get("forbid") or []), "reason": reason,
            "note": rules.get("note", "")}


# ── App 维度实测跑次（2026-10-25 e2e 真跑，Round 27）────────────────────
# 用途：场景矩阵此前只有引擎 CLI 维度；App 端到端（含 plan/编排/归档）的实际
# 成本-质量需要独立锚点，供 App 展示与动态选档参考。
MEASURED_APP_RUNS: List[dict] = [
    {"id": "app-fast-reasoning", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "reasoning", "question": "为什么在高原上煮饭更容易夹生？",
     "quality": 0.9588, "tokens": 698602, "calls": 107, "wall": 573.3,
     "verified": True, "ready": True, "plan": "fast/thinking off/web off"},
    {"id": "app-fast-fact", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "fact", "question": "HTTP 500状态码表示什么？",
     "quality": 0.9740, "tokens": 745091, "calls": 99, "wall": 493.0,
     "verified": True, "ready": True, "plan": "fast/thinking off/web on"},
    {"id": "app-fast-fact-population", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "fact", "question": "2024年中国出生人口是多少万人？",
     "quality": 0.9724, "tokens": 567594, "calls": 87, "wall": 385.8,
     "verified": True, "ready": True, "plan": "fast/thinking off/web on"},
    {"id": "app-fast-fact-legal", "mode": "daosheng_fast", "tier": "fast",
     "scenario": "fact", "question": "我国法定结婚年龄是多少岁？",
     "quality": 0.9769, "tokens": 719919, "calls": 97, "wall": 465.0,
     "verified": True, "ready": True, "plan": "fast/thinking off/web on"},
    {"id": "app-quality-fact", "mode": "daosheng", "tier": "quality",
     "scenario": "fact", "question": "珠穆朗玛峰的海拔是多少米？",
     "quality": 0.9447, "tokens": 1182916, "calls": 112, "wall": None,
     "verified": True, "ready": True, "plan": "B/thinking auto/web on"},
]


def measured_app_runs() -> List[dict]:
    """App 维度实测跑次（扁平副本）。"""
    return [dict(x) for x in MEASURED_APP_RUNS]


def app_runs_summary() -> List[dict]:
    """按 (scenario, tier) 聚合 App 实测：均值质量/tokens/calls、verified 率。"""
    groups: Dict[tuple, List[dict]] = {}
    for r in MEASURED_APP_RUNS:
        groups.setdefault((str(r.get("scenario")), str(r.get("tier"))),
                          []).append(r)
    out = []
    for (sc, tier), rows in sorted(groups.items()):
        n = len(rows)
        out.append({
            "scenario": sc, "tier": tier, "n_runs": n,
            "quality_mean": round(sum(float(r.get("quality") or 0)
                                      for r in rows) / n, 4),
            "tokens_mean": int(sum(int(r.get("tokens") or 0)
                                   for r in rows) / n),
            "calls_mean": round(sum(int(r.get("calls") or 0)
                                    for r in rows) / n, 1),
            "walls": [r.get("wall") for r in rows],
            "verified_ratio": round(sum(1 for r in rows
                                        if r.get("verified")) / n, 3),
            "ready_ratio": round(sum(1 for r in rows
                                     if r.get("ready")) / n, 3),
        })
    return out

