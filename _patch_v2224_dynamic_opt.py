# -*- coding: utf-8 -*-
"""[V2.2.24 / App 2.0.49] 动态配置优化 + 动态依赖调整（route 闭包 / 预算多目标）。"""
from pathlib import Path
import py_compile

P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")


def rep(a, b):
    global t
    c = t.count(a)
    assert c == 1, "锚点命中 %d: %r" % (c, a[:70])
    t = t.replace(a, b)


# 1) 常量：route 依赖闭包
rep('''VALID_ROUTE = ("0", "1", "both", "all")''',
'''VALID_ROUTE = ("0", "1", "both", "all")

# ★ [V2.2.24] 层依赖闭包：both 需要 0/1 的上游产物；all 需要 both/0/1。
#   动态预测/预算裁剪后若留下 both/all，则补齐依赖，避免"调度了 all 却没有 upstream"。
_ROUTE_ORDER = ("0", "1", "both", "all")
_ROUTE_DEPS = {"both": ("0", "1"), "all": ("both", "0", "1")}


def route_with_deps(route_list) -> tuple[list, list]:
    """返回 (按顺序补全依赖后的 route, 新增条目)。纯函数，可单测。"""
    have = set(str(x) for x in (route_list or []) if str(x))
    added: list[str] = []
    changed = True
    while changed:
        changed = False
        for entry in list(have):
            for dep in _ROUTE_DEPS.get(entry, ()):
                if dep not in have:
                    have.add(dep)
                    added.append(dep)
                    changed = True
    ordered = [e for e in _ROUTE_ORDER if e in have]
    return ordered, added''')

# 2) 内置预算配置：动态配置旋钮
rep('''    "budget": {"cny_per_million_tokens": 2.0, "degrade_below_cny": 8.0,
               "warn_below_cny": 4.0, "est_tokens_default": 1300000,
               "raw_max_tokens_fallback": 2000000},''',
'''    "budget": {"cny_per_million_tokens": 2.0, "degrade_below_cny": 8.0,
               "warn_below_cny": 4.0, "est_tokens_default": 1300000,
               "raw_max_tokens_fallback": 2000000,
               # ★ [V2.2.24] 动态配置：预留比例/临界倍数/降档圈数模板
               "reserve_ratio": 0.5, "critical_est_mult": 1.2,
               "rounds_economy": "0:1,1:2,both:1,all:1",
               "rounds_critical": "0:1,1:1,both:1,all:1"},''')

# 3) budget_guard：加 budget_level / est_affordable（decision 语义不变）
rep('''    if balance < warn_b:
        out["decision"] = "warn"''',
'''    # ★ [V2.2.24] 预算层级（动态配置用；decision 旧语义保持不变）
    _est_mult = float(cfg.get("critical_est_mult") or 1.2)
    _reserve = float(cfg.get("reserve_ratio") or 0.5)
    out["reserve_ratio"] = _reserve
    out["est_affordable"] = bool(balance >= est_cost / max(1e-6, _reserve))
    if balance < max(1.0, est_cost * _est_mult):
        out["budget_level"] = "critical"
    elif balance < warn_b:
        out["budget_level"] = "warn"
    elif balance < degrade_b:
        out["budget_level"] = "degrade"
    else:
        out["budget_level"] = "ok"
    if balance < warn_b:
        out["decision"] = "warn"''')

