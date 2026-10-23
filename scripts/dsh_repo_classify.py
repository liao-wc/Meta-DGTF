#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DSH repository classifier / guard.

Logical categories: app, engine, local_model, docs, ops, runtime, archive, legacy.
Physical paths are not moved here; this keeps imports stable while giving DSH
and CI a deterministic ownership map.
"""
from __future__ import annotations
import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".github" / "repo_manifest.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def git_files() -> list[str]:
    raw = subprocess.check_output(
        ["git", "ls-files"], cwd=str(ROOT), text=True, encoding="utf-8", errors="replace")
    return [x.strip() for x in raw.splitlines() if x.strip()]


def matches(path: str, pat: str) -> bool:
    p = path.replace("\\", "/")
    low = p.lower()
    q = str(pat or "").replace("\\", "/")
    if not q:
        return False
    if q.endswith("/"):
        return p.startswith(q) or ("/" + q) in p
    if any(ch in q for ch in "*?["):
        return fnmatch.fnmatch(low, q.lower()) or fnmatch.fnmatch(low.split("/")[-1], q.lower())
    return p.startswith(q) or q.lower() in low


def classify(files: list[str], man: dict) -> dict[str, list[str]]:
    cats = man.get("categories") or {}
    order = man.get("order") or list(cats)
    out: dict[str, list[str]] = {c: [] for c in order}
    for f in files:
        hit = None
        for c in order:
            for pat in cats.get(c) or []:
                if matches(f, pat):
                    hit = c
                    break
            if hit:
                break
        out.setdefault(hit or "other", []).append(f)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["classify", "check", "status"], nargs="?", default="classify")
    ap.add_argument("--strict", action="store_true", help="runtime/archive tracked -> exit 1")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    man = load_manifest()
    files = git_files()
    by = classify(files, man)
    counts = {k: len(v) for k, v in by.items()}
    if a.command == "check":
        bad = {k: v for k, v in by.items() if k in ("runtime", "archive") and v}
        print("repo check: files=%d categories=%s" % (len(files), json.dumps(counts, ensure_ascii=False)))
        for k, v in bad.items():
            print("WARN tracked %s: %d (e.g. %s)" % (k, len(v), v[0]))
        if a.strict and bad:
            return 1
        print("REPO CATEGORIES OK")
        return 0
    if a.command == "status":
        print(json.dumps(counts, ensure_ascii=False, indent=1))
        return 0
    # classify + write report
    report_dir = ROOT / "reports"
    report_dir.mkdir(exist_ok=True)
    payload = {"total": len(files), "counts": counts,
               "categories": {k: v[:2000] for k, v in by.items()}}
    (report_dir / "repo_classification.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# 仓库分类报告", "", "总计：%d 个 tracked 文件" % len(files), "",
             "| 分类 | 文件数 | 示例 |", "|---|---:|---|"]
    for k in man.get("order") or counts:
        v = by.get(k) or []
        lines.append("| %s | %d | %s |" % (k, len(v), (v[0] if v else "")))
    lines += ["", "> 物理路径未移动；分类用于 DSH 管理与 CI 守卫。"]
    (report_dir / "repo_classification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if a.json:
        print(json.dumps({"total": len(files), "counts": counts}, ensure_ascii=False))
    else:
        print("repo classified: total=%d" % len(files))
        for k in man.get("order") or counts:
            print("  %-10s %d" % (k, counts.get(k, 0)))
        print("report: reports/repo_classification.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
