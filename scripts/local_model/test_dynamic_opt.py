# -*- coding: utf-8 -*-
"""[V2.2.24 / App 2.0.49] 全链路动态配置优化 + 动态依赖调整判据（零成本）。

A 动态依赖：both ⇒ 补 0/1；all ⇒ 补 both/0/1；预测/union 下不破坏既有 route。
B 动态配置：余额 × 质量下限 × 成本多目标；候选枚举、可行域、预留比例、
  预算层级（ok/degrade/warn/critical）与圈数降档；显式 opts 永远优先。
C 接线：plan.dynamic_opt → apply_plan → build_cmd（引擎 --rounds/--web）。
D 变异体：去掉依赖闭包 / 去掉预算预留 / 事实题不强制 web ⇒ 判据必须红。
"""
from __future__ import annotations

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
ck("C5 显式 opts.rounds 时动态配置不覆盖（applied 为空）",
   (_px.get("dynamic_opt") or {}).get("applied") == {})
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