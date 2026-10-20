#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段1 G1.10 / F.1] bench 汇总报告（四列：判定 / 一致率 / 分层 pass / rubric）。

用法：
    python bench/bench_report.py bench/runs/<tag> > bench/reports/v122_full.md

★ 数据源优先 `packed.json`（结构化），其次解析产物 md。
  为什么两套：本项目的老坑是**日志侧与产物侧标记串不同**，只认一侧会
  数出 0 然后被误读成「出口没通」。这里结构化侧给主判据，md 侧做交叉核对，
  两侧都不一致时在表里标 `?`，不猜。
"""
from __future__ import annotations

# ── [v1.23.64] 终端编码兜底：Windows 管道下默认 cp936，打印非 ASCII 会崩 ──
import sys as _sys_utf8
for _s_utf8 in (_sys_utf8.stdout, _sys_utf8.stderr):
    try:
        _s_utf8.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "bench"))
from bench_score import score_actions, score_research_packed  # noqa: E402

OBJECTIVES = {"修行层": "manifest", "研究层": "truth",
              "对撞层": "collision", "元层": "closure"}


def _load_packed(item):
    p = item.get("md")
    if not p:
        return {}
    d = Path(p).parent
    for name in ("packed.json", "result.json"):
        f = d / name
        if f.is_file():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {}


def _md_text(item):
    p = item.get("md")
    if p and Path(p).is_file():
        try:
            return Path(p).read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""


def _layer_targets(md: str):
    """数产物头部「分层目标」那四行，并取出每行的 objective。"""
    out = {}
    for ln in md.splitlines():
        m = re.match(r"\s+- (修行层|研究层|对撞层|元层)（[^）]*"
                     r"objective=(\w+)）", ln)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _stability_ratio(packed):
    sq = ((packed.get("pools") or {}).get("1") or {}).get(
        "sub_questions") or []
    if not sq:
        return None, 0, 0, 0
    hi = sum(1 for s in sq if s.get("stability") == "high")
    me = sum(1 for s in sq if s.get("stability") == "medium")
    lo = sum(1 for s in sq if s.get("stability") == "low")
    return (hi + me) / len(sq), hi, me, lo


def main():
    if len(sys.argv) < 2:
        print("用法：bench_report.py <run_dir>")
        return 1
    d = Path(sys.argv[1])
    idxf = d / "index.json"
    if not idxf.is_file():
        print(f"缺 {idxf}")
        return 1
    idx = json.loads(idxf.read_text(encoding="utf-8"))
    # ★ 题目清单按**目录**枚举 meta.json，不只用 index.json：
    #   续跑（`--skip-existing`）时 index.json 只含本批跑的那些题，
    #   20 题的交付要求会被一份 17 行的报告悄悄打破。
    items = []
    for d0 in sorted(p for p in d.iterdir() if p.is_dir()):
        mf = d0 / "meta.json"
        if mf.is_file():
            try:
                items.append(json.loads(mf.read_text(encoding="utf-8")))
            except Exception:
                pass
    if not items:
        items = list(idx.get("items") or [])
    # 覆盖说明取所有来源，任一来源记过就算（续跑时两批的覆盖可能相同）
    _po = idx.get("profile_override") or ""
    _ro = idx.get("rounds_override") or ""
    lines = [f"# bench 全量报告 · {idx['tag']}", ""]
    _n_ok = sum(1 for x in items if x.get("ok"))
    lines += [f"- src：`{idx['src']}`　mock：{idx['mock']}　"
              f"产物 {_n_ok}/{len(items)}",
              f"- profile 覆盖：`{_po or '（用题目配置）'}`"
              f"　rounds 覆盖：`{_ro or '（用题目配置）'}`",
              f"- 题目来源：按目录枚举 `meta.json`（{len(items)} 题）"]
    if _po or _ro:
        lines += ["- ⚠️ **本批为降档跑**（预算受限）：原始档见题目 yaml；"
                  "原始档的真跑证据在阶段 1 的 `bench/runs/p1v2`。"]
    lines += ["",
              "| 题 | 取向 | 判定 | 一致率 | 分层 pass | rubric | 层 | 调用 |",
              "|---|---|---|---|---|---|---|---|"]
    n_pass = 0
    rub_sum, rub_n = 0, 0
    ratio_n = 0
    for it in items:
        pk = _load_packed(it)
        md = _md_text(it)
        r = score_research_packed(pk) if pk else {}
        dec = (pk.get("decidability") or {}).get("decidability") or "?"
        ratio, hi, me, lo = _stability_ratio(pk)
        if ratio is None:
            ratio_s, ratio_note = "N/A", ""
            m = re.search(r"一致率 (\d+(?:\.\d+)?)%", md)
            if m:
                ratio_s, ratio_note = f"{m.group(1)}%", "（md 侧）"
        else:
            ratio_s = f"{ratio:.0%}"
            ratio_note = f"（{hi}/{me}/{lo}）"
            ratio_n += 1
        tg = _layer_targets(md)
        pass4 = (len(tg) == 4
                 and all(tg.get(k) == v for k, v in OBJECTIVES.items()))
        if pass4:
            n_pass += 1
        _vs = pk.get("views") or {}
        _all = _vs.get("all") or {}
        _l1 = _vs.get("1") or {}
        # 新 packed：actions 在 all / 顶层；旧 packed：兼容 views.1._actions。
        acts = (_all.get("actions") or pk.get("actions")
                or _l1.get("_actions") or [])
        not_do = (_all.get("not_do") or pk.get("not_do")
                  or _l1.get("_not_do") or [])
        rb = score_actions(acts, not_do) if pk else None
        if isinstance(rb, dict):
            rub_sum += rb["score"]
            rub_n += 1
            rb_s = f"{rb['score']}/{rb['max']}"
        else:
            rb_s = "N/A"
        lines.append(
            f"| {it['id']} | {it.get('orientation')} | {dec} | "
            f"{ratio_s}{ratio_note} | {'✅' if pass4 else '❌'} | {rb_s} | "
            f"{'、'.join(sorted(it.get('layers_seen') or []))} | "
            f"{it.get('calls', '-')} |")
    lines += ["", f"**分层 pass**：{n_pass}/{len(items)}　"
                  f"**一致率可算**：{ratio_n}/{len(items)}"
                  + (f"　**rubric 平均**：{rub_sum/rub_n:.2f}/3"
                     if rub_n else "")]
    out = "\n".join(lines)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
