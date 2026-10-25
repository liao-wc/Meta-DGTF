# -*- coding: utf-8 -*-
"""诊断 2：fp16 权重 + fp32 计算（manual mixed precision）能否救训练吞吐。

背景：[A] 实测 fp16 matmul 0.54 TFLOPS vs fp32 matmul 2.47 TFLOPS
（GTX 1660 Ti / SM75 无 tensor core，cuBLAS 12.6 的 HGEMM 在该架构上极慢）。
若把 Linear 的 matmul 用 fp32 做、激活仍是 fp16（省显存），fwd+bwd 有望 3-4x。
用完可删。
"""
from __future__ import annotations
import functools
import os, time
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
import torch.nn as nn
import torch.nn.functional as F
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "local_model" / "models" / "Qwen2.5-1.5B-Instruct"


def bench(fn, n=3, warm=1):
    for _ in range(warm):
        fn()
    torch.cuda.synchronize()
    t = time.time()
    for _ in range(n):
        fn()
    torch.cuda.synchronize()
    return (time.time() - t) / n


def enable_fp32_compute(model, skip_names=("lm_head",)):
    """把 Linear 的 matmul 改成 fp32 计算、输出转回输入 dtype。

    激活/参数仍是 fp16（显存不变），只在 GEMM 里临时 upcast 权重（~12MB/层）。
    """
    n = 0

    def _fwd(self, x, *args, **kwargs):
        w = self.weight
        b = self.bias
        y = F.linear(x.float(), w.float(),
                     b.float() if b is not None else None)
        return y.to(x.dtype)

    for name, m in model.named_modules():
        if not isinstance(m, nn.Linear):
            continue
        if any(name.endswith(s) or name == s for s in skip_names):
            continue
        m.forward = functools.partial(_fwd, m)
        n += 1
    return n


def main():
    print("torch", torch.__version__, flush=True)
    for gc in (True,):
        model = AutoModelForCausalLM.from_pretrained(
            str(MODEL), dtype=torch.float16, trust_remote_code=True,
            local_files_only=True, attn_implementation="sdpa").to("cuda")
        if gc:
            model.gradient_checkpointing_enable()
            model.config.use_cache = False
        lcfg = LoraConfig(r=16, lora_alpha=32,
                          target_modules=["q_proj", "k_proj", "v_proj",
                                          "o_proj", "gate_proj", "up_proj",
                                          "down_proj"],
                          lora_dropout=0.05, bias="none",
                          task_type="CAUSAL_LM")
        model = get_peft_model(model, lcfg)
        n = enable_fp32_compute(model)
        print(f"[patch] linear layers patched={n} gc={gc}", flush=True)
        model.train()
        opt = torch.optim.AdamW([p for p in model.parameters()
                                 if p.requires_grad], lr=2e-4)

        def make_step(seq):
            ids = torch.randint(0, 1000, (1, seq), device="cuda")
            labels = ids.clone()

            def step():
                out = model(input_ids=ids, labels=labels)
                out.loss.backward()
                opt.step()
                opt.zero_grad(set_to_none=True)
            return step

        for seq in (1024, 1536):
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            try:
                dt = bench(make_step(seq), n=2, warm=1)
                peak = torch.cuda.max_memory_allocated() / 1024 ** 3
                print(f"[E] fp32-cast fwd+bwd seq{seq} gc={gc} {dt:.2f}s "
                      f"peak={peak:.2f}GB tok/s={seq / dt:.1f}", flush=True)
            except torch.OutOfMemoryError:
                print(f"[E] OOM seq{seq} gc={gc}", flush=True)
                torch.cuda.empty_cache()

        # 生成速度参考（fp16 vs fp32-cast）
        model.eval()
        ids = torch.randint(0, 1000, (1, 512), device="cuda")
        with torch.inference_mode():
            t = time.time()
            out = model.generate(input_ids=ids, max_new_tokens=48,
                                 do_sample=False,
                                 pad_token_id=0)
            torch.cuda.synchronize()
            gen_t = time.time() - t
        print(f"[F] generate 48 tok (prompt512) fp32-cast {gen_t:.2f}s "
              f"({48 / gen_t:.1f} tok/s decode)", flush=True)
        del model, opt
        torch.cuda.empty_cache()
    print("DIAG2_DONE", flush=True)


if __name__ == "__main__":
    main()
