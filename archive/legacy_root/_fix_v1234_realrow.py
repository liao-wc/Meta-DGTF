#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.4] 修报告的「真跑旁证」行 + 修定稿器的取材逻辑。

★ 问题：定稿器取的是**最新产物**（`glob` 按 mtime 排序取第一份）。本轮
  10 跑回归批当天又产出了一批产物 ⇒ 取到了它的产物（`requested` 全是 auto、
  `effort=low`），与那一行写着 `--effort high` **矛盾**。
  这正是本项目的老坑：**判据/取材的锚不能是「恰好只有一份产物」这种隐含前提**。

修法：**按 `_runtime.requested` 精确匹配**（真跑给的三项），而不是按 mtime。
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
WANT = {"web": "on", "thinking": "off", "effort": "high"}

# ---------------- 1 找到真跑产物 ----------------
hits = []
for p in list(HERE.glob("outputs/*.md")) + list(HERE.glob("outputs/*/*.md")):
    t = p.read_bytes().decode("utf-8", "replace")
    if '"_runtime"' not in t:
        continue
    m = re.search(r'"_runtime": \{(.*?)\n    \}', t, re.S)
    if not m:
        continue
    blk = m.group(1)

    def g(k, _b=blk):
        mm = re.search(r'"%s": "([^"]*)"' % k, _b)
        return mm.group(1) if mm else None

    if {k: g(k) for k in ("web", "thinking", "effort")} == WANT:
        hits.append((p.stat().st_mtime, p, blk))
hits.sort(key=lambda x: x[0], reverse=True)
assert hits, "没找到 requested 与真跑一致（%r）的产物" % WANT
prod = hits[0][1]
blk = hits[0][2]


def gv(k):
    mm = re.search(r'"%s": "?([^",\n]*)"?' % k, blk)
    return (mm.group(1).strip() if mm else "?")


ROW = ("| **真跑旁证**（端到端） | "
       "`python 元DGTF-V1.23.4.py … --web on --thinking off --effort high` | "
       "横幅：联网 开 | 思考 关（0 个环节开档 / 25 关）| 强度 high；"
       "产物 `_runtime.requested` = `{web: on, thinking: off, effort: high}`，"
       "生效值 `web_enabled=%s / thinking_default=%s / effort=%s`（`%s`） |"
       % (gv("web_enabled"), gv("thinking_default"), gv("effort"),
          prod.relative_to(HERE).as_posix()))

# ---------------- 2 换掉报告里那一行 ----------------
RP = HERE / "v1234_报告.md"
b = RP.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n")
s = b.decode("utf-8").replace("\r\n", "\n")
old = None
for ln in s.split("\n"):
    if ln.startswith("| **真跑旁证**"):
        old = ln
        break
assert old is not None, "报告里找不到「真跑旁证」行"
s = s.replace(old, ROW, 1)
RP.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("报告真跑旁证行已修：")
print("  " + ROW)

# ---------------- 3 修定稿器的取材逻辑 ----------------
FP = HERE / "_mk_v1234_fill.py"
fb = FP.read_bytes()
assert fb.count(b"\r\n") == fb.count(b"\n")
f = fb.decode("utf-8").replace("\r\n", "\n")
O = '''_prod = None
for _d in sorted((HERE / "outputs").glob("*"), key=lambda p: p.stat().st_mtime
                 if p.exists() else 0, reverse=True)[:6]:
    for _p in sorted(_d.glob("*.md"), key=lambda p: p.stat().st_mtime
                     if p.exists() else 0, reverse=True)[:1]:
        _t = _p.read_bytes().decode("utf-8", "replace")
        if "_runtime" in _t:
            _m5 = re.search(r'"web_enabled":\\s*(\\w+).*?"thinking_default":\\s*"(\\w+)".*?"effort":\\s*"(\\w+)"',
                            _t, re.S)
            _prod = (_p.name, _m5.groups() if _m5 else None)
            break
    if _prod:
        break'''
N = '''# ★ 按 `_runtime.requested` **精确匹配**本次真跑给的三项，不按 mtime 取最新 ——
#   同一天还有回归批的产物，按 mtime 会取到**别人的产物**（本轮实踩：
#   那一行写着 `--effort high` 而产物里是 `effort=low`，自相矛盾）。
_WANT = {"web": "on", "thinking": "off", "effort": "high"}
_prod = None
_cands = list((HERE / "outputs").glob("*.md")) \\
    + list((HERE / "outputs").glob("*/*.md"))
_cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
for _p in _cands:
    _t = _p.read_bytes().decode("utf-8", "replace")
    _mr = re.search(r'"_runtime": \\{(.*?)\\n    \\}', _t, re.S)
    if not _mr:
        continue
    _blk = _mr.group(1)

    def _g(k, _b=_blk):
        _mm = re.search(r'"%s": "([^"]*)"' % k, _b)
        return _mm.group(1) if _mm else None

    if {k: _g(k) for k in ("web", "thinking", "effort")} != _WANT:
        continue
    _m5 = re.search(r'"web_enabled":\\s*(\\w+).*?"thinking_default":\\s*"(\\w+)"'
                    r'.*?"effort":\\s*"(\\w+)"', _blk, re.S)
    _prod = (_p.name, _m5.groups() if _m5 else None)
    break'''
assert f.count(O) == 1, "定稿器取材段锚点 %d 次" % f.count(O)
f = f.replace(O, N, 1)
FP.write_bytes(f.replace("\n", "\r\n").encode("utf-8"))
print("定稿器取材逻辑已改为「按 requested 精确匹配」")
