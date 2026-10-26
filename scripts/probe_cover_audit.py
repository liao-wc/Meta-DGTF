# -*- coding: utf-8 -*-
"""probe_no_target_covered 误报审计（Round 126，零成本）。

背景：引擎 `_COVERS_SIM_MIN=0.30` / `_similar(..., _QC_DUP_SIM)` / `_overlap_coef>=0.50`
三把尺子判「探针是否真的打到未触及项」；历史 29.3% packs 带该 flag。
本脚本离线复算：对有 covers 的 flagged packs，用**中文 2-gram Jaccard / 3-gram 包含**
两种更保守的匹配，统计「现有判据判负、但更宽判据会判正」的候选误报量。

注意：这里只做**误报候选统计**（宽判据），不直接改引擎；实现前需人工看样例。
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "probe_cover_audit_20261026.json"


def bigrams(s: str) -> set:
    s = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", str(s or ""))
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else set()


def jac(a: str, b: str) -> float:
    A, B = bigrams(a), bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def contains_3gram(probe: str, target: str) -> bool:
    p = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", str(probe or ""))
    t = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", str(target or ""))
    if len(t) < 3 or len(p) < 3:
        return False
    return any(t[i:i + 3] in p for i in range(len(t) - 2))


def main() -> int:
    files = glob.glob(str(ROOT / "outputs" / "*.packed.json"))
    total = flagged = 0
    rows = []
    for f in files:
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        q = d.get("quality") or {}
        flags = q.get("flags") or []
        if not flags:
            continue
        total += 1
        if "probe_no_target_covered" not in flags:
            continue
        flagged += 1
        v1 = (d.get("views") or {}).get("1") or {}
        probes = v1.get("probes") or []
        untouched = v1.get("untouched") or []
        targets = {}
        for i, u in enumerate(untouched):
            t = str((u or {}).get("desc", "")).strip()
            if not t:
                continue
            targets["T%d" % (i + 1)] = t
            if (u or {}).get("id"):
                targets[str(u["id"])] = t
            else:
                targets[str(i + 1)] = t
        covers_seen = False
        bad_ref = 0
        best_j = 0.0
        any_3g = False
        for p in probes:
            pq = str((p or {}).get("question", ""))
            covers = [str(c) for c in ((p or {}).get("covers") or []) if str(c).strip()]
            if covers:
                covers_seen = True
                for c in covers:
                    c2 = re.sub(r"^#", "", re.sub(r"^T(?=\d)", "", c))
                    if c not in targets and c2 not in targets:
                        bad_ref += 1
            for _k, tgt in targets.items():
                j = jac(pq, tgt)
                best_j = max(best_j, j)
                if contains_3gram(pq, tgt):
                    any_3g = True
        rows.append({
            "file": os.path.basename(f),
            "question": str(d.get("question") or "")[:40],
            "probes": len(probes), "untouched": len(untouched),
            "covers_seen": covers_seen, "bad_ref": bad_ref,
            "best_bigram_jaccard": round(best_j, 3),
            "any_target_3gram_in_probe": any_3g,
            "aq": q.get("answer_quality"),
        })
    near = [r for r in rows if r["covers_seen"] and not r["bad_ref"]]
    fn_candidates = [r for r in near
                     if r["best_bigram_jaccard"] >= 0.34 or r["any_target_3gram_in_probe"]]
    summary = {
        "packs_with_quality": total,
        "flagged": flagged,
        "flag_ratio": round(flagged / total, 4) if total else 0,
        "flagged_with_covers": sum(1 for r in rows if r["covers_seen"]),
        "flagged_with_bad_ref": sum(1 for r in rows if r["bad_ref"] > 0),
        "near_miss_no_bad_ref": len(near),
        "fn_candidates_wide": len(fn_candidates),
        "fn_ratio_of_near": round(len(fn_candidates) / max(1, len(near)), 4),
        "by_aq": dict(Counter(str(r["aq"]) for r in rows)),
        "samples_fn": fn_candidates[:5],
        "samples_flagged": rows[:5],
        "rows": rows,
        "note": ("宽判据（bigram jaccard≥0.34 或 target 3-gram 出现在 probe 中）只用于"
                 "误报候选统计；引擎判据修改前需人工复核样例并跑回归。"),
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("packs:", total, "| flagged:", flagged, "(%.1f%%)" % (100 * summary["flag_ratio"]))
    print("flagged_with_covers:", summary["flagged_with_covers"], "| bad_ref:",
          summary["flagged_with_bad_ref"], "| near_miss:",
          summary["near_miss_no_bad_ref"], "| fn_candidates:", summary["fn_candidates_wide"],
          "(%.1f%%)" % (100 * summary["fn_ratio_of_near"]))
    print("by aq:", summary["by_aq"])
    for r in summary["samples_fn"][:3]:
        print("  fn?", r["file"][:34], "| j=", r["best_bigram_jaccard"],
              "| 3g=", r["any_target_3gram_in_probe"], "|", r["question"][:26])
    print("->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
