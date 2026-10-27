# -*- coding: utf-8 -*-
"""Hybrid 离线评估：本地 v9b（带 confidence）+ DeepSeek 兜底，30 条 min held-out。

输出：local / teacher / 不同 τ 的 hybrid 字段指标；并保存 teacher 输出供复查。
"""
from __future__ import annotations

import json
import re
import urllib.request

ROOT = "D:/Meta-DGTF-道生三阶模型"
SVC = "http://127.0.0.1:8772/generate"
API = "https://api.deepseek.com/chat/completions"
N = 30


def load_key() -> str:
    env = {}
    for line in open(ROOT + "/.env", encoding="utf-8", errors="replace"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env["DGTF_API_KEY"]


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


def main() -> int:
    rows = [json.loads(l) for l in open(ROOT + "/llm_sft/dgtf_stage/self_check_min_val.jsonl", encoding="utf-8") if l.strip()][:N]
    key = load_key()
    recs = []
    for i, r in enumerate(rows):
        msgs = r["messages"]
        system = next((m["content"] for m in msgs if m.get("role") == "system"), "")
        user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
        gold = extract_json(msgs[-1]["content"]) or {}
        # local
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
            pred_l = d.get("json") or extract_json(d.get("text") or "")
            conf = d.get("confidence")
        except Exception:  # noqa: BLE001
            pred_l, conf = None, None
        # teacher
        tbody = json.dumps({"model": "deepseek-chat",
                            "messages": [{"role": "system", "content": system},
                                         {"role": "user", "content": user}],
                            "temperature": 0.0, "max_tokens": 300,
                            "response_format": {"type": "json_object"}},
                           ensure_ascii=False).encode()
        treq = urllib.request.Request(API, data=tbody, headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + key})
        try:
            with urllib.request.urlopen(treq, timeout=120) as f:
                td = json.loads(f.read().decode())
            pred_t = extract_json(td["choices"][0]["message"]["content"])
        except Exception:  # noqa: BLE001
            pred_t = None
        recs.append({"i": i, "gold": gold, "local": pred_l, "teacher": pred_t,
                     "conf": conf})
    print("LOCAL  ", json.dumps(agg([score(r["local"], r["gold"]) for r in recs]), ensure_ascii=False))
    print("TEACHER", json.dumps(agg([score(r["teacher"], r["gold"]) for r in recs]), ensure_ascii=False))
    best = None
    for tau in (0.0, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.01):
        hyb = []
        for r in recs:
            use_local = (r["local"] is not None and r["conf"] is not None
                         and float(r["conf"]) >= tau)
            hyb.append(score(r["local"] if use_local else r["teacher"], r["gold"]))
        m = agg(hyb)
        m["tau"] = tau
        m["local_used"] = sum(1 for r in recs if (r["local"] is not None and r["conf"] is not None
                                                  and float(r["conf"]) >= tau))
        print("HYBRID", json.dumps(m, ensure_ascii=False))
        if best is None or m["field_mean"] > best["field_mean"]:
            best = m
    print("BEST", json.dumps(best, ensure_ascii=False))
    with open(ROOT + "/_audit_tmp/hybrid_eval_30.json", "w", encoding="utf-8") as f:
        json.dump(recs, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
