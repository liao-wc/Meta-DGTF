#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MEMORY.md 的 v1.23.6 节：按段落边界替换（不靠凭记忆的锚点）。"""
import re
from pathlib import Path

MEM = Path(__file__).resolve().parent / ".workbuddy" / "memory" / "MEMORY.md"
HEAD = "## ★ v1.23.6 起：代码正文不留「版次批注」"

NEW = """## ★ v1.23.6 起：代码正文不留「版次批注」（已落地）
- 模块 docstring **之外**不留版次标记；变更记录统一由 docstring changelog 承担。
- **口径**（判据与清理工具必须同一把尺子）：`\\[v\\d[^\\]]*\\]` 方括号短标签 ｜
  `(?<![A-Za-z0-9_-])v\\d+(?:\\.\\d+)*(?![A-Za-z0-9_-])` 裸 v+数字；两侧 lookaround
  挡掉 `deepseek-v4-pro` 这类假阳性。
- **量法按「块」不按「行」**：实测 注释行 441 / **批注块 378 个 / 覆盖 1479 行**
  （窄口径 `v1\\.2\\d` 只报 395 行 ⇒ 低估到 1/4；块内只有首行带标记）。
- ★★ **测试套件会把注释当锚点** —— 三类耦合：`assert "<注释片段>" in src`、
  `getsource(方法)` 里查注释、**变异体锚点含注释**（本轮 156 个片段）。
  ⇒ **清理必须配「判据驱动的保护名单」**：P1 含 `[AUDIT-n]` 的行不删；P2 判据片段做
  **最小代价保护**（只在会全部消失时保最短那一行）。**保护粒度 = 清理成败**。
- ★ **只删注释可被机器证明为零代码改动**（注释不进 AST）：AST 严格等价 + 字符串常量
  差异逐点 == 「剥前导标记」。见 `_mk_v1236_strip.py` 四条断言。
- 判据：抠 docstring 后无版次标记 + 变异体（插一行必须判红）；抠前先归一化换行。
- 残留口径：docstring **正文中段**的版本提及（40 个常量 / 76 行）不动 —— 那是文档
  行文，不是「代码前面的修改描述」；清它属编辑决策，另开一批。
"""

t = MEM.read_bytes().decode("utf-8").replace("\r\n", "\n")
if "（已落地）" in t and "批注块 378" in t:
    print("[skip] 已改过")
else:
    i = t.index(HEAD)
    j = t.index("\n## ", i + 1) + 1
    t = t[:i] + NEW + t[j:]
    MEM.write_bytes(t.replace("\n", "\r\n").encode("utf-8"))
    print("已替换 v1.23.6 节")
b = MEM.read_bytes()
print("MEMORY.md: %d 字节 字符=%d 行=%d CRLF=%d 裸LF=%d CRCRLF=%d"
      % (len(b), len(b.decode("utf-8")), b.count(b"\n"), b.count(b"\r\n"),
         b.count(b"\n") - b.count(b"\r\n"), b.count(b"\r\r\n")))
