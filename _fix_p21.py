# -*- coding: utf-8 -*-
"""[v1.23.2] P2.1.b/c 判据随实现更新（区域判据）。

本版把 triage 的**组装逻辑**从 `_anchor_crosscheck` 抽成纯函数
`_triage_suggestions`（为了可构造性验证）。于是
「crosscheck 改调 `_is_triage_candidate` / 先过 `_is_never_downgrade`」
这两条**区域判据**的锚区里不再有那两个调用 —— 判红。

★ 这不是回归，是**判据过时**。改法：判据覆盖「`_anchor_crosscheck` ∪
  `_triage_suggestions`」，并**额外钉住**两者之间的调用关系
  （`_anchor_crosscheck` 里必须出现 `_triage_suggestions(`）——
  比原来更强：既管「判据存在」，也管「它真的被那条路径用到」。
"""
import ast
from pathlib import Path

P = Path("_v122_verify.py")
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

O1 = '''    _i0 = txt.find("def _anchor_crosscheck")'''
N1 = '''    # [v1.23.2] 组装逻辑搬到纯函数 `_triage_suggestions` 之后，「区域」要扩成
    #   两处之和，并**额外钉住调用关系**（否则「搬走了」与「删掉了」看起来一样）。
    def _fn_src(_t, _name):
        for _n in ast.walk(ast.parse(_t)):
            if isinstance(_n, ast.FunctionDef) and _n.name == _name:
                return "\\n".join(_t.split("\\n")[_n.lineno - 1:_n.end_lineno])
        return ""

    _i0 = txt.find("def _anchor_crosscheck")'''
assert s.count(O1) == 1, "区域起点锚命中 %d 次" % s.count(O1)
s = s.replace(O1, N1)

O2 = '''    check("P2.1.b", "_is_triage_candidate(" in xc,
          "crosscheck 改调 _is_triage_candidate")
    check("P2.1.c", "_is_never_downgrade(" in xc,
          "crosscheck 先过 _is_never_downgrade")'''
N2 = '''    _tri_src = _fn_src(txt, "_triage_suggestions")
    _xc_all = xc + "\\n" + _tri_src
    check("P2.1.b ★ 判据存在 + 真的被 crosscheck 用到（判据区域 = "
          "_anchor_crosscheck ∪ _triage_suggestions）",
          "_is_triage_candidate(" in _xc_all
          and "_triage_suggestions(" in xc,
          "调用关系缺失：_anchor_crosscheck 未调 _triage_suggestions")
    check("P2.1.c ★ 同上（先过 _is_never_downgrade）",
          "_is_never_downgrade(" in _xc_all,
          "_is_never_downgrade( 不在判据区域内")'''
assert s.count(O2) == 1, "P2.1.b/c 锚命中 %d 次" % s.count(O2)
s = s.replace(O2, N2)

ast.parse(s)
P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("P2.1.b/c 已改到新语义（区域 = 两处之和 + 钉调用关系）")
