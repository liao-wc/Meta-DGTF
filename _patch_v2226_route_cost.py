# -*- coding: utf-8 -*-
"""[V2.2.26 / App 2.0.51] route 子集感知成本模型（用 3 臂云实测校准）。"""
from pathlib import Path
import py_compile

P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")


def rep(a, b):
    global t
    c = t.count(a)
    assert c == 1, "锚点 %d: %r" % (c, a[:70])
    t = t.replace(a, b)


# 1) 校准常量 + 层/圈可加成本模型
rep('''_DYN_TIER_FLOOR = {"project": 0.95, "quality_first": 0.95, "default": 0.90}
_WEB_TOKENS_EXTRA = 0.10   # 事实题 web on 的 token 增量（实测 ~+13.6 万 / 1.15M）''',
'''_DYN_TIER_FLOOR = {"project": 0.95, "quality_first": 0.95, "default": 0.90}
_WEB_TOKENS_EXTRA = 0.10   # 事实题 web on 的 token 增量（实测 ~+13.6 万 / 1.15M）

# ★ [V2.2.26] route 子集感知成本模型（3 臂有界云实测校准：
#   docs/dynamic_cost_calibration_20261029.json；fast/web-off/单层单圈口径）
_CALIB = {
    "u0": 31620.0,          # 层 0 每圈 tokens（fast；R3=63,240/2）
    "u1": 37119.0,          # 层 1 每圈 tokens（fast；R1）
    "multi_overlap": 0.905, # 两层可加性的重叠系数（R2 实测/可加预测）
    "full_default_tokens": 816983.0,   # fast 四层默认圈数（2,3,2,2）整单实测
    "web_fact_factor": 1.12, # 事实题 web on 的 token 增量（实测约 +12%）
    "fast_default_rounds": {"0": 2, "1": 3, "both": 2, "all": 2},
}
_un0, _un1 = _CALIB["u0"], _CALIB["u1"]
_avg = (_un0 + _un1) / 2.0
_base01 = 2 * _un0 + 3 * _un1
_remain = max(1.0, _CALIB["full_default_tokens"] - _base01)
_uB = _remain / (2 + 2 * (4.0 / 3.0))
_CALIB["both"] = round(_uB, 1)
_CALIB["all"] = round(_uB * 4.0 / 3.0, 1)


def _route_round_tokens(route, rounds, engine_mode="fast", web="off",
                        kind="") -> float:
    """层子集 × 圈数的 token 估算（fast 校准；其他 mode 按 MODES 比例缩放）。"""
    import re as _re
    entries = [e.strip() for e in str(route or "").split(",") if e.strip()]
    if not entries:
        entries = ["0", "1", "both", "all"]
    rmap = dict(_CALIB["fast_default_rounds"])
    for part in str(rounds or "").split(","):
        part = part.strip()
        if ":" in part:
            k, v = part.rsplit(":", 1)
            try:
                rmap[k.strip()] = int(v)
            except (TypeError, ValueError):
                pass
    tok = 0.0
    for e in entries:
        unit = _CALIB.get(e)
        if unit:
            tok += float(unit) * float(rmap.get(e, 1) or 1)
    if len(entries) > 1:
        tok *= _CALIB["multi_overlap"]
    # mode 比例：以 fast 为基准，其余按 MODES tokens 比例
    try:
        from dgtf_v2.mode_fusion import MODES as _MODES
        _fast = float((_MODES.get("fast") or {}).get("tokens") or 816983.0)
        _mode = float((_MODES.get(engine_mode) or {}).get("tokens") or _fast)
        tok *= (_mode / _fast)
    except Exception:  # noqa: BLE001
        pass
    if str(web) == "on" and str(kind) == "fact":
        tok *= _CALIB["web_fact_factor"]
    return round(tok, 1)''')

# 2) dynamic_config 候选成本改用 route 子集模型
rep('''        for wb in _web_opts:
            tok = base_tok * factor
            q = base_q''',
'''        for wb in _web_opts:
            try:
                tok = _route_round_tokens(route, rd, engine_mode=engine_mode,
                                          web=wb, kind=kind)
            except Exception:  # noqa: BLE001
                tok = base_tok * factor
            q = base_q''')

# 3) dynamic_opt 记录成本模型口径
rep('''            "scenario": kind, "route": route, "cache_hit": _cache_hit0,
            "candidates": candidates, "chosen": chosen,''',
'''            "scenario": kind, "route": route, "cache_hit": _cache_hit0,
            "cost_model": "route_subset_rounds.v1",
            "candidates": candidates, "chosen": chosen,''')

P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK route-subset cost model")
