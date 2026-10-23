# -*- coding: utf-8 -*-
"""元 DGTF **本真数据**提取与对比分析器（不加任何外部评分）。

★ 为什么单独写这个：项目里已经有一堆「尺子」——事实清单判分、中上游题评尺、
  开放题二选一探针、负向探针、机制触发审计。它们都是**架在元DGTF 外面的
  外部标准**，每一把都自带噪声（法官漂移、指标饱和、清单设计者的盲区）。
  踩过太多次：X/Y 饱和到 89 份里 84 份恒等、法官自身矛盾 1~3/11 条大于组间差、
  净分饱和。结论建立在尺子上，尺子一钝结论就塌。

  所以这里只提取**元DGTF 自己跑出来的东西**：
    · 调度：route 实际跑了哪几层、缺了哪几层、跳过哪几层
    · 每层：跑了几圈、为什么停（stop_reason）、是不是空转（idle）
    · 判定：decidability / 判定源 / 池判与外判是否分叉 / 不可判定里几条没追溯
    · 成本：llm_calls / tokens / 耗时（日志尾部原值，不重算）
    · 产物结构量：长度、章节数、挂账条数、张力条数、有无汇流圈
  这些不经过任何法官，没有评分，是机制自己留下的痕迹。

用法：
  python _native_analyze.py "v60_up_law_*.log" "v60_up_biz_*.log"
      ↑ 每个 glob 是一道题（组），组内按 mode 分行对比

  python _native_analyze.py "v60_up_*.log" --by mode
      ↑ 不预设题，按 mode 分组（用于跨题看模式自身的形态）

判据（沿用预注册规矩，不许事后改）：
  组间差 > 组内极差 才许说「A 比 B 高/低」；
  组内极差未知（每格只有 1 次观测）时，一律标「线索」，不许升格成结论。
"""
import ast
import glob
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAYERS = ("0", "1", "both", "all")

# ---- 日志尾部字段（都是 _run_v60.py 写出来的原值） ----
P_TAG = re.compile(r"^tag=(\S+)\s+mode=(\S+)\s+rounds=(\S+)", re.M)
P_TIME = re.compile(r"耗时\s+(\d+)s\s*=\s*([\d.]+)min")
P_COST = re.compile(r"llm_calls=(\d+)\s+tokens=(\d+)")
P_RAN = re.compile(r"dispatch\.ran=(\[[^\]]*\])")
P_MISS = re.compile(r"dispatch\.missing=(\[[^\]]*\])")
P_SKIP = re.compile(r"dispatch\.skipped=(\[[^\]]*\])")
P_DEC = re.compile(r"^decidability=(\S+)", re.M)
P_SRC = re.compile(r"^dec_src=(\S+)", re.M)
P_DIV = re.compile(r"分叉=(\w+)\(")
P_UNTR = re.compile(r"无追溯=(\d+)")
P_VIEWS = re.compile(r"views=(\[[^\]]*\])")
P_LC = re.compile(r"layer_contribution=(\{.*\})")
P_OUT = re.compile(r"^产物=(\S+)", re.M)
P_FAIL = re.compile(r"^❌ 产物落盘失败", re.M)


def parse_log(path: Path):
    txt = path.read_text(encoding="utf-8", errors="replace")
    d = {"log": path.name}
    m = P_TAG.search(txt)
    if not m:
        return None
    d["tag"], d["mode"], d["rounds"] = m.group(1), m.group(2), m.group(3)
    if (m := P_TIME.search(txt)):
        d["sec"], d["min"] = int(m.group(1)), float(m.group(2))
    if (m := P_COST.search(txt)):
        d["calls"], d["tokens"] = int(m.group(1)), int(m.group(2))
    for k, p in (("ran", P_RAN), ("missing", P_MISS), ("skipped", P_SKIP),
                 ("views", P_VIEWS)):
        if (m := p.search(txt)):
            d[k] = ast.literal_eval(m.group(1))
    if (m := P_DEC.search(txt)):
        d["decidability"] = m.group(1)
    if (m := P_SRC.search(txt)):
        d["dec_src"] = m.group(1)
    if (m := P_DIV.search(txt)):
        d["divergent"] = m.group(1)
    if (m := P_UNTR.search(txt)):
        d["untraced"] = int(m.group(1))
    if (m := P_LC.search(txt)):
        try:
            d["lc"] = ast.literal_eval(m.group(1))
        except Exception:
            d["lc"] = {}
    if (m := P_OUT.search(txt)):
        d["out"] = m.group(1)
    d["save_failed"] = bool(P_FAIL.search(txt))
    return d


