# -*- coding: utf-8 -*-
"""[v1.23.3] 修 `_ab_thinking_v1233.py`：`--from-capture` 必须**整段跳过录播**。

原实现只在 `by_stage` 构造处才判 `--from-capture` ⇒ 录播被**重跑一遍**
（白花 16 分钟），而且会把 `_v1233_think_capture.json` **覆盖**掉 —— 丢掉
`_ab_thinking_direct.py` 直接驱动来的那 5 个 stage。
（本机实踩：跑起来才发现。教训：skip 必须放在**被 skip 的那段之前**。）
"""
from pathlib import Path
import ast

BS = chr(92)
P = Path("_ab_thinking_v1233.py")
s = P.read_text(encoding="utf-8")
lines = s.split("\n")

# 1) 在录播段之前插入早退分支
k = None
for i, l in enumerate(lines):
    if l.strip() == "m.LLM.call = _patched":
        k = i
        break
assert k is not None, "找不到录播段入口 `m.LLM.call = _patched`"
print("录播段入口行:", k + 1, repr(lines[k]))
lines.insert(k, '    if "--from-capture" in sys.argv:')
lines.insert(k + 1, '        print("[think] --from-capture：跳过录播", flush=True)')
lines.insert(k + 2, "    else:")
# 把录播段缩进

j = None
for i in range(k + 3, len(lines)):
    if lines[i].strip() == "m.LLM.call = _orig":
        j = i
        break
assert j is not None, "找不到录播段结束 `m.LLM.call = _orig`"
for i in range(k + 3, j + 1):
    if lines[i].strip():
        lines[i] = "    " + lines[i]
s2 = "\n".join(lines)
ast.parse(s2)
P.write_text(s2, encoding="utf-8")
print("录播段已缩进进 else 分支（%d~%d 行）" % (k + 1, j + 1))
