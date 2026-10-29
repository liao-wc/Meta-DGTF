# -*- coding: utf-8 -*-
"""[V2.2.24] final_acceptance 增加 dynamic_opt 步骤（strict，零成本）。"""
from pathlib import Path
import py_compile

P = Path("scripts/final_acceptance.py")
t = P.read_text(encoding="utf-8")
old = '''    # [V2.2.22] 融合"更优"与动态最优配置：能力对等 + 实测矩阵对比 + 引擎 tick
    ("fused_optimal", ["scripts/local_model/test_fused_optimal.py"],
     POLICY_STRICT),'''
new = '''    # [V2.2.24] 全链路动态配置优化 + 动态依赖调整（route 闭包/预算多目标）
    ("dynamic_opt", ["scripts/local_model/test_dynamic_opt.py"],
     POLICY_STRICT),
    # [V2.2.22] 融合"更优"与动态最优配置：能力对等 + 实测矩阵对比 + 引擎 tick
    ("fused_optimal", ["scripts/local_model/test_fused_optimal.py"],
     POLICY_STRICT),'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK acceptance dynamic_opt step")
