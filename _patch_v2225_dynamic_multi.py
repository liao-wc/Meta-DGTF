# -*- coding: utf-8 -*-
"""[V2.2.25 / App 2.0.50] 动态配置细化：多圈档候选 + 缓存命中感知 + route 审计。"""
from pathlib import Path
import py_compile

P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")


def rep(a, b):
    global t
    c = t.count(a)
    assert c == 1, "锚点 %d: %r" % (c, a[:70])
    t = t.replace(a, b)


# 1) dynamic_config 签名：route/cache
rep('''                   scenario: dict | None = None, quality_first: bool = False,
                   require_web: bool = False, opts: dict | None = None,
                   project_related: bool = False) -> dict:''',
'''                   scenario: dict | None = None, quality_first: bool = False,
                   require_web: bool = False, opts: dict | None = None,
                   project_related: bool = False, route=None,
                   cache: dict | None = None) -> dict:''')

# 2) 候选 rounds：全档枚举（多目标），不再按层级只给一档
rep('''    # 候选 rounds：degrade 仍用实测 fast 档（质量已验证、成本可接受）；
    # warn 用 economy，critical 用最低圈；ok 保持传入值/quality_first。
    if level == "critical":
        _rounds_opts = [cfg.get("rounds_critical")]
    elif level == "warn":
        _rounds_opts = [cfg.get("rounds_economy")]
    elif level == "degrade" or tier == "fast":
        _rounds_opts = [ds.get("rounds_fast")]
    elif tier == "quality" and quality_first:
        _rounds_opts = [ds.get("rounds_quality") or "0:3,1:3,both:4,all:4"]
    else:
        _rounds_opts = [str(rounds or "auto")]
    _rounds_opts = [str(x) for x in _rounds_opts if x]''',
'''    # ★ [V2.2.25] 候选 rounds：全档枚举，由成本约束 + 质量排序共同选择
    #   （不再按预算层级硬编码单档；预算只决定"哪些候选可行"）。
    _rounds_opts: list[str] = []
    for _rc in (ds.get("rounds_fast"), cfg.get("rounds_economy"),
                cfg.get("rounds_critical"),
                ((ds.get("rounds_quality") or "0:3,1:3,both:4,all:4")
                 if (tier == "quality" and quality_first) else None),
                (str(rounds) if str(rounds or "") not in ("", "auto") else None)):
        if _rc and str(_rc) not in _rounds_opts:
            _rounds_opts.append(str(_rc))
    if not _rounds_opts:
        _rounds_opts = ["auto"]''')

# 3) 候选成本：缓存命中按 10% 计 + 记录 effective
rep('''            cost = round(tok / 1e6 * cny_m, 2)
            feasible = True
            if isinstance(balance, (int, float)):
                feasible = cost <= max(0.01, float(balance) * reserve)
            candidates.append({"engine_mode": engine_mode, "parallel": parallel,
                               "thinking": thinking, "effort": effort, "web": wb,
                               "rounds": rd, "est_quality": round(q, 4),
                               "est_tokens": int(tok), "est_cost_cny": cost,
                               "budget_level": level, "feasible": bool(feasible)})''',
'''            cost = round(tok / 1e6 * cny_m, 2)
            # ★ [V2.2.25] 缓存命中感知：精确命中 ⇒ 实际成本按 10% 计（近似零成本）
            _cache_hit = bool((cache or {}).get("exact"))
            cost_eff = round(cost * 0.1, 2) if _cache_hit else cost
            feasible = True
            if isinstance(balance, (int, float)):
                feasible = cost_eff <= max(0.01, float(balance) * reserve)
            candidates.append({"engine_mode": engine_mode, "parallel": parallel,
                               "thinking": thinking, "effort": effort, "web": wb,
                               "rounds": rd, "est_quality": round(q, 4),
                               "est_tokens": int(tok), "est_cost_cny": cost,
                               "est_cost_effective_cny": cost_eff,
                               "cache_hit": _cache_hit,
                               "budget_level": level, "feasible": bool(feasible)})''')

# 4) why / 返回字段：route + cache
rep('''    why = ("预算层级=%s 余额=%s 预留=%.0f%% → 选 quality=%.3f/tokens=%d/¥%.2f"
           % (level, ("¥%.2f" % float(balance)) if isinstance(balance, (int, float)) else "未知",
              reserve * 100, chosen["est_quality"], chosen["est_tokens"],
              chosen["est_cost_cny"]))
    return {"schema": "metadgtf.dynamic_config.v1", "budget_level": level,
            "balance_cny": balance, "reserve_ratio": reserve,
            "quality_floor": round(floor, 4), "require_web": bool(require_web),
            "scenario": kind, "candidates": candidates, "chosen": chosen,
            "applied": applied, "fallback": fallback, "why": why,
            "regret": 0.0 if not fallback else None}''',
'''    _cache_hit0 = bool((cache or {}).get("exact"))
    why = ("预算层级=%s 余额=%s 预留=%.0f%%%s → 选 quality=%.3f/tokens=%d/¥%.2f"
           % (level, ("¥%.2f" % float(balance)) if isinstance(balance, (int, float)) else "未知",
              reserve * 100, ("（缓存命中，按 10% 成本计）" if _cache_hit0 else ""),
              chosen["est_quality"], chosen["est_tokens"],
              chosen["est_cost_cny"]))
    return {"schema": "metadgtf.dynamic_config.v1", "budget_level": level,
            "balance_cny": balance, "reserve_ratio": reserve,
            "quality_floor": round(floor, 4), "require_web": bool(require_web),
            "scenario": kind, "route": route, "cache_hit": _cache_hit0,
            "candidates": candidates, "chosen": chosen,
            "applied": applied, "fallback": fallback, "why": why,
            "regret": 0.0 if not fallback else None}''')

# 5) build_plan：缓存预判提前到动态配置之前
rep('''    # ★ [V2.2.24] 全链路动态配置：预算（余额/预留/层级）× 质量（场景下限）×''',
'''    # ★ [V2.2.25] 缓存预判提前：动态配置需要知道"这次是否近似零成本"
    cache = cache_prediction(question, opts)
    # ★ [V2.2.24] 全链路动态配置：预算（余额/预留/层级）× 质量（场景下限）×''')
rep('''                         require_web=_require_web, opts=opts,
                         project_related=_prj)''',
'''                         require_web=_require_web, opts=opts,
                         project_related=_prj, route=route, cache=cache)''')
# 移除后面重复的 cache 预判
rep('''    cache = cache_prediction(question, opts)
    engine_desc = {"ok": bool(caps.get("ok")), "path": caps.get("path") or "",''',
'''    engine_desc = {"ok": bool(caps.get("ok")), "path": caps.get("path") or "",''')

P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK dynamic config multi-rounds + cache-aware")
