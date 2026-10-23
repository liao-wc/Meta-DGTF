#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.31：smoke_test 接入（SRC + EML 判据）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "smoke_test.py"
b = p.read_bytes()
is_crlf = b.count(b"\r\n") > 0 and b.count(b"\r\n") == b.count(b"\n")
s = b.decode("utf-8").replace("\r\n", "\n")


def rep(old, new, what, expect=1):
    global s
    n = s.count(old)
    assert n == expect, "%s: %d" % (what, n)
    s = s.replace(old, new)


rep('SRC = HERE / "元DGTF-V1.23.30.py"',
    'SRC = HERE / "元DGTF-V1.23.31.py"', "SRC")

FN = Path(HERE / "_smk_v12331_fn.py").read_text(encoding="utf-8")

rep("def check_v12330_duty_guard():", FN + "def check_v12330_duty_guard():",
    "插入判据")

rep("""    if not check_v12330_duty_guard():
        return 1
""", """    if not check_v12330_duty_guard():
        return 1
    if not check_v12331_memory_loop():
        return 1
""", "注册")

out = s.replace("\n", "\r\n") if is_crlf else s
p.write_bytes(out.encode("utf-8"))
print("smoke 接入完成（CRLF=%s）" % is_crlf)
