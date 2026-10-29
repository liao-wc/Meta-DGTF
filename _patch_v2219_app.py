# -*- coding: utf-8 -*-
"""[V2.2.19] App 接入输入驱动最优模式：server 走 plan_for_input/apply_mode_opts；runner 透传 --mode。"""
from pathlib import Path
import py_compile


def rep_file(path, pairs):
    p = Path(path)
    t = p.read_text(encoding="utf-8")
    for a, b in pairs:
        n = t.count(a)
        assert n == 1, "%s 锚点命中 %d 次: %r" % (path, n, a[:60])
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8")
    py_compile.compile(str(p), doraise=True)
    print("OK", path)


# ── 1) engine_runner：透传 --mode（能力门控）────────────────────────
rep_file("dgtf_app/engine_runner.py", [
    ('''    "history_fusion": "--history-fusion",
    "self_check_mode": "--self-check-mode",
    "dual_judge_mode": "--dual-judge-mode",
}''',
     '''    "history_fusion": "--history-fusion",
    "self_check_mode": "--self-check-mode",
    "dual_judge_mode": "--dual-judge-mode",
    # ★ [V2.2.19] 输入驱动自动模式（引擎 V2.2.19+ 才有；能力门控见 _GATED_FLAGS）
    "mode": "--mode",
}'''),
    ('''_CAPABILITY_FLAGS = {
    "self_check_mode": "--self-check-mode",
    "dual_judge_mode": "--dual-judge-mode",
    "history_fusion": "--history-fusion",
}''',
     '''_CAPABILITY_FLAGS = {
    "self_check_mode": "--self-check-mode",
    "dual_judge_mode": "--dual-judge-mode",
    "history_fusion": "--history-fusion",
    # ★ [V2.2.19] 自动模式选择（旧引擎无此 flag => 门控自动不透传）
    "auto_mode": "--mode",
}'''),
    ('_GATED_FLAGS = {"--history-fusion", "--self-check-mode", "--dual-judge-mode"}',
     '_GATED_FLAGS = {"--history-fusion", "--self-check-mode", "--dual-judge-mode",\n                "--mode"}'),
])

# ── 2) server：auto-fused 分支改成输入驱动最优选档 + 每模式专属配置 ────
SRV = Path("dgtf_app/server.py")
t = SRV.read_text(encoding="utf-8")

# 2a) 默认启用（保留 env kill switch）
old = '''            _fused_opt = opts.pop("auto_fused", None)
            _auto_fused = (bool(_fused_opt) if _fused_opt is not None
                           else not _is_mock_task)'''
new = '''            # ★ [V2.2.19] 输入驱动自动模式选择：真实任务默认启用（由题面 + 预算
            #   枚举最优模式），mock/自检关闭以稳定基线。DGTF_AUTO_MODE=0 可全局关。
            _fused_opt = opts.pop("auto_fused", None)
            _auto_fused = (bool(_fused_opt) if _fused_opt is not None
                           else (not _is_mock_task
                                 and os.environ.get("DGTF_AUTO_MODE", "1") != "0"))'''
assert t.count(old) == 1
t = t.replace(old, new)

# 2b) 替换旧的 fused_plan + 硬编码 if/elif 模式分支
old_block = '''            if _auto_fused:
                try:
                    import sys as _sys
                    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                    from dgtf_v2.mode_fusion import fused_plan
                    from dgtf_v2.quality_predictor import question_features
                    _fw = opts.pop("fused_max_wall", None)
                    _ft = opts.pop("fused_max_tokens", None)
                    _fq = opts.pop("fused_min_quality", None)
                    _fr = bool(opts.pop("fused_require_web", False))
                    _fp = str(opts.pop("fused_prefer", "quality") or "quality")
                    _feat = question_features(question)
                    # 通用事实题联网接地是 opt-in：实测显式 web 曾 verified
                    # （0.9783/320.8s），但默认 web 变体出现 no_official_source
                    # （quality 0.49/needs_evidence），因此默认保持 web off。
                    _fg = bool(opts.pop("fused_ground_web", False))
                    _ground_web = bool(_fg and (not _project_ctx)
                                       and _feat.get("fact"))
                    _plan = fused_plan(
                        min_quality=(float(_fq) if _fq not in (None, "") else None),
                        max_wall=(float(_fw) if _fw not in (None, "") else None),
                        max_tokens=(int(_ft) if _ft not in (None, "") else None),
                        require_web=_fr, cascade=not _is_mock_task,
                        features=_feat)
                    _sel = _plan.get("first") or {}
                    _mode = str(_sel.get("mode") or "")
                    # ★ 关键：M4 选档必须显式落成引擎参数，否则
                    #   behavior_fusion=auto 会再把 web/thinking 强制打开，
                    #   把“质量/墙钟优先”变成高价档（App 真实链路实测发现）。
                    #   圈数也要给提示档：App 默认 no-rounds 实测跑到 5/6/4/7 圈，
                    #   tokens 1.92M、wall 26.9min；直接 B 给 1 圈提示只到 2/2/2/5。
                    opts.setdefault("rounds", "0:1,1:1,both:1,all:1")
                    opts.setdefault("behavior_fusion", "off")
                    if _mode == "B":
                        opts.setdefault("parallel", "B")
                        opts.setdefault("web", "on" if _ground_web else "off")
                        opts.setdefault("thinking", "auto")
                        opts.setdefault("effort", "auto")
                    elif _mode == "serial":
                        opts.setdefault("parallel", "serial")
                        opts.setdefault("web", "off")
                        opts.setdefault("thinking", "auto")
                        opts.setdefault("effort", "auto")
                    elif _mode == "fast":
                        opts.setdefault("parallel", "serial")
                        opts.setdefault("web", "off")
                        opts.setdefault("thinking", "off")
                        opts.setdefault("effort", "auto")
                    elif _mode == "web":
                        opts.setdefault("parallel", "serial")
                        opts.setdefault("web", "on")
                        opts.setdefault("thinking", "auto")
                        opts.setdefault("effort", "auto")
                    _fused_info.update({
                        "mode": _mode,
                        "reason": _sel.get("reason"),
                        "scenario": {"min_quality": _fq, "max_wall": _fw,
                                     "max_tokens": _ft, "require_web": _fr,
                                     "prefer": _fp},
                        "readout": _sel.get("info") or {},
                        "quality_prediction": _plan.get("quality_prediction"),
                        "quality_guard": _plan.get("quality_guard"),
                        "cascade": _plan.get("cascade"),
                        "features": _feat,
                        "grounding_web": bool(_ground_web),
                        "applied_opts": {k: opts.get(k) for k in (
                            "parallel", "web", "thinking", "effort",
                            "behavior_fusion", "rounds")},
                    })
                    print("[mode-fusion] task 选择模式 %s：%s"
                          % (_mode, _sel.get("reason")), flush=True)
                except Exception as exc:  # noqa: BLE001
                    _fused_info["error"] = str(exc)
                    print("[mode-fusion] 选择模式失败，退回默认：%s" % exc,
                          flush=True)'''
