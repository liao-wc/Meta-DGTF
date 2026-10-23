#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段1 探针] 目标函数分层 / 覆盖率归属 / 未生分类 / route 分层。

用法：
    python _probe_v122_phase1.py <src.py> > _probe_v122_phase1_after.txt

★ 探针要能在**基线**上跑完：基线里这些函数/形参都还不存在，
  所以每一格都必须是「取值成功 / 具名异常」二选一，不许崩。
  崩了就看不出「改前是什么样」，对照也就没了。
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path

SRC = sys.argv[1]
spec = importlib.util.spec_from_file_location("dgtf_probe1", SRC)
dgtf = importlib.util.module_from_spec(spec)
sys.modules["dgtf_probe1"] = dgtf
spec.loader.exec_module(dgtf)
SRCTEXT = Path(SRC).read_text(encoding="utf-8")


def _try(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:90]}"


def _route(mod, ori, route=("0", "1", "both", "all")):
    inst = object.__new__(mod.MetaDGTF)
    inst.config = {}
    inst.vp = lambda *a, **k: None
    return inst._route_by_decidability("q", list(route), orientation=ori)


out = {
    "src": SRC,
    "version": getattr(dgtf, "__version__", "?"),
    "A_objective": {
        k: getattr(dgtf.PHASES.get(k), "objective", None)
        for k in ("0", "1", "both", "all")},
    "B_cov_entry": {
        e: _try(lambda e=e: dgtf.coverage_of(dgtf.Pool(), {}, entry=e))
        for e in ("0", "1", "both", "all")},
    "B2_cov_entry_passed_positionally": _try(
        lambda: dgtf.coverage_of(dgtf.Pool(), {}, "0")),
    "B3_cov_parts_entry0": _try(
        lambda: dgtf.coverage_parts(dgtf.Pool(), {}, entry="0")),
    "C_classify_view_empty": _try(
        lambda: dgtf._classify_unsaid(dgtf.View(entry="0", collision=""))),
    "C_classify_view_real": _try(
        lambda: dgtf._classify_unsaid(dgtf.View(
            entry="0", collision="一、让两端各自把话说完\n二、各推到极端",
            probes=[{"question": "Q", "covers": ["T1"]}]))),
    "C_classify_view_unsaid_kw": _try(
        lambda: dgtf._classify_unsaid(dgtf.View(
            entry="0", collision="（此处未生）",
            probes=[{"question": "Q", "covers": ["T1"]}]))),
    "C_classify_dict_real": _try(
        lambda: dgtf._classify_unsaid({"covers": ["T1"]})),
    "C_classify_dict_empty": _try(lambda: dgtf._classify_unsaid({})),
    "D_header_has_layer_target": "分层目标" in SRCTEXT,
    "D2_layer_objective_lines": _try(
        lambda: len(dgtf._layer_objective_lines({"views": {}, "pools": {}}))),
    "E_stop_reason_src_未生质量": "未生质量" in SRCTEXT,
    "E2_stop_reason_src_修行层不追求收敛": "修行层不追求收敛" in SRCTEXT,
    "F_settle_meta_ref_p0": _try(
        lambda: ('pools["0"]' in inspect.getsource(dgtf.MetaDGTF._settle_meta))
        or ("pools['0']" in inspect.getsource(dgtf.MetaDGTF._settle_meta))),
    "G_route_boundary": _try(lambda: _route(dgtf, "boundary")),
    "G2_route_two_layers": _try(lambda: _route(dgtf, "boundary", ["0", "1"])),
    "H_bench_questions": len(list((Path(SRC).resolve().parent
                                   / "bench/questions").glob("*.yaml"))),
    "H2_bench_gold": len(list((Path(SRC).resolve().parent
                               / "bench/gold").glob("*.yaml"))),
}

# 展示 objective 的渲染行（改前无此函数 → 记异常）
out["D3_legend"] = _try(lambda: dgtf._layer_objective_lines())

print(json.dumps(out, ensure_ascii=False, indent=2))
