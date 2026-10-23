# -*- coding: utf-8 -*-
"""修复 `_mk_v1230_smoke_checks.py` 第 916 行被 heredoc 吃掉的转义（`\n` → `/n`）。

★ 纪律：改脚本/主文件一律走**脚本文件**，不用 heredoc —— heredoc 的多级转义
  会把 `\n` 吃成 `/n`（本项目已踩 6 次）。
"""
from pathlib import Path

P = Path("_mk_v1230_smoke_checks.py")
L = P.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
BAD = [i for i, l in enumerate(L) if "/n    if _sc in src:" in l]
assert len(BAD) == 1, "损坏行命中 %d 次" % len(BAD)
k = BAD[0]
L[k:k + 1] = [
    "for _sc in STALE_CONFIG:",
    "    if _sc in src:",
    '        assert src.count(_sc) == 1, "过期登记行出现 %d 次" % src.count(_sc)',
]
s = "\n".join(L)
import ast
ast.parse(s)
P.write_bytes(s.encode("utf-8"))
print("已修复第 %d 行；文件 %d 行" % (k + 1, len(L)))
print("STALE_CONFIG 已在:", "STALE_CONFIG = tuple(" in s)
print("销账循环已在:", "for _sc in STALE_CONFIG:" in s)
