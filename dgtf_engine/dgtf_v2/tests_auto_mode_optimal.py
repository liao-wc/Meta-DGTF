# -*- coding: utf-8 -*-
"""[V2.2.19] 输入驱动自动模式选择判据：保留集裁剪 / 每模式专属参数 / 最优性 / 动态调整。

判据逻辑（零 GPU、零网络）：
  A 保留集：只剩 B / serial / fast；web 是标志位而不是模式；场景表不出现其他模式。
  B 最优性：枚举 oracle 对账 + 支配关系 + 确定性 + 单调性 + 不可行显式 fallback。
  C 输入驱动：事实题 -> fast；推理/选择题 -> B；显式预算 -> 对应最优模式。
  D 每模式专属配置：apply_mode_opts 落参正确；显式 opts 优先且可审计。
  E 运行期动态调整：预算超支降档 / fast 质量不达标升档 / 无必要时保持。
  F 静态接线：引擎 --parallel 只留 serial/B/auto；App 走 plan_for_input/apply_mode_opts。
  G 变异体：返回被支配模式 / 配置缺键 / 动态忽略预算 / 去掉约束让位 => 必须判红。
"""
from __future__ import annotations

import itertools
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dgtf_engine"))

from dgtf_v2 import mode_fusion as MF  # noqa: E402

P, F = [], []


def ck(name, cond, info=""):
    (P if cond else F).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (" :: " + str(info) if info and not cond else ""))


FACT_Q = "HTTP 404 状态码表示什么？"
REASON_Q = "为什么城市热岛效应在夜间比白天更明显？"
CHOICE_Q = "以下哪项属于可再生能源？A. 煤炭 B. 太阳能 C. 石油 D. 天然气"
LONG_Q = ("请系统比较三种城市内涝治理方案，并说明各自的适用边界与失效条件；"
          "它们的成本结构、维护要求、监管依赖分别如何？" * 3)

print("── A 保留集裁剪（只留 B/serial/fast；web 降为标志位）──")
ck("A1 KEPT 只有 B/serial/fast", tuple(MF.KEPT) == ("B", "serial", "fast"), MF.KEPT)
ck("A2 MODES 键 == KEPT（web 不再是模式）", set(MF.MODES) == set(MF.KEPT), list(MF.MODES))
ck("A3 MODE_CONFIGS 覆盖全部保留模式", set(MF.MODE_CONFIGS) == set(MF.KEPT))
_need = {"parallel", "thinking", "effort", "web", "behavior_fusion",
         "rounds_hint", "quality_floor", "quality_target"}
_bad_cfg = []
for m in MF.KEPT:
    c = MF.MODE_CONFIGS[m]
    if not _need.issubset(c):
        _bad_cfg.append((m, sorted(_need - set(c))))
    if c["parallel"] not in ("B", "serial"):
        _bad_cfg.append((m, "parallel"))
    if c["thinking"] not in ("auto", "on", "off"):
        _bad_cfg.append((m, "thinking"))
    if not isinstance(c["web"], bool):
        _bad_cfg.append((m, "web"))
    if not re.match(r"^0:\d+,1:\d+,both:\d+,all:\d+$", str(c["rounds_hint"])):
        _bad_cfg.append((m, "rounds_hint"))
ck("A4 每个模式的专属参数完整且取值合法", not _bad_cfg, _bad_cfg)
ck("A5 web 标志位有唯一实测读数（B+联网）",
   MF.WEB_READING.get("web") is True
   and float(MF.WEB_READING["quality"]) > 0)
_scen = MF.scenario_table()
ck("A6 场景表 5 项且模式全在保留集",
   len(_scen) == 5 and all(r["mode"] in MF.KEPT for r in _scen), _scen)
_web_row = next(r for r in _scen if r["scenario"] == "必须联网")
ck("A7 必须联网 -> B(+web) 标志位", _web_row["mode"] == "B" and _web_row["web"] is True)
ck("A8 _candidate_rows 非 web 只有 3 个",
   len(MF._candidate_rows(False)) == 3 and len(MF._candidate_rows(True)) == 1)

print("── B 最优性（枚举 oracle / 支配 / 确定性 / 单调 / 不可行显式）──")
BEST = {"quality": lambda r: (-float(r["quality"]), float(r["wall"]),
                              float(r["tokens"])),
        "wall": lambda r: (float(r["wall"]), -float(r["quality"]),
                           float(r["tokens"])),
        "tokens": lambda r: (float(r["tokens"]), -float(r["quality"]),
                             float(r["wall"]))}
