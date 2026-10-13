#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.30 前置分析：最近真跑 + 全量 packed 的质量读数体检。

量四类问题（不猜，全从产物里算）：
  A 职责失真：`distance_to_question` 缺省 1.0（= 模型没报）被当成「最远」，
    且只在 <1.0 时渲染 ⇒ 「没数据」静默变成「没问题」。
  B 对齐空转：研究层「对齐覆盖率」在真跑里 0.00 ⇒ 生成的 19/19 条结构
    **完全不与问题的方面重合**（独立度 1.00 + 对齐 0.00 = 彻底漂移）。
  C 截断：`体力耗尽（…未触发任何停止判据…）` ⇒ 停止与收敛机制没生效。
  D 交付面窄：交付正文（落地层）占全文比重；问项词命中率。
"""
import glob
import json
import re
import statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"

Q = "如何利用AI来帮助人类实现财富自由甚至文明升级？"


def terms(q):
    """粗切问项词：中文 2-gram 里挑有信息量的（去停用词）。"""
    stop = set("如何 什么 怎么 哪些 是否 可能 有没有 甚至 以及 因为 所以 到底"
               "一个 这个 那个 我们 他们 可以 能够 需要 应该".split())
    t = re.findall(r"[\u4e00-\u9fff]{2,4}|[A-Za-z]{2,}", q)
    out = []
    for x in t:
        if x in stop:
            continue
        # 2-gram 展开
        if re.fullmatch(r"[\u4e00-\u9fff]{4}", x):
            out += [x[:2], x[2:]]
        else:
            out.append(x)
    return sorted(set(out))


def coverage(text, ts):
    if not text:
        return 0.0, []
    hit = [t for t in ts if t in text]
    return len(hit) / len(ts), hit


def main():
    print("=" * 78)
    print("一、最近一次真跑（20261013_205109）")
    print("=" * 78)
    pk = (OUT / "20261013_205109_如何利用AI来帮助人类实现财富自由甚至文.packed.json")
    md = (OUT / "20261013_205109_如何利用AI来帮助人类实现财富自由甚至文.md")
    d = json.loads(pk.read_text(encoding="utf-8"))
    ts = terms(d["question"])
    print("问题：", d["question"])
    print("问项词（%d）：%s" % (len(ts), "、".join(ts)))
    print()
    print("%-6s %-6s %-8s %-10s %-12s %-8s %s" %
          ("层", "圈数", "d2q", "stop性质", "amps/线头/探针", "悬置", "覆盖"))
    rows = []
    for e in ("0", "1", "both", "all"):
        v = d["views"][e]
        p = d["pools"][e]
        stop = v.get("stop_reason", "")
        kind = "截断" if "体力耗尽" in stop else "自然"
        d2q = v.get("distance_to_question")
        txt = v.get("collision") or ""
        cv = v.get("covered_aspects") or []
        rows.append((e, d2q, kind, len(v.get("amps") or []),
                     len(v.get("threads") or []), len(v.get("probes") or []),
                     len(v.get("suspensions") or []), txt, cv, v))
        print("%-6s %-6s %-8s %-10s %-12s %-8s %s" %
              (e, v.get("rounds_run"), d2q, kind,
               "%d/%d/%d" % (len(v.get("amps") or []), len(v.get("threads") or []),
                             len(v.get("probes") or [])),
               len(v.get("suspensions") or []),
               "covered=%d uncovered=%d" % (len(cv), len(v.get("uncovered_aspects") or []))))
    print()
    print("── A 职责读数失真 ──")
    n_missing = sum(1 for r in rows if r[1] is None or float(r[1]) >= 0.999)
    print("d2q == 1.00（= 模型没报，缺省顶格）的层数：%d / 4" % n_missing)
    print("⇒ 交付正文里 d2q 只在 <1.0 时渲染 ⇒ 这 %d 层的「没有这个读数」"
          "在产物里**完全不可见**。" % n_missing)

    print()
    print("── B 对齐 / 漂移 ──")
    p1 = d["pools"]["1"]
    uch = p1.get("undecidable_channel") or {}
    print("研究层 独立度 last_indep_ratio =", uch.get("last_indep_ratio"),
          "| 对齐覆盖率 last_aligned_coverage =", uch.get("last_aligned_coverage"),
          "| 结构覆盖率 last_sc_ratio =", uch.get("last_sc_ratio"))
    print("研究层 belief_items =", len(p1.get("belief_items") or []),
          "| covered_unders =", len(p1.get("covered_unders") or []),
          "| aspect_units =", len(p1.get("aspect_units") or []))

    print()
    print("── D 交付面 vs 内部面 ──")
    txt = md.read_text(encoding="utf-8")
    lines = txt.split("\n")
    i_land = next(i for i, l in enumerate(lines) if l.startswith("## 落地层"))
    i_app = next(i for i, l in enumerate(lines) if l.startswith("## 附：逐层明细"))
    land = "\n".join(lines[i_land:i_app])
    print("全文 %d 行 / %d 字" % (len(lines), len(txt)))
    print("交付正文（落地层） %d 行 / %d 字 —— 占全文 **%.1f%%**"
          % (len(land.split("\n")), len(land), 100.0 * len(land) / len(txt)))
    print("内部明细（附） %d 行 —— 占全文 %.1f%%"
          % (len(lines) - i_app, 100.0 * (len(lines) - i_app) / len(lines)))
    c_all, hit_all = coverage(txt, ts)
    c_land, hit_land = coverage(land, ts)
    print("问项词命中：交付正文 %s（%d/%d = %.0f%%）"
          % (hit_land, len(hit_land), len(ts), 100 * c_land))

    print()
    print("── 每层「回到问题」段是否真回到问题 ──")
    for e in ("0", "1", "both", "all"):
        seg = "\n".join(lines[i_land:i_app]) if e == "x" else ""
    # 从逐层明细里抠每层的锚点/结论段
    for e in ("0", "1", "both", "all"):
        marker = {"0": "### 修行层", "1": "### 研究层",
                  "both": "### 对撞层", "all": "### 元层"}[e]
        try:
            i0 = next(i for i, l in enumerate(lines) if l.startswith(marker))
        except StopIteration:
            continue
        seg = "\n".join(lines[i0:i0 + 140])
        c, hit = coverage(seg, ts)
        print("  %-4s 段内问项词命中 %2d/%d = %3.0f%%  %s"
              % (e, len(hit), len(ts), 100 * c, "、".join(hit[:8])))

    print()
    print("=" * 78)
    print("二、全量 packed 体检（%d 份）" % len(glob.glob(str(OUT / "*.packed.json"))))
    print("=" * 78)
    n = cut = miss = alig0 = 0
    cut_runs, alig_vals, d2q_vals = [], [], []
    for fp in sorted(glob.glob(str(OUT / "*.packed.json"))):
        try:
            x = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception:
            continue
        vs = x.get("views") or {}
        if not vs:
            continue
        n += 1
        _cut = False
        for e, v in vs.items():
            st_reason = v.get("stop_reason") or ""
            if "体力耗尽" in st_reason or "截断" in st_reason:
                _cut = True
            dq = v.get("distance_to_question")
            if dq is not None:
                d2q_vals.append(float(dq))
                if float(dq) >= 0.999:
                    miss += 1
        if _cut:
            cut += 1
            cut_runs.append(Path(fp).name[:40])
        p1 = (x.get("pools") or {}).get("1") or {}
        ac = ((p1.get("undecidable_channel") or {})
              .get("last_aligned_coverage"))
        if ac is not None:
            alig_vals.append(float(ac))
            if float(ac) <= 1e-9:
                alig0 += 1
    print("有 views 的产物：%d 份" % n)
    print("含【体力耗尽/截断】停止的跑：%d 份（%.0f%%）" % (cut, 100.0 * cut / max(n, 1)))
    print("d2q >= 0.999（缺省顶格）的层-次：%d / %d（%.0f%%）"
          % (miss, len(d2q_vals), 100.0 * miss / max(len(d2q_vals), 1)))
    if alig_vals:
        print("研究层对齐覆盖率：样本 %d 份，== 0.00 的 %d 份（%.0f%%），"
              "中位 %.2f" % (len(alig_vals), alig0,
                             100.0 * alig0 / len(alig_vals),
                             st.median(alig_vals)))
    print()
    print("截断跑（前 10）：")
    for x in cut_runs[:10]:
        print("   ", x)


if __name__ == "__main__":
    main()
