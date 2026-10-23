#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P2b.7] 三题真跑：验 answers 路径能否把 triage 打通。

用法：
    python _run_v1221_p2b.py            # 三题顺序跑
    python _run_v1221_p2b.py 2          # 只跑第 2 题（便于三题并发）

与任务书骨架的两处差别（都已在报告里说明）：
  ① 骨架写 `tri = res["external_anchor"]["triage_downgrades"]` 再 `len(tri)`
     —— 引擎里它是 **int**（`base["triage_downgrades"] = len(_tg)`），
     `len(int)` 会 TypeError。这里用 `_as_n()` 同时兼容 int / list。
  ② 加 `--only` 索引 + 每跑一份 meta.json（留痕），并把 `save_dir` 写进 cfg。

产物：outputs/p2b_<tag>/<时间戳>.md + meta.json + stdout.log
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / os.environ.get("P2B_SRC", "元DGTF-V1.22.1-rc1b.py")
ONLY = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0

Q = [
    ("老城区内涝", "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？怎么权衡？"),
    ("中小制造", "现金流紧张的中小制造企业，上自动化产线还是维持人工加局部优化？怎么决策？"),
    ("社区医院", "社区医院人力有限，慢性病管理推远程监测还是加派人手上门随访？资源怎么配？"),
]


def _as_n(v) -> int:
    """triage_downgrades 可能是 int（引擎现状）或 list（任务书骨架的假设）。"""
    if isinstance(v, bool):
        return 0
    if isinstance(v, int):
        return v
    if isinstance(v, (list, tuple)):
        return len(v)
    return 0


def _und_partial_split(res: dict) -> dict:
    """[P2b.8 观察项] und→partial 变更的分类统计。**只记录，不判 pass/fail**。

    ★ 与任务书骨架 P2b.8 的两点实测差异（已写进报告）：
      ① 骨架按 `triage_items[*]["sub_id"]` 归类，但本引擎的 triage_items 是
         `{"from","to","aspect","anchor_id"}` —— **没有 sub_id**。照写会得到
         `triage_sids = {None}`，把所有条都归进「其他」（假归类）。
      ② 更根本：triage 只产**建议清单**（`base["triage_items"]`），**没有任何
         写 `decidability_log` 的路径**（不调 `apply_decidability_change`）。
         所以「triage 引起的 und→partial」在本引擎里**结构上恒为 0** ——
         不需要按 sub_id 去筛。
    本函数因此只做**去重计数**（同一次变更会镜像到 pool 1 与 pool all）。
    """
    ea = res.get("external_anchor") or {}
    n_triage = len(ea.get("triage_items") or [])
    pools = res.get("pools") or {}
    seen, un2p, applied = set(), 0, 0
    for pn, pool in pools.items():
        for ent in ((pool or {}).get("decidability_log") or []):
            if not isinstance(ent, dict):
                continue
            if str(ent.get("status")) != "applied":
                continue
            key = (ent.get("sub_id"), ent.get("from"), ent.get("to"))
            if key in seen:            # 同一变更镜像到多个池 → 去重计数
                continue
            seen.add(key)
            applied += 1
            if (str(ent.get("from")) == "undecidable"
                    and str(ent.get("to")) == "partial"):
                un2p += 1
    return {"und_to_partial": un2p, "applied_total": applied,
            "triage_suggestions": n_triage,
            "triage_writes_log": False,
            "ratio": round(un2p / applied, 3) if applied else None}



def main() -> int:
    spec = importlib.util.spec_from_file_location("dgtf_p2b", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_p2b"] = m
    spec.loader.exec_module(m)

    todo = [(i, t, q) for i, (t, q) in enumerate(Q, 1) if not ONLY or i == ONLY]
    for i, tag, q in todo:
        out = HERE / "outputs" / f"p2b_{tag}"
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
        info = {"run": i, "tag": tag, "question": q, "src": SRC.name,
                "ok": False, "error": ""}
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
                "triage_downgrades": _as_n(ea.get("triage_downgrades")),
                "triage_items": ea.get("triage_items"),
                "anchors": ea.get("anchors"),
                "anchor_used": (ea.get("summary") or {}).get("anchor_used"),
                "as_evidence": ea.get("as_evidence"),
                "tier_floor": ea.get("tier_floor"),
                "answers_all_missing": ea.get("answers_all_missing"),
                "und_aspects": (res.get("decidability") or {}).get(
                    "undecidable_aspects"),
                "drift": _und_partial_split(res),
            })
        except Exception as e:  # noqa: BLE001
            info["error"] = f"{type(e).__name__}: {e}"
        info["elapsed_s"] = round(time.time() - t0, 1)
        (out / "meta.json").write_bytes(json.dumps(
            info, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
        (out / "stdout.log").write_bytes(
            buf.getvalue().encode("utf-8", "replace"))
        print(f"[{tag}] ok={info['ok']} triage={info.get('triage_downgrades')} "
              f"calls={info.get('calls')} err={info['error'][:70]}")
    print("P2B_RUNS_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
