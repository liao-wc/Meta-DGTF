# -*- coding: utf-8 -*-
"""v1.23.28 修复效果验证：D1/D2 真实入口能否产出状态迁移。

对照两版（v1.23.27 / v1.23.28），走**同一个真实入口序列**：
  ① 同一主张被**不同层**独立复现（0 → 1 → both）⇒ 应触发 stable
  ② 出现攻击证据 ⇒ 应触发 revoked
  ③ 被可判定通道回答 ⇒ 应触发 resolved
  ④ 同层反复说（层名相同）⇒ **不该**算独立复现
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, py):
    spec = importlib.util.spec_from_file_location(name, py)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


TEXT = "排水管网改造应该优先于岸线景观工程"


def run_scenario(m, tag):
    print("=" * 72)
    print("  %s" % tag)
    print("=" * 72)

    # ① 跨层独立复现（层名不同 ⇒ 应凑齐 ≥2 来源 + ≥2 圈 ⇒ stable）
    p = m.Pool()
    for _layer, _rn in (("0", 1), ("1", 2), ("both", 3)):
        p.add_undecidable({"structural_amps": [TEXT],
                           "_layer_name": _layer, "_round_no": _rn},
                          layer=_rn)
        _it = p.belief_items[0] if p.belief_items else {}
        print("  圈%d layer=%s → support=%r rounds=%r status=%r"
              % (_rn, _layer, _it.get("support"), _it.get("rounds_seen"),
                 _it.get("status")))
    print("  belief_transitions = %r"
          % [(t.get("from"), "->", t.get("to"), t.get("why"))
             for t in (p.belief_transitions or [])])
    _n_stable = sum(1 for t in (p.belief_transitions or [])
                    if t.get("to") == "stable")
    print("  ★ stable 迁移条数 = %d" % _n_stable)

    # ② 攻击 ⇒ revoked
    p2 = m.Pool()
    p2.add_undecidable({"structural_amps": [TEXT],
                        "_layer_name": "0", "_round_no": 1,
                        "_belief_attack": "证据显示岸线工程边际效益更高"},
                       layer=1)
    _it2 = p2.belief_items[0] if p2.belief_items else {}
    print("  攻击场景 → status=%r attack=%r"
          % (_it2.get("status"), _it2.get("attack")))
    _n_rev = sum(1 for t in (p2.belief_transitions or [])
                 if t.get("to") == "revoked")
    print("  ★ revoked 迁移条数 = %d" % _n_rev)

    # ③ 清偿 ⇒ resolved
    p3 = m.Pool()
    p3.add_undecidable({"structural_amps": [TEXT],
                        "_layer_name": "1", "_round_no": 1,
                        "_belief_resolved": "decidable_channel"},
                       layer=1)
    _it3 = p3.belief_items[0] if p3.belief_items else {}
    print("  清偿场景 → status=%r" % _it3.get("status"))
    _n_res = sum(1 for t in (p3.belief_transitions or [])
                 if t.get("to") == "resolved")
    print("  ★ resolved 迁移条数 = %d" % _n_res)

    # ④ 同层反复说（**不该**算独立复现 ⇒ 不 stable）
    p4 = m.Pool()
    for _rn in (1, 2, 3, 4):
        p4.add_undecidable({"structural_amps": [TEXT],
                            "_layer_name": "1", "_round_no": _rn},
                           layer=_rn)
    _it4 = p4.belief_items[0] if p4.belief_items else {}
    _n_stable4 = sum(1 for t in (p4.belief_transitions or [])
                     if t.get("to") == "stable")
    print("  同层 4 圈 → support=%r status=%r" % (_it4.get("support"),
                                                 _it4.get("status")))
    print("  ★ 同层 stable 迁移条数 = %d（应为 0 —— 同层不算独立来源）"
          % _n_stable4)

    # ⑤ D3 熵落盘 + D1 统计出口
    print("  sense: semantic_entropy = %r"
          % [_b.get("semantic_entropy") for _b in (p.belief_items or [])][:3])
    _d = p.to_dict()
    print("  to_dict 含 belief_status_counts ? %r  -> %r"
          % ("belief_status_counts" in _d,
             _d.get("belief_status_counts")))
    print("  to_dict 含 aspect_units ? %r" % ("aspect_units" in _d))
    _v = m.View(entry="0")
    _v.add_aspect_unit("甲方面", polarity="阳")
    _vd = _v.to_dict()
    print("  view.to_dict 含 touch_rate ? %r  aspect_carry_rate ? %r"
          % ("touch_rate" in _vd, "aspect_carry_rate" in _vd))
    print()
    return dict(stable=_n_stable, revoked=_n_rev, resolved=_n_res,
                same_layer_stable=_n_stable4)


_r = {}
print()
print("################ v1.23.27（改前）################")
try:
    m27 = load("m27c", HERE / "元DGTF-V1.23.27.py")
    _r["27"] = run_scenario(m27, "v1.23.27 改前")
except Exception as e:
    print("  [崩] %s: %s" % (type(e).__name__, e))
    _r["27"] = None

print()
print("################ v1.23.28（改后）################")
try:
    m28 = load("m28c", HERE / "元DGTF-V1.23.28.py")
    _r["28"] = run_scenario(m28, "v1.23.28 改后")
except Exception as e:
    import traceback
    traceback.print_exc()
    _r["28"] = None

print()
print("=" * 72)
print("对照汇总")
print("=" * 72)
for k in ("27", "28"):
    print("  v1.23.%s -> %r" % (k, _r.get(k)))
