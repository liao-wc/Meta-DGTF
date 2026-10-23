# -*- coding: utf-8 -*-
"""[v1.23.38 第1步] 从 v1.23.37 复制出副本 + 改版本号两处。

铁律：主文件纯 CRLF；一律 read_bytes/write_bytes；改完自检。
版本号两处：docstring 标题 + __version__。
"""
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.37.py"
DST = HERE / "元DGTF-V1.23.38.py"

OLD_VER = "1.23.37"
NEW_VER = "1.23.38"

# ── 1) 复制（不覆盖源文件；DST 已存在就直接退出，幂等）────────────────
if DST.exists():
    print("[skip] %s 已存在，不做复制（幂等）" % DST.name)
else:
    shutil.copyfile(SRC, DST)
    print("[ok] 已复制 %s -> %s" % (SRC.name, DST.name))

# ── 2) 读原始字节，断言纯 CRLF ───────────────────────────────────────
raw = DST.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n"), "%s 不是纯 CRLF" % DST.name
assert b"\r\r\n" not in raw, "%s 含 CRLF 双写" % DST.name
s = raw.decode("utf-8").replace("\r\n", "\n")

n_before = len(s)

# ── 3) 版本号两处 ────────────────────────────────────────────────────
# 3a) docstring 标题：`元 DGTF · v1.23.37`
TITLE_OLD = "元 DGTF · v%s" % OLD_VER
TITLE_NEW = "元 DGTF · v%s" % NEW_VER
n_title = s.count(TITLE_OLD)
assert n_title == 1, "docstring 标题锚点命中 %d 次（要求 1）" % n_title
s = s.replace(TITLE_OLD, TITLE_NEW)

# 3b) __version__ = "1.23.38"
VER_OLD = '__version__ = "%s"' % OLD_VER
VER_NEW = '__version__ = "%s"' % NEW_VER
n_ver = s.count(VER_OLD)
assert n_ver == 1, "__version__ 锚点命中 %d 次（要求 1）" % n_ver
s = s.replace(VER_OLD, VER_NEW)

# ── 4) 写回（严格 CRLF）+ 自检 ───────────────────────────────────────
out = s.replace("\n", "\r\n").encode("utf-8")
assert b"\r\r\n" not in out, "写出后含 CRLF 双写"
DST.write_bytes(out)

# ── 5) 回读校验 ──────────────────────────────────────────────────────
chk = DST.read_bytes()
assert chk.count(b"\n") == chk.count(b"\r\n"), "回读：不是纯 CRLF"
assert b"\r\r\n" not in chk, "回读：含 CRLF 双写"
assert chk.count(b"\n") == len(s.split("\n")) - 1, "行数对不上"

import ast
ast.parse(chk.decode("utf-8"))

print("[ok] %s 行数（LF 计）=%d（改前 %d）"
      % (DST.name, len(s.split("\n")) - 1, n_before and -1 or 0))
print("[ok] docstring 标题 -> %s" % TITLE_NEW)
print("[ok] __version__    -> %s" % VER_NEW)
print("[ok] 纯 CRLF / 无 CRCRLF / AST OK")
