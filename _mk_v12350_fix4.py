# -*- coding: utf-8 -*-
"""v1.23.50 修正：代码正文不写版次批注（`check_v1236_no_version_tags` 判红）。

本项目自 v1.23.6 起要求：**注释/docstring 写「这段为什么长这样」，不写「哪个版本改的」**
（版次只在 `CHANGELOG.md`）。本版新写的 9 行注释 + 2 处 docstring 用了 `[v1.23.50 …]`
批注 ⇒ 判红。改法：保留**功能名**、去掉版次（与既有风格一致，如 `[B1 规则优先]`）。

CRLF 安全；改完用与判据同一把尺子复检（0 命中）。
"""
import re
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.50.py"
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n") and b.count(b"\r\r\n") == 0
t = b.decode("utf-8").replace("\r\n", "\n")

SUBS = [
    ("# \u2605 [v1.23.50] \u7eed\u8dd1\u8981\u8fd8\u539f**\u6c60**",
     "# \u2605 [\u7eed\u8dd1] \u8981\u8fd8\u539f**\u6c60**"),
    ("# \u2605 [v1.23.50 \u8bb0\u8d26] \u88ab\u6740\u8dd1\u6b21\u7684\u8ba1\u6570\u5668\u968f\u8fdb\u7a0b\u6d88\u5931",
     "# \u2605 [\u5feb\u7167\u8bb0\u8d26] \u88ab\u6740\u8dd1\u6b21\u7684\u8ba1\u6570\u5668\u968f\u8fdb\u7a0b\u6d88\u5931"),
    ("# \u2605\u2605 [v1.23.50] \u65ad\u70b9\u7eed\u8dd1 + \u5899\u949f\u9884\u7b97\uff08\u9ed8\u8ba4\u5168\u5173 \u21d2 \u96f6\u884c\u4e3a\u5dee\uff09\u3002",
     "# \u2605\u2605 [\u65ad\u70b9\u7eed\u8dd1] + [\u5899\u949f\u9884\u7b97]\uff08\u9ed8\u8ba4\u5168\u5173 \u21d2 \u96f6\u884c\u4e3a\u5dee\uff09\u3002"),
    ("# \u2605 [v1.23.50] \u8bb0**\u751f\u6548**\u7684 route\uff08\u88c1\u5b9a\u4e4b\u540e\uff09\u3002",
     "# \u2605 [route \u6b7b\u6355\u83b7] \u8bb0**\u751f\u6548**\u7684 route\uff08\u88c1\u5b9a\u4e4b\u540e\uff09\u3002"),
    ("# \u2605 [v1.23.50 \u65ad\u70b9\u7eed\u8dd1] \u6062\u7528\u5feb\u7167\u91cc**\u5df2\u5b8c\u6210\u7684\u5c42**\u3002",
     "# \u2605 [\u65ad\u70b9\u7eed\u8dd1] \u6062\u7528\u5feb\u7167\u91cc**\u5df2\u5b8c\u6210\u7684\u5c42**\u3002"),
    ("#   \u2605 [v1.23.50] \u5899\u949f\u9884\u7b97\u5230\u70b9\u65f6\u72b6\u6001\u662f **paused**",
     "#   \u2605 [\u5899\u949f\u9884\u7b97] \u5230\u70b9\u65f6\u72b6\u6001\u662f **paused**"),
    ("# \u2605 [v1.23.50 \u65ad\u70b9\u7eed\u8dd1] \u628a\u5feb\u7167\u91cc**\u5df2\u5b8c\u6210**\u7684\u5c42\u79cd\u56de",
     "# \u2605 [\u65ad\u70b9\u7eed\u8dd1] \u628a\u5feb\u7167\u91cc**\u5df2\u5b8c\u6210**\u7684\u5c42\u79cd\u56de"),
    ("# \u2605 [v1.23.50 \u65ad\u70b9\u7eed\u8dd1] \u5df2\u5b8c\u6210\u7684\u5c42\u76f4\u63a5\u8df3\u8fc7",
     "# \u2605 [\u65ad\u70b9\u7eed\u8dd1] \u5df2\u5b8c\u6210\u7684\u5c42\u76f4\u63a5\u8df3\u8fc7"),
    ("# \u2605 [v1.23.50 \u5899\u949f\u9884\u7b97] \u5c42\u95f4\u5b88\u536b\uff1a\u8d85\u9884\u7b97",
     "# \u2605 [\u5899\u949f\u9884\u7b97] \u5c42\u95f4\u5b88\u536b\uff1a\u8d85\u9884\u7b97"),
    ('        """[v1.23.50 \u65ad\u70b9\u7eed\u8dd1] `to_dict()` \u7684**\u9006**\uff1a\u4ece\u5feb\u7167/\u4ea7\u7269\u5b57\u5178\u8fd8\u539f View\u3002\n',
     '        """\u65ad\u70b9\u7eed\u8dd1\u7528\u7684\u8fd8\u539f\u5668\uff1a`to_dict()` \u7684**\u9006**\u2014\u2014\u4ece\u5feb\u7167/\u4ea7\u7269\u5b57\u5178\u8fd8\u539f View\u3002\n'),
    ('    """[v1.23.50 \u65ad\u70b9\u7eed\u8dd1] \u8bfb\u4e00\u4efd\u5feb\u7167 \u21d2 `{"ok", "why", "views", "pools"}`\u3002\n',
     '    """\u65ad\u70b9\u7eed\u8dd1\u5165\u53e3\uff1a\u8bfb\u4e00\u4efd\u5feb\u7167 \u21d2 `{"ok", "why", "views", "pools"}`\u3002\n'),
]
for i, (o, n) in enumerate(SUBS, 1):
    c = t.count(o)
    print("%2d \u547d\u4e2d %d | %s" % (i, c, o.strip()[:48]))
    assert c == 1, "\u951a\u70b9\u4e0d\u552f\u4e00/\u4e0d\u5b58\u5728\uff1a%s" % o[:70]
    t = t.replace(o, n, 1)

