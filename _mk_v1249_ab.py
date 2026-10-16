# -*- coding: utf-8 -*-
"""生成 `_fullrun_V1249AB.py`：v1.23.48 的 A/B 真跑脚本 → 指向 v1.23.49。

动机：12:37 的 A/B 真跑（V1248）被宿主回收、24 分钟 / ~¥2 **全丢** —— 那正是
v1.23.49「跑中快照」要防的事。本版重跑一次（③ 真跑对表），**带安全网**：
  · 引擎换成 v1.23.49（含 live_checkpoint 默认 true + 孤儿回收）；
  · 其余设计**一字不动**（同题 / 同 route/rounds / 同 A/B 口径：只差五个新键）。

替换：SRC 指向、run_id 前缀 V1248→V1249、结果/汇总文件名、docstring 版本引用。
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = (HERE / "_fullrun_V1248AB.py").read_text(encoding="utf-8")
t = src

subs = [
    ('SRC = HERE / "元DGTF-V1.23.48.py"', 'SRC = HERE / "元DGTF-V1.23.49.py"'),
    ('"""v1.23.48 真跑对表（A/B 对照，唯一花钱的一步，用户已确认）。',
     '"""v1.23.49 真跑对表（A/B 对照，唯一花钱的一步，用户已确认）。\n'
     '\n'
     '★ 与 `_fullrun_V1248AB.py` 的唯一区别：引擎换成 v1.23.49 —— **带跑中快照\n'
     '  安全网**（12:37 那次 V1248 真跑被宿主回收 ⇒ 24 分钟 / ~¥2 全丢；\n'
     '  本版起 live_checkpoint 默认 true ⇒ 中断可找回）。A/B 设计一字未动。'),
    ('run_id = "V1248%s_%s" % (tag, time.strftime("%Y%m%d_%H%M%S"))',
     'run_id = "V1249%s_%s" % (tag, time.strftime("%Y%m%d_%H%M%S"))'),
    ('out = HERE / ("_fullrun_V1248%s.json" % tag)',
     'out = HERE / ("_fullrun_V1249%s.json" % tag)'),
    ('(HERE / "_fullrun_V1248A.sum.json").write_text(',
     '(HERE / "_fullrun_V1249A.sum.json").write_text('),
    ('(HERE / "_fullrun_V1248B.sum.json").write_text(',
     '(HERE / "_fullrun_V1249B.sum.json").write_text('),
]
for o, n in subs:
    c = t.count(o)
    print("锚点 %d: %s" % (c, o[:60]))
    assert c == 1, "锚点不唯一/不存在：%s" % o[:80]
    t = t.replace(o, n, 1)

assert "元DGTF-V1.23.49.py" in t and "V1249" in t
assert "元DGTF-V1.23.48.py" not in t, "还有残留的 V1248 引擎引用"
out = HERE / "_fullrun_V1249AB.py"
out.write_bytes(t.encode("utf-8"))
print("OK ->", out.name)

import py_compile
py_compile.compile(str(out), doraise=True)
print("语法 OK")
