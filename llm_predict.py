# -*- coding: utf-8 -*-
"""本地 LoRA 调度预测：问题 → route/rounds JSON。供 app 子进程调用。"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

ROOT = Path(__file__).resolve().parent
SYSTEM = ("你是元DGTF的调度规划器。阅读用户问题，输出严格 JSON："
          '{"route": ["0","1","both","all"] 的子集, '
          '"rounds": {"0":int,"1":int,"both":int,"all":int}, '
          '"why": "不超过20字的理由"}。'
          "route 只放需要的层；rounds 给每层圈数（1-8）；不要输出 JSON 以外内容。")

def parse(txt):
    try:
        o = json.loads(txt.strip())
    except Exception:
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            return None
        try:
            o = json.loads(m.group(0))
        except Exception:
            return None
    if not isinstance(o, dict):
        return None
    route = [str(x) for x in o.get("route") or [] if str(x) in ("0","1","both","all")]
    rounds = {}
    for k, v in (o.get("rounds") or {}).items():
        if str(k) in route:
            try: rounds[str(k)] = max(1, min(8, int(v)))
            except Exception: rounds[str(k)] = 1
    return {"route": route, "rounds": rounds, "why": str(o.get("why") or "")[:80]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", required=True)
    ap.add_argument("--model", default="D:/dgtf_models/Qwen2.5-0.5B-Instruct")
    ap.add_argument("--adapter", default="llm_sft/adapter_qwen05b_v1")
    ap.add_argument("--max_new", type=int, default=96)
    args = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.float16, trust_remote_code=True).to("cuda")
    model = PeftModel.from_pretrained(model, str(ROOT / args.adapter))
    model.eval()
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": str(args.question)[:2000]}]
    text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    ids = tok(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        gen = model.generate(**ids, max_new_tokens=args.max_new, do_sample=False,
                             pad_token_id=tok.pad_token_id)
    raw = tok.decode(gen[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
    obj = parse(raw)
    print(json.dumps({"ok": bool(obj), "parsed": obj, "raw": raw[:500]},
                     ensure_ascii=False))

if __name__ == "__main__":
    main()
