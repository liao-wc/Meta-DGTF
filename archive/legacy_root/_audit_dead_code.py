# -*- coding: utf-8 -*-
"""审计：主文件里**只被定义、从未被引用**的顶层函数（疑似死代码）。

做法：
  · AST 取模块级 `def` / `class`；
  · 在**主文件 + smoke_test.py + _mut_v12332.py + dgtf_app/*.py** 里数这个名字
    作为 `Name` / `attr` 出现的次数（不含 def 那一行）；
  · 计数 0 ⇒ 没有任何调用点/引用点 ⇒ 疑似死代码。

★ 只是"疑似"：可能是给外部（未来调用方 / 手工 import）留的 API。
  所以这个脚本**只报不改**，要人看一眼再定。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
MAIN = HERE / "元DGTF-V1.23.61.py"
src = MAIN.read_text(encoding="utf-8")
tree = ast.parse(src)

defined = [n.name for n in tree.body
           if isinstance(n, (ast.FunctionDef, ast.ClassDef))]

# 所有引用点（主文件 + 判据 + 变异体 + app）
others = []
for p in [MAIN, HERE / "smoke_test.py", HERE / "_mut_v12332.py",
          HERE / "_v122_verify.py", HERE / "_probe_v1232_audit.py"]:
    if p.is_file():
        others.append(p.read_text(encoding="utf-8"))
for p in sorted((HERE / "dgtf_app").glob("*.py")):
    others.append(p.read_text(encoding="utf-8"))
blob = "\n".join(others)

dead = []
for name in defined:
    # 数"名字出现次数"：全文里出现 >1 次（定义那处 + 至少一处）才算有引用
    c = blob.count(name)
    if c <= 1:
        dead.append((name, c))

print("模块级 def/class：%d 个" % len(defined))
print("疑似死代码（名字全文只出现 1 次 = 只有定义）：%d 个" % len(dead))
for name, c in dead:
    print("  · %-44s 出现 %d 次" % (name, c))
