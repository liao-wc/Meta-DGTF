#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.27：把 smoke_test.py 的 SRC 指到新版。

★ 忘了这一步 = 全套**假绿**（判据还在跑旧版）。每轮第一件事。
"""
from pathlib import Path
import ast
import re

SMOKE = Path(__file__).resolve().parent / "smoke_test.py"
b = SMOKE.read_bytes()
_is_crlf = b.count(b"\r\n") > 0
txt = b.decode("utf-8")
if _is_crlf:
    txt = txt.replace("\r\n", "\n")

assert re.search(r'^SRC = .*$', txt, flags=re.M), "smoke 里没有 SRC 行"
old_line = re.search(r'^SRC = .*$', txt, flags=re.M).group(0)
new_line = 'SRC = HERE / "元DGTF-V1.23.27.py"'
assert old_line != new_line, f"SRC 已经指向新版了：{old_line}"
txt = re.sub(r'^SRC = .*$', new_line, txt, count=1, flags=re.M)
assert new_line in txt, "SRC 替换失败"

out = txt.replace("\n", "\r\n").encode("utf-8") if _is_crlf else txt.encode("utf-8")
SMOKE.write_bytes(out)
ast.parse(out.decode("utf-8"))
print(f"OK SRC: {old_line}  ->  {new_line}")
print("lines =", out.count(b"\n"), "bytes =", len(out))
