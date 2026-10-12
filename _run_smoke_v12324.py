#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑冒烟并可靠落盘（本机 shell `>` 偶发写空/写旧）。"""
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "C:/Users/18432/AppData/Local/Programs/Python/Python313/python.exe"
LOG = HERE / "_smoke_v12324.log"


def main():
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    t0 = time.time()
    with open(LOG, "w", encoding="utf-8", newline="\n") as fh:
        p = subprocess.run([PY, str(HERE / "smoke_test.py")],
                           cwd=str(HERE), stdout=fh,
                           stderr=subprocess.STDOUT, env=env)
    raw = LOG.read_bytes()
    ok = raw.count("✗".encode("utf-8"))
    good = raw.count("✓".encode("utf-8"))
    print("EXIT=%d  ✓=%d  ✗=%d  行=%d  用时=%.1fs  日志=%s(%d bytes)"
          % (p.returncode, good, ok, raw.count(b"\n"),
             time.time() - t0, LOG.name, len(raw)))
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
