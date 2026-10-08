#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.7 侦察 b：9 个「只活在 docstring」的片段，逐个查它的判据读的是哪个变量。"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEEDLES = ['## pending_fix', '## 双实现清单',
           'if view is not None and rounds_n > 1:', 'state["total_rounds"] <= 1',
           '← 重新挂账（接 d_001）', '不可判定覆盖轨迹', '新增池接入点',
           '组内极差', '组间差']

print("=== 主文件里那 1 处 __doc__ ===")
lf = (HERE / "元DGTF-V1.23.6.py").read_bytes().decode("utf-8").replace("\r\n", "\n")
for k, ln in enumerate(lf.split("\n"), 1):
    if "__doc__" in ln:
        print("  %5d| %s" % (k, ln.strip()[:120]))

for f in ("smoke_test.py", "_v122_verify.py"):
    print("\n=== %s ===" % f)
    t = (HERE / f).read_bytes().decode("utf-8").replace("\r\n", "\n")
    lines = t.split("\n")
    for nd in NEEDLES:
        for k, ln in enumerate(lines, 1):
            if nd in ln:
                print("  [%s]" % nd[:22])
                for x in range(max(0, k - 3), min(len(lines), k + 2)):
                    print("     %5d| %s" % (x + 1, lines[x].strip()[:112]))
                break
