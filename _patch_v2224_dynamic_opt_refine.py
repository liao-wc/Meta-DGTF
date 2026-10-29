# -*- coding: utf-8 -*-
"""[V2.2.24] 动态配置微调：degrade 用实测 fast 圈数；project 质量下限 0.95；未知余额标记。"""
from pathlib import Path
import py_compile

P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")

# 1) budget_guard 未知余额：budget_level=unknown
old = '''        out["fail_open"] = True
        out["reason"] = ("余额未知（%s）→ fail-open：不拒绝任务，按质量档继续"
                         % ("mock 跳过查询" if src == "mock-skip" else "查询失败"))
        return out'''
new = '''        out["fail_open"] = True
        out["budget_level"] = "unknown"
        out["reason"] = ("余额未知（%s）→ fail-open：不拒绝任务，按质量档继续"
                         % ("mock 跳过查询" if src == "mock-skip" else "查询失败"))
        return out'''
assert t.count(old) == 1
t = t.replace(old, new)

# 2) dynamic_config 增加 project_related；degrade 用实测 fast 圈数
old2 = '''                   scenario: dict | None = None, quality_first: bool = False,
                   require_web: bool = False, opts: dict | None = None) -> dict:'''
new2 = '''                   scenario: dict | None = None, quality_first: bool = False,
                   require_web: bool = False, opts: dict | None = None,
                   project_related: bool = False) -> dict:'''
assert t.count(old2) == 1
t = t.replace(old2, new2)

old3 = '''    floor = float(opts.get("min_quality") or 0.0) or (
        _DYN_TIER_FLOOR["project"] if kind == "project" else
        (_DYN_TIER_FLOOR["quality_first"] if quality_first
         else _DYN_TIER_FLOOR["default"]))'''
new3 = '''    floor = float(opts.get("min_quality") or 0.0) or (
        _DYN_TIER_FLOOR["project"] if (project_related or kind == "project") else
        (_DYN_TIER_FLOOR["quality_first"] if quality_first
         else _DYN_TIER_FLOOR["default"]))'''
assert t.count(old3) == 1
t = t.replace(old3, new3)

old4 = '''    # 候选 rounds：按预算层级给 economy/critical 档
    if level in ("degrade", "warn", "critical") or tier == "fast":
        _rounds_opts = [cfg.get("rounds_economy")
                        if level in ("warn", "degrade") else
                        (cfg.get("rounds_critical") if level == "critical"
                         else ds.get("rounds_fast"))]
    elif tier == "quality" and quality_first:
        _rounds_opts = [ds.get("rounds_quality") or "0:3,1:3,both:4,all:4"]
    else:
        _rounds_opts = [str(rounds or "auto")]'''
new4 = '''    # 候选 rounds：degrade 仍用实测 fast 档（质量已验证、成本可接受）；
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
        _rounds_opts = [str(rounds or "auto")]'''
assert t.count(old4) == 1
t = t.replace(old4, new4)

# 3) build_plan 调用传入 project_related
old5 = '''                         scenario=_sc1, quality_first=quality_first,
                         require_web=_require_web, opts=opts)'''
new5 = '''                         scenario=_sc1, quality_first=quality_first,
                         require_web=_require_web, opts=opts,
                         project_related=_prj)'''
assert t.count(old5) == 1
t = t.replace(old5, new5)

P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK dynamic config refinements")
