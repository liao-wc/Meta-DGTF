# -*- coding: utf-8 -*-
"""v11min 教师蒸馏适配器评估：self_check_min 30 条 held-out 字段质量（服务需在线）。"""
from __future__ import annotations

import json
import re
import sys
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
    m = re.search(r"\{.*\}", text, re.S)
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


def main() -> int:
    rows = [json.loads(l) for l in open(ROOT + "/llm_sft/dgtf_stage/self_check_min_val.jsonl", encoding="utf-8") if l.strip()][:N]
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
                           "preserve_system": True,
                           "max_new_tokens": 160, "temperature": 0.0,
                           "timeout": 120}, ensure_ascii=False).encode()
        req = urllib.request.Request(SVC, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=150) as f:
                d = json.loads(f.read().decode())
            pred = d.get("json") or extract_json(d.get("text") or "")
        except Exception as e:  # noqa: BLE001
            pred = None
        out.append(score(pred, gold))
        if (i + 1) % 5 == 0:
            print("progress", i + 1, "%.1fs" % (time.time() - t0), flush=True)
    rs = [x for x in out if x]
    metrics = {
        "n": len(rs),
        "json_n": len(rs),
        "susp_set_acc": round(sum(1 for s in rs if s["susp_set"]) / max(1, len(rs)), 3),
        "susp_f1": round(sum(s["susp_f1"] for s in rs) / max(1, len(rs)), 3),
        "ing_acc": round(sum(1 for s in rs if s["ing_ok"]) / max(1, len(rs)), 3),
        "esc_acc": round(sum(1 for s in rs if s["esc_ok"]) / max(1, len(rs)), 3),
        "field_mean": round(sum((s["susp_set"] + s["ing_ok"] + s["esc_ok"]) / 3 for s in rs) / max(1, len(rs)), 3),
    }
    print("METRICS", json.dumps(metrics, ensure_ascii=False))
    print("elapsed", round(time.time() - t0, 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
