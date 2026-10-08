#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 证据批次] 阶段 2 / 3 / 4 的真跑证据（一次跑齐，落 runs/v122/）。

产出：
  runs/v122/p2_consistency_1..3/    三态多票一致率（route=1，4 圈）
  runs/v122/p3_decision_1..3/       decision 行动闭环（四层，3/3/3/4 圈）
  runs/v122/p4_anchored/            外部锚点五档（tier=1 两条）
  runs/v122/_summary.json           每题 calls / tokens / 关键指标

★ 成本说明：任务书给的原始档（balanced + 5~6 圈四层）单题约 3 倍于此。
  这里用 economy + 缩短一圈，目的是**拿证据**而不是压测；原始档已在
  阶段 1 的 3 题真跑（bench/runs/p1v2）上验过。差异在报告里如实写。
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
SRC = HERE / "元DGTF-V1.22.0-rc1.py"
OUT = HERE / "runs" / "v122"
SUMMARY = {}

QUESTIONS_P2 = "订单系统要保证不超卖又要不卡顿。CAP 约束下，下单链路怎么设计？"
QUESTIONS_P3 = [
    "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？怎么权衡？",
    "现金流紧张的中小制造企业，上自动化产线还是维持人工加局部优化？怎么决策？",
    "社区医院人力有限，慢性病管理推远程监测还是加派人手上门随访？资源怎么配？",
]
Q_P4 = "老城区暴雨内涝频发，排水系统重建还是局部改造加海绵措施？"


def load_dotenv():
    p = HERE / ".env"
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def load_engine():
    spec = importlib.util.spec_from_file_location("dgtf_ev", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_ev"] = m
    spec.loader.exec_module(m)
    return m


def run_one(m, tag, question, route, rounds, profile="economy",
            patch_cfg=None):
    out = OUT / tag
    out.mkdir(parents=True, exist_ok=True)
    cfg = m.load_config(str(HERE / "dgtf_config.yaml"))
    cfg["output"]["verbose"] = False
    cfg["output"]["save_dir"] = str(out)
    cfg["cost_profile"] = profile
    if patch_cfg:
        patch_cfg(cfg)
    buf = io.StringIO()
    t0 = time.time()
    info = {"tag": tag, "question": question, "route": route,
            "rounds": rounds, "profile": profile, "ok": False, "error": ""}
    try:
        with contextlib.redirect_stdout(buf):
            meta = m.MetaDGTF(cfg)
            res = meta.run(question, route=route, rounds=rounds,
                           parallel_mode="serial", orientation="decision")
            md = m.save_result(res, str(out))
        info["ok"] = True
        info["md"] = str(md)
        info["calls"] = int(getattr(meta.llm, "total_calls", 0) or 0)
        info["tokens"] = int(getattr(meta.llm, "total_tokens", 0) or 0)
        info["layers"] = sorted((res.get("views") or {}).keys())
        sq = ((res.get("pools") or {}).get("1") or {}).get(
            "sub_questions") or []
        info["n_subs"] = len(sq)
        info["stability"] = {
            "high": sum(1 for s in sq if s.get("stability") == "high"),
            "medium": sum(1 for s in sq if s.get("stability") == "medium"),
            "low": sum(1 for s in sq if s.get("stability") == "low")}
        info["tri_consensus"] = res.get("tri_consensus")
        info["calibration_queue"] = len(res.get("calibration_queue") or [])
        info["freeze_sig_len"] = len(
            str((res.get("freeze") or {}).get("signature") or ""))
        v1 = (res.get("views") or {}).get("1") or {}
        info["n_actions"] = len(v1.get("_actions") or [])
        info["n_not_do"] = len(v1.get("_not_do") or [])
        info["view1_errors"] = list(v1.get("errors") or [])[:6]
        info["quality_flags"] = list(v1.get("quality_flags") or [])
        ea = res.get("external_anchor") or {}
        info["as_evidence"] = ea.get("as_evidence")
        info["tier_floor"] = ea.get("tier_floor")
        info["triage_downgrades"] = ea.get("triage_downgrades")
        info["conflicts"] = (ea.get("summary") or {}).get("conflicted")
        info["anchor_used"] = (ea.get("summary") or {}).get("anchor_used")
        info["pool1_meta"] = [x for x in
                              ((res.get("pools") or {}).get("1") or {}
                               ).get("meta") or []
                              if "锚点" in str(x)][:4]
        (out / "packed.json").write_bytes(json.dumps(
            res, ensure_ascii=False, indent=2, default=str).encode("utf-8"))
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
    info["elapsed_s"] = round(time.time() - t0, 1)
    (out / "stdout.log").write_bytes(buf.getvalue().encode("utf-8", "replace"))
    (out / "meta.json").write_bytes(json.dumps(
        info, ensure_ascii=False, indent=2).encode("utf-8"))
    print(f"  [{tag}] ok={info['ok']} calls={info.get('calls')} "
          f"{info['elapsed_s']}s {info['error'][:80]}")
    return info


def main() -> int:
    load_dotenv()
    OUT.mkdir(parents=True, exist_ok=True)
    m = load_engine()
    print(f"═══ v122 证据批次 · {SRC.name} ═══")

    # 阶段 2：一致率（route=1，4 圈，跑 3 次同条件）
    for i in (1, 2, 3):
        SUMMARY[f"p2_{i}"] = run_one(m, f"p2_consistency_{i}", QUESTIONS_P2,
                                    ["1"], "1:4")

    # 阶段 3：decision 三题（四层）
    for i, q in enumerate(QUESTIONS_P3, 1):
        SUMMARY[f"p3_{i}"] = run_one(
            m, f"p3_decision_{i}", q, ["0", "1", "both", "all"],
            "0:3,1:3,both:3,all:4")

    # 阶段 4：外部锚点（tier=1 两条，as_evidence=evidence）
    def _patch(cfg):
        ea = dict(cfg.get("external_anchor") or {})
        ea.update({"enabled": True, "path": "_test_anchors.json",
                   "as_evidence": "evidence", "tier_floor": 2,
                   "max_items": 4, "per_round": 2})
        cfg["external_anchor"] = ea

    SUMMARY["p4"] = run_one(m, "p4_anchored", Q_P4, ["0", "1"], "0:3,1:3",
                            patch_cfg=_patch)

    (OUT / "_summary.json").write_bytes(json.dumps(
        SUMMARY, ensure_ascii=False, indent=2).encode("utf-8"))
    ok = sum(1 for v in SUMMARY.values() if v.get("ok"))
    print(f"完成：{ok}/{len(SUMMARY)} 题成功 → runs/v122/")
    return 0 if ok == len(SUMMARY) else 2


if __name__ == "__main__":
    sys.exit(main())
