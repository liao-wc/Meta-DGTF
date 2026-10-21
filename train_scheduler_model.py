# -*- coding: utf-8 -*-
"""训练本地调度模型：EML/V2 outcome + packed 上下文 → quality / log(tokens) 岭回归。

这是 app 侧可应用的小模型权重训练，不是 LLM fine-tune。
用法：python train_scheduler_model.py [--out dgtf_memory/scheduler_model.json]
"""
from __future__ import annotations
import argparse, glob, json, math, os, re
from collections import Counter
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent

def bucket(q):
    s = str(q or "")
    if any(k in s for k in ("比较", "对比", "区别", "优劣", " vs ", "VS", "哪个好")): return "compare"
    if any(k in s for k in ("为什么", "原因", "导致", "影响", "后果")): return "causal"
    if any(k in s for k in ("如何", "怎么", "怎样", "步骤", "方案", "实现")): return "howto"
    if any(k in s for k in ("应该", "是否", "要不要", "选择", "决策")): return "decision"
    if any(k in s for k in ("什么时候", "何时", "时间", "发布", "多少", "定义", "是什么")): return "fact"
    return "general"

def load_rows():
    packed = {}
    for p in glob.glob(str(ROOT / "outputs" / "*.packed.json")):
        try:
            d = json.load(open(p, encoding="utf-8"))
            packed[Path(p).stem] = d
        except Exception:
            pass
    latest = {}
    ev = ROOT / "dgtf_memory" / "v2_events.jsonl"
    if ev.exists():
        for ln in ev.read_text(encoding="utf-8", errors="replace").splitlines():
            try: d = json.loads(ln)
            except Exception: continue
            if d.get("kind") != "schedule_outcome": continue
            pl = d.get("payload") or {}
            rid, t = str(d.get("run_id") or ""), str(pl.get("template") or "")
            if rid and t: latest[(rid, t)] = pl
    rows = []
    for (rid, t), pl in latest.items():
        d = packed.get(rid)
        if not d: continue
        q = str(d.get("question") or "")
        m = re.search(r":r(\d+)$", t)
        rounds = int(m.group(1)) if m else 1
        rows.append({"run_id": rid, "template": t, "bucket": bucket(q),
                     "qlen": len(q), "rounds": rounds,
                     "quality": float(pl.get("quality") or 0),
                     "tokens": float(pl.get("tokens") or 0),
                     "calls": float(pl.get("calls") or 0)})
    return rows

def design(rows, tpl_vocab, bkt_vocab, qlen_mean, qlen_std):
    names = ["intercept"]
    names += ["tpl:" + t for t in tpl_vocab]
    names += ["bucket:" + b for b in bkt_vocab]
    names += ["rounds", "qlen_z"]
    X = []
    for r in rows:
        v = [1.0]
        v += [1.0 if r["template"] == t else 0.0 for t in tpl_vocab]
        v += [1.0 if r["bucket"] == b else 0.0 for b in bkt_vocab]
        v += [float(r["rounds"]), (float(r["qlen"]) - qlen_mean) / max(1e-9, qlen_std)]
        X.append(v)
    return np.asarray(X, dtype=float), names

def fit_ridge(X, y, lam):
    n, d = X.shape
    A = X.T @ X + lam * np.eye(d)
    A[0, 0] -= lam  # 不惩罚截距
    b = X.T @ y
    return np.linalg.solve(A, b)

def metrics(y, pred):
    y = np.asarray(y); pred = np.asarray(pred)
    mae = float(np.mean(np.abs(y - pred)))
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2)) or 1e-9
    return {"mae": round(mae, 5), "r2": round(1 - ss_res / ss_tot, 5)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dgtf_memory/scheduler_model.json")
    ap.add_argument("--lam", type=float, default=2.0)
    ap.add_argument("--holdout", type=float, default=0.2)
    args = ap.parse_args()
    rows = load_rows()
    if len(rows) < 30:
        raise SystemExit("训练样本不足: %d" % len(rows))
    # 按 run 分组切分，避免同题泄漏
    runs = sorted({r["run_id"] for r in rows})
    cut = max(1, int(len(runs) * (1 - args.holdout)))
    train_runs = set(runs[:cut]); test_runs = set(runs[cut:])
    train = [r for r in rows if r["run_id"] in train_runs]
    test = [r for r in rows if r["run_id"] in test_runs]
    tpl_vocab = sorted({r["template"] for r in rows})
    bkt_vocab = sorted({r["bucket"] for r in rows})
    qlen_mean = float(np.mean([r["qlen"] for r in rows]))
    qlen_std = float(np.std([r["qlen"] for r in rows])) or 1.0
    Xtr, names = design(train, tpl_vocab, bkt_vocab, qlen_mean, qlen_std)
    Xte, _ = design(test, tpl_vocab, bkt_vocab, qlen_mean, qlen_std)
    yq_tr = np.array([r["quality"] for r in train], float)
    yq_te = np.array([r["quality"] for r in test], float)
    yt_tr = np.log1p(np.array([r["tokens"] for r in train], float))
    yt_te = np.log1p(np.array([r["tokens"] for r in test], float))
    wq = fit_ridge(Xtr, yq_tr, args.lam)
    wt = fit_ridge(Xtr, yt_tr, args.lam)
    predq = Xte @ wq; predt = Xte @ wt
    base = np.full_like(yq_te, float(np.mean(yq_tr)))
    model = {
        "version": "scheduler_model/v1", "kind": "local_ridge",
        "trained_at": __import__("time").time(),
        "rows": len(rows), "train_rows": len(train), "test_rows": len(test),
        "runs": len(runs), "train_runs": len(train_runs), "test_runs": len(test_runs),
        "templates": tpl_vocab, "buckets": bkt_vocab,
        "qlen_mean": qlen_mean, "qlen_std": qlen_std,
        "features": names,
        "quality_weights": [round(float(x), 6) for x in wq],
        "log_tokens_weights": [round(float(x), 6) for x in wt],
        "quality_test": metrics(yq_te, predq),
        "quality_baseline": metrics(yq_te, base),
        "log_tokens_test": metrics(yt_te, predt),
        "note": "本地调度小模型，不是 LLM 权重 fine-tune",
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(model, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: model[k] for k in ("rows", "train_rows", "test_rows", "runs",
                                           "quality_test", "quality_baseline",
                                           "log_tokens_test", "templates")},
                     ensure_ascii=False, indent=1)[:3000])
    print("WROTE", out)

if __name__ == "__main__":
    main()
