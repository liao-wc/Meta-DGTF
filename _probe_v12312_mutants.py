# -*- coding: utf-8 -*-
"""v1.23.12 变异体：证明 check_v12312_anchor_lanes 有判别力。

M1 丢联网通道   ：`_anchor_lane_lines` 在 web 段之前就 return（只剩文本通道）
M2 联网恒报关   ：把「开」分支改成永不可达（`elif not _w["enabled"]` → `elif True`）
M3 错误数清零   ：`_web_lane_stats` 不读 web_errors（失败恒 0 条）
M4 落地层漏接   ：只删 decision 模板那一处调用（boundary 保留）
M5 头部漏接     ：删掉 save_result 头部那处调用\nM6 锚点明细被吃掉：把锚点明细整段关掉（elif False）
"""
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.12.py"
SMOKE = HERE / "smoke_test.py"
SRC_RE = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.\d+\.py"')

SEC_LOOP = ('    for _al in _anchor_lane_lines(res):\n'
            '        out.append(f"- {_al}\\n")\n')

MUTS = {
    "M1_丢联网通道": (
        "    _w = _web_lane_stats(res)\n",
        "    return out\n    _w = _web_lane_stats(res)\n",
    ),
    "M2_联网恒报关": (
        '    elif not _w["enabled"]:\n',
        "    elif True:\n",
    ),
    "M3_错误数清零": (
        '        for _e in (_p.get("web_errors") or []):\n',
        "        for _e in ([]):\n",
    ),
    "M4_落地层漏接": (SEC_LOOP, "\n", 2, 1),      # 出现 2 次，只改第 1 处
    "M6_锚点明细被吃掉": (
        '            elif isinstance(_ea, dict):\n',
        "            elif False:\n",
    ),
    "M5_头部漏接": (
        "            for _al in _anchor_lane_lines(result):\n"
        '                f.write(_al + "\\n\\n")\n',
        "            pass\n",
    ),
}


def build_mutant(tag, mut):
    old, new = mut[0], mut[1]
    want = mut[2] if len(mut) > 2 else 1
    txt = SRC.read_bytes().decode("utf-8").replace("\r\n", "\n")
    n = txt.count(old)
    assert n == want, f"[{tag}] 变异锚点命中 {n} 次（要求 {want}）"
    idx = mut[3] if len(mut) > 3 else 1
    if idx == 1:
        txt = txt.replace(old, new, 1)
    else:
        head = txt.split(old)
        txt = old.join(head[:idx]) + new + old.join(head[idx:])
    p = HERE / f"_mut_v12312_{tag}.py"
    p.write_bytes(txt.replace("\n", "\r\n").encode("utf-8"))
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
    r = hm.check_v12312_anchor_lanes()
    print(f"[control 未变异] -> {r}（要求 True）")
    ok &= (r is True)

    for tag, mut in MUTS.items():
        p = build_mutant(tag, mut)
        hm = run_harness(p, tag)
        try:
            r = hm.check_v12312_anchor_lanes()
        except Exception as e:  # noqa: BLE001
            print(f"[{tag}] -> 抛异常（也算判红）: {type(e).__name__}: {e}")
            r = False
        print(f"[{tag}] -> {r}（要求 False）")
        ok &= (r is False)

    print("MUTANTS", "ALL-OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
