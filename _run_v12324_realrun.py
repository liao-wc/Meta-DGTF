#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.24 真跑验收：与 05:06 产物**同题同参**，只有引擎版本不同。

对照口径（改前 = 05:06 那份 v1.23.23 产物）：
  同题面 / 同 config（dgtf_app 的 20261013_042550_dff558.yaml）/
  --route 0,1 / --rounds 4 / --web on / --thinking on。
"""
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "C:/Users/18432/AppData/Local/Programs/Python/Python313/python.exe"
LOG = HERE / "_realrun_v12324.log"
CFG = HERE / "dgtf_app/runs/20261013_042550_dff558.yaml"
Q = "普通人应该做些什么来迎接AI时代的到来?"


def main():
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    # 引擎从环境变量取 key ⇒ 自己把 .env 读进来（不打印任何值）
    for ln in (HERE / ".env").read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        env.setdefault(k.strip(), v.strip())

    cmd = [PY, "-u", str(HERE / "元DGTF-V1.23.24.py"), Q,
           "--config", str(CFG), "--route", "0,1", "--rounds", "4",
           "--web", "on", "--thinking", "on"]
    print("CMD: %s" % " ".join(cmd[1:]))
    t0 = time.time()
    with open(LOG, "w", encoding="utf-8", newline="\n", buffering=1) as fh:
        p = subprocess.run(cmd, cwd=str(HERE), stdout=fh,
                           stderr=subprocess.STDOUT, env=env)
    print("EXIT=%d  用时=%.0fs  日志=%s" % (p.returncode, time.time() - t0,
                                          LOG.name))
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