out = t.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
P.write_bytes(out)
b2 = P.read_bytes()
assert b2.count(b"\r\n") == b2.count(b"\n") and b2.count(b"\r\r\n") == 0

# ── 用与判据同一把尺子复检 ─────────────────────────────────────────
import ast
TAG = re.compile(r"\[v\d[^\]]*\]|(?<![A-Za-z0-9_\-])v\d+(?:\.\d+)*(?![A-Za-z0-9_\-])")
src = b2.decode("utf-8").replace("\r\n", "\n")
lines = src.split("\n")
i = src.index('"""'); j = src.index('"""', i + 3)
de = src[:j].count("\n")
hits = [k + 1 for k in range(de + 1, len(lines))
        if lines[k].lstrip().startswith("#") and TAG.search(lines[k])]
trail = [k + 1 for k in range(de + 1, len(lines))
         if not lines[k].lstrip().startswith("#") and "#" in lines[k]
         and TAG.search(lines[k].split("#", 1)[1])]
docbad = []
for node in ast.walk(ast.parse(src)):
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        continue
    if node.body and isinstance(node.body[0], ast.Expr) and \
            isinstance(node.body[0].value, ast.Constant) and \
            isinstance(node.body[0].value.value, str) and node.lineno > de + 1 and \
            re.match(r"\s*(?:" + TAG.pattern + r")", node.body[0].value.value):
        docbad.append(node.name)
print("复检：注释 %d 行 / 行尾 %d 行 / docstring %d 处" % (len(hits), len(trail), len(docbad)))
assert not hits and not trail and not docbad, "仍有违规：%r %r %r" % (hits, trail, docbad)
print("OK：版次批注已清零（%d 处改动）" % len(SUBS))
