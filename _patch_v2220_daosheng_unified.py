# -*- coding: utf-8 -*-
"""[V2.2.20 / App 2.0.45] 道生支路接入统一模式体系（方案 A）。"""
from pathlib import Path
import py_compile


def rep(path, pairs):
    p = Path(path)
    t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        n = t.count(a)
        assert n == 1, "%s 锚点命中 %d 次: %r" % (path, n, a[:70])
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8")
    py_compile.compile(str(p), doraise=True)
    print("OK", path)


# ── 1) mode_fusion：dynamic_adjust 支持 rounds_locked ──────────────
p = Path("dgtf_engine/dgtf_v2/mode_fusion.py")
t = p.read_text(encoding="utf-8")
old = '''    if (mode == "fast" and target is not None and qprox is not None
            and float(qprox) < float(target)):
        return {"action": "upgrade", "from": mode, "to": "B",
                "patch": {"thinking": "auto", "rounds_extra": 1},
                "reason": "运行期质量代理 %.2f < 目标 %.2f => 升档 B（时间换质量）"
                          % (float(qprox), float(target)),'''
new = '''    _locked = bool(plan.get("rounds_locked"))
    if (mode == "fast" and target is not None and qprox is not None
            and float(qprox) < float(target)):
        _patch = {"thinking": "auto"}
        if not _locked:
            _patch["rounds_extra"] = 1
        return {"action": "upgrade", "from": mode, "to": "B",
                "patch": _patch,
                "reason": "运行期质量代理 %.2f < 目标 %.2f => 升档 B（时间换质量；%s）"
                          % (float(qprox), float(target),
                             "rounds 锁定，不改圈" if _locked else "补 1 圈"),'''
assert t.count(old) == 1
t = t.replace(old, new)
old2 = '''            why = ("墙钟预算过半而进度不足半" if wall_over else "tokens 已用 70%")
            return {"action": "downgrade", "from": mode, "to": "fast",
                    "patch": {"thinking": "off", "web": False, "cap_rounds": 1},
                    "reason": "%s => 降档 fast（质量下限 %.2f <= fast 0.93，仍满足）"
                              % (why, floor),'''
new2 = '''            why = ("墙钟预算过半而进度不足半" if wall_over else "tokens 已用 70%")
            _patch = {"thinking": "off", "web": False}
            if not _locked:
                _patch["cap_rounds"] = 1
            return {"action": "downgrade", "from": mode, "to": "fast",
                    "patch": _patch,
                    "reason": "%s => 降档 fast（质量下限 %.2f <= fast 0.93，仍满足；%s）"
                              % (why, floor,
                                 "rounds 锁定，不改圈" if _locked else "剩余圈数压到 +1"),'''
assert t.count(old2) == 1
t = t.replace(old2, new2)
p.write_text(t, encoding="utf-8")
py_compile.compile(str(p), doraise=True)
print("OK mode_fusion rounds_locked")

