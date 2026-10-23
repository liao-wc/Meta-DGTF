# -*- coding: utf-8 -*-
"""v1.23.50 变异体补丁：SRC 指新版 + +M101（续跑不跳过已完成层）+ 链接判据。

M101 锚点 `            if entry in self._results:`（层跳过条件）→ `if False:`
⇒ 已完成层会被**重跑**（白烧钱）⇒ `check_v12350_resume` 必须判红。

CRLF 安全。
"""
from pathlib import Path

P = Path(__file__).resolve().parent / "_mut_v12332.py"
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n") and b.count(b"\r\r\n") == 0
t = b.decode("utf-8").replace("\r\n", "\n")

# ① SRC
old_src = 'SRC = HERE / "\u5143DGTF-V1.23.49.py"\n'
new_src = 'SRC = HERE / "\u5143DGTF-V1.23.50.py"\n'
assert t.count(old_src) == 1, "SRC 锚点不唯一"
t = t.replace(old_src, new_src, 1)

# ② +M101
old_m = (
    '    ("M100 \u5b64\u513f\u56de\u6536\u4e0d\u5224\u8fc7\u671f\uff08\u6c38\u8fdc\u4e0d\u52a8\uff09",\n'
    '     \'        if _age < float(stale_sec):\',\n'
    '     \'        if True:\'),\n'
    ']\n'
)
new_m = (
    '    ("M100 \u5b64\u513f\u56de\u6536\u4e0d\u5224\u8fc7\u671f\uff08\u6c38\u8fdc\u4e0d\u52a8\uff09",\n'
    '     \'        if _age < float(stale_sec):\',\n'
    '     \'        if True:\'),\n'
    '    ("M101 \u7eed\u8dd1\u4e0d\u8df3\u8fc7\u5df2\u5b8c\u6210\u5c42\uff08\u91cd\u8dd1 \u21d2 \u767d\u70e7\u94f1\uff09",\n'
    '     \'            if entry in self._results:\',\n'
    '     \'            if False:  # MUT\'),\n'
    ']\n'
)
assert t.count(old_m) == 1, "M100 段锚点不唯一"
t = t.replace(old_m, new_m, 1)

# ③ 判据链接入
old_chain = '             "st.check_v12349_run_ckpt() and "\n'
new_chain = ('             "st.check_v12349_run_ckpt() and "\n'
             '             "st.check_v12350_resume() and "\n')
assert t.count(old_chain) == 1, "判据链锚点不唯一"
t = t.replace(old_chain, new_chain, 1)

assert 'M101' in t and 'check_v12350_resume' in t
out = t.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
P.write_bytes(out)
b2 = P.read_bytes()
assert b2.count(b"\r\n") == b2.count(b"\n") and b2.count(b"\r\r\n") == 0
print("OK：变异体 +M101、SRC 指新版、链接入（纯 CRLF 保持）")

# ④ 锚点唯一性预检（引擎里 count 必须 == 1，否则变异体会 ANCHOR 失效）
eng = (Path(__file__).resolve().parent / "\u5143DGTF-V1.23.50.py").read_bytes() \
    .decode("utf-8").replace("\r\n", "\n")
for name, anch in (("M101", "            if entry in self._results:"),
                   ("M100", "        if _age < float(stale_sec):")):
    print("  引擎内锚点 %s 命中 %d" % (name, eng.count(anch)))
    assert eng.count(anch) == 1, "锚点不唯一：%s" % name
print("锚点预检通过")
