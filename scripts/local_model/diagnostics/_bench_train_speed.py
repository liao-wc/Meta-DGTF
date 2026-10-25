# -*- coding: utf-8 -*-
"""临时基准：Qwen2.5-1.5B fp16 + LoRA r16 + grad checkpoint 的 fwd+bwd 速度。

用于在写正式训练脚本前估算「每样本秒数 / 总训练时长」，决定数据量与 epochs。
用完可删。
"""
from __future__ import annotations
import json, os, time
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "local_model" / "models" / "Qwen2.5-1.5B-Instruct"


def main():
    print("CUDA", torch.cuda.is_available(), flush=True)
    torch.backends.cuda.matmul.allow_tf32 = True
    try:
        torch.backends.cuda.enable_flash_sdp(True)
    except Exception:
        pass
    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        str(MODEL), torch_dtype=torch.float16, trust_remote_code=True,
        local_files_only=True, attn_implementation="sdpa")
    print("load_sec", round(time.time() - t0, 1), flush=True)
    model.gradient_checkpointing_enable()
    model.config.use_cache = False
    lcfg = LoraConfig(r=16, lora_alpha=32,
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                      "gate_proj", "up_proj", "down_proj"],
                      lora_dropout=0.05, bias="none", task_type="CAUSAL_LM")
    model = get_peft_model(model, lcfg)
    model.to("cuda")
    model.train()
    ntr = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print("trainable_params", ntr, flush=True)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=2e-4)
    scaler = torch.amp.GradScaler("cuda", enabled=True)
    results = []
    for seq in (512, 1024, 1536):
        ids = torch.randint(0, 1000, (1, seq), device="cuda")
        labels = ids.clone()
        # warmup 2 steps
        for _ in range(2):
            with torch.amp.autocast("cuda", dtype=torch.float16):
                loss = model(input_ids=ids, labels=labels).loss
            scaler.scale(loss).backward()
            scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True)
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        n = 5
        t = time.time()
        for _ in range(n):
            with torch.amp.autocast("cuda", dtype=torch.float16):
                loss = model(input_ids=ids, labels=labels).loss
            scaler.scale(loss).backward()
            scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True)
        torch.cuda.synchronize()
        dt = (time.time() - t) / n
        peak = torch.cuda.max_memory_allocated() / 1024 ** 3
        results.append({"seq": seq, "sec_per_step": round(dt, 3),
                        "peak_gb": round(peak, 2)})
        print("SEQ", seq, "sec/step", round(dt, 3), "peak_gb", round(peak, 2),
              flush=True)
    out = ROOT / "llm_sft" / "_bench_train_speed.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("BENCH_DONE", flush=True)


if __name__ == "__main__":
    main()
