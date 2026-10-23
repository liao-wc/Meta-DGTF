#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.6 变异体：证明 check_v1236_no_version_tags 有判别力。

做法（skill 7c）：读 smoke_test.py 原文，**只替换 SRC 那一行**指向变异体文件，
再 exec 成独立 module —— 每个变异体一个 module，互不污染。然后让**原样的判据
函数**去跑，必须判红。

  M0 正对照：未改的 v1.23.6                          → 必须判绿
  M1 注入一条全行版次批注 `# [v1.99.9] …`            → 必须判红
  M2 给一个函数 docstring 加前导版次标签 `[v122 P6] `  → 必须判红
  M3 注入一条行尾版次批注（代码 + `# … v1.99.9`）     → 必须判红
  M4 把模块 docstring 里也塞满版次标记（**不该**影响判据）→ 应仍判绿
     —— 这一条是「判据确实抠掉了 docstring」的负对照
"""
import ast
import re
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"
SRC6 = HERE / "元DGTF-V1.23.6.py"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')


def load_judge(target: Path):
    txt = SMOKE.read_bytes().decode("utf-8").replace("\r\n", "\n")
    n = len(SRC_RE.findall(txt))
    assert n == 1, "SRC 行命中 %d 次" % n
    # ★ 替换串里含 Windows 路径的反斜杠 —— 必须用函数形式，否则 re 会报 bad escape \U
    txt = SRC_RE.sub(lambda m: 'SRC = Path(r"%s")' % str(target), txt, count=1)
    mod = types.ModuleType("mut")
    mod.__file__ = str(SMOKE)
    sys.modules["mut"] = mod
    exec(compile(txt, str(SMOKE), "exec"), mod.__dict__)
    return mod


def body_de(t):
    i = t.index('"""')
    j = t.index('"""', i + 3)
    return j, t[:j].count("\n")


def doc_content_start(t, de):
    """第一个函数/类 docstring 的内容起点（绝对偏移）。"""
    tree = ast.parse(t)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                    and node.body[0].value.lineno > de + 1):
                d = node.body[0].value
                lines = t.split("\n")
                start = sum(len(x) + 1 for x in lines[:d.lineno - 1]) + d.col_offset
                assert t[start:start + 3] in ('"""', "'''")
                return start + 3, node.name
    raise SystemExit("没找到函数 docstring")


def main():
    base = SRC6.read_bytes().decode("utf-8").replace("\r\n", "\n")
    tmp = Path(tempfile.mkdtemp(prefix="_v1236mut_"))
    cases = []

    cases.append(("M0 正对照（未改）", base, True))

    j, de = body_de(base)
    _l = base[:j].count("\n")
    lines = base.split("\n")
    m1 = "\n".join(lines[:_l + 2] + ["# [v1.99.9] 变异体：故意留一条全行版次批注"] + lines[_l + 2:])
    cases.append(("M1 全行版次批注", m1, False))

    cs, fname = doc_content_start(base, de)
    m2 = base[:cs] + "[v122 P6] " + base[cs:]
    cases.append(("M2 docstring 前导标签（%s）" % fname, m2, False))

    pat = "\n    return None\n"
    if pat not in base:
        pat = "\n    return {}\n"
    assert pat in base, "找不到插入点"
    m3 = base.replace(pat, "\n    return None  # v1.99.9 变异体：行尾版次批注\n", 1)
    cases.append(("M3 行尾版次批注", m3, False))

    m4 = base.replace("元 DGTF · v1.23.6", "元 DGTF · v1.23.6（[v1.99.9] 塞在 docstring 里）", 1)
    cases.append(("M4 只在模块 docstring 里塞标记", m4, True))

    bad = 0
    for name, text, want_green in cases:
        p = tmp / (name.split()[0] + ".py")
        p.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        ast.parse(text)
        mod = load_judge(p)
        try:
            got = mod.check_v1236_no_version_tags()
        except Exception as e:
            got = "EXC:%s: %s" % (type(e).__name__, e)
        ok = (got is True) if want_green else (got is False)
        print("%-42s 期望 %-5s 实际 %-5s %s"
              % (name, "绿" if want_green else "红", got, "✓" if ok else "★ 不符"))
        if not ok:
            bad += 1
    print("\n变异体结果：%d 个不符（应 0）" % bad)
    print("临时目录：%s" % tmp)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
