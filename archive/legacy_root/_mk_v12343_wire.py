# -*- coding: utf-8 -*-
"""v1.23.43：插 P-2 判据 + 切两处 SRC + 加 M94 + 登记 2 符号 + 接 runner。"""
import ast
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"
MUT = HERE / "_mut_v12332.py"
ENG = HERE / "元DGTF-V1.23.43.py"


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
    return chk.decode("utf-8")


snippet = (Path("_v12343_judge_snippet.py").read_bytes().decode("utf-8")
           .replace("\r\n", "\n").rstrip() + "\n\n\n")


def _sm(s):
    a = "def check_v12342_ctx_shape():"
    assert s.count(a) == 1
    s = s.replace(a, snippet + a, 1)
    c = "    if not check_v12342_ctx_shape():\n        return 1\n"
    assert s.count(c) == 1
    s = s.replace(c, c + "    if not check_v12343_gain_stop():\n"
                        "        return 1\n", 1)
    s = s.replace('SRC = HERE / "元DGTF-V1.23.42.py"',
                  'SRC = HERE / "元DGTF-V1.23.43.py"')
    return s


def _mut(s):
    s = s.replace('SRC = HERE / "元DGTF-V1.23.42.py"',
                  'SRC = HERE / "元DGTF-V1.23.43.py"')
    new = ('    ("M94 单标量早停失效（增益恒不命中）",\n'
           "     '    if _gf <= 0:\\n        return False, \"\"',\n"
           "     '    if True:\\n        return False, \"\"'),\n")
    lines = s.split("\n")
    idx = max(i for i, l in enumerate(lines) if l == "]")
    lines[idx:idx] = new.rstrip("\n").split("\n")
    s = "\n".join(lines)
    c = '             "st.check_v12342_ctx_shape() and "\n'
    assert s.count(c) == 1
    s = s.replace(c, c + '             "st.check_v12343_gain_stop() and "\n', 1)
    assert 'SRC = HERE / "元DGTF-V1.23.43.py"' in s
    return s


if __name__ == "__main__":
    _rw(SM, _sm)
    print("[ok] smoke：判据已插 + SRC→V1.23.43")
    _rw(MUT, _mut)
    print("[ok] _mut：SRC→V1.23.43 + M94 + runner 已接")
    # 登记 2 符号
    p = HERE / "_v122_ast_registry.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    for nm, rsn in (("refinement_gain",
                     "P-2 早停的单标量增益（各层目标读数的逐圈增量，方向统一）"),
                    ("layer_gain_stop_signal",
                     "P-2 早停判据：gain_floor>0 时连续 N 圈增益趋零 ⇒ 停")):
        d["registry"].setdefault(nm, {"phase": "43", "reason": rsn})
    d["n_symbols_current"] = int(d["n_symbols_current"]) + 2
    d["current"] = "元DGTF-V1.23.43.py"
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[ok] registry:", len(d["registry"]), "条 | n_symbols_current", d["n_symbols_current"])
    # 校验 M94
    eng = ENG.read_bytes().decode("utf-8").replace("\r\n", "\n")
    spec = importlib.util.spec_from_file_location("mm", str(MUT))
    m = importlib.util.module_from_spec(spec)
    sys.modules["mm"] = m
    spec.loader.exec_module(m)
    print("[ok] MUTS 总数:", len(m.MUTS))
    for nm, old, nw in m.MUTS:
        if nm.startswith("M94"):
            h = eng.count(old)
            mut = eng.replace(old, nw, 1)
            try:
                ast.parse(mut)
                aok = "OK"
            except SyntaxError as e:
                aok = "ERR %s" % e
            print("  %s | 命中 %d | 变异后 %s" % (nm[:30], h, aok))
