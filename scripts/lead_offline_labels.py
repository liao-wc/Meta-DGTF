# -*- coding: utf-8 -*-
"""Lead 独立离线标签抽取（为 fine_check/self_check 细粒度替换做独立验证）。

不做算法判断，只做三件事：
  1. 从 outputs/*.packed.json 抽样出「每个 view 的完整输入 + LLM 自省标签」，
     落成 JSONL，供 Lead 独立复核（不与 engine-mech 的评测器共用代码）；
  2. 打印标签分布与候选字段分布（检查历史产物里到底有哪些可用于确定性
     判据的字段：source/kind/attribute/is_amp_candidate/rephrase_ratio 等）；
  3. 计算几个「零成本基线」：多数类准确率、按 entry 分组的多数类准确率，
     作为任何新机制必须超过的下限。

用法：
  python scripts/lead_offline_labels.py extract
  python scripts/lead_offline_labels.py stats
  python scripts/lead_offline_labels.py all
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "_lead_audit"
LABELS = OUT / "selfcheck_labels.jsonl"
JUDGE_LABELS = OUT / "judge_labels.jsonl"


def _packs() -> list[Path]:
    return sorted((ROOT / "outputs").glob("*.packed.json"),
                  key=lambda p: p.stat().st_mtime)


def extract() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    n_view = n_cand = 0
    with LABELS.open("w", encoding="utf-8") as fl, \
            JUDGE_LABELS.open("w", encoding="utf-8") as fj:
        for p in _packs():
            try:
                d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:  # noqa: BLE001
                continue
            views = d.get("views") or {}
            if not isinstance(views, dict):
                continue
            for entry, v in views.items():
                if not isinstance(v, dict):
                    continue
                sc = v.get("self_check")
                cands = v.get("candidates") or []
                row = {
                    "pack": d.get("id"),
                    "question": str(d.get("question") or "")[:120],
                    "entry": str(entry),
                    "anchor": str(v.get("anchor") or "")[:4000],
                    "collision": str(v.get("collision") or "")[:4000],
                    "manifest": str(v.get("manifest") or "")[:6000],
                    "candidates": cands,
                    "amps": v.get("amps") or [],
                    "quality_flags": v.get("quality_flags") or [],
                    "rephrase_ratio": v.get("rephrase_ratio"),
                    "upstream_texts": [str(t)[:1500] for t in
                                       (v.get("upstream_texts") or [])][:4],
                    "upstream_layers": v.get("upstream_layers"),
                    "rounds_run": v.get("rounds_run"),
                    "quality_verdict": str(v.get("quality_verdict") or "")[:300],
                    "self_check": sc,
                    "amp_diag": v.get("amp_diag"),
                }
                fl.write(json.dumps(row, ensure_ascii=False) + "\n")
                n_view += 1
                n_cand += len(cands)
                # 对偶判断标签：一个候选一行
                for i, c in enumerate(cands, 1):
                    if not isinstance(c, dict):
                        continue
                    fj.write(json.dumps({
                        "pack": d.get("id"), "question": str(d.get("question") or "")[:120],
                        "entry": str(entry), "idx": i,
                        "desc": str(c.get("desc") or "")[:600],
                        "kind": c.get("kind"), "source": c.get("source"),
                        "attribute": c.get("attribute"),
                        "position": c.get("position"),
                        "yin": c.get("yin"), "yang": c.get("yang"),
                        "is_amp_candidate": c.get("is_amp_candidate"),
                        "why_position": str(c.get("why_position") or "")[:120],
                        "attribute_anchored": c.get("attribute_anchored"),
                    }, ensure_ascii=False) + "\n")
    print("views=%d candidates=%d" % (n_view, n_cand))
    print("->", LABELS)
    print("->", JUDGE_LABELS)
    return 0


def _read_jsonl(p: Path):
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            yield json.loads(ln)


def stats() -> int:
    if not LABELS.exists():
        print("先跑 extract")
        return 2
    rows = list(_read_jsonl(LABELS))
    print("view 样本：%d" % len(rows))
    # ── self_check 标签分布 ─────────────────────────────
    sc_rows = [r for r in rows if isinstance(r.get("self_check"), dict)
               and r["self_check"]]
    print("有 self_check 标签：%d (%.1f%%)"
          % (len(sc_rows), 100.0 * len(sc_rows) / max(1, len(rows))))
    dist = collections.Counter()
    for r in sc_rows:
        sc = r["self_check"]
        dist["susp_cand_nonempty"] += bool(sc.get("suspicious_candidates"))
        dist["susp_amp_nonempty"] += bool(sc.get("suspicious_amps"))
        dist["ing_rephrased_true"] += bool(sc.get("ing_rephrased"))
        dist["honest_empty_false"] += sc.get("honest_about_empty") is False
        dist["unsaid_escape_true"] += bool(sc.get("unsaid_is_escape"))
        dist["notes_nonempty"] += bool(str(sc.get("notes") or "").strip())
        dist["flow_verdict_nonempty"] += bool(str(sc.get("flow_verdict") or "").strip())
        dist["unsaid_count_gt0"] += int(sc.get("unsaid_count") or 0) > 0
    for k, v in dist.items():
        print("  %-24s %4d  (%.1f%%)" % (k, v, 100.0 * v / len(sc_rows)))
    # ── 候选字段可用性 ──────────────────────────────────
    cands = [c for r in rows for c in (r.get("candidates") or [])
             if isinstance(c, dict)]
    print("\n候选字段分布（n=%d）：" % len(cands))
    for field in ("kind", "source", "attribute", "position",
                  "is_amp_candidate", "attribute_anchored"):
        cnt = collections.Counter(str(c.get(field)) for c in cands)
        print("  %-18s %s" % (field, dict(cnt.most_common(8))))
    # ── 位置标签基线（对偶判断可替换性下限）────────────
    jl = [r for r in _read_jsonl(JUDGE_LABELS)
          if r.get("position") in ("0", "1", "both")]
    print("\n对偶判断标签：%d 条" % len(jl))
    if jl:
        pc = collections.Counter(r["position"] for r in jl)
        print("  position 分布：%s" % dict(pc))
        maj = pc.most_common(1)[0][1] / len(jl)
        print("  全局多数类基线：%.4f" % maj)
        for group in ("entry", "source", "kind"):
            g = collections.defaultdict(collections.Counter)
            for r in jl:
                g[str(r.get(group))][r["position"]] += 1
            correct = sum(c.most_common(1)[0][1] for c in g.values())
            print("  按 %-7s 分组多数类：%.4f（组数 %d）"
                  % (group, correct / len(jl), len(g)))
        # 组合 (entry,kind) / (entry,source,attribute)
        for fields in (("entry", "kind"), ("entry", "source", "attribute"),
                       ("entry", "kind", "attribute", "is_amp_candidate")):
            g = collections.defaultdict(collections.Counter)
            for r in jl:
                g[tuple(str(r.get(f)) for f in fields)][r["position"]] += 1
            correct = sum(c.most_common(1)[0][1] for c in g.values())
            print("  按 %-38s 分组多数类：%.4f（组数 %d）"
                  % ("+".join(fields), correct / len(jl), len(g)))
    # ── 跨 run 重复候选（缓存命中潜力）──────────────────
    by_q = collections.defaultdict(list)
    for r in rows:
        for c in (r.get("candidates") or []):
            if isinstance(c, dict):
                by_q[r["question"]].append(
                    (r["pack"], str(c.get("desc") or "").strip()[:200]))
    total = sum(len(v) for v in by_q.values())
    dup_in_same_q = 0
    for q, lst in by_q.items():
        seen = set()
        for pack, desc in lst:
            key = desc
            if key in seen:
                dup_in_same_q += 1
            seen.add(key)
    print("\n跨 run 重复候选（同题、归一化文本完全相同）：%d / %d (%.1f%%)"
          % (dup_in_same_q, total, 100.0 * dup_in_same_q / max(1, total)))
    print("说明：这是 dual_judge 判定缓存的「上界乐观值」——只在复跑同一题时有效；"
          "不同题的候选不共享缓存。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["extract", "stats", "all"])
    a = ap.parse_args()
    if a.cmd in ("extract", "all"):
        extract()
    if a.cmd in ("stats", "all"):
        stats()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
