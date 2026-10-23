#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段4 证据] 只跑带锚点的那一题（evidence 档 + tier 门）。

用法：python _run_p4_only.py <src.py>
"""
from __future__ import annotations
import contextlib, importlib.util, io, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / (sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.22.0.py")
OUT = HERE / "runs" / "v122" / "p4_anchored"
Q = "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵措施？"


def main() -> int:
    for line in (HERE / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    spec = importlib.util.spec_from_file_location("dgtf_p4", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_p4"] = m
    spec.loader.exec_module(m)
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = m.load_config(str(HERE / "dgtf_config.yaml"))
    cfg["output"]["verbose"] = False
    cfg["output"]["save_dir"] = str(OUT)
    cfg["cost_profile"] = "economy"
    ea = dict(cfg.get("external_anchor") or {})
    ea.update({"enabled": True, "path": "_test_anchors.json",
               "as_evidence": "evidence", "tier_floor": 2,
               "max_items": 4, "per_round": 2})
    cfg["external_anchor"] = ea
    buf = io.StringIO()
    t0 = time.time()
    info = {"tag": "p4_anchored", "src": SRC.name, "question": Q,
            "ok": False, "error": ""}
    try:
        with contextlib.redirect_stdout(buf):
            meta = m.MetaDGTF(cfg)
            res = meta.run(Q, route=["0", "1"], rounds="0:3,1:3",
                           parallel_mode="serial", orientation="decision")
            md = m.save_result(res, str(OUT))
        ea_r = res.get("external_anchor") or {}
        sm = ea_r.get("summary") or {}
        sq = ((res.get("pools") or {}).get("1") or {}).get(
            "sub_questions") or []
        info.update({"ok": True, "md": str(md),
                     "calls": int(getattr(meta.llm, "total_calls", 0) or 0),
                     "tokens": int(getattr(meta.llm, "total_tokens", 0) or 0),
                     "as_evidence": ea_r.get("as_evidence"),
                     "tier_floor": ea_r.get("tier_floor"),
                     "anchors": ea_r.get("anchors"),
                     "pooled": ea_r.get("pooled"),
                     "claims": sm.get("claims"),
                     "supported": sm.get("supported"),
                     "conflicted": sm.get("conflicted"),
                     "unmatched": sm.get("unmatched"),
                     "anchor_used": sm.get("anchor_used"),
                     "triage_downgrades": ea_r.get("triage_downgrades"),
                     "triage_items": ea_r.get("triage_items"),
                     "blocked": ea_r.get("blocked_conclusions"),
                     "anchor_err": ea_r.get("error"),
                     "n_sub_questions": len(sq),
                     "citation_has_X": None})
        info["citation_has_X"] = [c for c, _ in m._citation_table(
            None, (meta.pools or {}).get("1") or m.Pool())
            if str(c).startswith("X")][:12] if False else None
        (OUT / "packed.json").write_bytes(json.dumps(
            res, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
    info["elapsed_s"] = round(time.time() - t0, 1)
    (OUT / "stdout.log").write_bytes(buf.getvalue().encode("utf-8", "replace"))
    (OUT / "meta.json").write_bytes(json.dumps(
        info, ensure_ascii=False, indent=2).encode("utf-8"))
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0 if info["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
