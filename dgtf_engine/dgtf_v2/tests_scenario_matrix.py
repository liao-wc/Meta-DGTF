# -*- coding: utf-8 -*-
"""实测场景矩阵判据（2026-10-25 Round 4）：场景/模式表 + 推荐规则。

覆盖：
  · 矩阵形状与必需字段（reasoning/choice/fact，共 7 行实测）；
  · fact 档的硬约束（必须 web、thinking 不可关、无证据档不可用）；
  · kind_of_question 题面分桶；
  · recommend_scenario 的 quality/wall/tokens 偏好、约束回退、未知场景兜底。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dgtf_v2.mode_fusion import (MEASURED_SCENARIOS, kind_of_question,  # noqa: E402
                                 measured_matrix, recommend_scenario)

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


def main():
    rows = measured_matrix()
    ck("矩阵行数 = 7（reasoning 3 / choice 1 / fact 3）", len(rows) == 7, len(rows))
    ck("三个场景桶齐全",
       set(MEASURED_SCENARIOS) == {"reasoning", "choice", "fact"},
       list(MEASURED_SCENARIOS))
    need = {"scenario", "label", "mode", "question", "quality", "verified",
            "tokens", "calls", "wall", "config"}
    ck("每行字段齐全", all(need.issubset(set(r)) for r in rows),
       [sorted(need - set(r)) for r in rows if not need.issubset(set(r))])
    ck("所有 quality/tokens/wall 为正数",
       all(float(r["quality"] or 0) > 0 and int(r["tokens"] or 0) > 0
           and float(r["wall"] or 0) > 0 for r in rows))

    fact = MEASURED_SCENARIOS["fact"]
    ck("fact：web_on_auto 为 verified", fact["runs"]["web_on_auto"]["verified"] is True)
    ck("fact：web_off_auto 与 web_on_fast 均未 verified",
       fact["runs"]["web_off_auto"]["verified"] is False
       and fact["runs"]["web_on_fast"]["verified"] is False)
    ck("fact：规则强制联网 + 禁用档位",
       fact["rules"]["requires_web"] is True
       and "web_off_auto" in fact["rules"]["forbid"]
       and "web_on_fast" in fact["rules"]["forbid"])

    rea = MEASURED_SCENARIOS["reasoning"]
    ck("reasoning：quality_first=auto / cost_first=fast",
       rea["rules"]["quality_first"] == "auto"
       and rea["rules"]["cost_first"] == "fast")
    ck("reasoning：fast 墙钟 < auto 墙钟（成本档成立）",
       rea["runs"]["fast"]["wall"] < rea["runs"]["auto"]["wall"])

    ck("分桶：为什么…→reasoning",
       kind_of_question("为什么城市热岛效应在夜间比白天更明显？") == "reasoning")
    ck("分桶：多少→fact", kind_of_question("光在水中传播的速度是多少？") == "fact")
    ck("分桶：还是/应该→choice",
       kind_of_question("应该优先补观测还是先统一定义？") == "choice")
    ck("分桶：空题兜底 reasoning", kind_of_question("") == "reasoning")

    r1 = recommend_scenario("reasoning", prefer="quality")
    ck("推荐：reasoning 质量优先 → auto（质量最高）",
       r1["mode"] == "auto"
       and r1["run"]["quality"] == max(x["quality"] for x in rea["runs"].values()),
       r1)
    r2 = recommend_scenario("reasoning", max_wall=300)
    ck("推荐：墙钟≤300s → fast", r2["mode"] == "fast", r2.get("mode"))
    r3 = recommend_scenario("reasoning", min_quality=0.94, prefer="tokens")
    ck("推荐：质量≥0.94 且 tokens 优先 → serial", r3["mode"] == "serial",
       (r3.get("mode"), r3.get("run", {}).get("tokens")))
    r4 = recommend_scenario("fact", prefer="wall")
    ck("推荐：fact 无论偏好都只从 verified 池选（web_on_auto）",
       r4["mode"] == "web_on_auto" and r4["require_web"] is True and
       r4["forbid"], r4)
    r5 = recommend_scenario("fact", min_quality=0.999)
    ck("推荐：约束不可满足 → 回退且 reason 可审计",
       "回退" in str(r5.get("reason")), r5.get("reason"))
    r6 = recommend_scenario("unknown-kind")
    ck("推荐：未知场景 → 兜底 reasoning",
       r6["scenario"] == "reasoning" and r6["mode"] in rea["runs"],
       r6.get("scenario"))

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