new_block = '''            if _auto_fused:
                try:
                    import sys as _sys
                    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                    # ★ [V2.2.19] 输入驱动最优选档：题面（事实/推理/选择/长度）
                    #   + 显式预算 => 枚举最优模式（B/serial/fast），每模式专属配置
                    #   由 MODE_CONFIGS 统一给出（不再硬编码 if/elif；web 是标志位）。
                    from dgtf_v2.mode_fusion import plan_for_input, apply_mode_opts
                    _fw = opts.pop("fused_max_wall", None)
                    _ft = opts.pop("fused_max_tokens", None)
                    _fq = opts.pop("fused_min_quality", None)
                    _fr = bool(opts.pop("fused_require_web", False))
                    _fp = str(opts.pop("fused_prefer", "quality") or "quality")
                    _mopts = {"prefer": _fp, "require_web": _fr}
                    if _fq not in (None, ""):
                        _mopts["min_quality"] = float(_fq)
                    if _fw not in (None, ""):
                        _mopts["max_wall"] = float(_fw)
                    if _ft not in (None, ""):
                        _mopts["max_tokens"] = int(_ft)
                    _plan = plan_for_input(question, _mopts)
                    _mode = str(_plan.get("mode") or "")
                    _applied = {}
                    if _mode:
                        opts, _applied = apply_mode_opts(opts, _plan)
                    # 通用事实题联网接地是 opt-in：实测显式 web 曾 verified，
                    # 默认 web 变体出现 no_official_source，故默认保持 web off。
                    _fg = bool(opts.pop("fused_ground_web", False))
                    _ground_web = bool(
                        _fg and (not _project_ctx)
                        and (_plan.get("preferences") or {}).get("kind") == "fact")
                    if _ground_web:
                        opts.setdefault("web", "on")
                        _applied["web"] = opts.get("web")
                    _fused_info.update({
                        "mode": _mode,
                        "reason": _plan.get("reason"),
                        "question_kind": _plan.get("question_kind"),
                        "preferences": _plan.get("preferences"),
                        "config": _plan.get("config"),
                        "optimality": _plan.get("optimality"),
                        "cascade": _plan.get("cascade"),
                        "grounding_web": bool(_ground_web),
                        "scope": ("显式指定" if (_plan.get("optimality") or {}).get("override")
                                  else "输入驱动枚举最优"),
                        "applied_opts": _applied,
                        "plan": _plan,
                    })
                    print("[mode-fusion] task 选择模式 %s（%s）：%s"
                          % (_mode, _plan.get("reason"),
                             (_plan.get("optimality") or {}).get("note")),
                          flush=True)
                except Exception as exc:  # noqa: BLE001
                    _fused_info["error"] = str(exc)
                    print("[mode-fusion] 选择模式失败，退回默认：%s" % exc,
                          flush=True)'''
assert t.count(old_block) == 1
t = t.replace(old_block, new_block)

# 2c) 模式面板接口：把每模式专属配置一起吐出来（只读展示）
old2 = '''        from dgtf_v2.mode_fusion import MODES, scenario_table'''
new2 = '''        from dgtf_v2.mode_fusion import MODES, MODE_CONFIGS, scenario_table'''
assert t.count(old2) == 1
t = t.replace(old2, new2)
old3 = '''                "kept": ["B", "serial", "fast"],'''
new3 = '''                "kept": ["B", "serial", "fast"],
                "configs": MODE_CONFIGS,'''
assert t.count(old3) == 1
t = t.replace(old3, new3)

SRV.write_text(t, encoding="utf-8")
py_compile.compile(str(SRV), doraise=True)
print("OK dgtf_app/server.py")
