# -*- coding: utf-8 -*-
"""v1.23.58 → v1.23.59：修行层增益**换信号**（Heaps 边际 → 相对新增率）。

为什么要换（实测，`_ab_v1255/对表.md` §九）：
  `stop.gain_floor` 依赖 `refinement_gain`，而修行层的增益取 `excavate`
  （Heaps 边际 ΔV/Δn）。那个读数有两道门：
    · `_lg_aspect_margin` 要 `len(hist) >= 3` 才开算；
    · 退化增长（early≤1e-12 而 late>1e-12）还**返回 None**。
  实测 4 圈里 3 圈是 None ⇒ `refinement_gain` 恒 None ⇒ 早停判据**永远不触发**。
  这不是阈值问题，是**信号太稀疏**。

换法（**只改修行层那一路**，其余三层一个字不动）：
  增益 = **相对新增率** = max(0, 本圈 n_aspects − 上圈 n_aspects) / 上圈 n_aspects
  · 只要**有两圈且上圈 n>0** 就有值 ⇒ 不再稀疏；
  · 语义仍是「新增趋零」（新增长不动 ⇒ 增益→0 ⇒ 迭代饱和）；
  · 0..1 有界（截断），与 `gain_floor` 同量纲；
  · 老产物没有 `n_aspects` ⇒ **退回原 Heaps 路径**（逐字不变）。

保留不动：
  · `excavate` 读数本身（四层目标语义的公开读数，红线：目标定义不改）；
  · 其余三层的增益方向（settle/fuse/crystallize 仍是「本圈 − 上圈」）；
  · `gain_floor <= 0`（默认）⇒ 判据直接返回，**零行为差**。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.58.py"
DST = HERE / "元DGTF-V1.23.59.py"

raw = SRC.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")


def rep(old, new, what, expect=1):
    global s
    c = s.count(old)
    assert c == expect, "%s：命中 %d 次（要求 %d）" % (what, c, expect)
    s = s.replace(old, new)
    print("  [OK] %s" % what)


# ── 1) 增益函数：修行层改走相对新增率 ─────────────────────────────
OLD = '''    _e = str(entry or "")
    _k = _LG_KEYS.get(_e)
    if not _k:
        return None
    _cur = _lg_num((goal or {}).get(_k))
    if _cur is None:
        return None
    _tr = list(prev or [])
    _pv = _lg_num((_tr[-1] or {}).get(_k)) if _tr else None
    if _pv is None:
        return None
    _d = (_pv - _cur) if _e == "0" else (_cur - _pv)
    return round(max(0.0, min(1.0, _d)), 4)
'''
NEW = '''    _e = str(entry or "")
    _k = _LG_KEYS.get(_e)
    if not _k:
        return None
    _tr = list(prev or [])
    # ★ [P-2 换信号] 修行层优先用**相对新增率**（Δ n_aspects / 上圈 n）：
    #   Heaps 边际（`excavate`）要 ≥3 圈历史、且对退化增长返回 None ⇒ 实测 4 圈
    #   里 3 圈是 None ⇒ 增益恒 None ⇒ 早停判据永远不触发（通道稀疏，不是阈值严）。
    #   相对新增率只要"有两圈 + 上圈 n>0"就有值；语义仍是「新增趋零」；
    #   0..1 有界，与 `gain_floor` 同量纲。老产物没 `n_aspects` ⇒ 退回下面那条。
    if _e == "0":
        _cn = _lg_num((goal or {}).get("n_aspects"))
        _pn = _lg_num((_tr[-1] or {}).get("n_aspects")) if _tr else None
        if _cn is not None and _pn is not None and _pn > 0:
            _r = max(0.0, float(_cn) - float(_pn)) / float(_pn)
            return round(max(0.0, min(1.0, _r)), 4)
    _cur = _lg_num((goal or {}).get(_k))
    if _cur is None:
        return None
    _pv = _lg_num((_tr[-1] or {}).get(_k)) if _tr else None
    if _pv is None:
        return None
    _d = (_pv - _cur) if _e == "0" else (_cur - _pv)
    return round(max(0.0, min(1.0, _d)), 4)
'''
rep(OLD, NEW, "refinement_gain：修行层走相对新增率")

# ── 2) docstring 说明换信号 ───────────────────────────────────────
rep('''      · `excavate`（修行，越小越接近挖尽）⇒ 增益 = 上一圈 − 本圈；''',
    '''      · `excavate`（修行，越小越接近挖尽）⇒ 增益 = 上一圈 − 本圈；
        ★ **实际取的是相对新增率**（Δ n_aspects / 上圈 n）：Heaps 边际读数稀疏
          （要 ≥3 圈历史、退化增长还给 None），拿它当早停信号等于让判据失效。
          只有老产物（没有 `n_aspects`）才退回 Heaps 那条算路。''',
    "docstring 说明换信号的缘由")

# ── 3) 停因文案：说清是「相对新增率」 ─────────────────────────────
rep('''    return True, ("本层再跑增益趋零（单标量 refinement_gain < %.3f 连续 %d 圈，"
                  "迭代已饱和）" % (_gf, int(_LG_STOP_FLAT_N)))''',
    '''    return True, ("本层再跑增益趋零（单标量 refinement_gain < %.3f 连续 %d 圈，"
                  "迭代已饱和）" % (_gf, int(_LG_STOP_FLAT_N)))''',
    "停因文案占位（不改）", expect=1)

# ── 4) 版本号 ────────────────────────────────────────────────────
rep("元 DGTF · v1.23.58\n", "元 DGTF · v1.23.59\n", "docstring 标题")
rep('__version__ = "1.23.58"\n', '__version__ = "1.23.59"\n', "__version__")

ast.parse(s)
assert s.count('_r = max(0.0, float(_cn) - float(_pn)) / float(_pn)') == 1
assert s.count('if _e == "0":') >= 1
# 其余三层的方向断言没被动
assert '_d = (_pv - _cur) if _e == "0" else (_cur - _pv)' in s
print("  [OK] 结构性自检：修行层新信号在、其余三层方向未动、旧路径仍可退回")

n1 = s.count("\n")
print("  [OK] 行数 %d → %d（+%d）" % (n0, n1, n1 - n0))

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
DST.write_bytes(out)
print("\n写出 %s（%d 字节 / %d 行 / 纯 CRLF）"
      % (DST.name, len(out), out.count(b"\r\n")))
