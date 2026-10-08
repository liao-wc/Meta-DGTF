"""auto_plan 端到端验证（§7.15 预注册）。
写进 prompt 组 7 题 + 留出组 10 题，每组跑 3 次，看：
  J1 留出组 route 命中率   J2 同题 3 次一致性
  J3 硬规矩（不推 C / 元层>=5 / rounds in [4,6]）   J4 写进prompt组（仅对照）
"""
import importlib.util, json, sys, time, collections
from pathlib import Path

p = Path('元DGTF-V1.21.61.py').resolve()
spec = importlib.util.spec_from_file_location("dgtf", str(p))
m = importlib.util.module_from_spec(spec)
sys.modules['dgtf'] = m
spec.loader.exec_module(m)

IN_PROMPT = [
    ("欧盟AI法案", "2024 年欧盟 AI 法案对高风险 AI 系统规定了哪些合规要求？", "light"),
    ("IPv6", "IPv6 地址的长度是多少位？相比 IPv4，它的首部结构主要去掉了哪些字段？", "light"),
    ("GIL", "Python 的 GIL 是什么？它在 3.13 版本里有什么变化？", "light"),
    ("TLS", "HTTPS 的 TLS 握手过程包含哪几个步骤？", "light"),
    ("P=NP", "P=NP", {"light", "full"}),   # ★ 2026-10-01 修正：我原先标 light 是
    #   错的 —— P=NP 是未解决的开放数学难题，判 full 完全合理。这条预期是我
    #   犯的错，不是模型的错。改成二选一都算对，并在报告里明写。
    ("地铁效率", "怎么衡量一条城市地铁线路的运营效率？用什么指标，各自怎么取舍？", "light"),
    ("AI能否IC", "AI 能否独立完成数字 IC 设计流程？", "light"),
]

HOLDOUT = [
    ("人有灵魂吗", "人有灵魂吗", {"full"}),
    ("人生意义", "人生的意义是什么", {"full"}),
    ("自由意志", "自由意志是否存在？如果不存在，道德责任还能成立吗？", {"full"}),
    ("整体大于部分", "整体大于部分之和，这个命题本身可判定吗？", {"full"}),
    ("复杂问题整体", "复杂问题被拆成几个部分分别研究之后，剩下的那个「整体」到底是什么？", {"full"}),
    ("与AI相处", "在AI飞速发展的当下，我们如何与之相处", {"full"}),
    ("AI时代能力", "AI时代，我们最需要具备的能力是什么", {"full"}),
    ("外星文明", "宇宙中是否还有其他文明，人类文明在宇宙中是唯一吗？", {"full"}),
    ("团队决策", "怎么让一个团队的决策既快又不出错？", {"light", "no_meta"}),
    ("自证安全", "一个 AI 系统能否证明自己的输出是安全的？", {"light", "no_meta"}),
]

# ★ 2026-10-02 补预注册（在复跑**之前**写下，不是看完结果再改标签）。
#   prompt 的 route 判据已从「按题型」改成「是否自足」，其中一条直接反转：
#   取证题原来盼 light，现在**不许**给 light。受影响的预期标签必须跟着翻，
#   否则 J4 会用一个已被作废的期望去打分，越改越像变好。
#   机械推导规则（不参考任何已看到的结果）：
#     问外部事实/规格/现状 → 取证 → 盼 {no_meta, full}
#     框架自己推理就能答   → 自足 → 保持原预期
#     没有终审答案         → 开放 → 保持 full
NEW_EXP = {
    "欧盟AI法案": {"no_meta", "full"},   # 条文事实，取证
    "IPv6":      {"no_meta", "full"},   # 规格事实，取证
    "GIL":       {"no_meta", "full"},   # 3.13 现状事实，取证
    "TLS":       {"no_meta", "full"},   # 协议步骤事实，取证
    "AI能否IC":   {"light", "no_meta", "full"},  # 边界：既需行业现状也可推理，全收
}

ROUTE_KEY = {
    ("0", "1"): "light",
    ("0", "1", "both"): "no_meta",
    ("0", "1", "both", "all"): "full",
}


def key_of(route):
    return ROUTE_KEY.get(tuple(route), "other:" + ",".join(route))


