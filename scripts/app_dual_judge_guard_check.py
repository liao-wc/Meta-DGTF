# -*- coding: utf-8 -*-
"""dual_judge local 防护判据（Round 58，离线）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dgtf_app"))
sys.path.insert(0, str(ROOT / "dgtf_engine"))
sys.path.insert(0, str(ROOT))

import daosheng_mode as dm  # noqa: E402

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


def main():
    real_preset = dm.load_preset

    def preset_with(value):
        ds = dict(real_preset())
        ds["dual_judge_mode"] = value
        return ds

    for value, expect in (("local", "llm"), ("llm", "llm"), ("auto", "auto")):
        dm.load_preset = lambda v=value: preset_with(v)
        try:
            plan = dm.build_plan("2024年中国GDP增速最新数据是多少？", {},
                                 requested="daosheng", is_mock=True,
                                 balance_cny=999.0)
        finally:
            dm.load_preset = real_preset
        ck("dual_judge_mode=%s → %s" % (value, expect),
           str(plan.get("dual_judge_mode")) == expect, plan.get("dual_judge_mode"))
        if value == "local":
            ck("local 回退 via 标记",
               plan.get("dual_judge_mode_via") == "local-unsupported-fallback",
               plan.get("dual_judge_mode_via"))
            ck("local 回退 warning",
               any("dual_judge" in str(x) for x in (plan.get("warnings") or [])))
        else:
            ck("%s 不被改写" % value,
               plan.get("dual_judge_mode_via") != "local-unsupported-fallback")
    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
