# -*- coding: utf-8 -*-
"""[V2.2.19] final_acceptance 增加 auto_mode_local 步骤（服务型）。"""
from pathlib import Path
import py_compile

P = Path("scripts/final_acceptance.py")
t = P.read_text(encoding="utf-8")
old = '''    # [V2.2.18] App selftest 自动门（自起临时 server；起不来 exit=2 = 没跑）
    ("app_selftest", ["scripts/app_selftest_gate.py"], POLICY_SERVICE),'''
new = '''    # [V2.2.18] App selftest 自动门（自起临时 server；起不来 exit=2 = 没跑）
    ("app_selftest", ["scripts/app_selftest_gate.py"], POLICY_SERVICE),
    # [V2.2.19] 自动模式真跑：--mode auto 由题面选 fast / 专属配置落参 / 最优性可审计
    ("auto_mode_local", ["scripts/local_model/test_auto_mode_local.py"],
     POLICY_SERVICE),'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK final_acceptance auto_mode_local step")
