#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 F.1 诊断] rubric 为 0 的成因：**没有可产的动作** vs **抽取失败**。

对 `bench/runs/v1221_full/*/packed.json` 逐题输出：
  · rubric 三项（来自 bench_score.score_actions）
  · dp.actions 条数（schema 产出）
  · answered_sub_ids 条数 / 子问题总数 / undecidable 条数
  · quality_flags / errors

判定口径（写清楚，避免把两种 0 混为一谈）：
  · 若 `answered == 0 且 全部子问题 undecidable` → **没有可产的动作**（引擎如实留痕，
    不是抽取失败）
  · 若 `answered > 0 但 dp.actions == 0` → **模型没按 schema 产出**（P1 的硬约束
    应当留痕 `action_incomplete`）
  · 若 `dp.actions > 0 但 rubric 低` → 抽取/字段问题

用法：python _diag_v1221_rubric.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "bench"))


def main() -> int:
    from bench_score import score_actions  # noqa: E402

    rows = []
    for d in sorted((HERE / "bench" / "runs" / "v1221_full").iterdir()):
        pk = d / "packed.json"
        if not pk.is_file():
            continue
        try:
            res = json.loads(pk.read_text(encoding="utf-8"))
        except Exception:
            continue
        v1 = (res.get("views") or {}).get("1") or {}
        dp = v1.get("decidable_product") or {}
        acts = list(dp.get("actions") or [])
        not_do = list(v1.get("_not_do") or [])
        sq = ((res.get("pools") or {}).get("1") or {}).get(
            "sub_questions") or []
        und = sum(1 for s in sq if s.get("decidability") == "undecidable")
        ans = list(dp.get("answered_sub_ids") or [])
        rb = score_actions(acts, not_do)
        if ans and not acts:
            cause = "模型没按 schema 产出（answered>0 但 actions=0）"
        elif not ans and sq and und == len(sq):
            cause = "没有可产的动作（子问题全 undecidable、答出 0）"
        elif not sq:
            cause = "无子问题"
        elif acts:
            cause = "有产出" + ("（rubric 低）" if rb["score"] < 2 else "")
        else:
            cause = "其他"
        rows.append({
            "id": d.name, "score": rb["score"], "n_actions": rb["n_actions"],
            "n_not_do": rb["n_not_do"], "dp_actions": len(acts),
            "answered": len(ans), "subs": len(sq), "und": und,
            "flags": [f for f in (v1.get("quality_flags") or [])
                      if f in ("action_incomplete", "action_fields_missing",
                               "not_do_missing")],
            "cause": cause,
        })

    if not rows:
        print("没有已完成的 run（先跑 F.1）")
        return 1
    tot = sum(r["score"] for r in rows)
    print("题数 " + str(len(rows)) + " | rubric 合计 " + str(tot)
          + " | 平均 " + format(tot / len(rows), ".2f") + "/3")
    print()
    print("| 题 | rubric | actions | 不做什么 | answered | 子问题 | und | flags | 成因 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print("| " + r["id"] + " | " + str(r["score"]) + " | "
              + str(r["n_actions"]) + " | " + str(r["n_not_do"]) + " | "
              + str(r["answered"]) + " | " + str(r["subs"]) + " | "
              + str(r["und"]) + " | " + ",".join(r["flags"]) + " | "
              + r["cause"] + " |")
    print()
    n_ok = sum(1 for r in rows if r["score"] >= 2)
    print("rubric ≥2 的题数：" + str(n_ok) + "/" + str(len(rows)))
    _c = {}
    for r in rows:
        _c[r["cause"]] = _c.get(r["cause"], 0) + 1
    print("成因分布：" + json.dumps(_c, ensure_ascii=False))
    Path("_diag_v1221_rubric.json").write_bytes(json.dumps(
        {"rows": rows, "avg": tot / len(rows), "n_ok": n_ok,
         "cause_dist": _c}, ensure_ascii=False, indent=2).encode("utf-8"))
    print("✓ _diag_v1221_rubric.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
