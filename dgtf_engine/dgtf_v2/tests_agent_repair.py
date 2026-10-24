# -*- coding: utf-8 -*-
import tempfile
from pathlib import Path
from dgtf_v2.agent_repair import stage_patch, apply_patch


def main():
    ok = True
    d = Path(tempfile.mkdtemp())
    r = stage_patch("t1", "diff --git a/x b/x\n", ["元DGTF-V1.30.0.py"], str(d / "p"))
    ok = ok and r["path_ok"]
    print(("PASS" if r["path_ok"] else "FAIL"), "path_ok")
    r2 = stage_patch("t2", "", ["/etc/passwd"], str(d / "p"))
    ok = ok and not r2["path_ok"]
    print(("PASS" if not r2["path_ok"] else "FAIL"), "bad_path")
    a = apply_patch(str(d / "p" / "t1.patch"), "")
    r3 = a["status"] == "refused"; ok = ok and r3
    print(("PASS" if r3 else "FAIL"), "approve_required")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
