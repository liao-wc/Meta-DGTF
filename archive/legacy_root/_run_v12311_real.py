# -*- coding: utf-8 -*-
"""v1.23.11 真跑验收：`--web auto`（默认）+ 事实型询问 ⇒ 应自动接入外部校验。

最小规模：`--route 1 --rounds 1`（只跑研究层 1 圈），只买「R10 接线是否真走到」。
不显式传 `--web`，走默认 auto —— 验证的正是「事实题自动接入」这条。
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = HERE / "元DGTF-V1.23.11.py"
Q = "新中国的成立时间是什么时候"

r = subprocess.run([sys.executable, str(MAIN), Q,
                    "--route", "1", "--rounds", "1"],
                   capture_output=True, cwd=str(HERE))
out = r.stdout + b"\n=== STDERR ===\n" + r.stderr
(HERE / "_realrun_v12311.log").write_bytes(out)
print("EXIT =", r.returncode)
print(out.decode("utf-8", "replace")[-2500:])
