#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.6 侦察：把「代码正文里的版次信息」按口径分类量清。

三类口径完全不同：
  A 全行批注（整行都是注释、且含版本号）      —— 要删
  B 行尾批注（代码 + 同行 `# ... v1.2x`）     —— 要删（只删注释部分）
  C 字符串里的版本号（函数 docstring / 文案） —— **不动**（是数据不是注释）
"""
import ast
import re
from pathlib import Path

SRC = Path("元DGTF-V1.23.5.py")
lf = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
L = lf.split("\n")
i = lf.index('"""')
j = lf.index('"""', i + 3)
doc_end = lf[:j].count("\n")          # 模块 docstring 结束所在的行索引
print("模块 docstring: 第 1 ~ %d 行" % (doc_end + 1))

VER = re.compile(r"v1\.2\d")

# ---- A 全行批注 ----
full = [k for k in range(doc_end + 1, len(L))
        if L[k].lstrip().startswith("#") and VER.search(L[k])]
print("\n[A] 全行批注（含版本号） = %d 行" % len(full))

# ---- B 行尾批注 ----
trail = [k for k in range(doc_end + 1, len(L))
         if not L[k].lstrip().startswith("#") and "#" in L[k]
         and VER.search(L[k].split("#", 1)[1])]
print("[B] 行尾批注 = %d 行" % len(trail))
for k in trail[:12]:
    print("     %5d| %s" % (k + 1, L[k].strip()[:96]))

# ---- C 字符串 ----
tree = ast.parse(lf)
strs = []
for node in ast.walk(tree):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        ln = getattr(node, "lineno", 0)
        if ln > doc_end + 1 and VER.search(node.value):
            strs.append((ln, node.value))
print("[C] 字符串里含版本号（不动） = %d 处" % len(strs))
for ln, v in strs[:10]:
    print("     %5d| %s" % (ln, repr(v.strip()[:88])))

# ---- 块（A 按连续注释行扩张；B 单独处理）----
def is_c(k):
    return L[k].lstrip().startswith("#")

blocks, seen = [], set()
for k in full:
    if k in seen:
        continue
    a = k
    while a - 1 > doc_end and is_c(a - 1) and (a - 1) not in full:
        a -= 1
    b = k
    while b + 1 < len(L) and is_c(b + 1):
        b += 1
    for x in range(a, b + 1):
        seen.add(x)
    blocks.append((a, b))
print("\n[A] 批注块数 = %d，覆盖行数 = %d"
      % (len(blocks), sum(b - a + 1 for a, b in blocks)))

# ---- 归属：每个块最近的 enclosing def/class ----
owner = {}
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        for k in range(node.lineno - 1, node.end_lineno or node.lineno):
            owner.setdefault(k, node.name)
from collections import Counter
c = Counter(owner.get(a, "<module>") for a, b in blocks)
print("块归属 top10:", c.most_common(10))

# ---- 试删：验证 AST 等价（注释不在 AST 里）----
kill = set()
for a, b in blocks:
    kill.update(range(a, b + 1))
kill.update(trail)
keep = [ln for k, ln in enumerate(L) if k not in kill]
with_doc = "\n".join(keep[:i] + ['"""X"""'] + keep[i + 1:]) if False else None
# 更直接：抠掉模块 docstring 后比较 AST
def ex(t):
    a = t.index('"""'); b = t.index('"""', a + 3)
    return t[:a] + '"""X"""' + t[b + 3:]
def nv(t):
    o, n = re.subn(r'__version__ = "1\.23\.\d+"', '__version__ = "X"', t)
    assert n == 1
    return o
try:
    d1 = ast.dump(ast.parse(nv(ex(lf))))
    d2 = ast.dump(ast.parse(nv(ex("\n".join(keep)))))
    print("\n试删 %d 行（块 %d + 行尾 %d）→ AST 等价: %s"
          % (len(kill), sum(b - a + 1 for a, b in blocks), len(trail), d1 == d2))
except SyntaxError as e:
    print("\n★ 试删后语法错误:", e)
print("行数 %d -> %d" % (len(L), len(keep)))
