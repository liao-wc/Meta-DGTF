# -*- coding: utf-8 -*-
"""fast 档质量下限对齐（fast 实测 0.93，不应沿用项目 0.95 导致假 fallback）。"""
from pathlib import Path
import py_compile
P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")
old = '''    floor = float(opts.get("min_quality") or 0.0) or (
        _DYN_TIER_FLOOR["project"] if (project_related or kind == "project") else
        (_DYN_TIER_FLOOR["quality_first"] if quality_first
         else _DYN_TIER_FLOOR["default"]))'''
new = '''    floor = float(opts.get("min_quality") or 0.0) or (
        _DYN_TIER_FLOOR["project"] if (project_related or kind == "project") else
        (_DYN_TIER_FLOOR["quality_first"] if quality_first
         else _DYN_TIER_FLOOR["default"]))
    # ★ fast 档的实测质量上限≈0.93：降级到 fast 后若仍卡 0.95 会假 fallback，
    #   把下限对齐到 fast 可满足档（0.90）；quality 档仍用项目/quality_first 0.95。
    if tier == "fast":
        floor = min(floor, _DYN_TIER_FLOOR["default"])'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK fast floor")
