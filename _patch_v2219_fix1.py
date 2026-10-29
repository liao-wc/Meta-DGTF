# -*- coding: utf-8 -*-
"""[V2.2.19] 动态调整降档条件放宽到「质量代理正常」；修 G1 变异体用例。"""
from pathlib import Path
import py_compile

# 1) mode_fusion：降档不再要求 qprox is None（引擎 tick 会传代理值）
F = Path("dgtf_engine/dgtf_v2/mode_fusion.py")
t = F.read_text(encoding="utf-8")
old = '''    if (wall_over or token_over) and mode != "fast" and qprox is None:'''
new = '''    # ★ 质量代理正常（或未知）时才允许降档：代理已明显偏低时降档会雪上加霜。
    if ((wall_over or token_over) and mode != "fast"
            and (qprox is None or float(qprox) >= 0.9)):'''
assert t.count(old) == 1
t = t.replace(old, new)
F.write_text(t, encoding="utf-8")
py_compile.compile(str(F), doraise=True)
print("OK dynamic downgrade gate")

# 2) 测试 G1：真实三个保留模式互为 Pareto 最优（无支配关系），
#    用合成「被支配的 fake 模式」验证支配检测有牙。
T = Path("dgtf_engine/dgtf_v2/tests_auto_mode_optimal.py")
s = T.read_text(encoding="utf-8")
old = '''# G1 变异体：返回被支配的 serial（当 B 更快更省时）
def _bad_pick(rows, prefer):
    return next(r for r in rows if r["mode"] == "serial")
_rows = MF._candidate_rows(False)
_chosen = _bad_pick(_rows, "quality")
_dom = [r["mode"] for r in _rows if MF._dominates(r, _chosen)]
ck("G1 变异体（选被支配的 serial）=> 支配检测必须判红", bool(_dom))'''
new = '''# G1 变异体：真实三模式互为 Pareto 最优（无支配）；合成一个「三面都更差」的
#    fake 模式，验证支配检测有牙 —— 若选择器返回 fake，支配判据必须红。
_rows = MF._candidate_rows(False)
ck("G1a 真实保留集里不存在支配关系（B/serial/fast 互为 Pareto 最优）",
   not any(MF._dominates(a, b) for a in _rows for b in _rows if a is not b))
_fake = dict(MF.MODES["serial"], mode="fake", quality=0.90,
             tokens=1300000, wall=2000)
_rows2 = _rows + [_fake]
_dom = [r["mode"] for r in _rows2 if r is not _fake and MF._dominates(r, _fake)]
ck("G1b 变异体（选被支配的 fake 模式）=> 支配检测必须判红", len(_dom) >= 2, _dom)'''
assert s.count(old) == 1
T.write_text(s.replace(old, new), encoding="utf-8")
print("OK G1 mutant")
