#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复制 v1.23.23 → v1.23.24 并升版本号（两处）。

★ 主文件纯 CRLF：read_bytes → 断言 → 转 LF → 替换 → 转回 CRLF → write_bytes。
★ 绝不 write_text（会把 \n 再翻成 \r\n ⇒ 每行 \r\r\n，且不报错）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.23.py"
DST = HERE / "元DGTF-V1.23.24.py"

OLD_TITLE = "元 DGTF · v1.23.23"
NEW_TITLE = "元 DGTF · v1.23.24"
OLD_VER = '__version__ = "1.23.23"'
NEW_VER = '__version__ = "1.23.24"'


def main():
    raw = SRC.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n"), "源文件不是纯 CRLF"
    assert raw.count(b"\r\r\n") == 0, "源文件已含 CRCRLF"
    s = raw.decode("utf-8").replace("\r\n", "\n")

    for _o, _n, _what in ((OLD_TITLE, NEW_TITLE, "docstring 标题"),
                          (OLD_VER, NEW_VER, "__version__")):
        n = s.count(_o)
        assert n == 1, "%s 命中 %d 次（要求 1）" % (_what, n)
        s = s.replace(_o, _n)

    # 反向断言：新串存在、旧串不再存在
    assert s.count(NEW_TITLE) == 1 and s.count(OLD_TITLE) == 0
    assert s.count(NEW_VER) == 1 and s.count(OLD_VER) == 0
    assert s.count("元 DGTF · v1.23.24") == 1

    out = s.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0, "产出含 CRCRLF（write_text 的坑）"
    assert out.count(b"\n") == out.count(b"\r\n"), "产出不是纯 CRLF"
    assert out.count(b"\r") == out.count(b"\r\n"), "产出有游离 CR"
    DST.write_bytes(out)

    # 回读校验（沙箱 overlay 会吞写入）
    chk = DST.read_bytes()
    assert chk == out, "回读不一致"
    print("OK %s  %d bytes  %d 行(LF)"
          % (DST.name, len(chk), chk.decode("utf-8").count("\n")))


if __name__ == "__main__":
    main()
