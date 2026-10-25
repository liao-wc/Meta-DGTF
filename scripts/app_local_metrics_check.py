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
