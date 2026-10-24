# -*- coding: utf-8 -*-
"""本地模型质量侧代理评估：同一组问题，两模型生成 + BGE 语义相似度 + 关键词覆盖。

只做本地/离线评估，不调用云端 LLM；质量是代理读数（相似度/覆盖/长度），
用于给本地模型 Pareto 补上「质量」维度。用本地模型环境运行：
  local_model/envs/dgtf_llm_env/Scripts/python.exe scripts/local_model_quality.py --json
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BGE = "http://127.0.0.1:8771"
MODELS = {
    "qwen05": ROOT / "local_model" / "models" / "Qwen2.5-0.5B-Instruct",
    "deepseek15": ROOT / "local_model" / "models" / "DeepSeek-R1-Distill-Qwen-1.5B",
}
PROMPTS = [
    {"q": "为什么城市热岛效应在夜间比白天更明显？",
     "ref": "夜间城市储热释放、郊区辐射冷却快、风速低、云量少，城乡温差因此更大。",
     "kw": ["夜间", "城乡", "储热", "辐射", "风速"]},
    {"q": "四层螺旋推理里，研究层和对撞层分别负责什么？",
     "ref": "研究层负责把问题拆成可判定子问题并求证据；对撞层负责让不同结论互相碰撞、裁决冲突。",
     "kw": ["研究", "子问题", "证据", "对撞", "冲突"]},
    {"q": "给出一个判断证据是否可判定的简单判据。",
     "ref": "证据能定位到具体来源、时间与主体，并且存在可被反例推翻的明确条件。",
     "kw": ["来源", "时间", "主体", "反例", "条件"]},
]


def _embed(texts):
    req = urllib.request.Request(BGE + "/embed",
                                 data=json.dumps({"texts": texts}).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return (json.loads(r.read().decode("utf-8", "replace")) or {}).get("vectors") or []


def _cos(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    return num / (da * db) if da and db else 0.0


def _generate(model, tok, prompt, max_new_tokens):
    import torch
    messages = [{"role": "user", "content": prompt}]
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok([text], return_tensors="pt").to(model.device)
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new_tokens,
                             do_sample=False, pad_token_id=tok.eos_token_id)
    dt = time.perf_counter() - t0
    ans = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    return ans, dt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-new-tokens", type=int, default=64)
    args = ap.parse_args()
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    if not _embed(["模"]):
        print(json.dumps({"ok": False, "error": "BGE /embed unavailable"}))
        return 1
    rows = []
    for name, path in MODELS.items():
        if not path.exists():
            continue
        t0 = time.perf_counter()
        tok = AutoTokenizer.from_pretrained(str(path), trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            str(path), dtype=dtype, trust_remote_code=True).to(device)
        model.eval()
        load_s = time.perf_counter() - t0
        for p in PROMPTS:
            ans, dt = _generate(model, tok, p["q"], args.max_new_tokens)
            vs = _embed([ans, p["ref"]]) if ans else []
            sim = _cos(vs[0], vs[1]) if len(vs) == 2 else 0.0
            hits = sum(1 for k in p["kw"] if k in ans)
            kw_cov = hits / len(p["kw"]) if p["kw"] else 0.0
            len_score = min(1.0, len(ans) / 80.0)
            proxy = round(0.5 * max(0.0, sim) + 0.3 * kw_cov + 0.2 * len_score, 3)
            rows.append({"model": name, "question": p["q"], "seconds": round(dt, 2),
                          "answer_chars": len(ans), "similarity": round(sim, 3),
                          "keyword_coverage": round(kw_cov, 3), "quality_proxy": proxy,
                          "answer": ans[:160]})
        del model
        if device == "cuda":
            torch.cuda.empty_cache()
        rows.append({"model": name, "load_seconds": round(load_s, 2)})
    # 汇总
    summary = {}
    for r in rows:
        m = r.get("model")
        if "quality_proxy" not in r:
            continue
        summary.setdefault(m, {"n": 0, "proxy": [], "sim": [], "kw": [], "sec": []})
        s = summary[m]
        s["n"] += 1
        s["proxy"].append(r["quality_proxy"])
        s["sim"].append(r["similarity"])
        s["kw"].append(r["keyword_coverage"])
        s["sec"].append(r["seconds"])
    summary = {k: {"n": v["n"],
                   "quality_proxy_p50": round(statistics.median(v["proxy"]), 3),
                   "similarity_p50": round(statistics.median(v["sim"]), 3),
                   "keyword_coverage_p50": round(statistics.median(v["kw"]), 3),
                   "latency_p50_s": round(statistics.median(v["sec"]), 2)}
               for k, v in summary.items()}
    out = {"ok": True, "device": device, "rows": rows, "summary": summary}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            if "load_seconds" in r:
                print("[load] %s %.2fs" % (r["model"], r["load_seconds"]))
            else:
                print("%-11s %.2fs sim=%.2f kw=%.2f proxy=%.3f" % (
                    r["model"], r["seconds"], r["similarity"],
                    r["keyword_coverage"], r["quality_proxy"]))
        print("summary:", json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
