# -*- coding: utf-8 -*-
"""v1.23.64 前沿内核判据：每条都带负对照/覆盖率/性质检验。"""
from __future__ import annotations

import importlib.util
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = 0
F = []


def ck(name, cond, note=""):
    global P
    if cond:
        P += 1
        print("  OK  %s" % name)
    else:
        F.append(name)
        print("  RED %s  %s" % (name, note))


_spec = importlib.util.spec_from_file_location("dgtf_kernel", HERE / "_kernel_v12364.py")
K = importlib.util.module_from_spec(_spec)
sys.modules["dgtf_kernel"] = K
_spec.loader.exec_module(K)
# 内核被设计成插入主文件的一段（math/json 由主文件导入）；独立跑时补上。
K.math = math
K.json = json

random.seed(20261018)

# ── 1. e-process：任意停时下的 I 类错误 ─────────────────────
N_SIM, LEN, ALPHA = 800, 140, 0.05
fp = 0
for _ in range(N_SIM):
    seq = [1 if random.random() < 0.5 else 0 for _ in range(LEN)]
    # 每步都看（optional stopping）
    bad = False
    for t in range(2, LEN + 1):
        if K.evalue_bernoulli(seq[:t], 0.5)["evalue"] >= 1.0 / ALPHA:
            bad = True
            break
    fp += int(bad)
rate = fp / float(N_SIM)
ck("F1 任意停时 I 类错误 ≤ α（实测 %.3f，理论 ≤ %.2f，MC 误差约 ±0.008）"
   % (rate, ALPHA), rate <= ALPHA + 0.02, "false positive=%d/%d" % (fp, N_SIM))

# ── 2. e-process：功效（比 stitched Hoeffding 更早停）────────
def _hoeffding_lb(xs, delta=0.05):
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    rad = math.sqrt((1.0 / (2.0 * n)) * (1.0 + 1.0 / n)
                    * math.log(math.sqrt(n + 1) / delta))
    return m - rad

stop_e, stop_h = [], []
for _ in range(200):
    seq = [1 if random.random() < 0.7 else 0 for _ in range(200)]
    te = th = 201
    for t in range(2, 201):
        if te == 201 and K.evalue_bernoulli(seq[:t], 0.5)["evalue"] >= 20:
            te = t
        if th == 201 and (_hoeffding_lb(seq[:t]) or 0) > 0.5:
            th = t
    stop_e.append(te)
    stop_h.append(th)
me = statistics.median(stop_e)
mh = statistics.median(stop_h)
ck("F2 e-process 比 stitched Hoeffding 更省样本（中位 %s vs %s）" % (me, mh),
   me < mh, "e=%s h=%s" % (me, mh))

# ── 3. 数值稳定：极长序列不炸、不返回负数 ───────────────────
r = K.evalue_bernoulli([1] * 5000, 0.5)
ck("F3 长序列 log-space 稳定（evalue=%r）" % (r["evalue"],),
   r["evalue"] > 1e6 and math.isfinite(r["log_evalue"]), repr(r))
r2 = K.evalue_bernoulli([0] * 5000, 0.5)
ck("F3b 反向长序列 e→0 且非负（%r）" % (r2["evalue"],),
   r2["evalue"] >= 0.0 and r2["evalue"] < 1e-6, repr(r2))

# ── 4. 保形预测：覆盖率 ─────────────────────────────────────
cal = [random.random() for _ in range(199)]
q = K.conformal_quantile(cal, 0.1)
cov = sum(1 for _ in range(4000) if random.random() <= q) / 4000.0
ck("F4 保形覆盖率 ≥ 1−α（实测 %.3f，n=199，α=0.1）" % cov,
   0.88 <= cov <= 0.98, "q=%.4f" % q)
ck("F4b 空校准集 ⇒ +inf（保守全弃权）",
   K.conformal_quantile([], 0.1) == float("inf"), "")
cal20 = [i / 20.0 for i in range(20)]
pset = K.conformal_prediction_set(cal20, {"a": 0.05, "b": 0.99}, 0.1)
ck("F4c 预测集按分数阈值取标签", pset == ["a"], repr(pset))
ck("F4d 校准集不足 ⇒ 全标签（保守）",
   K.conformal_prediction_set([0.1], {"a": 0.05, "b": 0.5}, 0.1) == ["a", "b"], "")

# ── 5. BOCPD：均值漂移检出 + 平稳负对照 ─────────────────────
_rng = random.Random(1)          # 局部 RNG：不受前面仿真消耗的全局种子影响
base = [_rng.gauss(0, 1) for _ in range(40)]
shift = [_rng.gauss(5.0, 1) for _ in range(40)]
b = K.bocpd_run(base + shift, hazard=0.05)
det = [i for i in b["detected"] if 38 <= i <= 47]
ck("F5 BOCPD 在 5σ 漂移后 0..7 步内检出（detected=%r）" % (b["detected"][:6],),
   bool(det), repr(b["detected"][:10]))
