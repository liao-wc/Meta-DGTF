# -*- coding: utf-8 -*-
"""v1.23.15 变异体：证明 check_v12315_history_calibration 有判别力。

M1 不分层         ：每桶上限失效（用总数上限）
M2 衰减失效       ：`_hist_weight` 恒返回 1.0
M3 三态抽取删掉   ：`_hist_from_md` 不抽三态一致率
M4 联网抽取删掉   ：`_hist_from_md` 不抽联网行
M5 缺字段写 0     ：联网行缺失时写 `web_hit/web_fail = 0`
M6 成本档退回 0.5 ：一致率门槛写死 0.5（拍脑袋那条）
M7 截断率门槛去掉 ：不要求层样本量
"""
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.15.py"
SMOKE = HERE / "smoke_test.py"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')

MUTS = {
    "M1_不分层": (
        '        if _q and _has_decision_context(_q):\n'
        '            if _cnt["nf"] < _lim:\n',
        '        if _q and _has_decision_context(_q):\n'
        '            if _acc_all["n"] < _lim:\n',
    ),
    "M2_衰减失效": (
        '    if not half_life or not mtime:\n        return 1.0\n',
        '    return 1.0\n    if not half_life or not mtime:\n        return 1.0\n',
    ),
    "M3_三态抽取删掉": (
        '    _mt = _HIST_RE_TRI.search(head)\n',
        '    _mt = None\n',
    ),
    "M4_联网抽取删掉": (
        '    _mw = _HIST_RE_WEB.search(head)\n',
        '    _mw = None\n',
    ),
    "M5_缺字段写0": (
        '        if _fa:\n            rec[\"web_fail\"] = int(_fa.group(1))\n    return rec\n',
        '        if _fa:\n            rec[\"web_fail\"] = int(_fa.group(1))\n'
        '    rec.setdefault(\"web_hit\", 0)\n'
        '    rec.setdefault(\"web_fail\", 0)\n'
        '    return rec\n',
    ),
    "M6_成本档退回0.5": (
        '    if (_trn >= _AUTO_TRI_MIN_N and _tr is not None and _tr < _tri_floor\n',
        '    _tri_floor = 0.5\n'
        '    if (_trn >= _AUTO_TRI_MIN_N and _tr is not None and _tr < _tri_floor\n',
    ),
    "M7_截断率门槛去掉": (
        '    if _cr is not None and _sn >= _AUTO_STOP_MIN_N and _cr >= 0.5:\n',
        '    if _cr is not None and _cr >= 0.5:\n',
    ),
}


def build_mutant(tag, old, new):
    txt = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
    n = txt.count(old)
    assert n == 1, "[%s] 变异锚点命中 %d 次（要求 1）" % (tag, n)
    p = HERE / ("_mut_v12315_%s.py" % tag)
    p.write_bytes(txt.replace(old, new, 1).replace("\n", "\r\n").encode("utf-8"))
    return p


def run_harness(target, tag):
    src = SMOKE.read_text(encoding="utf-8")
    assert len(SRC_RE.findall(src)) == 1, "smoke SRC 行不是 1 行"
    src = SRC_RE.sub('SRC = Path(r"%s")' % str(target).replace("\\", "\\\\"),
                     src, count=1)
    hm = types.ModuleType("harness_" + tag)
    hm.__file__ = str(SMOKE)
    sys.modules[hm.__name__] = hm
    exec(compile(src, str(SMOKE), "exec"), hm.__dict__)
    return hm


def main():
    ok = True
    hm = run_harness(SRC, "clean")
    r = hm.check_v12315_history_calibration()
    print("[control 未变异] -> %s（要求 True）" % r)
    ok &= (r is True)
    for tag, (old, new) in MUTS.items():
        try:
            p = build_mutant(tag, old, new)
        except AssertionError as e:
            print("[%s] -> 锚点失效（判红）: %s" % (tag, e))
            ok = False
            continue
        hm = run_harness(p, tag)
        try:
            r = hm.check_v12315_history_calibration()
        except Exception as e:  # noqa: BLE001
            print("[%s] -> 抛异常（也算判红）: %s: %s"
                  % (tag, type(e).__name__, e))
            r = False
        print("[%s] -> %s（要求 False）" % (tag, r))
        ok &= (r is False)
    print("MUTANTS", "ALL-OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
