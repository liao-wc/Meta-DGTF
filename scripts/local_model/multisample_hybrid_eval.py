# -*- coding: utf-8 -*-
"""路径2：多采样不确定性 hybrid 评估（30 条 min held-out）。

对每行本地 self_check_min 采样 3 次（temperature 0.3），计算字段一致性；
一致性低 → 升级教师（复用已保存 teacher 输出），否则取多数派。
"""
from __future__ import annotations

import json
import re
import statistics
import time
import urllib.request

ROOT = "D:/Meta-DGTF-道生三阶模型"
SVC = "http://127.0.0.1:8772/generate"
N = 30


def extract_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def as_set(x):
    if not isinstance(x, (list, tuple)):
        return set()
    out = set()
    for v in x:
        try:
            out.add(int(v))
        except (TypeError, ValueError):
            out.add(str(v))
    return out


def score(pred, gold):
    if not isinstance(pred, dict):
        return None
    g_s, p_s = as_set(gold.get("suspicious_candidates")), as_set(pred.get("suspicious_candidates"))
    tp = len(g_s & p_s)
    prec = tp / len(p_s) if p_s else (1.0 if not g_s else 0.0)
    rec = tp / len(g_s) if g_s else (1.0 if not p_s else 0.0)
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"susp_set": g_s == p_s, "susp_f1": f1,
            "ing_ok": bool(pred.get("ing_rephrased")) == bool(gold.get("ing_rephrased")),
            "esc_ok": bool(pred.get("unsaid_is_escape")) == bool(gold.get("unsaid_is_escape"))}


def agg(scored):
    rs = [x for x in scored if x]
    return {"n": len(rs),
            "susp_set_acc": round(sum(1 for s in rs if s["susp_set"]) / max(1, len(rs)), 3),
            "susp_f1": round(sum(s["susp_f1"] for s in rs) / max(1, len(rs)), 3),
            "ing_acc": round(sum(1 for s in rs if s["ing_ok"]) / max(1, len(rs)), 3),
            "esc_acc": round(sum(1 for s in rs if s["esc_ok"]) / max(1, len(rs)), 3),
            "field_mean": round(sum((s["susp_set"] + s["ing_ok"] + s["esc_ok"]) / 3 for s in rs) / max(1, len(rs)), 3)}


def sample(msgs, temp=0.3, max_new=120):
    system = next((m["content"] for m in msgs if m.get("role") == "system"), "")
    user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
    body = json.dumps({"stage": "self_check_min",
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}],
                       "preserve_system": True, "max_new_tokens": max_new,
                       "temperature": temp, "timeout": 90}, ensure_ascii=False).encode()
    req = urllib.request.Request(SVC, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as f:
        d = json.loads(f.read().decode())
    return d.get("json") or extract_json(d.get("text") or "")


def consistency(samples):
    """返回 (field_agreement, majority_pred, uncertainty)。"""
    valid = [s for s in samples if isinstance(s, dict)]
    if not valid:
        return 0.0, None, 1.0
    # suspicious 用集合 exact 一致率
    sets = [as_set(s.get("suspicious_candidates")) for s in valid]
    susp_agree = sum(1 for s in sets if s == sets[0]) / len(sets) if sets else 0.0
    ing_vals = [bool(s.get("ing_rephrased")) for s in valid]
    esc_vals = [bool(s.get("unsaid_is_escape")) for s in valid]

    def mode(vals):
        return max(set(vals), key=vals.count)

    ing_agree = vals_agree = sum(1 for v in ing_vals if v == mode(ing_vals)) / len(valid)
    esc_agree = sum(1 for v in esc_vals if v == mode(esc_vals)) / len(valid)
    agreement = (susp_agree + ing_agree + esc_agree) / 3.0
    majority = {"suspicious_candidates": sorted(mode([tuple(sorted(s)) for s in sets]) if False else []),
                "ing_rephrased": mode(ing_vals), "unsaid_is_escape": mode(esc_vals)}
    # 多数派集合：出现次数最多的集合
    counts = {}
    for s in sets:
        counts[tuple(sorted(s, key=str))] = counts.get(tuple(sorted(s, key=str)), 0) + 1
    best_set = max(counts, key=counts.get) if counts else tuple()
    majority["suspicious_candidates"] = list(best_set)
    return agreement, majority, round(1.0 - agreement, 4)


def main() -> int:
    recs = json.loads(open(ROOT + "/_audit_tmp/hybrid_eval_30.json", encoding="utf-8").read())
    rows = [json.loads(l) for l in open(ROOT + "/llm_sft/dgtf_stage/self_check_min_val.jsonl", encoding="utf-8") if l.strip()][:N]
    out = []
    t0 = time.time()
    for i, (r, rec) in enumerate(zip(rows, recs)):
        msgs = r["messages"]
        gold = rec["gold"]
        samples = []
        for _ in range(3):
            try:
                samples.append(sample(msgs))
            except Exception:
                samples.append(None)
        agreement, majority, unc = consistency(samples)
        gold_sc = score(majority, gold) if majority else None
        out.append({"i": i, "gold": gold, "teacher": rec["teacher"],
                    "agreement": agreement, "uncertainty": unc,
                    "majority": majority, "majority_score": gold_sc})
        if (i + 1) % 5 == 0:
            print("progress", i + 1, "%.0fs" % (time.time() - t0), flush=True)
    print("MULTI-SAMPLE", json.dumps(agg([x["majority_score"] for x in out]), ensure_ascii=False))
    print("TEACHER", json.dumps(agg([score(x["teacher"], x["gold"]) for x in out]), ensure_ascii=False))
    # 一致性分布
    agr = [x["agreement"] for x in out]
    print("agreement mean", round(statistics.mean(agr), 3), "min", round(min(agr), 3),
          "max", round(max(agr), 3))
    # 用一致性做 hybrid：低一致 → teacher
    best = None
    for tau in [0.0, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]:
        scored = []
        used_teacher = 0
        for x in out:
            if x["agreement"] < tau:
                used_teacher += 1
                scored.append(score(x["teacher"], x["gold"]))
            else:
                scored.append(x["majority_score"])
        m = agg(scored); m["tau"] = tau; m["teacher_used"] = used_teacher
        print("HYB", json.dumps(m, ensure_ascii=False))
        if best is None or m["field_mean"] > best["field_mean"]:
            best = m
    print("BEST", json.dumps(best, ensure_ascii=False))
    json.dump(out, open(ROOT + "/_audit_tmp/multisample_hybrid_30.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
