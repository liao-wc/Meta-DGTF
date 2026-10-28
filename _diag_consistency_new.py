# -*- coding: utf-8 -*-
"""诊断：outputs_consistency 的 6 条「新矛盾」到底是真缺陷还是本地 e2e 跑次混入。

零成本、只读。打印每个新包的矛盾子类型 + 来源线索。
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent  # 本脚本在仓库根
CUTOFF = "20261027"

packs = sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json")))
rows = []
for f in packs:
    stem = os.path.basename(f)
    if stem[:8] < CUTOFF:
        continue
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        rows.append((stem, ["PARSE_FAIL:" + str(e)], {}))
        continue
    q = d.get("quality") or {}
    aq = q.get("answer_quality")
    ready = q.get("answer_ready")
    asum = q.get("answer_summary") or d.get("answer_summary") or {}
    card = (d.get("decision_trace") or {}).get("fact_card") or {}
    reason = str(q.get("answer_ready_reason") or q.get("repair_note") or "").strip()
    dt_ready = (d.get("decision_trace") or {}).get("answer_ready")
    bad = []
    if aq == "unverified" and ready is True:
        bad.append("unverified+ready")
    if aq == "verified" and ready is False and not reason:
        bad.append("verified+!ready(no reason)")
    if ready is not None and dt_ready is not None and bool(ready) != bool(dt_ready):
        bad.append("cross_position(ready=%s vs dt=%s)" % (ready, dt_ready))
    if "flags_normalized" not in q:
        bad.append("missing flags_normalized")
    if "体力耗尽" in str(asum.get("stop_reason") or "") and ready is True:
        bad.append("truncated+ready")
    if (aq == "verified"
            and str(asum.get("question_type") or "") == "fact"
            and not str(card.get("answer_display") or "").strip()
            and ready is True):
        bad.append("verified_no_display")
    if "provenance" not in d or "question_hash" not in d:
        bad.append("missing provenance/question_hash")
    # 来源线索
    cfg = d.get("_config") or {}
    clue = {
        "cfg_keys": sorted(cfg.keys())[:8],
        "prov": (d.get("provenance") or {}).get("engine_version") if isinstance(d.get("provenance"), dict) else None,
        "llm_by_stage": list((d.get("llm_by_stage") or {}).keys())[:6]
        if isinstance(d.get("llm_by_stage"), dict) else "list/none",
        "model_hint": str(d.get("model") or d.get("engine") or "")[:60],
        "q": str(d.get("question") or "")[:40],
    }
    if bad:
        rows.append((stem, bad, clue))

print("新包总数(>=CUTOFF) =", sum(1 for f in packs if os.path.basename(f)[:8] >= CUTOFF))
print("有问题的新包 =", len(rows))
for stem, bad, clue in rows:
    print("\n==", stem)
    print("   bad:", bad)
    for k, v in clue.items():
        print("   %-14s %s" % (k, v))
