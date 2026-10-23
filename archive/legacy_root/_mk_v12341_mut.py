# -*- coding: utf-8 -*-
"""v1.23.41：加变异体 M89~M92（P1~P4 各一条）。"""
import ast
import importlib.util
import sys
from pathlib import Path

MUT = Path("_mut_v12332.py")
ENG = Path("元DGTF-V1.23.41.py")

NEW_MUTS = '''    ("M89 目标读数收尾不刷新（crystallize 恒层停止那刻的旧值）",
     '_fresh = layer_goal_readings({str(entry): _vd_f}).get(str(entry)) or {}',
     '_fresh = {}'),
    ("M90 excavate 显示丢方向提示（易被误读成没挖）",
     '_LG_HINT.get(_gk_f, "")',
     '""'),
    ("M91 截断不附近阈读数（不可判离触发多远）",
     'f"  近阈读数：{_near}")',
     'f"（略）")'),
    ("M92 自省未消化不附点名（不知是哪批）",
     'if "自省连续" in _sr4 and "未消化点名" not in _sr4:',
     'if False:'),
'''


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


def apply(s):
    # 在 MUTS 的收尾 `]` 前插入（取**最后**一个顶层行首 `]`）
    lines = s.split("\n")
    idx = max(i for i, l in enumerate(lines) if l == "]")
    block = NEW_MUTS.rstrip("\n").split("\n")
    lines[idx:idx] = block
    s2 = "\n".join(lines)
    assert s2.count("M89 目标读数收尾不刷新") == 1
    assert s2.count("M92 自省未消化不附点名") == 1
    return s2


if __name__ == "__main__":
    out = _rw(MUT, apply)
    # 校验 4 条有效
    eng = ENG.read_bytes().decode("utf-8").replace("\r\n", "\n")
    spec = importlib.util.spec_from_file_location("mm", str(MUT))
    m = importlib.util.module_from_spec(spec)
    sys.modules["mm"] = m
    spec.loader.exec_module(m)
    names = [x[0] for x in m.MUTS]
    print("[ok] MUTS 总数:", len(names))
    dup = [n for n in ("M89", "M90", "M91", "M92") if sum(
        1 for x in names if x.startswith(n)) != 1]
    assert not dup, "重复/缺失: %r" % dup
    for nm, old, new in m.MUTS:
        if nm[:3] in ("M89", "M90", "M91", "M92"):
            h = eng.count(old)
            mut = eng.replace(old, new, 1)
            try:
                ast.parse(mut)
                aok = "OK"
            except SyntaxError as e:
                aok = "ERR %s" % e
            print("  %s | 命中 %d | 变异后 %s" % (nm[:34], h, aok))
            assert h == 1 and aok == "OK", "无效变异体: %s" % nm
    print("[ok] M89~M92 全部有效")
