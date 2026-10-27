# -*- coding: utf-8 -*-
"""v9b 在全部 90 条 min val 上的生成式预测（供 top1 兜底 90 条复核）。"""
from __future__ import annotations

import json
import re
import time
import urllib.request

ROOT = "D:/Meta-DGTF-道生三阶模型"
SVC = "http://127.0.0.1:8772/generate"


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
    return {int(v) for v in x if str(v).isdigit()}


def score(pred, gold):
    if not isinstance(pred, dict):
        return None
    g, p = as_set(gold.get("suspicious_candidates")), as_set(pred.get("suspicious_candidates"))
    tp = len(g & p)
    prec = tp / len(p) if p else (1.0 if not g else 0.0)
    rec = tp / len(g) if g else (1.0 if not p else 0.0)
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"set": g == p, "f1": f1,
            "ing": bool(pred.get("ing_rephrased")) == bool(gold.get("ing_rephrased")),
            "esc": bool(pred.get("unsaid_is_escape")) == bool(gold.get("unsaid_is_escape")),
            "empty": len(p) == 0}


def main() -> int:
    rows = [json.loads(l) for l in open(ROOT + "/llm_sft/dgtf_stage/self_check_min_val.jsonl", encoding="utf-8") if l.strip()]
    out = []
    t0 = time.time()
    for i, r in enumerate(rows):
        msgs = r["messages"]
        system = next((m["content"] for m in msgs if m.get("role") == "system"), "")
        user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
        gold = extract_json(msgs[-1]["content"]) or {}
        body = json.dumps({"stage": "self_check_min",
                           "messages": [{"role": "system", "content": system},
                                        {"role": "user", "content": user}],
                           "preserve_system": True, "max_new_tokens": 160,
                           "temperature": 0.0, "timeout": 120}, ensure_ascii=False).encode()
        req = urllib.request.Request(SVC, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=150) as f:
                d = json.loads(f.read().decode())
            pred = d.get("json") or extract_json(d.get("text") or "")
            conf = d.get("confidence")
        except Exception:  # noqa: BLE001
            pred, conf = None, None
        out.append({"i": i, "gold": gold, "pred": pred, "conf": conf,
                    "score": score(pred, gold)})
        if (i + 1) % 15 == 0:
            print("progress", i + 1, "%.0fs" % (time.time() - t0), flush=True)
    rs = [x["score"] for x in out if x["score"]]
    n = len(rs)
    metrics = {"n": n,
               "set_acc": round(sum(1 for s in rs if s["set"]) / n, 3),
               "set_f1": round(sum(s["f1"] for s in rs) / n, 3),
               "ing_acc": round(sum(1 for s in rs if s["ing"]) / n, 3),
               "esc_acc": round(sum(1 for s in rs if s["esc"]) / n, 3),
               "empty_rate": round(sum(1 for s in rs if s["empty"]) / n, 3),
               "field_mean": round(sum((s["set"] + s["ing"] + s["esc"]) / 3 for s in rs) / n, 3)}
    print("V9B90", json.dumps(metrics, ensure_ascii=False))
    json.dump(out, open(ROOT + "/_audit_tmp/v9b_val90.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
