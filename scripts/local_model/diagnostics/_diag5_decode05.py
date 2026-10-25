# -*- coding: utf-8 -*-
"""诊断 5：0.5B decode 为何只有 ~6.5 tok/s？对比 fp16 decode vs fp32-cast decode，
并校验 service 的 patch 还原是否彻底（用 CPU 侧模块检查，不占显存）。"""
from __future__ import annotations
import functools
import os, time
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
MPATH = ROOT / "local_model" / "models" / "Qwen2.5-0.5B-Instruct"


def patch_model(model):
    import torch.nn.functional as F

    def _fwd(self, x, *args, **kwargs):
        w = self.weight
        b = self.bias
        with torch.amp.autocast("cuda", enabled=False):
            y = F.linear(x.float(), w.float(),
                         b.float() if b is not None else None)
        return y.to(w.dtype)

    seen, patches = set(), []
    for name, m in model.named_modules():
        if not isinstance(m, nn.Linear) or name.endswith("lm_head"):
            continue
        if id(m) in seen:
            continue
        seen.add(id(m))
        patches.append((m, m.forward, functools.partial(_fwd, m)))
    return patches


def set_fp32(patches, on):
    for m, orig, fast in patches:
        m.forward = fast if on else orig


def main():
    tok = AutoTokenizer.from_pretrained(str(MPATH), trust_remote_code=True,
                                        local_files_only=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        str(MPATH), dtype=torch.float16, trust_remote_code=True,
        local_files_only=True, attn_implementation="sdpa").to("cuda")
    model.eval()
    model.config.use_cache = True
    nlin = sum(1 for m in model.modules() if isinstance(m, nn.Linear))
    print("linear count (unique modules):", nlin, flush=True)
    patches = patch_model(model)
    print("patched:", len(patches), flush=True)

    # patch 还原检查（CPU 侧对象状态）
    set_fp32(patches, True)
    nfast = sum(1 for name, m in model.named_modules()
                if isinstance(m, nn.Linear) and isinstance(
                    getattr(m, "forward", None), functools.partial))
    set_fp32(patches, False)
    nfast_after = sum(1 for name, m in model.named_modules()
                      if isinstance(m, nn.Linear) and isinstance(
                          getattr(m, "forward", None), functools.partial))
    print(f"partial forwards: after_on={nfast} after_off={nfast_after} "
          f"(应 0)", flush=True)

    ids = tok("【锚点】\n" + "测试上下文。" * 200, return_tensors="pt",
              truncation=True, max_length=1600)["input_ids"].to("cuda")
    L = ids.shape[1]
    for mode in ("fp16", "fp32cast"):
        set_fp32(patches, mode == "fp32cast")
        with torch.inference_mode():
            t0 = time.time()
            outs = model(input_ids=ids, use_cache=True)
            torch.cuda.synchronize()
            pre = time.time() - t0
            past = outs.past_key_values
            nxt = outs.logits[:, -1, :].argmax(-1, keepdim=True)
            attn = torch.ones((1, L), dtype=torch.long, device="cuda")
            t1 = time.time()
            for i in range(32):
                attn = torch.cat([attn, torch.ones((1, 1), dtype=torch.long,
                                                   device="cuda")], dim=1)
                o = model(input_ids=nxt, attention_mask=attn,
                          past_key_values=past, use_cache=True)
                past = o.past_key_values
                nxt = o.logits[:, -1, :].argmax(-1, keepdim=True)
            torch.cuda.synchronize()
            dec = time.time() - t1
        print(f"[{mode}] prefill {L}tok={pre:.2f}s ({L/pre:.0f} tok/s) | "
              f"decode 32tok={dec:.2f}s -> {32/dec:.1f} tok/s", flush=True)
        del past, outs
        torch.cuda.empty_cache()
    set_fp32(patches, True)
    print("DIAG5_DONE", flush=True)


if __name__ == "__main__":
    main()
