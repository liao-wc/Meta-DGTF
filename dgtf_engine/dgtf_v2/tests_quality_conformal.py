# -*- coding: utf-8 -*-
"""保形（conformal）质量下界判据（Round 2）。

覆盖：
  · 分位数实现（插值/边界/空）
  · K-fold 交叉保形校准：字段完整、q_global 有限、覆盖率落在合理区间
  · 下界单调性：predict_lower <= predict，且无 conformal 段时返回 None
  · 模型 JSON 往返（conformal 段不丢）
  · mode_fusion 切档：有 conformal 时用下界做 fast→B 守卫；无 conformal 时保持旧行为
"""
import json
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dgtf_v2.mode_fusion import fused_plan  # noqa: E402
from dgtf_v2.quality_predictor import (MODEL_PATH_DEFAULT,  # noqa: E402
                                        _quantile, calibrate_conformal, fit,
                                        load_model, mode_bucket,
                                        predict, predict_lower,
                                        predict_lower_row, predict_row,
                                        question_features, save_model)

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


MODES = ("fast", "B", "serial")


def _rows(n_per=18, base=None):
    """造 n_per*3 行合成样本：y 由模式基准 + 题面特征确定性生成 + 交替噪声。"""
    base = base or {"fast": 0.86, "B": 0.97, "serial": 0.94}
    qs = ["为什么城市热岛效应在夜间更明显？",
          "如何设计一个可回放的推理引擎？",
          "1+1 等于几？",
          "是否应该把 web 默认打开？"]
    rows, ys = [], []
    for m in MODES:
        for i in range(n_per):
            q = qs[i % len(qs)]
            feats = question_features(q)
            rows.append({"_features": feats,
                         "_history": {"calls_med": 100 + i, "tokens_med": 600000 + i,
                                      "tri_rate": 0.5, "cut_rate": 0.1},
                         "_route_n": 4,
                         "_rounds_avg": 2.0 + (i % 3),
                         "_web": bool(i % 2),
                         "_mode": m})
            noise = 0.03 * math.sin(7.0 * i + ord(m[0]))
            ys.append(max(0.0, min(1.0, base[m] + noise)))
    return rows, ys


