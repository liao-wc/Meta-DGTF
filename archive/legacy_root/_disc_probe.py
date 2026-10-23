# -*- coding: utf-8 -*-
"""强迫二选一的辨别实验（判据事前写死在 `_disc_prereg.json`）。

上一把尺（逐条清单打分）的问题：开放题上法官自身矛盾 1~3/11~12 条，大于
组间差。逐条打分让法官每次都自由漂移；**强迫二选一**把漂移压到一个比特。

实验问的是形态本身："看得出四层那份多了一道环节吗？" —— 这正是「四层值不值
多一倍钱」唯一站得住的理由。它若读不出来，所有关于质量的辩护都要另找证据。

用法：
  python _disc_probe.py            # 跑 6 对真 + 2 对有效性对照
  python _disc_probe.py --only-validity
"""
import argparse
import importlib.util
import json
import random
import statistics as st
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent

PAIRS = [
    ("欧盟AI法案", "f1_2", "f1_4", "取证"),
    ("IPv6",      "f2_2", "f2_4", "取证"),
    ("TLS",       "f3_2", "f3_4", "取证"),
    ("自由意志",  "o1_2", "o1_4", "开放"),
    ("整体大于部分", "o2_2", "o2_4", "开放"),
    ("人有灵魂吗", "o3_2", "o3_4", "开放"),
]
# ★ 政策级对照：`auto_plan` 改了之后给开放题的组合，跟原四层比。
#   注意两者**差的不止层数**（新默认还换了 mode），所以这一组问的不是
#   "层数有没有用"，而是"**改完政策之后，读者照样看得出区别吗**"。
#   若 P 仍在 0.5 附近，说明省下来的钱确实是白省（没人吃亏）。
POLICY_PAIRS = [
    ("人有灵魂吗", "p1", "o3_4", "新默认"),
    ("自由意志",  "p2", "o1_4", "新默认"),
    ("整体大于部分", "p3", "o2_4", "新默认"),
]

VALIDITY = [("欧盟AI法案", "f1_2"), ("人有灵魂吗", "o3_2")], \
           [("IPv6", "f2_2"), ("自由意志", "o1_2")]

_SYS = ("你是严格的文本比较员。只看被给到的两份材料，不推测它们的生成过程。")

_PROMPT = """下面有两份材料（甲、乙），来自同一个问题的两次不同处理。

{probe}

只能回答三项之一："甲" / "乙" / "无法区分"。
- **必须真的有可指的区别才选甲或乙**，并且用一句话（≤25字）说明你依据的是什么。
- 如果只是"感觉哪份长一点/哪份热闹一点"，请答"无法区分"。
- 两份已经处理成完全相同的字数，字数不构成依据。

严格 JSON：{{"pick":"甲|乙|无法区分","why":"≤25字"}}

【材料·甲】
---
{a}
---

【材料·乙】
---
{b}
---
"""


