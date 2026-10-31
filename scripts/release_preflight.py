#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布预同步/预检（V2.2.104）。

把 runbook 的「预同步」步骤固化为一键：
1. sync_readme_numbers --write / --check
2. sync_snapshot_numbers --write / --check
3. release_process_check --pre-tag（快速门 + 发布门自检）
4. git 工作区提醒（只警告，不阻塞）

用法：
  python scripts/release_preflight.py            # 同步 + 预检
  python scripts/release_preflight.py --check    # 只校验，不写
退出码：0 = 全部通过；1 = 有硬失败。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def _j(name: str) -> dict:
    p = ROOT / "docs" / name
    try:
        import json
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _evidence_bad() -> list:
    """返回失败证据清单；为空 = 健康。

    ★ [V2.2.105] V2.2.104 曾把一次失败的 fast_gate 证据（26/27）同步进 README；
    预同步前必须先确认证据本身是 PASS 状态，否则拒绝写。
    """
    bad = []
    fg = _j("fast_gate_latest.json")
    if fg and (fg.get("failed") or fg.get("passed", 0) != fg.get("total", 0)):
        bad.append("fast_gate %s/%s" % (fg.get("passed"), fg.get("total")))
    v2 = _j("v2_tests_latest.json")
    if v2 and v2.get("fail"):
        bad.append("v2_tests fail=%s" % v2.get("fail"))
    st = _j("app_selftest_latest.json")
    if st and (st.get("fail") or not st.get("pass")):
        bad.append("app_selftest %s/%s" % (st.get("pass"), st.get("fail")))
    ac = _j("acceptance_latest.json")
    if ac and ac.get("failed"):
        bad.append("acceptance fail=%s" % ac.get("failed"))
    return bad


def _run(args: list) -> int:
    r = subprocess.run([PY] + args, cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    print(("PASS " if r.returncode == 0 else "FAIL ") + " ".join(args))
    if r.returncode != 0:
        for ln in tail[-8:]:
            print("   ", ln)
    return r.returncode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="只校验（不写 README/快照数字）")
    ap.add_argument("--write", action="store_true",
                    help="同步写回（默认行为；显式开关便于流水线）")
    args = ap.parse_args(argv)
    bad = _evidence_bad()
    print(("PASS " if not bad else "FAIL ") + "evidence_sanity"
          + ("" if not bad else "：" + "；".join(bad)))
    if bad:
        print("\nRELEASE PREFLIGHT: FAIL（证据未全 PASS，拒绝同步/预检）")
        return 1
    mode = "--check" if args.check else "--write"
    bad = 0
    # 1) 同步（写模式先 sync 再 check）
    bad += _run(["scripts/sync_readme_numbers.py", mode])
    bad += _run(["scripts/sync_snapshot_numbers.py", mode])
    if not args.check:
        bad += _run(["scripts/sync_readme_numbers.py", "--check"])
        bad += _run(["scripts/sync_snapshot_numbers.py", "--check"])
    # 2) 发布门预检（含状态快照含本版/证据新鲜度等）
    bad += _run(["scripts/release_process_check.py", "--pre-tag"])
    # 3) git 提醒
    r = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    dirty = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    if dirty:
        print("WARN 工作区非空（%d 项）——发布前应只剩证据类文件：" % len(dirty))
        for ln in dirty[:8]:
            print("   ", ln)
    print("\nRELEASE PREFLIGHT: %s" % ("PASS" if bad == 0 else "FAIL"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
