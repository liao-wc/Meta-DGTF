# -*- coding: utf-8 -*-
"""诊断：定位 1.5B fp16 训练吞吐异常（0.6 TFLOPS）的瓶颈。

分三层测：
  A. 纯 matmul —— 硬件能力上限
  B. 模型 forward only（无 checkpoint / 有 checkpoint）
  C. forward+backward（无 checkpoint / 有 checkpoint）+ optimizer
用完可删。
"""
from __future__ import annotations
import os, time
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "local_model" / "models" / "Qwen2.5-1.5B-Instruct"


def sync():
    torch.cuda.synchronize()


def bench(fn, n=3, warm=1):
    for _ in range(warm):
        fn()
    sync()
    t = time.time()
    for _ in range(n):
        fn()
    sync()
    return (time.time() - t) / n


def main():
    print("torch", torch.__version__, "cuda", torch.version.cuda, flush=True)
    p = torch.cuda.get_device_properties(0)
    print("gpu", p.name, "sm", p.multi_processor_count,
          "vram", round(p.total_memory / 1024 ** 3, 2), flush=True)

    # ---------- A. 纯 matmul ----------
    for dtype in (torch.float16, torch.float32):
        a = torch.randn(1024, 1536, device="cuda", dtype=dtype)
        b = torch.randn(1536, 1536, device="cuda", dtype=dtype)
        dt = bench(lambda: torch.matmul(a, b), n=200, warm=20)
        flops = 2 * 1024 * 1536 * 1536 / dt
        print(f"[A] matmul 1024x1536x1536 {dtype} {dt * 1e6:.1f}us "
              f"{flops / 1e12:.2f} TFLOPS", flush=True)
        del a, b
        torch.cuda.empty_cache()

    # ---------- B/C. 模型 ----------
    model = AutoModelForCausalLM.from_pretrained(
        str(MODEL), dtype=torch.float16, trust_remote_code=True,
        local_files_only=True, attn_implementation="sdpa")
    print("dtype", next(model.parameters()).dtype,
          "sdpa" if True else "", flush=True)
    model = model.to("cuda")
    for gc in (False, True):
        if gc:
            model.gradient_checkpointing_enable()
            model.config.use_cache = False
        ids = torch.randint(0, 1000, (1, 1024), device="cuda")
        torch.cuda.reset_peak_memory_stats()
        # fwd only
        model.eval()
        with torch.no_grad():
            dt_f = bench(lambda: model(input_ids=ids).logits, n=2)
        peak_f = torch.cuda.max_memory_allocated() / 1024 ** 3
        # fwd+bwd (no LoRA first: frozen backbone means no grad → wrong)
        del model
        torch.cuda.empty_cache()
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
        model.train()
        opt = torch.optim.AdamW([p for p in model.parameters()
                                 if p.requires_grad], lr=2e-4)
        labels = ids.clone()
        torch.cuda.reset_peak_memory_stats()

        def step():
            out = model(input_ids=ids, labels=labels)
            out.loss.backward()
            opt.step()
            opt.zero_grad(set_to_none=True)

        try:
            dt = bench(step, n=2, warm=1)
            peak = torch.cuda.max_memory_allocated() / 1024 ** 3
            print(f"[C] fwd+bwd+opt seq1024 gc={gc} {dt:.2f}s "
                  f"peak={peak:.2f}GB "
                  f"tok/s={1024 / dt:.1f}", flush=True)
        except torch.OutOfMemoryError:
            print(f"[C] OOM gc={gc}", flush=True)
            torch.cuda.empty_cache()
        del model, opt
        torch.cuda.empty_cache()

    # ---------- D. batch2 gc ----------
    model = AutoModelForCausalLM.from_pretrained(
        str(MODEL), dtype=torch.float16, trust_remote_code=True,
        local_files_only=True, attn_implementation="sdpa").to("cuda")
    model.gradient_checkpointing_enable()
    model.config.use_cache = False
    lcfg = LoraConfig(r=16, lora_alpha=32,
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                      "gate_proj", "up_proj", "down_proj"],
                      lora_dropout=0.05, bias="none", task_type="CAUSAL_LM")
    model = get_peft_model(model, lcfg)
    model.train()
    opt = torch.optim.AdamW([p for p in model.parameters()
                             if p.requires_grad], lr=2e-4)
    ids = torch.randint(0, 1000, (2, 1024), device="cuda")
    labels = ids.clone()
    torch.cuda.reset_peak_memory_stats()
    try:
        def step2():
            out = model(input_ids=ids, labels=labels)
            out.loss.backward()
            opt.step()
            opt.zero_grad(set_to_none=True)
        dt = bench(step2, n=2, warm=1)
        peak = torch.cuda.max_memory_allocated() / 1024 ** 3
        print(f"[D] fwd+bwd+opt bs2 seq1024 gc=True {dt:.2f}s peak={peak:.2f}GB "
              f"tok/s={2048 / dt:.1f}", flush=True)
    except torch.OutOfMemoryError:
        print("[D] OOM", flush=True)
    print("DIAG_DONE", flush=True)


if __name__ == "__main__":
    main()
