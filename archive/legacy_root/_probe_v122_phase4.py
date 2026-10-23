#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段4 探针] 外部锚点五档 / tier 门 / 检索器 / 冲突与 triage 出口。

用法：
    python _probe_v122_phase4.py <src.py> > _probe_v122_phase4_after.txt

基线里这些符号都不存在，所以每格都是「取值 / 具名异常」二选一。
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path

SRC = sys.argv[1]
spec = importlib.util.spec_from_file_location("dgtf_probe4", SRC)
dgtf = importlib.util.module_from_spec(spec)
sys.modules["dgtf_probe4"] = dgtf
spec.loader.exec_module(dgtf)
TXT = Path(SRC).read_text(encoding="utf-8")


def _try(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:90]}"


def _pool_with(anchors, as_ev=True, cfg=None):
    p = dgtf.Pool()
    p.anchors = list(anchors)
    p.anchor_as_evidence = as_ev
    p._anchor_cfg = dict(cfg or {"tier_floor": 2})
    return p


out = {
    "src": SRC,
    "version": getattr(dgtf, "__version__", "?"),
    "A_as_evidence_default": _try(lambda: (getattr(dgtf, "DEFAULT_CONFIG", {})
                                           .get("external_anchor", {})
                                           .get("as_evidence"))),
    "A2_tier_floor": _try(lambda: (dgtf.DEFAULT_CONFIG.get("external_anchor")
                                   or {}).get("tier_floor")),
    "A3_api_key_env": _try(lambda: (dgtf.DEFAULT_CONFIG.get("external_anchor")
                                    or {}).get("api_key_env")),
    "A4_retriever": _try(lambda: (dgtf.DEFAULT_CONFIG.get("external_anchor")
                                  or {}).get("retriever")),
    "B_tier_fn": _try(lambda: dgtf._anchor_tier({"as_evidence": True})),
    "B2_tier_fn_bool_false": _try(
        lambda: dgtf._anchor_tier({"as_evidence": False})),
    "B3_tier_fn_illegal": _try(
        lambda: dgtf._anchor_tier({"as_evidence": "随便"})),
    "C_enters_t1": _try(lambda: dgtf._anchor_enters_citation(
        {"id": "a", "tier": 1}, {"tier_floor": 2})),
    "C2_enters_t4": _try(lambda: dgtf._anchor_enters_citation(
        {"id": "a", "tier": 4}, {"tier_floor": 2})),
    "C3_enters_no_tier": _try(lambda: dgtf._anchor_enters_citation(
        {"id": "a"}, {"tier_floor": 2})),
    "D_citation_X_t1t4": _try(lambda: [
        c for c, _ in dgtf._citation_table(None, _pool_with(
            [{"id": "a1", "claim": "甲", "tier": 1},
             {"id": "a2", "claim": "乙", "tier": 4}]))
        if str(c).startswith("X")]),
    "D2_citation_X_off": _try(lambda: [
        c for c, _ in dgtf._citation_table(None, _pool_with(
            [{"id": "a1", "claim": "甲", "tier": 1}], as_ev=False))
        if str(c).startswith("X")]),
    "E_retriever_cls": _try(lambda: hasattr(dgtf, "AnchorRetriever")),
    "E2_snapshot_zero_calls": _try(
        lambda: dgtf.AnchorRetriever("snapshot", "").search(["q"], 3)),
    "E3_unknown_backend_raises": _try(
        lambda: dgtf.AnchorRetriever("web_search", "").search(["q"], 3)),
    "F_src_五档": all(k in TXT for k in ("off", "record", "crosscheck",
                                         "evidence", "gate")),
    "F2_src_锚点分级": "锚点分级" in TXT,
    "F3_src_triage": "triage_downgrades" in TXT,
    # ★ 判据别按「我记得写成了什么」拼，按**实际落点**搜：
    #   实测源码是 `_pv1.errors.append("锚点冲突：" + ...)`，
    #   我原来搜 `view.errors.append(f"锚点冲突` 得到 False —— 那是探针
    #   的串不对，不是功能没有（第一版就这么误报过一次）。
    "F4_src_冲突留痕三处": all(k in TXT for k in (
        '"锚点冲突："', "pool.meta.append(", "blocked_conclusions")),
    "G_crosscheck_triage_source": _try(
        lambda: "triage_downgrades" in inspect.getsource(
            dgtf.MetaDGTF._anchor_crosscheck)),
    "G2_ok": True,
}
print(json.dumps(out, ensure_ascii=False, indent=2))
