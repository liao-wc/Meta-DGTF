# -*- coding: utf-8 -*-
"""动态配置：按 tier 枚举圈数档（quality 保持 auto/quality 档；fast 才做低圈多目标）。"""
from pathlib import Path
import py_compile
P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")
old = '''    # ★ [V2.2.25] 候选 rounds：全档枚举，由成本约束 + 质量排序共同选择
    #   （不再按预算层级硬编码单档；预算只决定"哪些候选可行"）。
    _rounds_opts: list[str] = []
    for _rc in (ds.get("rounds_fast"), cfg.get("rounds_economy"),
                cfg.get("rounds_critical"),
                ((ds.get("rounds_quality") or "0:3,1:3,both:4,all:4")
                 if (tier == "quality" and quality_first) else None),
                (str(rounds) if str(rounds or "") not in ("", "auto") else None)):
        if _rc and str(_rc) not in _rounds_opts:
            _rounds_opts.append(str(_rc))
    if not _rounds_opts:
        _rounds_opts = ["auto"]'''
new = '''    # ★ [V2.2.25] 候选 rounds：按 tier 枚举（quality 保持 auto/quality 档；
    #   fast 才做 fast/economy/critical 多目标，由成本约束 + 质量排序选择）。
    _rounds_opts: list[str] = []
    if tier == "fast":
        _pool = (ds.get("rounds_fast"), cfg.get("rounds_economy"),
                 cfg.get("rounds_critical"))
    else:
        _pool = ((str(rounds) if str(rounds or "") not in ("", "auto")
                  else "auto"),
                 ((ds.get("rounds_quality") or "0:3,1:3,both:4,all:4")
                  if quality_first else None))
    for _rc in _pool:
        if _rc and str(_rc) not in _rounds_opts:
            _rounds_opts.append(str(_rc))
    if not _rounds_opts:
        _rounds_opts = ["auto"]'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK tier-based rounds")
