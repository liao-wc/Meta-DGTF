#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 Step6b（重写）：删掉 check_v12326_sim3 与 check_v12324 之间的污染行。

不猜转义层级了 —— 直接按行处理：找到 `def check_v12324_indep_therapy():`
所在行，把它**上面**紧邻的、以反斜杠开头的行删掉，并补齐两个空行。
"""
from pathlib import Path
import ast

SMOKE = Path(__file__).resolve().parent / "smoke_test.py"
b = SMOKE.read_bytes()
_is_crlf = b.count(b"\r\n") > 0
txt = b.decode("utf-8")
if _is_crlf:
    txt = txt.replace("\r\n", "\n")

lines = txt.split("\n")
# 定位被污染的 check_v12324 def 行（形如 `\n\n\ndef check_v12324...`）
tgt = next(i for i, l in enumerate(lines)
           if "def check_v12324_indep_therapy" in l)
print(f"check_v12324 所在行 {tgt + 1}: {lines[tgt]!r}")

# 该行前面若粘着 `\n` 系列字面（反斜杠 + n），剥掉
raw = lines[tgt]
clean = raw
while clean.startswith(chr(92) + "n"):
    clean = clean[2:]
print(f"剥离后: {clean!r}")
assert clean.startswith("def check_v12324_indep_therapy"), "剥离失败"

# 同时确认上一行是 return True
print(f"上一行 {tgt}: {lines[tgt - 1]!r}")

new_lines = lines[:tgt] + ["", "", "", clean] + lines[tgt + 1:]
txt2 = "\n".join(new_lines)

# 自检
ast.parse(txt2)
assert txt2.count("def check_v12326_sim3") == 1
assert txt2.count("def check_v12324_indep_therapy") == 1
assert chr(92) + "n" + chr(92) + "n" not in txt2.split("def check_v12324")[0][-80:]

out = txt2.replace("\n", "\r\n").encode("utf-8") if _is_crlf else txt2.encode("utf-8")
SMOKE.write_bytes(out)
print("OK Step6b: 污染行已删；AST OK")
print("lines =", out.count(b"\n"), "bytes =", len(out))
