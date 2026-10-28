# -*- coding: utf-8 -*-
"""审计：引擎里 self.llm.call(...) 哪些没传 stage=（成本归因盲区）。

只读分析，不改任何文件。输出按行号排序的清单 + 汇总。
"""
from __future__ import annotations
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
#: ★ 版本从**文件名**推导，不钉死版本号：钉死了下次升版就测的是旧文件，
#:   而「全绿」会让人误以为新版也没盲区（实测 V2.2.8 又冒出新的未打标调用点）。
#:   可用 argv[1] 显式指定版本做对照。
_ENG = ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
if len(sys.argv) > 1:
    TARGET = _ENG / sys.argv[1]
else:
    _cands = sorted(_ENG.glob("Meta-DGTF-V*.py"))
    TARGET = _cands[-1] if _cands else (_ENG / "Meta-DGTF-V2.2.4.py")


def caller_name(stack, node):
    """返回最内层包含该节点的函数名（限定名）。"""
    best = "<module>"
    for n in stack:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            best = n.name
    return best


def main() -> int:
    src = TARGET.read_text(encoding="utf-8")
    tree = ast.parse(src)
    missing = []
    total = 0

    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def visit_FunctionDef(self, node):
            self.stack.append(node)
            self.generic_visit(node)
            self.stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            nonlocal total
            f = node.func
            # 匹配 *.call(...) 形式
            if isinstance(f, ast.Attribute) and f.attr == "call":
                total += 1
                kw = {k.arg for k in node.keywords if k.arg}
                has_stage = "stage" in kw or len(node.args) >= 5
                if not has_stage:
                    base = ""
                    if isinstance(f.value, ast.Attribute):
                        base = f.value.attr
                    elif isinstance(f.value, ast.Name):
                        base = f.value.id
                    # 只关心自省/判定类调用（llm 实例）
                    if base in ("llm", "client", "LLM"):
                        missing.append((node.lineno, caller_name(self.stack, node), base))
            self.generic_visit(node)

    V().visit(tree)
    print("total *.call( ) sites:", total)
    print("missing stage:", len(missing))
    for ln, fn, base in missing:
        print(f"  L{ln:6d}  in {fn:44s}  base={base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
