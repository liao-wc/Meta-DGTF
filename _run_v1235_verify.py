# -*- coding: utf-8 -*-
"""跑 v1.23.5 的 --phase all，脚本自己落盘（本机 shell > 重定向不可靠）。"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
p = subprocess.run(
    [sys.executable, str(HERE / "_v122_verify.py"),
     "--src", str(HERE / "元DGTF-V1.23.5.py"), "--phase", "all"],
    capture_output=True, cwd=str(HERE))
out = (p.stdout or b"") + (p.stderr or b"")
dst = HERE / "_v1235_verify_all.log"
dst.write_bytes(out)
t = out.decode("utf-8", errors="replace")
print("exit", p.returncode, "bytes", len(out), "-> ", dst.name)
print("-" * 60)
for ln in t.split("\n"):
    if ("PASS" in ln or "FAIL" in ln or "❌" in ln
            or "Traceback" in ln or "crash" in ln.lower()):
        print(ln[:200])
