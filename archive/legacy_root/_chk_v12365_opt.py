# -*- coding: utf-8 -*-
"""v1.23.65 判据：token 软预算 / all_on 成本修正 / 配置生效 / 质量尺子。"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.65.py"
os.environ.setdefault("DGTF_API_KEY", "sk-opt-check")
_spec = importlib.util.spec_from_file_location("dgtf_opt", SRC)
mod = importlib.util.module_from_spec(_spec)
sys.modules["dgtf_opt"] = mod
_spec.loader.exec_module(mod)

sys.path.insert(0, str(HERE / "bench"))
_bs = importlib.util.spec_from_file_location("bs65", HERE / "bench" / "bench_score.py")
BS = importlib.util.module_from_spec(_bs)
sys.modules["bs65"] = BS
_bs.loader.exec_module(BS)

P, F = 0, []


def ck(name, cond, note=""):
    global P
    if cond:
        P += 1
        print("  OK  %s" % name)
    else:
        F.append(name)
        print("  RED %s  %s" % (name, note))


# ── 1. token 软预算 ───────────────────────────────────────
e = object.__new__(mod.MetaDGTF)
e.verbose = False
e.llm = types.SimpleNamespace(total_tokens=100, total_calls=3)
e._ck_base = {"tokens": 0}
e._token_budget = 0
e._call_budget = 0
ck("A1 0 = 不设限", e._token_budget_over() is False, "")
e._token_budget = 151
ck("A2 未到点不触发", e._token_budget_over() is False, "")
e.llm.total_tokens = 151
ck("A3 到点触发（>=）", e._token_budget_over() is True, "")
e._ck_base = {"tokens": 100}
e._token_budget = 252
ck("A4 续跑累计 251<252 不触发", e._token_budget_over() is False, "")
e._token_budget = 251
ck("A5 续跑累计 251>=251 触发", e._token_budget_over() is True, "")
e._note_budget_stop("单测")
ck("A6 预算留痕含「预算用尽」", "预算用尽" in e._budget_stop_note,
   e._budget_stop_note)

# ── 2. all_on 成本修正 ────────────────────────────────────
c, notes = mod._apply_all_on({"all_on": True})
ck("B1 all_on effort=low", c["api"]["thinking"]["effort"] == "low",
   c["api"]["thinking"].get("effort"))
ck("B2 all_on shape_limit=8", c["spiral"]["shape_limit"] == 8,
   c["spiral"].get("shape_limit"))
ck("B3 bandit 退出 all_on",
   not (c.get("auto", {}).get("bandit", {}) or {}).get("enabled", False), "")
ck("B4 merge_expand 仍在", c["actions"]["merge_expand"] is True, "")
ck("B5 all_on 仍 >=8 项", len(notes) >= 8, len(notes))

# ── 3. 配置实际生效 ───────────────────────────────────────
cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
ck("C1 配置 all_on=False（显式化）", cfg.get("all_on") is False, "")
ck("C1b 显式化：playbook/web/merge_expand 均在 yaml 打开",
   cfg["playbook"]["mode"] == "on"
   and cfg["web_search"]["enabled"] is True
   and cfg["actions"]["merge_expand"] is True, "")
ck("C2 配置 max_tokens=2.0M", int(cfg.get("max_tokens") or 0) == 2000000,
   cfg.get("max_tokens"))
ck("C3 shape_limit=8", cfg["spiral"]["shape_limit"] == 8,
   cfg["spiral"].get("shape_limit"))
ck("C4 all_extra_rounds=1", cfg["spiral"]["all_extra_rounds"] == 1, "")
ck("C5 span_tolerant=True", cfg["duty"]["span_tolerant"] is True, "")
ck("C6 effort=low", cfg["api"]["thinking"]["effort"] == "low", "")
st = cfg["api"]["thinking"]["stages"]
ck("C7 三个实测无收益环节已关",
   st.get("assess_decidability") == "disabled"
   and st.get("assess_decidability_from_pool_view") == "disabled"
   and st.get("re_evaluate_pool") == "disabled", st)
ck("C8 decompose_normal 开启", st.get("decompose_normal") == "enabled", "")
ck("C9 dual_judge 仍开", st.get("dual_judge") == "enabled", "")

# ── 4. 质量尺子：当前格式 3/3、旧格式仍可读 ────────────────
cur_md = (HERE / "outputs" / "20261014_103546_如何利用AI来帮助人类实现财富自由甚至文.md")
if cur_md.is_file():
    md = cur_md.read_text(encoding="utf-8")
    d = BS.score_decision_rubric(md)
    rs = BS.score_research(md)
    pr = BS.score_practice(md)
    ck("D1 当前模板 decision=3/3", d["score"] == 3 and d["format"] == "current",
       d)
    ck("D2 当前模板覆盖率可解析", rs.get("coverage_pct") is not None,
       rs.get("coverage_pct"))
    ck("D3 当前模板 objective 可解析",
       pr["score"] == 1.0 and rs["score"] == 1.0, (pr, rs))
else:
    ck("D1 当前样例存在", False, str(cur_md))
legacy_md = ("### 二、行动清单\n"
             "- **A1** verb=核查 object=清单 owner_role=X deadline_hint=Y "
             "acceptance=Z fallback=W\n"
             "- **A2** verb=备案 object=记录 owner_role=X deadline_hint=Y "
             "acceptance=Z fallback=W\n"
             "- **A3** verb=复核 object=产物 owner_role=X deadline_hint=Y "
             "acceptance=Z fallback=W\n"
             "### 五、不做什么\n- 不把开环 pass 当终局\n")
d2 = BS.score_decision_rubric(legacy_md)
ck("D4 旧单行六字段模板仍可判分",
   d2["score"] == 3 and d2["format"] == "legacy", d2)

# ── 5. 帕累托：129 calls 跑次支配 199 calls 跑次 ──────────
rows = [r for r in json.loads((HERE / "audits" / "opt_inventory_v12365.json")
                              .read_text(encoding="utf-8")) if r["complete"]]
qual = {}
for r in rows:
    md = (HERE / "outputs" / (r["stem"] + ".md")).read_text(encoding="utf-8")
    d = BS.score_decision_rubric(md)
    rs = BS.score_research(md)
    qual[r["stem"]] = (rs.get("coverage_pct") or 0, round((rs.get("tri_ratio") or 0) * 100), d["score"])
cheap = next((r for r in rows if r["calls"] == 129), None)
costly = next((r for r in rows if r["calls"] == 199), None)
if cheap and costly:
    qc, qx = qual[cheap["stem"]], qual[costly["stem"]]
    ck("E1 低价跑次在覆盖/一致率上不劣于最贵跑次",
       qc[0] >= qx[0] and qc[1] >= qx[1], (qc, qx))
    ck("E2 最贵跑次 tokens 至少是低价跑次的 2 倍",
       costly["tokens"] >= 2 * cheap["tokens"],
       (cheap["tokens"], costly["tokens"]))
else:
    ck("E1 两个对照跑次都存在", False, "")

print("\nOPT PASS %d / FAIL %d" % (P, len(F)))
sys.exit(1 if F else 0)
