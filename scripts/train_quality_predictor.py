# -*- coding: utf-8 -*-
"""用历史 packed 训练 M4 质量预测器（纯 Python ridge）。

用法：python scripts/train_quality_predictor.py [--model dgtf_memory/quality_predictor.json]
输出：模型 JSON + 训练/测试指标（MAE / R²）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))

from dgtf_v2.pareto_flow import extract_flow_metrics  # noqa: E402
from dgtf_v2.quality_predictor import (calibrate_conformal,  # noqa: E402
                                        evaluate, fit, fit_knn, mode_bucket,
                                        predict_lower_row, save_model,
                                        training_sample_ok)


def _rounds_avg(rounds) -> float:
    vals = []
    if isinstance(rounds, dict):
        for v in rounds.values():
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                pass
    return sum(vals) / len(vals) if vals else 2.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="dgtf_memory/quality_predictor.json")
    ap.add_argument("--lam", type=float, default=2.0)
    ap.add_argument("--test-ratio", type=float, default=0.2)
    ap.add_argument("--conformal-alpha", type=float, default=0.2,
                    help="保形下界的风险水平（0.2 ⇒ 实测覆盖率目标 80%%）")
    ap.add_argument("--conformal-folds", type=int, default=5)
    ap.add_argument("--include-invalid", action="store_true",
                    help="关闭「完整跑」过滤（默认开：排除部分跑/预算硬顶/无答案门）")
    args = ap.parse_args()
    rows, ys, metas = [], [], []
    drop_reasons = {}
    for p in sorted((ROOT / "outputs").glob("*.packed.json"),
                    key=lambda x: x.stat().st_mtime):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not args.include_invalid:
            _ok, _why = training_sample_ok(d)
            if not _ok:
                drop_reasons[_why] = drop_reasons.get(_why, 0) + 1
                continue
        m = extract_flow_metrics(d)
        feats = ((d.get("_auto_dispatch") or {}).get("_features") or {})
        if not feats or m.get("quality") is None:
            continue
        disp = d.get("_auto_dispatch") or {}
        mode = str((d.get("dispatch") or {}).get("_parallel_mode") or "")
        row = {"_features": feats,
               "_history": disp.get("_history") or {},
               "_route_n": len(d.get("route") or []),
               "_rounds_avg": _rounds_avg(d.get("rounds")),
               "_web": bool((d.get("api_usage") or {}).get("web_enabled")),
               "_mode": mode_bucket(mode)}
        rows.append(row)
        ys.append(float(m["quality"]))
        metas.append({"id": str(d.get("id") or p.stem), "mode": mode,
                      "file": p.name})
    if len(rows) < 8:
        print("样本不足：", len(rows))
        return 1
    import random as _random
    cut = max(1, int(len(rows) * (1.0 - args.test_ratio)))
    train_rows, test_rows = rows[:cut], rows[cut:]
    train_y, test_y = ys[:cut], ys[cut:]
    chrono = fit(train_rows, train_y, lam=args.lam)
    chrono_metrics = evaluate(chrono, test_rows, test_y)
    idx = list(range(len(rows)))
    _random.Random(20261024).shuffle(idx)
    rcut = max(1, int(len(rows) * (1.0 - args.test_ratio)))
    ridx = idx[:rcut]
    tidx = idx[rcut:]
    rand = fit([rows[i] for i in ridx], [ys[i] for i in ridx], lam=args.lam)
    rand_metrics = evaluate(rand, [rows[i] for i in tidx], [ys[i] for i in tidx])
    # kNN 变体：k=3/5/7，近期加权 / 等权
    _n = len(rows)
    _rec = [0.5 ** ((_n - 1 - i) / 40.0) for i in range(_n)]
    variants = {}
    best = None
    for kk in (3, 5, 7):
        for wname, wts in (("uniform", [1.0] * _n), ("recent", _rec)):
            m = fit_knn(rows, ys, k=kk, weights=wts)
            mets = {"chronological": evaluate(m, test_rows, test_y),
                    "random": evaluate(m, [rows[i] for i in tidx], [ys[i] for i in tidx])}
            variants["knn_k%d_%s" % (kk, wname)] = mets
            score = ((mets["random"].get("r2") or -9)
                     + 2 * (mets["chronological"].get("r2") or -9))
            if best is None or score > best[0]:
                best = (score, m, mets, "knn_k%d_%s" % (kk, wname))
    knn = best[1]
    knn_metrics = best[2]
    ridge_model = fit(rows, ys, lam=args.lam)
    model = knn if (knn_metrics["random"].get("r2") or -9) >= (rand_metrics.get("r2") or -9) else ridge_model
    model["metrics"] = {"chronological": chrono_metrics, "random": rand_metrics,
                        "knn": knn_metrics, "knn_variants": variants,
                        "chosen": model.get("kind", "ridge"),
                        "chosen_variant": best[3] if model is knn else "ridge"}
    model["n_train"] = len(rows)
    model["n_test"] = len(tidx)
    model["trained_from"] = "outputs/*.packed.json"
    # [Round 2] 保形下界：K-fold 交叉残差校准 + 留出集覆盖率实测。
    #   · q_global 进入 model["conformal"]，mode_fusion 用它做切档下界；
    #   · coverage_test 是「留出集真实质量 ≥ 下界」的比例，应接近 1-alpha；
    #   · 校准失败不阻断训练（写 error 段，mode_fusion 自动保持旧行为）。
    try:
        conf = calibrate_conformal(model, rows, ys,
                                   alpha=args.conformal_alpha,
                                   folds=args.conformal_folds)
        # ★ 必须先挂到 model 上，predict_lower_row 才看得到 conformal 段
        model["conformal"] = conf
        _ok = _n = 0
        for _i, _r in enumerate(test_rows):
            _pl = predict_lower_row(model, _r)
            if _pl is None:
                continue
            _n += 1
            if float(test_y[_i]) >= float(_pl):
                _ok += 1
        conf["coverage_test"] = round(_ok / _n, 4) if _n else None
        conf["coverage_test_n"] = _n
        model["conformal"] = conf
        print("conformal:", json.dumps(conf, ensure_ascii=False))
    except Exception as _exc:  # noqa: BLE001
        model["conformal"] = {"error": str(_exc)}
        print("conformal 校准失败（不阻断）：", _exc)

    if save_model(model, str(ROOT / args.model)):
        print("model ->", ROOT / args.model)
    try:
        repo_model = ROOT / "dgtf_engine" / "dgtf_v2" / "quality_predictor_model.json"
        save_model(model, str(repo_model))
        print("model(repo) ->", repo_model)
    except Exception:
        pass
    print("dropped:", json.dumps(drop_reasons, ensure_ascii=False), flush=True)
    print("samples:", len(rows), "train:", len(train_rows), "test:", len(test_rows))
    print("metrics:", json.dumps(model["metrics"], ensure_ascii=False))
    print("modes:", json.dumps({m: sum(1 for x in metas if x["mode"] == m)
                                for m in set(x["mode"] for x in metas)},
                               ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
