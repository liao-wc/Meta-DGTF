# -*- coding: utf-8 -*-
"""outputs 保留/膨胀审计（Round 129，零成本，只读不删）。

统计：文件数/体积、按日期分布、重复问题、缺 .md、旧引擎包占比；
输出 JSON 供清理决策（遵守「不删数据」红线：本脚本只报告，不移动/删除）。
"""
from __future__ import annotations

import glob
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_audit_tmp" / "outputs_retention.json"


def main() -> int:
    files = glob.glob(str(ROOT / "outputs" / "*"))
    packs = sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json")))
    by_date = Counter()
    stems = defaultdict(int)
    no_md = []
    total = 0
    for f in files:
        total += os.path.getsize(f)
    for f in packs:
        b = os.path.basename(f)
        by_date[b[:8]] += 1
        m = re.match(r"^\d{8}_\d{6}_(.+)\.packed\.json$", b)
        if m:
            stems[m.group(1)] += 1
        if not os.path.exists(f[:-len(".packed.json")] + ".md"):
            no_md.append(b)
    dup = {k: v for k, v in stems.items() if v > 1}
    doc = {
        "files": len(files), "packs": len(packs),
        "total_mb": round(total / 1048576, 1),
        "by_date": dict(sorted(by_date.items())),
        "duplicate_questions": len(dup),
        "max_copies": max(dup.values()) if dup else 0,
        "dup_top": sorted(dup.items(), key=lambda kv: -kv[1])[:5],
        "packs_without_md": len(no_md),
        "policy": "只读审计；清理需人工确认（红线：不删数据）",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("files=%d packs=%d MB=%.1f dup_questions=%d max_copies=%d no_md=%d"
          % (doc["files"], doc["packs"], doc["total_mb"],
             doc["duplicate_questions"], doc["max_copies"], doc["packs_without_md"]))
    print("->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
