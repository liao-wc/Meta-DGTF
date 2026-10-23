# -*- coding: utf-8 -*-
"""v1.23.12 验收档：phase 6 + phase all（本版与 v1.23.11 基线各跑一次）。"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERIFY = HERE / "_v122_verify.py"


def run(src, phase):
    r = subprocess.run([sys.executable, str(VERIFY), "--src", src,
                        "--phase", phase],
                       capture_output=True, cwd=str(HERE))
    return r.returncode, (r.stdout + b"\n=== STDERR ===\n" + r.stderr)


def redlist(txt):
    out = []
    for l in txt.split("\n"):
        s = l.strip()
        if s.startswith("\u274c") or s.startswith("FAIL"):
            out.append(s)
    return out


for tag, src in (("v12312", "元DGTF-V1.23.12.py"),
                 ("v12311_base", "元DGTF-V1.23.11.py")):
    for phase in ("6", "all"):
        rc, out = run(src, phase)
        (HERE / ("_verify_v12312_%s_phase%s.log"
                 % (tag, phase))).write_bytes(out)
        txt = out.decode("utf-8", "replace")
        reds = redlist(txt)
        print("==== %-12s phase %-3s EXIT=%d | 红 %d 条"
              % (tag, phase, rc, len(reds)))
        for r in reds:
            print("    ", r[:130])
        for l in txt.split("\n"):
            s = l.strip()
            if s.startswith(("\u2705", "PASS", "\u2139", "\u2501\u2501\u2501")):
                print("     ·", s[:120])
