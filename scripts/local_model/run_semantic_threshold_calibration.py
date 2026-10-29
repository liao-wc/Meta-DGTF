# -*- coding: utf-8 -*-
"""[V2.2.49] 语义缓存阈值边界标定（本地 BGE，零 API）。

验证 0.98 阈值：>=0.98 命中；<0.98 不命中；并测不同 HTTP 状态码的误命中风险。
证据 docs/semantic_threshold_calibration_20261030.json
"""
from __future__ import annotations

import json
import math
import time
import urllib.request
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dgtf_engine"))
sys.path.insert(0, str(ROOT / "dgtf_app"))
import daosheng_mode as DS  # noqa: E402

BASE = "为什么在高原上煮饭更容易夹生？"
VARIANTS = [
    "为什么高原上煮饭更容易夹生？",
    "在高原上煮饭为什么容易夹生？",
    "为什么高原上煮饭容易夹生？",
    "为什么在高原上煮饭容易夹生",
    "为什么在高原上做饭更容易夹生？",
    "为什么在高原上煮饭会夹生？",
]
HTTP_BASE = "HTTP 431状态码表示什么？"
HTTP_VARIANTS = ["HTTP 421 状态码表示什么？", "HTTP 425 状态码表示什么？",
                 "HTTP 432 状态码表示什么？"]


def _emb(texts):
    req = urllib.request.Request(
        "http://127.0.0.1:8771/embed",
        data=json.dumps({"texts": list(texts)}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))["vectors"]


def _sims(base, variants):
    vs = _emb([base] + variants)
    b = vs[0]
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    out = []
    for v, vec in zip(variants, vs[1:]):
        nv = math.sqrt(sum(x * x for x in vec)) or 1.0
        s = sum(a * c for a, c in zip(b, vec)) / (nb * nv)
        out.append((round(s, 4), v))
    return out


def main():
    t0 = time.time()
    rows = []
    for sim, v in _sims(BASE, VARIANTS):
        probe = DS._semantic_cache_probe(v, {"web": "off"})
        rows.append({"question": v, "raw_similarity": sim,
                     "probe_hit": bool(probe), "probe_similarity":
                     (probe or {}).get("similarity") if probe else None,
                     "expected": sim >= 0.98})
        print("[thr]", json.dumps(rows[-1], ensure_ascii=False), flush=True)
    http_rows = []
    for sim, v in _sims(HTTP_BASE, HTTP_VARIANTS):
        probe = DS._semantic_cache_probe(v, {"web": "on"})
        http_rows.append({"question": v, "raw_similarity": sim,
                          "probe_hit": bool(probe),
                          "probe_similarity": (probe or {}).get("similarity")
                          if probe else None})
        print("[thr-http]", json.dumps(http_rows[-1], ensure_ascii=False),
              flush=True)
    out = {"schema": "metadgtf.semantic_threshold_calibration.v1",
           "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
           "base_question": BASE, "threshold": DS._SEMANTIC_MIN_SIM,
           "rows": rows, "http_false_positive": http_rows,
           "summary": {
               "hits_above_threshold": sum(1 for r in rows
                                           if r["raw_similarity"] >= 0.98
                                           and r["probe_hit"]),
               "misses_below_threshold": sum(1 for r in rows
                                             if r["raw_similarity"] < 0.98
                                             and not r["probe_hit"]),
               "total": len(rows),
               "max_http_similarity": max((r["raw_similarity"]
                                          for r in http_rows), default=0),
               "http_hits": sum(1 for r in http_rows if r["probe_hit"]),
           },
           "wall_s": round(time.time() - t0, 2)}
    (ROOT / "docs" / "semantic_threshold_calibration_20261030.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("summary:", json.dumps(out["summary"], ensure_ascii=False))
    print("evidence -> docs/semantic_threshold_calibration_20261030.json")


if __name__ == "__main__":
    main()
