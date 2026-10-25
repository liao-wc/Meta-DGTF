#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2.2.3 离线回放：确定性自省核 vs 历史 LLM 自省标签（零 API 成本）。

用法（仓库根）：
    $env:PYTHONPATH="$PWD;$PWD/dgtf_engine"
    python scripts/eval_self_check_replay.py                    # 打印 JSON 报告
    python scripts/eval_self_check_replay.py --write-prior      # 另写结构先验表
    python scripts/eval_self_check_replay.py --out docs/xxx.json

口径（重要）
------------
1. packed 的 `views.*.candidates` 是**跨圈合并**后的列表，而 `self_check` 是
   **末圈**一次调用的标签 ⇒ 索引级 P/R 只在 `rounds_run==1`（单圈）子集上
   严格成立；全量只用「决策触发级」口径（挂不挂旗/给不给 carry）。
2. 回放态没有逐圈展开 provenance（`expanded_descs` 不在 packed 里），
   `new_candidates` 触发器**不可回放**；脚本只报「其余触发理由」的命中率，
   并给一个**模拟运行时**的跳过率上下界（expanded_descs = 全量候选 / None）。
3. 所有数字都是「确定性核单独」的读数：auto_narr 档的决策字段仍走 LLM，
   因此这些数字用来判断「哪些字段可以交给核」，不是上线指标承诺。
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_engine"))

from dgtf_v2 import fine_check as FC  # noqa: E402


def _load_views(paths):
    views = []
    for p in paths:
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        for entry, v in (d.get("views") or {}).items():
            if isinstance(v, dict) and isinstance(v.get("self_check"), dict):
                views.append({"pack": Path(p).name, "entry": entry, "view": v})
    return views


def _int_set(items):
    out = set()
    for x in items or []:
        try:
            out.add(int(str(x).strip()))
        except (TypeError, ValueError):
            continue
    return out


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4),
            "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn}


def eval_index_level(views, field):
    """单圈子集：索引级 P/R/F1（field=suspicious_candidates / suspicious_amps）。"""
    tp = fp = fn = 0
    per_view = []
    n_views = 0
    for rec in views:
        v = rec["view"]
        if int(v.get("rounds_run") or 0) != 1:
            continue
        n_views += 1
        det = set(FC.audit(v)[field])
        lab = _int_set((v.get("self_check") or {}).get(field))
        _tp, _fp, _fn = len(det & lab), len(det - lab), len(lab - det)
        tp, fp, fn = tp + _tp, fp + _fp, fn + _fn
        per_view.append({"view": rec["entry"], **_prf(_tp, _fp, _fn)})
    out = _prf(tp, fp, fn)
    out["views"] = n_views
    out["per_view_f1_mean"] = round(
        sum(x["f1"] for x in per_view) / max(1, len(per_view)), 4)
    return out


def eval_label_level(views):
    """全量：标签级（ing_rephrased / honest_about_empty）与计数一致性。"""
    tp = fp = fn = tn = 0
    truth = Counter()
    for rec in views:
        v = rec["view"]
        a = FC.audit(v)
        lab = bool((v.get("self_check") or {}).get("ing_rephrased"))
        pred = bool(a.get("ing_rephrased"))
        truth["llm_true"] += int(lab)
        truth["views"] += 1
        truth["det_true"] += int(pred)
        if pred and lab:
            tp += 1
        elif pred and not lab:
            fp += 1
        elif lab:
            fn += 1
        else:
            tn += 1
    rephrase = _prf(tp, fp, fn)
    rephrase.update({"tn": tn, "llm_true": truth["llm_true"],
                     "det_true": truth["det_true"], "views": truth["views"]})
    # honest_about_empty 一致率（无决策消费者，只看方向）
    agree = n = 0
    honest_false = 0
    for rec in views:
        v = rec["view"]
        lab = (v.get("self_check") or {}).get("honest_about_empty")
        if lab is None:
            continue
        n += 1
        honest_false += int(not bool(lab))
        agree += int(bool(lab) == bool(FC.audit(v).get("honest_about_empty")))
    return {"ing_rephrased": rephrase,
            "honest_about_empty": {"agreement": round(agree / max(1, n), 4),
                                   "n": n, "llm_false": honest_false}}


