# -*- coding: utf-8 -*-
"""修 v1.23.15 补丁脚本「历史行口径」锚点：把单反斜杠写成双反斜杠。

★ 原因：补丁脚本里 `repl(old, new)` 的 old/new 是 **Python 源字符串**，
  要匹配文件里**字面**的 `\n`（反斜杠+n），源里必须写 `\\n`；
  只写 `\n` 会被 Python 解析成真换行，锚点再也匹配不到。
"""
import ast
from pathlib import Path

B2 = chr(92) * 2
p = Path("_mk_v12315_patch.py")
L = p.read_text(encoding="utf-8").split("\n")
tgt = None
for i, l in enumerate(L):
    if l.startswith("repl('''") and "- 题型特征" in l:
        tgt = i
        break
assert tgt is not None, "找不到锚点行"
print("修正前:", repr(L[tgt]))
L[tgt] = ('repl(\'\'\'    out.append("' + B2 + 'n- 题型特征：%s' + B2 + 'n"\'\'\',')
print("修正后:", repr(L[tgt]))
p.write_text("\n".join(L), encoding="utf-8")
ast.parse(p.read_text(encoding="utf-8"))
print("语法 OK")
