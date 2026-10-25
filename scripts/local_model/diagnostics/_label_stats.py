# -*- coding: utf-8 -*-
"""统计 self_check / dual_judge 标签分布（给 Lead 汇报 + 评测基线用）。"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "llm_sft" / "dgtf_stage"


def rows(name):
    p = D / name
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
            if x.strip()]


sc = rows("self_check_val.jsonl")
scm = rows("self_check_min_val.jsonl")
dj = rows("dual_judge_val.jsonl")

print("=== dual_judge val ===")
pos = Counter()
n_j = 0
for r in dj:
    t = json.loads(r["messages"][-1]["content"])
    for j in t["judgments"]:
        pos[j["position"]] += 1
    n_j += len(t["judgments"])
print("samples", len(dj), "judgments", n_j, "positions", dict(pos))
print("share 0=%.3f 1=%.3f both=%.3f" % (
    pos["0"] / n_j, pos["1"] / n_j, pos["both"] / n_j))
print("by_phase", dict(Counter(r["phase"] for r in dj)))

print("\n=== self_check val (full) ===")
c = Counter()
susp_rate = 0
ing = 0
esc = 0
honest = 0
nz = 0
for r in sc:
    t = json.loads(r["messages"][-1]["content"])
    c["n"] += 1
    if t.get("suspicious_candidates"):
        susp_rate += 1
    if t.get("suspicious_amps"):
        c["susp_amps_nonempty"] += 1
    if t.get("ing_rephrased"):
        ing += 1
    if t.get("unsaid_is_escape"):
        esc += 1
    if not t.get("honest_about_empty", True):
        c["not_honest"] += 1
    if t.get("unsaid_count", 0) > 0:
        nz += 1
n = len(sc)
print("samples", n)
print("suspicious_candidates nonempty rate %.3f" % (susp_rate / n))
print("ing_rephrased true rate %.3f" % (ing / n))
print("unsaid_is_escape true rate %.3f" % (esc / n))
print("unsaid_count>0 rate %.3f" % (nz / n))
print("honest_about_empty false rate %.3f" % (c["not_honest"] / n))
print("by_phase", dict(Counter(r["phase"] for r in sc)))
print("avg target chars", round(sum(len(r["messages"][-1]["content"])
                                    for r in sc) / n, 1))
print("avg user chars", round(sum(len(r["messages"][1]["content"])
                                  for r in sc) / n, 1))
print("\n=== self_check_min val ===")
c2 = Counter()
for r in scm:
    t = json.loads(r["messages"][-1]["content"])
    if t.get("suspicious_candidates"):
        c2["susp_nonempty"] += 1
    if t.get("ing_rephrased"):
        c2["ing"] += 1
    if t.get("unsaid_is_escape"):
        c2["esc"] += 1
n2 = len(scm)
print("samples", n2, dict(c2),
      "avg target chars", round(sum(len(r["messages"][-1]["content"])
                                    for r in scm) / max(1, n2), 1))
