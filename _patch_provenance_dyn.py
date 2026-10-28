# -*- coding: utf-8 -*-
"""修 `dgtf_v2/provenance.py`：溯源指纹两处硬编码、且互相矛盾。

实测（V2.2.11 真跑产物）：
    provenance.engine_file    = "dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.4.py"
    provenance.engine_version = "V2.2.3"      ← 自相矛盾，且都落后于实际 V2.2.11

根因 = 把锚钉在**会变的东西**上（版本号硬编码成字面量）。这个模块存在的理由
就是「质量问题能归因到版本」，写错版本等于指纹不可信。

修法（不是"把 V2.2.3 改成 V2.2.11"——那下次还会漂）：
  · 优先用 `__main__.__file__`（本模块由引擎 import，主程序就是那个引擎）；
  · 取不到（pytest / 被别的主程序 import）⇒ 选引擎目录里**最高版本**；
  · `engine_version` 从**同一个文件名**推导 ⇒ 两字段同源，结构上不可能对不上。
"""
from __future__ import annotations

from pathlib import Path

SRC = Path(r"D:\Meta-DGTF-道生三阶模型\dgtf_engine\dgtf_v2\provenance.py")

data = SRC.read_bytes()
crlf, lf = data.count(b"\r\n"), data.count(b"\n")
assert crlf == lf and crlf > 0, "本文件应为纯 CRLF：crlf=%d lf=%d" % (crlf, lf)
src = data.decode("utf-8").replace("\r\n", "\n")
print("read: %s | lines=%d" % (SRC.name, src.count("\n") + 1))

edits = []

# ---- 1. 常量 -> 动态解析（同源）----
a = 'ENGINE_FILE = "dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.4.py"'
b = '''def _engine_path():
    """真正在跑的引擎文件路径（缓存）。

    本模块由引擎 import ⇒ `__main__.__file__` 就是那个引擎脚本（最准）；
    取不到（pytest / 被别的主程序 import）⇒ 退回「引擎目录里的最高版本」。
    ★ 绝不写死版本号：写死会立刻过期，而且 `engine_file` 与 `engine_version`
      会各写各的 —— 实测出现过 file=V2.2.4 / version=V2.2.3 的自相矛盾，
      而这个模块存在的理由就是「质量能归因到版本」。
    """
    if "engine_path" in _CACHE:
        return _CACHE["engine_path"]
    p = None
    try:
        import __main__
        _mf = str(getattr(__main__, "__file__", "") or "")
        if "Meta-DGTF-V" in _mf and Path(_mf).is_file():
            p = Path(_mf)
    except Exception:  # noqa: BLE001
        p = None
    if p is None:
        best = None
        for f in (ROOT / "dgtf_engine" / "dgtf_v2" / "engine").glob(
                "Meta-DGTF-V*.py"):
            m = re.search(r"V(\\d+)\\.(\\d+)\\.(\\d+)", f.name)
            if not m:
                continue
            key = tuple(int(x) for x in m.groups())
            if best is None or key > best[0]:
                best = (key, f)
        p = best[1] if best else None
    _CACHE["engine_path"] = p
    return p


def engine_file() -> str:
    """当前引擎相对仓库根的路径；取不到时明确写 unknown（不编造）。"""
    p = _engine_path()
    if p is None:
        return "unknown"
    try:
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:  # noqa: BLE001
        return p.as_posix()


def engine_version() -> str:
    """引擎版本 —— 从**与 engine_file 同一个文件名**推导，不可能对不上。"""
    p = _engine_path()
    if p is None:
        return "unknown"
    m = re.search(r"V(\\d+\\.\\d+\\.\\d+)", p.name)
    return ("V" + m.group(1)) if m else "unknown"'''
edits.append((a, b, 1))

# ---- 2. 调用点改用动态值 ----
a = '        "engine_file": ENGINE_FILE,\n        "engine_version": "V2.2.3",'
b = '        "engine_file": engine_file(),\n        "engine_version": engine_version(),'
edits.append((a, b, 1))

for old, new, want in edits:
    got = src.count(old)
    assert got == want, "锚点命中 %d 次（期望 %d）：%r" % (got, want, old[:60])
    src = src.replace(old, new)
    print("  ok: %s" % old[:50].replace("\n", "\\n"))

out = src.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
assert out.count(b"\r\n") == out.count(b"\n"), "输出不是纯 CRLF"
SRC.write_bytes(out)
print("written: %s | lines=%d | CRLF=%d" % (SRC.name, out.count(b"\n") + 1,
                                            out.count(b"\r\n")))
print("PATCH OK")
