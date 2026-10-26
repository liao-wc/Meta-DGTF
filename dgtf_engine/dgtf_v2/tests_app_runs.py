# -*- coding: utf-8 -*-
"""App 维度实测矩阵判据（Round 27）。"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.mode_fusion import (app_runs_summary,  # noqa: E402
                                 measured_app_runs)

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


def main():
    rows = measured_app_runs()
    ck("① 行数 = 9（App e2e 真跑）", len(rows) == 9, len(rows))
    need = {"id", "mode", "tier", "scenario", "question", "quality",
            "tokens", "calls", "wall", "verified", "ready", "plan"}
    ck("② 必需字段齐全", all(need.issubset(set(r)) for r in rows),
       [sorted(need - set(r)) for r in rows if not need.issubset(set(r))])
    ck("③ 所有 App 跑次 verified/ready",
       all(r["verified"] is True and r["ready"] is True for r in rows))
    ck("④ quality ∈ (0,1]、tokens>0、calls>0",
       all(0 < float(r["quality"]) <= 1 and int(r["tokens"]) > 0
           and int(r["calls"]) > 0 for r in rows))
    ck("⑤ fast 档存在 reasoning 与 fact 两场景",
       {r["scenario"] for r in rows if r["tier"] == "fast"} ==
       {"reasoning", "fact"},
       {r["scenario"] for r in rows if r["tier"] == "fast"})
    summ = app_runs_summary()
    ck("⑥ 聚合按 (scenario,tier) 共 3 组", len(summ) == 3, summ)
    fact_fast = [x for x in summ if x["scenario"] == "fact"
                 and x["tier"] == "fast"][0]
    fact_qual = [x for x in summ if x["scenario"] == "fact"
                 and x["tier"] == "quality"][0]
    ck("⑦ fact fast 比 quality 省 tokens",
       fact_fast["tokens_mean"] < fact_qual["tokens_mean"],
       (fact_fast["tokens_mean"], fact_qual["tokens_mean"]))
    ck("⑧ 聚合 verified/ready 率均为 1.0",
       all(x["verified_ratio"] == 1.0 and x["ready_ratio"] == 1.0
           for x in summ))
    ck("⑨ 确定性：两次聚合一致", app_runs_summary() == summ)
    ck("⑩ 副本隔离：修改返回值不影响源数据",
       (measured_app_runs()[0].__setitem__("quality", 0.0) or True)
       and measured_app_runs()[0]["quality"] != 0.0)

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