def eval_unsaid(views):
    """unsaid 计数一致率 + 决策旗（auto 跳过时会用核的计数）。"""
    exact = within1 = ge = n = 0
    gate_same = gate_more = gate_miss = 0
    for rec in views:
        v = rec["view"]
        sc = v.get("self_check") or {}
        a = FC.audit(v)
        det = int(a.get("unsaid_count") or 0)
        lab = int(sc.get("unsaid_count") or 0)
        n += 1
        exact += int(det == lab)
        within1 += int(abs(det - lab) <= 1)
        ge += int(det >= lab)
        lim = 3
        llm_gate = FC._unsaid_gate(max(det, lab), lim,
                                   bool(sc.get("unsaid_is_escape")),
                                   FC.DEFAULT_CFG)
        det_gate = FC._unsaid_gate(det, lim, False, FC.DEFAULT_CFG)
        if llm_gate == det_gate:
            gate_same += 1
        elif det_gate == "flag" or (det_gate == "note" and llm_gate == "off"):
            gate_more += 1
        else:
            gate_miss += 1
    return {"exact": round(exact / max(1, n), 4),
            "within1": round(within1 / max(1, n), 4),
            "det_ge_llm": round(ge / max(1, n), 4),
            "gate_same": round(gate_same / max(1, n), 4),
            "gate_more_conservative": round(gate_more / max(1, n), 4),
            "gate_miss": round(gate_miss / max(1, n), 4),
            "views": n}


def eval_decisions(views):
    """全量决策触发级：回填旗 / carry 种类 vs LLM 派生期望。"""
    # 回填旗：packed 的 candidates_backfilled 是**最终**旗（可能由自检挂上）
    tp = fp = fn = tn = 0
    for rec in views:
        v = rec["view"]
        a = FC.audit(v)
        det = bool((a.get("decision") or {}).get("backfill_flag"))
        lab = any("candidates_backfilled" in str(f)
                  for f in (v.get("quality_flags") or []))
        if det and lab:
            tp += 1
        elif det and not lab:
            fp += 1
        elif lab:
            fn += 1
        else:
            tn += 1
    backfill = _prf(tp, fp, fn)
    backfill["tn"] = tn
    # carry 种类：LLM 模式下会生成哪些 kind（与引擎 _build_carry 同口径）
    tp = fp = fn = 0
    kind_stat = Counter()
    for rec in views:
        v = rec["view"]
        sc = v.get("self_check") or {}
        a = FC.audit(v)
        det = set((a.get("decision") or {}).get("carry_kinds") or [])
        lab = set()
        if _int_set(sc.get("suspicious_candidates")):
            lab.add("candidate")
        if sc.get("ing_rephrased"):
            lab.add("ing")
        if sc.get("unsaid_is_escape"):
            lab.add("any")
        bq = v.get("both_quota") or {}
        if isinstance(bq, dict) and any(
                str(i.get("missing") or "").strip()
                for i in (bq.get("items") or []) if isinstance(i, dict)):
            lab.add("dual")
        tp += len(det & lab)
        fp += len(det - lab)
        fn += len(lab - det)
        kind_stat.update(lab)
    carry = _prf(tp, fp, fn)
    carry["llm_kind_counts"] = dict(kind_stat)
    return {"backfill_flag_vs_packed": backfill,
            "carry_kinds": carry}


def eval_triggers(views):
    """触发理由分布 + 模拟运行时跳过率（回放态 new_candidates 不可算）。"""
    reasons = Counter()
    static_hit = 0
    n = 0
    skip_replay = 0
    skip_sim_full = 0
    for rec in views:
        v = dict(rec["view"])
        n += 1
        a = FC.audit(v)
        rs = list((a.get("triggers") or {}).get("reasons") or [])
        reasons.update(rs)
        # 回放态：无 provenance ⇒ new_candidates 不触发
        if not rs:
            skip_replay += 1
        # 模拟运行时最好情况：expanded_descs = 全部候选 desc（新增=0）
        v2 = dict(v)
        v2["expanded_descs"] = [str(c.get("desc") or "")
                                for c in (v.get("candidates") or [])
                                if isinstance(c, dict)]
        a2 = FC.audit(v2)
        rs2 = list((a2.get("triggers") or {}).get("reasons") or [])
        if not rs2:
            skip_sim_full += 1
        # 模拟最坏情况：有 provenance 但全部候选都"新"
        v3 = dict(v)
        v3["expanded_descs"] = []
        a3 = FC.audit(v3)
        if not (a3.get("triggers") or {}).get("llm_needed"):
            static_hit += 1
    return {"views": n,
            "reason_counts": dict(reasons),
            "skip_rate_replay_no_provenance": round(skip_replay / max(1, n), 4),
            "skip_rate_runtime_bestcase_all_grown":
                round(skip_sim_full / max(1, n), 4),
            "skip_rate_runtime_worstcase_all_new": round(
                static_hit / max(1, n), 4)}


