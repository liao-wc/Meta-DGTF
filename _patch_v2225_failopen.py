# -*- coding: utf-8 -*-
"""fail-open：余额未知时动态配置只审计、不改变原配置。"""
from pathlib import Path
import py_compile
P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")
old = '''    applied = {}
    if not opts.get("rounds") and str(chosen["rounds"]) != str(rounds or "auto"):
        applied["rounds"] = chosen["rounds"]'''
new = '''    applied = {}
    if not isinstance(balance, (int, float)):
        # ★ 余额未知（fail-open）：只审计候选，保持原配置（不改 rounds/web）
        _same = next((c for c in candidates
                      if str(c["rounds"]) == str(rounds or "auto")), None) \
            or candidates[0]
        chosen = _same
        applied = {}
        fallback = False
        why = "余额未知 → fail-open：保持原配置（候选仅供审计）"
        return {"schema": "metadgtf.dynamic_config.v1", "budget_level": level,
                "balance_cny": balance, "reserve_ratio": reserve,
                "quality_floor": round(floor, 4),
                "require_web": bool(require_web), "scenario": kind,
                "route": route, "cache_hit": bool((cache or {}).get("exact")),
                "candidates": candidates, "chosen": chosen,
                "applied": applied, "fallback": fallback, "why": why,
                "regret": 0.0}
    if not opts.get("rounds") and str(chosen["rounds"]) != str(rounds or "auto"):
        applied["rounds"] = chosen["rounds"]'''
assert t.count(old) == 1
t = t.replace(old, new)
P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK fail-open audit-only")
