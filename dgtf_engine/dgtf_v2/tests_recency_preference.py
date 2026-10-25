# -*- coding: utf-8 -*-
"""时效优先判据（Round 11，零 API）。

覆盖：
  · 默认 prefer_recent=False ⇒ 与旧行为一致（官方源优先，不看日期）；
  · 题面含「最新/当前」时，证据日期更晚者优先（即使非官方源，0.5 加分可反超
    非最新官方源的 0.15）；
  · 无日期证据 ⇒ 退回原排序（官方优先）；
  · 时效词但不含日期 ⇒ 原排序；
  · fact_flow 集成：时效题 answered 答案取最新证据；非时效题不受影响。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.evidence import Evidence, answer_from_evidence  # noqa: E402
from dgtf_v2.fact_flow import build_fact_card  # noqa: E402
from dgtf_v2.evidence import EvidenceReport  # noqa: E402

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


def ev(eid, snippet, official=False):
    return Evidence(evidence_id=eid, query="q", title="", url="u/" + eid,
                    snippet=snippet, domain="", official=official,
                    fingerprint="fp_" + eid, rank=0)


Q_NEW = "珠穆朗玛峰的最新海拔是多少米？"
Q_OLD = "珠穆朗玛峰的海拔是多少米？"
OLD_OFF = ev("E1", "珠穆朗玛峰海拔8844.43米，2005年公布", official=True)
NEW_UNO = ev("E2", "珠穆朗玛峰海拔8848.86米，2020年12月8日联合公布",
             official=False)
OLD_OFF2 = ev("E3", "珠穆朗玛峰海拔8844.43米，2005年公布", official=True)


def main():
    # ① 默认关闭时旧行为：官方源优先（即使日期旧）
    a = answer_from_evidence([OLD_OFF, NEW_UNO], Q_NEW)
    ck("默认 prefer_recent=False → 旧行为（官方源优先，取 8844.43）",
       "8844.43" in a, a)
    # ② 时效题开启 → 最新日期证据优先
    b = answer_from_evidence([OLD_OFF, NEW_UNO], Q_NEW, prefer_recent=True)
    ck("时效题 prefer_recent=True → 最新证据优先（取 8848.86）",
       "8848.86" in b, b)
    # ③ 非时效题即使开启也保持官方优先
    c = answer_from_evidence([OLD_OFF, NEW_UNO], Q_OLD, prefer_recent=True)
    ck("非时效题 prefer_recent=True → 保持官方优先（8844.43）",
       "8844.43" in c, c)
    # ④ 无日期证据 → 原排序
    d = answer_from_evidence([ev("E4", "珠峰海拔8844.43米", True),
                              ev("E5", "珠峰海拔8848.86米", False)],
                             Q_NEW, prefer_recent=True)
    ck("无日期证据 → 退回官方优先（8844.43）", "8844.43" in d, d)
    # ⑤ fact_flow 集成：时效题 card.answer 取最新证据
    card = build_fact_card(Q_NEW, EvidenceReport(
        question=Q_NEW, queries=[Q_NEW], searches=2,
        items=[OLD_OFF2, ev("E6", "珠穆朗玛峰最新海拔8848.86米，"
                                  "2020年12月8日公布", official=True)],
        conflicts=[], gaps=["single_source"]))
    ck("fact_flow 集成：时效题 answered 取最新证据 8848.86",
       card.status == "answered" and "8848.86" in str(card.answer), card.answer)
    # ⑥ fact_flow 集成：同值不同上下文的两个官方源
    #    非时效题 → 取先出现的官方源（不看日期）；时效题 → 取最新日期者
    _o = ev("E7", "珠穆朗玛峰海拔8844.43米，2005年公布", official=True)
    _n = ev("E8", "珠穆朗玛峰最高海拔8848.86米，2020年12月8日更新",
            official=True)
    card_old = build_fact_card(Q_OLD, EvidenceReport(
        question=Q_OLD, queries=[Q_OLD], searches=2,
        items=[_o, _n], conflicts=[], gaps=["single_source"]))
    ck("fact_flow：非时效题不走时效加权（取先出现官方源）",
       card_old.status == "answered" and "8844.43" in str(card_old.answer),
       (card_old.status, card_old.answer))
    card_new = build_fact_card(Q_NEW, EvidenceReport(
        question=Q_NEW, queries=[Q_NEW], searches=2,
        items=[_o, _n], conflicts=[], gaps=["single_source"]))
    ck("fact_flow：时效题取最新日期证据",
       card_new.status == "answered" and "8848.86" in str(card_new.answer),
       (card_new.status, card_new.answer))

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
