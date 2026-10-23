# -*- coding: utf-8 -*-
"""小补丁：autotune_score 出口补 `t`（autotune_progress 按时间排序要用）。"""
from pathlib import Path

SRC = Path("元DGTF-V1.23.33.py")


def load_crlf(p):
    t = p.read_bytes().decode("utf-8")
    assert t.count("\n") == t.count("\r\n"), "非纯 CRLF"
    return t.replace("\r\n", "\n")


def save_crlf(p, t):
    assert "\r" not in t.replace("\r\n", "")
    out = t.replace("\r\n", "\n").replace("\n", "\r\n")
    assert out.count("\r\r\n") == 0
    p.write_bytes(out.encode("utf-8"))


t = load_crlf(SRC)

A = '''    return {
        "quality": quality, "q_basis": basis,
        "cost": _at_num((ep.get("cost") or {}).get("tokens")),
'''
R = '''    return {
        "quality": quality, "q_basis": basis,
        # ★ 时间戳出口：`autotune_progress` 要按 t 排序判「趋势」。
        "t": _at_num(ep.get("t"), 0.0),
        "cost": _at_num((ep.get("cost") or {}).get("tokens")),
'''

n = t.count(A)
assert n == 1, "锚点命中 %d" % n
t = t.replace(A, R, 1)
save_crlf(SRC, t)
print("OK: autotune_score 补 t 出口")
