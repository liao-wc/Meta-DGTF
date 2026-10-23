# -*- coding: utf-8 -*-
"""自检：作废脚本 `_mk_v12340_mut_fixanchor.py` 的护栏对 import 也生效。"""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("fx", "_mk_v12340_mut_fixanchor.py")
m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
    print("[!!] import 未被拦（危险）")
    sys.exit(1)
except SystemExit as e:
    print("[ok] import 被拦：", e)
    sys.exit(0)
