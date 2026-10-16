# -*- coding: utf-8 -*-
"""修错字：`铱`（\u94f1）→ `钱`（\u94b1）。三处（smoke 判据消息 / 变异体名 / 引擎注释）。

CRLF 安全（字节级替换，不动换行）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
BAD = "铱".encode("utf-8")
GOOD = "钱".encode("utf-8")
for f in ("smoke_test.py", "_mut_v12332.py", "元DGTF-V1.23.50.py"):
    p = HERE / f
    b = p.read_bytes()
    crlf, lf = b.count(b"\r\n"), b.count(b"\n")
    assert crlf == lf and b.count(b"\r\r\n") == 0, "%s 换行格式异常" % f
    n = b.count(BAD)
    print("%-24s 命中 %d" % (f, n))
    assert n == 1, "%s 命中数不是 1" % f
    b = b.replace(BAD, GOOD, 1)
    assert b.count(BAD) == 0
    assert b.count(b"\r\n") == crlf and b.count(b"\n") == lf, "换行被改动：%s" % f
    p.write_bytes(b)
print("OK：错字已修（三个文件，换行未动）")
