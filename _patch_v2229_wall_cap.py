# -*- coding: utf-8 -*-
"""[V2.2.29 / App 2.0.54] 预算层级 → 运行期墙钟硬上限（动态依赖）。"""
from pathlib import Path
import py_compile

P = Path("dgtf_app/daosheng_mode.py")
t = P.read_text(encoding="utf-8")


def rep(a, b):
    global t
    c = t.count(a)
    assert c == 1, "锚点 %d: %r" % (c, a[:70])
    t = t.replace(a, b)

# 1) 墙钟上限（与 token 上限同层，warn/critical）
rep('''            dyn["budget_cap"] = {"max_tokens": budget_max_tokens,
                                 "based_on_est_tokens": _est,
                                 "why": "预算 %s 档的硬边界，防止估算偏差导致超支"
                                        % dyn.get("budget_level"))''',
'''            dyn["budget_cap"] = {"max_tokens": budget_max_tokens,
                                 "based_on_est_tokens": _est,
                                 "why": "预算 %s 档的硬边界，防止估算偏差导致超支"
                                        % dyn.get("budget_level"))
    # ★ [V2.2.29] 墙钟硬上限：按估算 tokens / 保守速率折算分钟数（×1.5 安全边界）
    budget_max_minutes = 0
    if (dyn.get("budget_level") in ("warn", "critical")
            and opts.get("max_minutes") in (None, "")):
        _est2 = int((dyn.get("chosen") or {}).get("est_tokens") or 0)
        if _est2 > 0:
            _tps = 600.0  # 保守：500-1000 tokens/s 区间取下沿
            _sec = _est2 / _tps * 1.5
            budget_max_minutes = max(1, int((_sec + 59) // 60))
            warnings.append("预算依赖：%s 档 ⇒ 运行期 max_minutes=%d（估算 %d tokens）"
                            % (dyn.get("budget_level"), budget_max_minutes, _est2))
            dyn.setdefault("applied", {})["max_minutes"] = budget_max_minutes
            dyn.setdefault("budget_cap", {})["max_minutes"] = budget_max_minutes''')

# 2) plan 字段
rep('''        # ★ [V2.2.28] 预算 warn/critical 时的运行期 token 硬上限（0=不限）
        "max_tokens": budget_max_tokens,''',
'''        # ★ [V2.2.28] 预算 warn/critical 时的运行期 token 硬上限（0=不限）
        "max_tokens": budget_max_tokens,
        # ★ [V2.2.29] 同期墙钟硬上限（分钟；0=不限）
        "max_minutes": budget_max_minutes,''')

# 3) apply_plan 透传
rep('''              "history_fusion", "max_tokens"):''',
'''              "history_fusion", "max_tokens", "max_minutes"):''')

P.write_text(t, encoding="utf-8")
py_compile.compile(str(P), doraise=True)
print("OK wall-time cap")
