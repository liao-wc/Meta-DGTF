# -*- coding: utf-8 -*-
"""Qwen2.5-0.5B-Instruct LoRA SFT：元DGTF 问题→route/rounds JSON。

在 6GB GPU 上跑；fp16 + LoRA，不合并全量权重。
用法：
  python train_llm_lora.py --model Qwen/Qwen2.5-0.5B-Instruct --epochs 5
"""
from __future__ import annotations
import argparse, json, math, os, random, re, time
from pathlib import Path

# 在导入 transformers/huggingface_hub 之前设置镜像，否则 constants.ENDPOINT 已固化。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parent
SFT = ROOT / "llm_sft"
LAYERS = ["0", "1", "both", "all"]


def set_seed(n=42):
    random.seed(n); torch.manual_seed(n)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(n)


def load_examples(name):
    rows = []
    for ln in (SFT / name).read_text(encoding="utf-8").splitlines():
        if ln.strip():
            rows.append(json.loads(ln))
    return rows


def build_tokens(tok, rec, max_len):
    msgs = rec["messages"]
    prompt = tok.apply_chat_template(msgs[:-1], tokenize=False,
                                     add_generation_prompt=True)
    target = msgs[-1]["content"] + (tok.eos_token or "")
    p = tok(prompt, add_special_tokens=False)["input_ids"]
    t = tok(target, add_special_tokens=False)["input_ids"]
    ids = (p + t)[:max_len]
    labels = ([-100] * len(p) + t)[:max_len]
    return ids, labels


def collate(batch, tok, max_len):
    rows = [build_tokens(tok, r, max_len) for r in batch]
    m = max(len(x[0]) for x in rows)
    pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    input_ids, labels, mask = [], [], []
    for ids, lab in rows:
        n = m - len(ids)
        input_ids.append(ids + [pad] * n)
        labels.append(lab + [-100] * n)
        mask.append([1] * len(ids) + [0] * n)
    return (torch.tensor(input_ids, dtype=torch.long),
            torch.tensor(labels, dtype=torch.long),
            torch.tensor(mask, dtype=torch.long))


