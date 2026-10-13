# -*- coding: utf-8 -*-
"""[v1.23.27 诊断] check_v1221_p2b 如何弄坏 inspect.getsource。

假设：`_load_anchors()` 内部（或 `main()`）**改了进程 CWD**（chdir），
于是之后再 `inspect.getsource(mod.X)` 时，行缓存按**相对文件名**
解析失败 ⇒ 抛异常。

判据：跑 p2b 前后对比 `os.getcwd()`。
"""
import importlib.util
import inspect
import io
import contextlib
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("DGTF_API_KEY", "sk-smoke-test-key")
os.environ.setdefault("SMOKE_SAVE_DIR", "smoke_outputs")

spec = importlib.util.spec_from_file_location("sm", str(HERE / "smoke_test.py"))
m = importlib.util.module_from_spec(spec)
sys.modules["sm"] = m
spec.loader.exec_module(m)

srcfile = m.mod.__file__
print("mod.__file__ =", srcfile)
print("is abs before =", os.path.isabs(srcfile))
print("cwd before =", os.getcwd())
_bf = len(inspect.getsource(m.mod.save_result))

with contextlib.redirect_stdout(io.StringIO()):
    r = m.check_v1221_p2b()

print("p2b result =", r)
print("cwd after  =", os.getcwd())
print("is abs after =", os.path.isabs(m.mod.__file__))
try:
    _af = len(inspect.getsource(m.mod.save_result))
except Exception as e:
    _af = "EXC:" + type(e).__name__ + ":" + str(e)[:60]
print("getsource len before =", _bf)
print("getsource len after  =", _af)
