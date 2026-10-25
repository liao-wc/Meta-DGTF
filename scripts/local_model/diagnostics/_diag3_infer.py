# -*- coding: utf-8 -*-
"""诊断 3：推理（生成）速度 —— fp16 vs fp32-cast，prefill/decode 分解。

服务延迟预算决定量：p50 单次 self_check 调用 = prefill + decode。
用完可删。
"""
from __future__ import annotations
import os, time
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "local_model" / "models" / "Qwen2.5-1.5B-Instruct"


def load(fp16=True):
    tok = AutoTokenizer.from_pretrained(str(MODEL), trust_remote_code=True,
                                        local_files_only=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    m = AutoModelForCausalLM.from_pretrained(
        str(MODEL), dtype=torch.float16, trust_remote_code=True,
        local_files_only=True, attn_implementation="sdpa").to("cuda")
    m.eval()
    m.config.use_cache = True
    return tok, m


def timed(fn, n=3):
    fn()
    torch.cuda.synchronize()
    t = time.time()
    for _ in range(n):
        fn()
    torch.cuda.synchronize()
    return (time.time() - t) / n


def main():
    tok, model = load()
    print("loaded", flush=True)
    for n_prompt in (512, 1200, 1800):
        ids = tok("【锚点】\n" + "测试上下文。" * 400,
                  return_tensors="pt", truncation=True,
                  max_length=n_prompt).to("cuda")
        L = ids["input_ids"].shape[1]
        torch.cuda.reset_peak_memory_stats()
        with torch.inference_mode():
            dt = timed(lambda: model(**ids), n=2)
        peak = torch.cuda.max_memory_allocated() / 1024 ** 3
        print(f"[fp16] prefill {L} tok: {dt:.2f}s -> {L/dt:.0f} tok/s "
              f"peak={peak:.2f}GB", flush=True)
    # decode：greedy 64 新 token
    ids = tok("【锚点】\n" + "测试上下文。" * 300, return_tensors="pt",
              truncation=True, max_length=1200).to("cuda")
    L = ids["input_ids"].shape[1]
    torch.cuda.reset_peak_memory_stats()
    with torch.inference_mode():
        t = time.time()
        out = model.generate(input_ids=ids, max_new_tokens=64,
                             do_sample=False, pad_token_id=tok.pad_token_id)
        torch.cuda.synchronize()
        gen_t = time.time() - t
    peak = torch.cuda.max_memory_allocated() / 1024 ** 3
    print(f"[fp16] decode 64 tok (prompt {L}): {gen_t:.2f}s -> "
          f"{64/gen_t:.1f} tok/s peak={peak:.2f}GB", flush=True)

    # fp32-cast 版本
    import torch.nn as nn
    import torch.nn.functional as F

    def enable_fp32_compute(model):
        def _fwd(self, x, *args, **kwargs):
            w = self.weight
            b = self.bias
            with torch.amp.autocast("cuda", enabled=False):
                y = F.linear(x.float(), w.float(),
                             b.float() if b is not None else None)
            return y.to(w.dtype)
        n = 0
        for name, m in model.named_modules():
            if isinstance(m, nn.Linear) and not name.endswith("lm_head"):
                m.forward = _fwd.__get__(m)
                n += 1
        return n

    # 重新加载干净模型
    del model
    torch.cuda.empty_cache()
    tok, model = load()
    n = enable_fp32_compute(model)
    print("fp32-cast patched", n, flush=True)
    ids = tok("【锚点】\n" + "测试上下文。" * 300, return_tensors="pt",
              truncation=True, max_length=1800).to("cuda")
    L = ids["input_ids"].shape[1]
    torch.cuda.reset_peak_memory_stats()
    with torch.inference_mode():
        dt = timed(lambda: model(**ids), n=2)
    peak = torch.cuda.max_memory_allocated() / 1024 ** 3
    print(f"[fp32cast] prefill {L} tok: {dt:.2f}s -> {L/dt:.0f} tok/s "
          f"peak={peak:.2f}GB", flush=True)
    with torch.inference_mode():
        t = time.time()
        out = model.generate(input_ids=ids, max_new_tokens=32,
                             do_sample=False, pad_token_id=tok.pad_token_id)
        torch.cuda.synchronize()
        gen_t = time.time() - t
    print(f"[fp32cast] decode 32 tok (prompt {L}): {gen_t:.2f}s -> "
          f"{32/gen_t:.1f} tok/s", flush=True)
    print("DIAG3_DONE", flush=True)


if __name__ == "__main__":
    main()
