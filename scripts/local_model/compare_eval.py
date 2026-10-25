# -*- coding: utf-8 -*-
"""本地模型评测对比脚本：并排比较两个 eval_dgtf_stage*.json（如 v6 vs v8b）。

用法：
  python scripts/local_model/compare_eval.py llm_sft/eval_dgtf_stage_05b_v6_limit30.json llm_sft/eval_dgtf_stage_05b_v5_limit30.json
输出关键指标表 + 判定（新候选是否在「JSON/字段/escape/延迟」上不劣且至少一项更好）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KEYS = ("json_valid_rate", "decision_field_mean_acc", "unsaid_is_escape_acc",
        "susp_f1", "ing_rephrased_acc", "decision_all3_acc", "susp_set_acc")


def _load(path: str) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    a = d.get("adapter")
    if isinstance(a, dict) and "json_valid_rate" in a:
        return a
    # 新版 eval：stages dict（self_check_min / self_check / dual_judge）
    stages = d.get("stages")
    if isinstance(stages, dict):
        cand = stages.get("self_check_min") or stages.get("self_check")
        if isinstance(cand, dict) and "json_valid_rate" in cand:
            return cand
        for v in stages.values():
            if isinstance(v, dict) and "json_valid_rate" in v:
                return v
    if isinstance(stages, list):
        best = None
        for st in stages:
            if not isinstance(st, dict) or "json_valid_rate" not in st:
                continue
            if best is None or int(st.get("n") or 0) > int(best.get("n") or 0):
                best = st
        if best is not None:
            return best
    if "json_valid_rate" in d:
        return d
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("baseline")
    args = ap.parse_args()
    c = _load(args.candidate)
    b = _load(args.baseline)
    print("%-28s %12s %12s %10s" % ("metric", "candidate", "baseline", "delta"))
    worse = []
    better = []
    for k in KEYS:
        cv, bv = c.get(k), b.get(k)
        try:
            cv = float(cv)
            bv = float(bv)
        except (TypeError, ValueError):
            print("%-28s %12s %12s %10s" % (k, cv, bv, "-"))
            continue
        delta = cv - bv
        print("%-28s %12.4f %12.4f %+10.4f" % (k, cv, bv, delta))
        # 噪声容差：susp_f1 等小样本指标 ±0.02 内视为持平
        _noise = 0.02 if k in ("susp_f1", "ing_rephrased_acc",
                               "unsaid_is_escape_acc") else 1e-9
        if delta < -_noise:
            worse.append((k, delta))
        elif delta > _noise:
            better.append((k, delta))
    for k, get in (("p50_ms", lambda x: (x.get("latency_ms") or {}).get("p50")),
                   ("p95_ms", lambda x: (x.get("latency_ms") or {}).get("p95"))):
        cv, bv = get(c), get(b)
        try:
            cv, bv = float(cv), float(bv)
        except (TypeError, ValueError):
            print("%-28s %12s %12s %10s" % (k, cv, bv, "-"))
            continue
        delta = cv - bv
        print("%-28s %12.1f %12.1f %+10.1f" % (k, cv, bv, delta))
        # 延迟：候选更慢 >5% 记为 worse（可配置）
        if delta > 0.05 * max(bv, 1.0):
            worse.append((k, delta))
        elif delta < -1e-9:
            better.append((k, delta))
    print("\ncandidate better:", better)
    print("candidate worse:", worse)
    ok = (not worse) and bool(better)
    print("VERDICT:", "SWITCH_CANDIDATE" if ok else "KEEP_BASELINE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
