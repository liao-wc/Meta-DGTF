# -*- coding: utf-8 -*-
"""清理阶段动态路由代码：移除无用 walrus，保证 plan_extra_djm 始终定义。"""
from pathlib import Path
import py_compile
P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")
old = '''    # ★ [V2.2.27] 阶段动态路由：预算紧张时 dual_judge 走 cache（不牺牲项目/quality_first）
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
        plan_extra_djm = ""'''
new = '''    # ★ [V2.2.27] 阶段动态路由：预算紧张时 dual_judge 走 cache（不牺牲项目/quality_first）
    plan_extra_djm = ""
    if (dyn.get("budget_level") in ("warn", "critical")
            and not _prj and not quality_first
            and opts.get("dual_judge_mode") in (None, "")):
        _dj_sup = bool((caps.get("supports") or {}).get("dual_judge_mode"))
        if _dj_sup:
            plan_extra_djm = "cache"
            dyn.setdefault("applied", {})["dual_judge_mode"] = "cache"
            dyn["stage_routing"] = {"dual_judge_mode": "cache",
                                    "why": "预算层级=%s ⇒ 评审走 cache 降本"
                                           % dyn.get("budget_level")}
            warnings.append("阶段动态路由：预算%s ⇒ dual_judge=cache"
                            % dyn.get("budget_level"))'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK cleanup")
