#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""证据健康审计（V2.2.106）。

fast_gate 一项：各门禁最新证据必须处于 PASS 状态（失败计数为 0、通过数 > 0）。
防「失败证据被后续流程当作有效数字沿用」（V2.2.104 的 26/27 写 README 事故）。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = ROOT / "docs"
PROBE = ROOT / "outputs" / "_e2e_local" / "_layer_goals_probe_latest.json"


def _j(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def main() -> int:
    rows = []

    def add(name, ok, detail=""):
        rows.append((name, ok, detail))

    v2 = _j(DOCS / "v2_tests_latest.json")
    add("v2_tests", bool(v2) and not v2.get("fail") and int(v2.get("passed") or 0) > 0,
        "pass=%s fail=%s" % (v2.get("passed"), v2.get("fail")))
    st = _j(DOCS / "app_selftest_latest.json")
    add("app_selftest", bool(st) and not st.get("fail")
        and int(st.get("pass") or 0) > 0,
        "pass=%s fail=%s" % (st.get("pass"), st.get("fail")))
    ac = _j(DOCS / "acceptance_latest.json")
    add("acceptance", bool(ac) and not ac.get("failed")
        and int(ac.get("passed") or 0) > 0,
        "pass=%s fail=%s" % (ac.get("passed"), ac.get("failed")))
    pr = _j(PROBE)
    add("probe", bool(pr) and not pr.get("fail")
        and int(pr.get("pass") or 0) > 0,
        "pass=%s fail=%s" % (pr.get("pass"), pr.get("fail")))

    bad = [r for r in rows if not r[1]]
    for name, ok, detail in rows:
        print(("PASS " if ok else "FAIL ") + "%s: %s" % (name, detail))
    print("evidence items=%d fail=%d" % (len(rows), len(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
