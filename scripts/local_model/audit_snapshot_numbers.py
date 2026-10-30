#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""状态快照数字一致性审计（V2.2.100）。

把「当前状态快照」与各门禁最新证据逐项对齐，防 V2.2.99 那类
「标题已升版、正文数字仍是旧版」的长期漂移。
用法：python scripts/local_model/audit_snapshot_numbers.py
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = ROOT / "docs"


def _j(name: str) -> dict:
    p = DOCS / name
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _snapshot() -> Path | None:
    files = sorted(glob.glob(str(DOCS / "项目状态快照_*.md")))
    return Path(files[-1]) if files else None


def main() -> int:
    snap = _snapshot()
    if snap is None:
        print("FAIL 找不到 docs/项目状态快照_*.md")
        return 1
    text = snap.read_text(encoding="utf-8", errors="replace")
    rows = []

    # ★ fast_gate 行不能比对 fast_gate_latest.json —— 那是本检查的产物，
    #   会比对产生「证据滞后一圈」循环。改为直接数源码里的检查项（与门禁同源）。
    fg = None
    try:
        import sys as _sys
        _sys.path.insert(0, str(ROOT))
        import fast_gate as _fg
        n = len(_fg.build_checks(None))
        want = "%d/%d PASS" % (n, n)
        rows.append(("fast_gate", want, want in text))
    except Exception as _e:  # noqa: BLE001
        rows.append(("fast_gate", "build_checks 失败: %s" % _e, False))

    v2 = _j("v2_tests_latest.json")
    if v2:
        want = "%d/%d 文件 · %d checks" % (
            v2.get("passed", 0), v2.get("files", v2.get("total", 0)),
            v2.get("checks", 0))
        rows.append(("v2_tests", want, want in text))

    st = _j("app_selftest_latest.json")
    if st:
        want = "%d / %d" % (st.get("pass", 0), st.get("fail", 0))
        rows.append(("app_selftest", want, want in text))

    ac = _j("acceptance_latest.json")
    if ac:
        want = "PASS %d / SKIP %d / FAIL %d" % (
            ac.get("passed", ac.get("pass", 0)),
            ac.get("skipped", ac.get("skip", 0)),
            ac.get("failed", ac.get("fail", 0)))
        rows.append(("acceptance", want, want in text))

    # 引擎版本（最新引擎文件名里的 Vx.y.z）
    import re
    engs = glob.glob(str(ROOT / "dgtf_engine" / "dgtf_v2" / "engine" / "Meta-DGTF-V*.py"))
    best = None
    for f in engs:
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)\.py$", Path(f).name)
        if m:
            key = tuple(int(x) for x in m.groups())
            if best is None or key > best[0]:
                best = (key, "V%d.%d.%d" % key)
    if best:
        want = best[1]
        rows.append(("engine_version", want, want in text))

    bad = [r for r in rows if not r[2]]
    print("snapshot: %s" % snap.name)
    for name, want, ok in rows:
        print(("PASS " if ok else "FAIL ") + "%s: %s" % (name, want))
    print("checks=%d fail=%d" % (len(rows), len(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
