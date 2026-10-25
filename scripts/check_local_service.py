# -*- coding: utf-8 -*-
"""本地服务可观测性/并发检查（Round 25，零 API 成本，结果可复现）。

用法：
  python scripts/check_local_service.py                    # health+metrics+单次 generate
  python scripts/check_local_service.py --concurrency 4    # 并发 4 请求（测串行化/排队）
  python scripts/check_local_service.py --out llm_sft/service_metrics_probe.json
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8772"


def _get(path: str, timeout: float = 5.0):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as f:
        return json.loads(f.read().decode("utf-8"))


def _gen(i: int, timeout: float = 180.0):
    body = json.dumps({"stage": "self_check_min",
                       "text": '["测试%d","候选A","候选B"] 输出 self_check_min JSON'
                              % i,
                       "max_new_tokens": 100}).encode("utf-8")
    req = urllib.request.Request(BASE + "/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as f:
            r = json.loads(f.read().decode("utf-8"))
        return {"ok": bool(r.get("ok", True)), "wall_s": round(time.time() - t0, 2),
                "ms": r.get("ms"), "adapter": r.get("adapter")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "wall_s": round(time.time() - t0, 2),
                "error": "%s: %s" % (type(e).__name__, e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    out: dict = {"base": BASE, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        out["health"] = _get("/health")
        out["metrics_before"] = _get("/metrics")
    except Exception as e:  # noqa: BLE001
        out["error"] = "服务不可达: %s" % e
        print(json.dumps(out, ensure_ascii=False)[:400])
        return 1
    n = max(1, int(args.concurrency))
    t0 = time.time()
    if n == 1:
        out["runs"] = [_gen(0)]
    else:
        with ThreadPoolExecutor(max_workers=n) as ex:
            out["runs"] = list(ex.map(_gen, range(n)))
    out["total_wall_s"] = round(time.time() - t0, 2)
    out["metrics_after"] = _get("/metrics")
    out["serialized"] = bool(
        out["total_wall_s"] > 1.5 * max(
            [r.get("ms") or 0 for r in out["runs"]] or [1]) / 1000.0)
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print("health:", out["health"].get("status"),
          "| adapters:", json.dumps((out["health"].get("adapter_paths")
                                     or {}), ensure_ascii=False)[:160])
    print("runs:", [(r.get("ok"), r.get("wall_s"), r.get("ms")) for r in out["runs"]])
    print("total wall:", out["total_wall_s"], "s | serialized:", out["serialized"])
    _lat = (out["metrics_after"].get("latency") or {}) if isinstance(
        out["metrics_after"], dict) else {}
    if _lat:
        print("latency: n=%s p50=%sms p95=%sms mean=%sms"
              % (_lat.get("n"), _lat.get("p50"), _lat.get("p95"),
                 _lat.get("mean")))
    st = (out["metrics_after"].get("stats") or {})
    print("metrics: total=%s avg_ms=%s by_stage=%s errors=%s"
          % (st.get("requests_total"), out["metrics_after"].get("avg_ms"),
             st.get("by_stage"), st.get("errors")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
