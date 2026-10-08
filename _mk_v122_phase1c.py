#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段1c] 补 G1.7 的立据注释。

任务书 Step 1.7：「检查 `_settle_meta` 是否引用 `self.pools["0"]`。
若有，删掉；若无，加注释 `# [v122 P1] 元层只清算对撞张力，不评价修行层`。」
实测（探针 F_settle_meta_ref_p0 = false，基线与 rc1 一致）：**本就不引用**，
所以走「加注释」这一支 —— 本版不许删代码，也不该假装改了什么。

★ 上一次用 heredoc 内联跑同样的替换，锚点 count 报 0，而同一锚点在
  独立 `-c` 里 count = 1 —— heredoc 里的转义被外层吃掉了。
  纪律：改主文件一律走**脚本文件**，不用内联 heredoc。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

OLD = "    def _settle_meta(self) -> dict:\n"
NEW = (
    "    # [v122 P1 G1.7] 元层只清算对撞张力，不评价修行层。\n"
    "    #   实测（_probe_v122_phase1.py 的 F_settle_meta_ref_p0）本函数在\n"
    "    #   基线里就不读 self.pools[\"0\"] —— 「未生合法」这条红线在元层的\n"
    "    #   体现正是：修行层没有产出可以被元层当成欠账。此处立据为证，\n"
    "    #   免得以后有人为了让元层「闭环得更彻底」把修行池接进来。\n"
    + OLD
)


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")
    n = s.count(OLD)
    assert n == 1, f"锚点出现 {n} 次"
    s = s.replace(OLD, NEW, 1)
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))
    assert "G1.7" in out
    print(f"✓ G1.7 注释已加；行数 {len(s.splitlines())}；ast.parse OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