# ── 2) daosheng_mode：统一模式配置 + mode 透传 + 锁定标记 ──────────
D = Path("dgtf_app/daosheng_mode.py")
t = D.read_text(encoding="utf-8")
old = '''    route = ",".join((local.get("route") or _norm_route(ds.get("route"))))
    if tier == "fast":
        rounds = ds.get("rounds_fast") or "0:2,1:3,both:2,all:2"
        parallel, web, thinking, effort = "serial", "off", "off", "auto"
        # [Round 23] 修复后重测：fast+web on 事实题 thinking off 亦 verified
        #（0.9472/0.9726）⇒ 不再强制 thinking=auto；web 仍由场景规则强制 on。
        _scf = _scenario_of(m4)
        if _scf.get("require_web") or str(_scf.get("kind") or "") == "fact":
            web = "on"
    else:
        rounds = (ds.get("rounds_quality") or "0:3,1:3,both:4,all:4") if (
            quality_first and bg.get("decision") == "ok") else (ds.get("rounds") or "auto")
        parallel = ds.get("parallel") or "B"
        if engine_mode == "serial":
            parallel = "serial"
        web, thinking, effort = ds.get("web") or "auto", ds.get("thinking") or "auto", ds.get("effort") or "auto"
'''
new = '''    route = ",".join((local.get("route") or _norm_route(ds.get("route"))))
    # ★ [V2.2.20 / 方案 A] 道生支路接入统一模式体系：
    #   engine_mode（B/fast/serial）对应 MODE_CONFIGS 的专门配置作为默认值；
    #   道生预设显式值（rounds/rounds_quality/rounds_fast/parallel）与场景规则
    #   （事实/选项题强制 web）仍然优先 ⇒ 默认行为不变，配置来源统一 +
    #   引擎可据此启用运行期 dynamic_adjust。
    try:
        from dgtf_v2.mode_fusion import MODE_CONFIGS as _MODE_CONFIGS
        _unified_cfg = dict(_MODE_CONFIGS.get(engine_mode) or {})
    except Exception:  # noqa: BLE001
        _unified_cfg = {}
    if tier == "fast":
        rounds = ds.get("rounds_fast") or "0:2,1:3,both:2,all:2"
        # 统一模式配置：fast => parallel=B / thinking=off（实测 782s/817k 档）
        parallel = _unified_cfg.get("parallel") or "serial"
        thinking = _unified_cfg.get("thinking") or "off"
        effort = _unified_cfg.get("effort") or "auto"
        web = "off"
        _scf = _scenario_of(m4)
        if _scf.get("require_web") or str(_scf.get("kind") or "") == "fact":
            web = "on"
    else:
        rounds = (ds.get("rounds_quality") or "0:3,1:3,both:4,all:4") if (
            quality_first and bg.get("decision") == "ok") else (ds.get("rounds") or "auto")
        parallel = ds.get("parallel") or _unified_cfg.get("parallel") or "B"
        if engine_mode == "serial":
            parallel = _unified_cfg.get("parallel") or "serial"
        _think = str(ds.get("thinking") or "auto")
        _eff = str(ds.get("effort") or "auto")
        thinking = _unified_cfg.get("thinking") if _think in ("", "auto") \\
            else _think
        effort = _unified_cfg.get("effort") if _eff in ("", "auto") else _eff
        thinking = thinking or "auto"
        effort = effort or "auto"
        web = ds.get("web") or "auto"
    #: 显式 rounds（道生质量档/快档）已锁定圈数 ⇒ 运行期动态调整不改圈。
    rounds_locked = str(rounds) not in ("", "auto", "None")
    if _unified_cfg:
        warnings.append(
            "统一模式配置：engine_mode=%s → parallel=%s/thinking=%s/effort=%s"
            "（rounds=%s%s）"
            % (engine_mode, parallel, thinking, effort, rounds,
               "，锁定" if rounds_locked else ""))
'''
assert t.count(old) == 1
t = t.replace(old, new)
old2 = '''        "tier": tier,
        "engine_mode": engine_mode,
        "mode_reason": mode_reason,
'''
new2 = '''        "tier": tier,
        "engine_mode": engine_mode,
        # [V2.2.20 方案 A] 统一模式体系：引擎据此启用 MODE_CONFIGS + dynamic_adjust
        "mode": engine_mode,
        "unified_config": dict(_unified_cfg or {}),
        "rounds_locked": bool(rounds_locked),
        "mode_reason": mode_reason,
'''
assert t.count(old2) == 1
t = t.replace(old2, new2)
old3 = '''    for k in ("route", "rounds", "parallel", "web", "thinking", "effort",
              "self_check_mode", "dual_judge_mode", "history_fusion"):
'''
new3 = '''    for k in ("mode", "route", "rounds", "parallel", "web", "thinking",
              "effort", "self_check_mode", "dual_judge_mode",
              "history_fusion"):
'''
assert t.count(old3) == 1
t = t.replace(old3, new3)
old4 = '''        return {"enabled": True, "ok": True, "features": feats,
                "first_mode": str(first.get("mode") or ""),
                "first_reason": str(first.get("reason") or ""),
'''
new4 = '''        return {"enabled": True, "ok": True, "features": feats,
                "first_mode": str(first.get("mode") or ""),
                "first_reason": str(first.get("reason") or ""),
                # [V2.2.20] 统一模式体系回显：模式专属配置与最优性证据
                "first_config": dict(first.get("config") or {}),
                "optimality": plan.get("optimality") or {},
                "policy": plan.get("policy") or "",
'''
assert t.count(old4) == 1
t = t.replace(old4, new4)
D.write_text(t, encoding="utf-8")
py_compile.compile(str(D), doraise=True)
print("OK daosheng_mode unified")

# ── 3) server：道生分支回显统一模式信息 ────────────────────────────
S = Path("dgtf_app/server.py")
t = S.read_text(encoding="utf-8")
old5 = '''                _fused_info = {"enabled": False, "skipped": "daosheng_plan",
                               "mode": _ds_plan.get("engine_mode"),
                               "reason": _ds_plan.get("mode_reason")}'''
new5 = '''                # [V2.2.20 方案 A] 道生支路已接入统一模式体系：回显
                # MODE_CONFIGS 与 dynamic_adjust 是否启用（引擎侧 --mode 已透传）。
                _fused_info = {"enabled": False, "skipped": "daosheng_plan",
                               "unified": True,
                               "mode": _ds_plan.get("engine_mode"),
                               "config": _ds_plan.get("unified_config") or {},
                               "rounds_locked": bool(
                                   _ds_plan.get("rounds_locked")),
                               "dynamic": True,
                               "reason": _ds_plan.get("mode_reason")}'''
assert t.count(old5) == 1
t = t.replace(old5, new5)
S.write_text(t, encoding="utf-8")
py_compile.compile(str(S), doraise=True)
print("OK server daosheng fused_info")
