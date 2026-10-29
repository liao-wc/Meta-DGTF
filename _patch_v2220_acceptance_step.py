# -*- coding: utf-8 -*-
"""[V2.2.20] final_acceptance 增加 daosheng_unified 步骤（strict，零 GPU/零 API）。"""
from pathlib import Path
import py_compile

P = Path("scripts/final_acceptance.py")
t = P.read_text(encoding="utf-8")
old = '''    # [V2.2.19] 自动模式真跑：--mode auto 由题面选 fast / 专属配置落参 / 最优性可审计
    ("auto_mode_local", ["scripts/local_model/test_auto_mode_local.py"],
     POLICY_SERVICE),'''
new = '''    # [V2.2.20] 道生支路接入统一模式体系（方案 A）：统一配置/rounds_locked/mode 透传
    ("daosheng_unified", ["scripts/local_model/test_daosheng_unified.py"],
     POLICY_STRICT),
    # [V2.2.19] 自动模式真跑：--mode auto 由题面选 fast / 专属配置落参 / 最优性可审计
    ("auto_mode_local", ["scripts/local_model/test_auto_mode_local.py"],
     POLICY_SERVICE),'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK acceptance daosheng_unified step")
