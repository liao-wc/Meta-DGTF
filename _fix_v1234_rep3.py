#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.4] 报告补丁 4：修 §六 表格的空行 + 补上第 8 行（幂等，用长锚）。"""
from pathlib import Path

P = Path("v1234_报告.md")
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n")
s = b.decode("utf-8").replace("\r\n", "\n")

# 1 去掉表格中间的裸空行（第 5 行与第 6 行之间）
BAD = ("| 5 | 冒烟 `SRC` 还指着 v1.23.3 ⇒ 全套冒烟**假绿**"
       "（181 ✓ 却根本没测到新代码） | 检查发现 `runtime` 没进 yaml 却全绿，"
       "违反预期 | 把 v1234 注入器排在 v1233 之后；SRC 由生成器统一改写 |\n\n"
       "| 6 |")
if BAD in s:
    s = s.replace(BAD, BAD.replace("\n\n| 6 |", "\n| 6 |"), 1)
    print("已去掉 §六 表格中间的裸空行")

# 2 补第 8 行（长锚做幂等守卫：判「净语特征串」在不在，而不是判「8」）
KEY = "定稿器取「真跑旁证」产物时按"
if KEY not in s:
    ROW8 = ("| 8 | ★ 定稿器取「真跑旁证」产物时按 **mtime 取最新** ⇒ 同日回归批的"
            "产物被当成我的真跑产物（那一行写着 `--effort high`、产物里却是 "
            "`effort=low`，**自相矛盾**） | 读验收表时肉眼发现 | 改成按 "
            "`_runtime.requested` **精确匹配**本次真跑给的三项 |")
    O = "## 七、经验教训"
    assert s.count(O) == 1, "§七 锚点 %d 次" % s.count(O)
    s = s.replace(O, ROW8 + "\n\n" + O, 1)
    print("已补 §六 第 8 行")
else:
    print("§六 第 8 行已存在，跳过")

P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("行数：", s.count("\n") + 1)
