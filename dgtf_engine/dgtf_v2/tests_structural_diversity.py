# -*- coding: utf-8 -*-
"""[v1.31] 结构多样性检查与一次性重采样的回归测试。

验收口径（与提案一致）：
  1. 立场全同 + 论据类型单一/模板重复 → `homogeneous=True`；
  2. 命中时最多触发一次重采样，且只采用「结构确实变多样」的结果；
  3. **判定逻辑不变**：`position_all_same_structural` 的生成规则不动，
     只验证重采样让该 flag 的计数下降（1 → 0）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from dgtf_v2.structural_diversity import (
    analyze_structural_diversity, argument_type, homogeneous_count)

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / "dgtf_v2" / "engine" / "MetaDGTF-道生三阶模型-V2.0.0.py"

P = []
F = []


def ck(name, ok, info=""):
    (P if ok else F).append(name)
    print(("PASS " if ok else "FAIL ") + name
          + (" :: " + str(info) if info and not ok else ""))


def _load_main():
    spec = importlib.util.spec_from_file_location("dgtf_sd_regression", SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_sd_regression"] = mod
    spec.loader.exec_module(mod)
    return mod


def _cand(mod, desc, pos, why):
    return mod.Candidate(desc=desc, position=pos, attribute="0",
                         why_position=why)


def _quality_flags(dg, mod, cands, pool):
    view = mod.View(entry="0", anchor="q",
                    candidates=[c.to_dict() for c in cands])
    return dg._quality_check(view, pool, round_no=1, write_diag=False), view


def _count_structural(flags):
    return sum(1 for f in (flags or [])
               if f.endswith("_all_same_structural"))


def main():
    # ── A 纯函数：立场/论据类型结构多样性 ──────────────────────
    same_template = [
        {"position": "0", "why_position": "因为市场收缩导致需求下降"},
        {"position": "0", "why_position": "由于成本上升所以利润承压"},
        {"position": "0", "why_position": "源于竞争加剧因此份额流失"},
    ]
    a1 = analyze_structural_diversity(same_template)
    ck("A1 全同立场 + 因果模板 → homogeneous",
       a1["homogeneous"] is True and a1["same_position"] is True)
    ck("A2 论据类型单一可定位", a1["argument_kinds"] == 1,
       a1["argument_types"])
    ck("A3 样本能定位字段与行号",
       a1["samples"][0]["position"] == "0"
       and a1["samples"][0]["argument_type"] == "因果"
       and a1["samples"][0]["why_position"])

    mixed_arg = [
        {"position": "0", "why_position": "因为市场收缩导致需求下降"},
        {"position": "0", "why_position": "相比去年，竞争格局已经反转"},
        {"position": "0", "why_position": "数据显示份额下降 12%"},
    ]
    a2 = analyze_structural_diversity(mixed_arg)
    ck("A4 全同立场但论据类型多样 → 不判同构",
       a2["homogeneous"] is False and a2["argument_kinds"] >= 2,
       a2["argument_types"])

    mixed_pos = [
        {"position": "0", "why_position": "因为市场收缩导致需求下降"},
        {"position": "1", "why_position": "由于成本上升所以利润承压"},
    ]
    a3 = analyze_structural_diversity(mixed_pos)
    ck("A5 立场已多样 → 不判同构",
       a3["homogeneous"] is False and a3["position_kinds"] == 2)
    ck("A6 论据分类器可单测",
       argument_type("例如某案例") == "例证"
       and argument_type("") == "空")
    ck("A7 同构计数口径", homogeneous_count([a1, a2, a3]) == 1)

    # ── B 一次性重采样：只在结构改善时采用，且不改判定逻辑 ─────
    mod = _load_main()
    cfg = {
        "spiral": {"structural_resample": True,
                   "structural_resample_max": 1,
                   "qc_both_ratio": 0.6,
                   "qc_rephrase_ratio": 0.5},
        "actions": {"dual_judge": True},
        "output": {"verbose": False, "save_dir": "outputs"},
    }
    dg = mod.DGTF.__new__(mod.DGTF)
    dg.entry = "0"
    dg.config = cfg
    dg.sp = dict(cfg["spiral"])
    dg.show_dual = False
    dg.vp = lambda *_a, **_k: None

    pool = SimpleNamespace(amps=[], threads=[], probes=[])
    inp = SimpleNamespace(pool=pool, question="q", is_base=True,
                          upstream_views=[], context="")

    before_cands = [
        _cand(mod, "需求侧收缩", "0", "因为市场收缩导致需求下降"),
        _cand(mod, "成本侧压力", "0", "由于成本上升所以利润承压"),
        _cand(mod, "竞争侧流失", "0", "源于竞争加剧因此份额流失"),
    ]
    after_cands = [
        _cand(mod, "需求侧收缩", "0", "因为市场收缩导致需求下降"),
        _cand(mod, "竞争格局反转", "1", "相比去年，竞争格局已经反转"),
        _cand(mod, "份额数据", "1", "数据显示份额下降 12%"),
    ]

    calls = []

    def fake_judge(cands, _inp, _anchor, _view=None,
                   diversity_hint="", allow_retry=True):
        calls.append({"n": len(cands), "hint": diversity_hint,
                      "allow_retry": allow_retry})
        out = []
        for i, c in enumerate(cands):
            src = after_cands[i] if i < len(after_cands) else c
            out.append(mod.Candidate(**mod.asdict(src)))
        return out

    dg._dual_judge = fake_judge

    view = mod.View(entry="0", anchor="q",
                    candidates=[c.to_dict() for c in before_cands])
    retried = dg._maybe_structural_resample(before_cands, inp, view)
    rec = view.structural_resample
    ck("B1 命中时触发一次重采样",
       rec.get("triggered") is True and len(calls) == 1, rec)
    ck("B2 复检只调用一次且不带降级重试",
       calls and calls[0]["allow_retry"] is False
       and "结构复检" in calls[0]["hint"])
    ck("B3 结构改善才采用", rec.get("improved") is True
       and rec.get("adopted") is True)
    ck("B4 立场种类确实上升",
       rec["before"]["position_kinds"] == 1
       and rec["after"]["position_kinds"] == 2)
    ck("B5 每层预算只记一次",
       getattr(pool, "_structural_resample_used", 0) == 1)

    # 第二次调用：预算耗尽，只提示，不再调 LLM、不再改候选。
    n_calls_before = len(calls)
    again = dg._maybe_structural_resample(before_cands, inp, view)
    ck("B6 第二次只提示不重采样",
       len(calls) == n_calls_before
       and view.structural_resample.get("reason") == "budget_exhausted")
    ck("B7 未重采样时原候选不变",
       [c.position for c in again] == [c.position for c in before_cands])

    # ── C 判定逻辑不变：只验证 flag 计数因重采样而下降 ─────────
    flags0, view0 = _quality_flags(dg, mod, before_cands, pool)
    c0 = _count_structural(flags0)
    flags1, view1 = _quality_flags(dg, mod, retried, pool)
    c1 = _count_structural(flags1)
    ck("C1 重采样前命中 position_all_same_structural", c0 == 1, flags0)
    ck("C2 重采样后同构计数下降（1 → 0）", c1 == 0, flags1)
    ck("C3 判定函数未被改写（flag 名仍是原口径）",
       all(f.endswith("_all_same_structural")
           for f in flags0 if "position_all_same" in f))
    ck("C4 质量检查留下结构诊断读数",
       view0.structural_diversity.get("homogeneous") is True
       and view1.structural_diversity.get("n") == len(retried))

    print()
    print("PASS %d / FAIL %d" % (len(P), len(F)))
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())