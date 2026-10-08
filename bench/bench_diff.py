#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段1 G1.10] bench 两次跑动的差分。

用法：
    python bench/bench_diff.py bench/runs/<A> bench/runs/<B>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def _load(d: str):
    p = Path(d)
    if p.is_dir():
        p = p / "index.json"
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    if len(sys.argv) < 3:
        print("用法：bench_diff.py <runA> <runB>")
        return 1
    A, B = _load(sys.argv[1]), _load(sys.argv[2])
    ia = {i["id"]: i for i in A["items"]}
    ib = {i["id"]: i for i in B["items"]}
    ids = sorted(set(ia) | set(ib))
    print(f"# bench 差分：{A['tag']} → {B['tag']}\n")
    print("| id | calls A | calls B | Δcalls | tokens A | tokens B | Δtokens |"
          " 秒 A | 秒 B | ok |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    tc = tt = 0
    for i in ids:
        a, b = ia.get(i, {}), ib.get(i, {})
        ca, cb = a.get("calls", 0), b.get("calls", 0)
        ta, tb = a.get("tokens", 0), b.get("tokens", 0)
        tc += (cb - ca)
        tt += (tb - ta)
        print(f"| {i} | {ca} | {cb} | {cb-ca:+d} | {ta} | {tb} | {tb-ta:+d} | "
              f"{a.get('elapsed_s','-')} | {b.get('elapsed_s','-')} | "
              f"{a.get('ok')}/{b.get('ok')} |")
    print(f"\n**合计**：Δcalls={tc:+d}　Δtokens={tt:+d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
