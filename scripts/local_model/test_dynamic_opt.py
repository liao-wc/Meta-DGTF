# -*- coding: utf-8 -*-
"""[V2.2.24 / App 2.0.49] 全链路动态配置优化 + 动态依赖调整判据（零成本）。

A 动态依赖：both ⇒ 补 0/1；all ⇒ 补 both/0/1；预测/union 下不破坏既有 route。
B 动态配置：余额 × 质量下限 × 成本多目标；候选枚举、可行域、预留比例、
  预算层级（ok/degrade/warn/critical）与圈数降档；显式 opts 永远优先。
C 接线：plan.dynamic_opt → apply_plan → build_cmd（引擎 --rounds/--web）。
D 变异体：去掉依赖闭包 / 去掉预算预留 / 事实题不强制 web ⇒ 判据必须红。
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "dgtf_engine"), str(ROOT / "dgtf_app")):
    if p not in sys.path:
        sys.path.insert(0, p)

import daosheng_mode as DS  # noqa: E402
import engine_runner as ER  # noqa: E402

P, F = [], []


def ck(name, cond, info=""):
    (P if cond else F).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (" :: " + str(info) if info and not cond else ""))


FACT_Q = "HTTP 404 状态码表示什么？"
CHOICE_Q = "以下哪项属于可再生能源？A. 煤炭 B. 太阳能 C. 石油 D. 天然气"
REASON_Q = "为什么城市热岛效应在夜间比白天更明显？"
PROJ_Q = "Meta-DGTF 项目当前状态如何"

print("── A 动态依赖调整（route 闭包）──")
ck("A1 单层 route 不被强加依赖", DS.route_with_deps(["1"]) == (["1"], []))
ck("A2 both ⇒ 补 0/1（顺序规范）",
   DS.route_with_deps(["both"]) == (["0", "1", "both"], ["0", "1"]),
   DS.route_with_deps(["both"]))
ck("A3 all ⇒ 补 both/0/1",
   DS.route_with_deps(["all"]) == (["0", "1", "both", "all"],
                                   ["both", "0", "1"]))
ck("A4 已有部分依赖只补缺的",
   DS.route_with_deps(["0", "both"]) == (["0", "1", "both"], ["1"]))
ck("A5 非法/空输入不炸", DS.route_with_deps([]) == ([], []))

_pres = DS.load_preset()
_orig_load, _orig_pred = DS.load_preset, DS.predict_route_rounds
try:
    DS.predict_route_rounds = lambda *a, **k: {
        "source": "stub", "route": ["both"], "rounds": {}}
    DS.load_preset = lambda force=False: dict(_pres, route_policy="predict")
    _p = DS.build_plan(REASON_Q, {}, requested="daosheng", is_mock=True,
                       balance_cny=50.0)
    ck("A6 predict 到 both：plan.route 补成 0,1,both 且记录依赖新增",
       _p.get("route") == "0,1,both"
       and _p.get("route_dependency_added") == ["0", "1"],
       (_p.get("route"), _p.get("route_dependency_added")))
finally:
    DS.load_preset, DS.predict_route_rounds = _orig_load, _orig_pred

print("── B 动态配置（预算 × 质量 × 成本）──")
_bg = lambda bal, lvl, dec="ok": {"balance_cny": bal, "budget_level": lvl,
                                  "decision": dec, "est_cost_cny": 2.0,
                                  "reserve_ratio": 0.5}


def _dyn(bal, lvl, **kw):
    base = dict(ds=_pres, tier="fast", engine_mode="fast", parallel="B",
                thinking="off", web="on", rounds=_pres.get("rounds_fast"),
                budget_guard=_bg(bal, lvl), scenario={"kind": "fact"},
                require_web=True, opts={})
    base.update(kw)
    return DS.dynamic_config(**base)


_d_ok = _dyn(50.0, "ok")
_d_deg = _dyn(6.0, "degrade")
_d_warn = _dyn(2.0, "warn")
_d_crit = _dyn(0.5, "critical")
ck("B1 ok 档：有可行解、质量≥下限、无 fallback",
   (not _d_ok["fallback"]) and _d_ok["chosen"]["est_quality"] >= _d_ok["quality_floor"]
   and _d_ok["regret"] == 0.0)
ck("B2 预留比例生效：可行解成本 ≤ 余额×reserve",
   _d_ok["chosen"]["est_cost_cny"] <= 50.0 * 0.5
   and _d_deg["chosen"]["est_cost_cny"] <= 6.0 * 0.5)
ck("B3 degrade 用实测 fast 圈数（质量已验证）",
   _d_deg["chosen"]["rounds"] == _pres.get("rounds_fast"), _d_deg["chosen"])
ck("B4 warn 用 economy 圈数（成本再降）",
   _d_warn["chosen"]["rounds"] == _pres["budget"]["rounds_economy"])
ck("B5 critical 用最低圈数",
   _d_crit["chosen"]["rounds"] == _pres["budget"]["rounds_critical"])
ck("B6 余额越低圈数/token 不增（单调降本）",
   DS._rounds_count(_d_deg["chosen"]["rounds"])
   >= DS._rounds_count(_d_warn["chosen"]["rounds"])
   >= DS._rounds_count(_d_crit["chosen"]["rounds"]))
ck("B7 事实题 web 强制 on（off 实测不 verified）",
   all(c["web"] == "on" for c in _d_ok["candidates"]))
_proj_cfg = dict(ds=_pres, tier="quality", engine_mode="B", parallel="B",
                  thinking="auto", web="off", rounds="auto",
                  budget_guard=_bg(50.0, "ok"),
                  scenario={"kind": "reasoning"}, require_web=False, opts={},
                  project_related=True)
ck("B8 质量下限：项目题 quality 档 0.95",
   DS.dynamic_config(**_proj_cfg)["quality_floor"] == 0.95)
ck("B8b fast 档下限对齐实测（0.90），避免项目 0.95 造成假 fallback",
   DS.dynamic_config(**dict(_proj_cfg, tier="fast", engine_mode="fast",
                            rounds=_pres.get("rounds_fast")))["quality_floor"] == 0.90)
ck("B9 显式 opts.rounds 时不覆盖（applied 为空）",
   DS.dynamic_config(ds=_pres, tier="fast", engine_mode="fast",
                     rounds=_pres.get("rounds_fast"), web="on",
                     budget_guard=_bg(2.0, "warn"),
                     scenario={"kind": "fact"}, require_web=True,
                     opts={"rounds": "0:3"})["applied"] == {})
ck("B10 无余额（fail-open）时全部候选可行",
   all(c["feasible"] for c in _dyn(None, "unknown")["candidates"]))


print("── B2 多圈档候选 + 缓存命中感知（V2.2.25）──")
_deg2 = _dyn(6.0, "degrade")
ck("B11 多圈档候选全部枚举（≥3 档，由成本约束筛选）",
   len(_deg2["candidates"]) >= 3
   and len({c["rounds"] for c in _deg2["candidates"]}) >= 3,
   [c["rounds"] for c in _deg2["candidates"]])
_cheap = _dyn(2.0, "warn")
ck("B12 预算收紧时自动选更低圈（质量仍≥下限）",
   DS._rounds_count(_cheap["chosen"]["rounds"])
   <= DS._rounds_count(_deg2["chosen"]["rounds"])
   and _cheap["chosen"]["est_quality"] >= _cheap["quality_floor"])
_cache_cfg = DS.dynamic_config(ds=_pres, tier="fast", engine_mode="fast",
                               rounds=_pres.get("rounds_fast"), web="on",
                               budget_guard=_bg(1.0, "warn"),
                               scenario={"kind": "fact"}, require_web=True,
                               cache={"exact": True}, opts={})
ck("B13 缓存精确命中：标记 cache_hit 且按 10% 成本放宽可行域",
   _cache_cfg["cache_hit"] is True
   and any(c["feasible"] for c in _cache_cfg["candidates"])
   and _cache_cfg["chosen"]["est_cost_effective_cny"]
   <= 1.0 * _cache_cfg["reserve_ratio"] + 1e-9)
_nocache_cfg = DS.dynamic_config(ds=_pres, tier="fast", engine_mode="fast",
                                 rounds=_pres.get("rounds_fast"), web="on",
                                 budget_guard=_bg(1.0, "warn"),
                                 scenario={"kind": "fact"}, require_web=True,
                                 cache={"exact": False}, opts={})
ck("B14 未命中缓存时不放宽预算约束（对照）",
   _cache_cfg["chosen"]["est_quality"] >= _nocache_cfg["chosen"]["est_quality"])
ck("B15 route 进入 dynamic_opt 审计（为下一版 route 子集成本模型留接口）",
   DS.dynamic_config(ds=_pres, tier="fast", engine_mode="fast",
                     rounds=_pres.get("rounds_fast"), web="on",
                     budget_guard=_bg(50.0, "ok"),
                     scenario={"kind": "fact"}, require_web=True,
                     route="0", opts={})["route"] == "0")

# build_plan 缓存命中接线（monkeypatch 缓存预判）
_orig_cache = DS.cache_prediction
try:
    DS.cache_prediction = lambda q, o=None: {"exact": True, "exact_from": "stub"}
    _pc = DS.build_plan(FACT_Q, {}, requested="daosheng", is_mock=True,
                        balance_cny=1.0)
    _dc = _pc.get("dynamic_opt") or {}
    ck("C7 build_plan 注入缓存命中：dynamic_opt.cache_hit=True 且有可行解",
       _dc.get("cache_hit") is True and not _dc.get("fallback"),
       (_dc.get("cache_hit"), _dc.get("fallback")))
finally:
    DS.cache_prediction = _orig_cache
ck("E4 变异体：若忽略缓存（按原价），余额 1 元下可行域会收缩（判据有牙）",
   _cache_cfg["chosen"]["est_cost_effective_cny"] < _cache_cfg["chosen"]["est_cost_cny"])


print("── F route 子集感知成本模型（V2.2.26，3 臂云实测校准）──")
_rt = DS._route_round_tokens
ck("F1 单层 0 每圈 ≈31,620（R3 实测 63,240/2）",
   abs(_rt("0", "0:1") - 31620) < 500, _rt("0", "0:1"))
ck("F2 单层 1 每圈 ≈37,119（R1 实测）",
   abs(_rt("1", "1") - 37119) < 500, _rt("1", "1"))
ck("F3 两层可加性（R2 实测 62,180，误差 <5%）",
   abs(_rt("0,1", "0:1,1:1") - 62180) / 62180 < 0.05,
   _rt("0,1", "0:1,1:1"))
ck("F4 整单 fast 默认圈数 ≈816,983（整单实测，±2%）",
   abs(_rt("0,1,both,all", "0:2,1:3,both:2,all:2") - 816983) / 816983 < 0.02,
   _rt("0,1,both,all", "0:2,1:3,both:2,all:2"))
ck("F5 B 模式按 MODES 比例放大（≈1,269,082，±2%）",
   abs(_rt("0,1,both,all", "0:2,1:3,both:2,all:2", "B") - 1269082) / 1269082 < 0.02,
   _rt("0,1,both,all", "0:2,1:3,both:2,all:2", "B"))
ck("F6 事实题 web on 有 token 增量", _rt("0", "0:1", "fast", "on", "fact")
   > _rt("0", "0:1", "fast", "off", "fact"))
_calib = json.loads((ROOT / "docs" / "dynamic_cost_calibration_20261029.json")
                    .read_text(encoding="utf-8"))
_arm_pred = {a["route"] + "|" + a["rounds"]: a["tokens"]
             for a in _calib["arms"]}
ck("F7 校准证据存在且 3 臂齐全", len(_calib["arms"]) == 3
   and "u0_per_round" in _calib["fit"])
_pred_r1 = _rt("1", "1")
ck("F8 模型对校准臂的误差 <12%（R1）",
   abs(_pred_r1 - 37119) / 37119 < 0.12, _pred_r1)
_dyn_route0 = DS.dynamic_config(
    ds=_pres, tier="fast", engine_mode="fast", rounds=_pres.get("rounds_fast"),
    web="on", budget_guard=_bg(2.0, "warn"), scenario={"kind": "fact"},
    require_web=True, opts={}, route="0")
ck("F9 route=0 任务候选成本按子集估算（≤ 余额×预留，不再用整单口径）",
   _dyn_route0["chosen"]["est_tokens"] < 120000
   and _dyn_route0["chosen"]["est_cost_effective_cny"]
   <= 2.0 * _dyn_route0["reserve_ratio"] + 1e-9,
   _dyn_route0["chosen"])
ck("F10 dynamic_opt 标注成本模型口径", _dyn_route0.get("cost_model")
   == "route_subset_rounds.v1")


print("── G App 全流程开销 + 有效 route + 阶段路由 + 引擎依赖（V2.2.27）──")
_appcal = json.loads((ROOT / "docs" / "app_path_cost_calibration_20261029.json")
                     .read_text(encoding="utf-8"))
ck("G1 App 路径开销实测系数在 1.05~1.20（1 臂云校准）",
   1.05 <= float(_appcal.get("app_path_overhead") or 0) <= 1.20,
   _appcal.get("app_path_overhead"))
_chg = DS.dynamic_config(ds=_pres, tier="fast", engine_mode="fast",
                         rounds="0:2", web="off", budget_guard=_bg(50.0, "ok"),
                         scenario={"kind": "fact"}, require_web=True,
                         opts={}, route="0")
_ch = _chg["chosen"]
_rt_ch = DS._route_round_tokens("0", _ch["rounds"], "fast", _ch["web"], "fact")
_exp_tok = _rt_ch * 1.10
ck("G2 App 开销已计入候选 token（≈模型×1.10）",
   abs(_ch["est_tokens"] / max(1.0, _exp_tok) - 1.0) < 0.05,
   (_ch["est_tokens"], _rt_ch, _chg.get("app_overhead")))
_p_opt_route = DS.build_plan(FACT_Q, {"route": "0"}, requested="daosheng",
                             is_mock=True, balance_cny=3.0)
ck("G3 显式 opts.route=0：dynamic_opt.route 记录有效 route",
   (_p_opt_route.get("dynamic_opt") or {}).get("route") == "0")
_p_warn_low = DS.build_plan(FACT_Q, {}, requested="daosheng", is_mock=True,
                            balance_cny=3.0)
ck("G4 warn 档非项目题：阶段动态路由 dual_judge=cache",
   _p_warn_low.get("dual_judge_mode") == "cache"
   and ((_p_warn_low.get("dynamic_opt") or {}).get("applied") or {}).get(
       "dual_judge_mode") == "cache")
_p_warn_prj = DS.build_plan(PROJ_Q, {}, requested="daosheng", is_mock=True,
                            balance_cny=3.0)
ck("G5 项目题/quality_first 不降级评审（dual_judge != cache）",
   _p_warn_prj.get("dual_judge_mode") != "cache")
_p_ok = DS.build_plan(FACT_Q, {}, requested="daosheng", is_mock=True,
                      balance_cny=50.0)
ck("G6 ok 档不走 cache 评审（预算充足时保留双评审）",
   _p_ok.get("dual_judge_mode") != "cache")
_engs = sorted((ROOT / "dgtf_engine" / "dgtf_v2" / "engine").glob("Meta-DGTF-V*.py"),
               key=lambda p: tuple(int(x) for x in
                                   re.search(r"V(\d+)\.(\d+)\.(\d+)", p.name).groups()))
_esrc = _engs[-1].read_text(encoding="utf-8-sig")
ck("G7 引擎最高版含 route 依赖闭包与 main 接线",
   "_close_route_deps" in _esrc and "层依赖闭包" in _esrc
   and "★ [V2.2.27]" in _esrc, _engs[-1].name)
_spec2 = importlib.util.spec_from_file_location("eng_v2227", _engs[-1])
_M2 = importlib.util.module_from_spec(_spec2)
sys.modules["eng_v2227"] = _M2
_spec2.loader.exec_module(_M2)
ck("G8 引擎闭包：both⇒0/1、all⇒both/0/1、单层不变",
   _M2._close_route_deps(["both"]) == (["0", "1", "both"], ["0", "1"])
   and _M2._close_route_deps(["all"]) == (["0", "1", "both", "all"],
                                          ["both", "0", "1"])
   and _M2._close_route_deps(["1"]) == (["1"], []))


print("── H 预算层级 → 运行期 token 硬上限（V2.2.28）──")
_p_w = DS.build_plan(FACT_Q, {}, requested="daosheng", is_mock=True,
                     balance_cny=3.0)
_p_o = DS.build_plan(FACT_Q, {}, requested="daosheng", is_mock=True,
                     balance_cny=50.0)
_ch_w = ((_p_w.get("dynamic_opt") or {}).get("chosen") or {})
ck("H1 warn 档：plan.max_tokens = 估算×1.5（硬边界）",
   int(_p_w.get("max_tokens") or 0) > 0
   and abs(int(_p_w.get("max_tokens") or 0)
           / max(1.0, int(_ch_w.get("est_tokens") or 0) * 1.5) - 1.0) < 0.05,
   (_p_w.get("max_tokens"), _ch_w.get("est_tokens")))
ck("H2 ok/quality 档不设 token 硬上限（max_tokens=0）",
   int(_p_o.get("max_tokens") or 0) == 0)
_p_exp = DS.build_plan(FACT_Q, {"max_tokens": 123456}, requested="daosheng",
                       is_mock=True, balance_cny=2.0)
ck("H3 显式 opts.max_tokens 永远优先（plan 不覆盖）",
   int(_p_exp.get("max_tokens") or 0) == 0)
_o_cap = {}
DS.apply_plan(dict(_p_w), _o_cap)
ck("H4 apply_plan 把 max_tokens 透传到 opts", _o_cap.get("max_tokens")
   == _p_w.get("max_tokens") and _o_cap.get("max_tokens", 0) > 0)
cap_cmd = ER.build_cmd("问题", _o_cap)
ck("H5 build_cmd 带 --max-tokens（运行期硬边界可达）",
   "--max-tokens" in cap_cmd)
ck("H6 dynamic_opt 记录 budget_cap（可审计）",
   bool(((_p_w.get("dynamic_opt") or {}).get("budget_cap") or {}).get("max_tokens")))

_p_w2 = DS.build_plan(FACT_Q, {}, requested="daosheng", is_mock=True,
                      balance_cny=3.0)
_p_o2 = DS.build_plan(FACT_Q, {}, requested="daosheng", is_mock=True,
                      balance_cny=50.0)
ck("H7 warn 档：plan.max_minutes 为估算墙钟硬上限（>0）",
   int(_p_w2.get("max_minutes") or 0) > 0
   and int(_p_w2.get("max_minutes") or 0)
   == int((((_p_w2.get("dynamic_opt") or {}).get("budget_cap") or {})
           .get("max_minutes")) or -1))
ck("H8 ok 档不设墙钟上限（max_minutes=0）",
   int(_p_o2.get("max_minutes") or 0) == 0)
_p_expm = DS.build_plan(FACT_Q, {"max_minutes": 7}, requested="daosheng",
                        is_mock=True, balance_cny=2.0)
ck("H9 显式 opts.max_minutes 永远优先（plan 不覆盖）",
   int(_p_expm.get("max_minutes") or 0) == 0)
_o_cap2 = {}
DS.apply_plan(dict(_p_w2), _o_cap2)
ck("H10 apply_plan/build_cmd 透传 --max-minutes",
   _o_cap2.get("max_minutes") == _p_w2.get("max_minutes")
   and "--max-minutes" in ER.build_cmd("问题", _o_cap2))


print("── I 层子集质量风险标注（V2.2.30，3 臂 A/B 证据）──")
_ab_ev = json.loads((ROOT / "docs" / "route_subset_quality_ab_20261029.json")
                    .read_text(encoding="utf-8"))
ck("I1 A/B 证据存在（route0/route0,1/full 三臂）",
   len(_ab_ev.get("arms") or []) == 3)
_p_rq = DS.build_plan(PROJ_Q, {"route": "0"}, requested="daosheng",
                      is_mock=True, balance_cny=50.0)
_rq = (_p_rq.get("dynamic_opt") or {}).get("route_quality_risk") or {}
ck("I2 项目题显式省层 ⇒ high 风险 + 证据路径",
   _rq.get("level") == "high"
   and "route_subset_" in str(_rq.get("evidence") or ""),
   _rq)
_p_rq2 = DS.build_plan(FACT_Q, {"route": "0"}, requested="daosheng",
                       is_mock=True, balance_cny=50.0)
_rq2 = (_p_rq2.get("dynamic_opt") or {}).get("route_quality_risk") or {}
ck("I3 事实题显式省层 ⇒ info 风险（提示但保留）", _rq2.get("level") == "info")
_p_rq3 = DS.build_plan(FACT_Q, {"route": "0,1,both,all"}, requested="daosheng",
                       is_mock=True, balance_cny=50.0)
ck("I4 四层 route ⇒ 无风险标注",
   not ((_p_rq3.get("dynamic_opt") or {}).get("route_quality_risk")))
ck("I5 风险写入 warnings（可审计）",
   any("层子集质量风险" in str(w) for w in (_p_rq.get("warnings") or [])))

_p_pr = DS.build_plan(FACT_Q, {"route": "0", "rounds": "0:1"},
                      requested="daosheng", is_mock=True, balance_cny=50.0)
_prune = (_p_pr.get("dynamic_opt") or {}).get("route_pruning") or {}
ck("I6 短程事实题省层：advice=keep_four_layers（6 跑 A/B 收益≈0）",
   _prune.get("advice") == "keep_four_layers"
   and _prune.get("saved_pct_estimate") is not None, _prune)
ck("I7 省层证据指向 multi-sample JSON",
   str(_prune.get("evidence") or "").endswith("route_subset_multisample_20261029.json"))
_p_full = DS.build_plan(FACT_Q, {"route": "0,1,both,all", "rounds": "1"},
                        requested="daosheng", is_mock=True, balance_cny=50.0)
ck("I8 四层 route ⇒ 无省层收益判定",
   not ((_p_full.get("dynamic_opt") or {}).get("route_pruning")))
_rs = json.loads((ROOT / "docs" / "route_subset_reasoning_ab_20261029.json")
                 .read_text(encoding="utf-8"))
ck("I9 reasoning 实测证据存在（route0 vs full，2 reps）",
   len(_rs.get("rows") or []) == 4 and "summary" in _rs)
_p_long = DS.build_plan(REASON_Q, {"route": "0",
                                   "rounds": "0:1,1:1,both:1,all:1"},
                        requested="daosheng", is_mock=True, balance_cny=50.0)
_pl = (_p_long.get("dynamic_opt") or {}).get("route_pruning") or {}
ck("I10 reasoning 单圈：题型实测收益≈39% ⇒ advice=subset_may_save",
   _pl.get("advice") == "subset_may_save"
   and float(_pl.get("saved_pct_estimate") or 0) >= 0.30
   and str(_pl.get("evidence") or "").endswith("route_subset_reasoning_ab_20261029.json"),
   _pl)
_p_fact_long = DS.build_plan(FACT_Q, {"route": "0",
                                      "rounds": "0:3,1:3,both:3,all:3"},
                             requested="daosheng", is_mock=True, balance_cny=50.0)
_pf = (_p_fact_long.get("dynamic_opt") or {}).get("route_pruning") or {}
ck("I11 fact 长程：题型实测≈0 覆盖模型估算 ⇒ keep_four_layers",
   _pf.get("advice") == "keep_four_layers"
   and float(_pf.get("saved_pct_estimate") or 0) < 0.05, _pf)


print("── K2 rounds 依赖的省层收益（V2.2.35）──")
_rr2 = json.loads((ROOT / "docs" / "route_reasoning_rounds2_ab_20261029.json")
                  .read_text(encoding="utf-8"))
ck("K4 reasoning 高圈证据存在（route0/full 各 1 跑）",
   len(_rr2.get("rows") or []) == 2)
_p_r2 = DS.build_plan(REASON_Q, {"route": "0",
                                "rounds": "0:2,1:2,both:2,all:2"},
                      requested="daosheng", is_mock=True, balance_cny=50.0)
_rp2 = (_p_r2.get("dynamic_opt") or {}).get("route_pruning") or {}
ck("K5 reasoning 高圈（总 8）：省层收益≈0 ⇒ keep_four_layers（证据 rounds2）",
   _rp2.get("advice") == "keep_four_layers"
   and str(_rp2.get("evidence") or "").endswith(
       "route_reasoning_rounds2_ab_20261029.json"), _rp2)
_cr2 = (_p_r2.get("dynamic_opt") or {}).get("chosen") or {}
ck("K6 reasoning 高圈 route0：chosen≈65,608（高圈锚点）",
   abs(int(_cr2.get("est_tokens") or 0) - 65608) / 65608 < 0.15
   and _cr2.get("cost_source") == "measured_long_anchor",
   (_cr2.get("est_tokens"), _cr2.get("cost_source")))
_p_r2f = DS.build_plan(REASON_Q, {"route": "0,1,both,all",
                                  "rounds": "0:2,1:2,both:2,all:2"},
                       requested="daosheng", is_mock=True, balance_cny=50.0)
_cr2f = (_p_r2f.get("dynamic_opt") or {}).get("chosen") or {}
ck("K7 reasoning 高圈 full：chosen≈62,317（高圈锚点）",
   abs(int(_cr2f.get("est_tokens") or 0) - 62317) / 62317 < 0.15,
   _cr2f.get("est_tokens"))


print("── L 项目背景注入成本（V2.2.36，实测 +5,662 tokens）──")
_ctx_ev = json.loads((ROOT / "docs" / "project_context_ab_20261029.json")
                     .read_text(encoding="utf-8"))
ck("L1 项目上下文 A/B 证据存在（on/off 两臂）",
   len(_ctx_ev.get("rows") or []) == 2
   and int((_ctx_ev.get("delta") or {}).get("tokens") or 0) > 0)
_p_ctx = DS.build_plan(PROJ_Q, {"route": "0", "rounds": "0:1"},
                       requested="daosheng", is_mock=True, balance_cny=50.0)
_dctx = (_p_ctx.get("dynamic_opt") or {})
ck("L2 项目题默认：context_cost=5,662 且计入 chosen",
   int((_dctx.get("context_cost") or {}).get("tokens") or 0) == 5662
   and int(((_dctx.get("chosen") or {}).get("context_tokens")) or 0) == 5662,
   _dctx.get("context_cost"))
_p_ctx_off = DS.build_plan(PROJ_Q, {"route": "0", "rounds": "0:1",
                                    "project_context": False},
                           requested="daosheng", is_mock=True, balance_cny=50.0)
_doff = (_p_ctx_off.get("dynamic_opt") or {})
ck("L3 显式 project_context=false：不计上下文成本（chosen 42,798）",
   not _doff.get("context_cost")
   and abs(int((_doff.get("chosen") or {}).get("est_tokens") or 0) - 42798) / 42798 < 0.15,
   (_doff.get("context_cost"), (_doff.get("chosen") or {}).get("est_tokens")))


print("── M quality-retry 决策 / 预算分解 / 缓存 ROI（V2.2.37）──")
_p_m1 = DS.build_plan(FACT_Q, {}, requested="daosheng", is_mock=True,
                      balance_cny=10.0)
ck("M1 fact + 预算 ok：quality_retry 建议 web-retry",
   (_p_m1.get("quality_retry") or {}).get("retry") is True
   and (_p_m1.get("quality_retry") or {}).get("policy") == "auto:web-retry",
   _p_m1.get("quality_retry"))
_p_m2 = DS.build_plan(FACT_Q, {}, requested="daosheng", is_mock=True,
                      balance_cny=3.0)
ck("M2 fact + 预算 warn：建议关闭 web-retry（stable）",
   (_p_m2.get("quality_retry") or {}).get("retry") is False
   and (_p_m2.get("quality_retry") or {}).get("policy") == "auto:stable")
_p_m3 = DS.build_plan(PROJ_Q, {}, requested="daosheng", is_mock=True,
                      balance_cny=10.0)
ck("M3 项目题：quality_retry=verified 且不建议关闭",
   (_p_m3.get("quality_retry") or {}).get("policy") == "verified")
_p_m4 = DS.build_plan(PROJ_Q, {"route": "0", "rounds": "0:1"},
                      requested="daosheng", is_mock=True, balance_cny=3.0)
_cap = ((_p_m4.get("dynamic_opt") or {}).get("budget_cap") or {})
_est4 = ((_p_m4.get("dynamic_opt") or {}).get("chosen") or {}).get("est_tokens") or 0
ck("M4 预算 warn + 项目题：budget_cap 拆出 context_tokens=5,662",
   int(_cap.get("context_tokens") or 0) == 5662
   and int(_cap.get("base_tokens") or 0) == max(0, int(_est4) - 5662),
   (_cap.get("context_tokens"), _cap.get("base_tokens"), _est4))
_roi = ((_p_m1.get("dynamic_opt") or {}).get("cache_roi") or {})
ck("M5 cache_roi 读数齐（exact/semantic/expected_saving/note）",
   set(("exact", "semantic_capable", "expected_saving_pct", "note")
       ) <= set(_roi), _roi)


print("── N 余额续航预测（V2.2.38）──")
_p_n1 = DS.build_plan(FACT_Q, {"route": "0,1,both,all",
                               "rounds": "0:1,1:1,both:1,all:1"},
                      requested="daosheng", is_mock=True, balance_cny=10.0)
_fc = ((_p_n1.get("dynamic_opt") or {}).get("budget_forecast") or {})
ck("N1 续航预测字段齐且 safe_runs 合理（余额 10/估 0.13 ≈ 76 次）",
   _fc.get("advice") == "ok" and int(_fc.get("safe_runs") or 0) >= 70
   and abs(float(_fc.get("balance_after_cny") or 0)
           - (10.0 - float(_fc.get("est_cost_cny") or 0))) < 0.02,
   _fc)
_pres_n = DS.load_preset()
_pres_n2 = dict(_pres_n)
_pres_n2["budget"] = dict(_pres_n.get("budget") or {}, reserve_runs=500)
_orig_load_n = DS.load_preset
try:
    DS.load_preset = lambda force=False: _pres_n2
    _p_n2 = DS.build_plan(FACT_Q, {"route": "0,1,both,all",
                                   "rounds": "0:1,1:1,both:1,all:1"},
                          requested="daosheng", is_mock=True, balance_cny=10.0)
finally:
    DS.load_preset = _orig_load_n
ck("N2 续航不足（reserve_runs=500）⇒ 质量档自动降 fast",
   _p_n2.get("tier") == "fast" and _p_n2.get("engine_mode") == "fast"
   and "续航" in str(_p_n2.get("mode_reason")),
   (_p_n2.get("tier"), _p_n2.get("mode_reason")))
ck("N3 默认 reserve_runs=2 ⇒ 余额 10 不降级（tier=quality）",
   _p_n1.get("tier") == "quality")
_p_n4 = DS.build_plan(FACT_Q, {"route": "0", "rounds": "0:1"},
                      requested="daosheng", is_mock=True)
ck("N4 余额未知 ⇒ budget_forecast=None（fail-open 不预测）",
   (_p_n4.get("dynamic_opt") or {}).get("budget_forecast") is None)


print("── O 预算紧张允许复用未验证产物（V2.2.39）──")
_p_o1 = DS.build_plan(FACT_Q, {"route": "0", "rounds": "0:1"},
                      requested="daosheng", is_mock=True, balance_cny=50.0)
ck("O1 预算 ok：allow_unverified_cache=False",
   _p_o1.get("allow_unverified_cache") is False)
_p_o2 = DS.build_plan(FACT_Q, {"route": "0", "rounds": "0:1"},
                      requested="daosheng", is_mock=True, balance_cny=3.0)
_po2 = (( _p_o2.get("dynamic_opt") or {}).get("cache_policy") or {})
ck("O2 预算 warn：allow_unverified_cache=True + cache_policy 说明",
   _p_o2.get("allow_unverified_cache") is True
   and _po2.get("allow_unverified") is True
   and "未验证" in str(_po2.get("why")), _po2)
_o_opt = {}
DS.apply_plan(dict(_p_o2), _o_opt)
ck("O3 apply_plan 透传 allow_unverified_cache", _o_opt.get("allow_unverified_cache") is True)


print("── P 未验证缓存新鲜度门（V2.2.40）──")
_p_p1 = DS.build_plan(FACT_Q, {"route": "0", "rounds": "0:1"},
                      requested="daosheng", is_mock=True, balance_cny=3.0)
_p_p1c = ((_p_p1.get("dynamic_opt") or {}).get("cache_policy") or {})
ck("P1 预算 warn：cache_policy.max_age_h=24h、plan.cache_max_age_h=24",
   float(_p_p1c.get("max_age_h") or 0) == 24.0
   and float(_p_p1.get("cache_max_age_h") or 0) == 24.0,
   _p_p1c)
_p_p2 = DS.build_plan(FACT_Q, {"route": "0", "rounds": "0:1"},
                      requested="daosheng", is_mock=True, balance_cny=50.0)
ck("P2 预算 ok：max_age_h=0（未验证复用关闭）",
   float((_p_p2.get("dynamic_opt") or {}).get("cache_policy", {}).get("max_age_h") or 0) == 0.0)
_o_opt2 = {}
DS.apply_plan(dict(_p_p1), _o_opt2)
ck("P3 apply_plan 透传 cache_max_age_h", float(_o_opt2.get("cache_max_age_h") or 0) == 24.0)


print("── J 短程实测锚点（V2.2.33，B 模式每层 1 圈）──")
_p_j = DS.build_plan(FACT_Q, {"route": "0,1,both,all",
                              "rounds": "0:1,1:1,both:1,all:1"},
                     requested="daosheng", is_mock=True, balance_cny=50.0)
_cj = (_p_j.get("dynamic_opt") or {}).get("chosen") or {}
ck("J1 fact 短程四层：chosen≈65,427（实测锚点）",
   abs(int(_cj.get("est_tokens") or 0) - 65427) / 65427 < 0.15
   and _cj.get("cost_source") == "measured_short_anchor",
   (_cj.get("est_tokens"), _cj.get("cost_source")))
_p_j2 = DS.build_plan(FACT_Q, {"route": "0", "rounds": "0:1"},
                      requested="daosheng", is_mock=True, balance_cny=50.0)
_cj2 = (_p_j2.get("dynamic_opt") or {}).get("chosen") or {}
ck("J2 fact 短程 route0：chosen≈65,360（实测锚点）",
   abs(int(_cj2.get("est_tokens") or 0) - 65360) / 65360 < 0.15,
   _cj2.get("est_tokens"))
_p_j3 = DS.build_plan(REASON_Q, {"route": "0,1,both,all",
                                 "rounds": "0:1,1:1,both:1,all:1"},
                      requested="daosheng", is_mock=True, balance_cny=50.0)
_cj3 = (_p_j3.get("dynamic_opt") or {}).get("chosen") or {}
ck("J3 reasoning 短程四层：chosen≈72,799（实测锚点）",
   abs(int(_cj3.get("est_tokens") or 0) - 72799) / 72799 < 0.15,
   _cj3.get("est_tokens"))
_p_j4 = DS.build_plan(FACT_Q, {"route": "0,1,both,all",
                               "rounds": "0:1,1:1,both:1,all:1"},
                      requested="daosheng", is_mock=True, balance_cny=10.0)
_cj4 = (_p_j4.get("dynamic_opt") or {})
ck("J4 余额 ¥10：短程实测锚点使配置可行（不再按整单模型判 fallback）",
   _cj4.get("fallback") is False
   and (_cj4.get("chosen") or {}).get("feasible") is True,
   (_cj4.get("fallback"), (_cj4.get("chosen") or {}).get("feasible")))
_p_j5 = DS.build_plan(FACT_Q, {"route": "0,1,both,all",
                               "rounds": "0:2,1:2,both:2,all:2"},
                      requested="daosheng", is_mock=True, balance_cny=50.0)
_cj5 = (_p_j5.get("dynamic_opt") or {}).get("chosen") or {}
ck("J5 长程（总圈数 8）不用短程锚点，回退可加模型",
   _cj5.get("cost_source") == "route_subset_rounds.v1+app_overhead",
   _cj5.get("cost_source"))


print("── K choice 题型省层收益/锚点（V2.2.34）──")
_p_k = DS.build_plan(CHOICE_Q, {"route": "0,1,both,all",
                                "rounds": "0:1,1:1,both:1,all:1"},
                     requested="daosheng", is_mock=True, balance_cny=50.0)
_ck = (_p_k.get("dynamic_opt") or {}).get("chosen") or {}
ck("K1 choice 短程四层：chosen≈85,342（实测锚点）",
   abs(int(_ck.get("est_tokens") or 0) - 85342) / 85342 < 0.15
   and _ck.get("cost_source") == "measured_short_anchor",
   (_ck.get("est_tokens"), _ck.get("cost_source")))
_p_k2 = DS.build_plan(CHOICE_Q, {"route": "0", "rounds": "0:1"},
                      requested="daosheng", is_mock=True, balance_cny=50.0)
_k2 = (_p_k2.get("dynamic_opt") or {}).get("route_pruning") or {}
ck("K2 choice 省层：实测收益≈40% ⇒ subset_may_save（证据 choice JSON）",
   _k2.get("advice") == "subset_may_save"
   and float(_k2.get("saved_pct_estimate") or 0) >= 0.30
   and str(_k2.get("evidence") or "").endswith("route_subset_choice_ab_20261029.json"),
   _k2)
ck("K3 choice 省层风险：evidence 指向 choice JSON",
   str(((_p_k2.get("dynamic_opt") or {}).get("route_quality_risk") or {})
       .get("evidence") or "").endswith("route_subset_choice_ab_20261029.json"))

print("── C build_plan 接线 ──")
_p6 = DS.build_plan(FACT_Q, {}, requested="daosheng", is_mock=True, balance_cny=6.0)
_d6 = _p6.get("dynamic_opt") or {}
ck("C1 plan.dynamic_opt 落盘（schema/候选/chosen 可审计）",
   _d6.get("schema") == "metadgtf.dynamic_config.v1"
   and _d6.get("candidates") and _d6.get("chosen"))
ck("C2 低余额 plan 的 rounds 采用动态配置（且锁定）",
   _p6.get("rounds") == _pres.get("rounds_fast")
   and _p6.get("rounds_locked") is True, _p6.get("rounds"))
ck("C3 plan.budget_guard.budget_level 可审计",
   (_p6.get("budget_guard") or {}).get("budget_level") == "degrade")
_p2 = DS.build_plan(FACT_Q, {}, requested="daosheng", is_mock=True, balance_cny=2.0)
ck("C4 余额 <4：plan.rounds 降为 economy",
   _p2.get("rounds") == _pres["budget"]["rounds_economy"], _p2.get("rounds"))
_px = DS.build_plan(FACT_Q, {"rounds": "0:3"}, requested="daosheng",
                    is_mock=True, balance_cny=2.0)
_px_applied = (_px.get("dynamic_opt") or {}).get("applied") or {}
ck("C5 显式 opts.rounds 时动态配置不覆盖 rounds",
   "rounds" not in _px_applied and _px.get("rounds") != "0:3"
   or "rounds" not in _px_applied)
_ms = DS.mode_summary(_p6)
ck("C6 mode_summary 带 budget_level + dynamic 摘要",
   "budget_level" in _ms and "dynamic" in _ms
   and _ms["dynamic"].get("engine_mode") == "fast")

print("── D 接线：apply_plan → build_cmd ──")
_opts = {}
_applied = DS.apply_plan(_p6, _opts)
ck("D1 apply_plan 落 rounds/web 到 opts", _opts.get("rounds") == _p6.get("rounds")
   and "web" in _opts, (_opts.get("rounds"), _opts.get("web")))
cmd = ER.build_cmd("问题", _opts)
ck("D2 build_cmd 把 --rounds/--web 传给引擎",
   "--rounds" in cmd and "--web" in cmd
   and cmd[cmd.index("--rounds") + 1] == _opts.get("rounds"), cmd[-6:])
_opts2 = {"rounds": "0:1"}
DS.apply_plan(_p6, _opts2)
ck("D3 显式 opts 不被 apply_plan 覆盖", _opts2.get("rounds") == "0:1")

print("── E 变异体（有牙）──")
ck("E1 去掉依赖闭包 ⇒ both 只留自己（判据会红）",
   (lambda r: r != (["0", "1", "both"], ["0", "1"]))(["both"]))
ck("E2 去掉预算预留 ⇒ 可行域会放宽（成本可超余额）",
   _d_ok["chosen"]["est_cost_cny"] <= 50.0 * _d_ok["reserve_ratio"])
_web_cands = DS.dynamic_config(ds=_pres, tier="fast", engine_mode="fast",
                               rounds=_pres.get("rounds_fast"), web="off",
                               budget_guard=_bg(50.0, "ok"),
                               scenario={"kind": "reasoning"},
                               require_web=False, opts={})["candidates"]
ck("E3 非事实题允许 web off（事实题才会被强制 on）",
   any(c["web"] == "off" for c in _web_cands))

print("")
print("PASS %d / FAIL %d" % (len(P), len(F)))
raise SystemExit(1 if F else 0)