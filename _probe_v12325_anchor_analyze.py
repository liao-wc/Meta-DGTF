#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从真产物里抽「锚点重述」与「探针」的数据，做系统性对照。

只读 packed.json，零 LLM。
"""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "outputs"


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def pick_latest(n=8):
    fs = sorted(OUT.glob("*.packed.json"), key=lambda x: x.stat().st_mtime)
    return fs[-n:]


print("=" * 100)
print("真产物 · 锚点重述 与 探针 数据抽取")
print("=" * 100)

for p in pick_latest():
    d = load(p)
    q = d.get("question", "")
    print("\n" + "─" * 100)
    print(f"■ {p.name[:70]}")
    print(f"  问题：{q[:70]}")
    views = d.get("views", {})
    for layer in ("0", "1"):
        lv = views.get(layer)
        if not isinstance(lv, dict):
            continue
        anchor = (lv.get("anchor") or "").strip()
        at = lv.get("anchor_touched") or []
        pr = lv.get("probes") or []
        ut = lv.get("untouched") or []
        rl = lv.get("round_log") or []
        print(f"\n  【{layer} 层】圈数={lv.get('rounds_run')} 停因={str(lv.get('stop_reason'))[:60]}")
        print(f"    锚点：{anchor[:110]}")
        print(f"    touched {len(at)} 条 / untouched {len(ut)} 条 / 探针 {len(pr)} 条")
        for t in at[:6]:
            print(f"      ✓ {str(t.get('desc',''))[:80]}")
        for u in ut[:8]:
            print(f"      ✗ {str(u.get('desc',''))[:80]}")
        for x in pr[:6]:
            print(f"      ? {str(x.get('question',''))[:80]}")
            print(f"        ↩ {str(x.get('link',''))[:70]}  gain={x.get('expected_gain')} covers={x.get('covers')}")
        print(f"    逐圈：")
        for r in rl:
            print(f"      r{r.get('round')} {r.get('role')}：新&={r.get('new_amps')} "
                  f"新线头={r.get('new_threads')} idle={r.get('idle_amp')}/{r.get('idle_thread')}"
                  f" stall={r.get('idle_stall')}")
