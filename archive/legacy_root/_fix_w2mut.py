# -*- coding: utf-8 -*-
"""更新 `check_v123_w2` 里变异体 M2 的锚点（[v1.23.2] 新增 W# tier 门后失效）。

原因：M2 原先锚「W# 进表」整块（从 `if getattr(pool, "web_as_evidence"...)` 到
`break`）—— 本版在这块中间插了 tier 门（两行 + 三行注释），原来的锚**不连续**了
⇒ 命中 0 次。处理：把锚改成**更稳的尾段**（`_wi += 1` 到 `break`），
变异体改成 `pass`：删掉 append 后 W# 同样进不了引用表，M2 的判据意图不变。

★ 走脚本文件，不用 heredoc（转义会被吃掉）。
"""
import ast
from pathlib import Path

P = Path("_mk_v1230_smoke_checks.py")
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

OLD = """            ("M2 W# 进表",
             '    if getattr(pool, "web_as_evidence", False):\\n'
             '        _wi = 0\\n'
             '        for _w in (getattr(pool, "web_results", None) or []):\\n'
             '            if not str((_w or {}).get("claim", "")).strip():\\n'
             '                continue\\n'
             '            _wi += 1\\n'
             '            out.append((str(_w.get("id") or ("W" + str(_wi))),\\n'
             '                        str(_w.get("claim", ""))[:120]))\\n'
             '            if _wi >= 20:\\n'
             '                break\\n', ""),"""
NEW = """            # ★ [v1.23.2] 锚点改为**尾段**：本版在这块中间插了 W# tier 门
            #   （`if not _web_enters_citation(...): continue`）⇒ 原来那个
            #   从 `if getattr(pool, ...)` 到 `break` 的连续锚**已不连续**，
            #   命中 0 次（判据随实现更新，不是放宽）。
            #   变异体改为 `pass`：删掉 append 后 W# 同样进不了引用表，
            #   M2 的判据意图（「W# 有没有进表」）一字未改。
            ("M2 W# 进表",
             '            _wi += 1\\n'
             '            out.append((str(_w.get("id") or ("W" + str(_wi))),\\n'
             '                        str(_w.get("claim", ""))[:120]))\\n'
             '            if _wi >= 20:\\n'
             '                break\\n',
             '            pass\\n'),"""
assert s.count(OLD) == 1, "M2 锚点命中 %d 次" % s.count(OLD)
s = s.replace(OLD, NEW)
ast.parse(s)
P.write_bytes(s.encode("utf-8"))
print("M2 变异体锚点已更新为尾段")
