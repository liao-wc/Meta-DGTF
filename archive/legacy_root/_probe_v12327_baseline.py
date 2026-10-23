#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.27 前置量化探针（基线）：把 §3.5 点名的五个缺陷量化。

★ 只调**引擎侧纯函数**，不跑 LLM ⇒ 零成本、可反复复跑。
★ 同一支探针在改前（v1.23.27 未改）与改后各跑一次，对表。
★ 读数写 `_baseline_v12327.json`（冻结），供报告引用。

八组读数：
  P1 `expected_gain` 的来源与分布形态（模型自报 ⇒ 引擎算？）
  P2 `select_probe_focus` 三轮 take 的产出数（fallback 会不会必满）
  P3 `covers` 校验：编号对 + 语义错 会不会报红
  P4 `link` 校验：非空以外还查不查（能否反查池内条目）
  P5 空探针判据的方向（罚空还是双向）
  P6 `G`（引擎算的信息增益）是否存在、值域是否 [0,1]
  P7 子模批选是否有边际下限（floor）
  P8 `AspectUnit` / `BeliefItem` / 语义熵 是否存在（底座就位情况）
"""
import importlib.util
import io
import contextlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.27.py"
OUT = HERE / "_baseline_v12327.json"

spec = importlib.util.spec_from_file_location("dgtf", str(SRC))
mod = importlib.util.module_from_spec(spec)
sys.modules["dgtf"] = mod
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(mod)

src = SRC.read_text(encoding="utf-8").replace("\r\n", "\n")
R = {}

# ---------- P1: expected_gain 的来源（自报 or 引擎算） ----------
_p1 = {
    "prompt_requires_self_report": bool(
        re.search(r"expected_gain", src)),
    "engine_computes_G": bool(
        re.search(r"def _compute_gain|def _eig\b|def _info_gain", src)),
    "gain_from_llm_field": "p.get(\"expected_gain\"" in src,
}
R["P1_expected_gain"] = _p1

# ---------- P2: select_probe_focus 三轮 take vs 子模 ----------
_has_sf = hasattr(mod, "select_probe_focus")
R["P2_select_focus"] = {
    "exists": _has_sf,
    "has_submodular": bool(re.search(r"submodular|_marginal|G\(p \| S\)", src)),
    "has_floor": bool(re.search(r"stop_floor|gain_floor|marginal_floor", src)),
}
if _has_sf:
    # 驱动：4 条全不相干候选 + 空池 ⇒ 看选出几个
    from types import SimpleNamespace
    pool = mod.Pool()
    cands = [{"question": f"披萨烤制时长与面团发酵温度的第{i}种测法",
              "link": "x", "expected_gain": 0.6, "covers": []}
             for i in range(4)]
    cfg = {"probe": {"select_n": 3}}
    try:
        picked = mod.select_probe_focus(pool, cands, [], ["量子纠缠"], "锚", cfg)
        R["P2_select_focus"]["picked_n_irrelevant"] = len(picked)
        R["P2_select_focus"]["picked_n_expected_old"] = 3
    except Exception as e:  # noqa: BLE001
        R["P2_select_focus"]["drive_error"] = f"{type(e).__name__}: {e}"

# ---------- P3: covers 编号对 + 语义错 是否报红 ----------
_CLS = None
for _c in ("DGTF", "MetaDGTF"):
    if hasattr(mod, _c) and hasattr(getattr(mod, _c), "_quality_check"):
        _CLS = getattr(mod, _c)
        break
R["P3_covers"] = {"class_found": _CLS is not None}
if _CLS is not None:
    obj = _CLS.__new__(_CLS)
    obj.entry = "1"
    obj.config = dict(mod.DEFAULT_CONFIG)
    obj.vp = lambda *a, **k: None
    UT = ["材料在极低温下的超导相变临界温度测量方法",
          "实验装置的电磁屏蔽对测量信噪比的影响",
          "样品制备过程中杂质浓度对结果的可重复性"]

    def _mk(probes):
        v = mod.View.__new__(mod.View)
        for n, d in [("candidates", []), ("amps", []), ("threads", []),
                     ("probes", []), ("errors", []), ("self_check", {}),
                     ("collision", ""), ("engagements", []),
                     ("deferrals", []), ("reconfirmations", []),
                     ("resolutions", []), ("escalations", []),
                     ("reclassifications", []), ("meta", []),
                     ("refinements", []), ("probe_skipped", False)]:
            try:
                setattr(v, n, d)
            except Exception:  # noqa: BLE001
                pass
        v.untouched = [{"desc": t} for t in UT]
        v.probes = probes
        return v

    def _flags(probes):
        try:
            return obj._quality_check(_mk(probes), mod.Pool(), 1,
                                      write_diag=False)
        except Exception as e:  # noqa: BLE001
            return ["__驱动失败__:" + type(e).__name__]

    # 乱指 T1（编号对、语义错）
    f_bad = _flags([{"question": "披萨需要烤制多长时间才能外脆内软",
                     "covers": ["T1"], "expected_gain": 0.6, "link": "x"}])
    R["P3_covers"]["bad_ref_flagged"] = "probe_no_target_covered" in f_bad
    R["P3_covers"]["bad_ref_flags"] = f_bad
    R["P3_covers"]["has_bad_ref_marker"] = "probe_covers_bad_ref" in src
    # 编码对、语义对
    f_ok = _flags([{"question": "超导相变临界温度在极低温下如何测量",
                    "covers": ["T1"], "expected_gain": 0.6, "link": "x"}])
    R["P3_covers"]["good_ref_flagged"] = "probe_no_target_covered" in f_ok

# ---------- P4: link 校验 ----------
R["P4_link"] = {
    "has_dangling_marker": "probe_link_dangling" in src,
    "only_nonempty_check": bool(re.search(
        r"if not q or len\(q\) < 6 or not link", src)),
    "reverse_lookup": bool(re.search(r"_link_dangling|_resolve_link|"
                                     r"link.*反查", src)),
}

# ---------- P5: 空探针判据方向 ----------
R["P5_empty_probe"] = {
    "prompt_offers_empty_exit": bool(re.search(
        r"推不动.*返回空|推不动就让 probes 返回空", src)),
    "judge_punishes_empty": "probe_return_empty" in src,
    "judge_is_bidirectional": bool(
        "honest_empty" in src and "lazy_empty" in src),
    "has_no_probe_reason": "no_probe_reason" in src,
}

# ---------- P6: G（引擎算的信息增益） ----------
R["P6_engine_G"] = {
    "exists": bool(re.search(r"def _compute_gain|def _eig\b|def _info_gain",
                             src)),
}

# ---------- P7: 子模边际下限 ----------
R["P7_submodular"] = {
    "has_marginal_gain": bool(re.search(r"_marginal_gain|def _g_given", src)),
}

# ---------- P8: 底座（AspectUnit / BeliefItem / 语义熵） ----------
R["P8_base"] = {
    "aspect_unit_concept": bool(re.search(r"AspectUnit|aspect_unit", src)),
    "belief_item_concept": bool(re.search(r"BeliefItem|belief_item", src)),
    "semantic_entropy": bool(re.search(r"semantic_entropy|_h_sem|H_sem", src)),
    "suspension_status": "SUSPENSION_STATUS" in src,
    "untouched_is_dict_list": bool(re.search(
        r"untouched: List\[dict\]", src)),
    "untouched_is_str_list": bool(re.search(
        r"untouched: List\[str\]", src)),
}

OUT.write_text(json.dumps(R, ensure_ascii=False, indent=2), encoding="utf-8")
print("=" * 76)
print("v1.23.27 前置量化基线（改前）")
print("=" * 76)
for k, v in R.items():
    print(f"\n[{k}]")
    for kk, vv in v.items():
        print(f"  {kk} = {vv}")
print(f"\n已写 {OUT.name}")
