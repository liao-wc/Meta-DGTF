# -*- coding: utf-8 -*-
"""flags schema 判据（Round 129，零成本）。

F1 动态 flag 归一：`probe_link_dangling(3)` → `probe_link_dangling`
F2 去重且保持首次出现顺序
F3 普通 flag 原样保留；空输入 → []
"""
from dgtf_v2.quality_predictor import classify_flags, normalize_flags

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


def main() -> int:
    ck("F1 动态 flag 归一",
       normalize_flags(["probe_link_dangling(3)", "too_many_amp_candidates(70%)",
                        "duty_short"]) ==
       ["probe_link_dangling", "too_many_amp_candidates", "duty_short"],
       normalize_flags(["probe_link_dangling(3)", "too_many_amp_candidates(70%)",
                        "duty_short"]))
    ck("F2 去重且保序",
       normalize_flags(["duty_short", "duty_short(2)", "duty_short"]) == ["duty_short"],
       normalize_flags(["duty_short", "duty_short(2)", "duty_short"]))
    _cls = classify_flags(["duty_short", "probe_no_target_covered(2)",
                           "polarity_all_same_structural(1)"])
    ck("F4 flags 三分类（process/coverage/other）",
       _cls["process"] == ["duty_short"]
       and _cls["coverage"] == ["probe_no_target_covered"]
       and _cls["other"] == ["polarity_all_same_structural"], _cls)
    ck("F3 普通/空输入",
       normalize_flags([]) == []
       and normalize_flags(["all_closure_unavailable"]) == ["all_closure_unavailable"]
       and normalize_flags(None) == [])
    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
