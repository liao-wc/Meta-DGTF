#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.28 补丁 ③：E1 增益透传真 bug —— `_gains` 键取错字段。

【问题】L4408：
    `_gains = {str(x.get("text", "")): x.get("g")
               for x in (_det.get("trace") or []) if x.get("picked")}`
  · `select_probe_focus_submodular` 的 trace 条目键是 **`"picked"`**
    （值为被选候选的文本），**没有 `"text"` 键**；
  · 于是 `str(x.get("text",""))` **恒为 `""`** ⇒ `_gains == {"": G}`；
  · 后续 `_gains.get(str(_r.get("question")))` **恒 miss** ⇒
    `expected_gain_engine` **恒 None**、`gain_source` **恒 "model"**。
  ⇒ E1「EIG 可计算化」算出来的 G **从未到达输出** ——
    「有接线 ≠ 这跑走得到」的又一例。纯函数判据（`probe_information_gain`
    直接喂参）全绿，真实入口却把结果丢了。

【修法】按真实键取：`x.get("picked")`。

★ CRLF 往返 + 命中 == 1 断言。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TGT = HERE / "元DGTF-V1.23.28.py"

raw = TGT.read_bytes()
if raw.count(b"\r\n") != raw.count(b"\n"):
    sys.exit("❌ 不是纯 CRLF")
text = raw.decode("utf-8").replace("\r\n", "\n")

OLD = '''    _gains = {str(x.get("text", "")): x.get("g")
              for x in (_det.get("trace") or []) if x.get("picked")}'''
NEW = '''    # ★ trace 条目的键是 **"picked"**（值是候选文本），不是 "text"。
    #   改前用 `x.get("text","")` ⇒ 键恒为 "" ⇒ 增益**从未到达输出**
    #   （E1 白算）。这条修正由 `check_v12328_real_entry` 的 R-T1 背书。
    _gains = {str(x.get("picked", "")): x.get("g")
              for x in (_det.get("trace") or []) if x.get("picked")}'''

n = text.count(OLD)
if n != 1:
    sys.exit("❌ 锚点命中 %d 次（须 == 1）" % n)
text = text.replace(OLD, NEW)

out = text.replace("\n", "\r\n").encode("utf-8")
if out.count(b"\r\r\n"):
    sys.exit("❌ 产出含 \\r\\r\\n")
TGT.write_bytes(out)
print("已应用 1 项：gain-key")
print("主文件：%d 行 / %d bytes / CRCRLF=%d"
      % (out.count(b"\n"), len(out), out.count(b"\r\r\n")))
