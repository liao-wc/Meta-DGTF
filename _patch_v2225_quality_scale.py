# -*- coding: utf-8 -*-
"""动态配置质量估算细化：圈数减少按比例折算质量折扣（避免不同低圈档同分）。"""
from pathlib import Path
import py_compile
P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")
old = '''            if factor < 0.7:
                q -= 0.01                  # 低圈成本档的保守质量折扣'''
new = '''            if factor < 1.0:
                q -= (1.0 - factor) * 0.03  # 圈数减少的保守质量折扣（线性）'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK quality scaling")
