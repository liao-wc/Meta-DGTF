# -*- coding: utf-8 -*-
"""probe cover 判据误报复算 v2（Round 126，零成本，复用引擎函数）。

对每个带 probe_no_target_covered 的 pack：
  1. 用引擎原判据复算，验证 flag 可复现；
  2. 统计「放宽判据」会翻正的 pack 数：
     R1: _sim3 >= 0.20
     R2: _overlap_coef >= 0.40
     R3: _similar(...,0.55)
     R4: 以上任一（组合兜底）
  3. 输出被翻正样例（probe 问题 vs 靶子文本），供人工语义复核。
"""
from __future__ import annotations

import glob
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "probe_cover_audit_v2_20261026.json"


def load_engine():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "dgtf_engine"))
    eng = (ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
           / "Meta-DGTF-V2.2.4.py")
    spec = importlib.util.spec_from_file_location("engine_probe_audit", str(eng))
    m = importlib.util.module_from_spec(spec)
    sys.modules["engine_probe_audit"] = m
    spec.loader.exec_module(m)
    return m


def targets_of(view1):
    tp = {}
    for i, u in enumerate(view1.get("untouched") or []):
        t = str((u or {}).get("desc", "")).strip()
        if not t:
            continue
        tp["T%d" % (i + 1)] = t
        if (u or {}).get("id"):
            tp[str(u["id"])] = t
        else:
            tp[str(i + 1)] = t
    return tp


def match_strict(m, pq, tgt):
    return (m._similar(pq, tgt, m._QC_DUP_SIM)
            or m._sim3(pq, tgt) >= m._COVERS_SIM_MIN
            or m._overlap_coef(pq, tgt) >= m._COV_OVERLAP_MIN)


def variant(m, pq, tgt, rule):
    s3 = m._sim3(pq, tgt)
    ov = m._overlap_coef(pq, tgt)
    sm = m._similar(pq, tgt, 0.55)
    if rule == "R1":
        return s3 >= 0.20
    if rule == "R2":
        return ov >= 0.40
    if rule == "R3":
        return sm
    if rule == "R4":
        return s3 >= 0.20 or ov >= 0.40 or sm
    return False


def main() -> int:
    m = load_engine()
    files = glob.glob(str(ROOT / "outputs" / "*.packed.json"))
    flagged = reproduced = 0
    flips = {k: 0 for k in ("R1", "R2", "R3", "R4")}
    samples = []
    for f in files:
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        q = d.get("quality") or {}
        flags = q.get("flags") or []
        if "probe_no_target_covered" not in flags:
            continue
        flagged += 1
        v1 = (d.get("views") or {}).get("1") or {}
        probes = v1.get("probes") or []
        targets = targets_of(v1)
        strict_hit = False
        wide_hit = {k: False for k in flips}
        best_pair = None
        for p in probes:
            pq = str((p or {}).get("question", ""))
            for c in ((p or {}).get("covers") or []):
                c = str(c).strip()
                if not c:
                    continue
                c2 = c[1:] if c.startswith("#") else c
                c2 = c2[1:] if c2.startswith("T") and c2[1:].isdigit() else c2
                tgt = targets.get(c) or targets.get(c2)
                if not tgt:
                    continue
                if match_strict(m, pq, tgt):
                    strict_hit = True
                    break
                for r in wide_hit:
                    if variant(m, pq, tgt, r):
                        wide_hit[r] = True
                if best_pair is None:
                    best_pair = (pq[:60], tgt[:60], round(m._sim3(pq, tgt), 3),
                                 round(m._overlap_coef(pq, tgt), 3))
            if strict_hit:
                break
        if not strict_hit:
            reproduced += 1
            for r in wide_hit:
                if wide_hit[r]:
                    flips[r] += 1
            if wide_hit["R4"] and len(samples) < 8 and best_pair:
                samples.append({"file": os.path.basename(f),
                                "probe": best_pair[0], "target": best_pair[1],
                                "sim3": best_pair[2], "overlap": best_pair[3],
                                "aq": q.get("answer_quality")})
    summary = {
        "packs_with_quality": sum(1 for _ in files),
        "flagged": flagged,
        "flag_reproduced": reproduced,
        "wide_flips": flips,
        "wide_flip_ratio": {k: round(v / max(1, flagged), 4)
                            for k, v in flips.items()},
        "samples": samples,
        "note": ("strict 复算应≈flagged（验证一致性）；wide_flips 为放宽判据会翻正的数量，"
                 "需人工语义复核后决定是否落地。"),
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("flagged:", flagged, "| strict reproduced:", reproduced)
    print("wide flips:", flips)
    print("ratios:", summary["wide_flip_ratio"])
    for s in samples[:5]:
        print("  sample:", s["probe"][:34], "<=>", s["target"][:34],
              "| sim3", s["sim3"], "ov", s["overlap"], "| aq", s["aq"])
    print("->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
