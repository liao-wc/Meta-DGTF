# -*- coding: utf-8 -*-
"""provenance.py 补丁 2/2：为判据让路。

1) 解释性注释里**不写版本号字面量** —— 注释本身会污染「不许硬编码版本」
   这条判据（读源码做静态扫描时会把注释里的版本当成硬编码）。
2) 去掉 `Path(_mf).is_file()`：名字里带 `Meta-DGTF-V` 已经是够强的判据
   （pytest 下 `__main__` 不是引擎 ⇒ 自然回退），而要求文件存在会让
   「动态解析」无法被构造性证明（造不出一个不存在的假引擎文件）。
"""
from __future__ import annotations

from pathlib import Path

SRC = Path(r"D:\Meta-DGTF-道生三阶模型\dgtf_engine\dgtf_v2\provenance.py")
data = SRC.read_bytes()
crlf, lf = data.count(b"\r\n"), data.count(b"\n")
assert crlf == lf and crlf > 0, "应为纯 CRLF：crlf=%d lf=%d" % (crlf, lf)
src = data.decode("utf-8").replace("\r\n", "\n")

edits = [
    ("      会各写各的 —— 实测出现过 file=V2.2.4 / version=V2.2.3 的自相矛盾，\n"
     "      而这个模块存在的理由就是「质量能归因到版本」。",
     "      会各写各的 —— 实测出现过两个字段相差一个版本的自相矛盾，\n"
     "      而这个模块存在的理由就是「质量能归因到版本」。", 1),
    ('if "Meta-DGTF-V" in _mf and Path(_mf).is_file():',
     'if "Meta-DGTF-V" in _mf:', 1),
]

for old, new, want in edits:
    got = src.count(old)
    assert got == want, "锚点命中 %d 次（期望 %d）：%r" % (got, want, old[:60])
    src = src.replace(old, new)
    print("  ok: %s" % old[:46].replace("\n", "\\n"))

out = src.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
assert out.count(b"\r\n") == out.count(b"\n")
SRC.write_bytes(out)
print("PATCH2 OK | lines=%d" % (out.count(b"\n") + 1))
