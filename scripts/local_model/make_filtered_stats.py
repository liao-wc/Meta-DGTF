# -*- coding: utf-8 -*-
"""生成「过滤后训练集」统计（零 GPU）：drop-truncated + min 变体 + max_len 2048。

供 Lead 审核第二轮训练计划：样本数、被丢弃条数、prompt/target token 分布、
按 phase/问题分布。输出 llm_sft/dgtf_stage/dataset_stats_filtered.json。
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "local_model"))

import train_dgtf_stage_lora as tdl  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402

DATA = ROOT / "llm_sft" / "dgtf_stage"
MODEL = ROOT / "local_model" / "models" / "Qwen2.5-0.5B-Instruct"


def pctl(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * q))] if xs else 0


def stats_of(rows):
    plens = [r["prompt_len"] for r in rows]
    tlens = [r["target_len"] for r in rows]
    tot = [r["prompt_len"] + r["target_len"] for r in rows]
    return {
        "n": len(rows),
        "prompt_tokens": {"p50": pctl(plens, .5), "p95": pctl(plens, .95),
                          "max": max(plens) if plens else 0},
        "target_tokens": {"p50": pctl(tlens, .5), "p95": pctl(tlens, .95),
                          "max": max(tlens) if tlens else 0},
        "total_tokens": {"p50": pctl(tot, .5), "p95": pctl(tot, .95),
                         "max": max(tot) if tot else 0,
                         "mean": round(sum(tot) / max(1, len(tot)), 1)},
        "truncated": sum(1 for r in rows if r["truncated"]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DATA / "dataset_stats_filtered.json"))
    ap.add_argument("--max-len", type=int, default=2048)
    args = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(str(MODEL), trust_remote_code=True,
                                        local_files_only=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    out = {"filter_policy": {
        "max_len": args.max_len,
        "drop_truncated": True,
        "note": "超长样本直接丢弃（不中段切候选）；由 train_dgtf_stage_lora "
                "--drop-truncated 执行"},
        "tokenizer": str(MODEL.relative_to(ROOT)), "stages": {}}
    # self_check min：478 条全量里按 Lead 要求取 180
    rows = [json.loads(x) for x in
            (DATA / "self_check_min_train.jsonl")
            .read_text(encoding="utf-8").splitlines() if x.strip()]
    tok_rows = [r for r in (tdl.build_token(tok, x, args.max_len)
                            for x in rows) if r]
    keep = [r for r in tok_rows if not r["truncated"]][:180]
    out["stages"]["self_check_min"] = {
        "available": len(rows), "after_drop_truncated": len(
            [r for r in tok_rows if not r["truncated"]]),
        "planned_train": len(keep), **stats_of(keep),
        "label_dist": dict(Counter(
            json.loads(x["messages"][-1]["content"]).get("unsaid_is_escape")
            for x in rows)),
    }
    # dual_judge：取 110
    rows = [json.loads(x) for x in
            (DATA / "dual_judge_train.jsonl")
            .read_text(encoding="utf-8").splitlines() if x.strip()]
    tok_rows = [r for r in (tdl.build_token(tok, x, args.max_len)
                            for x in rows) if r]
    keep = [r for r in tok_rows if not r["truncated"]][:110]
    out["stages"]["dual_judge"] = {
        "available": len(rows),
        "after_drop_truncated": len([r for r in tok_rows
                                     if not r["truncated"]]),
        "planned_train": len(keep), **stats_of(keep),
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print("FILTERED_STATS_OK")


if __name__ == "__main__":
    main()
