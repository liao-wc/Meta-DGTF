# -*- coding: utf-8 -*-
"""验证语义 / 展示门 / 告警分级判据（Round 132）。"""
from dgtf_v2.quality_predictor import (alert_levels, display_gate,
                                       verification_semantics)

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


def main() -> int:
    fact_ok = verification_semantics("fact", "verified", True, True, True)
    fact_bad = verification_semantics("fact", "needs_evidence", False, False, True)
    proc = verification_semantics("reasoning", "verified", True, False, True)
    ck("S1 事实题 correctness=True / process=False",
       fact_ok["answer_correctness_verified"] and not fact_ok["process_contract_verified"]
       and fact_ok["evidence_basis"] == "official_evidence", fact_ok)
    ck("S2 非事实题 process=True / correctness=False",
       proc["process_contract_verified"] and not proc["answer_correctness_verified"]
       and proc["evidence_basis"] == "process_contract", proc)
    ck("S3 needs_evidence 两者皆 False",
       not fact_bad["answer_correctness_verified"]
       and not fact_bad["process_contract_verified"]
       and fact_bad["evidence_basis"] == "none", fact_bad)

    ck("D1 事实 verified 无 display ⇒ ready=False 理由",
       display_gate("fact", "verified", "")[0] is False)
    ck("D2 事实 verified 有 display ⇒ 不拦截",
       display_gate("fact", "verified", "32024亿美元")[0] is None)
    ck("D3 非事实题 display 门不适用",
       display_gate("reasoning", "verified", "")[0] is None)

    al = alert_levels(["duty_short", "probe_no_target_covered(2)", "core_audit_gaps"])
    ck("A1 告警分级 block/warn/info（Round 142 校准）",
       al["block"] == ["core_audit_gaps"]
       and al["warn"] == []
       and set(al["info"]) == {"duty_short", "probe_no_target_covered"}
       and al["max_level"] == "block", al)
    ck("A2 无告警 max_level=none", alert_levels([])["max_level"] == "none")
    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
