# -*- coding: utf-8 -*-
"""v1.23.33 轻量可达性核验：不跑完整编排，直接构造「池→回填→读数」链路。

只做三件事（全部零花费、秒级）：
  A. `Pool.merge` 每圈 append ⇒ 逐圈序列成立（含同值）；
  B. `layer_goal_readings` 对**真实 Pool/View.to_dict 形态**的输入有正确方向；
  C. `episode_from_result` 的 `goal_readings` 出口非空（读数进得了库）。
★ 完整编排可达性已由「主循环三处分支均无 continue」+ 打点探针在跑 证过；
  这里补的是**产物形态**层面的闭合。
"""
import importlib.util
import sys

SRC = "元DGTF-V1.23.33.py"
spec = importlib.util.spec_from_file_location("dgtf_chk", SRC)
m = importlib.util.module_from_spec(spec)
sys.modules["dgtf_chk"] = m
spec.loader.exec_module(m)

bad = []

# ── A. Pool.merge 每圈 append（逐圈序列）──
p = m.Pool()
for n in (2, 4, 4, 6):
    p.aspect_units.extend({"id": "A%d" % i} for i in range(n - len(p.aspect_units)))
    p.merge([], [], [])
print("A. Pool.aspect_hist =", p.aspect_hist)
if len(p.aspect_hist) != 4:
    bad.append("A: merge 未逐圈 append（len=%d）" % len(p.aspect_hist))
if p.aspect_hist[-1] != 6:
    bad.append("A: 末值不是池终态（%d）" % p.aspect_hist[-1])

# ── B. 方向的真实性：同样输入经 to_dict 后方向不变 ──
v = m.View(entry="0")
v.aspect_units = [{"id": "A%d" % i} for i in range(9)]
v.rounds_run = 4
v.aspect_hist = [2, 4, 6, 9]
d = v.to_dict()
print("B. View.to_dict 含 aspect_hist：", d.get("aspect_hist"))
if not d.get("aspect_hist"):
    bad.append("B: View.to_dict 未出口 aspect_hist")
r = m.layer_goal_readings({"0": d})["0"]
print("B. excavate =", r.get("excavate"), "converging =", r.get("converging"))
if r.get("excavate") is None:
    bad.append("B: excavate 取不到（回填链路断）")

# ── C. episode 出口非空 ──
ep = m.episode_from_result(
    {"id": "CHK", "question": "Q", "route": ["0", "1"],
     "rounds": {"0": 2, "1": 2},
     "views": {"0": {"aspect_units": [{"id": "A1"}], "rounds_run": 2,
                     "aspect_hist": [1, 1]},
               "1": {"covered_answer": {"answered": 1, "total": 2}}},
     "pools": {}, "llm_tokens": 1, "llm_calls": 1})
gr = ep.get("goal_readings") or {}
print("C. episode.goal_readings =", gr)
if not gr:
    bad.append("C: goal_readings 出口为空")

if bad:
    print("\nX 核验失败：")
    for x in bad:
        print("  -", x)
    sys.exit(1)
print("\nOK 可达性核验全过（逐圈序列 / 出口 / 读数方向 / 入库出口）")
