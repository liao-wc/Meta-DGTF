#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.30 真实入口验证探针：层职责守卫（LDG）。

覆盖：
  T1 问项抽取分类（core / background / followup）—— 正负样本
  T2 duty 三读数（C/R/S）—— 全相关 ⇒ 高；全无关 ⇒ 低（负对照）
  T3 S 的调和平均性质（C 高 R 低必须被拉下来）
  T4 真实入口 `_layer_duty_now`：把读数写进 `view.duty` / `duty_trace`
  T5 **署名纪律**：走真实 `_finalize_layer_common`，职责未尽 ⇒ 不许只写
     「自然安住」，必须改署并点名；达标 ⇒ 不许乱改（负对照）
  T6 补救注入：缺失 core 问项进 `_duty_carry`
  T7 `distance_to_question` 缺省不印（None）
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.30.py"

spec = importlib.util.spec_from_file_location("dgtf_v12330", SRC)
m = importlib.util.module_from_spec(spec)
sys.modules["dgtf_v12330"] = m
spec.loader.exec_module(m)

R = []
Q = "如何利用AI来帮助人类实现财富自由甚至文明升级？"


def ok(name, cond, note=""):
    R.append((name, bool(cond), note))
    print(("✓" if cond else "✗"), name, note)


# ── T1 问项抽取与分类 ─────────────────────────────────────
asp = m.question_aspects(Q)
kinds = {a["text"]: a["kind"] for a in asp}
ok("T1 抽出问项非空", len(asp) >= 1, str([(a["text"], a["kind"]) for a in asp]))
ok("T1 含 followup 档（甚至 引导）", "followup" in kinds.values(),
   str(kinds))
ok("T1 followup 权重最低",
   all(a["weight"] == 0.10 for a in asp if a["kind"] == "followup"))

# ── T2 三读数 ─────────────────────────────────────────────
_rel = ("利用AI帮助人类实现财富自由，并推动文明升级。"
        "AI 的作用体现在生产率提升与分配制度设计上。")
_irr = ("候选属性0◈阴展开×位置both；线头编号 th#3 与 &4 未对齐；"
        "悬置决定 stable 后不可撤销；探针覆盖不足。")
d_hi = m.duty_components(asp, _rel, objective_words=("利用", "财富"))
d_lo = m.duty_components(asp, _irr, objective_words=("利用", "财富"))
ok("T2 相关文本 ⟹ C 高", d_hi["C"] >= 0.5, f"C={d_hi['C']}")
ok("T2 无关文本 ⟹ C 低（负对照）", d_lo["C"] < d_hi["C"],
   f"C_lo={d_lo['C']} < C_hi={d_hi['C']}")
ok("T2 无关文本 R 低 ⟹ S 被拉下来", d_lo["S"] < d_hi["S"],
   f"S_lo={d_lo['S']} < S_hi={d_hi['S']}")
ok("T2 无关文本点名缺失 core", len(d_lo["missing_core"]) >= 1,
   str(d_lo["missing_core"][:3]))

# ── T3 调和平均：C 高 R 低必须塌 ─────────────────────────
d_mix = m.duty_components(asp, _rel + "。" + _irr * 3,
                          objective_words=("利用", "财富"))
ok("T3 调和平均惩罚偏科（S < min(C,R) 之上但不取算术平均）",
   d_mix["S"] <= (d_mix["C"] + d_mix["R"]) / 2 + 1e-9,
   f"C={d_mix['C']} R={d_mix['R']} S={d_mix['S']}")

# ── T4/T5/T6 真实入口 ────────────────────────────────────
try:
    cfg = dict(m.DEFAULT_CONFIG)
    eng = m.MetaDGTF(cfg)
    eng._question = Q
    v = m.View(entry="1")
    v.collision = _irr * 4            # 交付面全无关 ⇒ 应判职责未尽
    d = eng._layer_duty_now("1", v)
    ok("T4 真实入口写回 view.duty", v.duty and v.duty.get("S") == d["S"],
       f"S={d['S']}")
    ok("T4 逐圈 trace 记一笔", len(v.duty_trace) == 1, str(v.duty_trace))
    ok("T4 无关交付面 ⇒ short=True", bool(d.get("short")) is True,
       f"S={d['S']} floor={d.get('floor')}")
    _line = m.duty_short_line(d)
    ok("T4 读数行含 S/C/R 与缺项", "职责 S=" in _line and "缺核心" in _line,
       _line[:60])

    # 署名纪律（真实收尾）
    v.stop_reason = "悬置决定稳定，自然安住，螺旋停止"
    st = {"all_candidates": list(v.candidates), "all_amps": list(v.amps),
          "all_threads": list(v.threads), "all_rehashed": [],
          "all_expanded_descs": [], "all_dec_products": [],
          "all_und_products": [], "all_view_errors": [],
          "round_log": [], "roles_hist": [], "deferred_notes": [],
          "total_rounds": 4, "r": 1, "rounds_n": 4,
          "sp": dict(cfg.get("spiral") or {})}
    eng._finalize_layer_common("1", v, st)
    ok("T5 职责未尽 ⇒ 独立判定行（不动 stop_reason）",
       "职责未尽" in (v.duty_verdict or ""), (v.duty_verdict or "")[:60])
    ok("T5 停止理由保持原样（红线：停止与清算分开）",
       (v.stop_reason or "") == "悬置决定稳定，自然安住，螺旋停止",
       (v.stop_reason or "")[:50])
    ok("T5 留痕 duty_short flag", "duty_short" in (v.quality_flags or []),
       str(v.quality_flags))
    ok("T5 判定行与停止理由**分开存**", bool(v.duty_verdict) and bool(v.stop_reason))
    ok("T6 缺失 core 注入 _duty_carry",
       len(getattr(eng, "_duty_carry", []) or []) >= 1,
       str(getattr(eng, "_duty_carry", [])[:3]))

    # 负对照：交付面全相关 ⇒ 不许乱改署名
    eng2 = m.MetaDGTF(cfg)
    eng2._question = Q
    v2 = m.View(entry="1")
    v2.collision = _rel * 8
    st2 = dict(st, all_candidates=list(v2.candidates))
    v2.stop_reason = "悬置决定稳定，自然安住，螺旋停止"
    eng2._finalize_layer_common("1", v2, st2)
    ok("T5 负对照：职责达标 ⇒ 不写判定行",
       not (v2.duty_verdict or ""), (v2.duty_verdict or "")[:40])
    ok("T6 负对照：达标 ⇒ 不注入 carry",
       len(getattr(eng2, "_duty_carry", []) or []) == 0,
       str(getattr(eng2, "_duty_carry", [])[:2]))
except Exception as ex:
    import traceback
    traceback.print_exc()
    ok("T4~T6 真实入口", False, repr(ex))

# ── T7 distance 缺省不印 ─────────────────────────────────
try:
    v3 = m.View(entry="0")
    ok("T7 distance_to_question 缺省为 None", v3.distance_to_question is None,
       repr(v3.distance_to_question))
    _r = m.render_view_lines(v3) if hasattr(m, "render_view_lines") else ""
    ok("T7 缺省不进渲染文本", "distance_to_question" not in (_r or ""),
       (_r or "")[:40])
except Exception as ex:
    ok("T7 distance 缺省", False, repr(ex))

bad = [r for r in R if not r[1]]
print("\n=== 探针汇总：%d ✓ / %d ✗ ===" % (len(R) - len(bad), len(bad)))
sys.exit(1 if bad else 0)
