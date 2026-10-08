# -*- coding: utf-8 -*-
"""[v1.23.2] 修 P2.4.a 变异体循环：文件名/模块名不要用「标签原文」。

实测：同一个变异体文本，用**唯一模块名 + ASCII 文件名**加载 → 正确返回 ≥1 条；
用 `load_module()`（固定模块名 `dgtf_v122_mod`）+ `mut_tri_tier 门.py`
（含中文与空格）→ 返回 []，于是变异体「不判红」⇒ 判据变成假绿。

★ 教训：变异体文件用**序号**命名、模块名**唯一**，别把标签原文拼进路径。
"""
import ast
from pathlib import Path

P = Path("_v122_verify.py")
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

OLD = '''        for _nm, _o, _n, (_asp, _anc) in _MUT:
            if txt.count(_o) != 1:
                check("P2.4.a-mut." + _nm, False,
                      "变异体锚点 %d 次" % txt.count(_o))
                continue
            _mp = _mdir / ("mut_tri_%s.py" % _nm)
            _mp.write_bytes(txt.replace(_o, _n).replace(chr(10), chr(13) + chr(10))
                            .encode("utf-8"))
            _red = True
            try:
                _mm = load_module(str(_mp))
                _red = len(_mm._triage_suggestions(_asp, _anc,
                                                   {"tier_floor": 2})) >= 1
            except Exception:  # noqa: BLE001
                _red = True
            check("P2.4.a-mut ★ 变异体「破坏%s」→ 对应负对照判红" % _nm, _red,
                  "变异体下判据没判红")'''
NEW = '''        # ★ 变异体文件用**序号**命名、模块名**唯一** —— 不要把标签原文
        #   （含中文/空格）拼进路径：实测那样加载出来的模块行为不对，
        #   于是「变异体不判红」⇒ 判据假绿（本项目老坑：判据自己的环境问题
        #   会被读成被测代码没问题）。
        for _k, (_nm, _o, _n, (_asp, _anc)) in enumerate(_MUT):
            if txt.count(_o) != 1:
                check("P2.4.a-mut." + _nm, False,
                      "变异体锚点 %d 次" % txt.count(_o))
                continue
            _mp = _mdir / ("mut_tri_%d.py" % _k)
            _mp.write_bytes(txt.replace(_o, _n).replace(chr(10), chr(13) + chr(10))
                            .encode("utf-8"))
            _red = False
            _why = ""
            try:
                _spec = importlib.util.spec_from_file_location(
                    "dgtf_mut_tri_%d" % _k, str(_mp))
                _mm = importlib.util.module_from_spec(_spec)
                sys.modules["dgtf_mut_tri_%d" % _k] = _mm
                _spec.loader.exec_module(_mm)
                _out = _mm._triage_suggestions(_asp, _anc, {"tier_floor": 2})
                _red = len(_out) >= 1
                _why = repr(_out)[:90]
            except Exception as _e:  # noqa: BLE001
                _red = True
                _why = "加载/执行异常（按判红计）：" + type(_e).__name__
            check("P2.4.a-mut ★ 变异体「破坏%s」→ 对应负对照判红" % _nm, _red,
                  "变异体下判据没判红：" + _why)'''
assert s.count(OLD) == 1, "变异体循环锚点命中 %d 次" % s.count(OLD)
s = s.replace(OLD, NEW)
ast.parse(s)
P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("变异体循环已改为「序号命名 + 唯一模块名」")
