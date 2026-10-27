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





def _pareto_quality(flags):
    from dgtf_v2.pareto_flow import extract_flow_metrics
    pack = {"quality": {"answer_ready": True, "answer_quality": "verified",
                        "coverage": 1.0, "flags": flags},
            "decision_trace": {"answer_ready": True,
                               "answer_quality": "verified"},
            "process_ledger": {"standard_all": True},
            "llm_tokens": 100, "llm_calls": 10}
    return extract_flow_metrics(pack)["quality"]

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
    _q_proc = _pareto_quality(["duty_short"])
    _q_none = _pareto_quality([])
    _q_cov = _pareto_quality(["probe_no_target_covered"])
    ck("F5 pareto：process flag 不扣质量分",
       abs(_q_proc - _q_none) < 1e-9 and _q_cov < _q_none,
       (_q_proc, _q_none, _q_cov))
    ck("F3 普通/空输入",
       normalize_flags([]) == []
       and normalize_flags(["all_closure_unavailable"]) == ["all_closure_unavailable"]
       and normalize_flags(None) == [])
    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
