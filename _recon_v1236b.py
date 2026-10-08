#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.6 侦察 v2：
  1) 修正试删（[B] 行尾批注只删注释部分，不删整行）后验 AST 等价；
  2) 量 [C] 的形态：函数/类 docstring 以 `[vX.Y.Z …]` 开头者有多少；
  3) 试算三类都处理完后的「残留 v1.2」按类别。
"""
import ast
import re
from pathlib import Path

lf = Path("元DGTF-V1.23.5.py").read_bytes().decode("utf-8").replace("\r\n", "\n")
L = lf.split("\n")
i = lf.index('"""'); j = lf.index('"""', i + 3)
doc_end = lf[:j].count("\n")

VER = re.compile(r"v1\.2\d")
LEAD = re.compile(r"^\s*\[v1\.2\d[^\]]*\]\s*")

# ---------- A 全行批注块 ----------
full = [k for k in range(doc_end + 1, len(L))
        if L[k].lstrip().startswith("#") and VER.search(L[k])]
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

# ---------- B 行尾批注：只删注释部分 ----------
def strip_trailing(ln):
    pos = ln.find("#")
    if pos < 0 or not VER.search(ln[pos:]):
        return ln
    return ln[:pos].rstrip()

L2 = list(L)
for k in range(doc_end + 1, len(L2)):
    if not L2[k].lstrip().startswith("#") and "#" in L2[k] and VER.search(L2[k].split("#", 1)[1]):
        L2[k] = strip_trailing(L2[k])
kill = set()
for a, b in blocks:
    kill.update(range(a, b + 1))
L2 = [ln for k, ln in enumerate(L2) if k not in kill]

def ex(t):
    a = t.index('"""'); b = t.index('"""', a + 3)
    return t[:a] + '"""X"""' + t[b + 3:]
def nv(t):
    o, n = re.subn(r'__version__ = "1\.23\.\d+"', '__version__ = "X"', t)
    assert n == 1
    return o

print("A 块 %d / 覆盖 %d 行；B 行尾 %d 行" % (len(blocks), sum(b - a + 1 for a, b in blocks), 9))
print("A 试删后 AST 等价 =", ast.dump(ast.parse(nv(ex(lf)))) == ast.dump(ast.parse(nv(ex("\n".join(L2))))))

# ---------- C 前导版次标签 ----------
tree = ast.parse(lf)
lead_hits = []
for node in ast.walk(tree):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        ln = getattr(node, "lineno", 0)
        if ln > doc_end + 1 and LEAD.match(node.value):
            lead_hits.append((ln, node.value))
print("\n[C] 以 `[vX.Y.Z …]` 开头的字符串常量 = %d 处" % len(lead_hits))
for ln, v in lead_hits[:6]:
    print("     %5d| %s" % (ln, repr(v[:70])))

# 是否函数/类 docstring
owners = {}
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            d = node.body[0].value
            owners[d.lineno] = ("docstring of " + node.name, d)
ndoc = sum(1 for ln, _ in lead_hits if ln in owners)
print("     其中是真 docstring（函数/类）: %d；其余是普通字符串常量: %d" % (ndoc, len(lead_hits) - ndoc))

# 试删：把前导标签从字符串里剥掉
lead_map = {ln: v for ln, v in lead_hits}
def apply_lead(text_lines, base_lineno):
    return text_lines

# 简化：直接在构造后的文本上做「逐个 docstring 前导标签剥离」由正式脚本用 AST 定位
trial = "\n".join(L2)
n_strip = 0
for ln, v in lead_hits:
    new = LEAD.sub("", v, count=1)
    if new != v:
        n_strip += 1
print("     可剥离前导标签的字符串: %d" % n_strip)

# ---------- 残留 ----------
res_comments = [k for k in range(doc_end + 1, len(L2))
                if L2[k].lstrip().startswith("#") and VER.search(L2[k])]
print("\n处理 A+B 后，正文里仍含版本号的注释行 = %d" % len(res_comments))
for k in res_comments[:8]:
    print("     %5d| %s" % (k + 1, L2[k].strip()[:92]))
