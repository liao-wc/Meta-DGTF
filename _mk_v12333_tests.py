#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.33：yaml 补 auto.bandit + 第三批判据/探针/变异体。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ① yaml: auto.bandit
p = HERE / "dgtf_config.yaml"
b = p.read_bytes()
is_crlf = b.count(b"\r\n") == b.count(b"\n") and b.count(b"\r\n") > 0
y = b.decode("utf-8").replace("\r\n", "\n")
_anchor = "  history_halflife_days: 14\n"
assert y.count(_anchor) == 1, y.count(_anchor)
y = y.replace(_anchor, _anchor + """  # 【v1.23.33】预算 bandit（默认 false = 关 ⇒ 零行为差）。
  #   true 时用 UCB1-with-cost 在每层圈数上限三档（3/4/6）间选择；
  #   奖励 = 职责度中位 − cost_w ×（tokens/1000）。探索会故意选较差档。
  bandit:
    enabled: false
    cost_w: 0.3
    c: 1.0
""", 1)
p.write_bytes((y.replace("\n", "\r\n") if is_crlf else y).encode("utf-8"))
print("yaml auto.bandit 已补")

# ② 冒烟判据：第三批断言
ADD_JUDGE = '''
    # ── 第三批（机制级：anytime / 发散+指针 / bandit / compact / 锚点 / 裁决 / 陈旧）──
    for _n, _w in (("def stitched_hoeffding_lower(", "anytime 置信序列"),
                   ("def anytime_majority_decided(", "anytime 判据"),
                   ("def divergence_state(", "发散三态"),
                   ("def best_round_index(", "回滚指针"),
                   ("class BudgetBandit:", "预算 bandit"),
                   ("def compact_plan(", "compact 预算"),
                   ("def anchor_offline_check(", "锚点离线验证"),
                   ("def anchor_interest_hint(", "锚点内部批判"),
                   ("def anchor_evidence_standard(", "分级证明标准"),
                   ("def adjudication_aspect(", "裁决维度"),
                   ("def belief_staleness(", "信念陈旧度"),
                   ("anytime_ok=_any_ok", "anytime 接线")):
        if _n not in src:
            bad.append("[源码] %s 缺失（%r）" % (_w, _n))
    # anytime：12 个 1 ⇒ 下界 > 0.5 判「已确立」；3 个 1 ⇒ 样本不足不判（负对照）
    _lb = mod.stitched_hoeffding_lower([1] * 12)
    if not (_lb and _lb["lower"] > 0.5):
        bad.append("[anytime] 全 1 序列下界未 > 0.5（%r）" % (_lb,))
    if mod.anytime_majority_decided([1, 1, 1])[0]:
        bad.append("[anytime·负] 3 个样本就判「已确立」（过早）")
    if mod.stitched_hoeffding_lower([1]) is not None:
        bad.append("[anytime] n<2 未返回 None")
    # 发散/停滞/指针
    _dv = mod.divergence_state([1, 1, 2, 4, 8, 16])
    if not (_dv and _dv["state"] == "发散"):
        bad.append("[发散] 方差上升序列未判发散（%r）" % (_dv,))
    if mod.divergence_state([3] * 6)["state"] != "停滞":
        bad.append("[发散·负] 平稳序列未判停滞")
    if mod.best_round_index([1, 3, 2, 0]) != 2:
        bad.append("[指针] 历史最佳圈指针算错")
    # bandit：未试过的臂优先（确定性探索）；更新后仍可选
    _bb = mod.BudgetBandit([{"rounds": 3}, {"rounds": 4}, {"rounds": 6}])
    _p0 = _bb.pick()
    if not (_p0["explore"] is True and _p0["index"] == 0):
        bad.append("[bandit] 首挑未走确定性探索（%r）" % (_p0,))
    _bb.update(0, 0.9, 1.0)
    if _bb.n[0] != 1 or abs(_bb.mean[0] - 0.9) > 1e-9:
        bad.append("[bandit] 更新未生效（%r/%r）" % (_bb.n, _bb.mean))
    # compact（率失真口径）
    if not mod.compact_plan(900, 1000)["over"]:
        bad.append("[compact] 超预算未判 over")
    if mod.compact_plan(300, 1000)["over"]:
        bad.append("[compact·负] 预算内被误判超")
    # 锚点三项
    if not mod.anchor_offline_check("https://www.gov.cn/a")["ok"]:
        bad.append("[锚点] 合法 URL 未过离线检查")
    if mod.anchor_offline_check("htp:/x")["ok"]:
        bad.append("[锚点·负] 畸形 URL 竟通过")
    if "媒体" not in mod.anchor_interest_hint("https://blog.medium.com/x"):
        bad.append("[锚点·内部批判] 自媒体域名未识别")
    if mod.anchor_evidence_standard("causal")["standard"] != "beyond_reasonable_doubt":
        bad.append("[法学] 因果 claim 未用最高证明标准")
    # 裁决维度 + 陈旧度
    if not mod.adjudication_aspect("口径矛盾", "按实测数据").strip():
        bad.append("[裁决维度] 未判出维度")
    _st = mod.belief_staleness({"id": "B", "status": "active",
                                "last_confirmed_round": 1}, 5)
    if not (_st["age"] == 4 and _st["stale_hint"] is True):
        bad.append("[陈旧度] 读数不对（%r）" % (_st,))

'''
for _f in ("_smk_v12332_fn.py", "smoke_test.py"):
    q = HERE / _f
    qb = q.read_bytes()
    _crlf = qb.count(b"\r\n") > 0 and qb.count(b"\r\n") == qb.count(b"\n")
    qs = qb.decode("utf-8").replace("\r\n", "\n")
    # 改名（版本语义）：判据函数名保持不变，只在 SRC 与注释上体现新版本
    anchor = "    # ── 真实入口 + 不变量 ──\n"
    assert qs.count(anchor) == 1, (_f, qs.count(anchor))
    qs = qs.replace(anchor, ADD_JUDGE + anchor, 1)
    q.write_bytes((qs.replace("\n", "\r\n") if _crlf else qs).encode("utf-8"))
    print("第三批判据已补", _f)