# ---- 产物结构量（同样是元DGTF 自己写的，不是评分） ----
def parse_output(p: str):
    """从产物 md 里数几个**结构量**。

    只数「有没有、有几条」这种不依赖语义的量，不评价好坏。
    """
    if not p:
        return {}
    fp = Path(p)
    if not fp.is_absolute():
        fp = HERE / p
    if not fp.exists():
        return {"exists": False}
    txt = fp.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"^## ", txt, flags=re.M)[1:]
    res = {
        "exists": True,
        "chars": len(txt),
        "sections": len(blocks),
    }
    want = {
        "挂账": "延迟债务",
        "张力": "张力与悬空线头",
        "池": "池",
    }
    for key, kw in want.items():
        n = 0
        for b in blocks:
            if kw in b.split("\n", 1)[0]:
                n += sum(1 for ln in b.split("\n") if ln.startswith("- "))
        res[key] = n
    res["汇流圈"] = any("汇流圈" in b.split("\n", 1)[0] for b in blocks)
    return res


def fmt_row(d, keys):
    cells = []
    for k in keys:
        v = d.get(k)
        if v is None:
            cells.append("-")
        elif isinstance(v, bool):
            cells.append("是" if v else "否")
        else:
            cells.append(str(v))
    return cells


def stop_kind(s):
    """把 stop_reason 归成几类。**顺序敏感**：空转类要先判，
    否则「自省连续 3 圈点名同一批问题未消化（层内空转）」会被后面的
    关键词抢走，空转率就被记成别的。"""
    s = s or ""
    for kw, name in (("层内空转", "自省空转"), ("自省连续", "自省空转"),
                     ("无新维度", "饱和判定"), ("结构饱和度", "饱和判定"),
                     ("无新 &", "沉淀完毕"), ("无新&", "沉淀完毕"),
                     ("悬置决定稳定", "安住稳定"), ("自然安住", "安住稳定"),
                     ("体力耗尽", "走满未触发")):
        if kw in s:
            return name
    return "其他"


