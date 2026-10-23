# -*- coding: utf-8 -*-
"""v1.23.9 修（第二轮）：注释块第二行里还有 `v1.23.8`。

★ 教训：判据查的是「**块内任一行**出现版本号」，不是只看块首 ——
  第一轮只清了块首的 `★ v1.23.9：`，第二行里的「回到 v1.23.8 及以前」
  仍被判为版次批注（行号 14154）。
"""
from pathlib import Path

p = Path(__file__).resolve().parent / "元DGTF-V1.23.9.py"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

PAIRS = [
    ("#   词表只增不减 —— 加词只会让更多题走 decision 模板（即回到 v1.23.8 及",
     "#   词表只增不减 —— 加词只会让更多题走 decision 模板（即回到旧版行为），"),
    ("#   以前的行为），不会静默把本来走 decision 的题踢出去。",
     "#   不会静默把本来走 decision 的题踢出去。"),
]
for old, new in PAIRS:
    n = s.count(old)
    assert n == 1, f"{old[:24]!r} 命中 {n} 次（要求 1）"
    s = s.replace(old, new, 1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
p.write_bytes(out)

import ast  # noqa: E402
chk = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
ast.parse(chk)
print("残留版本标记行：",
      [(i + 1, l.strip()[:40]) for i, l in enumerate(chk.split("\n"))
       if "v1.23." in l])
print("ast OK |", len(chk.split("\n")) - 1, "行")
