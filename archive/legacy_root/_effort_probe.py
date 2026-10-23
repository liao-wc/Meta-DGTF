"""[半持久] thinking effort 怎么选：关闭 / low / high / max 四档的成本与正确率。

为什么重做一轮：上一批题（6 道）两种模式都 6/6 —— **天花板饱和**，
那样的题分不出档位，拿它选参数是自欺。这轮换区分度高、答案可判定的题。

设计要点：
  - **带非思考基线**：只比 low/high/max 只能说"相对谁"，比不出"值不值"。
  - **不给思考模式传 temperature**：那是非思考路径的参数，传了可能被拒
    或被静默忽略，两边不要混着用。非思考组给 temperature=0.0 求稳。
  - **每题两份重复**：单点不算观测。
  - **末尾做饱和度自检**：三档全对的题会被点名，避免又拿打平的题下结论。

由 _auto_pipeline.py 阶段2 调用。
"""
import os
import re
import statistics
from concurrent.futures import ThreadPoolExecutor

env = {}
for ln in open('.env', 'r', encoding='utf-8'):
    m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)', ln)
    if m and not ln.strip().startswith('#'):
        env[m.group(1)] = m.group(2).strip().strip('"').strip("'")

import openai

PROBE_MODEL = os.environ.get('PROBE_MODEL', 'deepseek-flash').strip()

cli = openai.OpenAI(api_key=env['DGTF_API_KEY'],
                    base_url=env.get('DGTF_BASE_URL'), timeout=180)

# 刻意挑**容易答错**的多步题，避免天花板饱和
Q = [
    ("时钟夹角", "3 点 15 分，时针和分针的夹角是多少度？只回答数字（度）。", "7.5"),
    ("集合容斥", "一个班 40 人，参加数学竞赛 25 人，参加物理竞赛 20 人，"
                 "两项都参加 10 人。两项都没参加的有几人？只回答数字。", "5"),
    ("逆运算", "一个数加上 7 之后再乘以 3，再减去 5，结果是 40。"
               "原来的数是多少？只回答数字。", "8"),
    ("涨跌陷阱", "某商品先涨价 20%，再降价 20%，"
                 "最终价格是原价的百分之几？只回答数字。", "96"),
    ("星期推算", "已知 2026 年 10 月 2 日是星期五。"
                 "2026 年 12 月 25 日是星期几？只回答星期几。", "星期五"),
    ("相遇行程", "A、B 两地相距 120 km，甲从 A 以 40 km/h 出发，"
                 "乙从 B 以 60 km/h 同时相向而行。几小时后相遇？只回答数字。", "1.2"),
    ("年龄倍数", "父亲比儿子大 28 岁。5 年后，父亲的年龄是儿子的 3 倍。"
                 "儿子今年几岁？只回答数字。", "9"),
    ("合作工期", "一项工程甲单独做需 10 天，乙单独做需 15 天。"
                 "两人合作需要几天？只回答数字。", "6"),
]

# (标签, extra_body, 是否给 temperature)
ARMS = [
    ("off",  {'thinking': {'type': 'disabled'}}, True),
    ("low",  {'thinking': {'type': 'enabled', 'effort': 'low'}}, False),
    ("high", {'thinking': {'type': 'enabled', 'effort': 'high'}}, False),
    ("max",  {'thinking': {'type': 'enabled', 'effort': 'max'}}, False),
]
LABELS = [a[0] for a in ARMS]
REPS = 2


def once(name, q, ans, label, extra, use_temp):
    kw = dict(model=PROBE_MODEL,
              messages=[{'role': 'user', 'content': q}],
              max_tokens=3000,
              extra_body=extra)
    if use_temp:
        kw['temperature'] = 0.0
    try:
        r = cli.chat.completions.create(**kw)
        c = (r.choices[0].message.content or '').strip()
        u = r.usage
        rc = getattr(r.choices[0].message, 'reasoning_content', None) or ''
        return {
            "q": name, "label": label, "hit": 1 if ans in c else 0,
            "out": getattr(u, 'completion_tokens', 0) or 0,
            "in": getattr(u, 'prompt_tokens', 0) or 0,
            "rc": len(rc),
            "raw": c[:40],
        }
    except Exception as e:
        return {"q": name, "label": label, "hit": 0, "out": 0, "in": 0,
                "rc": 0, "raw": f"ERR {type(e).__name__}: {str(e)[:60]}"}


