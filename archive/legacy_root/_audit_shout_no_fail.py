# -*- coding: utf-8 -*-
"""审计：`smoke_test.py` 里**打了 ✗ 却不会返回 False** 的判据。

为什么危险：门禁按**退出码**判（不是按 ✗ 文本 —— 实测验收日志里就有 ✗ 藏在
数据值里，按文本扫会误杀）。所以一个判据只要"打印 ✗ 但 return True"，
就会被门禁**放过**，而人看日志会以为它红了。

判据：函数体里出现 "✗" 字面量，但**既没有 `return False` 也没有 `ok = False`
/ `bad.append`** 这类失败标记 ⇒ 疑似"只喊不判"。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "smoke_test.py"
s = p.read_text(encoding="utf-8")
tree = ast.parse(s)

susp = []
for n in tree.body:
    if not isinstance(n, ast.FunctionDef) or not n.name.startswith("check_"):
        continue
    body = ast.get_source_segment(s, n) or ""
    if "✗" not in body:
        continue
    has_fail = ("return False" in body) or ("ok = False" in body) \
        or ("bad.append" in body) or ("bad = True" in body)
    if not has_fail:
        susp.append(n.name)

print("含 ✗ 的判据：%d 条" % sum(
    1 for n in tree.body
    if isinstance(n, ast.FunctionDef) and n.name.startswith("check_")
    and "✗" in (ast.get_source_segment(s, n) or "")))
print("疑似只喊不判（有 ✗ 无失败标记）：%d 条" % len(susp))
for x in susp:
    print("  · %s" % x)
