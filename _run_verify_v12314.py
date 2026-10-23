# -*- coding: utf-8 -*-
"""v1.23.14 验收档：phase 6 + phase all（本版与 v1.23.13 基线各跑一次）。"""
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


for tag, src in (("v12314", "元DGTF-V1.23.14.py"),
                 ("v12313_base", "元DGTF-V1.23.13.py")):
    for phase in ("6", "all"):
        rc, out = run(src, phase)
        (HERE / ("_verify_v12314_%s_phase%s.log" % (tag, phase))).write_bytes(out)
        txt = out.decode("utf-8", "replace")
        reds = [l.strip() for l in txt.split("\n")
                if l.strip().startswith("\u274c")]
        print("==== %-12s phase %-3s EXIT=%d | 红 %d 条"
              % (tag, phase, rc, len(reds)))
        for r in reds:
            print("    ", r[:130])
        for l in txt.split("\n"):
            if "\u2501\u2501\u2501" in l:
                print("     ", l.strip()[:60])