def print_profile(rows):
    """分布画像：**描述性**统计，不做组间对比。

    全量日志混着不同题、不同圈数、不同层数，任何「A 比 B 好」的对比都被
    混淆变量淹没（实测：calls 组间差 53.8 < 组内极差 356）。所以全量只
    用来画「元 DGTF 长什么样」，效果对比必须回到同题同圈数的受控批。
    """
    from collections import Counter
    print(f"\n{'=' * 78}\n【分布画像】全量只画形态，不比效果"
          f"（混淆变量未控制，组间对比无效）\n{'=' * 78}")
    n = len(rows)
    print(f"样本 {n} 份\n")

    # 1. 层数
    c = Counter(len(r.get("ran") or []) for r in rows)
    print("· 实际跑了几层：")
    for k in sorted(c):
        print(f"    {k} 层：{c[k]:>3} 份 ({c[k] / n * 100:.0f}%)")

    # 2. 每层：跑了没 / 圈数 / 空转率 / 停因
    has_lc = [r for r in rows if r.get("lc")]
    print(f"\n· 每层：平均圈数 · 空转率 · 停因分布"
          f"  （★ 只覆盖 {len(has_lc)}/{n} 份 —— layer_contribution 是 "
          f"v1.21.63 才加的字段，更早的日志没有，别拿这个比例当全量）")
    for L in LAYERS:
        got = [r for r in rows
               if (r.get("lc") or {}).get(L)
               and (r["lc"][L].get("rounds") or 0) > 0]
        if not got:
            print(f"    {L:<5} 无样本")
            continue
        rounds = [r["lc"][L].get("rounds") or 0 for r in got]
        idle = sum(1 for r in got if r["lc"][L].get("idle"))
        kinds = Counter(stop_kind(r["lc"][L].get("stop")) for r in got)
        top = "、".join(f"{k}{v}" for k, v in kinds.most_common())
        print(f"    {L:<5} {len(got):>3}/{len(has_lc)} 份  "
              f"均 {sum(rounds)/len(rounds):.1f} 圈"
              f"  空转 {idle}/{len(got)} ({idle/len(got)*100:.0f}%)  {top}")

    # 3. 判定
    print("\n· 可判定性分布：")
    c = Counter(r.get("decidability") or "缺失" for r in rows)
    for k, v in c.most_common():
        print(f"    {k:<14}{v:>4} 份 ({v / n * 100:.0f}%)")
    div = sum(1 for r in rows if r.get("divergent") == "True")
    print(f"    池判/外判分叉：{div}/{n} ({div / n * 100:.0f}%)")
    ut = [r.get("untraced") for r in rows if r.get("untraced") is not None]
    if ut:
        print(f"    不可判定里没追溯的条数：均 {sum(ut)/len(ut):.2f}，"
              f"最大 {max(ut)}（>0 的 {sum(1 for x in ut if x)}/{len(ut)} 份）")

    # 4. ★ 重复观测覆盖：哪些格子有误差棒
    print("\n· 重复观测覆盖（★ 这决定哪些格子将来能做统计断言）：")
    cells = {}
    for r in rows:
        k = r["tag"]
        if k.endswith("_" + r["mode"]):
            k = k[:-(len(r["mode"]) + 1)]
        cells.setdefault((k, r["mode"]), []).append(r["log"])
    multi = {k: v for k, v in cells.items() if len(v) > 1}
    print(f"    格子总数 {len(cells)}，有重复观测的 {len(multi)} 个 "
          f"({len(multi) / len(cells) * 100:.0f}%)")
    if multi:
        for (q, m), logs in sorted(multi.items(),
                                   key=lambda kv: -len(kv[1]))[:15]:
            print(f"      {q:<22} {m:<7} n={len(logs)}")
        if len(multi) > 15:
            print(f"      …… 还有 {len(multi) - 15} 个")
    else:
        print("    ⚠️ 一格重复都没有 → 现在手上**没有任何误差棒**，")
        print("       所有组间差都只能当线索。要结论先补重复观测。")


