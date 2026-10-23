#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P2.3] 三题真跑验 triage 命中率（任务书 Step P2.3 的实现版）。

与任务书骨架的差别：加 try/except + 每跑一份 meta.json（留痕），并把
`save_dir` 写进 cfg（骨架靠 `save_result(dir)` 直接给目录，本版两条都走）。

用法：python _run_v1221_p2.py [src.py]
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / (sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.22.1-rc1.py")

Q = [
    "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵措施？",
    "现金流紧张的中小制造企业，上自动化产线还是维持人工加局部优化？",
    "社区医院人力有限，慢性病管理推远程监测还是加派人手上门随访？",
]


def main() -> int:
    spec = importlib.util.spec_from_file_location("dgtf_p2", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_p2"] = m
    spec.loader.exec_module(m)

    for i, q in enumerate(Q, 1):
        out = HERE / "outputs" / f"p2_run{i}"
        out.mkdir(parents=True, exist_ok=True)
        cfg = m.DEFAULT_CONFIG.copy()
        cfg["external_anchor"] = dict(cfg["external_anchor"])
        cfg["external_anchor"].update({
            "enabled": True, "path": "_test_anchors.json",
            "as_evidence": "evidence", "tier_floor": 2,
        })
        cfg["output"] = dict(cfg.get("output") or {})
        cfg["output"]["save_dir"] = str(out)
        cfg["output"]["verbose"] = False
        info = {"run": i, "question": q, "src": SRC.name, "ok": False,
                "error": ""}
        buf = io.StringIO()
        t0 = time.time()
        try:
            with contextlib.redirect_stdout(buf):
                meta = m.MetaDGTF(cfg)
                res = meta.run(q, route=["0", "1"], rounds="0:3,1:3")
                md = m.save_result(res, str(out))
            ea = res.get("external_anchor") or {}
            info.update({
                "ok": True, "md": str(md),
                "calls": int(getattr(meta.llm, "total_calls", 0) or 0),
                "tokens": int(getattr(meta.llm, "total_tokens", 0) or 0),
                "triage_downgrades": ea.get("triage_downgrades"),
                "triage_items": ea.get("triage_items"),
                "anchors": ea.get("anchors"),
                "anchor_used": (ea.get("summary") or {}).get("anchor_used"),
                "blocked": ea.get("blocked_conclusions"),
                "as_evidence": ea.get("as_evidence"),
                "tier_floor": ea.get("tier_floor"),
                "und_aspects": (res.get("decidability") or {}).get(
                    "undecidable_aspects"),
            })
        except Exception as e:  # noqa: BLE001
            info["error"] = f"{type(e).__name__}: {e}"
        info["elapsed_s"] = round(time.time() - t0, 1)
        (out / "meta.json").write_bytes(json.dumps(
            info, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
        (out / "stdout.log").write_bytes(
            buf.getvalue().encode("utf-8", "replace"))
        print(f"run{i}: ok={info['ok']} triage={info.get('triage_downgrades')} "
              f"calls={info.get('calls')} err={info['error'][:60]}")
    print("P2_RUNS_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
