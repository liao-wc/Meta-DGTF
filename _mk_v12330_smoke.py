#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.30：smoke_test 接入（SRC 指向 + LDG 判据）。

把探针里已验证的 7 组判据收进 smoke（源码级 + 真实入口级），
并对其余判据的影响做最小改动。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
p = HERE / "smoke_test.py"
b = p.read_bytes()
is_crlf = b.count(b"\r\n") > 0 and b.count(b"\r\n") == b.count(b"\n")
s = b.decode("utf-8").replace("\r\n", "\n")


def rep(old, new, what, expect=1):
    global s
    n = s.count(old)
    assert n == expect, f"{what}: {n}"
    s = s.replace(old, new)


# 1) SRC
rep('SRC = HERE / "元DGTF-V1.23.29.py"',
    'SRC = HERE / "元DGTF-V1.23.30.py"', "SRC 指向")

# 2) 新判据函数
FN = '''def check_v12330_duty_guard():
    """[v1.23.30] 层职责守卫（LDG）：在**停止/收敛处**判「这层替问题干了什么」。

    判据分三层（源码级 / 纯函数级 / 真实入口级）：
      · 源码级：问项抽取、三读数、命中口径、停止判据、署名纪律、缺省修真
      · 纯函数级：相关 ⇒ C/S 高；无关 ⇒ C/S 低（负对照）；调和平均惩罚偏科
      · 真实入口级：走 `_finalize_layer_common`，职责未尽必须改署名 + 留痕；
        达标**不许**乱改（负对照）；缺失 core 注入 carry
    判别力由 `_mut_v12330.py` 背书（M1~M9）。
    """
    src = SRC.read_bytes().decode("utf-8")
    bad = []

    # ── 源码级 ──
    for _need, _what in (
            ("def question_aspects(question: str):", "问项抽取"),
            ("def duty_components(aspects, deliver_text", "三读数"),
            ("def duty_of_layer(entry, question, deliver_text", "层读数薄壳"),
            ("def duty_short_line(d:", "读数行"),
            ("_DUTY_KIND_W = {", "类别权重"),
            ("职责增益收敛", "新停止判据"),
            ("职责未尽：", "署名纪律"),
            ("_duty_carry", "补救注入")):
        if _need not in src:
            bad.append("[源码] %s 缺失（%r）" % (_what, _need))
    if '"distance_to_question": (None if d2q is None' not in src:
        bad.append("[源码] distance_to_question 入口缺省未修真")
    if src.count("distance_to_question is not None") != 2:
        bad.append("[源码] distance 渲染条件未改成「有值才印」")

    # ── 纯函数级 ──
    q = "如何利用AI来帮助人类实现财富自由甚至文明升级？"
    asp = mod.question_aspects(q)
    if not asp:
        bad.append("[纯函数] 问项抽取为空")
    else:
        if "followup" not in {a.get("kind") for a in asp}:
            bad.append("[纯函数] 「甚至…」未被归为 followup（%r）" % (asp,))
        if any(a.get("kind") == "followup" and a.get("weight") != 0.10
               for a in asp):
            bad.append("[纯函数] followup 权重不是最低档")
    _rel = ("利用AI帮助人类实现财富自由，并推动文明升级。"
            "AI 的作用体现在生产率提升与分配制度设计上。")
    _irr = ("候选属性0◈阴展开×位置both；线头编号 th#3 与 &4 未对齐；"
            "悬置决定 stable 后不可撤销；探针覆盖不足。")
    d_hi = mod.duty_components(asp, _rel, objective_words=("利用", "财富"))
    d_lo = mod.duty_components(asp, _irr, objective_words=("利用", "财富"))
    if d_hi["C"] < 0.5:
        bad.append("[纯函数] 相关交付面覆盖应高（实为 %r）" % d_hi["C"])
    if not (d_lo["C"] < d_hi["C"] and d_lo["S"] < d_hi["S"]):
        bad.append("[纯函数] 无关交付面未被拉低（C %r→%r / S %r→%r）"
                   % (d_hi["C"], d_lo["C"], d_hi["S"], d_lo["S"]))
    _mix = mod.duty_components(asp, _rel + "。" + _irr * 3,
                               objective_words=("利用", "财富"))
    if _mix["S"] > (_mix["C"] + _mix["R"]) / 2 + 1e-9:
        bad.append("[纯函数] 调和平均失效（S %r > 算术平均）" % _mix["S"])
    if not d_lo["missing_core"]:
        bad.append("[纯函数] 无关交付面未点名缺失 core")

    # ── 真实入口级 ──
    try:
        cfg = dict(mod.DEFAULT_CONFIG)
        eng = mod.MetaDGTF(cfg)
        eng._question = q
        v = mod.View(entry="1")
        v.collision = _irr * 4
        d = eng._layer_duty_now("1", v)
        if not v.duty or v.duty.get("S") != d["S"]:
            bad.append("[入口] duty 未写回 view")
        if len(v.duty_trace) != 1:
            bad.append("[入口] duty_trace 未记账（%r）" % v.duty_trace)
        if not d.get("short"):
            bad.append("[入口] 无关交付面未判 short")
        v.stop_reason = "悬置决定稳定，自然安住，螺旋停止"
        st = {"all_candidates": [], "all_amps": [], "all_threads": [],
              "all_rehashed": [], "all_expanded_descs": [],
              "all_dec_products": [], "all_und_products": [],
              "all_view_errors": [], "round_log": [], "roles_hist": [],
              "deferred_notes": [], "total_rounds": 4, "r": 1,
              "rounds_n": 4, "sp": dict(cfg.get("spiral") or {})}
        eng._finalize_layer_common("1", v, st)
        if "职责未尽" not in (v.stop_reason or ""):
            bad.append("[入口] 职责未尽未改署名")
        if "自然安住" not in (v.stop_reason or ""):
            bad.append("[入口] 原署名被删（只该追加，不许删）")
        if "duty_short" not in (v.quality_flags or []):
            bad.append("[入口] duty_short 未留痕（被收尾清洗吞了？）")
        if not (getattr(eng, "_duty_carry", None) or []):
            bad.append("[入口] 缺失 core 未注入 carry")
        # 负对照：达标不许乱改
        eng2 = mod.MetaDGTF(cfg)
        eng2._question = q
        v2 = mod.View(entry="1")
        v2.collision = _rel * 8
        v2.stop_reason = "悬置决定稳定，自然安住，螺旋停止"
        eng2._finalize_layer_common("1", v2, dict(st))
        if "职责未尽" in (v2.stop_reason or ""):
            bad.append("[入口·负] 达标却仍改署名")
        if (getattr(eng2, "_duty_carry", None) or []):
            bad.append("[入口·负] 达标却仍注入 carry")
    except Exception as e:
        import traceback
        traceback.print_exc()
        bad.append("[入口] 异常：%r" % (e,))

    # ── 缺省修真 ──
    if mod.View(entry="0").distance_to_question is not None:
        bad.append("[缺省] distance_to_question 缺省应为 None")

    if bad:
        for x in bad:
            print("  ✗", x)
        return False
    print("  ✓ v1.23.30 层职责守卫（源码/纯函数/真实入口 三层判据）全过")
    return True


'''
rep("def check_v12329_convergence():", FN + "def check_v12329_convergence():",
    "插入 LDG 判据函数")

# 3) 注册到主链
rep('''    if not check_v12329_convergence():
        return 1
''', '''    if not check_v12329_convergence():
        return 1
    if not check_v12330_duty_guard():
        return 1
''', "注册 LDG 判据")

out = s.replace("\n", "\r\n") if is_crlf else s
p.write_bytes(out.encode("utf-8"))
print("smoke_test.py 接入完成（CRLF=%s）" % is_crlf)
