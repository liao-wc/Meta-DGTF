# -*- coding: utf-8 -*-
"""v1.23.33 · 第三轮 patch-4：`autotune_run` 产出三阶段决策书。"""
from pathlib import Path

SRC = Path("元DGTF-V1.23.33.py")


def load_crlf(p):
    t = p.read_bytes().decode("utf-8")
    assert t.count("\n") == t.count("\r\n"), "非纯 CRLF"
    return t.replace("\r\n", "\n")


def save_crlf(p, t):
    assert "\r" not in t.replace("\r\n", "")
    out = t.replace("\r\n", "\n").replace("\n", "\r\n")
    assert out.count("\r\r\n") == 0
    p.write_bytes(out.encode("utf-8"))
    chk = p.read_bytes().decode("utf-8")
    assert chk.count("\n") == chk.count("\r\n")


def sub1(t, a, r):
    n = t.count(a)
    assert n == 1, "锚点命中 %d 次（必须 1）：%r" % (n, a[:90])
    return t.replace(a, r, 1)


A = '''        rec = {"ok": False, "why": "autotune_recommend 异常：%r" % (e,)}
    rec["n_read"] = len(eps)
'''
R = '''        rec = {"ok": False, "why": "autotune_recommend 异常：%r" % (e,)}
    rec["n_read"] = len(eps)
    # ★ [三阶段决策书] 前期选择 / 中期调整 / 后期学习 —— 一次跑全出，
    #   随建议一起落盘（「结论」必须留痕，否则只算内部状态）。
    #   ★ 段间**互不覆盖**：`rec` 仍是 `autotune_recommend` 的原样输出
    #     （下游 `autotune_apply_to_cfg` 读的就是它），三段挂在新键上。
    try:
        rec["decide"] = autotune_decide(
            eps, quality_tau=float(at.get("quality_tau", 0.05)),
            min_n=int(at.get("min_n", 2) or 2))
    except Exception as e:
        rec["decide"] = {"error": "%r" % (e,)}
'''

t = load_crlf(SRC)
t = sub1(t, A, R)
save_crlf(SRC, t)
print("OK: patch-4 autotune_run 出三阶段决策书")
