# -*- coding: utf-8 -*-
"""补丁 D3：修 `_STOP_CASCADE` **键区间重叠**（"耗尽" 吞掉 "体力耗尽"）。

★ 补丁 D2（剥括号）之后，判据立刻逮到第二层错位：

      stop_priority("体力耗尽（4 圈走满…）") == 2   # 应 3

  根因：档 2 里有**裸键 `"耗尽"`**，而 "体力**耗尽**" 是档 3 的键 ⇒
  档 2 先扫到 ⇒ 「走满被截断」被报成「无信息增益（停滞）」。
  这是**键区间重叠**：短键吞掉长键的语义。

  同理 `"停滞"` 也在档 2，而档 2 的 `"连续空转"` 等已足够表意。

修法（只动**档 2 的键表**，不新增档、不动其它档）：
  - 删裸键 `"耗尽"`：它是 `"材料耗尽"` 的**过宽子串**，且吞掉档 3 的
    `"体力耗尽"` / `"预算用尽"` 之外的 `"…耗尽"` 家族。
  - 保留 `"材料耗尽"`（本意就是它）。
  ★ 依据：本项目「键区间重叠 ⇒ 短键吞长键」是**同一个坑的第二形态**
    （第一形态是 v1.23.32 的判据正则过窄）。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

ANCHOR = '''    (2, ("无新", "无推进", "连续空转", "停滞", "材料耗尽", "耗尽")),'''
NEW = '''    (2, ("无新", "无推进", "连续空转", "停滞", "材料耗尽")),'''


def main():
    b = SRC.read_bytes()
    txt = b.decode("utf-8")
    if txt.count("\r\n") != txt.count("\n") or "\r\r\n" in txt:
        print("X 非纯 CRLF"); sys.exit(1)
    s = txt.replace("\r\n", "\n")
    n = s.count(ANCHOR)
    if n != 1:
        print("X 锚点命中 %d 次" % n); sys.exit(1)
    s = s.replace(ANCHOR, NEW, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    if out.decode("utf-8").count("\r\r\n"):
        print("X r-r-n"); sys.exit(1)
    SRC.write_bytes(out)
    print("OK 补丁 D3 已打：档 2 去掉过宽裸键「耗尽」")


if __name__ == "__main__":
    main()
