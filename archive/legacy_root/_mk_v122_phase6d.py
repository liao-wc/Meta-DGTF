#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段6d] 把两个 difflib 记账噪声清掉，让纯删除行数真正归零。

两个都不是「删机制」，是记账噪声：
  ① `_run_layer` 里 `_mi_from_view = getattr(...)` 那一行被我挪到了注释**后面**
     → difflib 把它读成「原位置删了一行、新位置加了一行」。
     把它挪回原位，只改真正要改的 `_rephrase_streak = ...` 那一行。
  ② 模块级 `def auto_plan(` 之前的空行从 2 个变成了 1 个（阶段6b 删
     `_auto_plan_once` 时连空行一起吃掉）→ 记为「删了两个空行」。
     补回 2 个。

★ 留着这 2 行「删除」，判据就得永远带一条例外说明；清掉它们，
  `count_del_lines = 0` 就是**字面成立**的，而不是「解释后成立」。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

OLD_A = '''            # [v1.21.56 P0-1] 两条来源分开成文，不再合成一个数再猜来源。
            #   · _rephrase_streak：真·复述（代码直检 + 自省判定）
            #   · carry_streak   ：自省点名的同一批问题连续没消化
            # [v122 P6 G6.3] 收口：串行/并行两侧共用唯一实现。
            _mi_from_view = getattr(view, "_meta_idle_streak", 0)
            _rephrase_streak = _compute_rephrase_streak(view, {
                "meta_idle_streak": meta_idle_streak})
'''
NEW_A = '''            _mi_from_view = getattr(view, "_meta_idle_streak", 0)
            # [v1.21.56 P0-1] 两条来源分开成文，不再合成一个数再猜来源。
            #   · _rephrase_streak：真·复述（代码直检 + 自省判定）
            #   · carry_streak   ：自省点名的同一批问题连续没消化
            # [v122 P6 G6.3] 收口：串行/并行两侧共用唯一实现（唯一 def）。
            _rephrase_streak = _compute_rephrase_streak(view, {
                "meta_idle_streak": meta_idle_streak})
'''


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")

    n = s.count(OLD_A)
    assert n == 1, f"[A] 锚点 {n} 次"
    s = s.replace(OLD_A, NEW_A, 1)
    print("  ✓ ① _mi_from_view 挪回原位")

    lines = s.split("\n")
    tgt = "def auto_plan(question: str, config: Optional[dict] = None,"
    idx = [i for i, l in enumerate(lines) if l == tgt]
    assert len(idx) == 1, f"auto_plan 定义 {len(idx)} 处"
    i = idx[0]
    k = i
    while k > 0 and lines[k - 1].strip() == "":
        k -= 1
    n_blank = i - k
    assert n_blank in (0, 1), f"现有空行 {n_blank} 个，预期 0 或 1"
    lines[k:i] = ["", ""]
    s = "\n".join(lines)
    print(f"  ✓ ② def auto_plan 前空行 {n_blank} → 2")

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))

    import difflib
    la = Path(HERE / "_baseline_v12177.py").read_text(
        encoding="utf-8").replace("\r\n", "\n").split("\n")
    lb = out.replace("\r\n", "\n").split("\n")
    sm = difflib.SequenceMatcher(None, la, lb)
    dels = [(t, i1 + 1, i2) for t, i1, i2, _j1, _j2 in sm.get_opcodes()
            if t == "delete"]
    print(f"✓ 阶段6d 完成；剩余纯删除块 {len(dels)} 个 {dels}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