def one(q):
    try:
        r = m.auto_plan(q, m.DEFAULT_CONFIG)
        return dict(route=key_of(r.get("route", [])), mode=r.get("mode"),
                    rounds=dict(r.get("rounds", {})),
                    max_calls=r.get("max_calls"), conf=r.get("confidence"),
                    reason=(r.get("reason") or "")[:80], err=None)
    except Exception as e:
        return dict(route="ERR", mode=None, rounds={}, max_calls=None,
                    conf=None, reason="", err=f"{type(e).__name__}: {e}")


def run_group(name, items, n=3):
    out = []
    for i, row in enumerate(items):
        tag, q = row[0], row[1]
        exp = row[2]
        runs = [one(q) for _ in range(n)]
        out.append(dict(tag=tag, q=q, exp=exp, runs=runs))
        n_diff = len({r["route"] for r in runs})
        print(f"  [{name}] {tag:12s} exp={str(exp):28s} -> "
              f"{[r['route'] for r in runs]}  mode={[r['mode'] for r in runs]}"
              f"{'  ✗ 不稳定' if n_diff > 1 else ''}")
        time.sleep(0.3)
    return out


print("=== auto_plan 验证开始 ===")
res_in = run_group("写进prompt", IN_PROMPT)
print()
res_out = run_group("留出", HOLDOUT)

OUT_PATH = sys.argv[1] if len(sys.argv) > 1 else '_autoplan_result.json'

json.dump({"in_prompt": res_in, "holdout": res_out},
          open(OUT_PATH, 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1, default=str)


def report(name, res):
    hit = stab = 0
    viol = []
    for row in res:
        exp = row["exp"]
        routes = [r["route"] for r in row["runs"]]
        majority = collections.Counter(routes).most_common(1)[0][0]
        if isinstance(exp, set):
            ok = majority in exp
        else:
            ok = majority == exp
        hit += ok
        stab += (len(set(routes)) == 1)
        for r in row["runs"]:
            if r["mode"] == "C":
                viol.append(f"{row['tag']}: 推了 C")
            if isinstance(r["rounds"], dict):
                al = r["rounds"].get("all")
                if isinstance(al, int) and al < 5:
                    viol.append(f"{row['tag']}: 元层 {al}")
                for k, v in r["rounds"].items():
                    if isinstance(v, int) and not (4 <= v <= 6):
                        viol.append(f"{row['tag']}: {k}层={v} 越界")
    n = len(res)
    print(f"\n--- {name} (n={n}) ---")
    print(f"  J1 命中率      : {hit}/{n} = {hit/n:.0%}")
    print(f"  J2 三次一致率  : {stab}/{n} = {stab/n:.0%}")
    print(f"  J3 硬规矩违反  : {len(viol)} 次 {viol[:6]}")
    return hit / n, stab / n, viol


print("\n=== 汇总 ===")
j4, s4, v4 = report("写进 prompt 组（J4，仅对照）", res_in)
j1, s2, v1 = report("留出组（J1 主判据）", res_out)

# J4 双口径：旧标签（题型时代）vs 新标签（自足时代，本次预注册）
_old = _new = 0
for row in res_in:
    if row["tag"] not in NEW_EXP:
        continue
    maj = collections.Counter([r["route"] for r in row["runs"]]).most_common(1)[0][0]
    exp_o = row["exp"] if isinstance(row["exp"], set) else {row["exp"]}
    _old += maj in exp_o
    _new += maj in NEW_EXP[row["tag"]]
_n = len(NEW_EXP)
print(f"\n  J4 细分：受 route 规则反转影响的 {_n} 题")
print(f"    旧标签口径（取证→light）  : {_old}/{_n}")
print(f"    新标签口径（取证→不light）: {_new}/{_n}   ← 本次预注册")

allv = v4 + v1
print(f"\n{'='*46}")
print(f"J1 留出组命中 ≥70%   : {j1:.0%}  {'✓ 过' if j1 >= .7 else '✗ 不过'}")
print(f"J2 同题三次一致 ≥80% : {max(s2, s4):.0%}~{min(s2, s4):.0%}  "
      f"{'✓ 过' if min(s2, s4) >= .8 else '✗ 不过'}")
print(f"J3 硬规矩违反 = 0    : {len(allv)} 次  {'✓ 过' if not allv else '✗ 不过'}")
print(f"J4 写进prompt组（对照）: {j4:.0%}  —— 达标不计功")
