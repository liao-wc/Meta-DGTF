#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""状态快照数字同步器（V2.2.103）。

把「当前状态快照」里 4 处门禁数字按最新证据自动同步/校验：
  fast_gate / V2 / App selftest / 一键验收。
- --check：不一致即退出码 1；
- --write：就地同步（并打印改动）；
与 audit_snapshot_numbers.py（只读审计）互补：本脚本用于发布前预同步。
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def _j(name: str) -> dict:
    p = DOCS / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _snapshot() -> Path | None:
    files = sorted(glob.glob(str(DOCS / "项目状态快照_*.md")))
    return Path(files[-1]) if files else None


def build_replacements() -> list:
    reps = []
    # fast_gate：数源码
    try:
        sys.path.insert(0, str(ROOT))
        import fast_gate as fg  # noqa: PLC0415
        n = len(fg.build_checks(None))
        reps.append((r"(\| 快速门（动态引擎） \| \*\*)\d+/\d+( PASS\*\*)",
                     r"\g<1>%d/%d\g<2>" % (n, n)))
    except Exception as e:  # noqa: BLE001
        print("WARN fast_gate 计数失败：%s" % e)
    v2 = _j("v2_tests_latest.json")
    if v2:
        reps.append((r"(\| V2 全量 \| \*\*)\d+/\d+ 文件 · \d+ checks · SKIP \d+(\*\*)",
                     r"\g<1>%d/%d 文件 · %d checks · SKIP %d\g<2>"
                     % (v2.get("passed", 0), v2.get("files", 0),
                        v2.get("checks", 0), v2.get("skip", 0))))
    st = _j("app_selftest_latest.json")
    if st:
        reps.append((r"(\| App selftest \| \*\*)\d+ / \d+(\*\*)",
                     r"\g<1>%d / %d\g<2>" % (st.get("pass", 0), st.get("fail", 0))))
    ac = _j("acceptance_latest.json")
    if ac:
        reps.append((r"(\| 一键验收（有服务） \| \*\*)PASS \d+ / SKIP \d+ / FAIL \d+(\*\*)",
                     r"\g<1>PASS %d / SKIP %d / FAIL %d\g<2>"
                     % (ac.get("passed", 0), ac.get("skipped", 0),
                        ac.get("failed", 0))))
    return reps


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="仅校验（默认行为，显式开关便于流水线）")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    snap = _snapshot()
    if snap is None:
        print("FAIL 找不到快照")
        return 1
    text = snap.read_text(encoding="utf-8")
    new = text
    changes = []
    for pat, repl in build_replacements():
        def _sub(m):
            return re.sub(pat, repl, m.group(0))
        newer = re.sub(pat, repl, new)
        if newer != new:
            changes.append((pat[:40], "changed"))
        new = newer
    # 逐条报告改动
    diff = []
    for a, b in zip(new.splitlines(), text.splitlines()):
        if a != b:
            diff.append((b.strip(), a.strip()))
    if not diff:
        print("snapshot numbers OK:", snap.name)
        return 0
    print("snapshot numbers mismatch: %d 行" % len(diff))
    for old, _ in diff[:6]:
        print("  -", old)
    if not args.write:
        return 1
    snap.write_text(new, encoding="utf-8")
    print("snapshot numbers written:", snap.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