def eval_dual_judge_prior(views):
    """结构先验 P(position|entry,source,kind,attribute) + 判定缓存统计。"""
    groups = defaultdict(Counter)
    total = 0
    uniq = set()
    pos_counter = Counter()
    first_pos = {}
    repeat = repeat_agree = 0
    for rec in views:
        v = rec["view"]
        entry = str(rec["entry"])
        anchor = str(v.get("anchor") or "")
        for c in (v.get("candidates") or []):
            if not isinstance(c, dict):
                continue
            total += 1
            pos = str(c.get("position") or "0")
            pos_counter[pos] += 1
            key = "|".join([entry, str(c.get("source") or "?"),
                            str(c.get("kind") or "?"),
                            str(c.get("attribute") or "?")])
            groups[key][pos] += 1
            # 跨跑同文本复用（缓存代理口径：entry+归一化 desc）
            tkey = (entry, FC.normalize_text(c.get("desc")))
            uniq.add(tkey)
            if tkey in first_pos:
                repeat += 1
                repeat_agree += int(first_pos[tkey] == pos)
            else:
                first_pos[tkey] = pos
    prior = {}
    hi_n = hi_ok = 0
    for k, cnt in groups.items():
        n = sum(cnt.values())
        pos, c0 = max(cnt.items(), key=lambda kv: kv[1])
        prior[k] = {"n": n, "counts": dict(cnt)}
        if n >= 20 and c0 / n >= 0.75:
            hi_n += n
            hi_ok += c0
    return {
        "candidates": total,
        "unique_entry_text": len(uniq),
        "unique_ratio": round(len(uniq) / max(1, total), 4),
        "cross_run_repeat_ratio": round(repeat / max(1, total), 4),
        "repeat_position_agreement": round(repeat_agree / max(1, repeat), 4),
        "position_dist": dict(pos_counter),
        "prior_groups": len(groups),
        "high_conf_coverage": round(hi_n / max(1, total), 4),
        "high_conf_accuracy": round(hi_ok / max(1, hi_n), 4),
        "prior": prior,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="V2.2.3 确定性自省核离线回放")
    ap.add_argument("--glob", default="outputs/*.packed.json")
    ap.add_argument("--out", default="")
    ap.add_argument("--write-prior", action="store_true",
                    help="把结构先验写到 engine/dual_judge_prior.json")
    args = ap.parse_args(argv)
    paths = sorted(glob.glob(str(ROOT / args.glob)))
    views = _load_views(paths)
    if not views:
        print("FAIL 未找到带 self_check 标签的 packed 产物", file=sys.stderr)
        return 2
    report = {
        "schema": "dgtf.fine_check.replay.v1",
        "packs": len({rec["pack"] for rec in views}),
        "views": len(views),
        "single_round_views": sum(
            1 for r in views if int(r["view"].get("rounds_run") or 0) == 1),
        "suspicious_candidates_index": eval_index_level(
            views, "suspicious_candidates"),
        "suspicious_amps_index": eval_index_level(views, "suspicious_amps"),
        "label_level": eval_label_level(views),
        "unsaid": eval_unsaid(views),
        "decisions": eval_decisions(views),
        "triggers": eval_triggers(views),
        "dual_judge": eval_dual_judge_prior(views),
    }
    if args.write_prior:
        prior = report["dual_judge"]["prior"]
        p = ROOT / "dgtf_engine" / "dgtf_v2" / "engine" / "dual_judge_prior.json"
        p.write_text(json.dumps({
            "schema": "dgtf.dual_judge_prior.v1",
            "source": "scripts/eval_self_check_replay.py",
            "groups": prior,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        report["prior_written"] = str(p.relative_to(ROOT))
    report["dual_judge"].pop("prior", None)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        (ROOT / args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
