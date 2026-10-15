# -*- coding: utf-8 -*-
"""[dry-run] 把 _mk_v12338_smoke.py 的 apply() 施加到**内存副本**，验证：
  ① 替换锚点各命中 1 次；
  ② 施加后 smoke_test.py 仍能 AST 解析；
  ③ 新增判据函数/调用各出现恰 1 次；
  ④ CRLF 往返不产生 \r\r\n。

★ 不写任何真实文件（只读 smoke_test.py）。
"""
import ast
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


mk = _load(HERE / "_mk_v12338_smoke.py", "mk_smoke")

SM = HERE / "smoke_test.py"
raw = SM.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n"), "smoke_test.py 不是纯 CRLF"
assert b"\r\r\n" not in raw, "smoke_test.py 含 CRLF 双写"
s = raw.decode("utf-8").replace("\r\n", "\n")

# ── 逐个锚点先查命中次数 ──
print("[check] OLD_SRC          命中", s.count(mk.OLD_SRC))
print("[check] roundtick def    命中", s.count("def check_v12337_roundtick():"))
print("[check] CALL_OLD         命中", s.count(mk.CALL_OLD))

# ── 施加 ──
try:
    s2 = mk.apply(s)
    print("[ok] apply() 成功")
except AssertionError as e:
    print("[FAIL] apply() 断言失败：%s" % e)
    raise SystemExit(1)

# ── 自检 ──
print("[check] 新判据定义 命中", s2.count("def check_v12338_backfeed():"))
print("[check] 新判据调用 命中", s2.count("if not check_v12338_backfeed():"))
print("[check] SRC 已切           ", 'SRC = HERE / "元DGTF-V1.23.38.py"' in s2)

# ── AST 解析（关键：转义是否落盘正确）────────────────────────────
try:
    ast.parse(s2)
    print("[ok] 施加后 AST OK（转义落盘正确）")
except SyntaxError as e:
    print("[FAIL] AST 失败：%s (line %s)" % (e, e.lineno))
    # 打印出问题那几行，便于定位
    _ls = s2.split("\n")
    _i = max(0, (e.lineno or 1) - 4)
    for _k in range(_i, min(len(_ls), (e.lineno or 1) + 3)):
        print("   %4d | %s" % (_k + 1, _ls[_k]))
    raise SystemExit(1)

# ── CRLF 往返模拟 ──
out = s2.replace("\n", "\r\n").encode("utf-8")
print("[check] 写出后 \\r\\r\\n 计数 =", out.count(b"\r\r\n"))
print("[check] 写出后 纯CRLF =", out.count(b"\n") == out.count(b"\r\n"))
print("[ok] dry-run 全过（未写任何真实文件）")
