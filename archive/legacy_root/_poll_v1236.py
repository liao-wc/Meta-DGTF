#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轮询 v1.23.36 全开真跑的进度（每 5 分钟一行，追加到 `_poll_v1236.log`）。

## 为什么单独做轮询器
用户在等长跑结果 ⇒ 需要**持续的进度读数**，而不是问一次答一次。
★ 用 Python 读日志而**不用 `grep`**：日志里有 emoji，`grep` 会**假阴性**
  （本版实测：`grep -c '📊'` = 0，Python 读 = 2~6）。
★ 轮询器**自己也会被回收**（与真跑同风险）⇒ 少轮、写盘、跑完即退。
"""
import io
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "_fullrun_V1236FULL.log")
OUT = os.path.join(HERE, "_poll_v1236.log")
ROUNDS, GAP = 14, 300          # 14 轮 × 5 分钟 ≈ 70 分钟


def snap():
    if not os.path.isfile(LOG):
        return "（日志未生成）"
    t = io.open(LOG, encoding="utf-8", errors="replace").read()
    _layers = [e for e in ("0", "1", "both", "all") if ("【%s】" % e) in t]
    _done = t.count("📊 [")
    _fin = "是" if "[DONE]" in t else "否"
    _tail = [l for l in t.split("\n") if l.strip()][-1][:60]
    return ("行 %-6d calls %-4d 圈 %-3d 完成层 %-16s 读数行 %-2d DONE %s | 尾: %s"
            % (t.count("\n"), t.count("[tok]"), t.count("圈）"),
               ",".join(_layers) or "-", _done, _fin, _tail))


def main():
    with io.open(OUT, "a", encoding="utf-8") as f:
        f.write("\n=== 轮询开始 %s ===\n" % time.strftime("%m-%d %H:%M:%S"))
        for i in range(ROUNDS):
            _s = snap()
            f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), _s))
            f.flush()
            if "DONE 是" in _s:
                f.write("=== 真跑完成，轮询退出 ===\n")
                break
            time.sleep(GAP)
        else:
            f.write("=== 轮询到上限退出（真跑可能仍在跑）===\n")


main()
