# -*- coding: utf-8 -*-
"""本地模型基线：BGE 服务健康 + 批量 embedding 时延/吞吐（只读 HTTP）。

用法：python scripts/local_model_bench.py [--json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BGE = "http://127.0.0.1:8771"
TEXTS = [
    "城市热岛效应在夜间比白天更明显",
    "四层螺旋推理：修行、研究、对撞、元",
    "证据链与事实卡的可判定性审计",
    "帕累托前沿：质量、成本、时延的权衡",
    "本地 embedding 服务吞吐基线",
    "多智能体自进化与确定性护栏",
    "会话独立窗口与实时镜像",
    "预算内选档与回滚边界",
]


def _req(url, payload=None, timeout=15):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = {"bge": {}, "batches": []}
    try:
        h = _req(BGE + "/health")
        out["bge"] = {"ok": bool(h.get("ok")), "device": h.get("dev"),
                      "dim": h.get("dim"), "model": h.get("model")}
    except Exception as e:
        out["bge"] = {"ok": False, "error": str(e)[:120]}
        print(json.dumps(out, ensure_ascii=False))
        return 1
    for n in (1, 4, 8, 16, 32, 64):
        texts = [TEXTS[i % len(TEXTS)] for i in range(n)]
        lat = []
        for _ in range(3):
            t0 = time.perf_counter()
            try:
                r = _req(BGE + "/embed", {"texts": texts})
                ok = bool(r.get("ok")) and len(r.get("vectors") or []) == n
                lat.append((time.perf_counter() - t0) * 1000)
            except Exception:
                ok = False
            if not ok:
                lat = []
                break
        row = {"n": n, "ok": bool(lat),
               "p50_ms": round(statistics.median(lat), 2) if lat else None,
               "texts_per_s": round(n / (statistics.median(lat) / 1000), 1) if lat else None}
        out["batches"].append(row)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("BGE:", json.dumps(out["bge"], ensure_ascii=False))
        for r in out["batches"]:
            print("batch n=%-2d ok=%s p50=%sms throughput=%s texts/s"
                  % (r["n"], r["ok"], r["p50_ms"], r["texts_per_s"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
