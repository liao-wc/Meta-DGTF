# -*- coding: utf-8 -*-
"""[V2.2.90] 研究层拆解确定性回退单测。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dgtf_v2.decompose_fallback import (  # noqa: E402
    answerable_fallback, fallback_subquestions)

_P, _F = [], []


def ck(name, ok, detail=""):
    (_P if ok else _F).append(name)
    print(("PASS " if ok else "FAIL ") + name + ("  — " + str(detail) if not ok else ""))


def main() -> int:
    probes = [
        {"question": "夜间热岛强度与风速的关系是什么？"},
        {"question": "城市材料热容对夜间降温速率的影响？"},
        {"question": ""},
        "not-a-dict",
    ]
    threads = [{"desc": "边界层稳定度如何量化？"}]
    subs = fallback_subquestions(probes, threads)
    ck("F1 探针优先生成子问题", len(subs) == 3, "n=%d" % len(subs))
    ck("F2 子问题可追溯 source",
       [s["source"] for s in subs][:2] == ["P1", "P2"],
       str([s["source"] for s in subs]))
    ck("F3 保守标 partial 且状态 open",
       all(s["decidability"] == "partial" and s["status"] == "open"
           for s in subs))
    ck("F4 空输入返回 []", fallback_subquestions([], []) == [])
    ck("F5 limit 生效", len(fallback_subquestions(probes, threads, limit=2)) == 2)
    ck("F6 线头兜底（无探针时）",
       [s["source"] for s in fallback_subquestions([], threads)] == ["T1"])
    all_und = [{"question": "甲问题？", "decidability": "undecidable",
                "id": 1, "source": ""}]
    fb = answerable_fallback(all_und, probes, threads)
    ck("F7 全不可判定时补 provisional partial", len(fb) >= 1 and
       all(s["decidability"] == "partial" for s in fb), "n=%d" % len(fb))
    ck("F8 补的 source 带 FB: 前缀",
       all(str(s["source"]).startswith("FB:") for s in fb),
       str([s["source"] for s in fb]))
    mixed = [{"question": "乙问题？", "decidability": "partial", "id": 1}]
    ck("F9 有可答子问题时不动", answerable_fallback(mixed, probes) == [])
    print("PASS %d / FAIL %d" % (len(_P), len(_F)))
    return 1 if _F else 0


if __name__ == "__main__":
    raise SystemExit(main())
