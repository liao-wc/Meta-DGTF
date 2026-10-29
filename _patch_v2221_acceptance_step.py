# -*- coding: utf-8 -*-
"""[V2.2.21] final_acceptance 增加 fused_full_chain 步骤（服务型）。"""
from pathlib import Path
import py_compile

P = Path("scripts/final_acceptance.py")
t = P.read_text(encoding="utf-8")
old = '''    # [V2.2.20] 道生支路接入统一模式体系（方案 A）：统一配置/rounds_locked/mode 透传
    ("daosheng_unified", ["scripts/local_model/test_daosheng_unified.py"],
     POLICY_STRICT),'''
new = '''    # [V2.2.21] 融合后全链路真跑：App(auto→daosheng) → 引擎 → 本地模型 → 产物 → 读数
    ("fused_full_chain", ["scripts/local_model/test_fused_full_chain.py"],
     POLICY_SERVICE),
    # [V2.2.20] 道生支路接入统一模式体系（方案 A）：统一配置/rounds_locked/mode 透传
    ("daosheng_unified", ["scripts/local_model/test_daosheng_unified.py"],
     POLICY_STRICT),'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK acceptance fused_full_chain step")
