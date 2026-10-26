# -*- coding: utf-8 -*-
"""ab_bench 重复真跑守卫判据（Round 132，零 API）。

G1 同题+同 web 的 valid verified 记录 ⇒ 命中（拒绝）
G2 不同题 / 低质量 / invalid / web 不匹配 ⇒ 不命中
G3 guardian 默认拒绝语义：cmd_run 参数存在 --allow-repeat
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


def load_ab():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("ab_bench_guard_test",
                                                  str(ROOT / "scripts" / "ab_bench.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["ab_bench_guard_test"] = m
    spec.loader.exec_module(m)
    return m


def main() -> int:
    ab = load_ab()
    tmp = Path(tempfile.mkdtemp(prefix="ab_guard_"))
    f = tmp / "ab_results.jsonl"
    rows = [
        {"tag": "a", "question": "HTTP 201状态码表示什么？", "valid": True,
         "quality": 0.95, "engine_args": ["--web", "on"], "ts": "x"},
        {"tag": "b", "question": "低质量题", "valid": True,
         "quality": 0.50, "engine_args": ["--web", "on"], "ts": "x"},
        {"tag": "c", "question": "无效题", "valid": False,
         "quality": 0.99, "engine_args": ["--web", "on"], "ts": "x"},
        {"tag": "d", "question": "无网题", "valid": True,
         "quality": 0.99, "engine_args": ["--web", "off"], "ts": "x"},
    ]
    f.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    old = ab.AB_RESULTS
    try:
        ab.AB_RESULTS = f
        hit = ab._find_verified_duplicate("HTTP 201状态码表示什么？", web="on")
        ck("G1 同题 verified 命中", bool(hit) and hit.get("tag") == "a", hit)
        ck("G2a 不同题不命中",
           ab._find_verified_duplicate("HTTP 204状态码表示什么？", web="on") is None)
        ck("G2b 低质量不命中",
           ab._find_verified_duplicate("低质量题", web="on") is None)
        ck("G2c invalid 不命中",
           ab._find_verified_duplicate("无效题", web="on") is None)
        ck("G2d web 模式不匹配不命中",
           ab._find_verified_duplicate("无网题", web="on") is None)
        ck("G2e 空白/标点归一后命中",
           bool(ab._find_verified_duplicate(" HTTP 201 状态码表示什么 ", web="on")))
    finally:
        ab.AB_RESULTS = old
    src = (ROOT / "scripts" / "ab_bench.py").read_text(encoding="utf-8")
    ck("G3 --allow-repeat 与拒绝文案存在",
       "--allow-repeat" in src and "拒绝重复真跑" in src)
    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