jobs = [(n, q, a, lab, ex, ut) for n, q, a in Q
        for lab, ex, ut in ARMS for _ in range(REPS)]
print(f"模型={PROBE_MODEL}  共 {len(jobs)} 次调用（{len(Q)} 题 × {len(ARMS)} 档 × {REPS} 次）…",
      flush=True)
with ThreadPoolExecutor(max_workers=4) as ex:
    rows = list(ex.map(lambda t: once(*t), jobs))

errs = [r for r in rows if r["raw"].startswith("ERR")]
if errs:
    print(f"⚠️ {len(errs)}/{len(rows)} 次调用失败，样本不可全信：")
    kinds = {}
    for r in errs:
        kinds[r["raw"][:40]] = kinds.get(r["raw"][:40], 0) + 1
    for k, v in kinds.items():
        print(f"   {v:3d}× {k}")

print(f"\n{'题目':10s}" + "".join(f"{lab:>14s}" for lab in LABELS))
print("-" * (10 + 14 * len(LABELS)))
agg = {lab: {"hit": [], "out": [], "inn": []} for lab in LABELS}
for n, q, a in Q:
    line = f"{n:10s}"
    for lab in LABELS:
        rs = [r for r in rows if r["q"] == n and r["label"] == lab]
        hits = sum(r["hit"] for r in rs)
        agg[lab]["hit"].append(hits)
        agg[lab]["out"] += [r["out"] for r in rs]
        agg[lab]["inn"] += [r["in"] for r in rs]
        line += f"{str(hits) + '/' + str(len(rs)):>14s}"
    print(line)
print("-" * (10 + 14 * len(LABELS)))

print(f"\n{'档位':8s}{'正确率':>12s}{'output/次(中位)':>18s}"
      f"{'input/次(中位)':>16s}{'相对输出成本':>14s}")
base = None
for lab in LABELS:
    hits = agg[lab]["hit"]
    tot_m = sum(hits)
    denom = len(Q) * REPS
    mo = statistics.median(agg[lab]["out"])
    mi = statistics.median(agg[lab]["inn"])
    if base is None:
        base = mo or 1
    print(f"{lab:8s}{tot_m}/{denom}={tot_m/denom*100:5.1f}%"
          f"{mo:>16.0f}{mi:>16.0f}{mo/base:>13.1f}x")

print("\n每题四档是否全一致（一致=该题没区分度，不能拿来选参数）：")
same = 0
for n, q, a in Q:
    hs = {lab: sum(r["hit"] for r in rows
                   if r["q"] == n and r["label"] == lab) for lab in LABELS}
    if len(set(hs.values())) == 1:
        same += 1
        print(f"   {n:10s} 四档都 {hs['off']}/{REPS} —— 无区分度")
    else:
        print(f"   {n:10s} {hs}")
print(f"→ {same}/{len(Q)} 题四档打平")

# 有区分度的题集合上的正确率才是能用的判据
disc = [n for n, q, a in Q
        if len({sum(r["hit"] for r in rows if r["q"] == n and r["label"] == lab)
                for lab in LABELS}) > 1]
if disc:
    print(f"\n只在 {len(disc)} 道有区分度的题上重算：")
    for lab in LABELS:
        tot = sum(r["hit"] for r in rows
                  if r["q"] in disc and r["label"] == lab)
        den = len(disc) * REPS
        mo = statistics.median([r["out"] for r in rows
                                if r["q"] in disc and r["label"] == lab])
        print(f"   {lab:6s} {tot}/{den}={tot/den*100:5.1f}%   output中位 {mo:.0f}")
else:
    print("\n⚠️ 没有一题被档位分开 —— 这批题在本任务上整体无区分度，"
          "不能据此选 effort。")
