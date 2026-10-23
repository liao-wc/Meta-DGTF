# -*- coding: utf-8 -*-
"""v1.23.9 真跑验收（一次，同题对照 v1.23.7 的旧产物）。

题目与 2026-10-09 09:33 那次相同（`新中国的成立时间是什么时候`），
这样可以直接对照 v1.23.7 产物看三处守卫（v1.23.8）+ 取向分流（v1.23.9）。
成本档 economy（控成本）；产物落 outputs/。
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = HERE / "元DGTF-V1.23.9.py"
Q = "新中国的成立时间是什么时候"

r = subprocess.run([sys.executable, str(MAIN), Q, "--profile", "economy"],
                   capture_output=True, cwd=str(HERE))
out = r.stdout + b"\n=== STDERR ===\n" + r.stderr
(HERE / "_realrun_v1239.log").write_bytes(out)
print("EXIT =", r.returncode)
txt = out.decode("utf-8", "replace")
print("--- tail ---")
print(txt[-1500:])
