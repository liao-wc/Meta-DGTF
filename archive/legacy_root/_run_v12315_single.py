# -*- coding: utf-8 -*-
"""单独驱动 check_v12315，验证「冻结快照」修复是否消掉假红。"""
import os
import sys
import importlib.util

os.environ.setdefault("DGTF_API_KEY", "sk-probe")

spec = importlib.util.spec_from_file_location("smk", "smoke_test.py")
smk = importlib.util.module_from_spec(spec)
sys.modules["smk"] = smk
spec.loader.exec_module(smk)          # 顶层 L31 已经把被测主文件加载成 smk.mod

print("mod =", getattr(smk, "mod", None))
print("--- 驱动 check_v12315 ---")
ok = smk.check_v12315_history_calibration()
print("RESULT =", ok)
