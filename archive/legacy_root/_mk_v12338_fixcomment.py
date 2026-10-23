# -*- coding: utf-8 -*-
"""[v1.23.38 补丁4] 去掉主文件代码注释里的版次批注 `[v1.23.38]`。

★ 红线：版次批注**不许写进代码注释**（要落 `CHANGELOG.md`）——
  由冒烟 `[v1236] 正文注释里仍有版次批注` 判据钉住。
★ 保留解释性文字，只去掉 `[vX.Y.Z]` 这个记号。
"""
from pathlib import Path

TGT = Path(__file__).resolve().parent / "元DGTF-V1.23.38.py"

OLD = "    #: ★ [v1.23.38] 按**同族补漏**扩展 4 个（4 → 8）："
NEW = "    #: ★ 按**同族补漏**扩展 4 个（4 → 8）："


def _rw(p, fn):
    raw = p.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "%s 不是纯 CRLF" % p.name
    assert b"\r\r\n" not in raw, "%s 含 CRLF 双写" % p.name
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out, "%s 写出后含 CRLF 双写" % p.name
    assert out.count(b"\n") == out.count(b"\r\n"), "%s 写出后不是纯 CRLF" % p.name
    p.write_bytes(out)


def apply(s):
    n = s.count(OLD)
    assert n == 1, "锚点命中 %d 次（要求 1）" % n
    return s.replace(OLD, NEW)


_rw(TGT, apply)

raw = TGT.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n")
assert b"\r\r\n" not in raw
src = raw.decode("utf-8")
import ast
ast.parse(src)

# ★ 自检：除 docstring 标题行外，不应再有 `[v1.23.38]`
_hits = [(i, l) for i, l in enumerate(src.split("\n"), 1)
         if "v1.23.38" in l]
print("[info] 仍含 v1.23.38 的行：")
for i, l in _hits:
    print("   %5d | %s" % (i, l.strip()))
assert len(_hits) == 1 and _hits[0][0] == 4, "仍有非标题行的版次批注"
print("[ok] 已去掉代码注释里的 [v1.23.38]（仅 docstring 标题保留）")
print("[ok] 纯 CRLF / 无 CRCRLF / AST OK / 行数 =", src.count("\n"))
