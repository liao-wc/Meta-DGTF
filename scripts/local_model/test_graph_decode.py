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

    # ── [V2.2.15] graph 采样 / 重复惩罚 / 复用 / base stage 适配器隔离 ──
    # ★ 这些判据只在「新版服务」上成立；旧服务没有 graph_key 字段 ⇒ 判红而不是假绿。
    u2 = uuid.uuid4().hex[:8]
    base_req = {"stage": "re_anchor",
                "text": "把这句话重述成 JSON：水的三态变化有哪些驱动因素 [%s]" % u2,
                "max_new_tokens": 32, "timeout": 90}
    d4 = _post({**base_req, "temperature": 0.3, "repetition_penalty": 1.2})
    ck("G4 ★ temp>0 走 CUDA graph（此前只有 temp==0 能走）",
       d4.get("graph") is True and d4.get("sampled") is True,
       {k: d4.get(k) for k in ("graph", "sampled", "ms")})
    ck("G5 ★ base stage 的 graph 是共用 base 图 + 适配器为空（未被别的 LoRA 污染）",
       d4.get("graph_key") == "base" and not d4.get("adapter"),
       {k: d4.get(k) for k in ("graph_key", "adapter")})
    ck("G6 ★ repetition_penalty 透传到服务并回显（0.5B 复读治理）",
       abs(float(d4.get("rep_pen") or 0) - 1.2) < 1e-6, d4.get("rep_pen"))
    d5 = _post({"stage": "dual_judge",
                "text": '{"anchor":"gs%s","candidates":[{"desc":"甲"},{"desc":"乙"}]}' % u2,
                "max_new_tokens": 32, "temperature": 0.3, "timeout": 90})
    ck("G7 ★ LoRA stage 用专属 graph（adapter::dual_judge）",
       d5.get("graph_key") == "adapter::dual_judge", d5.get("graph_key"))
    d6 = _post({**base_req, "temperature": 0.0, "text": base_req["text"] + " zero"})
    ck("G8 temp==0 仍走 graph 且 sampled=False（贪心路径没被改坏）",
       d6.get("graph") is True and d6.get("sampled") is False,
       {k: d6.get(k) for k in ("graph", "sampled")})
    m2 = json.loads(urllib.request.urlopen(BASE + "/metrics", timeout=5).read().decode())
    st2 = m2.get("stats") or {}
    ck("G9 ★ metrics 有 graph_sampled_generations（采样也走 graph 的证据）",
       int(st2.get("graph_sampled_generations") or 0) >= 1,
       st2.get("graph_sampled_generations"))
    keys = st2.get("graph_capture_keys") or []
    base_keys = [k for k in keys if k == "base"]
    ck("G10 ★ base stage 只捕获一张 graph（复用生效；18 张→5 张的显存前提）",
       len(base_keys) == 1, keys)
    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