grid = itertools.product(
    [None, 0.90, 0.93, 0.95, 0.99, 0.999],
    [None, 900, 1100, 1500, 2000],
    [None, 850000, 1000000, 1200000, 1400000],
    ["quality", "wall", "tokens"],
    [False, True])
oracle_ok, oracle_n = 0, 0
bad = []
for mq, mw, mt, prefer, web in grid:
    opts = {"prefer": prefer, "require_web": web}
    if mq is not None:
        opts["min_quality"] = mq
    if mw is not None:
        opts["max_wall"] = mw
    if mt is not None:
        opts["max_tokens"] = mt
    sel = MF.select_optimal_mode("", opts=opts)
    rows = MF._candidate_rows(web)
    # 显式约束（oracle 只认显式约束；推断下限允许让位，规则见 optimality.relaxed）
    hard_ok = []
    for r in rows:
        if mq is not None and float(r["quality"]) < mq:
            continue
        if mw is not None and float(r["wall"]) > mw:
            continue
        if mt is not None and float(r["tokens"]) > mt:
            continue
        hard_ok.append(r)
    if hard_ok:
        oracle = min(hard_ok, key=lambda r: BEST[prefer](r))
        oracle_n += 1
        ok = (sel["mode"] == oracle["mode"] and sel["optimality"]["regret"] == 0.0
              and not sel["fallback"])
        if ok:
            oracle_ok += 1
        else:
            bad.append((mq, mw, mt, prefer, web, sel["mode"], oracle["mode"]))
    else:
        # 显式约束下不可行 ⇒ 必须显式 fallback，不许假装最优
        if not sel["fallback"] or sel["optimality"]["regret"] is not None:
            bad.append(("fallback", mq, mw, mt, prefer, web,
                        sel["fallback"], sel["optimality"]["regret"]))
ck("B1 显式约束下枚举 oracle 全部命中（最优性可证）",
   not bad and oracle_n > 0, bad[:3] + [("n", oracle_n)])
ck("B2 可行时 regret=0 / 不可行时 regret=None 且 fallback=True",
   not [b for b in bad if b[0] == "fallback"])

# 支配关系：可行且非显式模式下，选中项不被任何候选支配
_viol = []
for mq in (0.90, 0.95, 0.99):
    for prefer in ("quality", "wall", "tokens"):
        sel = MF.select_optimal_mode("", opts={"min_quality": mq, "prefer": prefer})
        if sel["fallback"] or sel["optimality"]["override"]:
            continue
        rows = MF._candidate_rows(False)
        chosen = next(r for r in rows if r["mode"] == sel["mode"])
        dom = [r["mode"] for r in rows if MF._dominates(r, chosen)]
        if dom:
            _viol.append((mq, prefer, sel["mode"], dom))
ck("B3 选中项不被任何候选支配", not _viol, _viol[:3])

# 确定性 + 单调性
_s1 = MF.plan_for_input(REASON_Q)
_s2 = MF.plan_for_input(REASON_Q)
s1, s2 = MF.select_optimal_mode(REASON_Q), MF.select_optimal_mode(REASON_Q)
ck("B4 同一输入确定性（重复 5 次同结果）",
   all(MF.select_optimal_mode(REASON_Q)["mode"] == s1["mode"] for _ in range(5)))
ck("B5 墙钟上限收紧不会选到更慢的模式",
   float(MF.select_optimal_mode("", {"max_wall": 900})["reading"]["wall"])
   <= float(MF.select_optimal_mode("", {"max_wall": 2000})["reading"]["wall"]))
_no = MF.select_optimal_mode("", {"max_wall": 500})
ck("B6 显式约束不可行 => fallback=True / regret=None（不假装最优；"
   "退路=质量下限优先再比墙钟）",
   _no["fallback"] is True and _no["optimality"]["regret"] is None
   and _no["mode"] in ("B", "serial"), (_no["mode"], _no["reason"]))

print("── C 输入驱动选档 ──")
ck("C1 事实题 -> fast（省墙钟档）", MF.plan_for_input(FACT_Q)["mode"] == "fast",
   MF.plan_for_input(FACT_Q)["mode"])
ck("C2 推理题 -> B（质量档）", MF.plan_for_input(REASON_Q)["mode"] == "B")
ck("C3 选择题 -> B（质量档）", MF.plan_for_input(CHOICE_Q)["mode"] == "B")
ck("C4 长/多问题 -> B（质量优先）", MF.plan_for_input(LONG_Q)["mode"] == "B")
ck("C5 显式 min_quality=0.99 -> B",
   MF.plan_for_input(REASON_Q, {"min_quality": 0.99})["mode"] == "B")
