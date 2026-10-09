# -*- coding: utf-8 -*-
"""v1.23.9 修：把新加注释 / docstring 里的版次标记去掉。

★ v1.23.6 的红线是「代码正文不留版次批注」；本版补丁手写注释时又带了
  `★ v1.23.9：`，被 `[v1236]` 判据当场抓到（行号 14153/14154）。
  变更记录归 `CHANGELOG.md`，代码里不留版本号。
"""
from pathlib import Path

p = Path(__file__).resolve().parent / "元DGTF-V1.23.9.py"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

PAIRS = [
    ("# ★ v1.23.9：decision 模板的适用前提是「题面里有决策语境」。",
     "# decision 模板的适用前提是「题面里有决策语境」。"),
    ("    ★ v1.23.9 起 `auto` 还要看题面：无决策语境的单点事实询问",
     "    ★ `auto` 还要看题面：无决策语境的单点事实询问"),
]
for old, new in PAIRS:
    n = s.count(old)
    assert n == 1, f"{old[:30]!r} 命中 {n} 次（要求 1）"
    s = s.replace(old, new, 1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
p.write_bytes(out)

import re  # noqa: E402
chk = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
hits = [i + 1 for i, ln in enumerate(chk.split("\n")) if "v1.23.9" in ln]
print("残留 v1.23.9 标记的行号：", hits or "无")
import ast  # noqa: E402
ast.parse(chk)
print("ast OK |", len(chk.split(chr(10))) - 1, "行")
