# -*- coding: utf-8 -*-
"""评 1.5B 道生 stage 适配器（离线、GPU、零 API）。

为什么单独写：dgtf_local_llm/service.py 的 ADAPTER_CANDIDATES 写死 0.5B 路径，
1.5B 适配器（adapter_dgtf_*_15b_v1）不在服务解析表里；本脚本直接加载
「1.5B 底座 + 适配器」做 held-out 评测，口径与 eval_dgtf_stage.py 一致：
  · self_check / self_check_min：JSON 合法率、三项全对率、suspicious F1、ing/esc acc；
  · dual_judge：position 准确率/覆盖率/macro-F1；
  · 置信度用生成 token 的平均最大 softmax 概率近似（与 service 的 confidence 同口径），
    并给 τ∈{0.8,0.9,0.95} 的 coverage/agreement 曲线（QC 门控可用性）。
可选 --compare-base 同时评无适配器底座，作为对照。

用法（在本地模型 env 下跑）：
  local_model\\envs\\dgtf_llm_env\\Scripts\\python.exe scripts/local_model/eval_15b_adapter.py \
      --stage self_check_min --limit 14 --compare-base
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "local_model"))

import torch  # noqa: E402
from peft import PeftModel  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402

from dgtf_local_llm.service import try_parse_json  # noqa: E402

DATA = ROOT / "llm_sft" / "dgtf_stage"
STAGE_FILE = {
    "dual_judge": "dual_judge_val.jsonl",
    "self_check": "self_check_val.jsonl",
    "self_check_min": "self_check_min_val.jsonl",
}
STAGE_ADAPTER = {
    "dual_judge": "llm_sft/adapter_dgtf_judge_15b_v1",
    "self_check": "llm_sft/adapter_dgtf_selfcheck_15b_v1",
    "self_check_min": "llm_sft/adapter_dgtf_selfcheck_15b_v1",
}
DEFAULT_BASE = ROOT / "local_model" / "models" / "Qwen2.5-1.5B-Instruct"


def load_scorers():
    p = ROOT / "scripts" / "local_model" / "eval_dgtf_stage.py"
    spec = importlib.util.spec_from_file_location("eval_stage_base", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_jsonl(p: Path, limit: int) -> list[dict]:
    rows = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            rows.append(json.loads(ln))
        if limit and len(rows) >= limit:
            break
    return rows


def pctl(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(len(xs) * q))], 1)


class Runner:
    def __init__(self, base_model: Path, adapter: Path | None):
        self.tok = AutoTokenizer.from_pretrained(
            str(adapter or base_model), trust_remote_code=True,
            local_files_only=True)
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            str(base_model), torch_dtype=torch.float16,
            trust_remote_code=True, local_files_only=True).to("cuda")
        self.adapter = None
        if adapter is not None and (adapter / "adapter_config.json").exists():
            self.model = PeftModel.from_pretrained(self.model, str(adapter))
            self.adapter = str(adapter)
        self.model.eval()

    def gen(self, messages: list[dict], max_new_tokens: int = 96) -> dict:
        prompt = self.tok.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True)
        ids = self.tok(prompt, return_tensors="pt").to("cuda")
        t0 = time.time()
        with torch.inference_mode():
            out = self.model.generate(
                **ids, max_new_tokens=max_new_tokens, do_sample=False,
                pad_token_id=self.tok.pad_token_id,
                return_dict_in_generate=True, output_scores=True)
        dt = time.time() - t0
        seq = out.sequences[0][ids["input_ids"].shape[1]:]
        text = self.tok.decode(seq, skip_special_tokens=True)
        conf = None
        try:
            probs = []
            for step, sc in enumerate(out.scores or []):
                if step >= len(seq):
                    break
                p = torch.softmax(sc[0].float(), dim=-1)
                probs.append(float(p[int(seq[step])]))
            if probs:
                conf = round(sum(probs) / len(probs), 4)
        except Exception:  # noqa: BLE001
            conf = None
        return {"text": text, "ms": round(dt * 1000, 1), "confidence": conf}


def evaluate(stage: str, rows: list[dict], runner: Runner,
             scorer, max_new: int) -> dict:
    recs = []
    for r in rows:
        msgs = (r.get("messages") or [])[:-1]
        gold = {}
        try:
            gold = json.loads((r["messages"][-1].get("content") or "{}"))
        except Exception:  # noqa: BLE001
            continue
        g = runner.gen(msgs, max_new_tokens=max_new)
        pred = try_parse_json(g["text"])
        if isinstance(pred, dict) and stage != "dual_judge":
            # 决策字段允许从截断输出抢救（与服务同口径）
            pass
        if stage == "dual_judge":
            score = scorer.score_dual_judge(pred, gold)
            agree = (score.get("acc") == 1.0)
        else:
            score = scorer.score_self_check(pred, gold)
            agree = bool(score.get("all3"))
        recs.append({"id": r.get("id"), "json": isinstance(pred, dict),
                     "ms": g["ms"], "confidence": g["confidence"],
                     "agree": bool(agree), "score": score,
                     "pred": json.dumps(pred, ensure_ascii=False)[:200],
                     "gold": json.dumps(gold, ensure_ascii=False)[:200]})
    n = max(1, len(recs))
    out = {
        "stage": stage, "n": len(recs),
        "json_valid_rate": round(sum(1 for x in recs if x["json"]) / n, 3),
        "latency_ms": {"p50": pctl([x["ms"] for x in recs], 0.5),
                       "p95": pctl([x["ms"] for x in recs], 0.95)},
        "adapter": runner.adapter,
    }
    if stage == "dual_judge":
        accs = [x["score"].get("acc") or 0.0 for x in recs]
        out["position_acc"] = round(sum(accs) / n, 3)
        out["macro_f1"] = round(sum((x["score"].get("macro_f1") or 0.0)
                                    for x in recs) / n, 3)
        out["coverage"] = round(sum((x["score"].get("coverage") or 0.0)
                                    for x in recs) / n, 3)
        out["agree"] = round(sum(1 for x in recs if x["agree"]) / n, 3)
    else:
        out["decision_all3_acc"] = round(
            sum(1 for x in recs if x["score"].get("all3")) / n, 3)
        out["susp_f1"] = round(sum((x["score"].get("susp_f1") or 0.0)
                                   for x in recs) / n, 3)
        out["susp_set_acc"] = round(
            sum(1 for x in recs if x["score"].get("susp_set")) / n, 3)
        out["ing_rephrased_acc"] = round(
            sum(1 for x in recs if x["score"].get("ing_ok")) / n, 3)
        out["unsaid_is_escape_acc"] = round(
            sum(1 for x in recs if x["score"].get("esc_ok")) / n, 3)
        out["decision_field_mean_acc"] = round(
            (out["susp_set_acc"] + out["ing_rephrased_acc"]
             + out["unsaid_is_escape_acc"]) / 3.0, 3)
        out["agree"] = out["decision_all3_acc"]
    gating = []
    for tau in (0.8, 0.9, 0.95):
        cov = [x for x in recs if x.get("confidence") is not None
               and x["confidence"] >= tau]
        gating.append({"tau": tau,
                       "coverage": round(len(cov) / n, 3),
                       "agreement": (round(sum(1 for x in cov if x["agree"])
                                           / len(cov), 3) if cov else None),
                       "n_covered": len(cov)})
    out["gating"] = gating
    out["samples"] = recs[:5]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="self_check_min",
                    choices=tuple(STAGE_FILE))
    ap.add_argument("--limit", type=int, default=14)
    ap.add_argument("--base-model", default=str(DEFAULT_BASE))
    ap.add_argument("--adapter", default="")
    ap.add_argument("--compare-base", action="store_true")
    ap.add_argument("--max-new", type=int, default=96)
    ap.add_argument("--out", default="llm_sft/eval_15b_adapter.json")
    args = ap.parse_args()
    base = Path(args.base_model)
    adapter = Path(args.adapter) if args.adapter else \
        ROOT / STAGE_ADAPTER[args.stage]
    print("CUDA", torch.cuda.is_available(), torch.cuda.get_device_name(0),
          flush=True)
    print("base", base, "| adapter", adapter, flush=True)
    rows = read_jsonl(DATA / STAGE_FILE[args.stage], args.limit)
    print("rows", len(rows), flush=True)
    scorer = load_scorers()
    result = {"base_model": str(base), "rows": len(rows)}
    if adapter.exists() and (adapter / "adapter_config.json").exists():
        runner = Runner(base, adapter)
        result["adapter"] = evaluate(args.stage, rows, runner, scorer,
                                     args.max_new)
        del runner
        torch.cuda.empty_cache()
    else:
        result["adapter"] = {"error": "adapter 不存在：%s" % adapter}
    if args.compare_base:
        runner_b = Runner(base, None)
        result["base"] = evaluate(args.stage, rows, runner_b, scorer,
                                  args.max_new)
        result["delta"] = {
            k: round(float(result["adapter"].get(k) or 0)
                     - float(result["base"].get(k) or 0), 3)
            for k in ("json_valid_rate", "decision_all3_acc", "susp_f1",
                      "ing_rephrased_acc", "unsaid_is_escape_acc",
                      "position_acc", "macro_f1")
            if k in result["adapter"] or k in result["base"]
        }
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("RESULT", json.dumps({k: v for k, v in result.items()
                                if k not in ("adapter", "base")} |
                               {"adapter_summary": {k: v for k, v in
                                (result.get("adapter") or {}).items()
                                if k not in ("samples", "gating")},
                                "base_summary": {k: v for k, v in
                                (result.get("base") or {}).items()
                                if k not in ("samples", "gating")}},
                               ensure_ascii=False), flush=True)
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
