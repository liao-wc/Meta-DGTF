#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.7 判据补洞：`check_v1237_changelog_outside_code` 与 `_changelog_lint` 里的
版本段正则原来只认 `v1.2x`（`^v1\\.2\\d...`）——变异体 M1 注入 `v1.99.9 相对 v1.99.8`
竟**没被判红**。改成通用形态 `^v\\d+(?:\\.\\d+)+ 相对`。幂等、CRLF 往返。"""
import ast
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"
BAK = HERE / "_bak_smoke_test.pre_v1237_regex"

BS = chr(92)
PAIRS = [
    # _changelog_lint 的段标题提取
    ('re.findall(r"^v(1' + BS + '.2' + BS + 'd(?:' + BS + '.' + BS + 'd+)?) 相对", doc, re.M)',
     're.findall(r"^v(' + BS + 'd+(?:' + BS + '.' + BS + 'd+)+) 相对", doc, re.M)'),
    # check_v1237 的扫描（两处）
    ('if re.match(r"^v1' + BS + '.2' + BS + 'd(?:' + BS + '.' + BS + 'd+)? 相对", ln)]',
     'if re.match(r"^v' + BS + 'd+(?:' + BS + '.' + BS + 'd+)+ 相对", ln)]'),
    ('n = len(re.findall(r"^v1' + BS + '.2' + BS + 'd(?:' + BS + '.' + BS + 'd+)? 相对", cl, re.M))',
     'n = len(re.findall(r"^v' + BS + 'd+(?:' + BS + '.' + BS + 'd+)+ 相对", cl, re.M))'),
]


def main():
    raw = SK.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
    s = raw.decode("utf-8").replace("\r\n", "\n")
    if 'r"^v(\\d+(?:\\.\\d+)+) 相对"' in s:
        print("[skip] 正则已补")
        return 0
    for old, new in PAIRS:
        n = s.count(old)
        assert n == 1, "锚点命中 %d 次：%r" % (n, old[:60])
        s = s.replace(old, new, 1)
    if not BAK.exists():
        shutil.copy2(SK, BAK)
        print("回滚点：%s" % BAK.name)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
    SK.write_bytes(out)
    ast.parse(s)
    print("已补 3 处正则 → ^v\\d+(?:\\.\\d+)+ 相对")
    c = SK.read_bytes()
    print("smoke_test.py：%d 行 / CRLF=%d 裸LF=%d CRCRLF=%d"
          % (c.count(b"\n"), c.count(b"\r\n"),
             c.count(b"\n") - c.count(b"\r\n"), c.count(b"\r\r\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
