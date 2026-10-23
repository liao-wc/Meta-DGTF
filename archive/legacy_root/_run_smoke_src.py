#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 harness 复用方式跑 smoke_test：只读源码，正则换 SRC 一行后 exec。
不改磁盘上的 smoke_test.py（避免分叉）。用法：python _run_smoke_src.py <src.py>"""
import re, sys, runpy
from pathlib import Path
HERE = Path(__file__).resolve().parent
SRC_FILE = sys.argv[1]
st = (HERE / "smoke_test.py").read_text(encoding="utf-8").replace("\r\n", "\n")
pat = re.compile(r'SRC = HERE / "[^"]+\.py"')
assert len(pat.findall(st)) == 1, "SRC 行不唯一"
st = pat.sub(lambda _m: 'SRC = HERE / "%s"' % SRC_FILE, st, count=1)
g = {"__name__": "__main__", "__file__": str(HERE / "smoke_test.py")}
sys.exit(exec(compile(st, "smoke_test.py", "exec"), g) or 0)