false_alarm = [i for i in b["detected"] if i < 35]
ck("F5b 漂移前误报 ≤ 2", len(false_alarm) <= 2, repr(false_alarm))
b2 = K.bocpd_run([random.gauss(0, 1) for _ in range(80)], hazard=0.05)
ck("F5c 平稳序列误报 ≤ 3（%d）" % len(b2["detected"]), len(b2["detected"]) <= 3,
   repr(b2["detected"]))

# ── 6. 论证：grounded 语义的三条性质 ────────────────────────
af = K.ArgumentationFramework(["A", "B"], [("A", "B")])
ck("F6 单攻击：grounded={A}", af.grounded_extension() == ["A"],
   repr(af.grounded_extension()))
ck("F6b 被攻击者判 defeated", af.defeated() == ["B"], repr(af.defeated()))

af2 = K.ArgumentationFramework(["A", "B"], [("A", "B"), ("B", "A")])
ck("F6c 二元环：grounded 为空（怀疑论，不硬选）",
   af2.grounded_extension() == [], repr(af2.grounded_extension()))
bd = af2.burdens()
ck("F6d 二元环：负担并列（|Δ|<1e-6）", abs(bd["A"] - bd["B"]) < 1e-6, repr(bd))

af3 = K.ArgumentationFramework(["A", "B", "C"], [("A", "B"), ("B", "C")])
ck("F6e 三元链：grounded={A,C}", af3.grounded_extension() == ["A", "C"],
   repr(af3.grounded_extension()))

pb = [
    {"id": "L1", "kind": "schedule", "cond": {"issue": "cut"},
     "action": {"key": "rounds_delta", "delta": 1}, "status": "active"},
    {"id": "L2", "kind": "schedule", "cond": {"issue": "cut"},
     "action": {"key": "rounds_delta", "delta": 2}, "status": "active",
     "n_evidence": 3, "weight": 1.2},
]
res = K.resolve_playbook_conflicts(pb, apply=True)
ck("F7 playbook 冲突：恰好一个 winner / 一个 defeated",
   len(res["winners"]) == 1 and len(res["defeated"]) == 1, json.dumps(res, ensure_ascii=False))
ck("F7b 冲突只标不删（两条都还在、status 未改）",
   len(pb) == 2 and all(e.get("status") == "active" for e in pb), "")
ck("F7c 被标 defeated 的条目有 defeated_by",
   any(e.get("defeated_by") for e in pb), json.dumps(pb, ensure_ascii=False))

# 精确并列 ⇒ 不硬选（红线：未对齐合法）
pb3 = [
    {"id": "T1", "kind": "probe", "cond": {"issue": "x"},
     "action": {"key": "k", "v": 1}, "status": "active"},
    {"id": "T2", "kind": "probe", "cond": {"issue": "x"},
     "action": {"key": "k", "v": 2}, "status": "active"},
]
res3 = K.resolve_playbook_conflicts(pb3, apply=True)
ck("F7e 精确并列 ⇒ 全 undecided（不强行对齐）",
   not res3["winners"] and len(res3["undecided"]) == 2,
   json.dumps(res3, ensure_ascii=False))

# 负对照：无冲突时不该乱标
pb2 = [dict(pb[0])]
res2 = K.resolve_playbook_conflicts(pb2, apply=True)
ck("F7d 无冲突 ⇒ 零裁决（负对照）",
   res2["n_attacks"] == 0 and not res2["winners"] and not res2["defeated"],
   json.dumps(res2, ensure_ascii=False))

# ── 7. anytime_decided 分派：两种模式同签名 ─────────────────
def _hoeffding_dict(xs, delta=0.05):
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    rad = math.sqrt((1.0 / (2.0 * n)) * (1.0 + 1.0 / n)
                    * math.log(math.sqrt(n + 1) / delta))
    return {"n": n, "mean": m, "lower": m - rad, "upper": m + rad, "delta": delta}


K.stitched_hoeffding_lower = _hoeffding_dict
ok1, i1 = K.anytime_decided([1] * 30, 0.05, 0.5, mode="evalue")
ok2, i2 = K.anytime_decided([1] * 30, 0.05, 0.5, mode="hoeffding")
ck("F8 分派：evalue 模式", ok1 and i1.get("mode") == "evalue", repr(i1))
ck("F8b 分派：hoeffding 模式", ok2 and i2.get("mode") == "hoeffding", repr(i2))
ok3, i3 = K.anytime_decided([0, 1] * 20, 0.05, 0.5, mode="evalue")
ck("F8c 未达阈值不误停", not ok3, repr(i3))

print("\nKERNEL PASS %d / FAIL %d" % (P, len(F)))
sys.exit(0 if not F else 1)
