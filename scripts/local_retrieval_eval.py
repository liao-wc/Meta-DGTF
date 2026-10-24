# -*- coding: utf-8 -*-
"""本地 BGE 检索质量代理：小语料 recall@1/@3 + MRR（只用本地 /embed 服务）。

用途：给本地模型 Pareto 补「质量」维度（不只吞吐/时延）。
用法：python scripts/local_retrieval_eval.py [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time
import urllib.request
from pathlib import Path

BGE = "http://127.0.0.1:8771"
CORPUS = [
    ("c01", "四层螺旋推理包含修行层、研究层、对撞层和元层；修行层显形问题，研究层拆可判定子问题。"),
    ("c02", "对撞层让不同结论互相碰撞并裁决冲突，元层负责结晶决策、行动与残余风险。"),
    ("c03", "城市热岛效应在夜间更明显，因为城市储热释放、郊区辐射冷却快、风速低。"),
    ("c04", "证据可判定性要求证据能定位到来源、时间与主体，并且存在可被反例推翻的条件。"),
    ("c05", "帕累托前沿由所有非支配点组成：质量更高、成本更低或时延更短的改进不会同时牺牲其他目标。"),
    ("c06", "DeepSeek 官方联网检索使用 /v1/tools/search，抓取使用 /v1/tools/fetch，共用 DGTF_API_KEY。"),
    ("c07", "App 健康读数缓存 TTL 为 2 秒，会话列表缓存 TTL 为 1 秒，用于降低轮询时延。"),
    ("c08", "本地 BGE 服务提供 /embed 批量向量，维度 512，设备 cuda，适合检索与记忆召回。"),
    ("c09", "质量门包含 answer_ready、process_ready、answer_quality、coverage 与 flags 等读数。"),
    ("c10", "职责读数 S 由核心覆盖 C、实词覆盖 R 与问项交付面共同决定，低于下限会挂 duty_short。"),
    ("c11", "预算选档在 tokens 预算与最低质量约束下选择质量最高的非支配运行配置。"),
    ("c12", "V2.2.2 补丁根治 duty_short 与 unsaid_overused，并默认切换到 DeepSeek 官方联网。"),
]
QUERIES = [
    ("q1", "夜间城市热岛为什么更明显", ["c03"]),
    ("q2", "证据可判定的条件是什么", ["c04"]),
    ("q3", "帕累托前沿的定义", ["c05"]),
    ("q4", "DeepSeek 官方检索和抓取接口", ["c06"]),
    ("q5", "App 健康与会话缓存 TTL", ["c07"]),
    ("q6", "职责读数 duty_short 怎么来的", ["c10"]),
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    ids = [c[0] for c in CORPUS]
    texts = [c[1] for c in CORPUS]
    t0 = time.perf_counter()
    cvec = _embed(texts)
    corpus_ms = (time.perf_counter() - t0) * 1000
    if len(cvec) != len(texts):
        print(json.dumps({"ok": False, "error": "BGE embed failed"}))
        return 1
    rows = []
    for qid, q, rel in QUERIES:
        t1 = time.perf_counter()
        qv = _embed([q])[0]
        q_ms = (time.perf_counter() - t1) * 1000
        scores = [(cid, _cos(qv, cv)) for cid, cv in zip(ids, cvec)]
        scores.sort(key=lambda x: x[1], reverse=True)
        order = [cid for cid, _ in scores]
        rank = order.index(rel[0]) + 1 if rel[0] in order else 999
        rows.append({"query": q, "relevant": rel[0], "rank": rank,
                     "top1": order[0], "top3": order[:3],
                     "recall@1": 1.0 if rank == 1 else 0.0,
                     "recall@3": 1.0 if rank <= 3 else 0.0,
                     "reciprocal_rank": round(1.0 / rank, 3) if rank < 999 else 0.0,
                     "query_embed_ms": round(q_ms, 2)})
    summary = {
        "n": len(rows),
        "recall@1": round(sum(r["recall@1"] for r in rows) / len(rows), 3),
        "recall@3": round(sum(r["recall@3"] for r in rows) / len(rows), 3),
        "mrr": round(sum(r["reciprocal_rank"] for r in rows) / len(rows), 3),
        "corpus_embed_ms": round(corpus_ms, 2),
        "query_embed_ms_p50": round(statistics.median([r["query_embed_ms"] for r in rows]), 2),
        "corpus_texts": len(texts),
    }
    out = {"ok": True, "summary": summary, "rows": rows}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("BGE 检索质量：n=%d recall@1=%.3f recall@3=%.3f MRR=%.3f"
              % (summary["n"], summary["recall@1"], summary["recall@3"], summary["mrr"]))
        print("corpus embed %.1fms（%d 条）；query embed p50 %.1fms"
              % (summary["corpus_embed_ms"], summary["corpus_texts"],
                 summary["query_embed_ms_p50"]))
        for r in rows:
            print("  %-22s rank=%d top1=%s" % (r["query"], r["rank"], r["top1"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
