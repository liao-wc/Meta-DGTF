# -*- coding: utf-8 -*-
"""Lead 独立复核：fine_check.audit 与历史 LLM 自省标签的一致性。

独立性原则：不复用 engine-mech 的回放脚本；直接读 outputs/*.packed.json，
自己构造 view_dict、自己定义「记录标签」口径、自己算 P/R/一致率。
口径声明（写进输出，防止误读）：
  · packed 的 views.*.candidates 是跨圈合并、self_check 是末圈标签
    ⇒ 严格索引级 P/R 只在 rounds_run==1 的 view 上算；
  · 全量看「决策级」：backfill 旗 / unsaid 旗 / ing 复述 bool / carry 种类；
  · 记录标签来源：view.quality_flags（candidates_backfilled(x)/unsaid_overused(x)）
    + view.self_check（LLM 原始输出）+ view.carry（末圈 carry）。

用法：
  python scripts/lead_verify_finecheck.py [--limit 0] [--json out.json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKS = ROOT / "outputs"


def load_module():
    p = ROOT / "dgtf_engine" / "dgtf_v2" / "fine_check.py"
    spec = importlib.util.spec_from_file_location("lead_fine_check", str(p))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["lead_fine_check"] = mod
    spec.loader.exec_module(mod)
    return mod


def flag_has(flags, prefix: str) -> bool:
    return any(str(f).startswith(prefix) for f in (flags or []))


def view_dict_of(entry: str, v: dict) -> dict:
    return {
        "entry": str(entry),
        "anchor": v.get("anchor") or "",
        "candidates": v.get("candidates") or [],
        "amps": v.get("amps") or [],
        "collision": v.get("collision") or "",
        "manifest": v.get("manifest") or "",
        "upstream_texts": v.get("upstream_texts") or [],
        "quality_flags": v.get("quality_flags") or [],
        "rephrase_ratio": v.get("rephrase_ratio"),
        "rounds_run": v.get("rounds_run"),
        "threads": v.get("threads") or [],
    }


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) else None
    r = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * p * r / (p + r)) if (p and r) else None
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": None if p is None else round(p, 4),
            "recall": None if r is None else round(r, 4),
            "f1": None if f1 is None else round(f1, 4)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0=全部")
    ap.add_argument("--json", default="docs/lead_finecheck_verification.json")
    args = ap.parse_args()
    mod = load_module()
    packs = sorted(PACKS.glob("*.packed.json"), key=lambda p: p.stat().st_mtime)
    if args.limit:
        packs = packs[-args.limit:]
    stats = {
        "schema": getattr(mod, "SCHEMA", ""),
        "packs": 0, "views": 0, "views_with_label": 0,
        "index_aligned_views": 0,
        "audit_ms_total": 0.0,
        "backfill": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "unsaid": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "ing_rephrased": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "carry_kind": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
        "susp_index": {"tp": 0, "fp": 0, "fn": 0},
        "trigger": {"views": 0, "llm_needed": 0, "reasons": {}},
        "audit_errors": 0,
        "susp_full": {"pred_n": 0, "rec_n": 0, "overlap_n": 0},
    }
    for p in packs:
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        views = d.get("views") or {}
        if not isinstance(views, dict):
            continue
        stats["packs"] += 1
        for entry, v in views.items():
            if not isinstance(v, dict):
                continue
            stats["views"] += 1
            vd = view_dict_of(entry, v)
            t0 = time.perf_counter()
            try:
                out = mod.audit(vd)
            except Exception as e:  # noqa: BLE001
                stats["audit_errors"] += 1
                stats.setdefault("audit_error_samples", []).append(
                    {"pack": d.get("id"), "entry": str(entry), "err": str(e)[:200]})
                continue
            stats["audit_ms_total"] += (time.perf_counter() - t0) * 1000
            dec = out.get("decision") or {}
            trig = out.get("triggers") or {}
            stats["trigger"]["views"] += 1
            if trig.get("llm_needed"):
                stats["trigger"]["llm_needed"] += 1
                for r in trig.get("reasons") or []:
                    k = str(r).split("(")[0]
                    stats["trigger"]["reasons"][k] = \
                        stats["trigger"]["reasons"].get(k, 0) + 1
            sc = v.get("self_check")
            if not isinstance(sc, dict) or not sc:
                continue
            stats["views_with_label"] += 1
            flags = v.get("quality_flags") or []

            def bump(name, pred, rec):
                cell = stats[name]
                if pred and rec:
                    cell["tp"] += 1
                elif pred and not rec:
                    cell["fp"] += 1
                elif (not pred) and rec:
                    cell["fn"] += 1
                else:
                    cell["tn"] += 1

            bump("backfill",
                 bool(dec.get("backfill_flag")),
                 flag_has(flags, "candidates_backfilled"))
            bump("unsaid",
                 bool(dec.get("unsaid_flag")),
                 flag_has(flags, "unsaid_overused"))
            bump("ing_rephrased",
                 bool(out.get("ing_rephrased")),
                 bool(sc.get("ing_rephrased")))
            rec_carry = {str(c.get("kind")) for c in (v.get("carry") or [])
                         if isinstance(c, dict)}
            # carry 只在「至少一边有」时计入混淆矩阵，避免空对空放大一致率
            for kind in ("candidate", "ing", "any", "dual"):
                pred = kind in (dec.get("carry_kinds") or [])
                rec = kind in rec_carry
                if pred or rec:
                    bump("carry_kind", pred, rec)
            # 索引级（仅 rounds_run==1 才严格对齐）
            if int(v.get("rounds_run") or 0) == 1:
                stats["index_aligned_views"] += 1
                pred_set = set(out.get("suspicious_candidates") or [])
                rec_set = set(int(x) for x in (sc.get("suspicious_candidates") or [])
                              if str(x).isdigit())
                stats["susp_index"]["tp"] += len(pred_set & rec_set)
                stats["susp_index"]["fp"] += len(pred_set - rec_set)
                stats["susp_index"]["fn"] += len(rec_set - pred_set)
            else:
                pred_set = set(out.get("suspicious_candidates") or [])
                rec_set = set(int(x) for x in (sc.get("suspicious_candidates") or [])
                              if str(x).isdigit())
                stats["susp_full"]["pred_n"] += len(pred_set)
                stats["susp_full"]["rec_n"] += len(rec_set)
                stats["susp_full"]["overlap_n"] += len(pred_set & rec_set)

    stats["audit_ms_avg"] = round(
        stats["audit_ms_total"] / max(1, stats["views"]), 3)
    stats["backfill_prf"] = prf(stats["backfill"]["tp"], stats["backfill"]["fp"],
                                stats["backfill"]["fn"])
    stats["unsaid_prf"] = prf(stats["unsaid"]["tp"], stats["unsaid"]["fp"],
                              stats["unsaid"]["fn"])
    stats["ing_rephrased_prf"] = prf(stats["ing_rephrased"]["tp"],
                                     stats["ing_rephrased"]["fp"],
                                     stats["ing_rephrased"]["fn"])
    stats["carry_kind_prf"] = prf(stats["carry_kind"]["tp"],
                                  stats["carry_kind"]["fp"],
                                  stats["carry_kind"]["fn"])
    stats["susp_index_prf"] = prf(stats["susp_index"]["tp"],
                                  stats["susp_index"]["fp"],
                                  stats["susp_index"]["fn"])
    n = stats["trigger"]["views"] or 1
    stats["trigger"]["skip_ratio"] = round(
        1 - stats["trigger"]["llm_needed"] / n, 4)

    print("== Lead 独立复核 fine_check ==")
    print("packs=%d views=%d 有标签=%d 索引对齐(rounds_run==1)=%d audit_avg=%.3fms errors=%d"
          % (stats["packs"], stats["views"], stats["views_with_label"],
             stats["index_aligned_views"], stats["audit_ms_avg"],
             stats["audit_errors"]))
    print("auto 触发：llm_needed=%d/%d（跳过率 %.1f%%），reasons=%s"
          % (stats["trigger"]["llm_needed"], stats["trigger"]["views"],
             100 * stats["trigger"]["skip_ratio"],
             json.dumps(stats["trigger"]["reasons"], ensure_ascii=False)))
    for key in ("backfill_prf", "unsaid_prf", "ing_rephrased_prf",
                "carry_kind_prf", "susp_index_prf"):
        print("  %-18s %s" % (key, json.dumps(stats[key], ensure_ascii=False)))
    print("  全量 suspicious（索引不可严格对齐，只作参考）：pred=%d rec=%d overlap=%d"
          % (stats["susp_full"]["pred_n"], stats["susp_full"]["rec_n"],
             stats["susp_full"]["overlap_n"]))
    out = Path(args.json)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stats, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
