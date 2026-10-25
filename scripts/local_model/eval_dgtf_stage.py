# -*- coding: utf-8 -*-
"""道生 stage 适配器离线评测：JSON 合法率 / position 准确率 / self_check 决策字段。

用法：
  python scripts/local_model/eval_dgtf_stage.py \
      --limit-dj 10 --limit-sc 8 --limit-scmin 16
  # 加 --base 会同时评 base 模型（无适配器）作对照
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "local_model"))
sys.path.insert(0, str(ROOT))

import torch  # noqa: E402
from dgtf_local_llm.service import (LocalEngine, try_parse_json,  # noqa: E402
                                    DEFAULT_MODEL, resolve_adapter)

DATA = ROOT / "llm_sft" / "dgtf_stage"
STAGE_FILE = {
    "dual_judge": ("dual_judge_val.jsonl", 256),
    "self_check": ("self_check_val.jsonl", 320),
    "self_check_min": ("self_check_min_val.jsonl", 64),
}
SC_DECISION = ("suspicious_candidates", "ing_rephrased", "unsaid_is_escape")


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
            if x.strip()]


def pctl(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(len(xs) * q))], 1)


# ---------------- dual_judge ----------------
def score_dual_judge(pred: dict | None, gold: dict) -> dict:
    g = {int(j["idx"]): str(j["position"]) for j in gold.get("judgments", [])}
    p = {}
    if isinstance(pred, dict):
        js = pred.get("judgments")
        if isinstance(js, dict):
            js = [dict(v, idx=k) for k, v in js.items()]
        for j in js or []:
            if not isinstance(j, dict):
                continue
            try:
                p[int(j.get("idx", j.get("index")))] = str(
                    j.get("position", "")).lower()
            except (TypeError, ValueError):
                continue
    n = len(g)
    correct = sum(1 for i, pos in g.items() if p.get(i) == pos)
    cov = sum(1 for i in g if i in p)
    per = {}
    for c in ("0", "1", "both"):
        tp = sum(1 for i, pos in g.items() if pos == c and p.get(i) == c)
        fp = sum(1 for i, pos in p.items() if pos == c and g.get(i) != c)
        fn = sum(1 for i, pos in g.items() if pos == c and p.get(i) != c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per[c] = {"f1": round(f1, 3), "support": sum(1 for v in g.values()
                                                    if v == c)}
    return {"n_gold": n, "correct": correct,
            "acc": round(correct / n, 3) if n else 0.0,
            "coverage": round(cov / n, 3) if n else 0.0,
            "macro_f1": round(sum(v["f1"] for v in per.values())
                              / len(per), 3),
            "per_class": per}


# ---------------- self_check ----------------
def _as_set(x) -> set:
    if not isinstance(x, (list, tuple)):
        return set()
    out = set()
    for v in x:
        try:
            out.add(int(v))
        except (TypeError, ValueError):
            out.add(str(v))
    return out


def score_self_check(pred: dict | None, gold: dict) -> dict:
    if not isinstance(pred, dict):
        return {"json": False, "all3": False, "susp_set": False,
                "susp_f1": 0.0, "ing_ok": False, "esc_ok": False,
                "unsaid_mae": None}
    g_s = _as_set(gold.get("suspicious_candidates"))
    p_s = _as_set(pred.get("suspicious_candidates"))
    tp = len(g_s & p_s)
    prec = tp / len(p_s) if p_s else (1.0 if not g_s else 0.0)
    rec = tp / len(g_s) if g_s else (1.0 if not p_s else 0.0)
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    ing_ok = bool(pred.get("ing_rephrased")) == bool(gold.get("ing_rephrased"))
    esc_ok = bool(pred.get("unsaid_is_escape")) == bool(
        gold.get("unsaid_is_escape"))
    all3 = (g_s == p_s) and ing_ok and esc_ok
    mae = None
    if "unsaid_count" in gold and isinstance(pred.get("unsaid_count"),
                                             (int, float)):
        mae = abs(float(pred["unsaid_count"]) - float(gold["unsaid_count"]))
    return {"json": True, "all3": all3, "susp_set": g_s == p_s,
            "susp_f1": round(f1, 3), "ing_ok": ing_ok, "esc_ok": esc_ok,
            "pred_ing": bool(pred.get("ing_rephrased")),
            "gold_ing": bool(gold.get("ing_rephrased")),
            "pred_esc": bool(pred.get("unsaid_is_escape")),
            "gold_esc": bool(gold.get("unsaid_is_escape")),
            "unsaid_mae": round(mae, 2) if mae is not None else None}


def gating_curve(rows: list[dict], taus=(0.8, 0.9, 0.95)) -> list[dict]:
    out = []
    for t in taus:
        cov = [r for r in rows if r.get("confidence") is not None
               and r["confidence"] >= t]
        if not cov:
            out.append({"tau": t, "coverage": 0.0, "agreement": None,
                        "n_covered": 0})
            continue
        out.append({"tau": t,
                    "coverage": round(len(cov) / max(1, len(rows)), 3),
                    "agreement": round(sum(r["agree"] for r in cov)
                                       / len(cov), 3),
                    "n_covered": len(cov)})
    return out


def run_stage(eng: LocalEngine, stage: str, rows: list[dict], limit: int,
              max_new: int, use_adapter: bool, base: bool = False) -> dict:
    t_all = time.time()
    recs = []
    for r in rows[:limit]:
        gold = json.loads(r["messages"][-1]["content"])
        prompt = eng.tok.apply_chat_template(r["messages"][:-1],
                                             tokenize=False,
                                             add_generation_prompt=True)
        ids = eng.tok(prompt, return_tensors="pt", truncation=True,
                      max_length=2048)["input_ids"]
        t0 = time.time()
        try:
            if base:
                with eng.model.disable_adapter():
                    out = eng.generate(stage, ids, max_new, 0.0,
                                       time.time() + 180, use_adapter=False)
            else:
                out = eng.generate(stage, ids, max_new, 0.0,
                                   time.time() + 180, use_adapter=use_adapter)
            err = None
        except Exception as e:
            out = {"text": "", "confidence": None, "gen_tokens": 0}
            err = f"{type(e).__name__}: {e}"
        ms = round((time.time() - t0) * 1000, 1)
        pred = try_parse_json(out.get("text") or "")
        if stage == "dual_judge":
            sc = score_dual_judge(pred, gold)
            agree = sc["acc"]
        else:
            sc = score_self_check(pred, gold)
            agree = 1.0 if sc["all3"] else 0.0
        recs.append({"id": r["id"], "phase": r.get("phase"),
                     "variant": r.get("variant"),
                     "ms": ms, "confidence": out.get("confidence"),
                     "gen_tokens": out.get("gen_tokens"),
                     "json": bool(pred is not None),
                     "agree": agree, "score": sc, "err": err,
                     "pred": (out.get("text") or "")[:400],
                     "gold": json.dumps(gold, ensure_ascii=False)[:400]})
        print(f"  [{stage}{'-base' if base else ''}] {len(recs)}/{min(limit, len(rows))} "
              f"{ms/1000:.1f}s json={pred is not None} agree={agree:.2f} "
              f"conf={out.get('confidence')}", flush=True)

    n = len(recs)
    lat = [r["ms"] for r in recs]
    gtok = sum(r["gen_tokens"] or 0 for r in recs)
    tsum = sum(lat) / 1000
    res = {
        "stage": stage, "base_model": base, "n": n,
        "json_valid_rate": round(sum(1 for r in recs if r["json"]) / max(1, n),
                                 3),
        "latency_ms": {"p50": pctl(lat, 0.50), "p95": pctl(lat, 0.95),
                       "mean": round(sum(lat) / max(1, n), 1)},
        "gen_tokens_per_sec": round(gtok / max(1e-6, tsum), 2),
        "errors": sum(1 for r in recs if r["err"]),
        "gating": gating_curve(recs),
        "samples": [{k: r[k] for k in ("id", "phase", "ms", "confidence",
                                       "json", "agree")} for r in recs[:6]],
        "wall_sec": round(time.time() - t_all, 1),
    }
    if stage == "dual_judge":
        scs = [r["score"] for r in recs if r.get("score")]
        res["position_acc"] = round(
            sum(s["correct"] for s in scs) / max(1, sum(s["n_gold"]
                                                        for s in scs)), 3)
        res["position_coverage"] = round(
            sum(s["coverage"] * s["n_gold"] for s in scs)
            / max(1, sum(s["n_gold"] for s in scs)), 3)
        res["macro_f1"] = round(sum(s["macro_f1"] for s in scs)
                                / max(1, len(scs)), 3)
        res["per_class_f1"] = {
            c: round(sum(s["per_class"][c]["f1"] for s in scs)
                     / max(1, len(scs)), 3) for c in ("0", "1", "both")}
        res["n_gold_judgments"] = sum(s["n_gold"] for s in scs)
    else:
        scs = [r["score"] for r in recs if r.get("score")]
        res["decision_all3_acc"] = round(
            sum(1 for s in scs if s["all3"]) / max(1, len(scs)), 3)
        res["susp_set_acc"] = round(
            sum(1 for s in scs if s["susp_set"]) / max(1, len(scs)), 3)
        res["susp_f1"] = round(sum(s["susp_f1"] for s in scs)
                               / max(1, len(scs)), 3)
        res["ing_rephrased_acc"] = round(
            sum(1 for s in scs if s["ing_ok"]) / max(1, len(scs)), 3)
        res["unsaid_is_escape_acc"] = round(
            sum(1 for s in scs if s["esc_ok"]) / max(1, len(scs)), 3)
        maes = [s["unsaid_mae"] for s in scs if s["unsaid_mae"] is not None]
        res["unsaid_count_mae"] = (round(sum(maes) / len(maes), 2)
                                   if maes else None)
        # 布尔字段的「正类」F1（少数类才是信号：ing 7.7%、esc 17.6%）
        def _bool_f1(recs2, pk, gk):
            tp = sum(1 for s in recs2 if s.get(pk) and s.get(gk))
            fp = sum(1 for s in recs2 if s.get(pk) and not s.get(gk))
            fn = sum(1 for s in recs2 if not s.get(pk) and s.get(gk))
            prec = tp / (tp + fp) if tp + fp else 0.0
            rec = tp / (tp + fn) if tp + fn else 0.0
            return round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0
        res["ing_rephrased_f1_true"] = _bool_f1(scs, "pred_ing", "gold_ing")
        res["unsaid_is_escape_f1_true"] = _bool_f1(scs, "pred_esc",
                                                   "gold_esc")
        # 决策字段「全对」+ 字段级平均
        field_ok = []
        for s in scs:
            field_ok.append(sum([s["susp_set"], s["ing_ok"], s["esc_ok"]]) / 3)
        res["decision_field_mean_acc"] = round(
            sum(field_ok) / max(1, len(field_ok)), 3)
    res["_recs"] = recs
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(DEFAULT_MODEL))
    ap.add_argument("--stages", default="all")
    ap.add_argument("--limit-dj", type=int, default=10)
    ap.add_argument("--limit-sc", type=int, default=8)
    ap.add_argument("--limit-scmin", type=int, default=16)
    ap.add_argument("--base", action="store_true", help="同时评 base（无适配器）")
    ap.add_argument("--out", default="llm_sft/dgtf_stage/eval_dgtf_stage.json")
    args = ap.parse_args()

    stages = (["dual_judge", "self_check", "self_check_min"]
              if args.stages == "all" else args.stages.split(","))
    limits = {"dual_judge": args.limit_dj, "self_check": args.limit_sc,
              "self_check_min": args.limit_scmin}

    ns = argparse.Namespace(model=args.model)
    t0 = time.time()
    eng = LocalEngine(ns, autostart=False)
    eng._load()
    if eng.state != "ready":
        print("模型加载失败:", eng.error)
        return 1
    print(f"[eval] loaded in {time.time() - t0:.1f}s adapters="
          f"{list(eng.adapter_names)}", flush=True)

    results = {
        "model": args.model,
        "adapters": {s: resolve_adapter(s)[0] for s in STAGE_FILE},
        "loaded_adapters": dict(eng.adapter_paths),
        "gpu": torch.cuda.get_device_name(0),
        "torch": torch.__version__,
        "limits": limits,
        "note": ("生成用 prefill(fp32 GEMM)+decode(fp16) 混合；confidence = "
                 "生成 token 平均概率，用于 QC 门控 τ 曲线"),
        "stages": {},
    }
    for stage in stages:
        fname, max_new = STAGE_FILE[stage]
        rows = read_jsonl(DATA / fname)
        if not rows:
            print(f"[eval] {stage}: 无 val 数据 {fname}，跳过", flush=True)
            continue
        print(f"\n=== {stage} (val {len(rows)} 条, 取 {limits[stage]}) ===",
              flush=True)
        res = run_stage(eng, stage, rows, limits[stage], max_new,
                        use_adapter=(stage in eng.adapter_names))
        if args.base:
            print(f"--- {stage} base 对照 ---", flush=True)
            bres = run_stage(eng, stage, rows, limits[stage], max_new,
                             use_adapter=False, base=True)
            res["base"] = {k: v for k, v in bres.items() if k != "_recs"}
        res.pop("_recs", None)
        results["stages"][stage] = res
        keep = {k: v for k, v in res.items() if k != "samples"}
        print(f"[{stage}] {json.dumps(keep, ensure_ascii=False)}", flush=True)

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"\n[eval] saved -> {out.relative_to(ROOT)}", flush=True)
    print("EVAL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
