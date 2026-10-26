# -*- coding: utf-8 -*-
"""道生专属 stage LoRA 训练：dual_judge / self_check（full|min|mixed）。

硬件适配（实测结论，见 docs/local_model_daosheng.md）：
  GTX 1660 Ti（SM75，无 tensor core）上 cuBLAS 的 HGEMM 极慢：
  fp16 matmul 仅 0.54 TFLOPS，而 fp32 matmul 有 2.47 TFLOPS。
  因此本训练用 **fp16 权重 + fp32 GEMM**（`enable_fp32_compute`：把每个
  Linear 的 matmul 用 fp32 做、输出转回 fp16），实测 fwd+bwd 从
  55 tok/s 提到 ~110-160 tok/s（2-3x），显存基本不变（权重仍 fp16）。
  这不是量化也不是换精度存权重，只是 GEMM 的 compute dtype 选择。

其它：fp16 LoRA r=16/alpha=32，target q/k/v/o/gate/up/down，
gradient checkpointing，batch=1 + accum=8，max_len 2048（超长按
「保留 prompt 头 + 尾（候选列表）、丢中间」截断，计数写入 metrics）。

用法：
  python scripts/local_model/train_dgtf_stage_lora.py \
      --stage self_check --variant mixed --max-train 260 --epochs 1 \
      --out llm_sft/adapter_dgtf_selfcheck_05b_v1
  python scripts/local_model/train_dgtf_stage_lora.py \
      --stage dual_judge --max-train 300 --epochs 1 \
      --out llm_sft/adapter_dgtf_judge_05b_v1
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import os
import random
import time
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
import torch.nn as nn
import torch.nn.functional as F
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = ROOT / "local_model" / "models" / "Qwen2.5-1.5B-Instruct"
DEFAULT_DATA = ROOT / "llm_sft" / "dgtf_stage"
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                  "gate_proj", "up_proj", "down_proj"]


def set_seed(n: int) -> None:
    random.seed(n)
    torch.manual_seed(n)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(n)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ============================================================
# fp16 权重 + fp32 GEMM（针对 SM75 上 HGEMM 极慢的适配）
# ============================================================
def enable_fp32_compute(model, skip_suffix=("lm_head",)) -> list:
    """把 Linear 的 GEMM 换成 fp32 计算（输出转回 fp16），返回可还原的 patch 列表。"""
    originals: list = []

    def _fwd(self, x, *args, **kwargs):
        w = self.weight
        b = self.bias
        with torch.amp.autocast("cuda", enabled=False):
            y = F.linear(x.float(), w.float(),
                         b.float() if b is not None else None)
        return y.to(w.dtype)

    seen = set()
    for name, m in model.named_modules():
        if not isinstance(m, nn.Linear):
            continue
        if any(name == s or name.endswith("." + s) for s in skip_suffix):
            continue
        if id(m) in seen:  # named_modules 可能重复给出同一 module
            continue
        seen.add(id(m))
        originals.append((m, m.forward))
        m.forward = functools.partial(_fwd, m)
    return originals


def disable_fp32_compute(originals: list) -> None:
    """还原 Linear.forward（生成阶段必须关掉：decode 时 fp32-cast 反而慢）。"""
    for m, f in originals:
        m.forward = f


# ============================================================
# 数据
# ============================================================
def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
            if x.strip()]


def load_rows(args) -> tuple[list[dict], list[dict]]:
    data = Path(args.data_dir)
    if not data.is_absolute():
        data = ROOT / data
    if args.stage == "dual_judge":
        train = read_jsonl(data / "dual_judge_train.jsonl")
        val = read_jsonl(data / "dual_judge_val.jsonl")
    else:
        variant = args.variant
        if variant == "mixed":
            train = (read_jsonl(data / "self_check_train.jsonl")
                     + read_jsonl(data / "self_check_min_train.jsonl"))
            val = (read_jsonl(data / "self_check_val.jsonl")
                   + read_jsonl(data / "self_check_min_val.jsonl"))
        elif variant == "min":
            train = read_jsonl(data / "self_check_min_train.jsonl")
            val = read_jsonl(data / "self_check_min_val.jsonl")
        else:
            train = read_jsonl(data / "self_check_train.jsonl")
            val = read_jsonl(data / "self_check_val.jsonl")
    rng = random.Random(args.seed)
    if args.max_train and len(train) > args.max_train:
        # 混采两变体时保持比例；按问题轮转保多样性
        by_q: dict[str, list[dict]] = {}
        for r in train:
            by_q.setdefault(r["question"], []).append(r)
        qs = list(by_q)
        rng.shuffle(qs)
        for q in qs:
            rng.shuffle(by_q[q])
        out, i = [], 0
        while len(out) < args.max_train:
            added = False
            for q in qs:
                if i < len(by_q[q]):
                    out.append(by_q[q][i])
                    added = True
                    if len(out) >= args.max_train:
                        break
            if not added:
                break
            i += 1
        train = out
    rng.shuffle(train)
    return train, val


def build_token(tok, rec: dict, max_len: int) -> dict | None:
    msgs = rec["messages"]
    prompt = tok.apply_chat_template(msgs[:-1], tokenize=False,
                                     add_generation_prompt=True)
    target = msgs[-1]["content"] + (tok.eos_token or "")
    p = tok(prompt, add_special_tokens=False)["input_ids"]
    t = tok(target, add_special_tokens=False)["input_ids"]
    if len(t) >= max_len - 8:
        return None
    allowed = max_len - len(t)
    truncated = False
    if len(p) > allowed:
        # 截断策略：保住 system 头部 + user 尾部（候选列表在最后），丢中间
        head = allowed * 2 // 5
        tail = allowed - head
        p = p[:head] + p[-tail:]
        truncated = True
    return {"ids": p + t, "labels": [-100] * len(p) + t,
            "truncated": truncated, "prompt_len": len(p),
            "target_len": len(t)}


def collate(rows, pad_id):
    m = max(len(r["ids"]) for r in rows)
    ids, labels, mask = [], [], []
    for r in rows:
        n = m - len(r["ids"])
        ids.append(r["ids"] + [pad_id] * n)
        labels.append(r["labels"] + [-100] * n)
        mask.append([1] * len(r["ids"]) + [0] * n)
    return (torch.tensor(ids, dtype=torch.long),
            torch.tensor(labels, dtype=torch.long),
            torch.tensor(mask, dtype=torch.long))


# ============================================================
# 训练
# ============================================================


def _dry_run(args, tok) -> None:
    """不加载模型，检查数据/tokenize/丢弃截断后的量级。"""
    train_raw, val_raw = load_rows(args)
    print(f"[dry] stage={args.stage} variant={args.variant} "
          f"train={len(train_raw)} val={len(val_raw)}", flush=True)
    train = [r for r in (build_token(tok, x, args.max_len)
                         for x in train_raw) if r]
    val = [r for r in (build_token(tok, x, args.max_len)
                       for x in val_raw) if r]
    trunc = sum(1 for r in train if r["truncated"])
    if args.drop_truncated:
        train = [r for r in train if not r["truncated"]]
    plens = sorted(r["prompt_len"] for r in train)
    tlens = sorted(r["target_len"] for r in train)
    tot = sorted(r["prompt_len"] + r["target_len"] for r in train)

    def p(xs, q):
        return xs[min(len(xs) - 1, int(len(xs) * q))] if xs else 0

    print(f"[dry] after drop: train={len(train)} "
          f"dropped_truncated={trunc if args.drop_truncated else 0} "
          f"val={len(val)}", flush=True)
    print(f"[dry] prompt p50={p(plens, .5)} p95={p(plens, .95)} "
          f"max={plens[-1] if plens else 0}", flush=True)
    print(f"[dry] target p50={p(tlens, .5)} max={tlens[-1] if tlens else 0}",
          flush=True)
    print(f"[dry] total  p50={p(tot, .5)} p95={p(tot, .95)} "
          f"max={tot[-1] if tot else 0} "
          f"over_max_len={sum(1 for x in tot if x > args.max_len)}", flush=True)
    print(f"[dry] est_min_at_5s_step={len(train) * 5 / 60:.1f}", flush=True)
    print("DRY_RUN_OK", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="self_check",
                    choices=("dual_judge", "self_check"))
    ap.add_argument("--variant", default="mixed",
                    choices=("full", "min", "mixed"))
    ap.add_argument("--model", default=str(DEFAULT_MODEL))
    ap.add_argument("--allow-model-mismatch", action="store_true",
                    help="允许 out 名含 05b 但模型非 0.5B（默认拒绝，防错训）")
    ap.add_argument("--data-dir", default=str(DEFAULT_DATA))
    ap.add_argument("--out", default="")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--max-train", type=int, default=0)
    ap.add_argument("--max-steps", type=int, default=0,
                    help=">0 时到步数即停（时间预算保险）")
    ap.add_argument("--max-len", type=int, default=2048)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--weight-decay", type=float, default=0.0)
    ap.add_argument("--warmup-steps", type=int, default=10)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--val-subset", type=int, default=60)
    ap.add_argument("--log-every", type=int, default=5)
    ap.add_argument("--save-every", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true",
                    help="只做数据/tokenize 检查，不加载模型")
    ap.add_argument("--drop-truncated", action="store_true",
                    help="丢弃超 max_len 被截断的样本（lead 要求：不中段切候选）")
    ap.add_argument("--no-fp32-compute", action="store_true")
    ap.add_argument("--smoke", type=int, default=0,
                    help=">0 只跑 N 步做冒烟，不保存最终产物")
    args = ap.parse_args()
    # ★ [Round 116] 防错训：输出名含 05b 但 base 模型非 0.5B ⇒ 拒绝
    _model_l = str(args.model).lower()
    _out_l = str(args.out or '').lower()
    if ("05b" in _out_l and "0.5b" not in _model_l
            and not getattr(args, "allow_model_mismatch", False)):
        print("拒绝训练：out 名含 05b 但 base 模型不是 0.5B（%s）；请显式 --model" % args.model, flush=True)
        return 2
    set_seed(args.seed)

    out = Path(args.out) if args.out else (
        ROOT / ("llm_sft/adapter_dgtf_judge_05b_v1"
                if args.stage == "dual_judge"
                else "llm_sft/adapter_dgtf_selfcheck_05b_v1"))
    if not out.is_absolute():
        out = ROOT / out
    metrics_path = ROOT / "llm_sft" / (
        "train_metrics_dgtf_judge.json" if args.stage == "dual_judge"
        else "train_metrics_dgtf_selfcheck.json")

    log(f"stage={args.stage} variant={args.variant} out={out}")
    log(f"CUDA={torch.cuda.is_available()} "
        f"{torch.cuda.get_device_name(0) if torch.cuda.is_available() else ''}")
    t_load = time.time()
    tok = AutoTokenizer.from_pretrained(str(args.model),
                                        trust_remote_code=True,
                                        local_files_only=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    if args.dry_run:
        _dry_run(args, tok)
        return 0
    model = AutoModelForCausalLM.from_pretrained(
        str(args.model), dtype=torch.float16, trust_remote_code=True,
        local_files_only=True, attn_implementation="sdpa")
    model.to("cuda")
    model.gradient_checkpointing_enable()
    model.config.use_cache = False
    lcfg = LoraConfig(r=args.lora_r, lora_alpha=args.lora_alpha,
                      target_modules=TARGET_MODULES,
                      lora_dropout=args.lora_dropout, bias="none",
                      task_type="CAUSAL_LM")
    model = get_peft_model(model, lcfg)
    patches: list = []
    if not args.no_fp32_compute:
        patches = enable_fp32_compute(model)
    n_patch = len(patches)
    n_tr = sum(p.numel() for p in model.parameters() if p.requires_grad)
    log(f"load {time.time() - t_load:.1f}s trainable={n_tr:,} "
        f"fp32_gemm_patched={n_patch}")

    train_raw, val_raw = load_rows(args)
    log(f"data train={len(train_raw)} val={len(val_raw)}")
    if not train_raw:
        raise SystemExit("训练集为空")

    train = [r for r in (build_token(tok, x, args.max_len) for x in train_raw)
             if r]
    val = [r for r in (build_token(tok, x, args.max_len) for x in val_raw)
           if r]
    if args.val_subset and len(val) > args.val_subset:
        rng = random.Random(args.seed + 1)
        val = rng.sample(val, args.val_subset)
    trunc = sum(1 for r in train if r["truncated"])
    if args.drop_truncated and trunc:
        before = len(train)
        train = [r for r in train if not r["truncated"]]
        log(f"drop_truncated: {before} -> {len(train)}（丢弃 {before - len(train)} 条）")
    plens = sorted(r["prompt_len"] for r in train)
    tlens = sorted(r["target_len"] for r in train)
    log(f"tokenized train={len(train)} val={len(val)} "
        f"prompt_p50={plens[len(plens)//2]} "
        f"prompt_p95={plens[int(len(plens)*0.95)]} "
        f"target_p50={tlens[len(tlens)//2]} truncated={trunc}")
    if not train:
        raise SystemExit("tokenize 后训练集为空")

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=args.lr, weight_decay=args.weight_decay)
    scaler = torch.amp.GradScaler("cuda", enabled=True)
    steps_per_epoch = math.ceil(len(train) / args.batch)
    total_steps = steps_per_epoch * args.epochs
    if args.max_steps:
        total_steps = min(total_steps, args.max_steps)

    def lr_at(step: int) -> float:
        if step < args.warmup_steps:
            return args.lr * (step + 1) / max(1, args.warmup_steps)
        prog = (step - args.warmup_steps) / max(1, total_steps
                                                - args.warmup_steps)
        return args.lr * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * prog)))

    pad_id = tok.pad_token_id
    history: list[dict] = []
    epoch_rows: list[dict] = []
    best_val = float("inf")
    best_step = 0
    t0 = time.time()
    global_step = 0
    model.train()

    def run_val() -> float:
        model.eval()
        tot, n = 0.0, 0
        with torch.inference_mode():
            for i in range(0, len(val), args.batch):
                ids, labels, _ = collate(val[i:i + args.batch], pad_id)
                with torch.amp.autocast("cuda", enabled=False):
                    loss = model(input_ids=ids.to("cuda"),
                                 labels=labels.to("cuda")).loss
                tot += float(loss)
                n += 1
        model.train()
        return tot / max(1, n)

    stop = False
    ep = 1
    while ep <= args.epochs and not stop:
        random.shuffle(train)
        ep_loss, ep_n = 0.0, 0
        opt.zero_grad(set_to_none=True)
        for i in range(0, len(train), args.batch):
            batch = train[i:i + args.batch]
            ids, labels, _ = collate(batch, pad_id)
            ids = ids.to("cuda")
            labels = labels.to("cuda")
            res = model(input_ids=ids, labels=labels)
            loss = res.loss / args.accum
            scaler.scale(loss).backward()
            raw_loss = float(res.loss.detach())
            ep_loss += raw_loss
            ep_n += 1
            if not math.isfinite(raw_loss):
                log(f"!! 非有限 loss {raw_loss} @ step {global_step}，跳过该步")
                opt.zero_grad(set_to_none=True)
                continue
            if (i // args.batch + 1) % args.accum == 0 or \
                    i + args.batch >= len(train):
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(
                    [p for p in model.parameters() if p.requires_grad], 1.0)
                scaler.step(opt)
                scaler.update()
                opt.zero_grad(set_to_none=True)
            global_step += 1
            for g in opt.param_groups:
                g["lr"] = lr_at(global_step)
            if global_step % args.log_every == 0:
                el = time.time() - t0
                sps = global_step / max(1e-6, el)
                recent = history[-args.log_every:]
                avg = (sum(x["loss"] for x in recent) / len(recent)
                       if recent else raw_loss)
                log(f"ep{ep} step {global_step}/{total_steps} "
                    f"loss={raw_loss:.4f} avg={avg:.4f} "
                    f"lr={lr_at(global_step):.2e} "
                    f"step/s={sps:.2f} eta={(total_steps - global_step)/max(1e-6, sps)/60:.0f}min")
            history.append({"step": global_step, "epoch": ep,
                            "loss": round(raw_loss, 5),
                            "lr": round(lr_at(global_step), 8)})
            if args.save_every and global_step % args.save_every == 0:
                model.save_pretrained(str(out))
                tok.save_pretrained(str(out))
                log(f"checkpoint saved @ step {global_step}")
            if args.smoke and global_step >= args.smoke:
                stop = True
                break
            if args.max_steps and global_step >= args.max_steps:
                stop = True
                break
        if not stop:
            vl = run_val()
            epoch_rows.append({"epoch": ep,
                               "train_loss": round(ep_loss / max(1, ep_n), 5),
                               "val_loss": round(vl, 5),
                               "steps": global_step,
                               "sec": round(time.time() - t0, 1)})
            log(f"EPOCH {epoch_rows[-1]}")
            if vl < best_val:
                best_val = vl
                best_step = global_step
                out.mkdir(parents=True, exist_ok=True)
                model.save_pretrained(str(out))
                tok.save_pretrained(str(out))
                log(f"SAVED best val_loss={vl:.4f} -> {out}")
        ep += 1

    if args.smoke:
        log(f"SMOKE_DONE steps={global_step} "
            f"loss_first={history[0]['loss'] if history else None} "
            f"loss_last={history[-1]['loss'] if history else None}")
        return 0

    # 冒烟生成自检（greedy，少量样本）。★ 生成阶段必须关掉 fp32 GEMM patch：
    #   实测 decode(M=1) 时 fp32-cast 只有 2.5 tok/s，远慢于纯 fp16。
    disable_fp32_compute(patches)
    model.eval()
    gen_ok, gen_n = 0, 0
    gen_samples = []
    for r in train_raw[:max(1, 2)]:
        try:
            msgs = r["messages"][:-1]
            text = tok.apply_chat_template(msgs, tokenize=False,
                                           add_generation_prompt=True)
            ids = tok(text, return_tensors="pt", truncation=True,
                      max_length=args.max_len - 256).to("cuda")
            with torch.inference_mode():
                gen = model.generate(**ids, max_new_tokens=96,
                                     do_sample=False,
                                     pad_token_id=pad_token_id_or(tok))
            o = tok.decode(gen[0][ids["input_ids"].shape[1]:],
                           skip_special_tokens=True)
            try:
                json.loads(o[o.index("{"):o.rindex("}") + 1])
                gen_ok += 1
            except Exception:
                pass
            gen_n += 1
            gen_samples.append({"pred": o[:300],
                                "gold": r["messages"][-1]["content"][:300]})
        except Exception as e:
            log(f"gen smoke 失败: {e}")
    train_sec = round(time.time() - t0, 1)
    peak = torch.cuda.max_memory_allocated() / 1024 ** 3
    n_samples_seen = global_step * args.batch
    tok_seen = n_samples_seen * (sum(plens) / max(1, len(plens))
                                 + sum(tlens) / max(1, len(tlens)))
    metrics = {
        "base_model": str(args.model),
        "stage": args.stage, "variant": args.variant,
        "model": args.model, "adapter": str(out.relative_to(ROOT)),
        "train_n": len(train), "val_n": len(val),
        "epochs": args.epochs, "steps": global_step,
        "batch": args.batch, "accum": args.accum, "lr": args.lr,
        "max_len": args.max_len,
        "lora": {"r": args.lora_r, "alpha": args.lora_alpha,
                 "target_modules": TARGET_MODULES,
                 "dropout": args.lora_dropout},
        "fp32_gemm_patched_layers": n_patch,
        "gradient_checkpointing": True,
        "dtype": "fp16 weights + fp32 GEMM",
        "trainable_params": n_tr,
        "prompt_len": {"p50": plens[len(plens) // 2],
                       "p95": plens[int(len(plens) * 0.95)]},
        "target_len": {"p50": tlens[len(tlens) // 2]},
        "truncated_samples": trunc,
        "best_val_loss": round(best_val, 5), "best_step": best_step,
        "epoch_history": epoch_rows,
        "loss_curve": history,
        "gen_smoke": {"json_ok": gen_ok, "n": gen_n,
                      "samples": gen_samples[:3]},
        "peak_vram_gb": round(peak, 2),
        "train_sec": train_sec,
        "samples_per_sec": round(n_samples_seen / max(1e-6, train_sec), 3),
        "tokens_per_sec_est": round(tok_seen / max(1e-6, train_sec), 1),
        "note": ("LoRA SFT：引擎同构 prompt → stage JSON；fp16 权重 + fp32 GEMM "
                 "（SM75 HGEMM 慢的适配）；grad checkpointing；按问题分组留出"),
    }
    out.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    write_loss_svg(history, ROOT / "llm_sft" / (
        "loss_curve_dgtf_judge.svg" if args.stage == "dual_judge"
        else "loss_curve_dgtf_selfcheck.svg"))
    log(f"METRICS {json.dumps({k: metrics[k] for k in ('train_n','val_n','best_val_loss','steps','peak_vram_gb','train_sec')}, ensure_ascii=False)}")
    log("DONE")
    return 0


def pad_token_id_or(tok):
    return tok.pad_token_id if tok.pad_token_id is not None else 0


def write_loss_svg(history: list[dict], path: Path) -> None:
    """零依赖 loss 曲线（SVG），便于文档内嵌。"""
    pts = [(h["step"], h["loss"]) for h in history if h["loss"] is not None]
    if len(pts) < 2:
        return
    W, H, pad = 720, 240, 36
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if x1 == x0:
        x1 = x0 + 1
    if y1 == y0:
        y1 = y0 + 1e-6

    def sx(x):
        return pad + (x - x0) / (x1 - x0) * (W - 2 * pad)

    def sy(y):
        return H - pad - (y - y0) / (y1 - y0) * (H - 2 * pad)

    d = " ".join(("M" if i == 0 else "L") + f"{sx(x):.1f},{sy(y):.1f}"
                 for i, (x, y) in enumerate(pts))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="#ffffff"/>'
        f'<text x="{pad}" y="20" font-size="13" fill="#333">LoRA train loss '
        f'(min={y0:.4f}, max={y1:.4f}, steps={len(pts)})</text>'
        f'<line x1="{pad}" y1="{H - pad}" x2="{W - pad}" y2="{H - pad}" '
        f'stroke="#bbb"/><line x1="{pad}" y1="{pad}" x2="{pad}" '
        f'y2="{H - pad}" stroke="#bbb"/>'
        f'<path d="{d}" fill="none" stroke="#1f77b4" stroke-width="1.5"/>'
        f'<text x="{W - pad - 60}" y="{H - 8}" font-size="11" fill="#666">'
        f'step {x0}→{x1}</text></svg>')
    path.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
