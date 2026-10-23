# -*- coding: utf-8 -*-
"""抽出「可判定覆盖率 X/Y」做方差分析。

背景（2026-10-02）：我用「欧盟 light 跑出 3/5 vs 地铁 light 跑出 6/6」
判了一条大规则（砍层能不能省钱看题目自不自足）。但那两个数各自只有
**一次**观测，而 X/Y 的 Y 是「判决时冻出来的名单」，本身就带随机。
本脚本不复跑任何东西，只把采集器已经解析好的 ans_x/ans_y 按「题目」分组，
看同一道题在同样 / 不同配置下的分母到底飘多大。

用法：python _ans_variance.py
"""
import collections
import importlib.util
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "cm", str(HERE / "_convergence_matrix.py"))
cm = importlib.util.module_from_spec(spec)
sys.modules["cm"] = cm
spec.loader.exec_module(cm)

rows = [r for r in cm.collect("*.log")
        if not r.get("error") and r.get("ans_x") is not None]

by_q = collections.defaultdict(list)
for r in rows:
    by_q[r["qname"]].append(r)

print(f"=== 有 X/Y 的 run：{len(rows)} 份，覆盖 {len(by_q)} 道题 ===\n")
def _med(vals):
    vals = [v for v in vals if v is not None]
    return st.median(vals) if vals else None


print(f"{'题目':<26}{'n':<4}{'Y取值':<12}{'X==Y':<8}{'cov%中位':<10}{'calls中位'}")
print("-" * 92)
for q, rs in sorted(by_q.items(), key=lambda kv: -len(kv[1])):
    xys = [(r["ans_x"], r["ans_y"]) for r in rs]
    ys = sorted({y for _, y in xys})
    same = sum(1 for x, y in xys if x == y)
    print(f"{q[:24]:<26}{len(rs):<4}{str(ys)[:10]:<12}{same}/{len(rs):<8}"
          f"{str(_med([r.get('coverage') for r in rs])):<10}"
          f"{_med([r.get('calls') for r in rs])}")

_xy = [(r["ans_x"], r["ans_y"]) for r in rows]
_same = sum(1 for x, y in _xy if x == y)
print(f"\n★ 全库 {len(rows)} 份：X==Y 占 {_same}/{len(rows)}"
      f" = {_same/len(rows):.0%}"
      f"（接近 100% ⇒ X/Y 是饱和指标，不能拿它的差异判质量）")

print("\n=== 只看「跑过 ≥4 次」的题：Y 自身的波动 ===")
for q, rs in sorted(by_q.items(), key=lambda kv: -len(kv[1])):
    if len(rs) < 4:
        continue
    ys = [r["ans_y"] for r in rs]
    xs = [r["ans_x"] for r in rs]
    print(f"  {q[:24]:<26} n={len(rs)}  Y={min(ys)}~{max(ys)}"
          f"（极差 {max(ys)-min(ys)}）  X={min(xs)}~{max(xs)}"
          f"  答满率(X==Y)={sum(1 for x,y in zip(xs,ys) if x==y)}/{len(rs)}")

# ---------- 哪些指标有判别力：light(0+1) vs full(四层) ----------
# 判据：① 不饱和（不是每份都同一个值）② 组间差 > 组内噪声。
# 只看两个跑得最多的题，避免题型混进组间差（Simpson 悖论）。
print("\n=== 指标的判别力 (同题 × 砍层/不砍层) ===")
METRICS = ["ans_y", "coverage", "calls", "chars", "debts", "tri_total"]
_KEYQ = sorted({q for q, rs in by_q.items() if len(rs) >= 8})
for q in _KEYQ:
    light = [r for r in by_q[q] if sorted(r["layers"]) == ["0", "1"]]
    full = [r for r in by_q[q]
            if set(r["layers"]) == {"0", "1", "both", "all"}]
    if not light or not full:
        continue
    print(f"\n  [{q[:20]}]  砍层 n={len(light)}　四层 n={len(full)}")
    for mk in METRICS:
        lv = [r.get(mk) for r in light if r.get(mk) is not None]
        fv = [r.get(mk) for r in full if r.get(mk) is not None]
        if len(lv) < 2 or len(fv) < 2:
            print(f"    {mk:<10} 样本不足（砍层 {len(lv)} / 四层 {len(fv)}）")
            continue
        _ov = min(max(lv), max(fv)) - max(min(lv), min(fv))
        print(f"    {mk:<10} 砍层 {min(lv):>6.0f}~{max(lv):<6.0f}"
              f"中位{_med(lv):>6.0f}　四层 {min(fv):>6.0f}~{max(fv):<6.0f}"
              f"中位{_med(fv):>6.0f}　区间重叠={_ov:+.0f}")

# ★ 关键：同样的 (mode, layers) 配置下，X/Y 重不重现
print("\n=== 同题 + 同配置（模式/层集合一致）的重现性 ===")
grp = collections.defaultdict(list)
for r in rows:
    key = (r["qname"], r["mode"], tuple(sorted(r["layers"])))
    grp[key].append(r)
any_dup = False
for key, rs in sorted(grp.items(), key=lambda kv: (kv[0][0], -len(kv[1]))):
    if len(rs) < 2:
        continue
    any_dup = True
    q, mode, layers = key
    xys = [f"{r['ans_x']}/{r['ans_y']}" for r in rs]
    print(f"  {q[:22]:<24} mode={mode:<3} 层={'+'.join(layers):<16} n={len(rs)}"
          f"  X/Y={xys}")
if not any_dup:
    print("  （没有任何一组是同题同配置跑过两次的 —— 也就是说")
    print("   目前**全项目每一格证据都只有一次观测**，任何『A 比 B 好』")
    print("   的结论都还没有被重复 verify 过）")
