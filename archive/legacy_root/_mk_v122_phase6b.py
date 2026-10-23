#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段6b] 把 `_auto_plan_once` **内联**进 `auto_plan`。

为什么：任务书 Step 7.4 的判据是「函数节点数**不增加**」。阶段 6 原来做成
「搬到模块级新函数 `_auto_plan_once`」→ 函数节点 +2（搬运那股 + 新增的
`_compute_rephrase_streak`）。把搬运那股**内联**掉之后，阶段 6 的净增只剩
任务书**点名要求**新增的那一个（`_compute_rephrase_streak`），
节点差异因此可以逐条解释干净。

内联后 `auto_plan(question, cfg, config_path, llm=...)` 的结构：
    cfg = ...
    if llm is not None:
        <原 _auto_plan 的方法体，缩进 +4>
    <v1.21.62 的两次调用路径>
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")
    lines = s.split("\n")
    tree = ast.parse(s)

    node = None
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == "_auto_plan_once":
            node = n
            break
    assert node is not None, "找不到 _auto_plan_once"
    d0, d1 = node.lineno - 1, node.end_lineno

    # 方法体（跳过 docstring）
    body = node.body
    if body and isinstance(body[0], ast.Expr) and \
            isinstance(getattr(body[0], "value", None), ast.Constant):
        start = body[1].lineno - 1
    else:
        start = body[0].lineno - 1
    moved = ["    " + ln if ln.strip() else ln for ln in lines[start:d1]]
    assert moved, "方法体为空"
    print(f"  · 内联 {len(moved)} 行")

    # 替换 auto_plan 里的转发行
    fwd = "        return _auto_plan_once(question, cfg, llm)\n"
    assert s.count(fwd) == 1, f"转发行 {s.count(fwd)} 处"
    s = s.replace(fwd, "\n".join(moved) + "\n", 1)
    print("  · 转发行已换成正文")

    # 删掉 _auto_plan_once 定义（连同前后空行各留一份）
    lines = s.split("\n")
    tree = ast.parse(s)
    node = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_auto_plan_once")
    d0, d1 = node.lineno - 1, node.end_lineno
    while d0 > 0 and lines[d0 - 1].strip() == "":
        d0 -= 1
    while d1 < len(lines) and lines[d1].strip() == "":
        d1 += 1
    del lines[d0:d1]
    s = "\n".join(lines)
    print("  · _auto_plan_once 定义已移除（内容已内联）")

    assert "_auto_plan_once" not in s, "还有残留引用"
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    t = ast.parse(out.replace("\r\n", "\n"))
    n_def = sum(1 for x in ast.walk(t) if isinstance(x, ast.FunctionDef))
    print(f"✓ 阶段6b 完成；函数节点 {n_def}；行数 {len(out.splitlines())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
