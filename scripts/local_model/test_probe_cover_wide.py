# -*- coding: utf-8 -*-
"""probe 覆盖判据「词面近义 AND 兜底」判据（Round 126，零成本）。

W1 常量存在：_COVERS_SIM_WIDE=0.25 / _COV_OVERLAP_WIDE=0.30
W2 同义样例命中（待岗轮岗现金表 / RFC 9110 501-500）
W3 无关样例不命中（海水为什么咸 vs 春节放假4天）——防误报负对照
W4 完全相同的文本仍命中（严尺子行为保留）
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


def load_engine():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "dgtf_engine"))
    spec = importlib.util.spec_from_file_location(
        "engine_probe_wide_test",
        str(ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
            / "Meta-DGTF-V2.2.3.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["engine_probe_wide_test"] = m
    spec.loader.exec_module(m)
    return m


def main() -> int:
    m = load_engine()
    f = getattr(m, "_probe_covers_target", None)
    ck("W1 常量与纯函数存在",
       f is not None
       and abs(float(m._COVERS_SIM_WIDE) - 0.25) < 1e-9
       and abs(float(m._COV_OVERLAP_WIDE) - 0.30) < 1e-9,
       (bool(f), getattr(m, "_COVERS_SIM_WIDE", None),
        getattr(m, "_COV_OVERLAP_WIDE", None)))
    if f is None:
        print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
        return 1

    ck("W2a 同义样例：待岗轮岗现金表",
       f("把待岗轮岗的月摊薄流出与裁员的归零流出并到同一张月度现金表上",
         "待岗、轮岗、缩短工时这条路没算过现金效果：它们把人工流出按月摊薄，"
         "而不是一次性归零"))
    ck("W2b 同义样例：RFC 9110 501/500",
       f("核 RFC 9110 §15.1 默认可缓存集合：501 在内、500 不在",
         "RFC 9110 §15.1 的默认可缓存集合里有 501，没有 500"))
    ck("W3 负对照：无关文本不命中",
       not f("为什么海水是咸的？",
             "（二）春节，放假4天（农历除夕、正月初一至初三）"))
    ck("W4 相同文本命中（严尺子保留）",
       f("站台网格实测的局部密度与平均值之差", "站台网格实测的局部密度与平均值之差"))

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
