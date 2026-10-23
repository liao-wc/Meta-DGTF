# -*- coding: utf-8 -*-
"""F4 · both 原生论证契约包判据（10 项）。

1. 完整原生：both_view 自带齐全 argument_graph -> native=True / ok=True / 1.0；
2. bridge-only：只有 manifest/collision/adjudications/threads -> 形式齐全但 native=False；
3. 缺 synthesis：记 gap，且没有桥接源时不伪造 bridge_only；
4. 缺 defeated：记 gap，native=False；
5. 缺 undecided：记 gap，native=False；
6. 冲突解决非空：argument_graph / both 视图 / settlement 的既有 resolution 都能只读读出；
7. 空视图：0.0、三条缺项 gap、ok=False；
8. string 输入：JSON 整包 / graph JSON 串 / 纯文本 / 列表都不崩且分类正确；
9. to_dict：字段齐全、可 JSON 往返、缺省包可序列化；
10. native 标记：原生齐全才 True；桥接补齐、显式标注 bridge、空 defeated 都不算原生。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.layers_both import (BothArgumentPackage, assemble_both_package,  # noqa: E402
                                 REQUIRED_FIELDS)


def _native_graph():
    return {
        "synthesis": "综合：签字栏对象为空时 A 的计次口径不可用，采用 B 的两栏结构",
        "defeated": ["A 的计次口径把恒 1 部分并入分母，稀释命中率"],
        "undecided": ["签字栏对象为空时如何标缺"],
        "conflict_resolution": {"winner": "B 的两栏结构", "reason": "可数处没有信息"},
    }


def _native_view():
    return {"argument_graph": _native_graph(),
            "manifest": "旧 manifest（原生齐全时不得被用来覆盖）"}


def case_native_complete():
    p = assemble_both_package(_native_view(),
                              {"sub_questions": []},
                              {"decision": "d"})
    assert p.ok and not p.gaps, p.gaps
    assert p.native is True
    assert p.synthesis_origin == "native"
    assert p.contract_completeness == 1.0
    assert set(p.argument_graph) == {"synthesis", "defeated", "undecided",
                                     "conflict_resolution"}
    assert p.argument_graph["synthesis"] == _native_graph()["synthesis"]
    assert p.argument_graph["defeated"] == _native_graph()["defeated"]
    assert p.argument_graph["undecided"] == _native_graph()["undecided"]
    # 原生齐全时，旧 manifest 不能被当作 synthesis 覆盖原生图
    assert p.argument_graph["synthesis"] != "旧 manifest（原生齐全时不得被用来覆盖）"


def case_bridge_only():
    view = {
        "manifest": "旧 manifest 的综合文本",
        "collision": "旧 collision 文本",
        "adjudications": [
            {"tension": "计次口径是否合并", "polarity": "both"},
            "悬置：签字对象为空",
        ],
        "threads": [
            {"desc": "签字栏对象为空时如何标缺", "kind": "thread"},
            "另一条未决张力",
        ],
    }
    p = assemble_both_package(view)
    assert p.ok is False
    assert p.native is False
    assert p.synthesis_origin == "bridge"
    assert "bridge_only" in p.gaps, p.gaps
    # 契约形式可以齐全，但语义不算原生：形式通过 != 语义通过
    assert p.contract_completeness == 1.0
    assert p.argument_graph["synthesis"] == "旧 manifest 的综合文本"
    assert p.argument_graph["defeated"][0] == "计次口径是否合并"
    assert p.argument_graph["undecided"][0] == "签字栏对象为空时如何标缺"
    for name in REQUIRED_FIELDS:
        assert any(("缺 " + name) in gap for gap in p.gaps), (name, p.gaps)


def case_missing_synthesis():
    p = assemble_both_package({"argument_graph": {"defeated": ["d"],
                                                 "undecided": ["u"]}})
    assert p.ok is False and p.native is False
    assert any("缺 synthesis" in gap for gap in p.gaps), p.gaps
    assert "bridge_only" not in p.gaps  # 没有桥接源，不能假装桥接
    assert abs(p.contract_completeness - 2.0 / 3.0) < 1e-9
    assert p.synthesis_origin == "partial"


def case_missing_defeated():
    p = assemble_both_package({"argument_graph": {"synthesis": "s",
                                                 "undecided": ["u"]}})
    assert p.ok is False and p.native is False
    assert any("缺 defeated" in gap for gap in p.gaps), p.gaps
    assert p.contract_completeness < 1.0


def case_missing_undecided():
    p = assemble_both_package({"argument_graph": {"synthesis": "s",
                                                 "defeated": ["d"]}})
    assert p.ok is False and p.native is False
    assert any("缺 undecided" in gap for gap in p.gaps), p.gaps
    assert p.contract_completeness < 1.0


def case_conflict_resolution():
    p = assemble_both_package(_native_view())
    assert p.ok and p.native
    assert p.argument_graph["conflict_resolution"], p.argument_graph

    # 原生图未带 resolution，但 both 视图自带 -> 只读回退，原生判定不变
    graph = {k: v for k, v in _native_graph().items()
             if k != "conflict_resolution"}
    p2 = assemble_both_package({"argument_graph": graph,
                                "conflict_resolution": "采用 B 的两栏结构"})
    assert p2.ok and p2.native
    assert p2.argument_graph["conflict_resolution"] == "采用 B 的两栏结构"

    # settlement 也是既有产物，可作为 resolution 读数
    view3 = {"argument_graph": dict(graph),
             "settlement": {"resolved": True, "round": 12}}
    p3 = assemble_both_package(view3)
    assert p3.native and p3.ok
    assert p3.argument_graph["conflict_resolution"] == {"resolved": True,
                                                        "round": 12}


def case_empty_view():
    for raw in ({}, None, "", [], {"both": {}}):
        p = assemble_both_package(raw, {}, {})
        assert p.ok is False and p.native is False
        assert p.contract_completeness == 0.0
        assert len(p.gaps) == 3, (raw, p.gaps)
        assert p.synthesis_origin == "none"
        assert p.argument_graph == {"synthesis": "", "defeated": [],
                                    "undecided": [],
                                    "conflict_resolution": {}}


def case_string_inputs():
    # 1) JSON 字符串整包
    p = assemble_both_package(json.dumps({"argument_graph": _native_graph()},
                                         ensure_ascii=False))
    assert p.native and p.ok, p.gaps
    # 2) argument_graph 本身是 JSON 字符串
    p2 = assemble_both_package({"argument_graph": json.dumps(
        _native_graph(), ensure_ascii=False)})
    assert p2.native and p2.ok, p2.gaps
    # 3) 纯文本（旧产物）只能按桥接读，不能冒充原生
    p3 = assemble_both_package("只有一段旧的综合文本")
    assert p3.native is False and p3.synthesis_origin == "bridge"
    assert p3.argument_graph["synthesis"] == "只有一段旧的综合文本"
    assert "bridge_only" in p3.gaps
    # 4) 列表输入（旧 adjudications）不崩，按桥接映射
    p4 = assemble_both_package(["败方 A 被驳倒", {"tension": "张力 B"}])
    assert p4.native is False and p4.synthesis_origin == "bridge"
    assert p4.argument_graph["defeated"] == ["败方 A 被驳倒", "张力 B"]


def case_to_dict():
    p = assemble_both_package(_native_view())
    d = p.to_dict()
    assert isinstance(d, dict)
    assert set(d) == {"argument_graph", "native", "synthesis_origin", "gaps",
                      "contract_completeness", "ok"}
    assert d["native"] is True and d["ok"] is True
    assert isinstance(d["contract_completeness"], float)
    assert d["gaps"] == []
    roundtrip = json.loads(json.dumps(d, ensure_ascii=False))
    assert roundtrip["argument_graph"]["defeated"] == \
        p.argument_graph["defeated"]
    # 缺省构造的包也能序列化
    empty = BothArgumentPackage().to_dict()
    assert empty["ok"] is False and empty["contract_completeness"] == 0.0


def case_native_marking():
    native = assemble_both_package(_native_view())
    assert native.native is True  # 原生齐全才 True

    bridge = assemble_both_package({"manifest": "m",
                                    "adjudications": ["d"],
                                    "threads": ["u"]})
    assert bridge.native is False
    assert bridge.synthesis_origin == "bridge"
    assert bridge.contract_completeness == 1.0  # 形式完整
    assert bridge.ok is False

    # 原生缺一项、由桥接补齐：仍不算原生，且要留原生缺项 + bridge_only
    mixed = assemble_both_package({
        "argument_graph": {"synthesis": "s", "undecided": ["u"]},
        "adjudications": ["d"],
    })
    assert mixed.native is False and mixed.synthesis_origin == "bridge"
    assert any("缺 defeated" in gap for gap in mixed.gaps), mixed.gaps
    assert "bridge_only" in mixed.gaps
    assert mixed.contract_completeness == 1.0

    # 显式标注为桥接的论证图，字段齐全也不算原生
    labelled = assemble_both_package({"argument_graph": dict(
        _native_graph(), origin="bridge")})
    assert labelled.native is False and "bridge_only" in labelled.gaps

    # 原生 defeated 显式为空且无桥接源 -> 缺项，不能算齐全
    empty_defeated = assemble_both_package({"argument_graph": {
        "synthesis": "s", "defeated": [], "undecided": ["u"]}})
    assert empty_defeated.native is False
    assert empty_defeated.ok is False
    assert any("缺 defeated" in gap for gap in empty_defeated.gaps)


CASES = [case_native_complete, case_bridge_only, case_missing_synthesis,
         case_missing_defeated, case_missing_undecided,
         case_conflict_resolution, case_empty_view, case_string_inputs,
         case_to_dict, case_native_marking]


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
