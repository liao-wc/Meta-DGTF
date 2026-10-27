# -*- coding: utf-8 -*-
"""候选分类器与生成式 v9b 融合评估（前 30 条 val，零 API）。"""
from __future__ import annotations

import json

ROOT = "D:/Meta-DGTF-道生三阶模型"


def as_set(x):
    if not isinstance(x, (list, tuple)):
        return set()
    return {int(v) for v in x if str(v).isdigit()}


def score(pred_set, gold, base_pred):
    g = as_set(gold.get("suspicious_candidates"))
    tp = len(pred_set & g)
    prec = tp / len(pred_set) if pred_set else (1.0 if not g else 0.0)
    rec = tp / len(g) if g else (1.0 if not pred_set else 0.0)
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    ing = bool(base_pred.get("ing_rephrased")) == bool(gold.get("ing_rephrased"))
    esc = bool(base_pred.get("unsaid_is_escape")) == bool(gold.get("unsaid_is_escape"))
    return {"set": pred_set == g, "f1": f1, "ing": ing, "esc": esc}


def agg(rows):
    n = len(rows)
    return {"n": n,
            "set_acc": round(sum(1 for r in rows if r["set"]) / n, 3),
            "f1": round(sum(r["f1"] for r in rows) / n, 3),
            "field_mean": round(sum((r["set"] + r["ing"] + r["esc"]) / 3 for r in rows) / n, 3)}


def main() -> int:
    probs = json.loads(open(ROOT + "/_audit_tmp/cand_classifier_val_probs.json", encoding="utf-8").read())
    probs_by_row = {x["row"]: x["cands"] for x in probs}
    recs = json.loads(open(ROOT + "/_audit_tmp/hybrid_eval_30.json", encoding="utf-8").read())
    rows = [json.loads(l) for l in open(ROOT + "/llm_sft/dgtf_stage/self_check_min_val.jsonl", encoding="utf-8") if l.strip()][:30]
    data = []
    for i, (r, rec) in enumerate(zip(rows, recs)):
        pred = rec["local"] or {}
        v9b = as_set(pred.get("suspicious_candidates"))
        cands = probs_by_row.get(i) or []
        data.append({"gold": rec["gold"], "v9b": v9b, "pred": pred, "cands": cands})
    print("v9b", json.dumps(agg([score(d["v9b"], d["gold"], d["pred"]) for d in data]), ensure_ascii=False))
    # 融合策略
    for tau in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        for mode in ("union", "classifier_only", "fill_if_empty"):
            scored = []
            for d in data:
                cset = {c["i"] for c in d["cands"] if c["p"] >= tau}
                if mode == "union":
                    s = d["v9b"] | cset
                elif mode == "classifier_only":
                    s = cset
                else:
                    s = d["v9b"] if d["v9b"] else cset
                scored.append(score(s, d["gold"], d["pred"]))
            m = agg(scored); m.update({"tau": tau, "mode": mode})
            if m["field_mean"] > 0.589 or m["f1"] > 0.16:
                print("FUSE", json.dumps(m, ensure_ascii=False))
    # top-k
    for k in (1, 2, 3, 4, 5, 6):
        scored = []
        for d in data:
            top = sorted(d["cands"], key=lambda c: -c["p"])[:k]
            scored.append(score({c["i"] for c in top}, d["gold"], d["pred"]))
        m = agg(scored); m.update({"topk": k})
        print("TOPK", json.dumps(m, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
