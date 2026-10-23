#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.36 收尾看门狗：等**已在跑的两个长任务**结束，再自动跑验收。

背景（2026-10-15 03:2x）：本机已有两个进程在跑 ——
  · `_fullrun_V1236FULL`（全开四层真跑，03:24:17 起，`_fullrun_V1236FULL.log`）
  · `_mut_v12332.py`（变异体全套 68 条，03:23:51 起，`_mut_v12336.log`）
本脚本**只观测与验收，不启动任何真跑**（避免重复花钱）。

判定「真跑结束」= 日志里出现终止标记之一：
  `[DONE] 退出码` / `[STALL]` / `[异常]`
或日志 **900 秒无新增**（进程已死且没写终止标记，按中断处理）。

判定「变异体结束」= `_mut_v12336.log` 里出现 `=== 变异体汇总`。

结束时把结论追加进 `_v12336_watch_result.txt`，并跑
`_chk_v12336_fullrun.py V1236FULL`（本轮真跑的验收判据）。
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_LOG = HERE / "_fullrun_V1236FULL.log"
MUT_LOG = HERE / "_mut_v12336.log"
OUT = HERE / "_v12336_watch_result.txt"
PY = sys.executable

TERMINAL = ("[DONE] 退出码", "[STALL]", "[异常]")
IDLE_DONE = 900          # 真跑日志静止这么久 ⇒ 判中断
MAX_WAIT = 150 * 60      # 看门狗自身上限


def say(s):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), s)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def size_of(p):
    try:
        return p.stat().st_size
    except Exception:
        return -1


def text_of(p):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def wait_run():
    t0, last, t_last = time.time(), size_of(RUN_LOG), time.time()
    while time.time() - t0 < MAX_WAIT:
        txt = text_of(RUN_LOG)
        for m in TERMINAL:
            if m in txt:
                return "terminal:%s" % m
        sz = size_of(RUN_LOG)
        if sz != last:
            last, t_last = sz, time.time()
        elif time.time() - t_last > IDLE_DONE:
            return "idle:%ds 无新增（疑中断）" % IDLE_DONE
        time.sleep(20)
    return "timeout"


def wait_mut(max_s=1800):
    t0 = time.time()
    while time.time() - t0 < max_s:
        if "=== 变异体汇总" in text_of(MUT_LOG):
            return True
        time.sleep(20)
    return False


def main():
    say("看门狗启动（只观测，不启动真跑）")
    why = wait_run()
    dt = time.strftime("%H:%M:%S")
    say("真跑结束：%s（%s）" % (why, dt))
    say("真跑日志 %d 行 / %d bytes" % (text_of(RUN_LOG).count("\n") + 1,
                                  size_of(RUN_LOG)))
    if wait_mut():
        tail = [l for l in text_of(MUT_LOG).splitlines()
                if l.startswith("===") or l.startswith("X") or
                "假绿" in l]
        say("变异体汇总：" + (tail[-1] if tail else "<空>"))
    else:
        say("变异体 30 分钟内未见汇总行（可能仍在跑）")

    chk = HERE / "_chk_v12336_fullrun.py"
    if not chk.is_file():
        say("缺 %s —— 跳过验收" % chk.name)
        return 1
    p = subprocess.run([PY, str(chk), "V1236FULL"], cwd=str(HERE),
                       capture_output=True)
    out = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8",
                                                        errors="replace")
    say("验收 _chk_v12336_fullrun.py V1236FULL 退出码=%d" % p.returncode)
    for ln in out.splitlines():
        say("  " + ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
