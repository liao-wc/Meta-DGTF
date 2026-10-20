# -*- coding: utf-8 -*-
"""v1.23.64 前沿方法在**项目真实产物**上的只读实证。

数据源：
  · outputs/**/*.packed.json 的 views.<layer>.round_log（逐圈 new_amps/new_threads）
  · dgtf_memory/playbook.jsonl（真实经验库）
不写库、不调 LLM、不改任何产物；只产出 audits/frontier_v12364.{json,md}。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.64.py"
os.environ.setdefault("DGTF_API_KEY", "sk-frontier-audit")

_spec = importlib.util.spec_from_file_location("dgtf_fa", SRC)
mod = importlib.util.module_from_spec(_spec)
sys.modules["dgtf_fa"] = mod
_spec.loader.exec_module(mod)

random.seed(20261018)

# ── 1. 收集真实逐圈序列 ─────────────────────────────────────
series = []
for p in sorted((HERE / "outputs").glob("**/*.packed.json")):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    for layer, v in (d.get("views") or {}).items():
        if not isinstance(v, dict):
            continue
        rl = v.get("round_log") or []
        vals = [int((r or {}).get("new_amps", 0) or 0)
                + int((r or {}).get("new_threads", 0) or 0) for r in rl]
        if len(vals) >= 4:
            series.append({"file": p.name, "layer": str(layer), "vals": vals})

# ── 2. e-process vs Hoeffding（真实序列，逐前缀）────────────
cmp_rows = []
saved = []
for s in series:
    vals = s["vals"]
    bits = [1 if x > 0 else 0 for x in vals]
    n_e = n_h = None
    for t in range(2, len(bits) + 1):
        if n_e is None and mod.evalue_bernoulli(bits[:t], 0.5)["evalue"] >= 20:
            n_e = t
        lb = mod.stitched_hoeffding_lower(bits[:t], 0.05)
        if n_h is None and lb and lb["lower"] > 0.5:
            n_h = t
    cmp_rows.append({"run": s["file"], "layer": s["layer"], "n": len(bits),
                     "mean": round(sum(bits) / len(bits), 3),
                     "e_stop": n_e, "h_stop": n_h})
    if n_e and n_h:
        saved.append(n_h - n_e)

# ── 3. 保形预测：用「上一圈推下一圈」的持续性预测（真实序列）──
pairs = []
for s in series:
    v = s["vals"]
    for t in range(len(v) - 1):
        pairs.append((hashlib.sha1((s["file"] + s["layer"]).encode()).hexdigest()[:2],
                      abs(v[t + 1] - v[t]), s["layer"]))
cal = [x[1] for x in pairs if int(x[0], 16) % 10 < 7]
test = [x[1] for x in pairs if int(x[0], 16) % 10 >= 7]
q90 = mod.conformal_quantile(cal, 0.1)
coverage = (sum(1 for x in test if x <= q90) / len(test)) if test else None

# ── 4. BOCPD：真实序列里的制度切换 ──────────────────────────
boc = []
for s in series:
    r = mod.bocpd_run(s["vals"], hazard=0.1)
    if r["detected"]:
        boc.append({"run": s["file"], "layer": s["layer"], "n": len(s["vals"]),
                    "detected": r["detected"][:6],
                    "max_change_prob": max(r["change_probs"] or [0])})

# ── 4b. BOCPD：跨跑成本序列（episodes.jsonl，按时间排序）──
episodes = []
try:
    episodes = [json.loads(x) for x in
                (HERE / "dgtf_memory" / "episodes.jsonl").read_text(
                    encoding="utf-8").splitlines() if x.strip()]
except Exception:
    episodes = []
episodes.sort(key=lambda r: float(r.get("t") or 0))
cost_series = []
for r in episodes:
    _tk = float((r.get("cost") or {}).get("tokens") or 0)
    if _tk > 0:
        cost_series.append(round(math.log10(_tk + 1.0), 6))
cost_boc = mod.bocpd_run(cost_series, hazard=0.1) if len(cost_series) >= 3 else {}

# ── 5. 论证：真实 playbook 的只读冲突裁决 ───────────────────
playbook = mod.eml_read_jsonl(HERE / "dgtf_memory" / "playbook.jsonl")
real = mod.resolve_playbook_conflicts([dict(x) for x in playbook], apply=False)
# 负对照：人为造一条同条件不同动作 ⇒ 必须被判出冲突
inj = [dict(x) for x in playbook[:2]]
if inj:
    a = dict(inj[0])
    a["id"] = "INJ-1"
    a["action"] = dict(a.get("action") or {})
    a["action"]["_conflict_probe"] = True
    inj.append(a)
    inj_res = mod.resolve_playbook_conflicts(inj, apply=False)
else:
    inj_res = {"n_attacks": 0}

out = {
    "n_series": len(series),
    "n_rounds": sum(len(s["vals"]) for s in series),
    "eprocess": {
        "n_compared": len(cmp_rows),
        "e_only": sum(1 for r in cmp_rows if r["e_stop"] and not r["h_stop"]),
        "h_only": sum(1 for r in cmp_rows if r["h_stop"] and not r["e_stop"]),
        "both": sum(1 for r in cmp_rows if r["e_stop"] and r["h_stop"]),
        "median_saved_rounds": (statistics.median(saved) if saved else None),
        "examples": cmp_rows[:10],
    },
    "conformal": {"n_cal": len(cal), "n_test": len(test), "q90": q90,
                  "coverage": (round(coverage, 4) if coverage is not None else None),
                  "alpha": 0.1},
    "series_len": {"n": len(series), "min": min((len(s["vals"]) for s in series),
                                                default=0),
                   "median": (statistics.median([len(s["vals"]) for s in series])
                              if series else None),
                   "max": max((len(s["vals"]) for s in series), default=0)},
    "bocpd": {"n_with_change": len(boc), "examples": boc[:10],
              "cross_run_cost": {"n": len(cost_series),
                                 "detected": cost_boc.get("detected", []),
                                 "max_change_prob": (max(cost_boc.get("change_probs") or [0])
                                                     if cost_boc else None)}},
    "argumentation": {"n_playbook": len(playbook), "real": real,
                      "injected_conflict_detected": inj_res.get("n_attacks", 0) > 0,
                      "injected": inj_res},
}
(HERE / "audits").mkdir(exist_ok=True)
(HERE / "audits" / "frontier_v12364.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

L = ["# v1.23.64 前沿方法 · 真实产物实证", "",
     "- 数据：%d 条逐圈序列 / %d 圈（outputs/**/*.packed.json）"
     % (len(series), out["n_rounds"]),
     "- 口径：只读；不写库、不调 LLM、不改产物。", "",
     "## 1. e-process vs stitched Hoeffding", "",
     "| 项 | 值 |", "|---|---|",
     "| 可比较序列 | %d |" % len(cmp_rows),
     "| e 先判 / h 先判 / 同时 | %d / %d / %d |"
     % (out["eprocess"]["e_only"], out["eprocess"]["h_only"],
        out["eprocess"]["both"]),
     "| 同时判时节省圈数中位 | %s |"
     % (out["eprocess"]["median_saved_rounds"],), "",
     "> 说明：真实序列的边际 p 未必是 0.5，此表只比**两种口径的相对早晚**，",
     "> 不当作功效实验；I 类错误由合成仿真单独钉（KERNEL F1）。", "",
     "## 2. 保形预测（下一圈持续性预测的 90% 区间）", "",
     "| 项 | 值 |", "|---|---|",
     "| 校准/测试样本 | %d / %d |" % (len(cal), len(test)),
     "| q90 | %.4f |" % q90,
     "| 实测覆盖率 | %s |" % (out["conformal"]["coverage"],), "",
     "## 3. BOCPD 制度切换", "",
     "逐圈序列长度：min=%d / 中位=%s / max=%d（%d 条）。**短序列本来就不适合变点检测**，"
     % (out["series_len"]["min"], out["series_len"]["median"],
        out["series_len"]["max"], out["series_len"]["n"]),
     "所以下表把「真实逐圈」与「跨跑成本」分开报，不用前者冒充功效。", "",
     "| 序列 | n | 检出变点 | 最大变点概率 |", "|---|---|---|---|",
     "| 逐圈产出（真实） | %d 条 | %d 条 | — |"
     % (len(series), len(boc)),
     "| 跨跑 log10(tokens) | %d | %s | %s |"
     % (out["bocpd"]["cross_run_cost"]["n"],
        out["bocpd"]["cross_run_cost"]["detected"],
        out["bocpd"]["cross_run_cost"]["max_change_prob"]), "",
     "## 4. 论证冲突裁决（真实 playbook）", "",
     "| 项 | 值 |", "|---|---|",
     "| 论证数 / 攻击边 | %d / %d |"
     % (real["n_args"], real["n_attacks"]),
     "| winner / defeated / undecided | %d / %d / %d |"
     % (len(real["winners"]), len(real["defeated"]),
        len(real["undecided"])),
     "| 注入冲突被检出 | %s |" % out["argumentation"]["injected_conflict_detected"], "",
     "> 负对照：往真实库里注入一条同条件不同动作的条目，攻击边必须 >0。",
     "> 没有这条，表里的 0 可能只是「判据没工作」。", ""]
(HERE / "audits" / "frontier_v12364.md").write_text("\n".join(L) + "\n",
                                                    encoding="utf-8")
print("series", len(series), "rounds", out["n_rounds"])
print("eprocess", {k: v for k, v in out["eprocess"].items() if k != "examples"})
print("conformal", out["conformal"])
print("bocpd", out["bocpd"]["n_with_change"])
print("argumentation", {k: out["argumentation"][k] for k in
                        ("n_playbook", "injected_conflict_detected")},
      "real", {k: real[k] for k in ("n_args", "n_attacks")})
print("WROTE audits/frontier_v12364.{json,md}")
