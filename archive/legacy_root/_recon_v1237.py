#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.7 侦察：把 changelog 从代码里搬出去之前，先量清牵连面。

1) 模块 docstring 的规模与边界；
2) 引擎自己有没有读 `__doc__`；
3) 判据里哪些在读 docstring（而不是「抠掉 docstring 的源码」）；
4) 判据需要的片段里，哪些**只活在 docstring 里** —— 搬走就会消失（冲突集）。
"""
import ast
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.6.py"
LIT = r'(["\'])((?:(?!\1).){2,400}?)\1'

lf = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
L = lf.split("\n")
i = lf.index('"""')
j = lf.index('"""', i + 3)
de = lf[:j].count("\n")
doc = lf[i + 3:j]
body = lf[j + 3:]
print("模块 docstring：第 1 ~ %d 行（含引号行），正文 %d 字符 / %d 行"
      % (de + 1, len(doc), doc.count("\n")))
print("代码正文（docstring 之后）：%d 行" % (len(L) - de - 1))
print("docstring 占全文件 %.1f%%" % (100.0 * (de + 1) / len(L)))

print("\n=== 引擎自己有没有读 __doc__ ===")
print("主文件里出现 `__doc__` 次数 =", lf.count("__doc__"))
print("主文件里出现 `getdoc(` 次数 =", lf.count("getdoc("))

print("\n=== 判据里显式读 docstring 的地方 ===")
for f in ("smoke_test.py", "_v122_verify.py"):
    t = (HERE / f).read_bytes().decode("utf-8").replace("\r\n", "\n")
    for k, ln in enumerate(t.split("\n"), 1):
        if "__doc__" in ln and "replace" not in ln:
            print("  %-16s %5d| %s" % (f, k, ln.strip()[:110]))
    for k, ln in enumerate(t.split("\n"), 1):
        if re.search(r"元 DGTF|元DGTF ·|changelog|收束摘要", ln):
            print("  %-16s %5d| %s" % (f, k, ln.strip()[:110]))

print("\n=== 判据需要的片段里，哪些只活在 docstring 里 ===")
need = set()
for f in ("smoke_test.py", "_v122_verify.py"):
    t = (HERE / f).read_bytes().decode("utf-8").replace("\r\n", "\n")
    for m in re.finditer(LIT + r'\s+(?:not\s+)?in\s+(?:_?src|_?code|_?eng|body|raw|t|txt|s)\b', t):
        need.add(m.group(2))
    for m in re.finditer(r'\.count\(\s*' + LIT + r'\s*\)', t):
        need.add(m.group(2))
only_doc = sorted(n for n in need if n in doc and n not in body)
print("need 片段总数 = %d" % len(need))
print("只在 docstring 里 = %d" % len(only_doc))
for n in only_doc:
    print("   ★ %r" % n[:110])
