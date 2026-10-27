# -*- coding: utf-8 -*-
"""最终验收串跑器（Round 73）：一条命令跑完所有零成本验收与护栏。

用法：
  python scripts/final_acceptance.py            # 不含本地服务检查（服务可能停机训练）
  python scripts/final_acceptance.py --with-service
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STEPS = [
    ("fast_gate", ["fast_gate.py"]),
    ("v2_tests", ["scripts/run_v2_tests.py"]),
    ("replay_guard", ["scripts/lead_offline_fact_replay.py"]),
    ("process_gate_guard", ["scripts/lead_process_gate_audit.py"]),
    ("app_plan_matrix", ["scripts/app_plan_matrix_check.py"]),
    ("app_dual_judge_guard", ["scripts/app_dual_judge_guard_check.py"]),
    ("compare_eval_selftest", ["scripts/local_model/test_compare_eval.py"]),
    ("train_guard", ["scripts/local_model/test_train_guard.py"]),
    ("app_cache_bypass", ["scripts/local_model/test_app_cache_bypass.py"]),
    ("judge_fastfail", ["scripts/local_model/test_judge_fastfail.py"]),
    ("generate_batch", ["scripts/local_model/test_generate_batch.py"]),
    ("probe_cover_wide", ["scripts/local_model/test_probe_cover_wide.py"]),
    ("ab_repeat_guard", ["scripts/local_model/test_ab_repeat_guard.py"]),
    ("outputs_consistency", ["scripts/outputs_quality_consistency.py"]),
    ("fx_anchor_replay", ["scripts/fx_anchor_replay_check.py"]),
    ("scenario_matrix_guard", ["scripts/update_scenario_matrix.py"]),
]


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(ROOT / "dgtf_engine") + os.pathsep + str(ROOT)
    return env


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-service", action="store_true")
    args = ap.parse_args()
    steps = list(STEPS)
    if args.with_service:
        steps.append(("local_service", ["scripts/check_local_service.py"]))
    py = sys.executable
    results = []
    for name, argv in steps:
        t0 = time.time()
        r = subprocess.run([py] + [str(ROOT / a) for a in argv],
                           cwd=str(ROOT), env=_env(),
                           capture_output=True, text=True, timeout=1800)
        ok = r.returncode == 0
        tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
        results.append((name, ok, round(time.time() - t0, 1), tail[0][:80]))
        print(("PASS " if ok else "FAIL ") + "%-24s %6.1fs  %s"
              % (name, results[-1][2], results[-1][3]))
    bad = [n for n, ok, _, _ in results if not ok]
    print("\nFINAL ACCEPTANCE: %d/%d PASS" % (len(results) - len(bad), len(results)))
    if bad:
        print("FAILED:", bad)
        return 1
    print("ALL GUARDS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
