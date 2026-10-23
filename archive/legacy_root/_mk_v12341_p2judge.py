# -*- coding: utf-8 -*-
"""把 P2 判据插入 smoke_test.py 并接调用。"""
import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"
SNIP = HERE / "_v12341_judge_snippet2.py"


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    path.write_bytes(s2.replace("\n", "\r\n").encode("utf-8"))
    chk = path.read_bytes()
    assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
    ast.parse(chk.decode("utf-8"))
    return chk


snippet = SNIP.read_bytes().decode("utf-8").replace("\r\n", "\n").rstrip() + "\n\n\n"


def apply(s):
    anchor = "def check_v12341_goal_fresh():"
    assert s.count(anchor) == 1
    s = s.replace(anchor, snippet + anchor, 1)
    c = ("    if not check_v12341_goal_fresh():\n"
         "        return 1\n")
    assert s.count(c) == 1
    s = s.replace(c, c + "    if not check_v12341_excavate_dir():\n"
                        "        return 1\n", 1)
    assert s.count("def check_v12341_excavate_dir(") == 1
    assert s.count("if not check_v12341_excavate_dir():") == 1
    return s


if __name__ == "__main__":
    out = _rw(SM, apply)
    print("[ok] P2 判据已插入 | 行数", out.count(b"\n"))
