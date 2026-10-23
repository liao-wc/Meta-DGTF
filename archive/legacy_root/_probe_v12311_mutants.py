# -*- coding: utf-8 -*-
"""v1.23.11 变异体：证明 check_v12311_writeback_and_web 有判别力。

M1 自省不回写  ：_append_self_check_writeback 直接返回 body
M2 事实题不联网：_web_auto_for_facts 恒返回 False
"""
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.11.py"
SMOKE = HERE / "smoke_test.py"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')

MUTS = {
    "M1_自省不回写": (
        "    if not _items:\n        return body\n",
        "    return body\n    if not _items:\n        return body\n"),
    "M2_事实题不联网": (
        "    return not _has_decision_context(question)\n",
        "    return False\n"),
}


def build_mutant(tag, old, new):
    txt = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
    n = txt.count(old)
    assert n == 1, f"[{tag}] 变异锚点命中 {n} 次（要求 1）"
    p = HERE / f"_mut_v12311_{tag}.py"
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
    r = hm.check_v12311_writeback_and_web()
    print(f"[control 未变异] -> {r}（要求 True）")
    ok &= (r is True)

    for tag, (old, new) in MUTS.items():
        p = build_mutant(tag, old, new)
        hm = run_harness(p, tag)
        try:
            r = hm.check_v12311_writeback_and_web()
        except Exception as e:  # noqa: BLE001
            print(f"[{tag}] -> 抛异常（也算判红）: {type(e).__name__}: {e}")
            r = False
        print(f"[{tag}] -> {r}（要求 False）")
        ok &= (r is False)

    print("MUTANTS", "ALL-OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
