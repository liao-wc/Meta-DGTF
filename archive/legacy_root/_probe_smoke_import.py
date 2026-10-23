# -*- coding: utf-8 -*-
"""[v1.23.27 临时] 只探测：能否 import smoke_test 且不触发 __main__ 跑全套。

目的：验证 `smoke_test.py` 是否有 `if __name__ == "__main__"` 守卫。
若有 → 后续 check_* 判据可以「起服务 + import smoke」单跑，省掉 65 分钟。
"""
import importlib.util
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("DGTF_API_KEY", "sk-smoke-test-key")

t0 = time.time()
spec = importlib.util.spec_from_file_location("smoke_probe_mod", str(HERE / "smoke_test.py"))
m = importlib.util.module_from_spec(spec)
sys.modules["smoke_probe_mod"] = m
spec.loader.exec_module(m)
dt = time.time() - t0

print("IMPORT_OK dt=%.2fs" % dt)
print("HAS_MAIN_GUARD =", "__main__" in (HERE / "smoke_test.py").read_text(encoding="utf-8"))
names = [n for n in dir(m) if n.startswith("check_")]
print("N_CHECK =", len(names))
print("SAMPLE =", names[:5])
