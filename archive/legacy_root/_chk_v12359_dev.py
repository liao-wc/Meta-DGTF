# -*- coding: utf-8 -*-
"""v1.23.59 开发期验证：修行层增益换信号后**真的能触发**。

用 §九 实测的真实读数序列（n_aspects = 16, 16, 14, 20）当夹具 —— 不是编的数。

判据：
  A 旧版对照：同一组 trace（只有 n_aspects、没有 excavate）⇒ 增益恒 None ⇒ 不触发
  B 新版：同一条 trace ⇒ 触发（增益 0,0,0.43；前两对都是 0 ⇒ 连续 2 圈低于 0.01）
  C 负对照：层面在长（16→20→30）⇒ 不触发
  D 退回：没有 n_aspects 的老产物 ⇒ 仍走 Heaps 那条算路（行为与旧版一致）
  E 其余三层方向未变：settle 上升 ⇒ 增益 > 0 且不停
"""
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
bad, ok = [], []


def ck(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


def load(py):
    spec = importlib.util.spec_from_file_location("g59_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


new = load(HERE / "元DGTF-V1.23.59.py")
old = load(HERE / "元DGTF-V1.23.58.py")

# 实测序列（§九）：n_aspects = 16, 16, 14, 20；excavate 只有第 3 圈是 0.0，其余 None
REAL = [
    {"round": 1, "n_aspects": 16, "excavate": None},
    {"round": 2, "n_aspects": 16, "excavate": None},
    {"round": 3, "n_aspects": 14, "excavate": 0.0},
    {"round": 4, "n_aspects": 20, "excavate": None},
]

print("=" * 62)
print("【A】旧版对照：只有 n_aspects、excavate 基本为 None ⇒ 增益恒 None")
_g_old = [old.refinement_gain("0", REAL[i], REAL[:i]) for i in range(1, 4)]
ck(all(x is None for x in _g_old),
   "旧版四圈三对的增益 = %r（全 None ⇒ 判据永远不表态）" % (_g_old,))
_hit_old, _ = old.layer_gain_stop_signal("0", REAL[2], REAL[:3], 0.01)
ck(_hit_old is False, "旧版不触发（这就是实测里的\"零触发\"）")

print("\n【B】新版：同一条 trace ⇒ 触发")
_g_new = [new.refinement_gain("0", REAL[i], REAL[:i]) for i in range(1, 4)]
ck(_g_new == [0.0, 0.0, 0.4286],
   "新版三对增益 = %r（期望 [0.0, 0.0, 0.4286]）" % (_g_new,))
_hit_new, _why = new.layer_gain_stop_signal("0", REAL[2], REAL[:3], 0.01)
ck(_hit_new is True, "新版触发：%s" % (_why[:50] or "无理由"))

print("\n【C】负对照：层面在长 ⇒ 不触发")
GROW = [{"round": 1, "n_aspects": 16}, {"round": 2, "n_aspects": 20},
        {"round": 3, "n_aspects": 30}]
_g_grow = [new.refinement_gain("0", GROW[i], GROW[:i]) for i in range(1, 3)]
ck(_g_grow == [0.25, 0.5], "增长序列增益 = %r（期望 [0.25, 0.5]）" % (_g_grow,))
ck(new.layer_gain_stop_signal("0", GROW[2], GROW, 0.01)[0] is False,
   "在长就不停（判据没有变成\"见谁都停\"）")

print("\n【D】退回：没有 n_aspects 的老产物 ⇒ 仍走 Heaps 算路")
OLD_REC = [{"round": 1, "excavate": 0.90}, {"round": 2, "excavate": 0.90},
           {"round": 3, "excavate": 0.90}]
_g_fb = [new.refinement_gain("0", OLD_REC[i], OLD_REC[:i]) for i in range(1, 3)]
ck(_g_fb == [0.0, 0.0], "退回 Heaps：增益 = %r（与旧版一致）" % (_g_fb,))
ck(new.layer_gain_stop_signal("0", OLD_REC[2], OLD_REC, 0.5)[0] is True,
   "退回路径仍能触发")

print("\n【E】其余三层方向未变（settle 上升 ⇒ 增益 > 0）")
ST = [{"round": 1, "settle": 0.50}, {"round": 2, "settle": 0.60}]
ck(new.refinement_gain("1", ST[1], ST[:1]) == 0.1,
   "settle 0.50→0.60 ⇒ 增益 0.1（越大越好，方向不变）")
ck(old.refinement_gain("1", ST[1], ST[:1]) == 0.1,
   "与旧版逐字相同")

print("\n" + "=" * 62)
print("通过 %d / 判红 %d" % (len(ok), len(bad)))
for b in bad:
    print("  ! " + b)
sys.exit(1 if bad else 0)
