# -*- coding: utf-8 -*-
"""修 M107 的锚点：那行是 `_acct = {"llm_calls": ...` 连写的，不是行首键。

★ 教训：**锚点必须带上下文**。我按"键在行首"的习惯写锚，实际它跟在 `_acct = {`
  后面 ⇒ 命中 0 次 ⇒ 变异体"失效"。而汇总只报「0 判红」—— 看起来像"判据没牙"，
  其实是**变异体没插进去**。这两种失败必须分清（一个是判据问题，一个是工具问题）。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "_mut_v12332.py"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n")
s = raw.decode("utf-8").replace("\r\n", "\n")

OLD1 = """'                 "llm_calls": int(_base.get("calls") or 0) + _w_calls,'"""
NEW1 = """'{"llm_calls": int(_base.get("calls") or 0) + _w_calls,'"""
OLD2 = """'                 "llm_calls": _w_calls,  # MUT'"""
NEW2 = """'{"llm_calls": _w_calls,  # MUT'"""

for o, n in ((OLD1, NEW1), (OLD2, NEW2)):
    assert s.count(o) == 1, "锚点命中 %d 次：%s" % (s.count(o), o[:40])
    s = s.replace(o, n)

ast.parse(s)
p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("M107 锚点已修正（带上 `{` 上下文）")
