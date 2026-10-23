# -*- coding: utf-8 -*-
"""v1.23.8 变异体：证明 check_v1238_render_guards 有判别力。

做法照技能 7c：读 smoke_test.py 源码 → 只替换 SRC 那一行 → exec 成独立 module
（`hm.mod` 就是那份**畸形引擎**）→ 让**原样的判据函数**去跑，**必须判红**。

M1 空节复活：把「三」节的 else 内容换成 pass
M2 停因恒空：_stop_kind_summary 开头直接 return ""
M3 去重失效：删掉去重分支的 continue
"""
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.8.py"
SMOKE = HERE / "smoke_test.py"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')

MUTS = {
    "M1_空节复活": (
        '        out.append("（本节无内容：没有「缺时限」的行动，"\n'
        '                   "因此没有待补的现场量测项）\\n")\n',
        "        pass\n"),
    "M2_停因恒空": (
        "    if not isinstance(views, dict) or not views:\n"
        '        return ""\n'
        "    _nat = _cut = _none = 0\n",
        '    return ""\n'
        "    _nat = _cut = _none = 0\n"),
    "M3_去重失效": (
        "            _dup += 1\n            continue\n",
        "            _dup += 1\n"),
}


def build_mutant(tag, old, new):
    txt = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
    n = txt.count(old)
    assert n == 1, f"[{tag}] 变异锚点命中 {n} 次（要求 1）"
    p = HERE / f"_mut_v1238_{tag}.py"
    p.write_bytes(txt.replace(old, new, 1).encode("utf-8"))
    return p


def run_harness(target, tag):
    src = SMOKE.read_text(encoding="utf-8")
    m = SRC_RE.findall(src)
    assert len(m) == 1, "smoke SRC 行不是 1 行"
    src = SRC_RE.sub('SRC = Path(r"%s")' % str(target).replace("\\", "\\\\"),
                     src, count=1)
    hm = types.ModuleType("harness_" + tag)
    hm.__file__ = str(SMOKE)
    sys.modules[hm.__name__] = hm
    exec(compile(src, str(SMOKE), "exec"), hm.__dict__)
    return hm


def main():
    ok = True

    # 0) 未变异对照：判据必须判绿（否则判据本身坏了）
    hm = run_harness(SRC, "clean")
    r = hm.check_v1238_render_guards()
    print(f"[control 未变异] -> {r}（要求 True）")
    ok &= (r is True)

    # 1) 三个变异体：判据必须判红
    for tag, (old, new) in MUTS.items():
        p = build_mutant(tag, old, new)
        hm = run_harness(p, tag)
        try:
            r = hm.check_v1238_render_guards()
        except Exception as e:
            print(f"[{tag}] -> 抛异常（也算判红）: {type(e).__name__}: {e}")
            r = False
        print(f"[{tag}] -> {r}（要求 False）")
        ok &= (r is False)

    print("MUTANTS", "ALL-OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
