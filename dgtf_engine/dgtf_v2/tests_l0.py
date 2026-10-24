# -*- coding: utf-8 -*-
"""Phase 5 · L0-v2 判据（独立内核，不依赖生产引擎）。"""
import glob
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dgtf_v2.layers_l0 import (
    L0V2Strategy, MapElitesArchive, ThompsonProbeSelector, heaps_slope,
    evaluate_packed, tokens, jaccard,
)

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("  OK  " if ok else "  FAIL") + " " + name +
          (("  — " + str(detail)) if detail else ""))


def main():
    a = MapElitesArchive(capacity=2)
    check("novelty：空档案为 1", abs(a.novelty("x") - 1.0) < 1e-9)
    check("add：新格接收", a.add("远程办公信任", "0", 0.5))
    check("add：同格低分拒绝", not a.add("远程办公信任", "0", 0.4))
    check("novelty：重复为 0", a.novelty("远程办公信任") < 1e-9)
    a.add("结果验收", "1", 0.7)
    a.add("第三方仲裁", "both", 0.8)
    check("capacity：不超上限", len(a.cells) <= 2, len(a.cells))

    s = L0V2Strategy(elite_quota=3, novelty_floor=0.2)
    dup = [{"desc": "同一句", "position": "0"} for _ in range(5)]
    o = s.curate(dup, 1)
    check("curate：重复只收 1", len(o["accepted"]) == 1, o)
    new = [{"desc": "完全不同甲", "position": "0"},
           {"desc": "完全不同乙", "position": "1"},
           {"desc": "完全不同丙", "position": "both"}]
    o2 = s.curate(new, 2)
    check("curate：新描述可进", len(o2["accepted"]) >= 1, o2["accepted"])
    check("history：两圈", len(s.history) == 2, s.history)

    s3 = L0V2Strategy()
    obs = s3.observe([{"desc": "观察甲", "position": "0"},
                      {"desc": "观察乙", "position": "1"},
                      {"desc": "观察甲", "position": "0"}], 1)
    check("observe：不裁剪，全量观察", obs["observed"] == 3, obs)
    check("observe：有方向提示", bool(obs.get("directions")), obs.get("directions"))

    h = [{"round": 1, "cells": 1}, {"round": 2, "cells": 2},
         {"round": 3, "cells": 2}, {"round": 4, "cells": 2}]
    check("heaps：饱和斜率低", heaps_slope(h) < 1.0, heaps_slope(h))
    s2 = L0V2Strategy()
    s2.curate([], 1)
    s2.curate([], 2)
    check("stop：连续无接收则停", s2.should_stop(window=2), s2.history)

    t = ThompsonProbeSelector(seed=3)
    ps = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    check("thompson：选 k 个", len(t.pick(ps, 2)) == 2)
    t.update("a", True)
    check("thompson：后验更新", t.alpha["a"] == 2.0 and t.beta["a"] == 1.0)

    check("tokens/jaccard 正常",
          bool(tokens("远程办公 信任")) and jaccard(tokens("ab"), tokens("ab")) == 1.0)

    fs = sorted(glob.glob("outputs/20261019_08*.packed.json"), key=os.path.getmtime)
    if fs:
        e = evaluate_packed(fs[-1])
        check("真实 packed 回放", e["candidates"] > 0 and e["accepted"] > 0, e)
    elif os.getenv("DGTF_REQUIRE_REPLAY") == "1":
        check("真实 packed 回放", False, "no packed (DGTF_REQUIRE_REPLAY=1)")
    else:
        # CI 是干净 checkout：outputs/ 不入库，本地回放检查显式 SKIP（不是假绿）。
        print("  · SKIP 真实 packed 回放（无 outputs 回放数据）")

    print("\nPASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print("  - " + f)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
