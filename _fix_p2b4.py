# -*- coding: utf-8 -*-
"""[v1.23.2] P2b.4.a/b/a2/a3 判据随实现更新（区域判据）。

与 P2.1.b/c 同因：triage 的**组装逻辑**已抽成纯函数 `_triage_suggestions`
（为了可构造性验证），于是「crosscheck 调 `_hit_by_answers` / `_hit_by_claim`
/ 读 anchors 的 `answers` / tier 门在双路径之内」这四条**区域判据**的锚区里
不再有那些字面串 —— 判红。

★ 这不是回归，是判据过时。改法：区域 = `_anchor_crosscheck` ∪
  `_triage_suggestions`，并**额外钉住** crosscheck 真的调了它（比原来更强）。
"""
import ast
from pathlib import Path

P = Path("_v122_verify.py")
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

OLD = '''    _k0 = txt.find("def _anchor_crosscheck")
    _k1 = txt.find(NL + "    def ", _k0 + 10) if _k0 >= 0 else -1
    _xc = txt[_k0:_k1] if _k0 >= 0 and _k1 > _k0 else txt[_k0:]
    check("P2b.4.a", "_hit_by_answers(str(" in _xc, "crosscheck 调 _hit_by_answers")
    check("P2b.4.b", "_hit_by_claim(str(" in _xc, "crosscheck 调 _hit_by_claim")
    check("P2b.4.a2", 'x.get("answers")' in _xc, "crosscheck 读 anchors 的 answers 字段")
    check("P2b.4.a3", "<= _floor_c" in _xc, "tier 门仍在双路径之内")'''
NEW = '''    # [v1.23.2] 组装逻辑搬到纯函数 `_triage_suggestions` ⇒ 区域要扩成两处之和，
    #   并**钉住调用关系**（否则「搬走了」与「删掉了」在判据眼里一样）。
    _k0 = txt.find("def _anchor_crosscheck")
    _k1 = txt.find(NL + "    def ", _k0 + 10) if _k0 >= 0 else -1
    _xc = txt[_k0:_k1] if _k0 >= 0 and _k1 > _k0 else txt[_k0:]
    _tsrc = ""
    for _n in ast.walk(ast.parse(txt)):
        if isinstance(_n, ast.FunctionDef) and _n.name == "_triage_suggestions":
            _tsrc = NL.join(txt.split(NL)[_n.lineno - 1:_n.end_lineno])
            break
    _xc_all = _xc + NL + _tsrc
    check("P2b.4.a ★ crosscheck 路径调 _hit_by_answers（区域 = crosscheck ∪ "
          "_triage_suggestions，且跨check 必须真的调用它）",
          "_hit_by_answers(str(" in _xc_all and "_triage_suggestions(" in _xc,
          "调用关系缺失：_anchor_crosscheck 未调 _triage_suggestions")
    check("P2b.4.b ★ 同上（_hit_by_claim）", "_hit_by_claim(str(" in _xc_all,
          "crosscheck 路径没调 _hit_by_claim")
    check("P2b.4.a2 ★ 同上（读 anchors 的 answers 字段）",
          'x.get("answers")' in _xc_all,
          "crosscheck 路径没读 anchors 的 answers 字段")
    check("P2b.4.a3 ★ tier 门仍与双路径**同一处**（同一表达式内）",
          "<= _floor" in _xc_all and "and (" in _xc_all,
          "tier 门不在双路径之内")'''
assert s.count(OLD) == 1, "P2b.4 锚点命中 %d 次" % s.count(OLD)
s = s.replace(OLD, NEW)
ast.parse(s)
P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("P2b.4.a/b/a2/a3 已改到新语义")
