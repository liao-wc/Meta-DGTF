# -*- coding: utf-8 -*-
"""等两组真跑落盘 → 跑分析 → 打印结论（后台等，完成即通知）。"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
TAGS = ["_v12315_up2", "_v12315_auto"]
DEADLINE = time.time() + 60 * 60


def done(t):
    d = OUT / t
    return bool(list(d.glob("*.md"))) if d.is_dir() else False


while time.time() < DEADLINE:
    if all(done(t) for t in TAGS):
        print("两组都已落盘", flush=True)
        break
    time.sleep(30)
else:
    print("★ 超时；当前落盘情况:", [(t, done(t)) for t in TAGS], flush=True)

time.sleep(5)
r = subprocess.run([sys.executable, str(HERE / "_analyze_v12315_realrun.py")],
                   cwd=str(HERE))
sys.exit(r.returncode)
