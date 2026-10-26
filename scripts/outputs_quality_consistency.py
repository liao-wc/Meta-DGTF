# -*- coding: utf-8 -*-
"""产物质量一致性护栏（Round 129，零成本，离线）。

背景：历史 packs 存在 7 条自相矛盾（verified+!ready / unverified+ready）。
策略：**历史包不改写**（保留证据），但**新包**（日期前缀 >= CUTOFF）不允许矛盾；
     同时检查新包是否带 `flags_normalized`（Round 129 schema）。
用法：
  python scripts/outputs_quality_consistency.py            # 护栏模式（新包矛盾则 exit 1）
  python scripts/outputs_quality_consistency.py --out x.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUTOFF = "20261027"  # 新引擎产物起始日期前缀


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "_audit_tmp" / "outputs_consistency.json"))
    args = ap.parse_args()
    packs = sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json")))
    legacy_bad, new_bad, no_norm = [], [], []
    new_total = 0
    for f in packs:
        stem = os.path.basename(f)
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        q = d.get("quality") or {}
        aq = q.get("answer_quality")
        ready = q.get("answer_ready")
        is_new = stem[:8] >= CUTOFF
        if is_new:
            new_total += 1
            if (aq == "verified" and ready is False) or (aq == "unverified" and ready is True):
                new_bad.append(stem)
            if "flags_normalized" not in q:
                no_norm.append(stem)
        elif (aq == "verified" and ready is False) or (aq == "unverified" and ready is True):
            legacy_bad.append(stem)
    doc = {
        "packs": len(packs), "cutoff": CUTOFF, "new_packs": new_total,
        "legacy_contradictions": legacy_bad,
        "new_contradictions": new_bad,
        "new_missing_flags_normalized": no_norm,
        "pass": not new_bad and not no_norm,
        "note": "历史包保留不改写；新包必须无矛盾且带 flags_normalized（Round 129）。",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("packs=%d | new=%d | legacy contradictions=%d | new contradictions=%d | missing flags_normalized=%d"
          % (len(packs), new_total, len(legacy_bad), len(new_bad), len(no_norm)))
    if legacy_bad:
        print("WARN legacy（仅记录，不改写）：", legacy_bad[:5])
    print("CONSISTENCY %s" % ("PASS" if doc["pass"] else "FAIL"))
    return 0 if doc["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
