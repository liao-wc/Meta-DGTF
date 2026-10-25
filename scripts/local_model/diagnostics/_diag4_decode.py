# -*- coding: utf-8 -*-
"""诊断 4：fp16 decode 速度 + 手动 prefill(fp32-cast)+decode(fp16) 混合方案的可行性。"""
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
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "local_model" / "models" / "Qwen2.5-1.5B-Instruct"


def patch_fp32(model):
    orig = []

    def _fwd(self, x, *args, **kwargs):
        w = self.weight
        b = self.bias
        with torch.amp.autocast("cuda", enabled=False):
            y = F.linear(x.float(), w.float(),
                         b.float() if b is not None else None)
        return y.to(w.dtype)

    for name, m in model.named_modules():
        if isinstance(m, nn.Linear) and not name.endswith("lm_head"):
            orig.append((m, m.forward))
            m.forward = functools.partial(_fwd, m)
    return orig


def unpatch(orig):
    for m, f in orig:
        m.forward = f


def main():
    tok = AutoTokenizer.from_pretrained(str(MODEL), trust_remote_code=True,
                                        local_files_only=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        str(MODEL), dtype=torch.float16, trust_remote_code=True,
        local_files_only=True, attn_implementation="sdpa").to("cuda")
    model.eval()
    prompt = "【锚点】\n" + "测试上下文。" * 400
    ids = tok(prompt, return_tensors="pt", truncation=True,
              max_length=1700).to("cuda")
    L = ids["input_ids"].shape[1]

    # ---- 1. 纯 fp16 decode（greedy, 32 tok）----
    with torch.inference_mode():
        t = time.time()
        out = model.generate(input_ids=ids["input_ids"], max_new_tokens=32,
                             do_sample=False,
                             pad_token_id=tok.pad_token_id)
        torch.cuda.synchronize()
        dt = time.time() - t
    print(f"[fp16] generate 32 tok (prompt {L}): {dt:.2f}s -> "
          f"{32/dt:.1f} tok/s (含 prefill {L*0.006:.1f}s)", flush=True)

    # ---- 2. 混合：fp32-cast prefill + fp16 decode ----
    orig = patch_fp32(model)
    with torch.inference_mode():
        t0 = time.time()
        outs = model(input_ids=ids["input_ids"], use_cache=True)
        torch.cuda.synchronize()
        pre_t = time.time() - t0
    logits = outs.logits[:, -1, :]
    past = outs.past_key_values
    nxt = logits.argmax(-1, keepdim=True)
    unpatch(orig)
    gen = []
    attn_len = L
    with torch.inference_mode():
        t1 = time.time()
        for i in range(32):
            o = model(input_ids=nxt, past_key_values=past, use_cache=True)
            past = o.past_key_values
            nxt = o.logits[:, -1, :].argmax(-1, keepdim=True)
            gen.append(int(nxt))
        torch.cuda.synchronize()
        dec_t = time.time() - t1
    print(f"[mixed] prefill {L} fp32-cast: {pre_t:.2f}s -> "
          f"{L/pre_t:.0f} tok/s; fp16 decode 32 tok: {dec_t:.2f}s -> "
          f"{32/dec_t:.1f} tok/s; total={pre_t+dec_t:.2f}s", flush=True)
    print("sample:", tok.decode(gen[:16], skip_special_tokens=True), flush=True)
    print("DIAG4_DONE", flush=True)


if __name__ == "__main__":
    main()
