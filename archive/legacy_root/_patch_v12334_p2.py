# -*- coding: utf-8 -*-
"""v1.23.34 第二期：`ing`（对撞）提示词 —— 有据 + 智者语气 + 输出结构。

## 用户诉求
「ing、对撞 … 引用证据论述；有深度 + 让人类看得懂；语气像智者、和蔼；字数按需；
有理有据；优化 ing 的输出结构。」

## 前沿依据
① **第四面墙**（见第一期）：引用只到**内容**、不到**管道** ⇒ 复用 `EVIDENCE`；
② **换语气不改数据**：只改「怎么说」，不动六步、不动 `===ING-STRUCT===` 契约；
③ **证据要求要具体**：每步「先给结论、再给依据」——把"有据"落成可执行写法。

## 改什么 / 不改什么
**改**：① 六步正文要求**各起一行、用「一、」到「六、」打头**（输出结构，便于阅读）；
        ② 每步**先结论后依据**（有据）；
        ③ 接上 `VOICE` + `EVIDENCE`；④ 明确「篇幅按需」。
**不改**：① `===ING-STRUCT===` 结构化尾块（机器解析契约，`view.ing_structured`）；
          ② `_fix83_block` 硬约束（不许复述上游）；③ 六步本身与 `ing_focus`；
          ④ 原有「不煽情、不客服」的反廉价感要求（只在其后**追加**）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.34.py"

ANCHOR = '''            f"【本层侧重】{self.phase.ing_focus}\\n"
            "语气：清醒、克制，不煽情，不客服。\\n"'''

NEW = '''            f"【本层侧重】{self.phase.ing_focus}\\n"
            "语气：清醒、克制，不煽情，不客服。\\n"
            + VOICE
            + EVIDENCE
            + "【写法】六步各起一行，用「一、」到「六、」打头；"
            "每步先给一句结论，再给依据。\\n"
            "篇幅按需：六步走完即止——不要为了显得充实而铺陈。\\n"'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")

    n = s.count(ANCHOR)
    assert n == 1, "锚点命中 %d 次（应为 1）" % n
    s = s.replace(ANCHOR, NEW, 1)

    # ── 硬约束：这几样必须原样还在 ──
    for _tok in ("===ING-STRUCT===", "_fix83_block", "结构化尾块",
                 "ing_structured", "不煽情，不客服"):
        assert _tok in s, "硬约束「%s」不见了" % _tok
    # ★ 分别断言**定义数**与**使用数**（比数总出现次数精确）：总次数会把
    #   注释里提到的名字也算进去 ⇒ 容易出现「差 1」的假警报。
    assert s.count('VOICE = """') == 1, \
        "VOICE 定义数应为 1（实得 %d）" % s.count('VOICE = """')
    assert s.count('EVIDENCE = """') == 1, \
        "EVIDENCE 定义数应为 1（实得 %d）" % s.count('EVIDENCE = """')
    # 使用处：六处视角 + 一处 ing = **7**（缩进都是 12 空格，故合并计数）。
    assert s.count("            + VOICE") == 7, \
        "VOICE 使用数应为 7（六视角 + ing，实得 %d）" % s.count("            + VOICE")
    assert s.count("            + EVIDENCE") == 7, \
        "EVIDENCE 使用数应为 7（实得 %d）" % s.count("            + EVIDENCE")
    assert s.count('"【写法】六步各起一行') == 1, "ing 的【写法】段没接上"

    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    assert out.count(b"\n") == out.count(b"\r\n")
    P.write_bytes(out)
    print("OK 第二期已应用；行数 %d" % out.count(b"\n"))


main()
