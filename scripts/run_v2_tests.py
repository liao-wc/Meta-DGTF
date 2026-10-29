#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2 全量测试统一运行器（本地 / CI 共用）。

用法：
    python scripts/run_v2_tests.py                     # 跑全部 35 个 V2 测试文件
    python scripts/run_v2_tests.py --timeout 120       # 单文件超时（秒）
    python scripts/run_v2_tests.py --require-replay    # 本地严格模式：回放数据缺失即失败

规则：
- 发现 dgtf_engine/dgtf_v2/tests.py 与全部 tests_*.py，逐文件起独立子进程；
- 子进程工作目录 = 仓库根，PYTHONPATH 含 dgtf_engine，UTF-8 输出；
- 通过 = 退出码 0 且输出行首没有 FAIL/✗、没有 Traceback、汇总 FAIL 数为 0；
- 行首「· SKIP …」计入 skip，不算失败（干净 checkout 无 outputs/ 回放数据时，
  3 个真实 packed 回放检查会显式 SKIP，而不是假绿 —— 见 tests_all / tests_core / tests_l0）；
- --require-replay 或 DGTF_REQUIRE_REPLAY=1：回放数据缺失按失败处理（本地严格模式）。

退出码：0 = 全部通过；1 = 有失败；2 = 未发现测试 / 用法错误。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# [V2.2.60] 重资源判据串行锁（验收/V2/App selftest 与手动测试并发时互斥）
try:
    import sys as _s
    _s.path.insert(0, str(ROOT / "scripts" / "local_model"))
    from _serial_lock import acquire_serial_lock as _asl
    _LOCK = _asl("local_chain")
except Exception:  # noqa: BLE001
    _LOCK = -1
V2_DIR = ROOT / "dgtf_engine" / "dgtf_v2"

# 行首 FAIL/✗ 才算失败；"PASS 41 / FAIL 0" 这种汇总行不会命中。
FAIL_LINE_RE = re.compile(r"^\s*(?:FAIL|✗)\b")
SKIP_LINE_RE = re.compile(r"^\s*(?:·\s*)?SKIP\b")
SUMMARY_RE = re.compile(r"PASS\s+(\d+)\s*/\s*FAIL\s+(\d+)")
TRACEBACK = "Traceback (most recent call last):"


def _discover():
    files = sorted(V2_DIR.glob("tests_*.py"))
    main = V2_DIR / "tests.py"
    if main.is_file():
        files.insert(0, main)
    return files


def _child_env(require_replay: bool) -> dict:
    env = dict(os.environ)
    core = str(ROOT / "dgtf_engine")
    env["PYTHONPATH"] = core + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if require_replay:
        env["DGTF_REQUIRE_REPLAY"] = "1"
    return env


def _classify(rc: int, out: str):
    """返回 (ok, checks, skips, fail_lines, reason)。"""
    fail_lines = [ln.strip() for ln in out.splitlines() if FAIL_LINE_RE.match(ln)]
    skips = sum(1 for ln in out.splitlines() if SKIP_LINE_RE.match(ln))
    checks = len([ln for ln in out.splitlines() if ln.startswith(("PASS", "✓", "OK"))])
    summary = None
    for ln in out.splitlines():
        m = SUMMARY_RE.search(ln)
        if m:
            summary = (int(m.group(1)), int(m.group(2)))
    if summary:
        checks = summary[0]
    reason = ""
    if rc != 0:
        reason = "exit=%d" % rc
    elif TRACEBACK in out:
        reason = "traceback"
    elif summary and summary[1] > 0:
        reason = "summary FAIL=%d" % summary[1]
    elif fail_lines:
        reason = "FAIL lines: " + "; ".join(fail_lines[:3])
    return (not reason, checks, skips, fail_lines, reason)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="V2 全量测试统一运行器")
    ap.add_argument("--timeout", type=float, default=300.0, help="单文件超时秒数（默认 300）")
    ap.add_argument("--require-replay", action="store_true",
                    help="回放数据缺失按失败处理（等价 DGTF_REQUIRE_REPLAY=1）")
    args = ap.parse_args(argv)

    require_replay = bool(args.require_replay or os.getenv("DGTF_REQUIRE_REPLAY") == "1")
    files = _discover()
    if len(files) < 2:
        print("FAIL 未发现 V2 测试（%s）" % V2_DIR, file=sys.stderr)
        return 2

    env = _child_env(require_replay)
    bad = []
    total_checks = total_skips = 0
    t_all = time.time()
    for f in files:
        t0 = time.time()
        try:
            cp = subprocess.run(
                [sys.executable, str(f)], cwd=str(ROOT), env=env,
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=args.timeout)
            out = (cp.stdout or "") + "\n" + (cp.stderr or "")
            ok, checks, skips, fail_lines, reason = _classify(cp.returncode, out)
        except subprocess.TimeoutExpired:
            ok, checks, skips, fail_lines, reason = False, 0, 0, [], "timeout %.0fs" % args.timeout
            out = ""
        total_checks += checks
        total_skips += skips
        tag = "PASS" if ok else "FAIL"
        extra = (" checks=%d" % checks) if checks else ""
        skip_txt = (" skip=%d" % skips) if skips else ""
        print("%s  %-32s%s%s  (%.1fs)" % (tag, f.name, extra, skip_txt, time.time() - t0), flush=True)
        if not ok:
            bad.append((f.name, reason, out))

    elapsed = time.time() - t_all
    print("\nTOTAL %d · PASS %d · FAIL %d · SKIP %d · checks %d · %.1fs"
          % (len(files), len(files) - len(bad), len(bad), total_skips, total_checks, elapsed))
    for name, reason, out in bad:
        print("\n===== FAIL %s（%s） =====" % (name, reason))
        tail = "\n".join(out.strip().splitlines()[-25:])
        print(tail)
    # ★ [V2.2.18] 证据出口：release_process_check 校验新鲜度 + README 数字一致性
    try:
        _ev = {
            "schema": "dgtf.v2_tests.v1",
            "ts": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "files": len(files),
            "passed": len(files) - len(bad),
            "failed": len(bad),
            "skips": total_skips,
            "checks": total_checks,
            "elapsed_sec": round(elapsed, 1),
            "failed_names": [b[0] for b in bad],
            "ok": not bad,
        }
        _p = ROOT / "docs" / "v2_tests_latest.json"
        _p.parent.mkdir(parents=True, exist_ok=True)
        _p.write_text(json.dumps(_ev, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    if bad:
        print("\nV2 TESTS FAILED: %d / %d" % (len(bad), len(files)))
        return 1
    print("V2 TESTS PASS: %d / %d" % (len(files), len(files)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
