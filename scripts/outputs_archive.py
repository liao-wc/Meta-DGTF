# -*- coding: utf-8 -*-
"""outputs 保留策略：重复问题只保留最新 N 份，其余移动到归档目录（不删除）。

Round 133：产物 360 packs/321MB，65+ 问题重复（最多 46 份），无保留策略。
策略：按问题指纹分组，保留最新 `--keep`（默认 2）份；其余（含 .md/.run.log）
移动到 `outputs/_archive_20261027/`，可用 `--restore` 原样移回。
用法：
  python scripts/outputs_archive.py                # dry-run
  python scripts/outputs_archive.py --apply
  python scripts/outputs_archive.py --restore
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))
sys.path.insert(0, str(ROOT))
ARCHIVE = ROOT / "outputs" / "_archive_20261027"
COMPANIONS = (".md", ".run.log")


def _fingerprint(question: str) -> str:
    try:
        from dgtf_v2.provenance import question_fingerprint
        return question_fingerprint(question)
    except Exception:  # noqa: BLE001
        import hashlib
        import re
        q = re.sub(r"\s+", "", str(question or "")).lower()
        return hashlib.sha256(q.encode("utf-8")).hexdigest()[:16]


def _sidecar(p: Path, ext: str) -> Path:
    return p.with_name(p.name[:-len(".packed.json")] + ext)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--keep", type=int, default=2)
    ap.add_argument("--fact-keep", type=int, default=-1,
                    help="fact 包每问题保留最新 N 份；-1=全保留（默认，保护重放基线）")
    args = ap.parse_args()
    if args.restore:
        moved = 0
        for f in sorted(ARCHIVE.glob("*")):
            if f.is_file():
                shutil.move(str(f), str(ROOT / "outputs" / f.name))
                moved += 1
        print("restored:", moved)
        return 0

    packs = sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json")),
                   key=os.path.getmtime, reverse=True)  # newest first
    groups = defaultdict(list)
    for f in packs:
        try:
            import json
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        q = d.get("quality") or {}
        asum = q.get("answer_summary") or d.get("answer_summary") or {}
        qtype = str(asum.get("question_type") or "unknown")
        groups[_fingerprint(d.get("question") or "")].append((Path(f), qtype))
    to_move = []
    for fp, items in groups.items():
        # 保留策略：fact 包全部保留（离线重放/质量护栏基线依赖）；
        # 非 fact 包每问题只留最新 keep 份，其余归档。
        nonfact = [p for p, qt in items if qt != "fact"]
        facts = [p for p, qt in items if qt == "fact"]
        for p in nonfact[args.keep:]:
            to_move.append(p)
        if args.fact_keep >= 0:
            for p in facts[args.fact_keep:]:
                to_move.append(p)
    print("packs=%d groups=%d keep=%d to_archive=%d"
          % (len(packs), len(groups), args.keep, len(to_move)))
    for p in to_move[:8]:
        print("  ", p.name)
    if not args.apply:
        print("DRY-RUN（--apply 移动；--restore 还原）")
        return 0
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    moved = 0
    for p in to_move:
        for src in [p] + [_sidecar(p, ext) for ext in COMPANIONS]:
            if src.exists():
                shutil.move(str(src), str(ARCHIVE / src.name))
                moved += 1
    print("archived files:", moved, "->", ARCHIVE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
