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
from dgtf_v2.quality_predictor import (evaluate, fit, mode_bucket,  # noqa: E402
                                        save_model)


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
    args = ap.parse_args()
    rows, ys, metas = [], [], []
    for p in sorted((ROOT / "outputs").glob("*.packed.json"),
                    key=lambda x: x.stat().st_mtime):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
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
    model = fit(rows, ys, lam=args.lam)   # 部署用全量
    model["metrics"] = {"chronological": chrono_metrics, "random": rand_metrics}
    model["n_train"] = len(rows)
    model["n_test"] = len(tidx)
    model["trained_from"] = "outputs/*.packed.json"
    if save_model(model, str(ROOT / args.model)):
        print("model ->", ROOT / args.model)
    try:
        repo_model = ROOT / "dgtf_engine" / "dgtf_v2" / "quality_predictor_model.json"
        save_model(model, str(repo_model))
        print("model(repo) ->", repo_model)
    except Exception:
        pass
    print("samples:", len(rows), "train:", len(train_rows), "test:", len(test_rows))
    print("metrics:", json.dumps(model["metrics"], ensure_ascii=False))
    print("modes:", json.dumps({m: sum(1 for x in metas if x["mode"] == m)
                                for m in set(x["mode"] for x in metas)},
                               ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
