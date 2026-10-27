# -*- coding: utf-8 -*-
"""tri_alpha 的 test-retest 代理分析（Round 142，零成本）。

背景：tri_alpha 是**跨视角一致性**（inter-perspective），不是重测信度；
历史 87.6% <0.667 被误当"质量不可靠"。本脚本用**同一问题的重复产物**
（含归档目录）估计重测一致性：verified/ready 一致率、coverage 的 ICC(1)、
flag 数波动；并对照 tri_alpha 的分布，明确两者语义。
输出 docs/tri_retest_20261027.json + 控制台摘要。
"""
from __future__ import annotations

import glob
import json
import os
import re
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "tri_retest_20261027.json"


def _norm_q(q: str) -> str:
    return re.sub(r"[\s？?。.!！,，、;；:：]+", "", str(q or ""))


def _icc1(groups):
    """单因素随机 ICC(1)（近似，支持不等组大小）。groups: list[list[float]]"""
    groups = [g for g in groups if len(g) >= 2]
    if len(groups) < 2:
        return None
    k = statistics.mean(len(g) for g in groups)
    msb = sum(len(g) * (statistics.mean(g) - statistics.mean(
        [x for gg in groups for x in gg])) ** 2 for g in groups) / (len(groups) - 1)
    msw = sum(sum((x - statistics.mean(g)) ** 2 for x in g) for g in groups) / (
        sum(len(g) for g in groups) - len(groups))
    den = msb + (k - 1) * msw
    return round((msb - msw) / den, 4) if den else None


def main() -> int:
    files = []
    for pat in ("outputs/*.packed.json", "outputs/_archive*/*.packed.json",
                "outputs/_archive_unknown_*/*.packed.json"):
        files.extend(glob.glob(str(ROOT / pat)))
    files = [f for f in files if "_repair_backup" not in f]
    groups = defaultdict(list)
    tri_alpha_vals = []
    for f in files:
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        q = d.get("quality") or {}
        if not q:
            continue
        key = _norm_q(d.get("question"))
        if not key:
            continue
        flags = q.get("flags") or []
        tri = q.get("tri_alpha")
        if isinstance(tri, (int, float)):
            tri_alpha_vals.append(float(tri))
        groups[key].append({
            "verified": q.get("answer_quality") == "verified",
            "ready": bool(q.get("answer_ready")),
            "coverage": float(q.get("coverage") or 0.0),
            "n_flags": len(flags),
            "tri_alpha": float(tri) if isinstance(tri, (int, float)) else None,
        })
    dup = {k: v for k, v in groups.items() if len(v) >= 2}
    cov_groups = [[p["coverage"] for p in v] for v in dup.values()]
    flag_groups = [[p["n_flags"] for p in v] for v in dup.values()]
    ready_unanimous = sum(
        1 for v in dup.values() if len({p["ready"] for p in v}) == 1)
    ver_unanimous = sum(
        1 for v in dup.values() if len({p["verified"] for p in v}) == 1)
    contradictions = sum(
        1 for v in dup.values()
        if len({p["ready"] for p in v}) > 1 or len({p["verified"] for p in v}) > 1)
    tri_rt = [p["tri_alpha"] for v in dup.values() for p in v
              if p["tri_alpha"] is not None]
    doc = {
        "scanned_packs": len(files),
        "questions_with_duplicates": len(dup),
        "repeat_runs": sum(len(v) for v in dup.values()),
        "ready_unanimous_groups": ready_unanimous,
        "verified_unanimous_groups": ver_unanimous,
        "groups_with_disagreement": contradictions,
        "ready_unanimous_ratio": round(ready_unanimous / max(1, len(dup)), 3),
        "coverage_mean": round(statistics.mean(
            [x for g in cov_groups for x in g]), 4) if cov_groups else None,
        "coverage_icc1_testretest": _icc1(cov_groups),
        "flag_icc1_testretest": _icc1(flag_groups),
        "tri_alpha_n": len(tri_alpha_vals),
        "tri_alpha_mean": round(statistics.mean(tri_alpha_vals), 4)
        if tri_alpha_vals else None,
        "tri_alpha_unreliable_lt0667": sum(1 for x in tri_alpha_vals if x < 0.667),
        "note": ("tri_alpha=跨视角一致性（inter-perspective），不是重测信度；"
                 "本脚本用同题重复产物估计 test-retest：ready/verified 一致率、"
                 "coverage/flag 的 ICC(1)。"),
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("scanned", doc["scanned_packs"], "| dup questions", len(dup),
          "| repeat runs", doc["repeat_runs"])
    print("ready unanimous %.1f%% | verified unanimous %.1f%% | group disagreements %d"
          % (100 * doc["ready_unanimous_ratio"],
             100 * ver_unanimous / max(1, len(dup)), contradictions))
    print("coverage ICC(1)=%s | flag ICC(1)=%s | tri_alpha mean=%s (n=%d, <0.667=%d)"
          % (doc["coverage_icc1_testretest"], doc["flag_icc1_testretest"],
             doc["tri_alpha_mean"], doc["tri_alpha_n"],
             doc["tri_alpha_unreliable_lt0667"]))
    print("->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
