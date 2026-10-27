# -*- coding: utf-8 -*-
"""外部不确定性信号：v8b vs v9b 跨适配器分歧 → 升级教师（30 条 min held-out）。

- v9b 预测/教师预测复用 _audit_tmp/hybrid_eval_30.json；
- 通过服务 stage=self_check（v8b）重新取 v8b 预测；
- 评估：v8b、v9b、多数派/并集、分歧门控 hybrid（字段级/任一字段）。
"""
from __future__ import annotations

import json
import re
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


def call(stage, msgs):
    system = next((m["content"] for m in msgs if m.get("role") == "system"), "")
    user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
    body = json.dumps({"stage": stage,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}],
                       "preserve_system": True, "max_new_tokens": 160,
                       "temperature": 0.0, "timeout": 120}, ensure_ascii=False).encode()
    req = urllib.request.Request(SVC, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=150) as f:
        d = json.loads(f.read().decode())
    return d.get("json") or extract_json(d.get("text") or "")


def main() -> int:
    recs = json.loads(open(ROOT + "/_audit_tmp/hybrid_eval_30.json", encoding="utf-8").read())
    rows = [json.loads(l) for l in open(ROOT + "/llm_sft/dgtf_stage/self_check_min_val.jsonl", encoding="utf-8") if l.strip()][:N]
    out = []
    for i, (r, rec) in enumerate(zip(rows, recs)):
        pred8 = call("self_check", r["messages"])
        pred9 = rec["local"]
        teacher = rec["teacher"]
        gold = rec["gold"]
        s8, s9 = as_set((pred8 or {}).get("suspicious_candidates")), as_set((pred9 or {}).get("suspicious_candidates"))
        dis_susp = s8 != s9
        dis_ing = bool((pred8 or {}).get("ing_rephrased")) != bool((pred9 or {}).get("ing_rephrased"))
        dis_esc = bool((pred8 or {}).get("unsaid_is_escape")) != bool((pred9 or {}).get("unsaid_is_escape"))
        out.append({"i": i, "gold": gold, "p8": pred8, "p9": pred9, "teacher": teacher,
                    "dis_susp": dis_susp, "dis_ing": dis_ing, "dis_esc": dis_esc,
                    "dis_any": dis_susp or dis_ing or dis_esc})
        if (i + 1) % 10 == 0:
            print("progress", i + 1, flush=True)
    print("v8b ", json.dumps(agg([score(x["p8"], x["gold"]) for x in out]), ensure_ascii=False))
    print("v9b ", json.dumps(agg([score(x["p9"], x["gold"]) for x in out]), ensure_ascii=False))
    print("teacher", json.dumps(agg([score(x["teacher"], x["gold"]) for x in out]), ensure_ascii=False))
    print("disagreement rates",
          "susp", round(sum(1 for x in out if x["dis_susp"]) / N, 2),
          "ing", round(sum(1 for x in out if x["dis_ing"]) / N, 2),
          "esc", round(sum(1 for x in out if x["dis_esc"]) / N, 2),
          "any", round(sum(1 for x in out if x["dis_any"]) / N, 2))
    # 门控：分歧 → teacher，否则 v9b
    for gate_name, gate in (("susp", lambda x: x["dis_susp"]),
                            ("any", lambda x: x["dis_any"]),
                            ("ing_esc", lambda x: x["dis_ing"] or x["dis_esc"])):
        used_t = sum(1 for x in out if gate(x))
        scored = [score(x["teacher"] if gate(x) else x["p9"], x["gold"]) for x in out]
        print("HYB", gate_name, "teacher_used", used_t, json.dumps(agg(scored), ensure_ascii=False))
    # 并集/多数派（susp）
    for mode in ("union", "inter", "majority"):
        scored = []
        for x in out:
            s8, s9 = as_set((x["p8"] or {}).get("suspicious_candidates")), as_set((x["p9"] or {}).get("suspicious_candidates"))
            if mode == "union":
                s = s8 | s9
            elif mode == "inter":
                s = s8 & s9
            else:
                s = s8 if (x["p8"] or {}).get("ing_rephrased") is not None else s9
            pred = dict(x["p9"] or {})
            pred["suspicious_candidates"] = sorted(s)
            scored.append(score(pred, x["gold"]))
        print("ENS", mode, json.dumps(agg(scored), ensure_ascii=False))
    json.dump(out, open(ROOT + "/_audit_tmp/xadapter_hybrid_30.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
