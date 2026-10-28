# -*- coding: utf-8 -*-
"""确定性 guard 策略检查（SCOPE/RAIL Guard 思路的轻量落地）。"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    sys.path.insert(0, str(ROOT))
    try:
        from dgtf_app import server
    except Exception as exc:
        print("FAIL import:", exc)
        return 1
    cfg = getattr(server, "_DSH_TAKEOVER_DEFAULT", {}) or {}
    bad = []
    for k in ("allow_source_edit", "allow_tests", "allow_git_commit",
              "allow_version_iteration", "allow_proposal_autofix"):
        if not cfg.get(k):
            bad.append("allow 缺失/关闭:" + k)
    deny = " ".join(str(x) for x in (cfg.get("deny") or []))
    for needle in ("git push", "git reset --hard", "force push", "secrets",
                   "account/ACL"):
        if needle not in deny:
            bad.append("deny 缺失:" + needle)
    print("guard allow keys/takeover:", cfg.get("enabled", "?"))
    print("CHECK", "PASS" if not bad else "FAIL", "; ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
