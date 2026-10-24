# -*- coding: utf-8 -*-
"""本地 LLM 基线：加载本地小模型并测生成时延/吞吐（只读，不写业务数据）。

用本地模型环境运行：
  local_model/envs/dgtf_llm_env/Scripts/python.exe scripts/local_llm_bench.py
可选 --model deepseek15（默认 qwen05） --device cuda/cpu --json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = {
    "qwen05": ROOT / "local_model" / "models" / "Qwen2.5-0.5B-Instruct",
    "deepseek15": ROOT / "local_model" / "models" / "DeepSeek-R1-Distill-Qwen-1.5B",
}
PROMPTS = [
    "用一句话解释城市热岛效应为什么在夜间更明显。",
    "四层螺旋推理里，研究层和对撞层分别负责什么？",
    "给出一个判断证据是否可判定的简单判据。",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen05", choices=sorted(MODELS))
    ap.add_argument("--device", default="auto", choices=("auto", "cuda", "cpu"))
    ap.add_argument("--max-new-tokens", type=int, default=32)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    path = MODELS[args.model]
    if not path.exists():
        print(json.dumps({"ok": False, "error": "model missing: " + str(path)}))
        return 1
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    t0 = time.perf_counter()
    tok = AutoTokenizer.from_pretrained(str(path), trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        str(path), torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        trust_remote_code=True).to(device)
    model.eval()
    load_s = time.perf_counter() - t0
    gens = []
    for p in PROMPTS:
        messages = [{"role": "user", "content": p}]
        text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tok([text], return_tensors="pt").to(device)
        t1 = time.perf_counter()
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=args.max_new_tokens,
                                 do_sample=False, temperature=0.0,
                                 pad_token_id=tok.eos_token_id)
        dt = time.perf_counter() - t1
        n_new = int(out.shape[1] - inputs["input_ids"].shape[1])
        gens.append({"prompt": p, "seconds": round(dt, 3),
                     "new_tokens": n_new,
                     "tokens_per_s": round(n_new / dt, 1) if dt > 0 else None})
        try:
            del inputs, out
        except Exception:
            pass
    if device == "cuda":
        torch.cuda.empty_cache()
    res = {"ok": True, "model": args.model, "device": device,
           "load_seconds": round(load_s, 2), "generations": gens,
           "latency_p50_s": round(statistics.median([g["seconds"] for g in gens]), 3),
           "tokens_per_s_p50": round(statistics.median([g["tokens_per_s"] for g in gens]), 1)}
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print("model=%s device=%s load=%.2fs" % (args.model, device, load_s))
        for g in gens:
            print("  %.2fs  %d tok  %.1f tok/s" % (g["seconds"], g["new_tokens"], g["tokens_per_s"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
