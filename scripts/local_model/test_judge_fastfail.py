# -*- coding: utf-8 -*-
"""本地 judge 快失败判据（Round 125，零 API，需要 8772 服务在线）。

L1：并发两个 dual_judge 请求时，至少一个在 ~3s 内收到 503 BUSY（快速回退信号）。
L2：/metrics 的 stats.dual_judge_fastfail 计数 > 0。
L3：空闲时单发 dual_judge 仍返回 200（不误伤正常请求）。
"""
from __future__ import annotations

import json
import threading
import uuid
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8772"
P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


def _post(stage: str, text: str, max_new: int = 24, timeout: float = 120):
    body = json.dumps({"stage": stage, "text": text,
                       "max_new_tokens": max_new, "temperature": 0.0,
                       "timeout": timeout}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE + "/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout + 5) as f:
            return f.status, f.read().decode("utf-8", "replace"), (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), (time.perf_counter() - t0) * 1000
    except Exception as e:  # noqa: BLE001
        return 0, "%s: %s" % (type(e).__name__, e), (time.perf_counter() - t0) * 1000


def main() -> int:
    try:
        h = json.loads(urllib.request.urlopen(BASE + "/health", timeout=5).read().decode())
    except Exception as e:  # noqa: BLE001
        print("SKIP: 服务不可达（%s）" % e)
        return 0
    if h.get("status") != "ready":
        print("SKIP: 服务状态 %s" % h.get("status"))
        return 0

    results = {}
    _uniq = uuid.uuid4().hex[:8]

    def one(k):
        # 唯一 anchor：避免 LRU 缓存命中（否则并发两个请求都会毫秒级 200）
        _txt = ("判断以下候选位置：{\"anchor\":\"测试%s%s\","
                "\"candidates\":[{\"desc\":\"甲\"},{\"desc\":\"乙\"}]}"
                % (_uniq, k))
        results[k] = _post("dual_judge", _txt, max_new=24, timeout=60)

    t1 = threading.Thread(target=one, args=("a",), daemon=True)
    t2 = threading.Thread(target=one, args=("b",), daemon=True)
    t1.start(); time.sleep(0.05); t2.start()
    t1.join(timeout=180); t2.join(timeout=180)
    codes = {k: v[0] for k, v in results.items()}
    fast_busy = [k for k, v in results.items()
                 if v[0] == 503 and "BUSY" in v[1] and v[2] < 3000]
    ck("L1 并发 dual_judge 至少一个 503 BUSY 且 <3s",
       bool(fast_busy), (codes, {k: round(v[2]) for k, v in results.items()}))

    m = json.loads(urllib.request.urlopen(BASE + "/metrics", timeout=5).read().decode())
    ff = int((m.get("stats") or {}).get("dual_judge_fastfail", 0) or 0)
    ck("L2 metrics.dual_judge_fastfail > 0", ff > 0, ff)

    time.sleep(2.0)
    code, txt, ms = _post("dual_judge",
                          "判断以下候选位置：{\"anchor\":\"测试\",\"candidates\":[{\"desc\":\"甲\"}]}",
                          max_new=16, timeout=120)
    ck("L3 空闲单发 dual_judge 仍 200", code == 200, (code, round(ms), txt[:120]))

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
