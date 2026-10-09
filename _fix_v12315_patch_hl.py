# -*- coding: utf-8 -*-
"""修 v1.23.15 补丁脚本：把「取样口径」块插到 `_hl` 赋值**之后**。

★ 上一版把这块插在「题型特征」行之前，而 `_hl` 的赋值在那之后 ⇒
  `UnboundLocalError`（`_auto_dispatch_lines` 一调用就炸，产物渲染整个失效）。
  是**上一版遗留的判据**（v12314 的「产物渲染异常」）抓出来的。
★ 教训：插入点必须晚于它用到的所有变量 —— 判据要能跑到那段代码才看得见。
"""
import ast
from pathlib import Path

p = Path("_mk_v12315_patch.py")
s = p.read_text(encoding="utf-8")

OLD_ANCHOR = '''repl(\'\'\'    out.append("\\n- 题型特征：%s\\n"\'\'\',
     \'\'\'    if _hl is not None:
        out.append("- 取样口径：每题型上限 %s 条 · 时间半衰期 %s 天"
                   "（0=不衰减）\\n" % (_plt or "—", _hl))
    out.append("- 题型特征：%s\\n"\'\'\',
     "历史行口径")'''
NEW_ANCHOR = '''# ★ 插到「历史读数」行**之前**（那行的位置晚于 `_hl` 赋值）；插在
#   「题型特征」之前会撞 `UnboundLocalError`（变量还没赋值）。
repl(\'\'\'    out.append("- 历史读数：**%d 份**（%s）· token 中位 %s / p75 %s · "\'\'\',
     \'\'\'    if _hl is not None:
        out.append("- 取样口径：每题型上限 %s 条 · 时间半衰期 %s 天"
                   "（0=不衰减）\\n" % (_plt or "—", _hl))
    out.append("- 历史读数：**%d 份**（%s）· token 中位 %s / p75 %s · "\'\'\',
     "历史行口径")'''
assert s.count(OLD_ANCHOR) == 1, "历史行口径锚点 %d" % s.count(OLD_ANCHOR)
s = s.replace(OLD_ANCHOR, NEW_ANCHOR, 1)
p.write_text(s, encoding="utf-8")
ast.parse(s)
print("补丁脚本已修（取样口径插到 _hl 赋值之后）")
