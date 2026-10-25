# -*- coding: utf-8 -*-
"""离线审计：用已存 *.packed.json 验证机制覆盖与剩余问题（零 API 成本）。

Round 12 用途：预算受限，不再跑新任务，改为审计今天所有真实跑次的 packed 产物：
  · 事实题：fact_card 状态/缺口/冲突类型分布、官方源优先与时效优先覆盖情况、
    过程门（standard_all / meta_closure）阻断原因；
  · 非事实题：answer_quality/ready、过程门；
  · 阶段 token 占比（self_check/dual_judge 等）——压缩/优化空间的可量化输入；
  · 答案展示：answer vs answer_display 差异（数值紧凑是否生效）。
输出：docs/offline_pack_audit_20261025.json + 终端摘要。
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))

from dgtf_v2.pareto_flow import extract_flow_metrics  # noqa: E402

OUT = ROOT / "docs" / "offline_pack_audit_20261025.json"


def _aux(c: dict) -> bool:
    try:
        from dgtf_v2.fact_flow import _is_aux_date_conflict
        return bool(_is_aux_date_conflict(c))
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    rows = []
    for f in sorted(glob.glob(str(ROOT / "outputs" / "*.packed.json")),
                    key=os.path.getmtime, reverse=True):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8",
                                             errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        try:
            m = extract_flow_metrics(d)
        except Exception:  # noqa: BLE001
            m = {}
        dt = d.get("decision_trace") or {}
        q = d.get("quality") or {}
        card = dt.get("fact_card") or {}
        asum = q.get("answer_summary") or {}
        pl = d.get("process_ledger") or {}
        views = d.get("views") or {}
        mc = (views.get("all") or {}).get("meta_closure") or {}
        stage = d.get("api_usage") or {}
        confs = card.get("conflicts") or []
        rows.append({
            "file": os.path.basename(f),
            "mtime": os.path.getmtime(f),
            "question": str(d.get("question") or "")[:40],
            "question_type": dt.get("question_type"),
            "quality": m.get("quality"),
            "answer_quality": m.get("answer_quality"),
            "answer_ready": m.get("answer_ready"),
            "tokens": m.get("tokens"),
            "calls": m.get("calls"),
            "route": d.get("route"),
            "web": bool((stage or {}).get("web_enabled")),
            "card_status": card.get("status"),
            "card_gaps": list(card.get("gaps") or []),
            "conflicts": len(confs),
            "conflicts_aux_date": sum(1 for c in confs if _aux(c)),
            "resolved_conflicts": len(card.get("resolved_conflicts") or []),
            "process_standard_all": pl.get("standard_all"),
            "meta_clean": mc.get("clean") if mc else None,
            "meta_unsettled": mc.get("unsettled") if mc else None,
            "answer": str(card.get("answer") or "")[:120],
            "answer_display": str(card.get("answer_display")
                                  or asum.get("answer") or "")[:120],
            "layers_standard": (q.get("depth") or {}).get("layers_standard"),
        })
    if not rows:
        print("无 packed 产物可审计")
        return 1
    facts = [r for r in rows if r["question_type"] == "fact"]
    ck = [r for r in rows if r["question_type"] != "fact"]
    summary = {
        "n_packs": len(rows),
        "n_fact": len(facts),
        "n_nonfact": len(ck),
        "aq": dict(Counter(str(r["answer_quality"]) for r in rows)),
        "ready": dict(Counter(str(r["answer_ready"]) for r in rows)),
        "fact_card_status": dict(Counter(str(r["card_status"]) for r in facts)),
        "fact_gaps_top": dict(Counter(
            g for r in facts for g in r["card_gaps"]).most_common(15)),
        "fact_conflicts": {"runs_with_conflict":
                           sum(1 for r in facts if r["conflicts"]),
                           "aux_date_conflicts":
                           sum(r["conflicts_aux_date"] for r in facts),
                           "resolved": sum(r["resolved_conflicts"]
                                           for r in facts)},
        "process_blockers": {
            "standard_all_false": sum(1 for r in rows
                                      if r["process_standard_all"] is False),
            "meta_clean_false": sum(1 for r in rows
                                    if r["meta_clean"] is False),
            "meta_unsettled_total": sum(int(r["meta_unsettled"] or 0)
                                        for r in rows),
        },
        "display_diff": sum(1 for r in rows
                            if r["answer"] and r["answer_display"]
                            and r["answer_display"] not in r["answer"]),
        "web_runs": sum(1 for r in rows if r["web"]),
        "route_short_runs": sum(1 for r in rows
                                if (r["route"] or []) and len(r["route"]) < 4),
        "fact_runs_route_short": sum(1 for r in facts
                                     if (r["route"] or [])
                                     and len(r["route"]) < 4),
        "rows": rows,
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("packs:", summary["n_packs"], "| fact:", summary["n_fact"])
    print("AQ:", summary["aq"], "| ready:", summary["ready"])
    print("fact card:", summary["fact_card_status"])
    print("fact gaps:", summary["fact_gaps_top"])
    print("fact conflicts:", summary["fact_conflicts"])
    print("process:", summary["process_blockers"])
    print("display_diff:", summary["display_diff"],
          "| web:", summary["web_runs"],
          "| short_route:", summary["route_short_runs"],
          "(fact:", summary["fact_runs_route_short"], ")")
    for r in facts:
        print(" · %-42s q=%s aq=%s ready=%s route=%s gaps=%s resolved=%d display=%s"
              % (r["file"][:42], r["quality"], r["answer_quality"],
                 r["answer_ready"], r["route"], r["card_gaps"],
                 r["resolved_conflicts"], r["answer_display"][:36]))
    print("→", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
