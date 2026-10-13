#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.33 补丁 P5：把「层读数」写进**产物**（此前只进了 verbose 转储）。

真跑抓出的真缺口：`【主因】/【发散三态】/【anytime 下界】/【早期预警】` 挂在
`dump_view_fields()`（**控制台转储**）里 ⇒ **产物 md 里看不到**。
用户读产物时，这些读数等于不存在。

修法：在 `save_result` 的头部读数区（与「层职责（LDG）」同处）新增一个
**「层读数」块**，按层输出：主因 / 发散三态 + 回滚指针 / anytime 下界 / 早期预警。
"""
from pathlib import Path
import ast

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"
BSNL = chr(92) + "n"


def _load(p=SRC):
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n") and b.count(b"\r\r\n") == 0
    return b.decode("utf-8").replace("\r\n", "\n")


def _save(s, p=SRC):
    assert "\r\r\n" not in s
    p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))


NEW_BLOCK = '''        # ★ [层读数进产物] 此前【主因】/【发散三态】/【anytime 下界】/【早期预警】
        #   只写在 `dump_view_fields()`（**控制台转储**）里 ⇒ **产物 md 看不到**，
        #   读者视角等于不存在（真跑抓出的真缺口）。这里按层补进产物。
        try:
            _lay_rows = []
            for _e in ("0", "1", "both", "all"):
                _vv = (result.get("views") or {}).get(_e) or {}
                if not _vv:
                    continue
                _bits = []
                if _vv.get("stop_primary"):
                    _bits.append("主因=%s" % str(_vv["stop_primary"])[:46])
                _dvv = _vv.get("divergence") or {}
                if _dvv:
                    _bits.append("三态=%s" % _dvv.get("state"))
                    if _vv.get("best_round"):
                        _bits.append("历史最佳=第%s圈" % _vv["best_round"])
                _atv = _vv.get("anytime") or {}
                if _atv.get("lower") is not None:
                    _bits.append("anytime下界=%.3f" % float(_atv["lower"]))
                _cvv = (_vv.get("csd") or {}).get("new_amps") or {}
                if _cvv:
                    _bits.append("早预警=%s"
                                 % ("有前兆" if _cvv.get("hint") else "无前兆"))
                if _bits:
                    _lay_rows.append("  - %s层：%s"
                                     % (_LAYER_LABEL.get(_e, _e),
                                        " ｜ ".join(_bits)))
            if _lay_rows:
                f.write("**层读数（每层）**：@@NL@@")
                for _lr in _lay_rows:
                    f.write(_lr + "@@NL@@")
                f.write("      ★ 「三态」= 收敛/平稳/停滞/发散；「历史最佳」是**回滚指针**"
                        "（被回滚的圈不删）；anytime 下界对**任意停时**有效。@@NL@@")
                f.write("@@NL@@")
        except Exception as _el:
            f.write("**层读数（每层）**：取层读数失败（%s）@@NL@@@@NL@@"
                    % type(_el).__name__)

'''


def main():
    s = _load()
    anchor = '''        # ★ [compact 内部面预算] 率失真读数（不自动压缩，避免 ACE 式掉分）。'''
    assert s.count(anchor) == 1, s.count(anchor)
    s = s.replace(anchor, NEW_BLOCK.replace("@@NL@@", BSNL) + anchor, 1)
    ast.parse(s)
    _save(s)
    s2 = SRC.read_bytes().decode("utf-8")
    assert "**层读数（每层）**" in s2
    assert s2.count("\r\r\n") == 0
    print("OK P5：层读数已进产物（主因/三态/指针/anytime/早预警）")


if __name__ == "__main__":
    main()
