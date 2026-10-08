#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段6 补] G6.4 的负对照：同一文件两次跑，差分量级是多少？

背景：任务书 Step 6.4 的判据是「rc1 与定稿的产物排掉时间戳后**逐字一致**」。
实测 **DIFF**（218155 vs 238349 字节）。但这**不说明行为变了** ——
引擎每一步都是独立抽样，两次跑本来就不会逐字相同。

正确的处理（本项目的测量学纪律）：**补负对照**。
  跑两次**同一个定稿文件**（参数完全相同），量出「同文件两次跑」的差异；
  再拿 rc1→定稿 的差异跟它比。若两者同量级，那么 rc1→定稿 的差异
  **不含信号** —— 「逐字一致」这条判据本身在这个引擎上不可达。

同时给出**可达的**等价判据：结构化字段（路由 / 调度 / 圈数 / 层集合 /
头部那些**计数**标记的**存在性**）是否一致。
"""
from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OBJECTIVE_MARKS = ("修行层", "研究层", "对撞层", "元层")
HEAD_MARKS = ("**路由**", "**调度**", "**并行模式**", "**成本档位**",
              "**分层目标**", "**三态多票**", "**冻结**",
              "**机制审计**", "## 落地层")


def _strip(p: Path):
    return "\n".join(ln for ln in p.read_text(encoding="utf-8").splitlines()
                     if not ln.startswith("**时间**"))


def _diff(a: str, b: str) -> dict:
    la, lb = a.split("\n"), b.split("\n")
    sm = difflib.SequenceMatcher(None, la, lb)
    chg = sum(max(x[2] - x[1], x[4] - x[3])
              for x in sm.get_opcodes() if x[0] != "equal")
    return {"lines_a": len(la), "lines_b": len(lb), "changed_lines": chg,
            "same_lines": sum(x[2] - x[1] for x in sm.get_opcodes()
                              if x[0] == "equal")}


def _struct(text: str) -> dict:
    return {"head_marks": {k: (k in text) for k in HEAD_MARKS},
            "has_4_layer_targets": all(
                any(k in ln and "objective=" in ln for ln in text.splitlines())
                for k in OBJECTIVE_MARKS),
            "decision_landing": "落地层（decision 模式）" in text,
            "action_section": "### 二、行动清单" in text,
            "audit_line_pending": "pending_fix" in text}


def main() -> int:
    before = HERE / "_v122_phase6_before.md"
    after = HERE / "_v122_phase6_after.md"
    c1 = HERE / "_v122_ctrl1.md"
    c2 = HERE / "_v122_ctrl2.md"
    out = {}
    if before.is_file() and after.is_file():
        a, b = _strip(before), _strip(after)
        out["rc1_vs_final"] = _diff(a, b)
        out["rc1_struct"] = _struct(a)
        out["final_struct"] = _struct(b)
        out["rc1_vs_final_struct_equal"] = (_struct(a) == _struct(b))
    if c1.is_file() and c2.is_file():
        x, y = _strip(c1), _strip(c2)
        out["same_file_negative_control"] = _diff(x, y)
        out["same_file_struct_equal"] = (_struct(x) == _struct(y))
    # before/after 的头部逐行对照（只打头部 40 行，便于人核）
    if before.is_file() and after.is_file():
        ha = _strip(before).split("\n")[:40]
        hb = _strip(after).split("\n")[:40]
        out["head_diff_lines"] = [
            f"- {x}" for x in ha if x not in hb] + [
            f"+ {y}" for y in hb if y not in ha]
    (HERE / "_v122_phase6_g64.json").write_bytes(json.dumps(
        out, ensure_ascii=False, indent=2).encode("utf-8"))
    print(json.dumps(out, ensure_ascii=False, indent=2)[:2500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
