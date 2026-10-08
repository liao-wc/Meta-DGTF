# -*- coding: utf-8 -*-
"""[v1.23.2] 把 V1/V3 抠 `_thinking_stage` 的正则改成「容忍嵌套括号」。

起因：`_check_input_sanity` 那处的调用是
`_thinking_stage(getattr(d, 'config', None), 'check_input_sanity')` ——
参数里有**逗号**，原正则 `[^,]+` 直接抠不到 ⇒ `_wired` 少 1 个 ⇒ V3 报
「意外改动」（判据自己抠漏了，却报成配置的问题）。

★ 走脚本文件，不用 heredoc。
"""
import ast
from pathlib import Path

OLD = 'r"stage=_thinking_stage\\([^,]+,\\s*[\\"\'](\\w+)[\\"\']"'
NEW = 'r"""stage=_thinking_stage\\([^\\n]*?,\\s*["\'](\\w+)["\']\\)"""'

for f in ("_mk_v1232_verify.py", "_v122_verify.py"):
    p = Path(f)
    if not p.is_file():
        print("跳过（不存在）:", f)
        continue
    s = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
    n = s.count(OLD)
    if n == 0:
        print("未找到锚点:", f)
        continue
    s = s.replace(OLD, NEW)
    ast.parse(s)
    p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
    print("已改 %s（%d 处）" % (f, n))
