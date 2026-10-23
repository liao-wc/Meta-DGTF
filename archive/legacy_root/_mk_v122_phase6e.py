#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段6e] 薄壳 docstring 补上「与模块级 auto_plan 的关系」。

v1.21.71 F8 的判据要求 `_auto_plan` 的 docstring 同时提到 `auto_plan` 与
`plan_resources` —— 它拦的是「两份实现的漂移没人标注」。收口后这条判据
不但不过时，反而更该留：它保证读者一眼能看出「这里只是壳，实现在哪」。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

OLD = '''    def _auto_plan(self, question: str) -> dict:
        """[v122 P6 G6.2] 收口：唯一实现搬到模块级 `auto_plan`。

        本方法现在只是一层兼容壳 —— 签名与返回值形状都不变，`run()` 与
        外部脚本都不用改。传 `llm` 让模块级走**单调用**那条路径，于是
        行为与 v1.21.77 逐字相同（对照见 `_probe_v122_phase6.py`）。
        """
        return auto_plan(question, self.config, llm=self.llm)
'''

NEW = '''    def _auto_plan(self, question: str) -> dict:
        """[v122 P6 G6.2] 收口：唯一实现在模块级 `auto_plan`，本方法退薄壳。

        本方法不再自己实现任何调度逻辑 —— 签名与返回值形状都不变，
        `run()` 与外部脚本都不用改。

        ★ 与模块级 `auto_plan` 的关系（v1.21.71 F8 起要求写清，收口后
          更要写清）：
            · 传 `llm` → 模块级走**单调用**路径（一次定 mode + rounds），
              也就是原 `_auto_plan` 的正文，行为与 v1.21.77 逐字相同；
              对照见 `_probe_v122_phase6.py` 的 before/after 快照。
            · 不传 `llm` → 模块级走 `plan_orientation` + `plan_resources`
              两段（v1.21.62 起的对外 API 路径，仅外部脚本使用）。
        """
        return auto_plan(question, self.config, llm=self.llm)
'''

REPS = [("shell_doc", OLD, NEW, 1)]


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")
    for name, old, new, want in REPS:
        got = s.count(old)
        assert got == want, f"[{name}] 锚点 {got} 次"
        s = s.replace(old, new, want)
        print(f"  ✓ {name}")
    assert "plan_resources" in s
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))
    print(f"✓ 阶段6e 完成；行数 {len(out.splitlines())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
