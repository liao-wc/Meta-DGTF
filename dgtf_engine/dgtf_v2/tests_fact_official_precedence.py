# -*- coding: utf-8 -*-
"""官方源优先冲突消解判据（Round 8 精化版，fact_flow 新机制）。

规则：只有**日期类辅助冲突**（单位/锚点是年/月/日/date，或数值全在 1000~2100
像年份）才允许被官方源优先消解；目标量冲突（如 GDP 增速 %）必须保持 conflict。
覆盖：
  · 日期类冲突 + 官方源可答 ⇒ answered、答案清洗、冲突进 resolved_conflicts；
  · 目标量冲突 + 官方 ⇒ 保持 conflict（不得越权消解）；
  · 官方源参与冲突 / 无官方源 / 官方源答不出 ⇒ 保持 conflict；
  · 答案清洗：去行首 [日期]/###/markdown；
  · 输出 JSON 往返、两次运行逐字相同、引擎门口径可 verified。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.evidence import Evidence, EvidenceReport  # noqa: E402
from dgtf_v2.fact_flow import build_fact_card, run_fact_flow  # noqa: E402

P, F = [], []

Q = "珠穆朗玛峰的海拔是多少米？"


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


def ev(eid, snippet, official=False, url=None, rank=0):
    return Evidence(evidence_id=eid, query=Q, title="",
                    url=url or ("https://www.stats.gov.cn/%s" % eid.lower()
                                if official
                                else "https://a.example.com/%s" % eid),
                    snippet=snippet, domain="", official=official,
                    fingerprint="fp_%s" % eid, rank=rank)


def report(items, conflicts, question=Q, gaps=None):
    # gaps 显式给 [] 会触发 detect_gaps 的合成数据缺口（uncovered:…）；
    # 机制判据只关心 conflict_unresolved 的处理，故默认给一个非硬缺口。
    return EvidenceReport(question=question, queries=[Q], searches=2,
                          items=items, conflicts=conflicts,
                          gaps=(["single_source"] if gaps is None else gaps))


DATE_CONFLICT = {"term": "起始年", "unit": "年", "anchor": "",
                 "values": [1852.0, 1856.0], "evidence_ids": ["E1", "E2"]}
TARGET_CONFLICT = {"term": "2023 年中国GDP增长", "unit": "%", "anchor": "",
                   "values": [5.2, 6.8], "evidence_ids": ["E1", "E2"]}


def hard_gaps(card: dict) -> list:
    return [str(g) for g in (card.get("gaps") or [])
            if str(g).startswith("uncovered:") or str(g) in
            ("conflict_unresolved", "insufficient_evidence",
             "question_token_not_in_evidence", "no_query", "search_error",
             "no_record")]


def main():
    off = ev("E8", "[2018-09-20] ### 关于珠峰高度：最新海拔8848.86米，"
                   "本次测量由自然资源部发布", official=True)

    # ① 日期类冲突 + 官方可答 ⇒ 消解（答案清洗）
    card = build_fact_card(Q, report(
        [ev("E1", "珠穆朗玛峰海拔测量历史可追溯到1852年"),
         ev("E2", "珠穆朗玛峰海拔测量历史可追溯到1856年"), off], [DATE_CONFLICT]))
    ck("日期冲突消解：status=answered", card.status == "answered", card.reason)
    ck("日期冲突消解：答案含官方数值 8848.86",
       "8848.86" in str(card.answer), card.answer)
    ck("日期冲突消解：答案已清洗（无 [日期] / ### 痕迹）",
       "[2018" not in str(card.answer) and "###" not in str(card.answer),
       card.answer)
    ck("日期冲突消解：原冲突进 resolved_conflicts",
       len(card.resolved_conflicts) == 1 and not card.conflicts,
       (card.resolved_conflicts, card.conflicts))
    ck("日期冲突消解：gaps 去 conflict_unresolved、留官方优先标记",
       "conflict_unresolved" not in card.gaps
       and any(str(g).startswith("conflict_resolved_official")
               for g in card.gaps), card.gaps)
    cd = card.to_dict()
    ck("日期冲突消解：引擎门口径具备 verified 资格",
       cd.get("status") == "answered" and not hard_gaps(cd)
       and bool(cd.get("official_evidence_ids")))
    ck("to_dict 含 resolved_conflicts 列表",
       isinstance(cd.get("resolved_conflicts"), list))

    # ② 目标量冲突 + 官方 ⇒ 保持 conflict（term 含「年」字也不得误判辅助）
    card2 = build_fact_card(Q, report(
        [ev("E1", "2023年中国GDP增长5.2%"), ev("E2", "2023年中国GDP增长6.8%"),
         off], [TARGET_CONFLICT]))
    ck("负对照：目标量冲突 → 保持 conflict（含『年』字不误判）",
       card2.status == "conflict"
       and "conflict_unresolved" in card2.gaps, card2.status)

    # ③ 官方源参与冲突 ⇒ conflict
    off2 = ev("E9", "最新海拔8844.43米", official=True)
    card3 = build_fact_card(Q, report(
        [ev("E1", "珠峰高程测量的历史可追溯到1852年"),
         ev("E2", "珠峰高程测量的历史可追溯到1856年"), off2],
        [{"term": "起始年", "unit": "年", "values": [1852.0, 1856.0],
          "evidence_ids": ["E1", "E9"]}]))
    ck("负对照：官方源参与冲突 → 保持 conflict", card3.status == "conflict")

    # ④ 无官方源 ⇒ conflict
    card4 = build_fact_card(Q, report(
        [ev("E1", "1852年起有人测量珠峰"),
         ev("E2", "1856年起有人测量珠峰")], [DATE_CONFLICT]))
    ck("负对照：无官方源 → 保持 conflict", card4.status == "conflict")

    # ⑤ 官方源存在但答不出 ⇒ conflict
    card5 = build_fact_card(Q, report(
        [ev("E1", "1852年起有人测量珠峰"),
         ev("E2", "1856年起有人测量珠峰"), ev("E8", "", official=True)],
        [DATE_CONFLICT]))
    ck("负对照：官方源无可用答案 → 保持 conflict", card5.status == "conflict")

    # ⑥ 无冲突 ⇒ 原路径不变
    card6 = build_fact_card(Q, report(
        [ev("E1", "珠峰海拔8848.86米"),
         ev("E2", "珠峰海拔8848.86米"), off], []))
    ck("回归：无冲突 → answered/unknown 且无官方优先标记",
       card6.status in ("answered", "unknown")
       and not any(str(g).startswith("conflict_resolved_official")
                   for g in card6.gaps), (card6.status, card6.gaps))

    # ⑦ 集成：run_fact_flow 的 GDP 目标量冲突仍 conflict
    r = run_fact_flow("2023年中国GDP增长多少", lambda q: [
        {"title": "国家统计局", "url": "https://www.stats.gov.cn/a",
         "snippet": "2023年中国GDP增长5.2%"},
        {"title": "某资讯", "url": "https://a.example.com/1",
         "snippet": "2023年中国GDP增长6.8%"},
        {"title": "统计局", "url": "https://www.stats.gov.cn/b",
         "snippet": "统计局公报：2023年中国GDP增长5.2%"}],
        reasoning="2023年中国GDP增长5.2%")
    ck("集成：run_fact_flow GDP 目标量冲突 → conflict（不被消解）",
       r.card.status == "conflict", r.card.gaps)

    # ⑧ 确定性 + JSON 往返
    def build():
        return build_fact_card(Q, report(
            [ev("E1", "珠峰高程测量的历史可追溯到1852年"),
             ev("E2", "珠峰高程测量的历史可追溯到1856年"), off],
            [DATE_CONFLICT])).to_dict()

    a, b = build(), build()
    ck("确定性：两次运行逐字相同",
       json.dumps(a, sort_keys=True, default=str) ==
       json.dumps(b, sort_keys=True, default=str))
    ck("契约：JSON 往返稳定",
       json.loads(json.dumps(a, ensure_ascii=False))["status"] == a["status"])

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
