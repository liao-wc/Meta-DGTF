#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 打补丁：版本号两处（docstring 标题 + __version__）。

铁律：read_bytes -> 断言 CRLF==LF -> 转 LF -> 替换（断言各命中 1 次）
-> 转回 CRLF -> 断言 -> write_bytes。绝不 write_text。
"""
from pathlib import Path

SRC = Path(__file__).resolve().parent / "元DGTF-V1.23.26.py"

b = SRC.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "源文件不是纯 CRLF"
assert b.count(b"\r\r\n") == 0, "源文件已含 \\r\\r\\n"
txt = b.decode("utf-8").replace("\r\n", "\n")

# ---- 替换 1：docstring 标题 ----
old1 = "\u5143 DGTF \u00b7 v1.23.25"
new1 = "\u5143 DGTF \u00b7 v1.23.26"
assert txt.count(old1) == 1, f"docstring 标题命中 {txt.count(old1)} 次"
txt = txt.replace(old1, new1)

# ---- 替换 2：__version__ ----
old2 = '__version__ = "1.23.25"'
new2 = '__version__ = "1.23.26"'
assert txt.count(old2) == 1, f"__version__ 命中 {txt.count(old2)} 次"
txt = txt.replace(old2, new2)

# ---- 断言：docstring 标题在前 4000 字符内（_probe_v1232_audit 的 C1 口径） ----
assert new1 in txt[:4000], "docstring 标题不在前 4000 字符内"
assert new2 in txt[:4000], "__version__ 不在前 4000 字符内"

out = txt.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n")
assert out.count(b"\r") == out.count(b"\r\n")
assert out.count(b"\r\r\n") == 0
SRC.write_bytes(out)

print("OK docstring+__version__ -> 1.23.26")
print("bytes =", len(out))
