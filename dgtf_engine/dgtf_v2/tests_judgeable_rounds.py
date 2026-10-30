# -*- coding: utf-8 -*-
"""[V2.2.92] 层1 可判定化：auto min_rounds 纯函数单测。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dgtf_v2.judgeable_rounds import (  # noqa: E402
    enabled, judgeable_min_rounds, judgeable_rounds_plan, layers, target)

_P, _F = [], []


def ck(name, ok, detail=""):
    (_P if ok else _F).append(name)
    print(("PASS " if ok else "FAIL ") + name + ("  — " + str(detail) if not ok else ""))


def main() -> int:
    off = {"spiral": {}}
    ck("J1 默认关闭 enabled=False", enabled(off) is False)
    plan, ch = judgeable_rounds_plan(off, {"1": 2, "both": 2})
    ck("J2 默认关闭不改计划", (not ch) and plan == {"1": 2, "both": 2}, str(plan))
    ck("J3 默认关闭不改 min_rounds",
       judgeable_min_rounds(off, "1", None) == {})
    on = {"spiral": {"min_rounds_judgeable": True}}
    plan2, ch2 = judgeable_rounds_plan(on, {"1": 2, "both": 2, "0": 2})
    ck("J4 开启后研究/对撞抬到 3", ch2 and plan2 == {"1": 3, "both": 3, "0": 2},
       str(plan2))
    ck("J5 target 默认 3", target(on) == 3)
    ck("J6 min_rounds 合并（保留已有更大值）",
       judgeable_min_rounds(on, "1", {"1": 4, "0": 2}) == {"1": 4, "0": 2})
    ck("J7 非目标层不抬", judgeable_min_rounds(on, "0", {"0": 2}) == {"0": 2})
    custom = {"spiral": {"min_rounds_judgeable": True,
                         "min_rounds_judgeable_layers": ["1"],
                         "min_rounds_judgeable_target": 4}}
    plan3, ch3 = judgeable_rounds_plan(custom, {"1": 2, "both": 2})
    ck("J8 自定义层/目标生效", ch3 and plan3 == {"1": 4, "both": 2}, str(plan3))
    ck("J9 layers 归一为字符串", layers(custom) == ["1"])
    bad = {"spiral": {"min_rounds_judgeable": True,
                      "min_rounds_judgeable_target": "x"}}
    ck("J10 非法 target 回退默认", target(bad) == 3)
    print("PASS %d / FAIL %d" % (len(_P), len(_F)))
    return 1 if _F else 0


if __name__ == "__main__":
    raise SystemExit(main())
