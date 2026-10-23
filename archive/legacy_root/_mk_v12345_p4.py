# -*- coding: utf-8 -*-
"""v1.23.45 · P-4：**输出内**逐字复读率读数（补集合式 n-gram 信号的结构盲区）。

依据：Reflective Budget Governor（Zenodo 22844856）实测「集合式 trigram 信号对
**输出内逐字复读**结构盲」——两次灾难性退化（~50 段逐字重复）都没被它发现。
故单列一条**输出内**读数：n-gram 中重复出现的占比（0=全新鲜，1=全复读）。
"""
import ast
from pathlib import Path

TGT = Path("元DGTF-V1.23.45.py")

FN = '''

_OUTREP_N = 3          # [P-4] 输出内复读：n-gram 的 n
_OUTREP_ALERT = 0.3    # [P-4] 复读率 >= 它 ⇒ 记 repeat（告警级）


def output_repetition(text: str, n: int = _OUTREP_N):
    """[P-4] **输出内**逐字复读率 = 重复出现的 n-gram 占比（0=全新鲜，1=全复读）。

    ★ 为什么要单独一条：集合式 n-gram / trigram 信号对「**同一输出内部**的逐字
      复读」**结构盲**（Reflective Budget Governor 实测：两次灾难性退化——约 50 段
      逐字重复——都没被它发现）。本条只看**本段输出内部**的重合。
    ★ 返回 None = 文本太短（算不出）⇒ **不表态**，不假装 0。
    """
    _t = "".join(str(text or "").split())
    if len(_t) < int(n) * 4:
        return None
    _g = [_t[i:i + int(n)] for i in range(len(_t) - int(n) + 1)]
    if not _g:
        return None
    return round(1.0 - len(set(_g)) / float(len(_g)), 4)

'''

WIRE_ANCHOR = '''                except Exception:
                    pass
                for _ln in (view.collision or "").splitlines():
                    self.vp("   🔥 │ " + _ln)'''
WIRE_NEW = '''                except Exception:
                    pass
                # ★ [P-4] 输出内**逐字复读率**（补集合式信号的结构盲区）。
                try:
                    _orv = output_repetition(view.collision)
                    if _orv is not None:
                        _quant_note(view, "output_repetition", {
                            "value": _orv, "n": _OUTREP_N,
                            "verdict": ("repeat" if _orv >= _OUTREP_ALERT
                                        else "ok")})
                        if _orv >= _OUTREP_ALERT:
                            self.vp("   ⚑ ing 输出内复读率 %.2f（>=%.2f ⇒ 段间/"
                                    "段内逐字重复，集合式信号看不见）"
                                    % (_orv, _OUTREP_ALERT))
                except Exception:
                    pass
                for _ln in (view.collision or "").splitlines():
                    self.vp("   🔥 │ " + _ln)'''


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    ast.parse(s2)              # ★ 先校验后写
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\n") == out.count(b"\r\n")
    path.write_bytes(out)
    return out.decode("utf-8")


def apply(s):
    # ① 新函数：插在 `def _quant_note(` 之前（同区）
    a = "def _quant_note(view, key: str, val) -> None:"
    assert s.count(a) == 1, "函数锚点 %d" % s.count(a)
    s = s.replace(a, FN.strip("\n") + "\n\n\n" + a, 1)
    # ② 接线
    assert s.count(WIRE_ANCHOR) == 1, "接线锚点 %d" % s.count(WIRE_ANCHOR)
    s = s.replace(WIRE_ANCHOR, WIRE_NEW)
    # ③ 两个标签表（读数出口）
    rl = '    ("ing_density", "密度"),\n'
    assert s.count(rl) == 1, "_READING_LABELS 锚点 %d" % s.count(rl)
    s = s.replace(rl, rl + '    ("output_repetition", "内复读"),\n', 1)
    ql = '    "ing_density": "ing 语义密度",\n'
    assert s.count(ql) == 1, "_QUANT_LABELS 锚点 %d" % s.count(ql)
    s = s.replace(ql, ql + '    "output_repetition": "输出内复读率",\n', 1)
    return s


if __name__ == "__main__":
    t = _rw(TGT, apply)
    for tok, want in (("def output_repetition(text: str", 1),
                      ("_OUTREP_N = 3", 1),
                      ('_quant_note(view, "output_repetition"', 1),
                      ('("output_repetition", "内复读")', 1),
                      ('"output_repetition": "输出内复读率"', 1)):
        assert t.count(tok) == want, "自检 %r = %d" % (tok, t.count(tok))
    print("[ok] P-4 补丁已落 | 纯 CRLF | AST OK")
