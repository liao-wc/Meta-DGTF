# -*- coding: utf-8 -*-
"""CUDA graph 解码判据（Round 150，零 API，需要 8772 在线）。

G1：dual_judge 单请求走 graph 且返回合法 JSON。
G2：self_check_min 单请求（另一 stage，独立 graph 捕获）返回合法 JSON。
G3：/metrics graph_generations >= 2。
"""
from __future__ import annotations

import json
import urllib.request
import uuid

BASE = "http://127.0.0.1:8772"
P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


def _post(req):
    body = json.dumps(req, ensure_ascii=False).encode()
    r = urllib.request.Request(BASE + "/generate", data=body,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=120) as f:
        return json.loads(f.read().decode())


def main() -> int:
    try:
        h = json.loads(urllib.request.urlopen(BASE + "/health", timeout=5).read().decode())
    except Exception as e:  # noqa: BLE001
        print("SKIP: 服务不可达（%s）" % e)
        return 0
    if h.get("status") != "ready":
        print("SKIP: 服务状态 %s" % h.get("status"))
        return 0
    u = uuid.uuid4().hex[:8]
    d1 = _post({"stage": "dual_judge",
                "text": '{"anchor":"graph%s","candidates":[{"desc":"甲"},{"desc":"乙"}]}' % u,
                "max_new_tokens": 32, "temperature": 0.0, "timeout": 90})
    ck("G1 dual_judge graph 返回合法 JSON",
       bool(d1.get("json")) and d1.get("ok") is not False, d1.get("json"))
    d2 = _post({"stage": "self_check_min",
                "text": '{"anchor":"graph%s","candidates":[{"desc":"甲"}],"collision":""}' % u,
                "max_new_tokens": 32, "temperature": 0.0, "timeout": 90})
    ck("G2 self_check_min graph 返回合法 JSON",
       bool(d2.get("json")) and d2.get("ok") is not False, d2.get("json"))
    m = json.loads(urllib.request.urlopen(BASE + "/metrics", timeout=5).read().decode())
    g = int((m.get("stats") or {}).get("graph_generations") or 0)
    ck("G3 metrics.graph_generations >= 2", g >= 2, g)
    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
