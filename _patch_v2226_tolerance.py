# -*- coding: utf-8 -*-
"""动态配置可行域容差：估算误差 ±10%，避免预算线附近误杀更优档。"""
from pathlib import Path
import py_compile
P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")
old = '''            feasible = True
            if isinstance(balance, (int, float)):
                feasible = cost_eff <= max(0.01, float(balance) * reserve)'''
new = '''            feasible = True
            if isinstance(balance, (int, float)):
                # 估算误差容差 ±10%：预算线附近优先保留质量更高的可行档
                feasible = cost_eff <= max(0.01, float(balance) * reserve) * 1.10'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK feasibility tolerance")
