# -*- coding: utf-8 -*-
"""route 成本模型：rounds 无冒号（如 1/2）表示所有层同圈。"""
from pathlib import Path
import py_compile
P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")
old = '''    rmap = dict(_CALIB["fast_default_rounds"])
    for part in str(rounds or "").split(","):
        part = part.strip()
        if ":" in part:
            k, v = part.rsplit(":", 1)
            try:
                rmap[k.strip()] = int(v)
            except (TypeError, ValueError):
                pass'''
new = '''    rmap = dict(_CALIB["fast_default_rounds"])
    _parts = [p.strip() for p in str(rounds or "").split(",") if p.strip()]
    if _parts and all(":" not in p and p.isdigit() for p in _parts):
        rmap = {e: int(_parts[0]) for e in entries}
    else:
        for part in _parts:
            if ":" in part:
                k, v = part.rsplit(":", 1)
                try:
                    rmap[k.strip()] = int(v)
                except (TypeError, ValueError):
                    pass'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK rounds integer handling")
