# -*- coding: utf-8 -*-
"""补丁 D：把**目标停因**登记进 `_STOP_CASCADE`（修优先级错位）。

★ 自洽核查逮到：`stop_priority` 按**关键词**映射优先级，而目标停因文案
  （「修行目标已达成」「研究目标已达成」「对撞目标受阻」「元层目标已达成」）
  **一个都不命中** `_STOP_CASCADE` 的键 ⇒ 全落到**最低档 3**
  —— 与「体力耗尽」同级。语义错位：**目标达成属于「判定/收敛达成」= 档 0**
  （与「职责增益收敛」同类）。

  不修的话：目标达成停因会被报成「最低优先级主因」，与真实语义相反
  （正是本项目反复栽的「方向错的断言比没断言更危险」的同族）。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

ANCHOR = '''    (0, ("职责增益收敛", "结构饱和度", "悬置决定稳定", "自然安住")),'''
NEW = '''    (0, ("职责增益收敛", "结构饱和度", "悬置决定稳定", "自然安住",
         # ★ [四层目标] 目标达成 = 判定/收敛达成，**与上述同级**。
         #   缺了这行，目标停因会落到最低档 3（与「体力耗尽」同级）——
         #   语义刚好相反（达成 ≠ 耗尽力竭）。
         "目标已达成", "目标受阻")),'''


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
    print("OK 补丁 D 已打：目标停因登记进优先级 0")


if __name__ == "__main__":
    main()
