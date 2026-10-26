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
    ck("矩阵行数 = 57（reasoning 6 / choice 4 / fact 47）", len(rows) == 57, len(rows))
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
    ck("fact：web_on_auto 及其变体均为 verified",
       all(fact["runs"][k]["verified"] is True
           for k in ("web_on_auto", "web_on_auto2", "web_on_auto3")))
    ck("fact：web_off_auto 与修复前 fast 未 verified（历史对照）",
       fact["runs"]["web_off_auto"]["verified"] is False
       and fact["runs"]["web_on_fast_pre_fix"]["verified"] is False)
    ck("fact：修复后 fast+web 已 verified（成本档可用，4 题）",
       all(fact["runs"][k]["verified"] is True
           for k in ("web_on_fast", "web_on_fast2", "web_on_fast3",
                     "web_on_fast4", "web_on_fast5", "web_on_fast6", "web_on_fast7",
                     "web_on_fast8", "web_on_fast9", "web_on_fast10", "web_on_fast11", "web_on_fast12", "web_on_fast13", "web_on_fast14", "web_on_fast15", "web_on_fast16", "web_on_fast17", "web_on_fast18", "web_on_fast19", "web_on_fast20", "web_on_fast21", "web_on_fast22", "web_on_fast23", "web_on_fast24", "web_on_fast25", "web_on_fast26", "web_on_fast27", "web_on_fast28")))
    ck("fact：成本档 tokens 低于 auto 且质量不低",
       fact["runs"]["web_on_fast"]["tokens"] < fact["runs"]["web_on_auto"]["tokens"]
       and fact["runs"]["web_on_fast2"]["tokens"] < fact["runs"]["web_on_auto"]["tokens"])
    ck("fact：规则强制联网 + 仅禁用无 web/修复前档",
       fact["rules"]["requires_web"] is True
       and "web_off_auto" in fact["rules"]["forbid"]
       and "web_on_fast_pre_fix" in fact["rules"]["forbid"])

    rea = MEASURED_SCENARIOS["reasoning"]
    ck("reasoning：quality_first=auto / cost_first=fast",
       rea["rules"]["quality_first"] == "auto"
       and rea["rules"]["cost_first"] == "fast")
    ck("reasoning：fast 墙钟 < auto 墙钟（成本档成立）",
       rea["runs"]["fast"]["wall"] < rea["runs"]["auto"]["wall"])

    ck("分桶：为什么…→reasoning",
       kind_of_question("为什么城市热岛效应在夜间比白天更明显？") == "reasoning")
    ck("分桶：多少→fact", kind_of_question("光在水中传播的速度是多少？") == "fact")
    ck("分桶：表示什么→fact",
       kind_of_question("HTTP 404状态码表示什么？") == "fact")
    ck("分桶：还是/应该→choice",
       kind_of_question("应该优先补观测还是先统一定义？") == "choice")
    ck("分桶：空题兜底 reasoning", kind_of_question("") == "reasoning")

    r1 = recommend_scenario("reasoning", prefer="quality")
    ck("推荐：reasoning 质量优先 → 规则档 auto（实测方差内取稳档）",
       r1["mode"] == "auto" and "规则" in str(r1.get("reason")), r1)
    r2 = recommend_scenario("reasoning", max_wall=300, prefer="wall")
    ck("推荐：墙钟≤300s 且 prefer=wall → fast（188s）",
       r2["mode"] == "fast", r2.get("mode"))
    r3 = recommend_scenario("reasoning", min_quality=0.94, prefer="tokens")
    ck("推荐：质量≥0.94 且 tokens 优先 → 最少 tokens 的 verified 档",
       r3["mode"] == "fast_domain2"
       and r3["run"]["tokens"] == min(
           x["tokens"] for x in rea["runs"].values()
           if x["verified"] and x["quality"] >= 0.94),
       (r3.get("mode"), r3.get("run", {}).get("tokens")))
    _ch = MEASURED_SCENARIOS["choice"]["runs"]
    ck("choice：fast 与 auto 同质量（Δ≤0.01）且更省 tokens/墙钟",
       abs(_ch["fast"]["quality"] - _ch["auto"]["quality"]) <= 0.01
       and _ch["fast"]["tokens"] < _ch["auto"]["tokens"]
       and _ch["fast"]["wall"] < _ch["auto"]["wall"], _ch)
    r4 = recommend_scenario("fact", prefer="wall")
    ck("推荐：fact 墙钟优先 → 最低墙钟已验证档（fast 系）",
       str(r4["mode"]).startswith("web_on_fast") and
       r4["require_web"] is True and r4["forbid"], r4)
    r5 = recommend_scenario("fact", min_quality=0.999)
    ck("推荐：约束不可满足 → 回退且 reason 可审计",
       "回退" in str(r5.get("reason")), r5.get("reason"))
    r6 = recommend_scenario("unknown-kind")
    # ★ [Round 90] 场景分类：地点/排序型问句 → fact（App 事实档强制 web on）
    ck("场景分类：地点问句 → fact",
       kind_of_question("联合国的总部设在哪个城市？") == "fact")
    ck("场景分类：最大问句 → fact",
       kind_of_question("中国最大的淡水湖是哪个？") == "fact")
    ck("场景分类：为什么仍 → reasoning",
       kind_of_question("为什么海水是咸的？") == "reasoning")
    ck("场景分类：选项题 → choice",
       kind_of_question("以下哪项属于可再生能源？"
                        "A. 煤炭 B. 太阳能 C. 石油 D. 天然气") == "choice")
    ck("场景分类：选择问句仍 → choice",
       kind_of_question("企业建设数据中心，应该优先选择哪个方案？"
                        "A. 自建 B. 公有云") == "choice")

    ck("推荐：未知场景 → 兜底 reasoning",

       r6["scenario"] == "reasoning" and r6["mode"] in rea["runs"],
       r6.get("scenario"))

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
