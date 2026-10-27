# -*- coding: utf-8 -*-
"""dual_judge 适配器 token/延迟评测（Round 135，零 API，本地 GPU）。

用法（在本地模型 env 下运行）：
  python scripts/local_model/eval_dual_judge_tokens.py \
      --adapter llm_sft/adapter_dgtf_judge_05b_v3 --vals 320 --limit 12 \
      --out docs/dual_judge_v3_eval.json
不传 --adapter 时用服务默认候选（judge_v2）。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "local_model"))


def load_eval_module():
    spec = importlib.util.spec_from_file_location(
        "eval_stage_mod",
        str(ROOT / "scripts" / "local_model" / "eval_dgtf_stage.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["eval_stage_mod"] = m
    spec.loader.exec_module(m)
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="", help="相对路径；设置 DGTF_LOCAL_ADAPTER")
    ap.add_argument("--vals", default="320", help="逗号分隔 max_new_tokens")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--out", default="docs/dual_judge_eval.json")
    args = ap.parse_args()
    if args.adapter:
        os.environ["DGTF_LOCAL_ADAPTER"] = args.adapter
    m = load_eval_module()
    ns = argparse.Namespace(model=str(m.DEFAULT_MODEL))
    t0 = time.time()
    eng = m.LocalEngine(ns, autostart=False)
    eng._load()
    if getattr(eng, "state", "") != "ready":
        print("模型加载失败:", getattr(eng, "error", ""))
        return 1
    print("loaded in %.1fs adapters=%s" % (time.time() - t0,
                                           dict(getattr(eng, "adapter_paths", {}))))
    fname, _ = m.STAGE_FILE["dual_judge"]
    rows = m.read_jsonl(m.DATA / fname)
    out = {"stage": "dual_judge", "limit": args.limit, "vals": args.vals,
           "adapter": args.adapter or "(default candidates)",
           "adapter_paths": dict(getattr(eng, "adapter_paths", {})),
           "val_rows": len(rows), "variants": {}}
    for mn in [int(x) for x in str(args.vals).split(",") if x.strip()]:
        print("\n=== max_new_tokens=%d ===" % mn, flush=True)
        res = m.run_stage(eng, "dual_judge", rows, args.limit, mn, use_adapter=True)
        out["variants"][str(mn)] = {
            k: res.get(k) for k in ("n", "json_valid_rate", "latency_ms",
                                    "gen_tokens_per_sec", "position_acc",
                                    "position_coverage", "macro_f1",
                                    "wall_sec", "errors")}
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n->", p)
    for mn, r in out["variants"].items():
        print("max_new=%s json=%s pos_acc=%s macro_f1=%s p50=%sms p95=%sms"
              % (mn, r.get("json_valid_rate"), r.get("position_acc"),
                 r.get("macro_f1"), (r.get("latency_ms") or {}).get("p50"),
                 (r.get("latency_ms") or {}).get("p95")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
