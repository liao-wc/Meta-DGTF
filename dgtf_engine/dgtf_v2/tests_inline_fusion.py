# -*- coding: utf-8 -*-
"""V2.2.0 单引擎内联融合判据（12 项）。

不再依赖 dgtf_v2.history_fusion / behavior_fusion 外部模块；
直接加载 Meta-DGTF-V2.2.0.py，验证内联函数。
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "engine" / "Meta-DGTF-V2.2.0.py"


def _load():
    spec = importlib.util.spec_from_file_location("metadgtf_v220_inline", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["metadgtf_v220_inline"] = mod
    spec.loader.exec_module(mod)
    return mod


ENG = _load()


def case_axes_inline():
    assert len(ENG._HF_AXES) == 17
    assert ENG._HF_VERSION_COUNT >= 150
    assert all(a["status"] in ("native", "bridged") for a in ENG._HF_AXES)


def case_history_plan():
    p = ENG._hf_plan()
    assert p["target"] == "2.2.0"
    assert p["total_versions"] == ENG._HF_VERSION_COUNT
    assert p["readiness"] == 1.0 and p["continuity_ok"] is True
    assert len(p["axes"]) == 17


def case_behavior_arms():
    keys = {a["key"] for a in ENG._BEHAVIOR_ARMS}
    assert len(keys) == 5
    assert "fusion_full" in keys
    full = next(a for a in ENG._BEHAVIOR_ARMS if a["key"] == "fusion_full")
    assert set(full["caps"]) == {a["key"] for a in ENG._HF_AXES}


def _empty_stats():
    return {"schema": ENG._BEHAVIOR_SCHEMA, "arms": {}, "updated_at": ""}


def _choose(q):
    old = ENG._bf_load_stats
    ENG._bf_load_stats = lambda: _empty_stats()
    try:
        return ENG._bf_choose(q)
    finally:
        ENG._bf_load_stats = old


def case_fact_arm():
    a, m = _choose("GPT5 是什么时候发布的？")
    assert a["key"] == "v2_contract", (a, m)


def case_decision_arm():
    a, m = _choose("如何决定一个系统先优化哪一层？")
    assert a["key"] == "fusion_full", (a, m)


def case_open_arm():
    a, m = _choose("聊聊宇宙")
    assert a["key"] == "v1_spiral", (a, m)


def case_explicit_preserved():
    plan = {"_items": {"mode": {"source": "explicit"}, "rounds": {"source": "explicit"}}}
    before = json.dumps(plan, ensure_ascii=False, sort_keys=True)
    ENG.apply_behavior_fusion({}, "如何决定？", plan)
    assert json.dumps(plan, ensure_ascii=False, sort_keys=True) == before


def case_auto_changed():
    plan = {"_items": {k: {"source": "auto"} for k in
                       ("mode", "rounds", "stop", "thinking", "effort")}}
    s = ENG.apply_behavior_fusion({}, "如何决定？", plan)
    assert s["arm"] in ("fusion_full", "v2_contract", "v2_pareto"), s
    assert plan["_items"]["stop"].get("behavior_arm") is True
    assert s["behavior_changes"]


def case_metadata():
    cfg = {"actions": {"zero_v2": True}}
    s = ENG.apply_behavior_fusion(cfg, "如何决定？", {"_items": {}})
    assert cfg["_behavior_fusion"] is s
    assert s["capabilities_total"] == 17
    assert s["history_versions"] == ENG._HF_VERSION_COUNT


def case_audit_pack():
    s = ENG.apply_behavior_fusion({}, "如何决定？", {"_items": {}})
    pack = {"route": ["0", "1", "both", "all"],
            "views": {k: {} for k in ("0", "1", "both", "all")},
            "quality": {"answer_quality": "verified", "coverage": 1.0,
                        "answer_ready": True, "process_ready": True}}
    a = ENG.audit_behavior(pack, s)
    assert a["full_route"] and a["quality_score"] == 1.0
    assert a["capabilities_total"] == 17


def case_history_audit():
    s = ENG.apply_history_fusion({}, '如何决定？')
    a = ENG.audit_history_fusion({'route': ['0', '1', 'both', 'all'],
                                   'views': {k: {} for k in ('0', '1', 'both', 'all')}}, s)
    assert a['total_versions'] == ENG._HF_VERSION_COUNT
    assert a['readiness'] == 1.0
    assert a['axes_total'] == 17
    assert a['views_present'] == ['0', '1', 'both', 'all']


def case_runtime_thinking_off():
    # V2.2.0 fix：--thinking off 必须同时关掉 reasoner 档，否则长调用会挂。
    cfg, notes = ENG._apply_runtime({}, {"thinking": "off"})
    assert cfg["api"]["thinking"]["default"] == "disabled"
    assert cfg["api"]["thinking"]["reasoner"] == "disabled"
    assert any("思考" in n for n in notes)


def case_record_outcome():
    old = ENG._bf_stats_path
    with tempfile.TemporaryDirectory() as td:
        ENG._bf_stats_path = lambda: Path(td) / "stats.json"
        try:
            r = ENG.record_outcome("fusion_full", {
                "llm_calls": 2, "llm_tokens": 10,
                "quality": {"answer_quality": "verified", "coverage": 1.0,
                            "answer_ready": True}})
            assert r["n"] == 1
            d = json.loads((Path(td) / "stats.json").read_text(encoding="utf-8"))
            assert d["arms"]["fusion_full"]["n"] == 1
            assert "answer" not in json.dumps(d, ensure_ascii=False)
        finally:
            ENG._bf_stats_path = old


CASES = [case_axes_inline, case_history_plan, case_behavior_arms,
         case_fact_arm, case_decision_arm, case_open_arm,
         case_explicit_preserved, case_auto_changed, case_metadata,
         case_audit_pack, case_history_audit, case_record_outcome,
         case_runtime_thinking_off]


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
