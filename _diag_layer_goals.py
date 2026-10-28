# -*- coding: utf-8 -*-
"""四层目标读数普查 v2：解析 views[L].goal_verdict 字符串。

零成本只读。回答：
  · 每层 verdict 是否非空（修行层实测出现过空字符串）
  · 有值时数值分布
"""
from __future__ import annotations

import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAYERS = ["0", "1", "both", "all"]
NAMES = {"0": "修行", "1": "研究", "both": "对撞", "all": "元"}
KEYS = {"0": "excavate", "1": "settle", "both": "fuse", "all": "crystallize"}

packs = sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json"))
               + glob.glob(str(ROOT / "outputs" / "_e2e_local" / "*.packed.json")))
stat = {L: {"ran": 0, "empty": 0, "noval": 0, "vals": []}
        for L in LAYERS}
for f in packs:
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        continue
    views = d.get("views") or {}
    for L in LAYERS:
        v = views.get(L)
        if not (isinstance(v, dict) and v):
            continue
        stat[L]["ran"] += 1
        gv = str(v.get("goal_verdict") or "").strip()
        if not gv:
            stat[L]["empty"] += 1
            continue
        m = re.search(r"=\s*([0-9.]+)", gv)
        if not m:
            stat[L]["noval"] += 1
        else:
            stat[L]["vals"].append(float(m.group(1)))

print("包总数 =", len(packs))
print()
print("%-10s %-6s %-10s %-8s %s" %
      ("层", "跑了", "verdict空", "无数值", "值分布(min/中位/max, n)"))
for L in LAYERS:
    s = stat[L]
    vs = sorted(s["vals"])
    med = vs[len(vs) // 2] if vs else None
    dist = ("%.3f / %.3f / %.3f, n=%d" % (vs[0], med, vs[-1], len(vs))
            if vs else "无")
    print("%-10s %-6d %-10d %-8d %s"
          % (NAMES[L] + "(" + L + ")", s["ran"], s["empty"], s["noval"], dist))