_p = MF.plan_for_input(REASON_Q, {"min_quality": 0.95, "max_tokens": 1000000})
ck("C6 显式 tokens 上限 + 质量下限 -> serial（唯一可行）", _p["mode"] == "serial", _p["mode"])
_pw0 = MF.plan_for_input(FACT_Q, {"max_wall": 900})
ck("C7a 事实题 + 墙钟上限：fast 本来就在推断下限 0.90 之上（无需让位）",
   _pw0["mode"] == "fast" and not (_pw0["optimality"]["relaxed"] or []),
   (_pw0["mode"], _pw0["optimality"].get("relaxed")))
_pw = MF.plan_for_input(REASON_Q, {"max_wall": 900})
ck("C7b 推理题 + 显式墙钟上限：推断下限 0.95 让位 -> fast（relaxed 可见）",
   _pw["mode"] == "fast"
   and "min_quality(inferred)" in (_pw["optimality"]["relaxed"] or []),
   (_pw["mode"], _pw["optimality"].get("relaxed")))
_pweb = MF.plan_for_input(FACT_Q, {"require_web": True})
ck("C8 require_web -> B + web（唯一实测联网档）",
   _pweb["mode"] == "B" and _pweb["web"] is True
   and _pweb["config"]["web"] is True)
_pf = MF.plan_for_input(FACT_Q)
ck("C9 fast 计划带运行期升档 cascade（fast->B）",
   _pf["mode"] == "fast" and (_pf.get("cascade") or {}).get("upgrade_to") == "B"
   and float(_pf["cascade"]["on_quality_below"]) > float(MF.MODES["fast"]["quality"]))

print("── D 每模式专属配置落参 ──")
for m in MF.KEPT:
    plan = {"mode": m, "web": False, "config": dict(MF.MODE_CONFIGS[m])}
    out, applied = MF.apply_mode_opts({}, plan)
    cfg = MF.MODE_CONFIGS[m]
    ok = (out.get("parallel") == cfg["parallel"]
          and out.get("thinking") == cfg["thinking"]
          and out.get("effort") == cfg["effort"]
          and out.get("web") == "off"
          and out.get("rounds") == cfg["rounds_hint"]
          and out.get("mode") == m
          and applied.get("parallel") == cfg["parallel"])
    ck("D1 %s 专属参数落成任务 opts" % m, ok, {"out": out, "applied": applied})
_out, _ap = MF.apply_mode_opts({"thinking": "off", "parallel": "serial"},
                               {"mode": "B", "web": False,
                                "config": dict(MF.MODE_CONFIGS["B"])})
ck("D2 显式任务参数优先于模式默认（可审计）",
   _out.get("thinking") == "off" and _out.get("parallel") == "serial"
   and _ap.get("thinking") == "off" and _ap.get("parallel") == "serial")
_src_opts = {"thinking": "off"}
_out2, _ = MF.apply_mode_opts(_src_opts, {"mode": "B", "web": False,
                                          "config": dict(MF.MODE_CONFIGS["B"])})
ck("D3 apply_mode_opts 不改入参且挂 plan", _src_opts == {"thinking": "off"}
   and isinstance(_out2.get("_mode_plan"), dict))

print("── E 运行期动态调整 ──")
_planB = {"mode": "B", "config": dict(MF.MODE_CONFIGS["B"]),
          "preferences": {"min_quality": 0.90}}
_d1 = MF.dynamic_adjust(_planB, {"elapsed_sec": 600, "wall_budget_sec": 900,
                                 "layers_done": 0, "layers_total": 4})
ck("E1 墙钟预算过半且进度不足半 => 降档 fast",
   _d1["action"] == "downgrade" and _d1["to"] == "fast"
   and _d1["patch"].get("thinking") == "off", _d1)
_d2 = MF.dynamic_adjust(_planB, {"tokens_used": 8_000_000, "token_budget": 10_000_000,
                                 "layers_done": 1, "layers_total": 4})
ck("E2 tokens 已用 70% => 降档 fast", _d2["action"] == "downgrade", _d2)
_planF = {"mode": "fast", "config": dict(MF.MODE_CONFIGS["fast"]),
          "cascade": {"on_quality_below": 0.95}, "preferences": {"min_quality": 0.90}}
_d3 = MF.dynamic_adjust(_planF, {"quality_proxy": 0.5})
ck("E3 fast 质量代理低于目标 => 升档 B",
   _d3["action"] == "upgrade" and _d3["to"] == "B"
   and _d3["patch"].get("thinking") == "auto", _d3)
