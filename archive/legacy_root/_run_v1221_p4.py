#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P4.2] 一致率 ON/OFF 对照（同题同配置，各 3 次）。

用法：
    python _run_v1221_p4.py ON       # 跑 ON 组 3 次
    python _run_v1221_p4.py OFF      # 跑 OFF 组 3 次
    python _run_v1221_p4.py BOTH     # 顺序跑两组（慢，但省心）

与任务书骨架的差别（已写进报告）：
  ① 骨架用 `subprocess` + 环境变量 `DGTF_TRI_MULTI_VOTE`；本引擎**没有**该
     环境变量的读取路径。任务书自己已注明「上面骨架里的 --actions-off 是错的
     …… 实际脚本要传的是 tri_multi_vote 的环境变量**或配置覆盖**」
     —— 这里走**配置覆盖**（`cfg["actions"]["tri_multi_vote"]`），
     不新造 env→config 机制。
  ② 骨架 `tri = ...` 后再 `len()`：`triage_downgrades` 是 int，见 P2b 报告。
  ③ 一致率**同时**取两条口径：结构化（packed 的 `stability` 计数）与
     任务书要求的 md 正则（`三态多票：high N / medium N / low N（共 N 条）`），
     两者对不上就在报告里如实写。

产物：runs/v1221/p4_{ON,OFF}_{1..3}/ + meta.json + stdout.log
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
SRC = HERE / os.environ.get("P4_SRC", "元DGTF-V1.22.1-rc2.py")
Q = "订单系统要保证不超卖又要不卡顿。CAP 约束下，下单链路怎么设计？"
MD_RE = re.compile(r"三态多票.*?high (\d+).*?medium (\d+).*?low (\d+)"
                   r".*?共 (\d+)")


def _parse_md(md: Path):
    """任务书 Step P4.3 的 md 口径（照抄它的正则）。"""
    try:
        t = md.read_text(encoding="utf-8")
    except Exception:
        return None
    m = MD_RE.search(t)
    if not m:
        return None
    hi, me, lo, tot = map(int, m.groups())
    return {"high": hi, "medium": me, "low": lo, "total": tot,
            "consistency": ((hi + me) / tot) if tot else None}


def _structured(res: dict):
    """结构化口径：直接从 packed 的 sub_questions 数 stability。"""
    sq = (((res.get("pools") or {}).get("1") or {})
          .get("sub_questions") or [])
    hi = sum(1 for s in sq if s.get("stability") == "high")
    me = sum(1 for s in sq if s.get("stability") == "medium")
    lo = sum(1 for s in sq if s.get("stability") == "low")
    return {"high": hi, "medium": me, "low": lo, "total": len(sq),
            "consistency": ((hi + me) / len(sq)) if sq else None}


def run_arm(m: dict, arm: str, i: int) -> dict:
    out = HERE / "runs" / "v1221" / ("p4_" + arm + "_" + str(i))
    out.mkdir(parents=True, exist_ok=True)
    cfg = m.DEFAULT_CONFIG.copy()
    cfg["actions"] = dict(cfg.get("actions") or {})
    cfg["actions"]["tri_multi_vote"] = (arm == "ON")
    cfg["output"] = dict(cfg.get("output") or {})
    cfg["output"]["save_dir"] = str(out)
    cfg["output"]["verbose"] = False
    buf = io.StringIO()
    t0 = time.time()
    info = {"arm": arm, "rep": i, "ok": False, "error": "",
            "tri_multi_vote": cfg["actions"]["tri_multi_vote"]}
    try:
        with contextlib.redirect_stdout(buf):
            meta = m.MetaDGTF(cfg)
            res = meta.run(Q, route=["1"], rounds="1:4",
                           parallel_mode="serial")
            md = m.save_result(res, str(out))
        info.update({"ok": True, "md": str(md),
                     "calls": int(getattr(meta.llm, "total_calls", 0) or 0),
                     "tokens": int(getattr(meta.llm, "total_tokens", 0) or 0),
                     "md_reading": _parse_md(Path(md)),
                     "structured": _structured(res),
                     "tri_consensus": res.get("tri_consensus")})
    except Exception as e:  # noqa: BLE001
        info["error"] = type(e).__name__ + ": " + str(e)
    info["elapsed_s"] = round(time.time() - t0, 1)
    (out / "meta.json").write_bytes(json.dumps(
        info, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
    (out / "stdout.log").write_bytes(
        buf.getvalue().encode("utf-8", "replace"))
    print("[" + arm + " " + str(i) + "] ok=" + str(info["ok"])
          + " calls=" + str(info.get("calls"))
          + " md=" + json.dumps(info.get("md_reading"), ensure_ascii=False)
          + " err=" + str(info["error"])[:60])
    return info


def main() -> int:
    which = (sys.argv[1] if len(sys.argv) > 1 else "BOTH").upper()
    spec = importlib.util.spec_from_file_location("dgtf_p4", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_p4"] = m
    spec.loader.exec_module(m)
    arms = ["ON", "OFF"] if which == "BOTH" else [which]
    for arm in arms:
        for i in (1, 2, 3):
            run_arm(m, arm, i)
    print("P4_" + which + "_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
