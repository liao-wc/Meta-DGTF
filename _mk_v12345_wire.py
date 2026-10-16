# -*- coding: utf-8 -*-
"""v1.23.45：插 P-4 判据 + 切两处 SRC + 加 M96 + 登记 output_repetition + 接 runner。"""
import ast
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"
MUT = HERE / "_mut_v12332.py"
ENG = HERE / "元DGTF-V1.23.45.py"


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


snippet = (Path("_v12345_judge_snippet.py").read_bytes().decode("utf-8")
           .replace("\r\n", "\n").rstrip() + "\n\n\n")


def _sm(s):
    a = "def check_v12344_eml_adaptive():"
    assert s.count(a) == 1
    s = s.replace(a, snippet + a, 1)
    c = "    if not check_v12344_eml_adaptive():\n        return 1\n"
    assert s.count(c) == 1
    s = s.replace(c, c + "    if not check_v12345_output_rep():\n"
                        "        return 1\n", 1)
    s = s.replace('SRC = HERE / "元DGTF-V1.23.44.py"',
                  'SRC = HERE / "元DGTF-V1.23.45.py"')
    return s


def _mut(s):
    s = s.replace('SRC = HERE / "元DGTF-V1.23.44.py"',
                  'SRC = HERE / "元DGTF-V1.23.45.py"')
    new = ('    ("M96 输出内复读率恒 0（盲区又回去了）",\n'
           "     '    return round(1.0 - len(set(_g)) / float(len(_g)), 4)',\n"
           "     '    return 0.0'),\n")
    lines = s.split("\n")
    idx = max(i for i, l in enumerate(lines) if l == "]")
    lines[idx:idx] = new.rstrip("\n").split("\n")
    s = "\n".join(lines)
    c = '             "st.check_v12344_eml_adaptive() and "\n'
    assert s.count(c) == 1
    s = s.replace(c, c + '             "st.check_v12345_output_rep() and "\n', 1)
    assert 'SRC = HERE / "元DGTF-V1.23.45.py"' in s
    return s


if __name__ == "__main__":
    _rw(SM, _sm)
    print("[ok] smoke：判据已插 + SRC→V1.23.45")
    _rw(MUT, _mut)
    print("[ok] _mut：SRC→V1.23.45 + M96 + runner 已接")
    p = HERE / "_v122_ast_registry.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["registry"].setdefault("output_repetition", {
        "phase": "45",
        "reason": "P-4 输出内逐字复读率（补集合式 n-gram 信号对输出内复读的结构盲）"})
    d["n_symbols_current"] = int(d["n_symbols_current"]) + 1
    d["current"] = "元DGTF-V1.23.45.py"
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[ok] registry:", len(d["registry"]), "条")
    eng = ENG.read_bytes().decode("utf-8").replace("\r\n", "\n")
    spec = importlib.util.spec_from_file_location("mm", str(MUT))
    m = importlib.util.module_from_spec(spec)
    sys.modules["mm"] = m
    spec.loader.exec_module(m)
    print("[ok] MUTS 总数:", len(m.MUTS))
    for nm, old, nw in m.MUTS:
        if nm.startswith("M96"):
            h = eng.count(old)
            mut = eng.replace(old, nw, 1)
            try:
                ast.parse(mut)
                aok = "OK"
            except SyntaxError as e:
                aok = "ERR %s" % e
            print("  %s | 命中 %d | 变异后 %s" % (nm[:30], h, aok))