def print_cross_consistency(buckets, metrics):
    """★ 跨题一致性：每题内部按 mode 排序，看 N 道题是不是给出同一个序。

    为什么要有这一段：受控批里每格只有 1 次观测，没有组内极差，
    「组间差 > 组内极差」这条判据根本没法执行，所有对比卡在「线索」上。
    但**跨题**能补一档：每格仍是 1 次观测，可**题是独立重复的**——N 道题
    各自独立排出同一个序，不是巧合的概率比单份高。

    ⚠️ 比单份点估计强一档，**仍不是结论**：题不是随机抽样（才 2~3 道），
    而且挑两道题凑出想要的序太容易。判据写死：
      ≥3 题且全部一致 → 够格叫「稳定排序」，仍不许写成因果；
      只有 2 题一致 → 只叫「不矛盾」，不许升格。
    """
    print(f"\n{'-' * 78}\n【跨题一致性】每题内部排一遍 mode 的序，看题之间矛不矛盾"
          f"\n{'-' * 78}")
    any_run = False
    for key, name in metrics:
        ranks = {}
        for bn, rows in buckets.items():
            vals = {r["mode"]: r[key] for r in rows if r.get(key) is not None}
            if len(vals) >= 2:
                ranks[bn] = vals
        if len(ranks) < 2:
            continue
        any_run = True
        print(f"\n· {name}：")
        orders = []
        for bn, vals in sorted(ranks.items()):
            desc = sorted(vals.items(), key=lambda kv: -kv[1])
            orders.append(tuple(m for m, _ in desc))
            print(f"    {bn:<22} " +
                  "  ".join(f"{m}={v:g}" for m, v in desc))
        same = len(set(orders)) == 1
        if same and len(orders) >= 3:
            print(f"    ✅ {len(orders)}/{len(orders)} 题排序完全一致"
                  f" → 够格叫「稳定排序」（仍非因果结论）")
        elif same:
            print(f"    ⚠️ {len(orders)}/{len(orders)} 题排序一致，但只有 "
                  f"{len(orders)} 题 → 只能叫「不矛盾」，不许升格")
        else:
            print(f"    ❌ 排序不一致：{sorted(set(orders))}"
                  f" → 这个指标上没有跨题信号")

    # 「有没有」型：汇流圈这种布尔字段，不看大小看有无
    for key, name in (("out_汇流圈", "有无汇流圈"),):
        tab = {}
        for bn, rows in buckets.items():
            for r in rows:
                if r.get(key) is not None:
                    tab.setdefault(bn, {})[r["mode"]] = r[key]
        if len(tab) >= 2:
            any_run = True
            print(f"\n· {name}：")
            pats = []
            for bn, v in sorted(tab.items()):
                pat = tuple(sorted(m for m, has in v.items() if has))
                pats.append(pat)
                print(f"    {bn:<22} 有汇流圈的 mode：{pat or '（无）'}")
            ok = len(set(pats)) == 1
            print(f"    {'✅' if ok else '❌'} "
                  f"{'跨题一致' if ok else '跨题不一致'}（{len(pats)} 题）"
                  + ("，但只有 2 题 → 只作线索" if ok and len(pats) < 3 else ""))
    if not any_run:
        print("\n（没有可跨题排序的指标：每个题里只有一种配置）")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    by_mode = "--by" in sys.argv and "mode" in sys.argv
    if not args:
        print(__doc__)
        return 1

    groups = []
    for g in args:
        files = sorted(Path(f) for f in glob.glob(str(HERE / g)))
        rows = [r for f in files if (r := parse_log(f))]
        if rows:
            groups.append((g, rows))
    if not groups:
        print("没有解析到任何日志，检查 glob")
        return 1

    # 产物结构量
    for _, rows in groups:
        for r in rows:
            r.update({f"out_{k}": v for k, v in
                      parse_output(r.get("out", "")).items()})

    # ---------- 1. 明细：每一格一行 ----------
    keys = ["tag", "mode", "rounds", "calls", "tokens", "min",
            "ran", "missing", "skipped",
            "decidability", "dec_src", "divergent", "untraced",
            "out_chars", "out_sections", "out_挂账", "out_张力", "out_汇流圈"]
    head = ["tag", "mode", "圈", "calls", "tokens", "min",
            "跑了", "缺", "跳", "判定", "判定源", "分叉", "无追溯",
            "字数", "节数", "挂账", "张力", "汇流"]
    for gname, rows in groups:
        print(f"\n{'=' * 78}\n【{gname}】{len(rows)} 份\n{'=' * 78}")
        w = [max(len(str(h)), *(len(str(fmt_row(r, keys)[i]))
                                for r in rows))
             for i, h in enumerate(head)]
        print("  ".join(h.ljust(w[i]) for i, h in enumerate(head)))
        for r in rows:
            print("  ".join(c.ljust(w[i]) for i, c in
                            enumerate(fmt_row(r, keys))))
            if r.get("save_failed"):
                print("     ⚠️ 该份产物落盘失败，产物列不可用")

    # ---------- 2. 每层：跑了几圈 / 停在哪 / 空转没 ----------
    print(f"\n{'=' * 78}\n【层贡献】每层跑了几圈、为什么停、是不是空转"
          f"\n{'=' * 78}")
    print(f"{'格':<26}" + "".join(f"{L + ' 圈':>7}" for L in LAYERS)
          + "   停因（简）")
    for gname, rows in groups:
        for r in rows:
            lc = r.get("lc") or {}
            cells = []
            stops = []
            for L in LAYERS:
                info = lc.get(L)
                if not info:
                    cells.append("-")
                    continue
                cells.append(f"{info.get('rounds', '?')}"
                             + ("*" if info.get("idle") else ""))
                if info.get("stop"):
                    stops.append(f"{L}:{info['stop'][:14]}")
            print(f"{r['tag'] + '/' + r['mode']:<26}"
                  + "".join(c.rjust(7) for c in cells)
                  + "   " + " | ".join(stops))
    print("  （* = 该层空转；「-」= 这一层没跑）")

    # ---------- 2.5 全量分布画像 ----------
    all_rows = [r for _, rows in groups for r in rows]
    print_profile(all_rows)

    # ---------- 3. 组间对比 + 能不能说 ----------
    print(f"\n{'=' * 78}\n【对比与判据】\n{'=' * 78}")
    # ★ 分组键必须是「题」，不是 glob：一个 glob 往往就把一整批都装进来了，
    #   按 glob 分就只剩一个桶，所有指标都被 `len(stat)<2` 跳掉，对比段全空。
    #   题 key 从 tag 里剥掉末尾的模式后缀（up_law_A + mode=A → up_law），
    #   剥不掉就用原 tag（up_tech 这种本来就没带模式名）。
    buckets = {}
    for _, rows in groups:
        for r in rows:
            if by_mode:
                k = r["mode"]
            else:
                k = r["tag"]
                if k.endswith("_" + r["mode"]):
                    k = k[:-(len(r["mode"]) + 1)]
            buckets.setdefault(k, []).append(r)
    label = "模式" if by_mode else "题"
    print(f"分组维度：{label}（{len(buckets)} 组）\n")

    metrics = [("calls", "calls"), ("tokens", "tokens"), ("min", "耗时min"),
               ("out_chars", "产物字数"), ("out_挂账", "挂账条数"),
               ("out_张力", "张力条数")]
    for key, name in metrics:
        stat = {}
        for bn, rows in buckets.items():
            vals = [r.get(key) for r in rows if r.get(key) is not None]
            if not vals:
                continue
            stat[bn] = (sum(vals) / len(vals), min(vals), max(vals), len(vals))
        if len(stat) < 2:
            continue
        means = {k: v[0] for k, v in stat.items()}
        spread = max(means.values()) - min(means.values())
        # 组内极差：只有在同一格有 ≥2 次观测时才存在
        inner = max((v[2] - v[1]) for v in stat.values())
        reps = max(v[3] for v in stat.values())
        n_obs = sum(v[3] for v in stat.values())
        has_rep = n_obs > len(stat)
        print(f"· {name}：")
        for bn, (mu, lo, hi, n) in sorted(stat.items()):
            print(f"    {bn:<26} 均 {mu:>10.1f}  "
                  f"[{lo}~{hi}]  n={n}")
        print(f"    组间差 = {spread:.1f}；组内极差 = "
              f"{inner if has_rep else '未知（每格 1 次观测）'}")
        if has_rep and spread > inner:
            print("    ✅ 组间差 > 组内极差 → 可以断言")
        elif has_rep:
            print("    ⚠️ 组间差 ≤ 组内极差 → 噪声内，不许断言")
        else:
            print("    ⚠️ 无重复观测 → 只作**方向线索**，不许写成结论")
        print()

    # ---------- 3.5 跨题一致性（按题分组时才有意义） ----------
    if not by_mode:
        print_cross_consistency(buckets, metrics)

    # ---------- 4. 缺口 ----------
    print(f"{'=' * 78}\n【数据缺口】\n{'=' * 78}")
    gaps = []
    for gname, rows in groups:
        for r in rows:
            if r.get("missing"):
                gaps.append(f"{r['tag']}/{r['mode']}：missing={r['missing']}")
            if r.get("save_failed"):
                gaps.append(f"{r['tag']}/{r['mode']}：产物落盘失败")
            if not r.get("lc"):
                gaps.append(f"{r['tag']}/{r['mode']}：layer_contribution 缺失")
            if r.get("decidability") is None:
                gaps.append(f"{r['tag']}/{r['mode']}：decidability 缺失")
    print("\n".join(gaps) if gaps else "无")
    return 0


if __name__ == "__main__":
    sys.exit(main())