def load_mod():
    spec = importlib.util.spec_from_file_location(
        "dgtf", str(HERE / "元DGTF-V1.21.61.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf"] = m
    spec.loader.exec_module(m)
    return m


def product_of(tag):
    """兼容 v60_<tag>_r*_<mode>.log 各种写法 —— 自动规划那批的日志名带的是
    规划出来的 mode（如 v60_p1_rauto_B.log），写死 `_r5_A` 会取不到产物。"""
    for lg in sorted(HERE.glob(f"v60_{tag}_r*.log")):
        for line in lg.read_text(encoding="utf-8",
                                 errors="replace").splitlines():
            if line.startswith("产物="):
                p = Path(line[3:].strip())
                if p.exists():
                    return p
    return None


def equal_len(a: str, b: str):
    n = min(len(a), len(b))
    return a[:n], b[:n], n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--only-validity", action="store_true")
    ap.add_argument("--policy", action="store_true",
                    help="比「改完政策后的自动组合」vs「原四层」（POLICY_PAIRS）")
    args = ap.parse_args()

    mod = load_mod()
    pre = json.load(open(HERE / "_disc_prereg.json", encoding="utf-8"))
    probes = pre["探针"]
    llm = mod.LLM(mod.load_config(str(HERE / "dgtf_config.yaml")))

    def one(judge_args):
        pa, pb, probe_text = judge_args
        p = _PROMPT.replace("{probe}", probe_text) \
                   .replace("{a}", pa).replace("{b}", pb)
        raw = llm.call(_SYS, p, temperature=0.0, max_tokens=300,
                       json_mode=True)
        d = llm.parse_json(raw) or {}
        return (d.get("pick") or "").strip(), (d.get("why") or "").strip()

    jobs = []          # (key, args)
    meta = []          # (key, side_of_full)
    _pairs = POLICY_PAIRS if args.policy else PAIRS
    for name, t_l, t_f, kind in _pairs:
        if args.only_validity:
            continue
        pl, pf = product_of(t_l), product_of(t_f)
        if not pl or not pf:
            print(f"  ⚠ {name}: 产物不齐，跳过")
            continue
        a, b, n = equal_len(pl.read_text(encoding="utf-8"),
                            pf.read_text(encoding="utf-8"))
        for pr in probes:
            for order in ("full_first", "light_first"):
                first, second = (b, a) if order == "full_first" else (a, b)
                for rep in range(args.reps):
                    key = (name, kind, pr["i"], order, rep, n)
                    jobs.append((key, (first, second, pr["问"])))
                    meta.append((key, order))

    print(f"=== 强迫二选一{'（政策级）' if args.policy else ''}：{len(jobs)} 次判定 "
          f"（{len(_pairs)} 对 × {len(probes)} 探针 × 2 顺序 × {args.reps} 重复）===")
    res = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for (key, _args), (pick, why) in zip(
                [(k, v) for k, v in jobs], ex.map(one, [j[1] for j in jobs])):
            res.append((key, pick, why))

    # ------- 主分析：把「full 在甲还是乙」还原出来 -------
    def score(rows):
        hits = []
        for key, pick, _why in rows:
            _name, _kind, _pi, order, _rep, _n = key
            if pick == "无法区分":
                hits.append(0.5)
            elif order == "full_first":
                hits.append(1.0 if pick == "甲" else 0.0)
            else:
                hits.append(1.0 if pick == "乙" else 0.0)
        ties = sum(1 for _k, p, _w in rows if p == "无法区分")
        return hits, ties

    def report(title, rows):
        hits, ties = score(rows)
        n = len(hits)
        if not n:
            return
        p = st.mean(hits)
        strict = [h for h in hits if h != 0.5]
        print(f"\n--- {title} ---")
        print(f"  判定次数 {n}　其中「无法区分」{ties}（{ties/n:.0%}）")
        print(f"  主分析（无法区分记 0.5）：P(选中四层) = {p:.2f}")
        if len(strict) >= 2:
            print(f"  次分析（剔除无法区分）：P = {st.mean(strict):.2f}"
                  f"（n={len(strict)}）")
        verdict = ("✓ 四层留下**可识别的形态差**" if p >= 0.70
                   else ("〜 差异够不上做决策依据" if p > 0.60
                         else "✗ **没有可检测的形态差**"))
        print(f"  按预注册门槛 → {verdict}")

    allrows = res
    report("全部 6 对", allrows)
    for kind in sorted({r[0][1] for r in allrows}):
        rows = [r for r in allrows if r[0][1] == kind]
        report(f"{kind}组（{len(rows)//(len(probes)*2*args.reps)} 对）", rows)
    print("\n--- 分探针（不合起来取平均） ---")
    for pr in probes:
        rows = [r for r in allrows if r[0][2] == pr["i"]]
        hits, ties = score(rows)
        print(f"  探针{pr['i']}：P={st.mean(hits):.2f}（n={len(hits)}，"
              f"无法区分 {ties}）　{pr['问'][:28]}…")

    # ------- 有效性对照：不同题的两个产物，若判「无区别」则整套作废 -------
    if not args.only_validity:
        print("\n=== 有效性对照（不同题的两份产物）===")
        vjobs = []
        for specs in VALIDITY:
            (n1, t1), (n2, t2) = specs
            p1, p2 = product_of(t1), product_of(t2)
            if not p1 or not p2:
                continue
            a, b, _ = equal_len(p1.read_text(encoding="utf-8"),
                                p2.read_text(encoding="utf-8"))
            vjobs.append(((n1, n2), (a, b, probes[0]["问"])))
        vres = []
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for (k, _a), (pick, _w) in zip(
                    vjobs, ex.map(one, [j[1] for j in vjobs])):
                vres.append((k, pick))
        ties = sum(1 for _k, p in vres if p == "无法区分")
        print(f"  {len(vres)} 次判定，其中「无法区分」{ties} 次 "
              f"= {ties/max(1,len(vres)):.0%}")
        print(f"  预注册作废线：>50% → "
              f"{'⚠️ 装置失灵，本轮全部结论作废' if ties > len(vres)/2 else '✓ 装置有效'}")

    out = HERE / ("_disc_result_policy.json" if args.policy
                  else "_disc_result.json")
    json.dump([{"name": k[0], "kind": k[1], "probe": k[2], "order": k[3],
                "rep": k[4], "trunc": k[5], "pick": p, "why": w}
               for k, p, w in res],
              open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n原始判定 → {out.name}")


if __name__ == "__main__":
    main()
