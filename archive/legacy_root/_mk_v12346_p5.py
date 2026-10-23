# -*- coding: utf-8 -*-
"""v1.23.46 · P-5：职责 S 口径对称化 —— C(全文) vs R(逐句) 的**长度不对称**。

实测：真产物 duty_trace = `{S:0.0, C:0.25, R:0.0}` ⇒ S=0 是 **R=0** 拖的。
根因（诊断）：C 用 `_hit(问项, **全文**)` 计覆盖；R 用 `_hit(问项, **单句**)` 计「直接段」。
`_hit` 的 gram 覆盖率是**按问项自身长度**归一 —— 同一个问项在长文里够 0.5、在短句里不够
⇒ **问项跨句时 C 记、R 不记**；S=2CR/(C+R) 便被拖到 0。

修法（配置式，**默认关 ⇒ 逐字零行为差**）：R 的「直接命中」加**跨句窗口**
（`sg + 下一句`）—— 窗口仅在 `duty.span_tolerant=True` 时用。
"""
import ast
from pathlib import Path

TGT = Path("元DGTF-V1.23.46.py")

SIG_OLD = ('def duty_of_layer(entry, question, deliver_text, objective_words=(),\n'
           '                  corpus=None, floor=None) -> dict:')
SIG_NEW = ('def duty_of_layer(entry, question, deliver_text, objective_words=(),\n'
           '                  corpus=None, floor=None,\n'
           '                  span_tolerant: bool = False) -> dict:')

R_OLD = '''    direct = useful = useless = 0
    for sg in segs:
        # ★ 与 C 同口径（都走 `_hit`）：两处口径分叉会让「覆盖高、相关低」
        #   变成算法噪声而不是事实。
        if any(_hit(str(a.get("text", "")), sg) for a in _as):
            direct += 1
        elif any(w in sg for w in _aw):
            useful += 1
        else:
            useless += 1'''
R_NEW = '''    direct = useful = useless = 0
    # ★ [P-5] C 判**全文**、R 判**逐句** —— 但 `_hit` 的 gram 覆盖率按**问项长度**
    #   归一 ⇒ 同一问项在长文里够阈值、在短句里不够 ⇒ **问项跨句时 C 记、R 不记**
    #   ⇒ S=2CR/(C+R) 被拖到 0（真产物实测 C=0.25 而 R=0.0）。
    #   `span_tolerant=True` ⇒ R 的「直接命中」改用**跨句窗口**（本句 + 下一句）。
    #   默认 False ⇒ `_probe` 逐字等于 `sg`，R 与改前**完全相同**（零行为差）。
    _as_list = [str(a.get("text", "")) for a in _as]
    for _i, sg in enumerate(segs):
        _probe = sg
        if span_tolerant and (_i + 1) < len(segs):
            _probe = sg + segs[_i + 1]
        if any(_hit(t, _probe) for t in _as_list):
            direct += 1
        elif any(w in sg for w in _aw):
            useful += 1
        else:
            useless += 1'''

CALL_OLD = ('        d = duty_of_layer(entry, self._question, deliver,\n'
            '                          objective_words=_DUTY_OBJ_WORDS.get(entry, ()),\n'
            '                          corpus=getattr(self, "_sim_corpus", None),\n'
            '                          floor=getattr(self, "_duty_floor", _DUTY_FLOOR))')
CALL_NEW = ('        _dspan = False\n'
            '        try:\n'
            '            _dspan = bool((self.config.get("duty") or {}).get(\n'
            '                "span_tolerant", False))\n'
            '        except Exception:\n'
            '            _dspan = False\n'
            '        d = duty_of_layer(entry, self._question, deliver,\n'
            '                          objective_words=_DUTY_OBJ_WORDS.get(entry, ()),\n'
            '                          corpus=getattr(self, "_sim_corpus", None),\n'
            '                          floor=getattr(self, "_duty_floor", _DUTY_FLOOR),\n'
            '                          span_tolerant=_dspan)')


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    ast.parse(s2)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\n") == out.count(b"\r\n")
    path.write_bytes(out)
    return out.decode("utf-8")


def apply(s):
    for nm, old, new in (("签名", SIG_OLD, SIG_NEW), ("R 环", R_OLD, R_NEW),
                         ("调用点", CALL_OLD, CALL_NEW)):
        n = s.count(old)
        assert n == 1, "%s 锚点 %d" % (nm, n)
        s = s.replace(old, new)
    d = '    "duty": {\n'
    assert s.count(d) == 1, "duty 锚点 %d" % s.count(d)
    s = s.replace(d, d
                  + '        # [P-5] 职责 S 口径对称化：R 的「直接命中」用跨句窗口\n'
                    '        #   （修 C 判全文 / R 判逐句 的长度不对称）。默认 false ⇒ 逐字不变。\n'
                    '        "span_tolerant": False,\n', 1)
    return s


if __name__ == "__main__":
    t = _rw(TGT, apply)
    for tok, want in (("span_tolerant: bool = False) -> dict:", 1),
                      ("if span_tolerant and (_i + 1) < len(segs):", 1),
                      ('"span_tolerant": False,', 1),
                      ("span_tolerant=_dspan)", 1)):
        assert t.count(tok) == want, "自检 %r = %d" % (tok, t.count(tok))
    print("[ok] P-5 补丁已落 | 纯 CRLF | AST OK")