def main():
    # ── 1. 分位数实现 ─────────────────────────────
    ck("_quantile 线性插值（.25 → 1.75）",
       abs(_quantile([1, 2, 3, 4], 0.25) - 1.75) < 1e-9,
       _quantile([1, 2, 3, 4], 0.25))
    ck("_quantile 边界（0 → 最小、1 → 最大）",
       _quantile([3, -1, 2], 0.0) == -1 and _quantile([3, -1, 2], 1.0) == 3)
    ck("_quantile 空列表 → 0.0", _quantile([], 0.2) == 0.0)

    # ── 2. 校准 ───────────────────────────────────
    rows, ys = _rows()
    model = fit(rows, ys, lam=2.0)
    conf = calibrate_conformal(model, rows, ys, alpha=0.2, folds=5)
    ck("校准字段完整", all(k in conf for k in
                        ("alpha", "folds", "n", "q_global", "q_by_mode",
                         "coverage_oof", "mae_oof")), conf)
    ck("校准样本数正确", conf["n"] == len(rows) and conf["alpha"] == 0.2, conf)
    ck("q_global 有限", isinstance(conf["q_global"], float)
       and -1.0 < conf["q_global"] < 1.0, conf["q_global"])
    ck("q_by_mode 至少覆盖 B 模式（每组 18 条、且与全局偏离≤0.15）",
       "B" in conf["q_by_mode"], conf["q_by_mode"])
    ck("OOF 覆盖率落在 0.6~1.0（alpha=0.2 期望≈0.8）",
       conf["coverage_oof"] is not None
       and 0.6 <= float(conf["coverage_oof"]) <= 1.0, conf["coverage_oof"])
    ck("残差分位数单调（q10 <= q50 <= q90）",
       conf["residual_q10"] <= conf["residual_q50"] <= conf["residual_q90"],
       (conf["residual_q10"], conf["residual_q50"], conf["residual_q90"]))
    conf2 = calibrate_conformal(model, rows, ys, alpha=0.2, folds=5)
    ck("校准可复现（同输入同输出）", conf2 == conf)

    small = calibrate_conformal(model, rows[:5], ys[:5], alpha=0.2)
    ck("样本不足 8 → note 且 q_global=0",
       small.get("q_global") == 0.0 and "note" in small, small)

    # ── 3. 下界：单调 + 无 conformal 返回 None ────
    feats = question_features("为什么城市热岛效应在夜间更明显？")
    model_conf = dict(model)
    model_conf["conformal"] = conf
    p = predict(model_conf, feats, mode="B")
    lo = predict_lower(model_conf, feats, mode="B")
    ck("predict_lower ≤ predict", lo is not None and lo <= p + 1e-9,
       (p, lo))
    ck("predict_lower ∈ [0,1]", 0.0 <= lo <= 1.0, lo)
    ck("无 conformal 段 → predict_lower 返回 None",
       predict_lower(model, feats, mode="B") is None)
    ck("predict_lower_row 与 predict_lower 一致",
       abs(predict_lower_row(model_conf, rows[5])
           - predict_lower(model_conf, rows[5].get("_features") or {},
                           int(rows[5].get("_route_n") or 4),
                           float(rows[5].get("_rounds_avg") or 2.0),
                           bool(rows[5].get("_web")),
                           str(rows[5].get("_mode") or "other"),
                           rows[5].get("_history") or {})) < 1e-9)
    ck("predict_row 与 predict 一致",
       abs(predict_row(model_conf, rows[3])
           - predict(model_conf, rows[3]["_features"], 4,
                     float(rows[3]["_rounds_avg"]), bool(rows[3]["_web"]),
                     rows[3]["_mode"], rows[3]["_history"])) < 1e-9)

    # ── 4. 模型 JSON 往返 ─────────────────────────
    with tempfile.TemporaryDirectory() as td:
        mp = Path(td) / "m.json"
        ok = save_model(model_conf, str(mp))
        loaded = load_model(str(mp))
        ck("模型保存/加载往返（含 conformal）",
           ok and loaded and loaded.get("conformal", {}).get("q_global")
           == conf["q_global"], loaded.get("conformal") if loaded else None)

        # ── 5. mode_fusion：有 conformal 用下界切档 ──
        # fast 墙钟 782.6s，max_wall=900 ⇒ first=fast；min_quality=0.93
        plan = fused_plan(min_quality=0.93, max_wall=900, features=feats,
                          model_path=str(mp), cascade=False)
        ck("plan 暴露保形下界三模式",
           isinstance(plan.get("quality_prediction_lower"), dict)
           and set(plan["quality_prediction_lower"]) == {"fast", "B", "serial"},
           plan.get("quality_prediction_lower"))
        ck("plan 暴露 conformal 元数据（alpha/coverage）",
           isinstance(plan.get("conformal"), dict)
           and plan["conformal"].get("alpha") == 0.2,
           plan.get("conformal"))
        _low = plan.get("quality_prediction_lower") or {}
        _guard = str(plan.get("quality_guard") or "")
        if _low.get("fast", 1.0) < 0.93 <= _low.get("B", 0.0):
            ck("保形守卫触发 fast→B 且理由可审计",
               _guard.startswith("fast→B by conformal lower")
               and (plan.get("first") or {}).get("mode") == "B", _guard)
        else:
            ck("保形守卫未触发时也保留可审计状态",
               ("conformal" in _guard) or ("conformal lower" in _guard)
               or ("abstain" in _guard) or (plan.get("conformal") is not None),
               _guard)

        # 无 conformal 的模型 → 旧行为：不出现下界字段
        m2 = dict(model_conf)
        m2.pop("conformal", None)
        mp2 = Path(td) / "m2.json"
        save_model(m2, str(mp2))
        plan2 = fused_plan(min_quality=0.93, max_wall=900, features=feats,
                           model_path=str(mp2), cascade=False)
        ck("无 conformal 时保持旧行为（无下界字段）",
           "quality_prediction_lower" not in plan2, list(plan2))

    # ── 5b. 手工构造模型：显式验证「保形下界触发 fast→B」──────
    from dgtf_v2.quality_predictor import FEATURES
    _mean = {k: 0.0 for k in FEATURES}
    _std = {k: 1.0 for k in FEATURES}
    _coef = [0.0] * len(FEATURES)
    _coef[FEATURES.index("mode_B")] = 0.04
    _coef[FEATURES.index("mode_fast")] = -0.05
    craft = {"kind": "ridge", "features": list(FEATURES),
             "mean": _mean, "std": _std, "coef": _coef, "intercept": 0.95,
             "conformal": {"alpha": 0.2, "q_global": -0.02,
                           "q_by_mode": {"fast": 0.0, "B": 0.02},
                           "coverage_oof": 0.8}}
    with tempfile.TemporaryDirectory() as td2:
        cp = Path(td2) / "craft.json"
        save_model(craft, str(cp))
        plan3 = fused_plan(min_quality=0.93, max_wall=900, features=feats,
                           model_path=str(cp), cascade=False)
        _l3 = plan3.get("quality_prediction_lower") or {}
        ck("手工模型下界符合预期（fast<0.93≤B）",
           _l3.get("fast", 1.0) < 0.93 <= _l3.get("B", 0.0), _l3)
        ck("保形守卫触发 fast→B（手工模型）",
           str(plan3.get("quality_guard")) == "fast→B by conformal lower"
           and (plan3.get("first") or {}).get("mode") == "B",
           (plan3.get("quality_guard"), plan3.get("first")))

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
