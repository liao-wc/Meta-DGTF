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
    legacy_trunc, legacy_nodisp = [], []
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
        asum = q.get("answer_summary") or d.get("answer_summary") or {}
        card = (d.get("decision_trace") or {}).get("fact_card") or {}
        truncated = "体力耗尽" in str(asum.get("stop_reason") or "")
        _reason = str(q.get("answer_ready_reason")
                      or q.get("repair_note") or "").strip()
        contradict = ((aq == "unverified" and ready is True)
                      or (aq == "verified" and ready is False
                          and not _reason))
        no_display = (str(asum.get("question_type") or "") == "fact"
                      and not str(card.get("answer_display") or "").strip())
        if is_new:
            new_total += 1
            if contradict:
                new_bad.append(stem)
            if "flags_normalized" not in q:
                no_norm.append(stem)
            if truncated and ready is True:
                new_bad.append(stem + "::truncated_ready")
            if aq == "verified" and no_display and ready is True:
                new_bad.append(stem + "::verified_no_display")
            if "provenance" not in d or "question_hash" not in d:
                new_bad.append(stem + "::missing_provenance")
        else:
            if contradict:
                legacy_bad.append(stem)
            if truncated and ready is True:
                legacy_trunc.append(stem)
            if aq == "verified" and no_display and ready is True:
                legacy_nodisp.append(stem)
    doc = {
        "packs": len(packs), "cutoff": CUTOFF, "new_packs": new_total,
        "legacy_contradictions": legacy_bad,
        "legacy_truncated_ready": legacy_trunc,
        "legacy_verified_no_display": legacy_nodisp,
        "new_contradictions": new_bad,
        "new_missing_flags_normalized": no_norm,
        "pass": not new_bad and not no_norm,
        "note": "历史包保留不改写；新包必须无矛盾且带 flags_normalized（Round 129）。",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("packs=%d | new=%d | legacy contradictions=%d | new contradictions=%d"
          " | missing flags_normalized=%d | legacy truncated_ready=%d | legacy verified_no_display=%d"
          % (len(packs), new_total, len(legacy_bad), len(new_bad), len(no_norm),
             len(legacy_trunc), len(legacy_nodisp)))
    if legacy_bad:
        print("WARN legacy（仅记录，不改写）：", legacy_bad[:5])
    print("CONSISTENCY %s" % ("PASS" if doc["pass"] else "FAIL"))
    return 0 if doc["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
