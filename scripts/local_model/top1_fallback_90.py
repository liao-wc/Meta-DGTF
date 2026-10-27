# -*- coding: utf-8 -*-
"""top1 兜底 / 集合级解码 在 90 条 val 上的复核（v9b + 分类器概率）。"""
from __future__ import annotations

import json

ROOT = "D:/Meta-DGTF-道生三阶模型"


def as_set(x):
    if not isinstance(x, (list, tuple)):
        return set()
    return {int(v) for v in x if str(v).isdigit()}


def score(pred, gold, base):
    g = as_set(gold.get("suspicious_candidates"))
    tp = len(pred & g)
    prec = tp / len(pred) if pred else (1.0 if not g else 0.0)
    rec = tp / len(g) if g else (1.0 if not pred else 0.0)
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    ing = bool(base.get("ing_rephrased")) == bool(gold.get("ing_rephrased"))
    esc = bool(base.get("unsaid_is_escape")) == bool(gold.get("unsaid_is_escape"))
    return {"set": pred == g, "f1": f1, "ing": ing, "esc": esc}


def agg(rows):
    n = len(rows)
    return {"n": n,
            "set_acc": round(sum(1 for r in rows if r["set"]) / n, 3),
            "set_f1": round(sum(r["f1"] for r in rows) / n, 3),
            "field_mean": round(sum((r["set"] + r["ing"] + r["esc"]) / 3 for r in rows) / n, 3)}


def main() -> int:
    v9b = json.loads(open(ROOT + "/_audit_tmp/v9b_val90.json", encoding="utf-8").read())
    probs = json.loads(open(ROOT + "/_audit_tmp/cand_classifier_val_probs.json", encoding="utf-8").read())
    probs_by_row = {x["row"]: x["cands"] for x in probs}
    rows = []
    for rec in v9b:
        i = rec["i"]
        base = rec["pred"] or {}
        cands = sorted(probs_by_row.get(i) or [], key=lambda c: -c["p"])
        rows.append({"i": i, "gold": rec["gold"], "base": base,
                     "v9b_set": as_set(base.get("suspicious_candidates")),
                     "cands": cands})
    print("V9B90", json.dumps(agg([score(r["v9b_set"], r["gold"], r["base"]) for r in rows]), ensure_ascii=False))
    # top-k 覆盖
    for k in (1, 2, 3, 4):
        scored = []
        for r in rows:
            s = {c["i"] for c in r["cands"][:k]}
            scored.append(score(s, r["gold"], r["base"]))
        print("TOPK", k, json.dumps(agg(scored), ensure_ascii=False))
    # union v9b + top-k
    for k in (1, 2, 3):
        scored = []
        for r in rows:
            s = r["v9b_set"] | {c["i"] for c in r["cands"][:k]}
            scored.append(score(s, r["gold"], r["base"]))
        print("UNION", k, json.dumps(agg(scored), ensure_ascii=False))
    # 自适应 k：top1 与 top2 概率差 > m 则 k=1，否则 k=2
    for m in (0.0, 0.1, 0.2, 0.3, 0.5):
        scored = []
        for r in rows:
            cs = r["cands"]
            k = 1
            if len(cs) >= 2 and (cs[0]["p"] - cs[1]["p"]) <= m:
                k = 2
            scored.append(score({c["i"] for c in cs[:k]}, r["gold"], r["base"]))
        print("ADAPT", m, json.dumps(agg(scored), ensure_ascii=False))
    # 只在 v9b 为空时 top1（当前 empty_rate=0，等于 noop）
    scored = []
    for r in rows:
        s = r["v9b_set"] if r["v9b_set"] else {r["cands"][0]["i"]} if r["cands"] else set()
        scored.append(score(s, r["gold"], r["base"]))
    print("FILL_EMPTY", json.dumps(agg(scored), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
