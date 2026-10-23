# -*- coding: utf-8 -*-
"""F3 · 1 层 AnswerSetPackage 判据。"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.layers_one import (AnswerSetPackage, assemble_answer_set,  # noqa: E402
                                LABELS)


def _rv(subs):
    return {"sub_questions": subs}


def case_full():
    p = assemble_answer_set(_rv([
        {"id": 1, "question": "q1", "decidability": "decidable",
         "answer": "a1", "citations": ["c1"]},
        {"id": 2, "question": "q2", "decidability": "partial",
         "answer": "a2", "citations": []},
    ]), {"coverage": 0.5})
    assert p.ok and not p.gaps, p.gaps
    assert p.coverage == 0.5
    assert p.contract_completeness == 1.0
    assert p.citations_ok
    assert p.no_actions
    assert p.tri_distribution.get("decidable") == 1


def case_decidable_no_citation():
    p = assemble_answer_set(_rv([
        {"id": 1, "question": "q", "decidability": "decidable", "answer": "a"}]), {})
    assert not p.ok and any("citations" in g for g in p.gaps), p.gaps
    assert not p.citations_ok


def case_actions_overreach():
    p = assemble_answer_set({"sub_questions": [
        {"id": 1, "question": "q", "decidability": "partial"}],
        "actions": [{"owner": "x"}]}, {})
    assert not p.ok and any("越权" in g for g in p.gaps), p.gaps
    assert not p.no_actions


def case_bad_label():
    p = assemble_answer_set(_rv([
        {"id": 1, "question": "q", "decidability": "maybe"}]), {})
    assert not p.ok and any("非法" in g for g in p.gaps), p.gaps
    assert p.contract_completeness == 0.0


def case_empty():
    p = assemble_answer_set({}, {})
    assert not p.ok and p.gaps
    assert p.contract_completeness == 0.0


def case_no_quality_coverage():
    p = assemble_answer_set(_rv([
        {"id": 1, "question": "q", "decidability": "undecidable"}]), {})
    assert p.coverage == 0.0
    assert p.ok


def case_citations_string():
    p = assemble_answer_set(_rv([
        {"id": 1, "question": "q", "decidability": "decidable",
         "answer": "a", "evidence": "e1"}]), {})
    assert p.ok and p.citations_ok


def case_to_dict_roundtrip():
    p = assemble_answer_set(_rv([
        {"id": 1, "question": "q", "decidability": "partial"}]), {})
    d = p.to_dict()
    assert set(d) >= {"answers", "coverage", "gaps", "ok"}
    assert json.loads(json.dumps(d, ensure_ascii=False))["ok"] is True


def case_decidable_product_fallback():
    p = assemble_answer_set({"question": "Q", "decidable_product": {
        "answer": "A", "evidence": ["E"]}}, {})
    assert p.ok and p.answers and p.answers[0]["label"] == "decidable"


def case_labels_are_three():
    assert LABELS == ("decidable", "partial", "undecidable")


CASES = [case_full, case_decidable_no_citation, case_actions_overreach,
         case_bad_label, case_empty, case_no_quality_coverage,
         case_citations_string, case_to_dict_roundtrip,
         case_decidable_product_fallback, case_labels_are_three]


def main():
    bad = []
    for fn in CASES:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception as e:  # noqa: BLE001
            bad.append((fn.__name__, e))
            print("FAIL", fn.__name__, type(e).__name__, e)
    print("\nPASS %d / FAIL %d" % (len(CASES) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
