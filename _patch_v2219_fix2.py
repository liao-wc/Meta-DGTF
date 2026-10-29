# -*- coding: utf-8 -*-
"""[V2.2.19] 修正三处判据口径：B6 fallback 策略、C7 让位用例、F3 引擎接线口径。"""
from pathlib import Path

T = Path("dgtf_engine/dgtf_v2/tests_auto_mode_optimal.py")
s = T.read_text(encoding="utf-8")
REP = [
    # B6：显式墙钟上限不可行时，fallback 策略是「质量下限优先 -> 墙钟短」= B，
    # 不是"墙钟最短的 fast"；关键判据是 fallback/regret 显式（不假装最优）。
    ('''_no = MF.select_optimal_mode("", {"max_wall": 500})
ck("B6 显式约束不可行 => fallback=True / regret=None（不假装最优）",
   _no["fallback"] is True and _no["optimality"]["regret"] is None
   and _no["mode"] == "fast", _no["mode"])''',
     '''_no = MF.select_optimal_mode("", {"max_wall": 500})
ck("B6 显式约束不可行 => fallback=True / regret=None（不假装最优；"
   "退路=质量下限优先再比墙钟）",
   _no["fallback"] is True and _no["optimality"]["regret"] is None
   and _no["mode"] in ("B", "serial"), (_no["mode"], _no["reason"]))'''),
    # C7：让位要发生在「推断下限挡住可行集」的题上；事实题的 0.90 下限本来就容得下
    #     fast(0.93)，不需要让位 —— 改用推理题（推断下限 0.95）验证墙钟上限让位。
    ('''_pw = MF.plan_for_input(FACT_Q, {"max_wall": 900})
ck("C7 显式墙钟上限：推断下限让位 -> fast（记录 relaxed）",
   _pw["mode"] == "fast"
   and "min_quality(inferred)" in (_pw["optimality"]["relaxed"] or []), _pw["mode"])''',
     '''_pw0 = MF.plan_for_input(FACT_Q, {"max_wall": 900})
ck("C7a 事实题 + 墙钟上限：fast 本来就在推断下限 0.90 之上（无需让位）",
   _pw0["mode"] == "fast" and not (_pw0["optimality"]["relaxed"] or []),
   (_pw0["mode"], _pw0["optimality"].get("relaxed")))
_pw = MF.plan_for_input(REASON_Q, {"max_wall": 900})
ck("C7b 推理题 + 显式墙钟上限：推断下限 0.95 让位 -> fast（relaxed 可见）",
   _pw["mode"] == "fast"
   and "min_quality(inferred)" in (_pw["optimality"]["relaxed"] or []),
   (_pw["mode"], _pw["optimality"].get("relaxed")))'''),
    # F3：引擎接线口径 = plan_for_input + 用计划里的每模式配置落 args
    ('''ck("F3 引擎调用 plan_for_input / apply_mode_opts",
   "plan_for_input(" in _esrc and "apply_mode_opts(" in _esrc)''',
     '''ck("F3 引擎调用 plan_for_input 并用计划里的专属配置落参",
   "plan_for_input(" in _esrc and '_mc.get("parallel")' in _esrc
   and '_mc.get("thinking")' in _esrc and '_mc.get("rounds_hint")' in _esrc)'''),
]
for a, b in REP:
    n = s.count(a)
    assert n == 1, "锚点命中 %d 次: %r" % (n, a[:60])
    s = s.replace(a, b)
T.write_text(s, encoding="utf-8")
print("OK test fixes")
