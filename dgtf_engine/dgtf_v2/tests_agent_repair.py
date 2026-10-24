# -*- coding: utf-8 -*-
import os
import tempfile
from pathlib import Path
from dgtf_v2.agent_repair import AUDIT_ENV, stage_patch, apply_patch


def main():
    ok = True
    d = Path(tempfile.mkdtemp())
    # 测试隔离：审计写临时文件，绝不污染生产 dgtf_memory/agent_patch_audit.jsonl
    audit = d / "audit.jsonl"
    os.environ[AUDIT_ENV] = str(audit)
    try:
        r = stage_patch("t1", "diff --git a/x b/x\n", ["元DGTF-V1.30.0.py"], str(d / "p"))
        ok = ok and r["path_ok"]
        print(("PASS" if r["path_ok"] else "FAIL"), "path_ok")
        r2 = stage_patch("t2", "", ["/etc/passwd"], str(d / "p"))
        ok = ok and not r2["path_ok"]
        print(("PASS" if not r2["path_ok"] else "FAIL"), "bad_path")
        a = apply_patch(str(d / "p" / "t1.patch"), "")
        r3 = a["status"] == "refused"; ok = ok and r3
        print(("PASS" if r3 else "FAIL"), "approve_required")
        lines = len(audit.read_text(encoding="utf-8").splitlines()) if audit.exists() else 0
        r4 = lines == 3; ok = ok and r4
        print(("PASS" if r4 else "FAIL"), "audit_isolated", lines)
    finally:
        os.environ.pop(AUDIT_ENV, None)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
