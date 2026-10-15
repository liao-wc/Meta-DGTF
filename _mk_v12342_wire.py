# -*- coding: utf-8 -*-
"""v1.23.42：插 P-1 判据 + 切两处 SRC + 加变异体 M93 + 接进 runner。"""
import ast
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"
MUT = HERE / " _mut_v12332.py".strip()
ENG = HERE / "元DGTF-V1.23.42.py"


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw, \
        "非纯 CRLF %s" % path.name
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    path.write_bytes(s2.replace("\n", "\r\n").encode("utf-8"))
    chk = path.read_bytes()
    assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
    ast.parse(chk.decode("utf-8"))
    return chk.decode("utf-8")


snippet = (Path("_v12342_judge_snippet.py").read_bytes().decode("utf-8")
           .replace("\r\n", "\n").rstrip() + "\n\n\n")


def _sm(s):
    a = "def check_v12341_goal_fresh():"
    assert s.count(a) == 1
    s = s.replace(a, snippet + a, 1)
    c = "    if not check_v12341_attribution():\n        return 1\n"
    assert s.count(c) == 1
    s = s.replace(c, c + "    if not check_v12342_ctx_shape():\n"
                        "        return 1\n", 1)
    s = s.replace('SRC = HERE / "元DGTF-V1.23.41.py"',
                  'SRC = HERE / "元DGTF-V1.23.42.py"')
    assert s.count("def check_v12342_ctx_shape(") == 1
    assert 'SRC = HERE / "元DGTF-V1.23.42.py"' in s
    return s


def _mut(s):
    s = s.replace('SRC = HERE / "元DGTF-V1.23.41.py"',
                  'SRC = HERE / "元DGTF-V1.23.42.py"')
    assert 'SRC = HERE / "元DGTF-V1.23.42.py"' in s
    # 加 M93
    new = ('    ("M93 shape_of 窗口不生效（退回升全量渲染）",\n'
           "     '            return (_xs[-_lim:] if (_lim > 0 and len(_xs) > _lim)',\n"
           "     '            return (_xs'),\n")
    lines = s.split("\n")
    idx = max(i for i, l in enumerate(lines) if l == "]")
    lines[idx:idx] = new.rstrip("\n").split("\n")
    s = "\n".join(lines)
    # 接进 runner 判据清单
    c = '             "st.check_v12341_attribution() and "\n'
    assert s.count(c) == 1
    s = s.replace(c, c + '             "st.check_v12342_ctx_shape() and "\n', 1)
    assert s.count("M93 shape_of") == 1
    assert s.count("check_v12342_ctx_shape() and") == 1
    return s


if __name__ == "__main__":
    _rw(SM, _sm)
    print("[ok] smoke_test.py：判据已插 + SRC→V1.23.42")
    _rw(MUT, _mut)
    print("[ok] _mut_v12332.py：SRC→V1.23.42 + M93 + runner 已接")
    # 校验 M93
    eng = ENG.read_bytes().decode("utf-8").replace("\r\n", "\n")
    spec = importlib.util.spec_from_file_location("mm", str(MUT))
    m = importlib.util.module_from_spec(spec)
    sys.modules["mm"] = m
    spec.loader.exec_module(m)
    print("[ok] MUTS 总数:", len(m.MUTS))
    for nm, old, nw in m.MUTS:
        if nm.startswith("M93"):
            h = eng.count(old)
            mut = eng.replace(old, nw, 1)
            try:
                ast.parse(mut)
                aok = "OK"
            except SyntaxError as e:
                aok = "ERR %s" % e
            print("  %s | 命中 %d | 变异后 %s" % (nm[:30], h, aok))
            assert h == 1 and aok == "OK"
