#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 F.4] 交付物清单核对（`_v1221_taskbook.md` 的 23 项 + 本轮实增项）。

用法：python _check_v1221_deliverables.py
期望：`缺失: []`，退出码 0。
"""
from __future__ import annotations

import sys
from pathlib import Path

REQ = [
    # ---- 任务书 F.4 列的 23 项 ----
    "元DGTF-V1.22.1.py",
    "smoke_test.py",
    "_v122_verify.py",
    "_probe_v1221_p1.py", "_probe_v1221_p2.py", "_probe_v1221_p3.py",
    "_probe_v1221_p4.py", "_probe_v1221_p5.py", "_probe_v1221_p6.py",
    "_negctl_v1221_p3.py", "_negctl_v1221_p3.json",
    "_run_v1221_p4.py", "_v1221_p4_consistency.json",
    "docs/机制负对照-v1221.md",
    "docs/不做什么-v1221.md",
    "v1221_p1_报告.md", "v1221_p2_报告.md", "v1221_p3_报告.md",
    "v1221_p4_报告.md", "v1221_p5_报告.md", "v1221_p6_报告.md",
    "v1221_报告.md",
    "bench/reports/v1221_full.md",
]

# ---- 本轮实增（任务书 F.4 未列，但属 P2b 与第二/三档的交付物）----
EXTRA = [
    "_v1221_p2b_taskbook.md",
    "v1221_p2b_报告.md",
    "_probe_v1221_p2b.py",
    "_probe_v1221_p2b_before.txt", "_probe_v1221_p2b_after.txt",
    "_run_v1221_p2b.py",
    "_run_v1221_p56.py",
    "_v1221_p4_agg.py",
    "_v122_ast_registry.json",
    "_test_anchors.json",
]


def main() -> int:
    req = REQ + EXTRA
    missing = [r for r in req if not Path(r).exists()]
    print("必查项 " + str(len(req)) + " 项（任务书 F.4 的 " + str(len(REQ))
          + " 项 + 本轮实增 " + str(len(EXTRA)) + " 项）")
    print("缺失: " + str(missing))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