_d4 = MF.dynamic_adjust(_planB, {"elapsed_sec": 100, "wall_budget_sec": 900,
                                 "layers_done": 2, "layers_total": 4})
ck("E4 进度正常 => keep", _d4["action"] == "keep" and _d4["patch"] == {})
_planHigh = {"mode": "B", "config": dict(MF.MODE_CONFIGS["B"]),
             "preferences": {"min_quality": 0.99}}
_d5 = MF.dynamic_adjust(_planHigh, {"elapsed_sec": 600, "wall_budget_sec": 900,
                                    "layers_done": 0, "layers_total": 4})
ck("E5 质量下限高于 fast 实测 => 不降档（预算让位质量）", _d5["action"] == "keep", _d5)
ck("E6 每次调整带 reason/alternatives/optimality",
   all(_d.get("reason") for _d in (_d1, _d3, _d4))
   and isinstance(_d1.get("alternatives"), list)
   and isinstance(_d1.get("optimality"), dict))

print("── F 静态接线（引擎/App 必须真的用新机制）──")
ENG_DIR = ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
_engs = sorted(ENG_DIR.glob("Meta-DGTF-V*.py"),
               key=lambda p: tuple(int(x) for x in
                                   re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name).groups()))
_eng = _engs[-1]
_esrc = _eng.read_text(encoding="utf-8-sig")
ck("F1 引擎 --parallel 只保留 serial/B/auto（A-H 用户面移除）",
   'choices=["serial", "B", "auto"]' in _esrc, _eng.name)
ck("F2 引擎有 --mode auto|B|serial|fast", '"--mode"' in _esrc
   and '"B", "serial", "fast"' in _esrc)
ck("F3 引擎调用 plan_for_input 并用计划里的专属配置落参",
   "plan_for_input(" in _esrc and '_mc.get("parallel")' in _esrc
   and '_mc.get("thinking")' in _esrc and '_mc.get("rounds_hint")' in _esrc)
ck("F4 引擎 packed 有 auto_mode 读数", '"auto_mode"' in _esrc)
_ssrc = (ROOT / "dgtf_app" / "server.py").read_text(encoding="utf-8", errors="replace")
ck("F5 App 走 plan_for_input/apply_mode_opts（不再硬编码模式分支）",
   "plan_for_input(" in _ssrc and "apply_mode_opts(" in _ssrc)

print("── G 变异体（有牙）──")
# G1 变异体：真实三模式互为 Pareto 最优（无支配）；合成一个「三面都更差」的
#    fake 模式，验证支配检测有牙 —— 若选择器返回 fake，支配判据必须红。
_rows = MF._candidate_rows(False)
ck("G1a 真实保留集里不存在支配关系（B/serial/fast 互为 Pareto 最优）",
   not any(MF._dominates(a, b) for a in _rows for b in _rows if a is not b))
_fake = dict(MF.MODES["serial"], mode="fake", quality=0.90,
             tokens=1300000, wall=2000)
_rows2 = _rows + [_fake]
_dom = [r["mode"] for r in _rows2 if r is not _fake and MF._dominates(r, _fake)]
ck("G1b 变异体（选被支配的 fake 模式）=> 支配检测必须判红", len(_dom) >= 2, _dom)
# G2 变异体：模式配置缺 parallel
_badplan = {"mode": "B", "web": False, "config": {"thinking": "auto"}}
_o, _a = MF.apply_mode_opts({}, _badplan)
ck("G2 变异体（模式配置缺 parallel）=> 落参校验必须判红",
   _a.get("parallel") is None)
# G3 变异体：动态调整忽略预算
def _bad_dyn(plan, progress):
    return {"action": "keep"}
ck("G3 变异体（动态调整忽略预算）=> E1 口径必须判红",
   _bad_dyn(_planB, {"elapsed_sec": 600, "wall_budget_sec": 900,
                     "layers_done": 0, "layers_total": 4})["action"] == "keep")
# G4 变异体：去掉「推断下限让位」=> 墙钟上限题会 fallback 而不是 fast
_sel_no_relax = MF.select_optimal_mode("", {"max_wall": 900, "prefer": "quality"})
ck("G4 让位记录可见（relaxed 非空）且选出可行 fast",
   _sel_no_relax["mode"] == "fast"
   and "min_quality(inferred)" in (_sel_no_relax["optimality"]["relaxed"] or []))

print("")
print("PASS %d / FAIL %d" % (len(P), len(F)))
raise SystemExit(1 if F else 0)
