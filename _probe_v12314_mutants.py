# -*- coding: utf-8 -*-
"""v1.23.14 变异体：证明 check_v12314_history_corpus 有判别力。

M1 字段名读错     ：`rounds_run` → `rounds`（复现本版修掉的那个静默 bug）
M2 md 源不扫       ：`want_md` 恒 False
M3 跑批源不扫      ：`want_batch` 恒 False
M4 不按题型分桶    ：`_hist_for` 恒返回全语料
M5 忽视样本门槛    ：实际停圈只要 `>0` 就采用（单条噪声盖掉 200 份分布）
M6 成本档退回绝对阈值：`>= 400000`（拍脑袋那条）
M7 实际停圈不落产物：`_rounds_run_line` 恒返回 ""
"""
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.14.py"
SMOKE = HERE / "smoke_test.py"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')

MUTS = {
    "M1_字段名读错": (
        '        _rn = _v.get("rounds_run")\n',
        '        _rn = _v.get("rounds")\n',
    ),
    "M2_md源不扫": (
        "    if want_md:\n",
        "    if False:\n",
    ),
    "M3_跑批源不扫": (
        "    if want_batch:\n",
        "    if False:\n",
    ),
    "M4_不按题型分桶": (
        '    return _sub if int(_sub.get("n") or 0) > 0 else (hist or {})',
        "    return (hist or {})",
    ),
    "M5_忽视样本门槛": (
        "        if _a > 0 and int(_act_n.get(e) or 0) >= _AUTO_ACT_MIN:\n",
        "        if _a > 0:\n",
    ),
    "M6_成本档退回绝对阈值": (
        "    _exp = ((_tk75 and _tk >= _tk75) or (_cl75 and _cl >= _cl75))\n",
        "    _exp = (_tk >= 400000)\n",
    ),
    "M7_实际停圈不落产物": (
        'def _rounds_run_line(views) -> str:\n',
        'def _rounds_run_line(views) -> str:\n    return ""\n',
    ),
}


def build_mutant(tag, old, new):
    txt = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
    n = txt.count(old)
    assert n == 1, "[%s] 变异锚点命中 %d 次（要求 1）" % (tag, n)
    p = HERE / ("_mut_v12314_%s.py" % tag)
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
    r = hm.check_v12314_history_corpus()
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
            r = hm.check_v12314_history_corpus()
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
