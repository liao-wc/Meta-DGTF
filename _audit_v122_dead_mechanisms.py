#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段5 G5.1/G5.2] 机制审计（**只标不删**）。

用法：
    python _audit_v122_dead_mechanisms.py [--src 元DGTF-V1.22.0-rc1.py]

产出：`audit_v122_dead_mechanisms.md`

三列命中数，各自的口径：
  · `src_hits`  —— 源码里出现这个机制名的次数（机制**存在**的证据）；
  · `log_hits`  —— 运行日志里的次数（引擎内部标记，verbose/诊断行）；
  · `prod_hits` —— 产物 md 里的次数（**读者能看到的**出口）。

★ 为什么日志侧与产物侧要分开数：本项目的已知坑 —— 同一件事的标记串在
  日志侧与产物侧常常**不同**（例如「螺旋停止」在日志是 `【螺旋停止】…`、
  在产物是 `**螺旋停止**：…`）。照一侧去数另一侧会数出 0，然后被误读成
  「出口没通」。所以这里两侧都数，并在表里写明各自用的标记串。

判定只用一句话：**「零触发」不等于「没用」**。verdict 给三档之一：
  可达    —— 日志或产物侧有命中，机制确实在出口上；
  仅源码  —— 只在源码里出现，说明有实现但本批产物里没被触发；
  需核对  —— 源码里也没有这个字面串（可能名字对不上，要人工看）。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

# (机制名, 触发条件, 日志侧标记串, 产物侧标记串)
#   ★ 标记串为空时回落到机制名本身。
MECHS = [
    ("escalate_starve_rounds", "连续 N 圈无进展 + 名下有账",
     "escalate_starve_rounds", "escalate_starve_rounds"),
    ("no_push_when_idle", "空转类判据 + 未深入方向",
     "no_push_when_idle", "no_push_when_idle"),
    ("_reopen_closed_debt", "分类被推翻 + 曾有 escalated",
     "_reopen_closed_debt", "_reopen_closed_debt"),
    ("stable_layers", "悬置连续 N 圈同批", "stable_layers", "stable_layers"),
    ("both_quota.max_ratio", "both 占比超阈值",
     "both_quota", "both_quota"),
    ("both_tighten_ratio", "同上，改判", "both_tighten_ratio",
     "both_tighten_ratio"),
    ("_all_settle_streak", "元层清算未下降",
     "_all_settle_streak", "_all_settle_streak"),
    ("min_rounds", "layer_no < min_r", "min_rounds", "min_rounds"),
    ("structure_saturation", "每 N 圈无新维度",
     "structure_saturation", "structure_saturation"),
    ("_budget_exhausted", "调用数超预算", "_budget_exhausted",
     "_budget_exhausted"),
    ("DecidabilityFreeze.verify", "签名不匹配",
     "DecidabilityFreeze", "freeze"),
    ("triage_downgrades", "信息不足型 und + 锚点命中",
     "triage_downgrades", "triage 降级"),
    ("_anchor_crosscheck.conflict", "结论与锚点相反",
     "锚点冲突", "锚点冲突"),
]


def _scan(paths, needle: str) -> int:
    n = 0
    for p in paths:
        try:
            n += p.read_text(encoding="utf-8", errors="replace").count(needle)
        except Exception:
            continue
    return n


def _collect():
    logs = []
    for pat in ("*.log", "runs/v122/*.log", "bench/runs/**/*.log",
                "bench/runs/**/stdout.log", "bench/runs/**/stderr.log"):
        logs += [p for p in HERE.glob(pat) if p.is_file()]
    prods = []
    for pat in ("outputs/*.md", "bench/runs/**/*.md", "bench/reports/*.md"):
        prods += [p for p in HERE.glob(pat) if p.is_file()]
    # 去重（同一个文件可能被多個 glob 命中）
    logs = sorted(set(logs), key=lambda p: str(p))
    prods = sorted(set(prods), key=lambda p: str(p))
    return logs, prods


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="元DGTF-V1.22.0-rc1.py")
    a = ap.parse_args()
    src = HERE / a.src
    st = src.read_text(encoding="utf-8") if src.is_file() else ""
    logs, prods = _collect()

    rows = []
    for name, cond, lmark, pmark in MECHS:
        sh = st.count(name)
        lh = _scan(logs, lmark or name)
        ph = _scan(prods, pmark or name)
        if lh + ph > 0:
            v = "可达"
        elif sh > 0:
            v = "仅源码"
        else:
            v = "需核对"
        rows.append({"mechanism": name, "condition": cond,
                     "log_mark": lmark or name, "prod_mark": pmark or name,
                     "src_hits": sh, "log_hits": lh, "prod_hits": ph,
                     "verdict": v})

    n_reach = sum(1 for r in rows if r["verdict"] == "可达")
    n_src = sum(1 for r in rows if r["verdict"] == "仅源码")
    n_chk = sum(1 for r in rows if r["verdict"] == "需核对")
    lines = [
        "# 机制审计 v122",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 被测源码：`{a.src}`",
        f"- 语料：日志 {len(logs)} 份 / 产物 {len(prods)} 份",
        f"- 合计：可达 {n_reach} · 仅源码 {n_src} · 需核对 {n_chk}"
        f"（共 {len(rows)} 项）",
        "",
        "★ 「零触发」不等于「没用」。verdict 只要不是 `需核对`，都说明机制"
        "在源码里存在、只是本批产物没走到那条分支 —— 要区分"
        "「条件不可达」「条件窄但成立」「机制压根没工作」需要**负对照**，"
        "那张表在 `docs/机制审计-v122.md` 的 `## pending_fix` 里。",
        "",
        "| 机制 | 触发条件 | 日志标记 | 产物标记 | 源码 | 日志 | 产物 | 判定 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['mechanism']}` | {r['condition']} | "
            f"`{r['log_mark']}` | `{r['prod_mark']}` | {r['src_hits']} | "
            f"{r['log_hits']} | {r['prod_hits']} | {r['verdict']} |")
    lines += ["", "## 语料清单", "", f"日志（{len(logs)}）："]
    lines += [f"- `{p.relative_to(HERE)}`" for p in logs[:40]]
    lines += ["", f"产物（{len(prods)}）："]
    lines += [f"- `{p.relative_to(HERE)}`" for p in prods[:40]]

    out = HERE / "audit_v122_dead_mechanisms.md"
    out.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    (HERE / "_audit_v122_result.json").write_bytes(json.dumps(
        {"rows": rows, "n_logs": len(logs), "n_prods": len(prods),
         "n_reach": n_reach, "n_src_only": n_src, "n_check": n_chk},
        ensure_ascii=False, indent=2).encode("utf-8"))
    print(f"audit -> {out.name}"
          f"（可达 {n_reach} / 仅源码 {n_src} / 需核对 {n_chk}；"
          f"日志 {len(logs)} 份 · 产物 {len(prods)} 份）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
