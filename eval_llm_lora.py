# -*- coding: utf-8 -*-
"""留出评估：base Qwen2.5-0.5B-Instruct vs +LoRA adapter。

指标：JSON 解析率、route 完全匹配、rounds MAE。
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

ROOT = Path(__file__).resolve().parent
SFT = ROOT / "llm_sft"

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
    return ([str(x) for x in o.get("route") or []],
            {str(k): int(v) for k, v in (o.get("rounds") or {}).items()})

def run(model, tok, val, max_new=96):
    model.eval(); rows = []
    for rec in val:
        text = tok.apply_chat_template(rec["messages"][:-1], tokenize=False,
                                       add_generation_prompt=True)
        ids = tok(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            gen = model.generate(**ids, max_new_tokens=max_new, do_sample=False,
                                 pad_token_id=tok.pad_token_id)
        out = tok.decode(gen[0][ids["input_ids"].shape[1]:],
                         skip_special_tokens=True)
        gold = json.loads(rec["messages"][-1]["content"])
        gr = [str(x) for x in gold.get("route") or []]
        grd = {str(k): int(v) for k, v in (gold.get("rounds") or {}).items()}
        pr = parse(out)
        ok = bool(pr and pr[0] == gr)
        mae = None
        if pr:
            errs = [abs(pr[1].get(k, 0) - grd.get(k, 0))
                    for k in set(pr[1]) | set(grd)]
            mae = sum(errs) / max(1, len(errs))
        rows.append({"json": bool(pr), "route_ok": ok, "round_mae": mae,
                     "out": out[:400], "gold": rec["messages"][-1]["content"]})
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="D:/元DGTF-多模并行架构/local_model/models/Qwen2.5-0.5B-Instruct")
    ap.add_argument("--adapter", default="llm_sft/adapter_qwen05b_v1")
    ap.add_argument("--max", type=int, default=14)
    ap.add_argument("--base-only", action="store_true")
    ap.add_argument("--out", default="llm_sft/eval_base_vs_lora.json")
    args = ap.parse_args()
    val = [json.loads(x) for x in (SFT / "val.jsonl").read_text(
        encoding="utf-8").splitlines() if x.strip()][:args.max]
    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    base = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.float16, trust_remote_code=True).to("cuda")
    rb = run(base, tok, val)
    del base; torch.cuda.empty_cache()
    if args.base_only:
        out = {"base": {"name": "base", "n": len(rb),
                        "json_rate": round(sum(r["json"] for r in rb) / max(1, len(rb)), 3),
                        "route_exact": round(sum(r["route_ok"] for r in rb) / max(1, len(rb)), 3),
                        "round_mae": round(sum((r["round_mae"] or 0) for r in rb) / max(1, len(rb)), 3)}}
        out_path = SFT / Path(args.out).name
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=1))
        print("WROTE", out_path)
        return
    tuned = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.float16, trust_remote_code=True).to("cuda")
    tuned = PeftModel.from_pretrained(tuned, str(ROOT / args.adapter))
    rt = run(tuned, tok, val)
    def agg(rows, name):
        n = len(rows)
        return {"name": name, "n": n,
                "json_rate": round(sum(r["json"] for r in rows) / max(1, n), 3),
                "route_exact": round(sum(r["route_ok"] for r in rows) / max(1, n), 3),
                "round_mae": round(sum((r["round_mae"] or 0) for r in rows) / max(1, n), 3)}
    out = {"base": agg(rb, "base"), "lora": agg(rt, "lora"),
           "samples": [{"base": rb[i]["out"][:180], "lora": rt[i]["out"][:180],
                        "gold": rt[i]["gold"][:180]} for i in range(min(3, len(rt)))]}
    _out_path = SFT / Path(args.out).name
    _out_path.write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("base", "lora")},
                     ensure_ascii=False, indent=1))
    print("WROTE", _out_path)

if __name__ == "__main__":
    main()
