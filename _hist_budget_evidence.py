# -*- coding: utf-8 -*-
"""预算定标证据：从历史产物里提取「各层圈数 / 是否被截断 / 产出质量」。

用法：python _hist_budget_evidence.py

样本目录（两批旧产物，v1.21.50 之前）：
  C:/Users/18432/Desktop/元DGTF/元DGTF.outputs.1   (223 项)
  C:/Users/18432/Desktop/DGTF/DGTF.outputs         (127 项)

只解析同时含「调度」行 / 「实际走了 N 圈」/「螺旋停止」的样本。
输出四块：
  A. 各层实际圈数分布（大预算样本 → 看"自然停止点"）
  B. 同一天内 大预算 vs 小预算（版本相同，控制版本混淆）
  C. 预算档 × 日期（看是否完全混淆，决定 B 可不可信）
  D. 代码实算指标 vs 模型自报指标（方向是否一致）

★ 结论（2026-09-30 实测，v1.21.58）：A 里那批"自然停止点"是在 v1.21.56
  收紧停止判据**之前**跑的，当前版本给多少预算就跑多少圈，所以
  A 只能当历史参考，不能当"目标预算"。详见真跑验证报告第十二节。
"""
import collections
import glob
import os
import re
import statistics as stats

DIRS = [
    r"C:/Users/18432/Desktop/元DGTF/元DGTF.outputs.1",
    r"C:/Users/18432/Desktop/DGTF/DGTF.outputs",
]
LAYERS = ("修行", "研究", "对撞", "元")
re_sched = re.compile(
    r"修行\((\d+)圈\).*?研究\((\d+)圈\).*?对撞\((\d+)圈\).*?元\((\d+)圈\)")
re_rounds = re.compile(r"\*\*实际走了 (\d+) 圈\*\*（上限 (\d+) 圈）")
re_stop = re.compile(r"\*\*螺旋停止\*\*：(.+?)(?:\n|$)")


def collect():
    out = []
    for d in DIRS:
        for p in sorted(glob.glob(os.path.join(d, "*.md"))):
            try:
                t = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            t = t.replace("\r\n", "\n")
            m = re_sched.search(t)
            if not m:
                continue
            rs = re_rounds.findall(t)
            ss = re_stop.findall(t)
            if len(rs) < 4 or len(ss) < 4:
                continue
            comp = re.search(r"\*\*综合距离\*\*：([\d.]+)", t)
            defer = re.search(r"延迟债务 (\d+) 条", t)
            out.append({
                "day": os.path.basename(p)[:8],
                "bud": tuple(int(x) for x in m.groups()),
                "rounds": [int(x[0]) for x in rs[:4]],
                "trunc": sum(1 for s in ss[:4]
                             if "体力耗尽" in s or "被截断" in s),
                # 代码实算（可信）
                "flags": len(re.findall(r"\*\*质量线索\*\*：(.+)", t)),
                "unsaid": t.count("此处未生"),
                "defer": int(defer.group(1)) if defer else 0,
                # 模型自报（只作对照）
                "comp": float(comp.group(1)) if comp else None,
            })
    return out


rows = collect()
print(f"可解析样本 {len(rows)}")
print()
print("=== A. 大预算(≥8)样本里各层实际跑了几圈（历史参考）===")
big = [r for r in rows if max(r["bud"]) >= 8]
print(f"  n={len(big)}")
for i, k in enumerate(LAYERS):
    v = sorted(r["rounds"][i] for r in big)
    if v:
        print(f"  {k}: {dict(sorted(collections.Counter(v).items()))}")
print()
print("=== C. 预算档 × 日期（看是否完全混淆）===")
byday = collections.defaultdict(collections.Counter)
for r in rows:
    b = max(r["bud"])
    k = f"预算{b}" if b in (2, 3, 4, 6) else "预算≥8"
    byday[k][r["day"]] += 1
for k in sorted(byday):
    print(f"  {k:8} {dict(sorted(byday[k].items()))}")
print()
print("=== B. 同一天内 大预算 vs 小预算（版本相同 → 可信）===")
for day in sorted(set(r["day"] for r in rows)):
    v = [r for r in rows if r["day"] == day]
    b = [r for r in v if max(r["bud"]) >= 8]
    s = [r for r in v if max(r["bud"]) <= 4]
    if not (b and s):
        continue
    print(f"  {day}")
    for tag, g in (("大预算≥8", b), ("小预算≤4", s)):
        print(f"    {tag:8} n={len(g):3} 总圈数="
              f"{stats.mean([sum(x['rounds']) for x in g]):5.1f}"
              f"  被截断层={stats.mean([x['trunc'] for x in g]):.2f}"
              f"  质量线索={stats.mean([x['flags'] for x in g]):.2f}"
              f"  未生={stats.mean([x['unsaid'] for x in g]):5.1f}")
print()
print("=== D. 两个口径方向是否一致（大预算 vs 小预算）===")
for tag, g in (("大预算≥8", big), ("小预算≤4", [r for r in rows
                                          if max(r["bud"]) <= 4])):
    if not g:
        continue
    cc = [x["comp"] for x in g if x["comp"] is not None]
    print(f"  {tag:8} 代码实算·质量线索={stats.mean([x['flags'] for x in g]):.2f}"
          f"（越低越好）  |  模型自报·综合距离="
          f"{stats.mean(cc) if cc else float('nan'):.2f}"
          f"（口径同上，越低越好）")
print("  → 两个口径给出**相反**的结论；以代码实算为准。")
