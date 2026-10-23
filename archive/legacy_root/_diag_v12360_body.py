# -*- coding: utf-8 -*-
"""v1.23.60：用 AST 精确取 `load_resume_snapshot` 的函数体，判「只记不恢复」。

★ 为什么不用字符串切：`s.split("def load_resume_snapshot")[1].split("\\ndef ")[0]`
  会把**后面 7700 行**都当函数体（类里的方法缩进 4 格，`\\ndef ` 根本匹配不到顶层边界）
  ⇒ 判据测的是整份文件，永远判红。**抠函数体一律走 AST。**
"""
import ast
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.60.py"
s = SRC.read_text(encoding="utf-8")
tree = ast.parse(s)


def body_of(name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return ast.get_source_segment(s, node) or ""
    return ""


body = body_of("load_resume_snapshot")
print("load_resume_snapshot 函数体行数：", body.count("\n"))
bad = []
if "layer_progress" in body:
    bad.append("函数体里出现了 layer_progress（续跑读了它 ⇒ 不是'只记不恢复'）")
if "goal_hist" in body:
    bad.append("函数体里出现了 goal_hist")
for b in bad:
    print("  ✗ " + b)
print("判红 %d 项" % len(bad))
sys.exit(1 if bad else 0)
