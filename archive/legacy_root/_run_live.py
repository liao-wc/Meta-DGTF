# -*- coding: utf-8 -*-
"""运行子进程并把 stdout/stderr 实时写入日志（给右栏实时面板 tail）。"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
argv = sys.argv[1:]
assert "--" in argv, "用法: python _run_live.py <日志> -- <命令...>"
i = argv.index("--")
log = HERE / argv[:i][0]
cmd = argv[i + 1:]
p = subprocess.Popen(cmd, cwd=str(HERE), stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, bufsize=0)
with log.open("wb") as f:
    assert p.stdout is not None
    while True:
        chunk = p.stdout.read(1024)
        if not chunk:
            break
        f.write(chunk)
        f.flush()
        try:
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
        except Exception:
            pass
code = p.wait()
print("\nEXIT=%d 日志 %s（%d 字节）" % (code, log.name, log.stat().st_size), flush=True)
raise SystemExit(code)
