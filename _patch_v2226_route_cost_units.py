# -*- coding: utf-8 -*-
"""修正 route 成本模型的 0/1 单位映射与两层重叠系数适用范围。"""
from pathlib import Path
import py_compile
P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")
old = '''    tok = 0.0
    for e in entries:
        unit = _CALIB.get(e)
        if unit:
            tok += float(unit) * float(rmap.get(e, 1) or 1)
    if len(entries) > 1:
        tok *= _CALIB["multi_overlap"]'''
new = '''    tok = 0.0
    for e in entries:
        if e == "0":
            unit = _un0
        elif e == "1":
            unit = _un1
        else:
            unit = _CALIB.get(e)
        if unit:
            tok += float(unit) * float(rmap.get(e, 1) or 1)
    # 两层 0/1 的实测重叠系数只在"纯 0/1 子集"生效；
    # 含 both/all 时单位已按整单实测反解，不再叠系数（避免双重打折）。
    if len(entries) > 1 and not any(e in ("both", "all") for e in entries):
        tok *= _CALIB["multi_overlap"]'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK route model units")
