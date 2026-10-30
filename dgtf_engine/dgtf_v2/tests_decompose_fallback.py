# -*- coding: utf-8 -*-
"""[V2.2.90] 研究层拆解确定性回退单测。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dgtf_v2.decompose_fallback import fallback_subquestions  # noqa: E402

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
    print("PASS %d / FAIL %d" % (len(_P), len(_F)))
    return 1 if _F else 0


if __name__ == "__main__":
    raise SystemExit(main())
