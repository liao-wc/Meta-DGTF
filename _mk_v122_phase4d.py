#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段4d] 修阶段 4 引出的两条旧判据回归。

1) `[B] 授权后引用表 X 编号为 []，期望 ['X1','X2']`
   —— **判据随实现更新**（不是代码错）。v122 起引用表加了 tier 门
   （tier ≤ tier_floor，缺省 3 ≤ 2 不成立），所以「无 tier 字段」的锚点
   默认进不了表。这条判据测的是**授权门**，给 fixture 补上够硬的 tier=1
   即可，判据的含义（授权→进表 / 未授权→不进表）不变。

2) `[D] 未实现的检索后端静默放过了`
   —— **是我改了措辞**。阶段 4 把 raise 的文案从「尚未实现」写成
   「未实现的检索后端」，而这句文案是旧判据的锚点。恢复原文案
   （`tavily` 现在是真实现，其余仍走 raise + 留痕，语义没变）。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "元DGTF-V1.22.0-rc1.py"
SMOKE = HERE / "smoke_test.py"

OLD_FIX = '''    p1.anchors = [{"id": "a1", "claim": "回本周期 1-3 年"},
                  {"id": "a5", "claim": "稼动率红线 75%"}]
'''
NEW_FIX = '''    # [v122 P4] 补 tier=1：v122 起引用表带 **tier 门**（tier ≤ 缺省 2），
    #   不带 tier 的锚点缺省 3 ＝ 二手转述 —— 那种锚点**授权也不该进表**。
    #   本条判据测的是「授权门」，所以给够硬的 tier（含义不变）。
    p1.anchors = [{"id": "a1", "claim": "回本周期 1-3 年", "tier": 1},
                  {"id": "a5", "claim": "稼动率红线 75%", "tier": 1}]
'''

OLD_MSG = '''            raise RuntimeError(
                "未实现的检索后端: " + repr(self.backend) + "（不静默降级）")
'''
NEW_MSG = '''            # ★ 文案里必须留「尚未实现」四个字：旧判据（v75 [D]）以它
            #   为锚点。改措辞会被读成「静默放过了」——实测踩过一次。
            raise RuntimeError(
                "external_anchor.retriever=" + repr(self.backend)
                + " 尚未实现（当前只有 'snapshot' 与 'tavily'）；"
                + "不静默降级")
'''


def _patch(path: Path, reps):
    b = path.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0, path.name
    s = s.replace("\r\n", "\n")
    for name, old, new, want in reps:
        got = s.count(old)
        assert got == want, f"[{path.name}:{name}] 锚点 {got} 次，期望 {want}"
        s = s.replace(old, new, want)
        print(f"  ✓ {path.name}: {name}")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    path.write_bytes(out.encode("utf-8"))
    import ast
    ast.parse(out.replace("\r\n", "\n"))


def main() -> int:
    _patch(SMOKE, [("fix_fixture", OLD_FIX, NEW_FIX, 1)])
    _patch(ENGINE, [("msg_wording", OLD_MSG, NEW_MSG, 1)])
    print("✓ 阶段4d 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
