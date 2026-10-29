# -*- coding: utf-8 -*-
"""[V2.2.27 / App 2.0.52] 有效 route 成本 + App 开销系数 + 阶段动态路由（dual_judge）。"""
from pathlib import Path
import py_compile

P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")


def rep(a, b):
    global t
    c = t.count(a)
    assert c == 1, "锚点 %d: %r" % (c, a[:70])
    t = t.replace(a, b)

# 1) App 路径开销（1 臂云实测 1.098 ≈ 1.10）
rep('''    "web_fact_factor": 1.12, # 事实题 web on 的 token 增量（实测约 +12%）''',
'''    "web_fact_factor": 1.12, # 事实题 web on 的 token 增量（实测约 +12%）
    # App 全流程开销（自省/质量门/归档；1 臂云实测 34,727/31,620=1.098；
    # docs/app_path_cost_calibration_20261029.json）
    "app_overhead": 1.10,''')

# 2) dynamic_config：token 估算乘 App 开销 + 记录
rep('''            q = base_q
            if wb == "on" and kind == "fact":''',
'''            tok = tok * float(_CALIB.get("app_overhead") or 1.0)
            q = base_q
            if wb == "on" and kind == "fact":''')
rep('''            "cost_model": "route_subset_rounds.v1",''',
'''            "cost_model": "route_subset_rounds.v1",
            "app_overhead": float(_CALIB.get("app_overhead") or 1.0),''')

# 3) 可行域容差 ±20%（估算 + App 开销；预算线附近保留更优档）
rep('''                # 估算误差容差 ±10%：预算线附近优先保留质量更高的可行档
                feasible = cost_eff <= max(0.01, float(balance) * reserve) * 1.10''',
'''                # 估算误差容差 ±20%（模型误差 + App 开销）：预算线附近保留更优档
                feasible = cost_eff <= max(0.01, float(balance) * reserve) * 1.20''')

# 4) build_plan：有效 route（显式 opts.route 优先）+ 传给动态配置
rep('''    _require_web = bool(_sc1.get("require_web")
                        or str(_sc1.get("kind") or "") == "fact"
                        or _opt_n >= 2)''',
'''    _require_web = bool(_sc1.get("require_web")
                        or str(_sc1.get("kind") or "") == "fact"
                        or _opt_n >= 2)
    # ★ [V2.2.27] 成本模型用"有效 route"：显式 opts.route 优先（否则会高估省层任务）
    _dyn_route = str(opts.get("route") or route)''')
rep('''                         project_related=_prj, route=route, cache=cache)''',
'''                         project_related=_prj, route=_dyn_route, cache=cache)''')

# 5) 阶段动态路由：warn/critical 非项目/非 quality_first => dual_judge=cache
rep('''    if dyn.get("fallback"):
        warnings.append("动态配置：无满足质量下限的可行解 → 取最低成本兜底"
                        "（质量下限 %.2f，余额 %s）"
                        % (dyn.get("quality_floor"), dyn.get("balance_cny")))''',
'''    if dyn.get("fallback"):
        warnings.append("动态配置：无满足质量下限的可行解 → 取最低成本兜底"
                        "（质量下限 %.2f，余额 %s）"
                        % (dyn.get("quality_floor"), dyn.get("balance_cny")))
    # ★ [V2.2.27] 阶段动态路由：预算紧张时 dual_judge 走 cache（不牺牲项目/quality_first）
    try:
        _djm_opt = str((plan_djm := dyn.get("budget_level")) or "")
    except Exception:  # noqa: BLE001
        _djm_opt = ""
    if (dyn.get("budget_level") in ("warn", "critical")
            and not _prj and not quality_first
            and opts.get("dual_judge_mode") in (None, "")):
        try:
            _dj_sup = bool((caps.get("supports") or {}).get("dual_judge_mode"))
        except Exception:  # noqa: BLE001
            _dj_sup = False
        if _dj_sup:
            plan_extra_djm = "cache"
            dyn.setdefault("applied", {})["dual_judge_mode"] = "cache"
            dyn["stage_routing"] = {"dual_judge_mode": "cache",
                                    "why": "预算层级=%s ⇒ 评审走 cache 降本"
                                           % dyn.get("budget_level")}
            warnings.append("阶段动态路由：预算%s ⇒ dual_judge=cache"
                            % dyn.get("budget_level"))
        else:
            plan_extra_djm = ""
    else:
        plan_extra_djm = ""''')

# 6) plan 字段：dual_judge_mode 动态值
rep('''        "dual_judge_mode": djm,''',
'''        "dual_judge_mode": (plan_extra_djm or djm),''')

P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK App V2.2.27 dynamic cost/route/stage")