# ③ smoke_test：SRC 指向 v1.23.33
q = HERE / "smoke_test.py"
qb = q.read_bytes()
_crlf = qb.count(b"\r\n") > 0 and qb.count(b"\r\n") == qb.count(b"\n")
qs = qb.decode("utf-8").replace("\r\n", "\n")
qs = qs.replace('SRC = HERE / "元DGTF-V1.23.32.py"',
                'SRC = HERE / "元DGTF-V1.23.33.py"', 1)
q.write_bytes((qs.replace("\n", "\r\n") if _crlf else qs).encode("utf-8"))
print("smoke SRC → v1.23.33")

# ④ 探针：第三批 T15+
ADD_PROBE = '''
# ── T15~ 第三批（机制级）─────────────────────────────────
ok("T15 anytime：12 个 1 ⇒ 下界 > 0.5", m.stitched_hoeffding_lower([1]*12)["lower"] > 0.5)
ok("T15 anytime：3 个样本不判「已确立」（负对照）",
   not m.anytime_majority_decided([1, 1, 1])[0])
ok("T15 anytime：n<2 ⇒ None（不表态）", m.stitched_hoeffding_lower([1]) is None)
ok("T16 发散：方差上升 + 正 AC1 ⇒ 发散",
   m.divergence_state([1, 1, 2, 4, 8, 16])["state"] == "发散")
ok("T16 停滞（负对照）", m.divergence_state([3]*6)["state"] == "停滞")
ok("T16 回滚指针：历史最佳圈（1-based）", m.best_round_index([1, 3, 2, 0]) == 2)
_bb = m.BudgetBandit([{"rounds": 3}, {"rounds": 4}, {"rounds": 6}])
ok("T17 bandit：未试过的臂优先（确定性探索）",
   _bb.pick()["explore"] is True and _bb.pick()["index"] == 0)
_bb.update(0, 0.9, 1.0)
ok("T17 bandit：更新写入 mean/n", _bb.n[0] == 1 and abs(_bb.mean[0]-0.9) < 1e-9)
ok("T18 compact：率失真口径（超预算判 over）",
   m.compact_plan(900, 1000)["over"] and not m.compact_plan(300, 1000)["over"])
ok("T19 锚点离线：合法过 / 畸形拦",
   m.anchor_offline_check("https://www.gov.cn/a")["ok"]
   and not m.anchor_offline_check("htp:/x")["ok"])
ok("T20 锚点内部批判：自媒体 vs 公权力可区分",
   "媒体" in m.anchor_interest_hint("https://blog.medium.com/x")
   and "公权力" in m.anchor_interest_hint("https://www.stats.gov.cn/a"))
ok("T21 分级证明标准：因果用最高档",
   m.anchor_evidence_standard("causal")["standard"] == "beyond_reasonable_doubt")
ok("T22 裁决维度拆分", "/" in m.adjudication_aspect("口径矛盾", "按实测数据"))
ok("T23 信念陈旧度（不改四态）",
   m.belief_staleness({"id":"B","status":"active","last_confirmed_round":1}, 5)["stale_hint"])

'''
q = HERE / "_probe_v12332.py"
qs = q.read_text(encoding="utf-8")
qs = qs.replace('SRC = HERE / "元DGTF-V1.23.32.py"',
                'SRC = HERE / "元DGTF-V1.23.33.py"', 1)
