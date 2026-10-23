# -*- coding: utf-8 -*-
"""v1.23.44：插 P-3 判据 + 切两处 SRC + 加 M95 + 接 runner。"""
import ast
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"
MUT = HERE / "_mut_v12332.py"
ENG = HERE / "元DGTF-V1.23.44.py"


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    ast.parse(s2)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\n") == out.count(b"\r\n")
    path.write_bytes(out)
    return out.decode("utf-8")


snippet = (Path("_v12344_judge_snippet.py").read_bytes().decode("utf-8")
           .replace("\r\n", "\n").rstrip() + "\n\n\n")


def _sm(s):
    a = "def check_v12343_gain_stop():"
    assert s.count(a) == 1
    s = s.replace(a, snippet + a, 1)
    c = "    if not check_v12343_gain_stop():\n        return 1\n"
    assert s.count(c) == 1
    s = s.replace(c, c + "    if not check_v12344_eml_adaptive():\n"
                        "        return 1\n", 1)
    s = s.replace('SRC = HERE / "元DGTF-V1.23.43.py"',
                  'SRC = HERE / "元DGTF-V1.23.44.py"')
    return s


def _mut(s):
    s = s.replace('SRC = HERE / "元DGTF-V1.23.43.py"',
                  'SRC = HERE / "元DGTF-V1.23.44.py"')
    new = ('    ("M95 EML 冷启自适应失效（门槛不降）",\n'
           "     '            if len(playbook or []) < int(_EML_COLD_LIB):\\n"
           "                _eff_n = 1',\n"
           "     '            if False:\\n                _eff_n = 1'),\n")
    lines = s.split("\n")
    idx = max(i for i, l in enumerate(lines) if l == "]")
    lines[idx:idx] = new.rstrip("\n").split("\n")
    s = "\n".join(lines)
    c = '             "st.check_v12343_gain_stop() and "\n'
    assert s.count(c) == 1
    s = s.replace(c, c + '             "st.check_v12344_eml_adaptive() and "\n', 1)
    assert 'SRC = HERE / "元DGTF-V1.23.44.py"' in s
    return s


if __name__ == "__main__":
    _rw(SM, _sm)
    print("[ok] smoke：判据已插 + SRC→V1.23.44")
    _rw(MUT, _mut)
    print("[ok] _mut：SRC→V1.23.44 + M95 + runner 已接")
    eng = ENG.read_bytes().decode("utf-8").replace("\r\n", "\n")
    spec = importlib.util.spec_from_file_location("mm", str(MUT))
    m = importlib.util.module_from_spec(spec)
    sys.modules["mm"] = m
    spec.loader.exec_module(m)
    print("[ok] MUTS 总数:", len(m.MUTS))
    for nm, old, nw in m.MUTS:
        if nm.startswith("M95"):
            h = eng.count(old)
            mut = eng.replace(old, nw, 1)
            try:
                ast.parse(mut)
                aok = "OK"
            except SyntaxError as e:
                aok = "ERR %s" % e
            print("  %s | 命中 %d | 变异后 %s" % (nm[:30], h, aok))