# 4) dynamic_config：多目标候选枚举/约束/选择（纯函数，可单测）
rep('''# ── 缓存命中预判 ───────────────────────────────────────────────''',
'''# ── 动态配置优化（预算/质量/时延多目标；纯函数）──────────────────
_DYN_TIER_FLOOR = {"project": 0.95, "quality_first": 0.95, "default": 0.90}
_WEB_TOKENS_EXTRA = 0.10   # 事实题 web on 的 token 增量（实测 ~+13.6 万 / 1.15M）


def _rounds_count(rounds) -> int:
    """解析 rounds 字符串里的总圈数（auto/空 => 0，表示交给引擎）。"""
    n = 0
    for part in str(rounds or "").split(","):
        part = part.strip()
        if ":" in part:
            try:
                n += int(part.rsplit(":", 1)[1])
            except (TypeError, ValueError):
                continue
    return n


def dynamic_config(*, ds: dict | None = None, tier: str = "quality",
                   engine_mode: str = "B", parallel: str = "B",
                   thinking: str = "auto", effort: str = "auto",
                   web: str = "auto", rounds="auto",
                   budget_guard: dict | None = None,
                   scenario: dict | None = None, quality_first: bool = False,
                   require_web: bool = False, opts: dict | None = None) -> dict:
    """在现有资源（余额/历史/场景）上枚举可行配置，选质量最高且成本可控者。

    返回可审计 dict；applied 只含安全可覆盖项（rounds/web），显式 opts 永远优先。
    """
    ds = ds or load_preset()
    bg = dict(budget_guard or {})
    opts = dict(opts or {})
    cfg = dict(_BUILTIN_DS["budget"])
    cfg.update(ds.get("budget") or {})
    cny_m = float(cfg.get("cny_per_million_tokens") or 2.0)
    reserve = float(cfg.get("reserve_ratio") or 0.5)
    balance = bg.get("balance_cny")
    level = str(bg.get("budget_level") or "ok")
    kind = str((scenario or {}).get("kind") or "")
    try:
        from dgtf_v2.mode_fusion import MODES as _MODES
    except Exception:  # noqa: BLE001
        _MODES = {}
    base = dict(_MODES.get(engine_mode) or {})
    base_q = float(base.get("quality") or (0.93 if engine_mode == "fast" else 1.0))
    base_tok = float(base.get("tokens") or (816983 if engine_mode == "fast" else 1269082))
    floor = float(opts.get("min_quality") or 0.0) or (
        _DYN_TIER_FLOOR["project"] if kind == "project" else
        (_DYN_TIER_FLOOR["quality_first"] if quality_first
         else _DYN_TIER_FLOOR["default"]))
    # 候选 rounds：按预算层级给 economy/critical 档
    if level in ("degrade", "warn", "critical") or tier == "fast":
        _rounds_opts = [cfg.get("rounds_economy")
                        if level in ("warn", "degrade") else
                        (cfg.get("rounds_critical") if level == "critical"
                         else ds.get("rounds_fast"))]
    elif tier == "quality" and quality_first:
        _rounds_opts = [ds.get("rounds_quality") or "0:3,1:3,both:4,all:4"]
    else:
        _rounds_opts = [str(rounds or "auto")]
    _rounds_opts = [str(x) for x in _rounds_opts if x]
    _web_opts = ["on"] if require_web else ([str(web)] if web not in ("", "auto") else ["off"])
    ref_count = max(1, _rounds_count("0:2,1:3,both:2,all:2"))
    candidates = []
    for rd in _rounds_opts:
        cnt = _rounds_count(rd)
        factor = 1.0 if cnt <= 0 else max(0.3, min(1.3, cnt / float(ref_count)))
        for wb in _web_opts:
            tok = base_tok * factor
            q = base_q
            if wb == "on" and kind == "fact":
                tok *= (1.0 + _WEB_TOKENS_EXTRA)
                q = max(q, 0.955)          # 事实 web on 实测 0.958（fast）
            if factor < 0.7:
                q -= 0.01                  # 低圈成本档的保守质量折扣
            cost = round(tok / 1e6 * cny_m, 2)
            feasible = True
            if isinstance(balance, (int, float)):
                feasible = cost <= max(0.01, float(balance) * reserve)
            candidates.append({"engine_mode": engine_mode, "parallel": parallel,
                               "thinking": thinking, "effort": effort, "web": wb,
                               "rounds": rd, "est_quality": round(q, 4),
                               "est_tokens": int(tok), "est_cost_cny": cost,
                               "budget_level": level, "feasible": bool(feasible)})
    feasible_cs = [c for c in candidates
                   if c["feasible"] and c["est_quality"] >= floor - 1e-9]
    fallback = not feasible_cs
    if feasible_cs:
        chosen = max(feasible_cs, key=lambda c: (c["est_quality"], -c["est_cost_cny"]))
    else:
        chosen = min(candidates, key=lambda c: (c["est_cost_cny"], -c["est_quality"]))
    applied = {}
    if not opts.get("rounds") and str(chosen["rounds"]) != str(rounds or "auto"):
        applied["rounds"] = chosen["rounds"]
    if not opts.get("web") and str(chosen["web"]) != str(web or "auto"):
        applied["web"] = chosen["web"]
    why = ("预算层级=%s 余额=%s 预留=%.0f%% → 选 quality=%.3f/tokens=%d/¥%.2f"
           % (level, ("¥%.2f" % float(balance)) if isinstance(balance, (int, float)) else "未知",
              reserve * 100, chosen["est_quality"], chosen["est_tokens"],
              chosen["est_cost_cny"]))
    return {"schema": "metadgtf.dynamic_config.v1", "budget_level": level,
            "balance_cny": balance, "reserve_ratio": reserve,
            "quality_floor": round(floor, 4), "require_web": bool(require_web),
            "scenario": kind, "candidates": candidates, "chosen": chosen,
            "applied": applied, "fallback": fallback, "why": why,
            "regret": 0.0 if not fallback else None}


# ── 缓存命中预判 ───────────────────────────────────────────────''')

