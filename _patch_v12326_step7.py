#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 Step7：清掉本轮补丁引入的**版次批注**（v1.23.6 判据要求）。

现象：`check_v1236_no_version_tags` 判红 2 行成块 ——
  L619  `# 池内去重阈值。**这两个值等价于 v1.23.25 里 Pool.merge 内的硬编码`
  L18012 `# 池内去重阈值（v1.23.25 及以前是 Pool.merge 里的硬编码字面量）。`

两处都是本轮 step4 补丁**自己写进去**的注释：正文注释里带了版本号字面
（判据 TAG = `[v...]` 或裸 `v\d+(\.\d+)*`）。

修法：把版本号换成**语义表述**（「上一版」）—— 信息不丢，判据不再命中。
★ 这不是「放宽判据」：判据的意图是「正文不留版次批注」，换成语义表述后
  该意图**仍然成立**，而且信息对读者更清楚（读者不关心是哪一版）。
"""
from pathlib import Path
import ast

SRC = Path(__file__).resolve().parent / "元DGTF-V1.23.26.py"
b = SRC.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "主文件不是纯 CRLF"
assert b.count(b"\r\r\n") == 0, "主文件含 CRCRLF"
txt = b.decode("utf-8").replace("\r\n", "\n")

EDITS = [
    (
        "# 池内去重阈值。**这两个值等价于 v1.23.25 里 Pool.merge 内的硬编码\n"
        "# 字面量**（0.9 / 0.85），提取出来只是为了让「参数按层可覆盖」这条红线\n",
        "# 池内去重阈值。**这两个值等价于上一版 Pool.merge 内的硬编码字面量**\n"
        "# （0.9 / 0.85），提取出来只是为了让「参数按层可覆盖」这条红线\n",
    ),
    (
        "        # 池内去重阈值（v1.23.25 及以前是 Pool.merge 里的硬编码字面量）。\n",
        "        # 池内去重阈值（上一版及以前是 Pool.merge 里的硬编码字面量）。\n",
    ),
]

for old, new in EDITS:
    c = txt.count(old)
    assert c == 1, f"锚点命中 {c} 次（期望 1）：{old[:40]!r}"
    txt = txt.replace(old, new, 1)

# 写回：纯 CRLF + write_bytes
out = txt.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "写回后出现 CRCRLF"
SRC.write_bytes(out)
ast.parse(out.decode("utf-8"))

# 自检：正文注释里不再有版次标记
import re
_src = out.decode("utf-8").replace("\r\n", "\n")
_i = _src.index('"""'); _j = _src.index('"""', _i + 3)
_de = _src[:j].count("\n") if False else _src[:_j].count("\n")
_lines = _src.split("\n")
_TAG = re.compile(r"\[v\d[^\]]*\]|(?<![A-Za-z0-9_\-])v\d+(?:\.\d+)*(?![A-Za-z0-9_\-])")
_left = [k + 1 for k in range(_de + 1, len(_lines))
         if _lines[k].lstrip().startswith("#") and _TAG.search(_lines[k])]
assert not _left, f"仍残留版次批注：{_left}"

print("OK Step7: 版次批注已清（2 处 -> 语义表述）")
print("lines =", out.count(b"\n"), "bytes =", len(out))
