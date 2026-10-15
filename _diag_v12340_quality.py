# -*- coding: utf-8 -*-
"""v1.23.40 诊断：扫真实产物，量化「运行中暴露的质量问题」。

只读 outputs/*.packed.json（不跑引擎、不改任何东西）。
输出：各产物的四层读数表 + 跨产物汇总（找系统性问题）。
"""
import glob
import json
import os
from collections import Counter, defaultdict

READ_AXES = ("excavate", "settle", "fuse", "crystallize")


def _q(v):
    """从 quant_readings 取四个轴 + 有效读数。"""
    q = v.get("quant_readings") or {}
    out = {}
    for k, d in q.items():
        if isinstance(d, dict):
            out[k] = d.get("verdict") if "verdict" in d else d.get("value")
    return out


def scan(path):
    d = json.load(open(path, encoding="utf-8"))
    views = d.get("views") or {}
    rows = []
    for e in ("0", "1", "both", "all"):
        v = views.get(e)
        if not v:
            continue
        rows.append({
            "层": e,
            "圈": v.get("rounds_run"),
            "候选": len(v.get("candidates") or []),
            "&": len(v.get("amps") or []),
            "线头": len(v.get("threads") or []),
            "悬置": len([s for s in (v.get("suspensions") or [])
                        if isinstance(s, dict) and s.get("status") in ("active", "stable")]),
            "分歧": (v.get("divergence") if v.get("divergence") is not None
                    else "?"),
            "职责S": (round(float(v["duty_trace"][-1]["S"]), 3)
                    if v.get("duty_trace") and isinstance(v["duty_trace"][-1], dict)
                    and isinstance(v["duty_trace"][-1].get("S"), (int, float)) else "?"),
            "goal": str(v.get("goal_verdict") or "")[:48],
            "读数": _q(v),
            "停止": str(v.get("stop_reason") or "")[:70].replace("\n", " "),
        })
    return d.get("question", "")[:24], d.get("route"), rows


files = sorted(glob.glob("outputs/*.packed.json"), key=os.path.getmtime, reverse=True)
print("=" * 78)
print("真实产物质量诊断（共 %d 个 packed.json）" % len(files))
print("=" * 78)

agg = defaultdict(Counter)
for f in files[:8]:
    q, route, rows = scan(f)
    print("\n■ %s  route=%s" % (q, route))
    for r in rows:
        print("   层 %-4s 圈%-2s 候选%-3s &%-3s 线头%-2s 悬置%-2s 分歧=%-6s S=%-4s"
              % (r["层"], r["圈"], r["候选"], r["&"], r["线头"], r["悬置"],
                 r["分歧"], r["职责S"]))
        print("        goal=%s" % r["goal"])
        print("        读数=%s" % json.dumps(r["读数"], ensure_ascii=False))
        print("        停止=%s" % r["停止"])
        agg["分歧空"][str(r["分歧"])] += 1
        agg["候选0"][r["候选"] == 0] += 1
        agg["职责S0"][str(r["职责S"]) == "0.0"] += 1
        agg["停止"][r["停止"][:24]] += 1

print("\n" + "=" * 78)
print("【跨产物汇总】")
print("  分歧取值分布:", dict(agg["分歧空"]))
print("  候选=0 层数:", dict(agg["候选0"]))
print("  职责S==0.0 层数:", dict(agg["职责S0"]))
print("  停止理由 top:")
for k, c in agg["停止"].most_common(8):
    print("    %-30s %d" % (k, c))
