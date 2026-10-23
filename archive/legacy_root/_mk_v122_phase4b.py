#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段4b] 补 `_anchor_enters_citation`（tier 门的**唯一**判据）。

为什么要独立成一个函数：`_citation_table` 是纯函数、`_tier_floor` 读配置，
两段逻辑散在两处时「tier=4 到底进不进表」只能靠读代码回答。抽成一个
谓词之后，验收脚本可以直接喂 (anchor, cfg) 两个方向各测一次。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

HELPER = '''
def _anchor_enters_citation(anchor, cfg) -> bool:
    """[v122 P4 G4.2] 该锚点是否够格进引用表（tier ≤ tier_floor）。

    tier 缺省 3；tier 小的更硬。让一条 tier=4 的二手转述去支撑
    →decidable，比「没有证据」更危险 —— 所以这里是**门**不是排序。
    """
    try:
        t = int((anchor or {}).get("tier", 3) or 3)
    except (TypeError, ValueError):
        t = 3
    return t <= _tier_floor(cfg)

'''

A_CITE = '''        _floor_c = _tier_floor(getattr(pool, "_anchor_cfg", None) or {})
        _xi = 0
        for _xa in (getattr(pool, "anchors", None) or []):
            _t = int(_xa.get("tier", 3) or 3)
            if _t > _floor_c:
                continue
            _xi += 1
'''
B_CITE = '''        _acfg = getattr(pool, "_anchor_cfg", None) or {}
        _xi = 0
        for _xa in (getattr(pool, "anchors", None) or []):
            if not _anchor_enters_citation(_xa, _acfg):
                continue
            _xi += 1
'''

REPS = [("cite_use_helper", A_CITE, B_CITE, 1)]


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")
    for name, old, new, want in REPS:
        got = s.count(old)
        assert got == want, f"[{name}] 锚点 {got} 次，期望 {want}"
        s = s.replace(old, new, want)
        print(f"  ✓ {name}")
    anchor = "def _citation_table(view, pool) -> List[tuple]:\n"
    assert s.count(anchor) == 1
    s = s.replace(anchor, HELPER.lstrip("\n") + "\n" + anchor, 1)
    print("  ✓ _anchor_enters_citation")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))
    print(f"✓ 阶段4b 完成；行数 {len(out.splitlines())}；ast.parse OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
