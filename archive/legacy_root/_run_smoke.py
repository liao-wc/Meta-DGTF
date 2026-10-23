# -*- coding: utf-8 -*-
"""通用冒烟 runner：跑全套 + 落盘（本机 `>` 重定向不可靠，用 write_bytes）。

日志名从 `smoke_test.py` 的 SRC 行推导：`_smoke_v<版本号>.log`
（★ 不再写死 —— 每版换名忘改就会把上一版的日志覆盖掉）。
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"

_src = SK.read_text(encoding="utf-8")
_m = re.findall(r"元DGTF-V(1\.23\.\d+)\.py", _src)
assert _m, "从 smoke_test.py 里找不到 SRC 的版本号"
VER = _m[0]
LOG = HERE / ("_smoke_v%s.log" % VER.replace(".", ""))

r = subprocess.run([sys.executable, str(SK)], capture_output=True, cwd=str(HERE))
out = r.stdout + b"\n=== STDERR ===\n" + r.stderr
LOG.write_bytes(out)
txt = out.decode("utf-8", "replace")
print("SRC 版本 =", VER, "| 日志 =", LOG.name)
print("EXIT =", r.returncode)
print("✗ =", txt.count("\u2717"), " ✓ =", txt.count("\u2713"))
for line in txt.split("\n"):
    if "\u2717" in line:
        print("FAIL:", line.strip())
