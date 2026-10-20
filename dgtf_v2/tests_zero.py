# -*- coding: utf-8 -*-
"""F5 · 0 层审计/延期契约包判据（10 项）。

口径依据 docs/v1240_phase5_fusion.md §3.1 / §6.3：0 层只接契约、不接 L0-v2，
novelty_curve 空是延期读数而非职责缺口；F5 整体 deferred。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.layers_zero import ZeroLayerPackage, assemble_zero_package  # noqa: E402


def _full():
    """原生齐全的 0 层视图：aspects=3 / probes=1 / suspensions=1 / novelty 有值。"""
    return {
        "candidates": [{"desc": "方面甲"}, {"desc": "方面乙"}],
        "amps": [{"desc": "侧面丙"}],
        "probes": [{"question": "探针一"}],
        "suspensions": [{"id": "s_001", "status": "active"}],
        "novelty_curve": [0.91, 0.84, 0.77],
    }


def case_complete():
    p = assemble_zero_package(_full(), {"coverage": 0.5})
    assert p.aspects == 3, p.aspects
    assert p.probes == 1 and p.suspensions == 1, (p.probes, p.suspensions)
    assert p.novelty_measured and p.novelty_curve == [0.91, 0.84, 0.77]
    assert p.no_actions and not p.gaps, p.gaps
    assert p.contract_completeness == 1.0 and p.ok
    assert p.deferred is True


def case_missing_aspects():
    p = assemble_zero_package({"probes": [{"question": "q"}],
                               "suspensions": [{"id": "s"}]})
    assert p.aspects == 0
    assert not p.ok
    assert any("aspects" in g for g in p.gaps), p.gaps
    assert p.contract_completeness == 0.5, p.contract_completeness


def case_no_probes_no_suspensions():
    p = assemble_zero_package({"candidates": [{"desc": "a"}],
                               "amps": [{"desc": "b"}],
                               "probes": [], "suspensions": []})
    assert p.probes == 0 and p.suspensions == 0
    assert not p.ok
    assert any("probes" in g and "suspensions" in g for g in p.gaps), p.gaps
    assert p.contract_completeness == 0.5, p.contract_completeness


def case_actions_overreach():
    p = assemble_zero_package({**_full(), "actions": [{"owner": "x"}]})
    assert p.no_actions is False
    assert not p.ok
    assert any("越权" in g and "actions" in g for g in p.gaps), p.gaps
    # 原生齐全但越权：完整性仍是 1.0，ok 必须为 False
    assert p.contract_completeness == 1.0 and p.ok is False

    p2 = assemble_zero_package({**_full(), "not_do": ["不做甲"]})
    assert p2.no_actions is False and not p2.ok
    assert any("越权" in g and "not_do" in g for g in p2.gaps), p2.gaps

    p3 = assemble_zero_package({**_full(), "decidable_product": {
        "actions": [{"owner": "y"}]}})
    assert p3.no_actions is False and not p3.ok
    assert any("decidable_product.actions" in g for g in p3.gaps), p3.gaps


def case_novelty_empty_deferred():
    view = _full()
    view.pop("novelty_curve")
    p = assemble_zero_package(view, {"coverage": 0.4})
    assert p.novelty_curve == [] and p.novelty_measured is False
    # 延期项：novelty 空不记 gap，也不挡 0 层契约 ok
    assert not any("novelty" in g.lower() for g in p.gaps), p.gaps
    assert p.deferred is True
    assert p.ok is True


def case_novelty_measured():
    p = assemble_zero_package(_full())
    assert p.novelty_measured is True
    assert p.novelty_curve and all(isinstance(x, float) for x in p.novelty_curve)
    assert not any("novelty" in g.lower() for g in p.gaps), p.gaps
    assert p.ok is True
    # quality 只作只读补充：视图缺 novelty 时可用质量读数里的 novelty_curve
    p2 = assemble_zero_package({"candidates": [{"desc": "a"}],
                                "probes": [{"question": "q"}]},
                               {"novelty_curve": [0.6, 0.5]})
    assert p2.novelty_measured is True and p2.ok is True


def case_empty_view():
    p = assemble_zero_package({}, {})
    assert (p.aspects, p.probes, p.suspensions) == (0, 0, 0)
    assert len(p.gaps) == 2, p.gaps
    assert p.contract_completeness == 0.0
    assert not p.ok
    assert p.deferred is True
    assert assemble_zero_package(None).to_dict() == p.to_dict()


def case_string_tolerance():
    raw = json.dumps({
        "candidates": [{"desc": "a"}],
        "amps": [{"desc": "b"}],
        "probes": "2",             # 数字字符串
        "suspensions": "[]",       # JSON 空列表字符串
        "novelty_curve": "[0.5, 0.4]",
    }, ensure_ascii=False)
    p = assemble_zero_package(raw, json.dumps({"coverage": 0.3}))
    assert p.aspects == 2 and p.probes == 2 and p.suspensions == 0
    assert p.novelty_measured and p.novelty_curve == [0.5, 0.4]
    assert p.ok and not p.gaps, p.gaps
    # 非法字符串不抛异常：按空视图审计
    bad = assemble_zero_package("{not json", None)
    assert not bad.ok and len(bad.gaps) >= 2


def case_to_dict():
    p = assemble_zero_package(_full())
    d = p.to_dict()
    keys = {"aspects", "probes", "suspensions", "novelty_curve",
            "novelty_measured", "no_actions", "gaps",
            "contract_completeness", "ok", "deferred"}
    assert set(d) == keys, set(d) ^ keys
    assert d["deferred"] is True and d["novelty_measured"] is True
    assert d["contract_completeness"] == 1.0 and d["ok"] is True
    assert json.loads(json.dumps(d, ensure_ascii=False))["ok"] is True
    z = ZeroLayerPackage().to_dict()
    assert z["deferred"] is True and z["ok"] is False
    assert z["contract_completeness"] == 0.0 and z["gaps"] == []


def case_ok_semantics():
    full = assemble_zero_package(_full())
    assert full.ok is True
    bad = {
        "缺 aspects": assemble_zero_package({"probes": [{"question": "q"}]}),
        "probes/suspensions 都 0": assemble_zero_package(
            {"candidates": [{"desc": "a"}]}),
        "actions 越权": assemble_zero_package({**_full(),
                                               "actions": [{"owner": "x"}]}),
        "not_do 越权": assemble_zero_package({**_full(), "not_do": ["x"]}),
        "空视图": assemble_zero_package({}),
    }
    for name, pkg in bad.items():
        assert pkg.ok is False, name
        assert pkg.deferred is True, name
        # ok 的唯一语义：原生齐全（完整性 1.0）且无任何 gap
        assert pkg.ok == (pkg.contract_completeness == 1.0
                          and not pkg.gaps), name
    base = _full()
    base.pop("novelty_curve")
    assert assemble_zero_package(base).ok is True


CASES = [case_complete, case_missing_aspects, case_no_probes_no_suspensions,
         case_actions_overreach, case_novelty_empty_deferred,
         case_novelty_measured, case_empty_view, case_string_tolerance,
         case_to_dict, case_ok_semantics]


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
