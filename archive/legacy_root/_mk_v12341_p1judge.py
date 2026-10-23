# -*- coding: utf-8 -*-
"""把 P1 判据函数插入 smoke_test.py，并接进调用清单。"""
import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"
SNIP = HERE / "_v12341_judge_snippet.py"


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw, \
        "非纯 CRLF: %s" % path.name
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    out = s2.replace("\n", "\r\n").encode("utf-8")
    path.write_bytes(out)
    chk = path.read_bytes()
    assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
    ast.parse(chk.decode("utf-8"))
    return out


snippet = SNIP.read_bytes().decode("utf-8").replace("\r\n", "\n").rstrip() + "\n\n\n"


def apply(s):
    # ① 插函数：在 check_v12340_relax_force 定义前
    anchor = "def check_v12340_relax_force():"
    assert s.count(anchor) == 1, "函数锚点 %d" % s.count(anchor)
    s = s.replace(anchor, snippet + anchor, 1)
    # ② 接调用：在 backfeed_stage 调用之后
    c = ("    if not check_v12340_backfeed_stage():\n"
         "        return 1\n")
    assert s.count(c) == 1, "调用锚点 %d" % s.count(c)
    s = s.replace(c, c + "    if not check_v12341_goal_fresh():\n"
                        "        return 1\n", 1)
    # 自检
    assert s.count("def check_v12341_goal_fresh(") == 1
    assert s.count("if not check_v12341_goal_fresh():") == 1
    return s


if __name__ == "__main__":
    out = _rw(SM, apply)
    print("[ok] P1 判据已插入 smoke_test.py | 行数", out.count(b"\n"))
