# -*- coding: utf-8 -*-
"""看门狗：等 up2 / auto 两组落盘后，立刻停掉两个 runner（避免它们继续跑 up6/up10）。

★ 成本依据（实测）：单次 LLM 调用 ≈ 25 秒；up2（四层 × 2 圈）已用 40+ 次调用。
  up6 / up10 分别是 3× / 5× 规模 ⇒ 预计 1.5 小时以上，而边际价值低：
  **up2（上限 2）与 auto（圈数由历史定，实测 3/3/5/6）已构成两点对照**。
"""
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
WANT = {"_v12315_up2": "主实验 runner", "_v12315_auto": "auto runner"}
DEADLINE = time.time() + 60 * 90


def pids(pattern):
    try:
        r = subprocess.run(["ps", "-W"], capture_output=True, text=True)
        out = []
        for l in r.stdout.split("\n"):
            if pattern in l and "python" in l:
                f = l.split()
                if f:
                    out.append(int(f[0]))
        return out
    except Exception:  # noqa: BLE001
        return []


def done(tag):
    d = OUT / tag
    return bool(list(d.glob("*.md"))) if d.is_dir() else False


killed = set()
while time.time() < DEADLINE:
    for tag, who in WANT.items():
        if tag in killed:
            continue
        if done(tag):
            print("[%s] 已落盘 → 停掉 %s" % (tag, who), flush=True)
            pat = ("_run_v12315_uppers.py" if "up2" in tag
                   else "_run_v12315_auto.py")
            for pid in pids(pat):
                try:
                    os.kill(pid, 9)
                    print("  kill pid=%d（%s）" % (pid, pat), flush=True)
                except Exception as e:  # noqa: BLE001
                    print("  kill %d 失败：%s" % (pid, e), flush=True)
            killed.add(tag)
    if len(killed) >= len(WANT):
        print("两组都已完成并停掉 runner", flush=True)
        break
    time.sleep(20)
else:
    print("★ 看门狗超时（90 分钟）", flush=True)
print("看门狗退出", flush=True)
sys.exit(0)