P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK dynamic_config + route deps + budget levels")

# 5) build_plan：route 闭包
old_route = '''    route = ",".join(_route_list)
    if _route_policy != "predict" and _route_pred and _route_pred != _route_preset:
        warnings.append("route 安全门（%s）：预测=%s 未砍层，实际=%s"
                        % (_route_policy, ",".join(_route_pred), route))'''
new_route = '''    # ★ [V2.2.24] 动态依赖调整：补全层依赖（both ⇒ 0/1；all ⇒ both/0/1）
    _route_ordered, _route_added = route_with_deps(_route_list)
    _route_list = _route_ordered
    route = ",".join(_route_list)
    if _route_added:
        warnings.append("层依赖闭包：补 %s（both 需 0/1，all 需 both/0/1）"
                        % ",".join(_route_added))
    if _route_policy != "predict" and _route_pred and _route_pred != _route_preset:
        warnings.append("route 安全门（%s）：预测=%s 未砍层，实际=%s"
                        % (_route_policy, ",".join(_route_pred), route))'''
assert t.count(old_route) == 1
t = t.replace(old_route, new_route)

# 6) build_plan：web 规则后插入动态配置
old_dyn = '''    memory = memory_summary(question, ds, project_related=_prj, history=history)'''
new_dyn = '''    # ★ [V2.2.24] 全链路动态配置：预算（余额/预留/层级）× 质量（场景下限）×
    #   成本（token 估算）多目标枚举，选可行解中质量最高、成本最低者。
    _require_web = bool(_sc1.get("require_web")
                        or str(_sc1.get("kind") or "") == "fact"
                        or _opt_n >= 2)
    dyn = dynamic_config(ds=ds, tier=tier, engine_mode=engine_mode,
                         parallel=parallel, thinking=thinking, effort=effort,
                         web=web, rounds=rounds, budget_guard=bg,
                         scenario=_sc1, quality_first=quality_first,
                         require_web=_require_web, opts=opts)
    _dyn_applied = dyn.get("applied") or {}
    if _dyn_applied.get("rounds"):
        rounds = str(_dyn_applied["rounds"])
        rounds_locked = True
        warnings.append("动态配置：预算层级=%s→圈数降为 %s"
                        % (dyn.get("budget_level"), rounds))
    if _dyn_applied.get("web"):
        web = str(_dyn_applied["web"])
    if dyn.get("fallback"):
        warnings.append("动态配置：无满足质量下限的可行解 → 取最低成本兜底"
                        "（质量下限 %.2f，余额 %s）"
                        % (dyn.get("quality_floor"), dyn.get("balance_cny")))
    memory = memory_summary(question, ds, project_related=_prj, history=history)'''
assert t.count(old_dyn) == 1
t = t.replace(old_dyn, new_dyn)

# 7) plan 字段
old_plan = '''        "route": route,
        # [V2.2.23] route 安全门读数（可审计）
        "route_policy": _route_policy,
        "route_source": _route_source,
        "route_prediction": list(_route_pred),
        "rounds": rounds,'''
new_plan = '''        "route": route,
        # [V2.2.23] route 安全门读数（可审计）
        "route_policy": _route_policy,
        "route_source": _route_source,
        "route_prediction": list(_route_pred),
        # [V2.2.24] 动态依赖调整 + 动态配置优化
        "route_dependency_added": list(_route_added),
        "dynamic_opt": dyn,
        "rounds": rounds,'''
assert t.count(old_plan) == 1
t = t.replace(old_plan, new_plan)

# 8) mode_summary
old_sum = '''            "budget_decision": bg.get("decision") or "",
            "reason": str(plan.get("reason") or "")[:300]}'''
new_sum = '''            "budget_decision": bg.get("decision") or "",
            "budget_level": bg.get("budget_level") or "",
            "dynamic": {k: v for k, v in
                        ((plan.get("dynamic_opt") or {}).get("chosen") or {}).items()
                        if k in ("engine_mode", "web", "rounds",
                                 "est_quality", "est_cost_cny")},
            "reason": str(plan.get("reason") or "")[:300]}'''
assert t.count(old_sum) == 1
t = t.replace(old_sum, new_sum)

P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK build_plan dynamic config + route closure + mode_summary")
