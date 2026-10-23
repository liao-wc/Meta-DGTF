#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 _mk_v1236_head.py 的 changelog 数字刷成最新实测（含 not-in 锚点那一轮）。"""
from pathlib import Path

p = Path(__file__).resolve().parent / "_mk_v1236_head.py"
t = p.read_text(encoding="utf-8")
REPL = [
    ("（378 块 / 1477 行）", "（378 块 / 1476 行）"),
    ("收集全部 `\"X\" in src` 与 `src.count(\"X\")` 的 X（110 个）",
     "收集全部 `\"X\" in src` / `\"X\" not in src` 与 `src.count(\"X\")` 的 X（156 个）"),
    ("（实保 2 行），而不是整块", "（实保 3 行），而不是整块"),
    ("④ 判据需要的 110 个片段", "④ 判据需要的 156 个片段"),
    ("【规模】23237 → **21760 行**（-1477）；1296038 → **1169527 字节**（-124 KB）。",
     "【规模】23237 → **21761 行**（-1476）；1296038 → **1169589 字节**（-123 KB）。"),
]
for old, new in REPL:
    n = t.count(old)
    assert n == 1, "锚点命中 %d 次：%r" % (n, old[:50])
    t = t.replace(old, new, 1)
p.write_text(t, encoding="utf-8")
print("已刷新 %d 处" % len(REPL))
for bad in ("1477", "21760 ", "1169527", "110 个"):
    assert bad not in t, "残留旧值 %r" % bad
print("无残留旧值")
