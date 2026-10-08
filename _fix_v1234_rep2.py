#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.4] 报告补丁 3：第 8 处发现 + 教训 9（幂等）。"""
from pathlib import Path

P = Path("v1234_报告.md")
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "报告不是纯 CRLF"
s = b.decode("utf-8").replace("\r\n", "\n")

ROW8 = ("| 8 | ★ 定稿器取「真跑旁证」产物时按 **mtime 取最新** ⇒ 同日回归批的产物被"
        "当成我的真跑产物（那一行写着 `--effort high`、产物里却是 `effort=low`，"
        "**自相矛盾**） | 读验收表时肉眼发现 | 改成按 `_runtime.requested` "
        "**精确匹配**本次真跑给的三项 |")

if ROW8.split("|")[1].strip() not in s:
    O = "## 七、经验教训"
    assert s.count(O) == 1, "§七 锚点 %d 次" % s.count(O)
    s = s.replace(O, ROW8 + "\n\n" + O, 1)
    print("§六 已补第 8 行")

TXT9 = "\n".join([
    "9. ★ **「取最新产物」是另一种会腐烂的锚。** 平时它比「取排序第一」好，",
    "   但当天还有别的批次产物时，它照样取错 —— 而且错得**看不出来**",
    "   （差异藏在 JSON 深处，只有把人写的那行字与产物对读才会发现）。",
    "   正解：**按内容匹配你在找的那份**（这里按 `_runtime.requested` 的三个值）。",
    "   ★ 通则：**引用产物时，别用「时间 / 名字」定位，用「内容特征」定位。**",
    "",
    "## 八、附录：交付物",
])
if "「取最新产物」是另一种会腐烂的锚" not in s:
    O2 = "## 八、附录：交付物"
    assert s.count(O2) == 1, "§八 锚点 %d 次" % s.count(O2)
    s = s.replace(O2, TXT9, 1)
    print("§七 已补教训 9")

# 附录补两个脚本
O3 = "| `_flatcfg.py` | 对读两份配置、打印差异项（报告里「行为不变」的证据来源） |"
if O3 in s and "_fix_v1234_realrow.py" not in s:
    s = s.replace(O3, O3 + "\n"
                  "| `_fix_v1234_realrow.py` | 修「真跑旁证」取材逻辑"
                  "（按 `requested` 精确匹配，不按 mtime 取最新） |", 1)
    print("§八 已补 _fix_v1234_realrow.py")

P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("报告行数：", s.count("\n") + 1)
