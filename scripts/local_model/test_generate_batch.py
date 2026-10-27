# -*- coding: utf-8 -*-
"""服务端批量生成判据（Round 146，零 API，需要 8772 在线）。

B1：/generate_batch 对 2 条 dual_judge 请求返回 2 条结果（ok + JSON 可解析）。
B2：批量返回的 gen_tokens/ms 存在（可审计）。
B3：根端点列表包含 /generate_batch。
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
    reqs = [{"stage": "dual_judge",
             "text": '{"anchor":"批测%s%d","candidates":[{"desc":"甲"},{"desc":"乙"}]}' % (u, i),
             "max_new_tokens": 64, "temperature": 0.0, "timeout": 120}
            for i in (1, 2)]
    body = json.dumps({"requests": reqs, "timeout": 120}, ensure_ascii=False).encode()
    req = urllib.request.Request(BASE + "/generate_batch", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as f:
            d = json.loads(f.read().decode())
    except Exception as e:  # noqa: BLE001
        ck("B1 /generate_batch 返回 2 条结果", False, str(e))
        print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
        return 1
    rs = d.get("results") or []
    ck("B1 /generate_batch 返回 2 条结果", len(rs) == 2, (len(rs), d.get("ms")))
    ok_json = sum(1 for r in rs if r.get("ok") and isinstance(r.get("json"), dict))
    ck("B2 结果含 JSON 与 gen_tokens", ok_json == 2
       and all(r.get("gen_tokens") is not None for r in rs), ok_json)
    root = json.loads(urllib.request.urlopen(BASE + "/", timeout=5).read().decode())
    ck("B3 端点列表含 /generate_batch",
       "/generate_batch" in (root.get("endpoints") or []), root.get("endpoints"))
    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
