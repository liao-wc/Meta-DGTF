# -*- coding: utf-8 -*-
"""补丁 C：`goal_trace`（逐圈目标序列）+ `goal_verdict` 进 View.to_dict 出口。

★ 依据本项目通病：「字段有值 ≠ 有出口」。`goal_trace` 每圈在 append，
  但不出出口 ⇒ 产物里看不到 ⇒ 真跑无法验收「每圈都读到目标」。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

ANCHOR = '''        if getattr(self, "sem_stagnation", None) is not None:
            d["sem_stagnation"] = float(self.sem_stagnation)'''

NEW = '''        if getattr(self, "sem_stagnation", None) is not None:
            d["sem_stagnation"] = float(self.sem_stagnation)
        # ★ [四层目标 · 运行痕迹] 逐圈目标读数序列（停因判据就是读它）。
        #   出口的理由：真跑验收要能看见「每圈有没有读到目标」——
        #   只 append 不出出口 = 产物里看不到（本项目已栽过多次）。
        if getattr(self, "goal_trace", None):
            d["goal_trace"] = list(self.goal_trace)
        if getattr(self, "goal_verdict", ""):
            d["goal_verdict"] = str(self.goal_verdict)'''


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
    print("OK 补丁 C 已打：锚点命中 1 次")


if __name__ == "__main__":
    main()
