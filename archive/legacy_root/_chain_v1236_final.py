#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动链：**等变异体全量结束 → 跑最终真跑 → 跑验收检查**（无人值守）。

## 用户口径
「所有改动和测试都完成后**最后再启动一次真跑**进行全面的验证，确认都没问题后才存档」
⇒ 本条链负责前三步；**存档留给 agent 判断**（要读验收结果才能决定）。

## 为什么要有它
变异体全量 ~25 分钟 + 真跑 ~60 分钟，中间**不该等人盯着**。
本脚本用「变异体日志里出现『变异体汇总』」作为**前一步完成的判据**
（Python 进程退出时会 flush ⇒ 该行一定落盘），然后自动接上真跑与检查。

## 用途与边界
· 只做**执行与记录**，不改任何源码；
· 真跑用**独立 tag**（`V1236FULL2`）⇒ 与上一跑（`V1236FULL`）**可对比**，
  这正是用户要的「检查之前的改动有没有生效」。
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
MUT_LOG = HERE / "_mut_v12336full.log"
TAG = "V1236FULL2"


def _say(msg):
    print("[chain %s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def wait_mutants(timeout_s: int = 3600) -> bool:
    _t0 = time.time()
    while time.time() - _t0 < timeout_s:
        if MUT_LOG.is_file():
            t = MUT_LOG.read_text(encoding="utf-8", errors="replace")
            if "变异体汇总" in t:
                _last = [l for l in t.split("\n") if "变异体汇总" in l]
                _say("变异体全量结束：%s" % (_last[-1] if _last else "?"))
                return True
        time.sleep(20)
    _say("⚠ 等变异体超时（%d 秒）—— 仍继续跑真跑" % timeout_s)
    return False


def run_full() -> int:
    _say("启动最终真跑（tag=%s）..." % TAG)
    _log = HERE / ("_fullrun_%s.log" % TAG)
    _outer = HERE / ("_fullrun_%s.outer.log" % TAG)
    cmd = [PY, str(HERE / "_run_full_v12333.py"),
           "--src", "元DGTF-V1.23.36.py", "--tag", TAG,
           "--question", "一个领域里的常识是如何形成的，它可靠吗？"]
    with open(_outer, "w", encoding="utf-8") as fo:
        _rc = subprocess.call(cmd, cwd=str(HERE), stdout=fo, stderr=fo)
    _say("真跑结束，退出码 %s" % _rc)
    if _log.is_file():
        t = _log.read_text(encoding="utf-8", errors="replace")
        _say("  行数 %d | calls≈%d | 📊 %d | 总表 %d"
             % (t.count("\n"), t.count("[tok]"),
                t.count("📊 ["), t.count("读数总表")))
    return _rc


def run_check() -> int:
    _say("跑验收检查（tag=%s）..." % TAG)
    _out = HERE / ("_chk_%s.out.txt" % TAG)
    with open(_out, "w", encoding="utf-8") as fo:
        _rc = subprocess.call([PY, str(HERE / "_chk_v12336_fullrun.py"), TAG],
                              cwd=str(HERE), stdout=fo, stderr=fo)
    _say("检查完成，退出码 %s；输出见 %s" % (_rc, _out.name))
    for l in _out.read_text(encoding="utf-8", errors="replace").split("\n"):
        if l.strip().startswith(("✓", "✗", "[OK]", "[FAIL]")):
            _say("  " + l.strip())
    return _rc


def main():
    _say("自动链启动（等变异体 → 真跑 → 检查）")
    wait_mutants()
    run_full()
    run_check()
    _say("自动链完成 —— **存档由 agent 判断**（需读验收结果）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
