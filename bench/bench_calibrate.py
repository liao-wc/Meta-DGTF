#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段2 G2.6] 三态判决的人工校准导出 / 回填。

用法：
    python bench/bench_calibrate.py export <run_dir> <out.md>
    python bench/bench_calibrate.py import <filled.md> <run_dir>

表格 6 列（导出即建表，人在「人工 verdict」列填：
decidable / partial / undecidable 之一）：
    | # | 子问题 | 三票 | 最终 | 人工 verdict | 备注 |

★ 队列为空时**回落到研究层带票的子问题**，而不是导出一张空表 ——
  空表会让下游把"这次没有分歧"读成"校准跑了但没有内容"。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
LEGAL = ("decidable", "partial", "undecidable")


def _packed(run_dir: Path) -> dict:
    """取 packed。★ 兼容两种落盘名：harness 写 `packed.json`，
    任务书 Step 2.6 的示例读 `result.json` —— 只认一个就会在另一边静默
    返回空 dict，然后被读成「这次没有分歧」。"""
    if run_dir.is_dir():
        cands = [run_dir / "packed.json", run_dir / "result.json"]
    else:
        cands = [run_dir]
    for p in cands:
        if not p.is_file():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict):
            return d
    return {}


def _votes_str(vs) -> str:
    """三票的可打印形态：既吃 ["a","b"]，也吃 [{"voter":0,"label":"a"}]。"""
    out = []
    for v in (vs or []):
        out.append(str(v.get("label") or "?") if isinstance(v, dict)
                   else str(v))
    return " / ".join(out) or "（无票）"


def _queue(packed: dict):
    q = packed.get("calibration_queue") or []
    if q:
        return q, "calibration_queue"
    out = []
    subs = ((packed.get("pools") or {}).get("1") or {}).get("sub_questions") or []
    for i, s in enumerate(subs, 1):
        # ★ 只回落「无多数票」的那些（`_tri_level == "low"`）。
        #   以前这里写的是 `s.get("_tri_votes") or s.get("first_label")` ——
        #   而 first_label 每一条都有，于是"队列为空"时导出表里是**满的**，
        #   把"没有分歧"读成了"全都要人工核"。
        if s.get("_tri_level") == "low" or s.get("stability") == "low":
            out.append({"sub_id": s.get("id", i),
                        "question": str(s.get("question", ""))[:160],
                        "votes": list(s.get("_tri_votes") or []),
                        "final": s.get("_tri_final") or s.get("decidability"),
                        "first_label": s.get("first_label"),
                        "level": s.get("_tri_level", "")})
    return out, "pools.1.sub_questions(回落)"


def cmd_export(a) -> int:
    packed = _packed(Path(a.run_dir))
    if not packed:
        print(f"✗ 找不到 packed.json：{a.run_dir}")
        return 1
    items, src = _queue(packed)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# 三态判决人工校准表 · {Path(a.run_dir).name}",
        "",
        f"- 来源：`{src}`　共 {len(items)} 条",
        f"- 冻结签名：`{(packed.get('freeze') or {}).get('signature', '')}`",
        f"- 填表：在「人工 verdict」列写 `{' / '.join(LEGAL)}` 之一；"
        f"留空 = 跳过该条。",
        "",
        "| # | 子问题 | 三票 | 最终 | 人工 verdict | 备注 |",
        "|---|---|---|---|---|---|",
    ]
    for i, it in enumerate(items, 1):
        q = str(it.get("question", "")).replace("|", "/")[:80]
        vs = _votes_str(it.get("votes"))
        lines.append(f"| {i} | {q} | {vs} | {it.get('final', '')} |  |  |")
    out.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    print(f"✓ 导出 {len(items)} 行 → {out}")
    return 0 if items else 2


def cmd_import(a) -> int:
    md = Path(a.md)
    if not md.is_file():
        print(f"✗ 找不到 {md}")
        return 1
    rows = []
    for ln in md.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln.startswith("|") or "---" in ln:
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) < 6 or cells[0] in ("#", ""):
            continue
        rows.append(cells)
    verdicts = {}
    bad = []
    for c in rows:
        v = c[4].lower()
        if not v:
            continue
        if v not in LEGAL:
            bad.append(c[4])
            continue
        verdicts[str(c[0])] = {"verdict": v, "question": c[1],
                               "votes": c[2], "final": c[3],
                               "note": c[5]}
    run_dir = Path(a.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "verdicts.json").write_bytes(json.dumps(
        {"n": len(verdicts), "verdicts": verdicts, "illegal": bad},
        ensure_ascii=False, indent=2).encode("utf-8"))
    print(f"✓ 回填 {len(verdicts)} 条人工 verdict → "
          f"{run_dir / 'verdicts.json'}（非法值 {bad}）")
    return 0 if verdicts or not bad else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("run_dir")
    e.add_argument("out")
    e.set_defaults(fn=cmd_export)
    i = sub.add_parser("import")
    i.add_argument("md")
    i.add_argument("run_dir")
    i.set_defaults(fn=cmd_import)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
