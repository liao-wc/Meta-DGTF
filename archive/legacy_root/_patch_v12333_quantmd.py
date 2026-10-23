# -*- coding: utf-8 -*-
"""v1.23.33 续（五）：把量化读数渲染进**产物 md 正文**（可读段）。

## 为什么必须修（链路断点）
`quant_readings` 原来只有**一个出口** `View.to_dict()`（→ packed JSON）。
产物 md 里它只出现在 `_render_full_appendix` 的**机械 JSON dump**（得翻 JSON）。
⇒ 引擎算了 4 个读数，人类看正文**看不到**、日志里**只有 collapsed 告警一行**。

而用户诉求原文就是「ing 的输出内容，以及 view 的输出重点等也要有相关依据」——
**读数不可见 = 有值但零信息量**（本项目第 2 类失败的形态）。

## 设计（★ 不维护「该渲染什么」的清单）
段落**遍历 `quant_readings` 的全部键**，标签走映射、未知键**降级为键名**
⇒ 以后加第五个读数会**自动出现**，不会再犯「新增字段静默漏掉」那个老事故
（`_render_full_appendix` 的注释里正记着这个教训）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.33.py"

OLD = '''        if view.carry_check:
            lines += ["", f"【自省回流核对】{view.carry_check.get('notes', '')}"]

        return "\\n".join(lines)
'''

NEW = '''        if view.carry_check:
            lines += ["", f"【自省回流核对】{view.carry_check.get('notes', '')}"]
        # ★ [第六期] 各环节量化读数 —— **正文可读段**。
        #   为什么必须有：`quant_readings` 原来只出到 packed JSON（附录里得翻），
        #   正文与日志都没有 ⇒ 「算了但看不见」= 有值但零信息量。
        #   ★ 遍历**全部键**（不维护「该渲染什么」的清单）：以后加第五个读数
        #     会自动出现，标签未知时降级为键名 —— 避免 `_render_full_appendix`
        #     注释里记的那个老事故（「新增字段静默漏掉」）。
        _qr = getattr(view, "quant_readings", None) or {}
        if _qr:
            lines += ["", "【各环节量化】（零成本读数；缺输入一律不给）"]
            for _qk, _qv in _qr.items():
                if isinstance(_qv, dict) and len(_qv) == 1 and "value" in _qv:
                    _qv = {"value": _qv["value"]}
                if not isinstance(_qv, dict) or not _qv:
                    continue
                _vd = str(_qv.get("verdict") or "")
                _pairs = "、".join(
                    "%s=%s" % (_kk, _vv) for _kk, _vv in _qv.items()
                    if _kk != "verdict")
                lines += ["  · %s：%s%s" % (_QUANT_LABELS.get(_qk, _qk), _vd,
                                            ("（%s）" % _pairs) if _pairs else "")]

        return "\\n".join(lines)
'''

LABELS = '''#: [第六期] 量化读数的中文标签（**只做展示**；未知键降级为键名 ⇒
#: 新增读数会自动出现在产物正文里，不必回来改这张表）。
_QUANT_LABELS = {
    "restate_fidelity": "锚点保真度",
    "yin_yang_divergence": "阴阳分歧度",
    "ing_density": "ing 语义密度",
    "candidate_yield": "候选产出率",
}


def _quant_note(view, key: str, val) -> None:'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")

    # A1：加标签表（锚在 `def _quant_note(view, key: str, val) -> None:` 整行）
    a1 = "def _quant_note(view, key: str, val) -> None:"
    assert s.count(a1) == 1, "A1 锚点命中 %d 次" % s.count(a1)
    assert "_QUANT_LABELS" not in s, "标签表已存在"
    s = s.replace(a1, LABELS, 1)

    # A2：正文渲染段
    assert s.count(OLD) == 1, "A2 锚点命中 %d 次" % s.count(OLD)
    s = s.replace(OLD, NEW, 1)

    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    assert out.count(b"\n") == out.count(b"\r\n")
    P.write_bytes(out)
    print("OK 量化正文段已加；行数 %d" % out.count(b"\n"))


main()
