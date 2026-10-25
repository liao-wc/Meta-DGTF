# -*- coding: utf-8 -*-
"""8772 本地推理服务实测探针：/health 时延、/generate p50/p95、JSON 合法率、
错误回退（400/503）、并发串行化。

用法：
  python scripts/local_model/probe_local_llm.py --port 8772 --reps 3
输出：llm_sft/dgtf_stage/service_probe.json + 控制台表格
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "llm_sft" / "dgtf_stage"


def post(port: int, payload: dict, timeout: float = 120):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/generate", data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8"))
            return r.status, body, round((time.time() - t0) * 1000, 1)
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode("utf-8"))
        return e.code, body, round((time.time() - t0) * 1000, 1)


def get_health(port: int) -> tuple[dict, float]:
    t0 = time.time()
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health",
                                timeout=5) as r:
        return json.loads(r.read().decode("utf-8")), round(
            (time.time() - t0) * 1000, 1)


def pctl(xs, q):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(len(xs) * q))], 1)


def load_sample(stage: str) -> dict | None:
    f = {"dual_judge": "dual_judge_val.jsonl",
         "self_check": "self_check_val.jsonl",
         "self_check_min": "self_check_min_val.jsonl"}.get(stage)
    if f is None:
        return None
    p = DATA / f
    if not p.exists():
        return None
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
            if x.strip()]
    return rows[0] if rows else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8772)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--out", default="llm_sft/dgtf_stage/service_probe.json")
    ap.add_argument("--stages", default="self_check_min,self_check,dual_judge,route")
    args = ap.parse_args()
    port = args.port

    # ---------- 1. /health ----------
    health, hms = get_health(port)
    h_times = []
    for _ in range(5):
        h, ms = get_health(port)
        h_times.append(ms)
    print(f"[health] status={health.get('status')} ok={health.get('ok')} "
          f"p50={pctl(h_times, 0.5)}ms max={max(h_times)}ms "
          f"gpu_mem={health.get('gpu_mem_mb')}MB "
          f"adapters={health.get('adapters')}")
    if health.get("status") != "ready":
        print("服务未 ready，终止")
        return 1

    # ---------- 2. /generate 各 stage ----------
    stages = tuple(x.strip() for x in args.stages.split(",") if x.strip())
    max_new = {"self_check_min": 96, "self_check": 128,
               "dual_judge": 224, "route": 96}
    results = {"health": {"status": health.get("status"),
                          "p50_ms": pctl(h_times, 0.5),
                          "max_ms": max(h_times),
                          "gpu_mem_mb": health.get("gpu_mem_mb"),
                          "adapters": health.get("adapters")},
               "generate": {}, "errors": {}, "concurrency": None,
               "port": port}
    for stage in stages:
        sample = load_sample(stage)
        if sample is not None:
            payload_msgs = sample["messages"][:-1]
            gold = sample["messages"][-1]["content"]
        else:
            payload_msgs = [{"role": "user", "content": "2+2等于几？"}]
            gold = None
        lat, oks, confs, texts = [], [], [], []
        for i in range(args.reps):
            code, body, ms = post(port, {
                "stage": stage, "messages": payload_msgs,
                "max_new_tokens": max_new[stage], "temperature": 0.0,
                "timeout": 90})
            lat.append(ms)
            oks.append(bool(body.get("ok") and body.get("json") is not None))
            confs.append(body.get("confidence"))
            if i == 0:
                texts.append((body.get("text") or "")[:300])
        print(f"[generate:{stage}] n={args.reps} p50={pctl(lat, 0.5)}ms "
              f"p95={pctl(lat, 0.95)}ms json_ok={sum(oks)}/{len(oks)} "
              f"conf={confs[0]} out={texts[0][:120]!r}")
        results["generate"][stage] = {
            "n": args.reps, "p50_ms": pctl(lat, 0.5),
            "p95_ms": pctl(lat, 0.95),
            "mean_ms": round(statistics.mean(lat), 1),
            "json_ok": f"{sum(oks)}/{len(oks)}",
            "confidence": confs[0],
            "sample_output": texts[0] if texts else "",
            "gold": gold[:200] if gold else None,
        }

    # ---------- 3. 错误回退 ----------
    code, body, ms = post(port, {"stage": "nope", "text": "x", "timeout": 5})
    results["errors"]["bad_stage"] = {"http": code,
                                      "body": body.get("error")}
    print(f"[error:bad_stage] http={code} {body.get('error')}")
    code, body, ms = post(port, {"stage": "self_check_min", "text": "x",
                                 "max_new_tokens": 512, "timeout": 1})
    results["errors"]["timeout"] = {"http": code, "body": body.get("error"),
                                    "ms": ms}
    print(f"[error:timeout] http={code} {body.get('error')} took={ms}ms")
    code, body, ms = post(port, {"stage": "self_check_min", "timeout": 5})
    results["errors"]["missing_input"] = {"http": code,
                                          "body": body.get("error")}
    print(f"[error:missing_input] http={code} {body.get('error')}")

    # ---------- 4. 并发 3 请求（应为串行队列，不 OOM） ----------
    outs = []

    def _one(i):
        code, body, ms = post(port, {
            "stage": "self_check_min", "text": f"并发探针 {i}",
            "max_new_tokens": 16, "temperature": 0.0, "timeout": 90})
        outs.append((code, body.get("ok"), ms))

    ths = [threading.Thread(target=_one, args=(i,)) for i in range(3)]
    t0 = time.time()
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    wall = round((time.time() - t0) * 1000, 1)
    results["concurrency"] = {"n": 3, "wall_ms": wall,
                              "results": [{"http": c, "ok": o, "ms": m}
                                          for c, o, m in outs]}
    print(f"[concurrency] 3 请求 wall={wall}ms results={outs}")

    results["tested_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"[probe] saved -> {out.relative_to(ROOT)}")
    print("PROBE_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
