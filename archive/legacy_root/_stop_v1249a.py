# -*- coding: utf-8 -*-
"""把被**主动终止**的 A 跑快照按真实原因留痕（不是崩溃，是用户要求停手）。

★ 为什么手工写这条：引擎侧目前只有两条路 —— `stop_run_ckpt`（要在跑进程里，
拿得到 `stop_evt`）与 `recover_orphan_runs`（自动判据给的 why 恒定是
「进程被回收/崩溃」）。本次是**跑外主动停**，前者的 why 会失真、后者拿不到
`evt`。为了不留一条**错的原因**在库里，这里用引擎自己的 `write_run_ckpt`
（同一条原子写路径）把 status/why 改准。

顺带清点抢救到的内容（这次是被杀/停手后的「能拿走什么」）。
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("m", str(HERE / "元DGTF-V1.23.49.py"))
m = importlib.util.module_from_spec(spec)
sys.modules["m"] = m
spec.loader.exec_module(m)

p = HERE / "outputs/_run_ckpt/V1249A_20261016_154031.json"
d = json.loads(p.read_text(encoding="utf-8"))
print("改前: status=%s n_views=%s 层=%s" % (d.get("status"), d.get("n_views"),
                                        sorted((d.get("views") or {}).keys())))
for k, v in sorted((d.get("views") or {}).items()):
    if isinstance(v, dict):
        print("  层 %s: 候选 %d / & %d / 线头 %d / 悬置 %d | 停因 %.40s"
              % (k, len(v.get("candidates") or []), len(v.get("amps") or []),
                 len(v.get("threads") or []), len(v.get("suspensions") or []),
                 str(v.get("stop_reason"))))

_rid = str(d.get("id"))
_start = time.strftime("%H:%M:%S", time.localtime(float(d.get("t") or 0)))
d["status"] = "interrupted"
d["interrupted_why"] = ("用户要求停手（成本优先）⇒ **主动终止（非崩溃/非回收）**；"
                        "跑次于 %s 起，最后一次心跳 %s"
                        % (_start, time.strftime("%H:%M:%S", time.localtime(float(d.get("t") or 0)))))
m.write_run_ckpt(_rid, d)

d2 = json.loads(p.read_text(encoding="utf-8"))
print("改后: status=%s why=%s" % (d2.get("status"), str(d2.get("interrupted_why"))[:80]))
print("（原子写路径 = 引擎自己的 write_run_ckpt）")
