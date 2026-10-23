# -*- coding: utf-8 -*-
"""v1.23.9 变异体：证明 check_v1239_orientation_guard 有判别力。

做法照技能 7c：读 smoke_test.py 源码 → 只替换 SRC 那一行 → exec 成独立 module
（`hm.mod` 就是那份**畸形引擎**）→ 让**原样的判据函数**去跑，**必须判红**。

M1 ctx 恒 True   ：事实题也走 decision
M2 ctx 恒 False  ：决策题也走 boundary
M3 删 auto 短路  ：事实题回到 decision
M4 短路条件放宽  ：连显式 `decision` 也被改写成 boundary（覆盖用户选择）
"""
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.9.py"
SMOKE = HERE / "smoke_test.py"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')

_CTX_BODY = ('    _q = str(question or "")\n'
             "    if not _q.strip():\n"
             "        return False\n"
             "    return any(_c in _q for _c in _DECISION_CUES)\n")

MUTS = {
    "M1_ctx恒True": (_CTX_BODY, "    return True\n"),
    "M2_ctx恒False": ("    return any(_c in _q for _c in _DECISION_CUES)\n",
                      "    return False\n"),
    "M3_删auto短路": (
        '    if orientation == "auto" and not _has_decision_context(\n'
        '            str(res.get("question") or "")):\n'
        "        return _render_landing_boundary(res)\n",
        "    if False:\n        return _render_landing_boundary(res)\n"),
    "M4_短路放宽到decision": (
        '    if orientation == "auto" and not _has_decision_context(\n',
        '    if orientation in ("auto", "decision") and not _has_decision_context(\n'),
}


def build_mutant(tag, old, new):
    txt = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
    n = txt.count(old)
    assert n == 1, f"[{tag}] 变异锚点命中 {n} 次（要求 1）"
    p = HERE / f"_mut_v1239_{tag}.py"
    p.write_bytes(txt.replace(old, new, 1).encode("utf-8"))
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
    r = hm.check_v1239_orientation_guard()
    print(f"[control 未变异] -> {r}（要求 True）")
    ok &= (r is True)

    for tag, (old, new) in MUTS.items():
        p = build_mutant(tag, old, new)
        hm = run_harness(p, tag)
        try:
            r = hm.check_v1239_orientation_guard()
        except Exception as e:  # noqa: BLE001
            print(f"[{tag}] -> 抛异常（也算判红）: {type(e).__name__}: {e}")
            r = False
        print(f"[{tag}] -> {r}（要求 False）")
        ok &= (r is False)

    print("MUTANTS", "ALL-OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
