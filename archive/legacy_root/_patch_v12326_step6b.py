#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 Step6b：修 step6 引入的字面 `\n\n\n` 污染行。

原因：step6 用 `NEW_CHECK.strip("\\n")`，那是**两个字的字符串**
（反斜杠 + n），不是换行；同理拼接用的 `"\\n\\n\\n"` 也被字面写入。
教训（写进记忆）：**在补丁脚本里拼换行一律用 `chr(10)` 或真换行，
不要写 `"\\n"`** —— 外层脚本自己的转义层级很容易吞掉一层。
"""
from pathlib import Path

SMOKE = Path(__file__).resolve().parent / "smoke_test.py"
b = SMOKE.read_bytes()
_is_crlf = b.count(b"\r\n") > 0
txt = b.decode("utf-8")
if _is_crlf:
    txt = txt.replace("\r\n", "\n")

BS = chr(92)
BAD = ("    return True\n" + BS + "n" + BS + "n" + BS + "n"
       + "\ndef check_v12324_indep_therapy():")
GOOD = "    return True\n\n\ndef check_v12324_indep_therapy():"
assert txt.count(BAD) == 1, f"污染行命中 {txt.count(BAD)} 次"
txt = txt.replace(BAD, GOOD, 1)

out = txt.replace("\n", "\r\n").encode("utf-8") if _is_crlf else txt.encode("utf-8")
SMOKE.write_bytes(out)

import ast
ast.parse(out.decode("utf-8"))
print("OK Step6b: 污染行已修；AST OK")
print("lines =", out.count(b"\n"), "bytes =", len(out))
