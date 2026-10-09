# -*- coding: utf-8 -*-
"""v1.23.8：AST 登记表同步（新增 3 个渲染层纯函数）。

`_v122_verify.py` 的 6.6 是**两向对账**：新增未登记判红、登记却不存在判红。
本版新增 `_dedup_suspensions_for_render` / `_stop_kind_summary` / `_susp_key`，
同步登记（added 93→96，n_symbols_current 380→386，current 指向本版）。
"""
from pathlib import Path

p = Path(__file__).resolve().parent / "_v122_ast_registry.json"
t = p.read_text(encoding="utf-8")

for old, new in (
    (' "added": 93,', ' "added": 96,'),
    (' "current": "元DGTF-V1.23.5.py",', ' "current": "元DGTF-V1.23.8.py",'),
    (' "n_symbols_current": 380,', ' "n_symbols_current": 386,'),
):
    n = t.count(old)
    assert n == 1, f"{old!r} 命中 {n} 次（要求 1）"
    t = t.replace(old, new, 1)

anchor = ' "registry": {\n'
assert t.count(anchor) == 1, "registry 锚点不唯一"
NEW = (
    '  "_dedup_suspensions_for_render": {\n'
    '   "phase": "8",\n'
    '   "reason": "渲染层归一：同 target 的悬置只渲染一条 + 合并条数留痕"\n'
    '  },\n'
    '  "_stop_kind_summary": {\n'
    '   "phase": "8",\n'
    '   "reason": "各层 stop_reason 归纳成一行「自然 n / 被截断 m」，接在产物头部"\n'
    '  },\n'
    '  "_susp_key": {\n'
    '   "phase": "8",\n'
    '   "reason": "悬置归并键：target 首个分句（「；」前），短串退回全长"\n'
    '  },\n'
)
t = t.replace(anchor, anchor + NEW, 1)
p.write_text(t, encoding="utf-8")

import json  # noqa: E402

d = json.loads(p.read_text(encoding="utf-8"))
print("added", d["added"], "| n_symbols_current", d["n_symbols_current"],
      "| registry", len(d["registry"]))
for k in ("_dedup_suspensions_for_render", "_stop_kind_summary", "_susp_key"):
    print(" 登记", k, "->", d["registry"][k]["phase"])
