#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.27 Step1：复制出 v1.23.27 并改版本号（两处）。

★ 不覆盖源文件。★ 保持纯 CRLF（write_bytes，不用 write_text）。
★ 版本号从**文件名推导**（锚不能是会变的东西）。
"""
from pathlib import Path
import ast
import re

HERE = Path(__file__).resolve().parent
OLD = HERE / "元DGTF-V1.23.26.py"
NEW = HERE / "元DGTF-V1.23.27.py"

assert OLD.is_file(), f"源文件不存在：{OLD}"
assert not NEW.exists(), f"目标已存在（不覆盖）：{NEW}"

# 版本号从文件名推导
m_old = re.search(r"V(\d+\.\d+\.\d+)", OLD.name)
m_new = re.search(r"V(\d+\.\d+\.\d+)", NEW.name)
assert m_old and m_new, "文件名里没有版本号"
v_old, v_new = m_old.group(1), m_new.group(1)
print(f"版本：{v_old} -> {v_new}")

b = OLD.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "源文件不是纯 CRLF"
assert b.count(b"\r\r\n") == 0, "源文件含 CRCRLF"
txt = b.decode("utf-8")

# ---- 改动 1：docstring 标题 ----
A1 = f"元 DGTF · v{v_old}"
A1n = f"元 DGTF · v{v_new}"
assert txt.count(A1) == 1, f"docstring 标题命中 {txt.count(A1)} 次"
txt = txt.replace(A1, A1n, 1)

# ---- 改动 2：__version__ ----
A2 = f'__version__ = "{v_old}"'
A2n = f'__version__ = "{v_new}"'
assert txt.count(A2) == 1, f"__version__ 命中 {txt.count(A2)} 次"
txt = txt.replace(A2, A2n, 1)

out = txt.encode("utf-8")
assert out.count(b"\r\r\n") == 0, "写回后出现 CRCRLF"
NEW.write_bytes(out)
ast.parse(out.decode("utf-8"))

# 自检：两处都改了、且没有残留旧版本号作为「标题/版本」
_s = out.decode("utf-8")
assert f"元 DGTF · v{v_new}" in _s
assert f'__version__ = "{v_new}"' in _s
print(f"OK Step1: {NEW.name} 已生成（纯 CRLF）")
print("lines =", out.count(b"\n"), "bytes =", len(out))
