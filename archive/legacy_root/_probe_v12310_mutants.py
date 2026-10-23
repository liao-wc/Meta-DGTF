# -*- coding: utf-8 -*-
"""v1.23.10 变异体：证明 check_v12310_render_ops 有判别力（四项各一个）。

做法照技能 7c：读 smoke_test.py 源码 → 只替换 SRC 那一行 → exec 成独立 module
（`hm.mod` 就是那份**畸形引擎**）→ 让**原样的判据函数**去跑，**必须判红**。

M1 声明不插    ：_with_form_declaration 直接返回 body
M2 附录不外置  ：_appendix_to_file 直接返回 text
M3 成本档恒 quality：_auto_profile 恒返回 quality
M4 未校验留痕关 ：R10 的条件恒 False
"""
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.10.py"
SMOKE = HERE / "smoke_test.py"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')

MUTS = {
    "M1_声明不插": (
        '    _decl = (f"\\n> **形态声明**：本次落地层用 **{template}** 模板 —— {why}。\\n"',
        '    return body\n    _decl = (f"\\n> **形态声明**：本次落地层用 **{template}** 模板 —— {why}。\\n"'),
    "M2_附录不外置": (
        '    _m = _APPENDIX_JSON_RE.search(text)\n    if not _m:\n        return text\n',
        '    return text\n    _m = _APPENDIX_JSON_RE.search(text)\n    if not _m:\n        return text\n'),
    "M3_成本档恒quality": (
        '    return "economy" if not _has_decision_context(question) else "balanced"',
        '    return "quality"'),
    "M4_未校验留痕关": (
        "                if not _has_decision_context(\n",
        "                if False and not _has_decision_context(\n"),
}


def build_mutant(tag, old, new):
    txt = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
    n = txt.count(old)
    assert n == 1, f"[{tag}] 变异锚点命中 {n} 次（要求 1）"
    p = HERE / f"_mut_v12310_{tag}.py"
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
    r = hm.check_v12310_render_ops()
    print(f"[control 未变异] -> {r}（要求 True）")
    ok &= (r is True)
    # 顺带：改过的 v67 判据在干净版上必须判绿
    r67 = hm.check_v67_full_appendix()
    print(f"[control v67 判据] -> {r67}（要求 True）")
    ok &= (r67 is True)

    for tag, (old, new) in MUTS.items():
        p = build_mutant(tag, old, new)
        hm = run_harness(p, tag)
        try:
            r = hm.check_v12310_render_ops()
        except Exception as e:  # noqa: BLE001
            print(f"[{tag}] -> 抛异常（也算判红）: {type(e).__name__}: {e}")
            r = False
        print(f"[{tag}] -> {r}（要求 False）")
        ok &= (r is False)

    # 变异体也要能打穿 v67（M2 打的就是它的取源）
    hm = run_harness(HERE / "_mut_v12310_M2_附录不外置.py", "v67_on_M2")
    try:
        r67b = hm.check_v67_full_appendix()
    except Exception as e:  # noqa: BLE001
        print(f"[M2 × v67] -> 抛异常：{type(e).__name__}: {e}")
        r67b = False
    print(f"[M2 × v67] -> {r67b}（要求 True：不外置 = 内联，仍是旧行为）")

    print("MUTANTS", "ALL-OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
