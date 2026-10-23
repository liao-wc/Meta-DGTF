#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段5b] 定点修复被「子串锚点」插坏的头部块缩进。

事故：`_mk_v122_phase5.py` 用 8 空格 + 注释当锚点，而目标注释实际是
**12 空格** —— 8 空格是 12 空格的**子串**，于是替换发生在行中间，
留下 4 个空格的残渣，并把后面的 8 空格行塞进了 12 空格的作用域里 →
`IndentationError: unexpected indent`。

教训（补进纪律）：锚点带前导空格时，**必须**用「整行相等」或
行首 + 换行边界，否则空格数不同也会命中。

修法：把那 6 行整块换回 12 空格版本。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

GOOD = [
    "            # [v122 阶段5 G5.5] 机制审计：pending_fix / 双实现各几项。",
    "            #   数字由登记常量给，冒烟负责核它和源码注释条数是否一致。",
    '            f.write(f"**机制审计**：pending_fix {_AUDIT122_PENDING_FIX} 项，"',
    '                    f"双实现 {_AUDIT122_DUAL_IMPL} 项"',
    '                    f"（详见 docs/机制审计-v122.md）\\n\\n")',
    "            # [v122 阶段2 G2.5/G2.6] 三态多票 + **冻结**",
]

BAD_SIGS = [
    "# [v122 阶段5 G5.5] 机制审计：pending_fix / 双实现各几项。",
    "#   数字由登记常量给，冒烟负责核它和源码注释条数是否一致。",
    "+**机制审计**：pending_fix",
    "双实现 {_AUDIT122_DUAL_IMPL} 项",
    "docs/机制审计-v122.md",
    "# [v122 阶段2 G2.5/G2.6] 三态多票 + **冻结**",
]


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    lines = s.replace("\r\n", "\n").split("\n")

    # 定位坏块：从「含 阶段5 G5.5 的那一行」到「含 阶段2 G2.5/G2.6 的那一行」
    i0 = [i for i, l in enumerate(lines) if "阶段5 G5.5" in l]
    i1 = [i for i, l in enumerate(lines)
          if "阶段2 G2.5/G2.6" in l and "三态多票" in l]
    assert len(i0) == 1, f"起点 {len(i0)} 处"
    assert len(i1) == 1, f"终点 {len(i1)} 处"
    a, z = i0[0], i1[0]
    assert z - a == 5, f"坏块行数 {z - a + 1}，期望 6"
    got = lines[a:z + 1]
    assert any("pending_fix" in c for c in got), "块里没有 pending_fix？起点不对"
    assert any("docs/机制审计-v122.md" in c for c in got), "块里没有文档路径"
    # 坏块的指纹：有前导 8 空格的行（正确版本全是 12 空格）
    assert any(len(c) - len(c.lstrip(" ")) == 8 for c in got), \
        "没看到 8 空格行 —— 这不是被插坏的那块"
    print(f"  坏块 {a + 1}..{z + 1} 已定位（含 8 空格行）")
    for chunk in got:
        print("   -", repr(chunk[:72]))
    lines[a:z + 1] = GOOD
    out = "\n".join(lines)
    ast.parse(out)
    out = out.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    print("✓ 阶段5b 修复完成；ast.parse OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
