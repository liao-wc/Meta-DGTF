#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P5/P6] 真跑证据：4 次小跑（route 0，economy 档）。

  ① p5_auto      parallel_mode=auto + **不传 rounds** → 触发 `_auto_plan`；
                 orientation 默认 auto → 期望头部出现「取向判定（plan_orientation）」，
                 若模型判成 boundary（非 decision）还应出现「取向错配」。
  ② p5_boundary  同上，但**显式** orientation=boundary → 期望**不出现**错配告警（负对照）。
  ③ p6_notier    锚点快照里全是「无 tier」→ 期望头部出现「锚点 tier 警告」。
  ④ p6_tier      正常锚点快照（都有 tier）→ 期望**不出现**警告（负对照）。

用法：python _run_v1221_p56.py P5 | P6 | BOTH
产物：outputs/{p5_auto,p5_boundary,p6_notier,p6_tier}/ + meta.json + stdout.log
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / os.environ.get("P56_SRC", "元DGTF-V1.22.1-rc3.py")
Q = "地铁运营效率该怎么衡量？"


def _grep(md: Path, *pats):
    t = md.read_text(encoding="utf-8")
    return {p: (p in t) for p in pats}


def _run(m, tag: str, *, parallel_mode: str, rounds, orientation: str,
         anchor_path: str = "") -> dict:
    out = HERE / "outputs" / tag
    out.mkdir(parents=True, exist_ok=True)
    cfg = m.DEFAULT_CONFIG.copy()
    cfg["cost_profile"] = "economy"
    cfg["output"] = dict(cfg.get("output") or {})
    cfg["output"]["save_dir"] = str(out)
    cfg["output"]["verbose"] = False
    if anchor_path:
        cfg["external_anchor"] = dict(cfg.get("external_anchor") or {})
        cfg["external_anchor"].update({
            "enabled": True, "path": anchor_path,
            "as_evidence": "evidence", "tier_floor": 2})
    info = {"tag": tag, "ok": False, "error": "",
            "parallel_mode": parallel_mode, "rounds": rounds,
            "orientation": orientation, "anchor_path": anchor_path}
    buf = io.StringIO()
    t0 = time.time()
    try:
        with contextlib.redirect_stdout(buf):
            meta = m.MetaDGTF(cfg)
            res = meta.run(Q, route=["0"], rounds=rounds,
                           parallel_mode=parallel_mode,
                           orientation=orientation)
            md = m.save_result(res, str(out))
        p = Path(md)
        info.update({
            "ok": True, "md": str(md),
            "calls": int(getattr(meta.llm, "total_calls", 0) or 0),
            "tokens": int(getattr(meta.llm, "total_tokens", 0) or 0),
            "auto_plan_used": res.get("_auto_plan_used"),
            "declared_orientation": res.get("orientation"),
            "anchor_tier_warning": res.get("_anchor_tier_warning"),
            "hits": _grep(p, "取向判定（plan_orientation）", "取向错配",
                          "锚点 tier 警告"),
        })
    except Exception as e:  # noqa: BLE001
        info["error"] = type(e).__name__ + ": " + str(e)
    info["elapsed_s"] = round(time.time() - t0, 1)
    (out / "meta.json").write_bytes(json.dumps(
        info, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
    (out / "stdout.log").write_bytes(
        buf.getvalue().encode("utf-8", "replace"))
    print("[" + tag + "] ok=" + str(info["ok"]) + " calls=" + str(info.get("calls"))
          + " hits=" + json.dumps(info.get("hits"), ensure_ascii=False)
          + " err=" + str(info["error"])[:60])
    return info


def main() -> int:
    which = (sys.argv[1] if len(sys.argv) > 1 else "BOTH").upper()
    notier = HERE / "_test_anchors_notier.json"
    notier.write_bytes(json.dumps(
        {"question": "地铁运营效率该怎么衡量？", "retriever": "manual",
         "anchors": [{"id": "a1", "claim": "地铁运营效率的评价指标包括客流强度、"
                                            "正点率、单位人公里成本等"},
                     {"id": "a2", "claim": "行车间隔与运能利用率是常见考核项"}]},
        ensure_ascii=False, indent=2).encode("utf-8"))

    spec = importlib.util.spec_from_file_location("dgtf_p56", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_p56"] = m
    spec.loader.exec_module(m)

    if which in ("P5", "BOTH"):
        _run(m, "p5_auto", parallel_mode="auto", rounds=0, orientation="auto")
        _run(m, "p5_boundary", parallel_mode="auto", rounds=0,
             orientation="boundary")
    if which in ("P6", "BOTH"):
        _run(m, "p6_notier", parallel_mode="serial", rounds="0:1",
             orientation="decision", anchor_path=str(notier))
        _run(m, "p6_tier", parallel_mode="serial", rounds="0:1",
             orientation="decision",
             anchor_path=str(HERE / "_test_anchors.json"))
    print("P56_" + which + "_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
