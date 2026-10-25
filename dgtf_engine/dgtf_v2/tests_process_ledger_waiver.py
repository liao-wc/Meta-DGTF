# -*- coding: utf-8 -*-
"""Round 21 判据：过程门语义（审计修复不阻断 + 事实已证时元层张力豁免）。"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.process_ledger import build_ledger  # noqa: E402

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


def packed(meta_clean=True, fact_status="answered", official=("E1",),
           audit_bad=0, audit_rows=None, qtype="fact"):
    views = {
        "0": {"manifest": "l0 manifest text", "rounds_run": 2},
        "1": {"decidable_product": {"answer": "l1 answer text"},
              "rounds_run": 2,
              "decidability_audit": {"status": "verified" if not audit_bad
                                     else "mixed", "n": 2, "ok": 1,
                                     "bad": audit_bad,
                                     "rows": audit_rows or []}},
        "both": {"collision": "both collision text", "rounds_run": 2},
        "all": {"decision": "all decision text", "rounds_run": 2,
                "meta_closure": {"clean": meta_clean, "unsettled": 0 if meta_clean else 2}},
    }
    card = {"status": fact_status,
            "official_evidence_ids": list(official),
            "gaps": []}
    return {
        "question": "Q?", "route": ["0", "1", "both", "all"],
        "views": views, "pools": {},
        "fact_contract": {"layers": {e: {"ok": True}
                                     for e in ("0", "1", "both", "all")}},
        "decision_trace": {"question_type": qtype, "fact_card": card},
    }


def main():
    # ① 事实已证 + 元层张力 → all 层豁免，账本标注
    led = build_ledger(packed(meta_clean=False, fact_status="answered",
                              official=("E1",)))
    ck("① 事实已证时元层张力豁免 → standard_all=True",
       led["standard_all"] is True, led["layers"]["all"]["standard_ok"])
    ck("① 豁免在 notes 中可审计",
       led.get("notes", {}).get("closure_waived") is True
       and led.get("notes", {}).get("closure_unsettled") == 2,
       led.get("notes"))
    ck("① soul.standard_all 与顶层一致",
       led["soul"]["standard_all"] is True)

    # ② 事实卡无官方源 → 不豁免
    led2 = build_ledger(packed(meta_clean=False, fact_status="answered",
                               official=()))
    ck("② 无官方源不豁免 → standard_all=False",
       led2["standard_all"] is False)

    # ③ 事实卡 conflict → 不豁免
    led3 = build_ledger(packed(meta_clean=False, fact_status="conflict"))
    ck("③ conflict 不豁免 → standard_all=False",
       led3["standard_all"] is False)

    # ④ 非事实题 + 元层张力 → 不豁免
    led4 = build_ledger(packed(meta_clean=False, fact_status="answered",
                               qtype="decision"))
    ck("④ 非事实题不豁免 → standard_all=False", led4["standard_all"] is False)

    # ⑤ 元层 clean → 正常 True，无豁免标记
    led5 = build_ledger(packed(meta_clean=True))
    ck("⑤ 元层 clean → standard_all=True 且无豁免标记",
       led5["standard_all"] is True and "closure_waived" not in led5["notes"])

    # ⑥ 审计「已修复行」不阻断
    repaired = [{"id": 1, "before": "undecidable", "after": "partial",
                 "issue": "undecidable_but_evidence_exists", "warning": ""}]
    led6 = build_ledger(packed(audit_bad=1, audit_rows=repaired))
    ck("⑥ 审计已修复行不阻断 layer1", led6["layers"]["1"]["standard_ok"] is True)

    # ⑦ 审计「未修复行」仍阻断
    unrepaired = [{"id": 1, "before": "partial", "after": "partial",
                   "issue": "undecidable_but_evidence_exists", "warning": ""}]
    led7 = build_ledger(packed(audit_bad=1, audit_rows=unrepaired))
    ck("⑦ 审计未修复行仍阻断 layer1", led7["layers"]["1"]["standard_ok"] is False)

    # ⑧ 确定性
    a = build_ledger(packed(meta_clean=False))
    b = build_ledger(packed(meta_clean=False))
    ck("⑧ 确定性：两次一致",
       a["standard_all"] == b["standard_all"]
       and a.get("notes") == b.get("notes"))

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
