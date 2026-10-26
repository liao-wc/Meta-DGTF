# -*- coding: utf-8 -*-
"""dual_judge local 可控合并器（Round 120，零成本）。

用法：
  python scripts/merge_dual_judge_local.py --check-only   # 临时 worktree 全量校验（推荐）
  python scripts/merge_dual_judge_local.py --commit       # 主引擎干净时应用+Gates+提交

约束：
  · --commit 要求主引擎工作树干净（git status 为空；--allow-dirty 可显式覆盖，不推荐）；
  · 校验使用 git worktree（HEAD 干净副本）顺序 apply 0001→0003 并跑 T1–T8；
  · 提交只包含引擎 + 本地判据脚本。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ENGINE_REL = "dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.3.py"
TEST_REL = "scripts/local_model/test_dual_judge_local.py"


def _run(cmd, cwd, env=None, timeout=1800):
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout,
                       env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _check_via_worktree(root: Path, patches: list) -> int:
    """在 HEAD 的临时 worktree 顺序 apply 补丁 + 跑 T1–T8。"""
    tmp = Path(tempfile.mkdtemp(prefix="dgtf_djlocal_"))
    wt = tmp / "wt"
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    code, txt = _run(["git", "worktree", "add", str(wt), "--detach", "HEAD"], root)
    if code != 0:
        print("FAIL: 无法创建临时 worktree：", txt[-200:])
        shutil.rmtree(tmp, ignore_errors=True)
        return 3
    try:
        for p in patches:
            code, txt = _run(["git", "apply", str(p)], wt)
            print("[check] apply", p.name, "=>", "OK" if code == 0 else "FAIL")
            if code != 0:
                print(txt[-300:])
                return 4
        test_src = root / "docs" / "patches" / "test_dual_judge_local.py"
        dst = wt / TEST_REL
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(test_src.read_text(encoding="utf-8"), encoding="utf-8")
        py = sys.executable
        code, txt = _run([py, str(dst)], wt, env=env)
        print("[check] T1–T8 =>", "PASS" if code == 0 else "FAIL", "|", txt.strip().splitlines()[-1:])
        return 0 if code == 0 else 5
    finally:
        _run(["git", "worktree", "remove", str(wt), "--force"], root)
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--check-only", action="store_true", default=False)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--allow-dirty", action="store_true")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    engine = root / ENGINE_REL
    patches = sorted((root / "docs" / "patches").glob("000*.patch"))
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    print("[1] root =", root)
    print("[2] engine exists:", engine.exists(), "| patches:", [p.name for p in patches])
    if not engine.exists() or not patches:
        print("FAIL: 缺少引擎或补丁")
        return 2

    code, txt = _run(["git", "status", "--short", "--", ENGINE_REL], root)
    dirty = bool(txt.strip())
    print("[3] engine dirty:", dirty, ("|" + txt.strip()[:120]) if dirty else "")
    if dirty and not args.allow_dirty and args.commit:
        print("FAIL: 主引擎工作树不干净，拒绝合并（--allow-dirty 可覆盖）")
        return 3

    if args.check_only or not args.commit:
        return _check_via_worktree(root, patches)

    for p in patches:
        code, txt = _run(["git", "apply", str(p)], root)
        if code != 0:
            print("FAIL apply:", p.name, txt[:200])
            return 5
        print("[5] applied", p.name)
    test_src = root / "docs" / "patches" / "test_dual_judge_local.py"
    dst = root / TEST_REL
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(test_src.read_text(encoding="utf-8"), encoding="utf-8")
    print("[6] copied", TEST_REL)
    py = sys.executable
    for name, cmd in (
            ("fast_gate", [py, str(root / "fast_gate.py")]),
            ("v2_tests", [py, str(root / "scripts" / "run_v2_tests.py")]),
            ("dual_local_test", [py, str(dst)])):
        code, txt = _run(cmd, root, env=env)
        print("[7]", name, "=>", "PASS" if code == 0 else "FAIL",
              "|", txt.strip().splitlines()[-1:])
        if code != 0:
            return 6
    _run(["git", "add", ENGINE_REL, TEST_REL], root)
    code, txt = _run(["git", "-c", "commit.gpgsign=false", "commit", "-m",
                      "feat(engine): merge dual_judge local（0001-0003，T1-T8 通过）"],
                     root)
    print("[8] commit =>", "OK" if code == 0 else txt.strip()[:200])
    return 0 if code == 0 else 7


if __name__ == "__main__":
    raise SystemExit(main())
