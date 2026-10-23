#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段3c] 修「硬约束 flag 被 quality_flags 重算冲掉」。

**怎么发现的**：不是读代码，是读**真跑的 packed** ——
`runs/v122/p2_consistency_1/packed.json` 里：

```
views.1.errors        = ['decision 模式行动清单不足（0 < 3），需补 A1~A3',
                         'decision 模式未交代「不做什么」，需补该清单']
views.1.quality_flags = []
```

errors 留下了、quality_flags 空了 —— 说明 flag 被**后写覆盖**。

根因：`_finalize_layer_common` 里我的硬约束块写在 16012~16026 行，
而 **19 行后**（16072）有：

```python
view.quality_flags = _keep_selfcheck_flags(
    view, _dg._quality_check(view, self.pools[entry], r_actual, ...))
```

`_quality_check` 是**整体重算**，而 `_keep_selfcheck_flags` 只保住
自省派生的那两个线索（`_SELFCHECK_FLAGS`）。本项目早有过同类事故
（P2-8 的注释就写着「合并后重算 quality_flags 时必须保住」），
这次是第三个家族：**硬约束 flag**。

修法：把硬约束 flag 也加进「重算时必须保住」的集合（加性，不动原集合）。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

OLD = '''_SELFCHECK_FLAGS = ("unsaid_overused", "candidates_backfilled")


def _keep_selfcheck_flags(view, new_flags):
    """重算 quality_flags 后，把自省派生的线索补回去（不重复）。"""
    kept = [f for f in (getattr(view, "quality_flags", None) or [])
            if any(k in str(f) for k in _SELFCHECK_FLAGS)]
'''

NEW = '''_SELFCHECK_FLAGS = ("unsaid_overused", "candidates_backfilled")

# [v122 P3 G3.5] 硬约束 flag 也要在重算时保住。
#   ★ 实测踩过：决策模式判定「行动清单不足 / 没交代不做什么」后
#     `view.quality_flags.append(...)`，19 行之后那句
#     `_keep_selfcheck_flags(view, _dg._quality_check(...))` 把整个列表
#     **整体重算**，两条 flag 当场消失 —— errors 里还在、quality_flags 里没了。
#     留下的症状很隐蔽：产物照常渲染，只是那条线索活不到 md。
_V122_HARD_FLAGS = ("action_incomplete", "not_do_missing")

# 重算 quality_flags 时**必须保住**的全部家族。
_PRESERVED_FLAGS = _SELFCHECK_FLAGS + _V122_HARD_FLAGS


def _keep_selfcheck_flags(view, new_flags):
    """重算 quality_flags 后，把「不该被重算冲掉」的线索补回去（不重复）。

    保两类：自省派生线索（`_SELFCHECK_FLAGS`）+ 硬约束 flag
    （`_V122_HARD_FLAGS`，v122 阶段 3 加）。
    """
    kept = [f for f in (getattr(view, "quality_flags", None) or [])
            if any(k in str(f) for k in _PRESERVED_FLAGS)]
'''


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")
    n = s.count(OLD)
    assert n == 1, f"锚点 {n} 次"
    s = s.replace(OLD, NEW, 1)
    print("  ✓ _PRESERVED_FLAGS 已加")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))
    print(f"✓ 阶段3c 完成；行数 {len(out.splitlines())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
