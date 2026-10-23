# -*- coding: utf-8 -*-
"""跑全套冒烟并把 stdout+stderr 一次性落盘（本机 `>` 重定向不可靠）。"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
r = subprocess.run([sys.executable, str(HERE / "smoke_test.py")],
                   capture_output=True, cwd=str(HERE))
out = r.stdout + b"\n=== STDERR ===\n" + r.stderr
(HERE / "_smoke_v1238.log").write_bytes(out)
txt = out.decode("utf-8", "replace")
print("EXIT =", r.returncode)
print("✗ =", txt.count("\u2717"), " ✓ =", txt.count("\u2713"))
for line in txt.split("\n"):
    if "\u2717" in line:
        print("FAIL:", line.strip())
