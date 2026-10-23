#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 附6C Step 8.1] 拆模块方案的依赖分析（**只出方案，不落地**）。

做什么：
  1. 取全库顶层符号（函数 / 类 / 模块级常量名）；
  2. 用「符号体里是否出现另一个顶层符号名」建依赖边（词法近似，
     不解析作用域 —— 目的是**找圈**和量级，不是做编译器）；
  3. 数互相依赖的环（SCC 近似：双向边即成环）；
  4. 按命名前缀给一份候选模块划分，并统计跨模块边占比。

不做：真的拆。任务书 6C 明说只出报告。
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 候选模块：前缀 / 名字谓词 → 模块名
PREFIX_MODULES = [
    ("_ANCHOR", "anchors"), ("AnchorRetriever", "anchors"),
    ("_anchor", "anchors"),
    ("_DEC_", "decidability"), ("DecidabilityFreeze", "decidability"),
    ("_adjudicate", "decidability"), ("apply_decidability", "decidability"),
    ("_TRI_VOTE", "decidability"), ("_classify_unsaid", "decidability"),
    ("coverage_", "decidability"),
    ("_ACTION_", "render"), ("_extract_", "render"), ("_guess_", "render"),
    ("render_", "render"), ("_render_", "render"), ("_pool_meta", "render"),
    ("_layer_objective", "render"), ("save_result", "render"),
    ("_spiral", "spiral"), ("_stop_reasons", "spiral"),
    ("_carry_", "spiral"), ("_damp", "spiral"),
    ("DEFAULT_CONFIG", "config"), ("load_config", "config"),
    ("_deep_merge", "config"),
    ("LLM", "llm"), ("_is_reasoner", "llm"),
    ("Pool", "pools"), ("View", "pools"), ("Phase", "pools"),
    ("Input", "pools"), ("PHASE_", "pools"), ("PHASES", "pools"),
    ("auto_plan", "meta"), ("plan_orientation", "meta"),
    ("plan_resources", "meta"), ("MetaDGTF", "meta"),
    ("_probe", "meta"), ("_audit", "meta"),
    ("main", "main"), ("_ask_", "main"), ("_validate_", "main"),
    ("_warmup", "lifecycle"), ("_dispatch", "lifecycle"),
    ("_run_", "lifecycle"), ("_b_", "lifecycle"), ("_finalize", "lifecycle"),
    ("_route", "lifecycle"), ("_settle", "lifecycle"),
]


def _module_of(name: str) -> str:
    for pre, mod in PREFIX_MODULES:
        if name.startswith(pre):
            return mod
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="元DGTF-V1.22.0-rc1.py")
    ap.add_argument("--out", default="_v122_phase7_modules.json")
    a = ap.parse_args()
    src = HERE / a.src
    text = src.read_text(encoding="utf-8")
    tree = ast.parse(text)

    top = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            top[n.name] = n
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    top[t.id] = n
    names = sorted(top)
    print(f"顶层符号 {len(names)} 个")

    # 依赖边：把每个符号的源码片段拿出来，扫别的顶层符号名
    lines = text.replace("\r\n", "\n").split("\n")
    frag = {}
    for k, n in top.items():
        e = getattr(n, "end_lineno", None) or n.lineno
        frag[k] = "\n".join(lines[n.lineno - 1:e])
    edges = set()
    for k, body in frag.items():
        for other in names:
            if other == k or len(other) < 3:
                continue
            if other in body:
                edges.add((k, other))
    print(f"依赖边 {len(edges)} 条")

    mutual = sorted({tuple(sorted((a_, b_))) for a_, b_ in edges
                     if (b_, a_) in edges and a_ != b_})
    print(f"双向边（互相依赖，成环的强证据）{len(mutual)} 对")

    mod_of = {k: _module_of(k) for k in names}
    cross = [(a_, b_) for a_, b_ in edges if mod_of[a_] != mod_of[b_]]
    n_mod = Counter(mod_of.values())
    cross_pairs = Counter(tuple(sorted((mod_of[a_], mod_of[b_])))
                          for a_, b_ in cross)
    print(f"跨模块边 {len(cross)} 条 / 总边 {len(edges)} 条 "
          f"（{len(cross) / max(1, len(edges)):.0%}）")

    out = {
        "src": a.src,
        "n_top_symbols": len(names),
        "n_edges": len(edges),
        "n_mutual_edges": len(mutual),
        "n_cross_edges": len(cross),
        "cross_ratio": round(len(cross) / max(1, len(edges)), 3),
        "modules": dict(n_mod.most_common()),
        "top_cross_pairs": {f"{k[0]} <-> {k[1]}": v
                            for k, v in cross_pairs.most_common(12)},
        "mutual_sample": [" <-> ".join(x) for x in mutual[:20]],
    }
    (HERE / a.out).write_bytes(json.dumps(
        out, ensure_ascii=False, indent=2).encode("utf-8"))
    print(f"→ {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