def parse_route(txt):
    try:
        obj = json.loads(txt.strip())
        return ([str(x) for x in obj.get("route") or []],
                {str(k): int(v) for k, v in (obj.get("rounds") or {}).items()})
    except Exception:
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            return [], {}
        try:
            obj = json.loads(m.group(0))
            return ([str(x) for x in obj.get("route") or []],
                    {str(k): int(v) for k, v in (obj.get("rounds") or {}).items()})
        except Exception:
            return [], {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--max_len", type=int, default=512)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--out", default="llm_sft/adapter_qwen05b_v1")
    ap.add_argument("--max_eval", type=int, default=14)
    ap.add_argument("--offline", action="store_true",
                    help="只用本地 HF 缓存，不访问 HuggingFace")
    args = ap.parse_args()
    set_seed()
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    print("CUDA", torch.cuda.is_available(), torch.cuda.get_device_name(0)
          if torch.cuda.is_available() else "", flush=True)

    def _set_offline():
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

    if args.offline:
        _set_offline()
    try:
        tok = AutoTokenizer.from_pretrained(
            args.model, trust_remote_code=True, use_fast=True,
            local_files_only=bool(args.offline))
        model = AutoModelForCausalLM.from_pretrained(
            args.model, torch_dtype=torch.float16,
            device_map=None, trust_remote_code=True,
            local_files_only=bool(args.offline))
    except Exception as exc:
        print("在线模型加载失败，回退本地 HF 缓存：%s" % exc, flush=True)
        _set_offline()
        tok = AutoTokenizer.from_pretrained(
            args.model, trust_remote_code=True, use_fast=True,
            local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(
            args.model, torch_dtype=torch.float16,
            device_map=None, trust_remote_code=True,
            local_files_only=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model.to("cuda" if torch.cuda.is_available() else "cpu")
    model.gradient_checkpointing_enable()
    model.config.use_cache = False
    lcfg = LoraConfig(r=8, lora_alpha=16,
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                      "gate_proj", "up_proj", "down_proj"],
                      lora_dropout=0.05, bias="none",
                      task_type="CAUSAL_LM")
    model = get_peft_model(model, lcfg)
    model.print_trainable_parameters()
    train = load_examples("train.jsonl")
    val = load_examples("val.jsonl")
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=args.lr)
    scaler = torch.cuda.amp.GradScaler(enabled=torch.cuda.is_available())
    history = []
    best = 1e9
    for ep in range(1, args.epochs + 1):
        model.train()
        random.shuffle(train)
        t0 = time.time(); step = 0; total = 0.0
        opt.zero_grad(set_to_none=True)
        for i in range(0, len(train), args.batch):
            batch = train[i:i + args.batch]
            ids, labels, mask = collate(batch, tok, args.max_len)
            ids = ids.to(model.device); labels = labels.to(model.device)
            with torch.cuda.amp.autocast(enabled=torch.cuda.is_available()):
                out = model(input_ids=ids, labels=labels)
                loss = out.loss / args.accum
            scaler.scale(loss).backward()
            total += float(out.loss.detach()) / args.accum
            step += 1
            if step % args.accum == 0:
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(
                    [p for p in model.parameters() if p.requires_grad], 1.0)
                scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True)
        # val loss
        model.eval(); vl = 0.0; nv = 0
        with torch.no_grad():
            for i in range(0, len(val), args.batch):
                ids, labels, mask = collate(val[i:i + args.batch], tok, args.max_len)
                ids = ids.to(model.device); labels = labels.to(model.device)
                with torch.cuda.amp.autocast(enabled=torch.cuda.is_available()):
                    vl += float(model(input_ids=ids, labels=labels).loss)
                nv += 1
        vl = vl / max(1, nv)
        history.append({"epoch": ep, "train_loss": round(total / max(1, step), 4),
                        "val_loss": round(vl, 4),
                        "sec": round(time.time() - t0, 1)})
        print("EPOCH", history[-1], flush=True)
        if vl < best:
            best = vl
            model.save_pretrained(str(ROOT / args.out))
            tok.save_pretrained(str(ROOT / args.out))
            print("SAVED", args.out, flush=True)
    # generation eval on val
    model.eval()
    rows = []
    for rec in val[:args.max_eval]:
        msgs = rec["messages"][:-1]
        text = tok.apply_chat_template(msgs, tokenize=False,
                                       add_generation_prompt=True)
        ids = tok(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            gen = model.generate(**ids, max_new_tokens=96, do_sample=False,
                                 pad_token_id=tok.pad_token_id)
        out = tok.decode(gen[0][ids["input_ids"].shape[1]:],
                         skip_special_tokens=True)
        gold = json.loads(rec["messages"][-1]["content"])
        pr, prounds = parse_route(out)
        gr = [str(x) for x in gold.get("route") or []]
        route_ok = (pr == gr)
        round_err = []
        for k in set(prounds) | set(gold.get("rounds") or {}):
            round_err.append(abs(int(prounds.get(k, 0))
                                 - int((gold.get("rounds") or {}).get(k, 0))))
        rows.append({"route_ok": route_ok, "pred": out[:300],
                     "gold": rec["messages"][-1]["content"],
                     "round_mae": round(sum(round_err) / max(1, len(round_err)), 3)})
    metrics = {
        "model": args.model, "epochs": args.epochs, "lr": args.lr,
        "train_n": len(train), "val_n": len(val),
        "history": history, "best_val_loss": round(best, 4),
        "eval": {"route_exact": round(sum(r["route_ok"] for r in rows) / max(1, len(rows)), 3),
                 "round_mae": round(sum(r["round_mae"] for r in rows) / max(1, len(rows)), 3),
                 "n": len(rows)},
        "samples": rows[:4],
        "adapter": args.out,
        "note": "LoRA SFT：问题→route/rounds JSON；fp16；留出按问题分组"
    }
    (SFT / "train_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    print("METRICS", json.dumps(metrics["eval"], ensure_ascii=False), flush=True)
    print("DONE", flush=True)

if __name__ == "__main__":
    main()