_anchor = "# ── T9~T15 第二批 ──"
assert qs.count(_anchor) == 1
qs = qs.replace(_anchor, ADD_PROBE + _anchor, 1)
q.write_text(qs, encoding="utf-8", newline="\n")
print("探针已补第三批 + SRC → v1.23.33")

# ⑤ 变异体：M16+
MUT = '''    ("M16 anytime 恒判「已确立」",
     '    return bool(lb["lower"] > float(thr)), lb',
     '    return True, lb'),
    ("M17 发散检测恒判收敛",
     '    if v2 > 1.5 * v1 and ac1 > 0.2:\\n        state = "发散"',
     '    if False:\\n        state = "发散"'),
    ("M18 回滚指针恒取最后一圈",
     '    best = max(xs) if higher_is_better else min(xs)\\n    return xs.index(best) + 1',
     '    return len(xs)'),
    ("M19 bandit 不做探索（恒选 0 号臂）",
     '        if self.n[i] == 0:\\n            return float("inf")',
     '        if False:\\n            return float("inf")'),
    ("M20 compact 恒判不超预算",
     '    over = share > float(budget)',
     '    over = False'),
    ("M21 锚点离线检查恒通过",
     '    if not (u.startswith("http://") or u.startswith("https://")):',
     '    if False:'),
    ("M22 分级证明标准恒 preponderance",
     '    std, who = table.get(k, ("preponderance", "主张者举证"))',
     '    std, who = ("preponderance", "主张者举证")'),
    ("M23 陈旧度恒不提示",
     '            "stale_hint": bool(age is not None and age >= 3',
     '            "stale_hint": bool(False and age is not None and age >= 3'),
'''
q = HERE / "_mut_v12332.py"
qs = q.read_text(encoding="utf-8")
qs = qs.replace('SRC = HERE / "元DGTF-V1.23.32.py"',
                'SRC = HERE / "元DGTF-V1.23.33.py"', 1)
_old = '    ("M15 '
i = qs.index(_old)
j = qs.index("]", i)
qs = qs[:j] + MUT + qs[j:]
q.write_text(qs, encoding="utf-8", newline="\n")
print("变异体已补 M16~M23 + SRC → v1.23.33")
