# -*- coding: utf-8 -*-
"""A/B 结果摘要（Round 133）：按问题聚合最佳结果，区分主线/探索基线。

输出 docs/ab_summary_20261027.md + .json；供"项目质量口径"使用（不新增真跑）。
"""
from __future__ import annotations

import glob
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "ab_results.jsonl"
OUT_MD = ROOT / "docs" / "ab_summary_20261027.md"
OUT_JSON = ROOT / "docs" / "ab_summary_20261027.json"


def _norm(q: str) -> str:
    return re.sub(r"[\s？?。.!！,，、;；:：]+", "", str(q or ""))


def main() -> int:
    rows = []
    for ln in SRC.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:  # noqa: BLE001
            continue
    groups = defaultdict(list)
    for r in rows:
        groups[_norm(r.get("question") or "")].append(r)
    summary = []
    for qn, rs in groups.items():
        scale = Counter(str(r.get("quality_band") or "unknown") for r in rs)
        main = [r for r in rs if str(r.get("quality_scale") or "mainline") == "mainline"]
        pool = main or rs
        best = max(pool, key=lambda r: float(r.get("quality") or 0))
        summary.append({
            "question": str(best.get("question") or qn)[:120],
            "n_rows": len(rs),
            "scale": dict(scale),
            "best_quality": float(best.get("quality") or 0),
            "best_tag": best.get("tag"),
            "best_ts": best.get("ts"),
            "best_verified": str(best.get("answer_quality")) == "verified",
            "best_cost_window": best.get("cost_window_cny"),
            "tags": sorted({str(r.get("tag")) for r in rs})[:6],
        })
    summary.sort(key=lambda x: -x["best_quality"])
    doc = {
        "rows": len(rows),
        "questions": len(summary),
        "mainline_rows": sum(1 for r in rows
                             if str(r.get("quality_scale") or "mainline") == "mainline"),
        "low_quality_rows": sum(1 for r in rows
                                if str(r.get("quality_band")) == "low"),
        "band_counts": dict(Counter(str(r.get("quality_band") or "unknown")
                                    for r in rows)),
        "verified_rows": sum(1 for r in rows
                             if str(r.get("answer_quality")) == "verified"),
        "top10": summary[:10],
        "bottom10": summary[-10:],
        "all": summary,
        "note": ("quality_band=low 为 quality<0.5 的负结果/失败基线；"
                 "mainline 为可对照主线。cost_window 为窗口差，不可归因。"),
    }
    OUT_JSON.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# A/B 结果摘要（2026-10-27）", "",
             "- 总行数：%d；问题数：%d；mainline=%d / low_quality=%d；band=%s；verified=%d"
             % (doc["rows"], doc["questions"], doc["mainline_rows"],
                doc["low_quality_rows"], json.dumps(doc["band_counts"],
                                                    ensure_ascii=False),
                doc["verified_rows"]),
             "- 口径：`quality_band=low/mid/high` 按结果分带（low=负结果/失败基线，"
             "不参与主线对照）；`cost_window_cny` 为窗口差、不可归因。", "",
             "## 最佳结果 Top10", "",
             "| 问题 | best | tag | verified | 行数 | 口径 |",
             "|---|---|---|---|---|---|"]
    for s in summary[:10]:
        lines.append("| %s | %.4f | %s | %s | %d | %s |"
                     % (s["question"][:40], s["best_quality"], s["best_tag"],
                        "✓" if s["best_verified"] else "✗", s["n_rows"],
                        ",".join("%s:%d" % (k, v) for k, v in s["scale"].items())))
    lines += ["", "## 底部 Bottom10", "",
              "| 问题 | best | tag | verified | 行数 |",
              "|---|---|---|---|---|"]
    for s in summary[-10:]:
        lines.append("| %s | %.4f | %s | %s | %d |"
                     % (s["question"][:40], s["best_quality"], s["best_tag"],
                        "✓" if s["best_verified"] else "✗", s["n_rows"]))
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("rows=%d questions=%d mainline=%d low_quality=%d verified=%d"
          % (doc["rows"], doc["questions"], doc["mainline_rows"],
             doc["low_quality_rows"], doc["verified_rows"]))
    print("->", OUT_MD, "|", OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
