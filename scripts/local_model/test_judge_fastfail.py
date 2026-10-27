# -*- coding: utf-8 -*-
"""dual_judge 有界排队判据（Round 140，零 API，需要 8772 在线）。

L1（并发）：两个并发 dual_judge 请求都应完成；至少一个 200（排队后接管）。
L2（确定性 busy）：长请求占住单卡，第二个请求有界等待后仍 200（waited>0）。
L3：空闲单发仍 200。
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
import uuid

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
        with urllib.request.urlopen(req, timeout=timeout + 10) as f:
            return f.status, f.read().decode("utf-8", "replace"), (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), (time.perf_counter() - t0) * 1000
    except Exception as e:  # noqa: BLE001
        return 0, "%s: %s" % (type(e).__name__, e), (time.perf_counter() - t0) * 1000


def _judge_text(anchor: str, n: int = 2) -> str:
    cands = ",".join('{"desc":"%s"}' % ("甲乙丙丁"[i % 4]) for i in range(n))
    return ('{"anchor":"%s","candidates":[%s]}' % (anchor, cands))


def main() -> int:
    try:
        h = json.loads(urllib.request.urlopen(BASE + "/health", timeout=5).read().decode())
    except Exception as e:  # noqa: BLE001
        print("SKIP: 服务不可达（%s）" % e)
        return 0
    if h.get("status") != "ready":
        print("SKIP: 服务状态 %s" % h.get("status"))
        return 0

    _uniq = uuid.uuid4().hex[:8]
    results = {}

    def one(k):
        results[k] = _post("dual_judge", _judge_text("排队%s%s" % (_uniq, k)),
                           max_new=24, timeout=110)

    t1 = threading.Thread(target=one, args=("a",), daemon=True)
    t2 = threading.Thread(target=one, args=("b",), daemon=True)
    t1.start(); time.sleep(0.1); t2.start()
    t1.join(timeout=200); t2.join(timeout=200)
    oks = [k for k, v in results.items() if v[0] == 200]
    ck("L1 并发 dual_judge 至少一个 200（排队接管）", len(oks) >= 1,
       ({k: v[0] for k, v in results.items()},
        {k: round(v[2]) for k, v in results.items()}))

    # L2：确定性 busy —— 长请求先占住单卡，第二个请求应有界等待后 200。
    _slow = {}

    def _slow_one():
        _slow["r"] = _post("dual_judge", _judge_text("慢%s" % _uniq, n=3),
                           max_new=160, timeout=120)

    th = threading.Thread(target=_slow_one, daemon=True)
    th.start()
    time.sleep(2.0)
    code2, txt2, ms2 = _post("dual_judge", _judge_text("等%s" % _uniq, n=1),
                             max_new=16, timeout=120)
    th.join(timeout=240)
    m = json.loads(urllib.request.urlopen(BASE + "/metrics", timeout=5).read().decode())
    st = m.get("stats") or {}
    ck("L2 有界排队生效（waited>0 且排队请求 200）",
       int(st.get("dual_judge_waited") or 0) > 0 and code2 == 200,
       (st.get("dual_judge_waited"), code2, round(ms2)))

    time.sleep(1.0)
    code3, txt3, ms3 = _post("dual_judge", _judge_text("空闲%s" % _uniq, n=1),
                             max_new=16, timeout=120)
    ck("L3 空闲单发仍 200", code3 == 200, (code3, round(ms3), txt3[:100]))
    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
