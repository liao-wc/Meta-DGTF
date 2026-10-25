# -*- coding: utf-8 -*-
"""Round 26 验证脚本：App 本地服务 busy → self_check 云端回退（离线，可用真实服务）。

用法：
  python scripts/app_local_metrics_check.py           # 真实服务 metrics 探测
  python scripts/app_local_metrics_check.py --sim    # 模拟 busy，验证 plan 回退逻辑
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_app"))
sys.path.insert(0, str(ROOT / "dgtf_engine"))
sys.path.insert(0, str(ROOT))

import daosheng_mode as dm  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--real-busy", action="store_true",
                    help="并发注入本地服务负载，验证真实 busy 信号 + plan 回退")
    args = ap.parse_args()
    ok = 0
    fail = 0

    def ck(name, cond, info=""):
        nonlocal ok, fail
        if cond:
            ok += 1
        else:
            fail += 1
        print(("PASS " if cond else "FAIL ") + name +
              ((" :: " + str(info)) if info and not cond else ""))

    m = dm.local_llm_metrics(force=True)
    ck("① /metrics 可达且含 busy/avg_ms",
       m.get("ok") is True and "busy" in m, m)
    ck("② metrics 字段完整",
       all(k in m for k in ("busy", "avg_ms", "requests_total", "adapter")), m)

    if args.real_busy:
        import json as _json
        import threading
        import time as _time
        import urllib.request as _ur
        base = "http://127.0.0.1:8772/generate"
        loads = []

        def _hit(i):
            body = _json.dumps({"stage": "self_check_min",
                                "text": '["并发注入%d","a","b"] 输出 JSON' % i,
                                "max_new_tokens": 400}).encode()
            req = _ur.Request(base, data=body,
                              headers={"Content-Type": "application/json"})
            try:
                with _ur.urlopen(req, timeout=240) as f:
                    loads.append(_json.loads(f.read().decode()).get("ms"))
            except Exception as e:  # noqa: BLE001
                loads.append("ERR:%s" % e)

        ths = [threading.Thread(target=_hit, args=(i,), daemon=True)
               for i in range(3)]
        for th in ths:
            th.start()
        _time.sleep(1.2)
        busy_seen = False
        for _ in range(6):
            mm = dm.local_llm_metrics(force=True)
            if mm.get("ok") and mm.get("busy"):
                busy_seen = True
                break
            _time.sleep(0.5)
        ck("① 并发注入下 /metrics 观察到 real busy=True", busy_seen, mm)
        real_metrics = dm.local_llm_metrics
        real_preset = dm.load_preset

        def fake_metrics(preset=None, force=False):
            return dm.local_llm_metrics(preset, force=True) if False else {
                "ok": True, "busy": True, "avg_ms": 9999.0,
                "requests_total": 1, "errors": 0, "adapter": {}}

        def fake_preset():
            ds = dict(real_preset())
            ds["self_check_mode"] = "local"
            return ds

        dm.local_llm_metrics = fake_metrics
        dm.load_preset = fake_preset
        try:
            plan = dm.build_plan("HTTP 500状态码表示什么？", {},
                                 requested="daosheng", is_mock=True,
                                 balance_cny=999.0)
            ck("② busy 下 plan 回退云端 llm",
               plan.get("self_check_mode") == "llm"
               and plan.get("self_check_mode_via") == "busy-fallback",
               (plan.get("self_check_mode"), plan.get("self_check_mode_via")))
            ck("③ plan warnings 记录回退",
               any("本地服务忙" in str(x) for x in (plan.get("warnings") or [])))
        finally:
            dm.local_llm_metrics = real_metrics
            dm.load_preset = real_preset
        for th in ths:
            th.join(timeout=120)
        ck("④ 并发注入请求全部成功", all(isinstance(x, (int, float))
                                        for x in loads), loads[:3])

    if args.sim:
        real_metrics = dm.local_llm_metrics
        real_preset = dm.load_preset

        def fake_metrics(preset=None, force=False):
            return {"ok": True, "busy": True, "avg_ms": 9000.0,
                    "requests_total": 3, "errors": 0, "adapter": {}}

        def fake_preset():
            ds = dict(real_preset())
            ds["self_check_mode"] = "local"
            return ds

        dm.local_llm_metrics = fake_metrics
        dm.load_preset = fake_preset
        try:
            plan = dm.build_plan("HTTP 404状态码表示什么？", {},
                                 requested="daosheng", is_mock=True,
                                 balance_cny=999.0)
            ck("③ busy + 预设 local → self_check_mode=llm",
               str(plan.get("self_check_mode")) == "llm", plan.get("self_check_mode"))
            ck("④ via=busy-fallback", str(plan.get("self_check_mode_via"))
               == "busy-fallback", plan.get("self_check_mode_via"))
            ck("⑤ warnings 记录本地忙回退",
               any("本地服务忙" in str(x) for x in (plan.get("warnings") or [])),
               plan.get("warnings"))
            ck("⑥ plan.local_llm.metrics 可审计",
               isinstance((plan.get("local_llm") or {}).get("metrics"), dict))
        finally:
            dm.local_llm_metrics = real_metrics
            dm.load_preset = real_preset
    print("\nTOTAL PASS %d / FAIL %d" % (ok, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
