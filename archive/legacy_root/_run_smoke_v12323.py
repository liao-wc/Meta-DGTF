#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑全套冒烟并把 stdout+stderr 一次 write_bytes 落盘。

为什么不用 shell 的 `>`：本机 sandbox 的重定向**偶发写空/写旧**
（SKILL「坑」清单里记了两次），于是「验收没跑完」会被读成「跑到这儿就失败了」。

    python _run_smoke_v12323.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / "_smoke_v12323.log"
PY = sys.executable


def main() -> int:
    t0 = time.time()
    p = subprocess.run([PY, str(HERE / "smoke_test.py")],
                       cwd=str(HERE), capture_output=True)
    out = (p.stdout or b"") + (b"\n===== STDERR =====\n" if p.stderr else b"") + (p.stderr or b"")
    LOG.write_bytes(out)
    txt = LOG.read_text(encoding="utf-8", errors="replace")
    n_ok = txt.count("\u2713")
    n_bad = txt.count("\u2717")
    print("EXIT=%d  行数=%d  ✓=%d  ✗=%d  用时=%.1f min"
          % (p.returncode, txt.count("\n") + 1, n_ok, n_bad, (time.time() - t0) / 60))
    print("日志：%s" % LOG.name)
    if n_bad:
        print("--- 失败行（最多 20 条）---")
        for ln in txt.splitlines():
            if "\u2717" in ln:
                print("   " + ln.strip()[:160])
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
