#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成型运行态清理：默认 dry-run，--apply 才删除。

只清 _audit_tmp / smoke_outputs / __pycache__ 与 7 天前启动器日志；
outputs、dgtf_memory、模型、密钥永不触碰。
"""
from __future__ import annotations
import argparse
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAFE_DIRS = ("_audit_tmp", "smoke_outputs")
LOG_GLOBS = ("_app_out_*.log*", "_app_err_*.log*")


def _olds(path: Path, cutoff: float):
    for p in path.iterdir():
        try:
            if p.stat().st_mtime < cutoff:
                yield p
        except OSError:
            continue


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    cutoff = time.time() - max(1, a.days) * 86400
    removed = 0
    for name in SAFE_DIRS:
        p = ROOT / name
        if not p.is_dir():
            continue
        for child in _olds(p, cutoff):
            print(("DELETE" if a.apply else "DRYRUN"), child)
            if a.apply:
                try:
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=True)
                    else:
                        child.unlink(missing_ok=True)
                    removed += 1
                except OSError:
                    pass
    for pat in LOG_GLOBS:
        for child in ROOT.glob(pat):
            try:
                if child.stat().st_mtime >= cutoff or not child.is_file():
                    continue
            except OSError:
                continue
            print(("DELETE" if a.apply else "DRYRUN"), child.name)
            if a.apply:
                try:
                    child.unlink(missing_ok=True)
                    removed += 1
                except OSError:
                    pass
    # __pycache__ 不按时间，全部是重建缓存
    for child in ROOT.rglob("__pycache__"):
        if not child.is_dir():
            continue
        print(("DELETE" if a.apply else "DRYRUN"), child)
        if a.apply:
            try:
                shutil.rmtree(child, ignore_errors=True)
                removed += 1
            except OSError:
                pass
    print("removed=%d applied=%s days=%d" % (removed, a.apply, a.days))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
