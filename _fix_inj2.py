# -*- coding: utf-8 -*-
"""[v1.23.3] 修注入器 NEW_CHECK 里两处缺 `+` 的隐式拼接（Python 不允许
「表达式 + 字面量 字面量」相邻拼接跨行成这样）。

★ 不写反斜杠；锚点用不含反斜杠的片段。
"""
from pathlib import Path
import ast

P = Path(__file__).resolve().parent / "_mk_v1233_smoke_checks.py"
s = P.read_text(encoding="utf-8")

A = ("              + \"        return {int(k) + 1: v for k, v in "
     "judged.items()}, \"\n                chr(34) + \"0起+1\" + chr(34))")
B = ("              + \"        return {int(k) + 1: v for k, v in "
     "judged.items()}, \"\n              + chr(34) + \"0起+1\" + chr(34))")
assert s.count(A) == 1, "锚点 A 命中 %d" % s.count(A)
s = s.replace(A, B)

C = ("                                    + \"        return {int(k) + 1: v \"\n"
     "                                      \"for k, v in judged.items()}, \"")
D = ("                                    + \"        return {int(k) + 1: v \"\n"
     "                                    + \"for k, v in judged.items()}, \"")
assert s.count(C) == 1, "锚点 C 命中 %d" % s.count(C)
s = s.replace(C, D)

ast.parse(s)
P.write_text(s, encoding="utf-8")
print("两处缺 + 已补（注入器 parse OK）")
