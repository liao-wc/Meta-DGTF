# -*- coding: utf-8 -*-
"""审计：`smoke_test.py` 里定义了、但**没接进 main()** 的判据。

为什么危险：一个 `check_xxx` 定义了却没被 main 调用 ⇒ 它**永远不跑**，
但名字在文件里 ⇒ 看代码的人以为覆盖到了（"假绿"的典型）。

做法：
  · AST 取所有 `def check_*`；
  · 在 main() 的函数体里找 `check_xxx(` 的调用；
  · 差集 = 未接线。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "smoke_test.py"
s = p.read_text(encoding="utf-8")
tree = ast.parse(s)

defined = [n.name for n in tree.body
           if isinstance(n, ast.FunctionDef) and n.name.startswith("check_")]

main_body = ""
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name == "main":
        main_body = ast.get_source_segment(s, n) or ""
        break

unwired = [d for d in defined if ("%s(" % d) not in main_body]
print("定义 %d 条判据，main() 里调用 %d 条"
      % (len(defined), len(defined) - len(unwired)))
if unwired:
    print("未接线（定义了但 main 不调）：")
    for u in unwired:
        print("  · %s" % u)
else:
    print("✓ 无未接线判据")
raise SystemExit(1 if unwired else 0)
