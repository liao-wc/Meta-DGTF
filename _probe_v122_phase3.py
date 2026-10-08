#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段3 探针] decision 行动闭环的可探测量。

用法：
    python _probe_v122_phase3.py <src.py> > _probe_v122_phase3_after.txt

基线上这些符号都不存在，所以每格都是「取值 / 具名异常」二选一。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SRC = sys.argv[1]
spec = importlib.util.spec_from_file_location("dgtf_probe3", SRC)
dgtf = importlib.util.module_from_spec(spec)
sys.modules["dgtf_probe3"] = dgtf
spec.loader.exec_module(dgtf)
TXT = Path(SRC).read_text(encoding="utf-8")

GOOD = ("指派 排水公司 核查 老城区内涝点位台账，汛期前完成，"
        "验收以抽检合格为准，否则回退人工分片排查。"
        "申请 信息科 调取 近三年积水点水位记录，本月内完成，"
        "验收以台账入库为准，否则沿用去年记录。"
        "委托 项目组 试点 海绵改造，本季度完成，"
        "验收以积水频次下降为准，否则回退局部清淤。")
VIEW = {"decidable_product": {"answer": GOOD}}
EMPTY = {"decidable_product": {"answer": ""}}


def _try(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:90]}"


def _acts():
    a = dgtf._extract_actions(VIEW)
    return {"n": len(a),
            "ids": [x.get("id") for x in a],
            "verbs": [x.get("verb") for x in a],
            "fields_complete": all(
                all(x.get(k) for k in ("verb", "object", "owner_role",
                                       "deadline_hint", "acceptance",
                                       "fallback")) for x in a),
            "roles": [x.get("owner_role") for x in a],
            "deadlines": [x.get("deadline_hint") for x in a]}


def _dispatch(ori, on):
    r = {"orientation": ori, "_config": {"actions": {"landing_decision": on}},
         "views": {"1": {"decidable_product": {"answer": GOOD}}},
         "decidability": {}, "pools": {}}
    t = dgtf.render_landing(r)
    return {"decision_template": "落地层（decision 模式）" in t,
            "has_action_section": "### 二、行动清单" in t,
            "has_not_do_section": "### 五、不做什么" in t,
            "pool_meta_summary": "**池级留痕**" in t,
            "len": len(t)}


out = {
    "src": SRC,
    "version": getattr(dgtf, "__version__", "?"),
    "A_switch": _try(
        lambda: (dgtf.DEFAULT_CONFIG.get("actions") or {}).get(
            "landing_decision")),
    "B_render_boundary_exists": _try(
        lambda: hasattr(dgtf, "_render_landing_boundary")),
    "B2_render_decision_exists": _try(
        lambda: hasattr(dgtf, "_render_landing_decision")),
    "C_extract": _try(_acts),
    "C2_extract_empty": _try(lambda: len(dgtf._extract_actions(EMPTY))),
    "C3_extract_cached": _try(
        lambda: dgtf._extract_actions({"_actions": [{"id": "A1"}]})),
    "D_not_do": _try(lambda: dgtf._extract_not_do(
        {"decidable_product": {"answer": "不要整体翻新。先试点。"}})),
    "D2_not_do_none": _try(lambda: dgtf._extract_not_do(VIEW)),
    "E_dispatch": {
        "boundary": _try(lambda: _dispatch("boundary", True)),
        "decision": _try(lambda: _dispatch("decision", True)),
        "decision_off": _try(lambda: _dispatch("decision", False)),
        "auto": _try(lambda: _dispatch("auto", True)),
    },
    "F_src_action_incomplete": "action_incomplete" in TXT,
    "F2_src_not_do_missing": "not_do_missing" in TXT,
    "F3_src_orientation_field": '_orientation' in TXT,
    "G_pack_keys": _try(lambda: [k for k in ("orientation", "_config")
                                 if k in TXT]),
    "H_boundary_template_unchanged": _try(
        lambda: "**池级留痕**" in TXT and "_pool_meta_summary" in TXT),
}
print(json.dumps(out, ensure_ascii=False, indent=2))
