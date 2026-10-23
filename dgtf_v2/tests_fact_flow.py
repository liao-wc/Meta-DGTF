# -*- coding: utf-8 -*-
"""fact_flow 离线判据（纯确定性；不调 LLM、不联网）。

覆盖：
- 事实题分类（事实 / 决策 / 空题面；决策语汇优先的负对照）
- 四层固定不砍层（事实短题、决策题、空题面都不许把 route 变短）
- 每层圈数建议（事实短题只砍圈；按层钳制；hard_max 截断）
- FactCard 四态：answered / no_record / conflict / unknown（含各自负对照）
- 注入式 fake search（返回空 / 抛错 / 返回非 list / 有副作用 spy）
- 证据预算与去重进入闭环
- 检索 vs 推理一致性接线（match / mismatch / not_comp）
- 输出可 JSON 往返、两次运行逐字相同
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.evidence import EvidenceBudget  # noqa: E402
from dgtf_v2.fact_flow import (CARD_STATUSES, LAYER_ENTRIES,  # noqa: E402
                               FactCard, classify_question, extract_queries,
                               fixed_route, plan_fact_run, run_fact_flow,
                               suggest_rounds)

Q_FACT = "2023年中国GDP增长多少"
Q_DECISION = "社区医院远程监测先做哪类慢病，如何排优先级"
Q_FACT_LONG = ("北京奥运会中国体育代表团在二〇〇八年一共获得多少枚金牌，"
               "银牌和铜牌各多少枚，请分别列出并注明项目名称")

OFFICIAL = {"title": "国家统计局", "url": "https://www.stats.gov.cn/sj/gdp",
            "snippet": "2023年中国GDP增长5.2%"}
OFFICIAL2 = {"title": "另一份统计公报", "url": "https://www.stats.gov.cn/b",
             "snippet": "2023年中国GDP增长6.8%"}
UNOFFICIAL_A = {"title": "某资讯", "url": "https://a.example.com/1",
                "snippet": "2023年中国GDP增长5.2%"}
UNOFFICIAL_B = {"title": "另一资讯", "url": "https://b.example.org/2",
                "snippet": "据测算 2023 年中国 GDP 增速为 5.2%"}


def fake_search(hits_by_query=None, default=None, error=None):
    """注入式 fake search：记录调用；可返回固定/按 query 的结果，或抛错。"""
    calls = []

    def search(query):
        calls.append(query)
        if error is not None:
            raise error
        if hits_by_query is not None and query in hits_by_query:
            return list(hits_by_query[query])
        return list(default or [])

    search.calls = calls
    return search


# ---------------------------------------------------------------- 分类
def case_classify_fact():
    p = classify_question(Q_FACT)
    assert p.kind == "fact" and p.is_fact is True
    assert p.orientation == "boundary" and p.landing == "boundary"
    assert p.signals["blank"] is False and p.signals["short"] is True
    assert p.signals["fact_hits"], p.signals
    assert not p.signals["decision_hits"]
    assert p.reasons


def case_classify_decision():
    p = classify_question(Q_DECISION)
    assert p.kind == "decision" and p.is_fact is False
    assert p.orientation == "decision" and p.landing == "decision"
    assert "如何" in p.signals["decision_hits"], p.signals
    # 决策语汇优先（题面同时有事实词与决策词也走决策型）
    p2 = classify_question("是否需要统计2023年GDP数据，如何取舍")
    assert p2.kind == "decision" and p2.is_fact is False
    # 负对照：纯事实题不能被判决策
    assert classify_question("2008年北京奥运会中国获得多少枚金牌").kind == "fact"


def case_classify_blank():
    for raw in ("", "   ", None):
        p = classify_question(raw)
        assert p.kind == "unknown" and p.is_fact is False, (raw, p)
        assert p.signals["blank"] is True
        assert p.reasons


# ---------------------------------------------------------------- 排程
def case_route_fixed_four_layers():
    assert list(LAYER_ENTRIES) == ["0", "1", "both", "all"]
    assert fixed_route() == ["0", "1", "both", "all"]
    for q in (Q_FACT, Q_DECISION, Q_FACT_LONG, "", "   "):
        plan = plan_fact_run(q)
        assert plan.route == ["0", "1", "both", "all"], (q, plan.route)
        assert set(plan.route) == {"0", "1", "both", "all"}
        assert plan.rounds.keys() == set(LAYER_ENTRIES)
        assert plan.note and "不砍层" in plan.note


def case_rounds_fact_short_vs_decision():
    # 事实短题：四层仍全跑，每层被 auto.fact_flow.rounds_max（默认 2）收紧
    fact_short = suggest_rounds(Q_FACT)
    assert fact_short == {"0": 2, "1": 2, "both": 2, "all": 2}, fact_short
    assert plan_fact_run(Q_FACT).rounds == {"0": 2, "1": 2,
                                            "both": 2, "all": 2}
    # rounds_max 可调；0 = 不收紧（回到按层默认的短题口径）
    assert set(suggest_rounds(Q_FACT, rounds_max=3).values()) == {3}
    assert suggest_rounds(Q_FACT, rounds_max=0) == {"0": 4, "1": 4,
                                                    "both": 4, "all": 5}
    # 决策题不受 rounds_max 影响（只有事实短题被收紧）
    decision = suggest_rounds(Q_DECISION, rounds_max=2)
    assert decision == {"0": 4, "1": 4, "both": 5, "all": 6}, decision
    # 负对照：事实长题按实测默认，不按短题收紧
    assert len(Q_FACT_LONG) > 40
    assert suggest_rounds(Q_FACT_LONG) == {"0": 4, "1": 4,
                                           "both": 5, "all": 6}
    blank = suggest_rounds("")
    assert blank == {"0": 4, "1": 4, "both": 5, "all": 6}, blank


def case_rounds_layer_clamp_and_hard_max():
    base = plan_fact_run(Q_FACT_LONG).rounds
    assert base["1"] <= 5 and base["all"] >= 5, base
    assert all(4 <= v <= 6 for v in base.values()), base
    hard4 = plan_fact_run(Q_FACT_LONG, hard_max=4).rounds
    assert set(hard4.values()) == {4}, hard4
    hard5 = plan_fact_run(Q_FACT_LONG, hard_max=5).rounds
    assert hard5 == {"0": 4, "1": 4, "both": 5, "all": 5}, hard5
    # 负对照：hard_max 很小也不能把层砍掉
    assert plan_fact_run(Q_FACT, hard_max=2).route ==         ["0", "1", "both", "all"]


def case_extract_queries():
    qs = extract_queries("请问2023年中国GDP增长多少？",
                         extra=["2023 GDP 官方",
                                "请问2023年中国GDP增长多少？"])
    assert qs == ["请问2023年中国GDP增长多少？",
                  "2023年中国GDP增长多少", "2023 GDP 官方"], qs
    assert extract_queries("") == []
    assert extract_queries("   ") == []
    # extra 去重（与题面相同的值不再追加）
    assert extract_queries("GDP 数据", extra=["GDP 数据"]) == ["GDP 数据"]


# ---------------------------------------------------------------- FactCard 四态
def case_card_answered_official():
    spy = fake_search(default=[OFFICIAL])
    r = run_fact_flow(Q_FACT, spy)
    assert r.card.status == "answered", r.card.reason
    assert r.card.ok is True and r.card.answer == OFFICIAL["snippet"]
    assert r.card.official_evidence_ids == ["E1"]
    assert r.card.queries and spy.calls and spy.calls[0]
    assert r.evidence.official_count == 1
    assert r.evidence.set_fingerprint
    assert len(r.plan.route) == 4


def case_card_no_record():
    spy = fake_search(default=[])
    r = run_fact_flow(Q_FACT, spy)
    assert r.card.status == "no_record", r.card.reason
    assert r.card.answer == "" and r.card.ok is False
    assert "no_record" in r.card.gaps and "no_evidence" in r.card.gaps
    assert r.evidence.searches >= 1
    # 负对照：查到了（answered）就不许是 no_record
    r2 = run_fact_flow(Q_FACT, fake_search(default=[OFFICIAL]))
    assert r2.card.status != "no_record"


def case_card_conflict():
    r = run_fact_flow(Q_FACT, fake_search(default=[OFFICIAL, OFFICIAL2]))
    assert r.card.status == "conflict", r.card.reason
    assert r.card.conflicts, r.card.conflicts
    assert r.card.ok is False and r.card.answer == ""
    assert "conflict_unresolved" in r.card.gaps
    # 负对照：同一数值不判冲突
    same = dict(OFFICIAL2, snippet=OFFICIAL["snippet"])
    r2 = run_fact_flow(Q_FACT, fake_search(default=[OFFICIAL, same]))
    assert r2.card.status != "conflict", r2.card.gaps


def case_card_unknown_paths():
    # ① 没有注入检索能力
    r = run_fact_flow(Q_FACT, None)
    assert r.card.status == "unknown" and r.card.ok is False
    assert "search_error" in r.card.gaps and "search_unavailable" in r.evidence.errors
    assert r.evidence.searches == 0
    # ② 检索失败（不崩，留痕）
    spy = fake_search(error=RuntimeError("boom"))
    r2 = run_fact_flow(Q_FACT, spy)
    assert r2.card.status == "unknown"
    assert any("boom" in e for e in r2.evidence.errors), r2.evidence.errors
    assert spy.calls
    # ③ 查到了但来源不够（单条非官方）
    r3 = run_fact_flow(Q_FACT, fake_search(default=[UNOFFICIAL_A]))
    assert r3.card.status == "unknown", r3.card.status
    assert "insufficient_evidence" in r3.card.gaps
    assert "no_official_source" in r3.card.gaps
    # ④ 返回值类型不对 ⇒ 记错误，不崩
    r4 = run_fact_flow(Q_FACT, lambda q: "not-a-list")
    assert r4.card.status == "unknown"
    assert any("search_bad_return" in e for e in r4.evidence.errors)


def case_card_independent_sources_answered():
    # 官方源缺位，但两个独立域名一致 ⇒ answered（同时保留 no_official_source 读数）
    r = run_fact_flow(Q_FACT, fake_search(default=[UNOFFICIAL_A, UNOFFICIAL_B]))
    assert r.card.status == "answered", r.card.reason
    assert r.card.ok is True
    assert "no_official_source" in r.card.gaps
    assert r.card.official_evidence_ids == []
    # 负对照：单域名不变（虽然文本重复也不够独立）
    r2 = run_fact_flow(Q_FACT, fake_search(default=[UNOFFICIAL_A]))
    assert r2.card.status == "unknown"


def case_budget_and_dedup_in_flow():
    hits = [{"title": "t%d" % i,
             "url": "https://example.com/%d?utm_source=x" % i,
             "snippet": "2023年中国GDP增长5.2%%（第 %d 份）" % i}
            for i in range(6)]
    r = run_fact_flow(Q_FACT, fake_search(default=hits),
                      budget=EvidenceBudget(max_items=2, max_per_domain=2))
    assert len(r.evidence.items) <= 2, len(r.evidence.items)
    assert len(r.evidence.dropped) >= 3, r.evidence.dropped
    assert all(str(d.get("reason", "")).startswith("budget_")
               for d in r.evidence.dropped), r.evidence.dropped
    # 去重：同文不同 url 只留一条
    dup = [{"title": "x", "url": "https://example.com/a?utm_source=1",
            "snippet": "同一条证据"},
           {"title": "x", "url": "https://example.com/a?utm_source=2",
            "snippet": "同一条证据"}]
    r2 = run_fact_flow(Q_FACT, fake_search(default=dup))
    assert len(r2.evidence.items) == 1, r2.evidence.items
    assert any(d.get("reason") in ("dup_url", "dup_text")
               for d in r2.evidence.dropped)


# ---------------------------------------------------------------- 一致性接线
def case_consistency_wiring():
    # 推理与检索一致 ⇒ match，整条闭环 ok
    r = run_fact_flow(Q_FACT, fake_search(default=[OFFICIAL]),
                      reasoning=OFFICIAL["snippet"])
    assert r.consistency.verdict == "match", r.consistency.reasons
    assert r.consistency.ok is True and r.ok is True
    assert "consistency:not_comp" not in r.gaps
    # 数值矛盾 ⇒ mismatch，闭环不 ok
    r2 = run_fact_flow(Q_FACT, fake_search(default=[OFFICIAL]),
                       reasoning="2023年中国GDP增长6.8%")
    assert r2.consistency.verdict == "mismatch", r2.consistency.reasons
    assert r2.ok is False and "consistency:mismatch" in r2.gaps
    # 没给推理 ⇒ not_comp（不可比，不冒充 match）
    r3 = run_fact_flow(Q_FACT, fake_search(default=[OFFICIAL]))
    assert r3.consistency.verdict == "not_comp"
    assert r3.ok is False and "consistency:not_comp" in r3.gaps


# ---------------------------------------------------------------- 输出契约
def case_output_contract():
    spy = fake_search(default=[OFFICIAL])
    r1 = run_fact_flow(Q_FACT, spy, reasoning=OFFICIAL["snippet"])
    d = r1.to_dict()
    assert set(d) == {"question", "profile", "plan", "fact_card",
                      "evidence", "consistency", "gaps", "ok"}
    assert d["fact_card"]["status"] in CARD_STATUSES
    assert d["plan"]["route"] == ["0", "1", "both", "all"]
    assert d["profile"]["kind"] in ("fact", "decision", "unknown")
    assert isinstance(d["ok"], bool)
    roundtrip = json.loads(json.dumps(d, ensure_ascii=False))
    assert roundtrip["fact_card"]["status"] == d["fact_card"]["status"]
    # 两次运行（同输入、同 fake 行为）逐字相同
    r2 = run_fact_flow(Q_FACT, fresh_fake(), reasoning=OFFICIAL["snippet"])
    assert json.dumps(r1.to_dict(), ensure_ascii=False, sort_keys=True,
                      default=str) == \
        json.dumps(r2.to_dict(), ensure_ascii=False, sort_keys=True,
                   default=str)
    # 缺省 FactCard 也能序列化，且状态合法
    assert FactCard().to_dict()["status"] in CARD_STATUSES


def fresh_fake():
    return fake_search(default=[OFFICIAL])


CASES = [
    case_classify_fact,
    case_classify_decision,
    case_classify_blank,
    case_route_fixed_four_layers,
    case_rounds_fact_short_vs_decision,
    case_rounds_layer_clamp_and_hard_max,
    case_extract_queries,
    case_card_answered_official,
    case_card_no_record,
    case_card_conflict,
    case_card_unknown_paths,
    case_card_independent_sources_answered,
    case_budget_and_dedup_in_flow,
    case_consistency_wiring,
    case_output_contract,
]


def main():
    bad = []
    for fn in CASES:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception as e:  # noqa: BLE001
            bad.append((fn.__name__, e))
            print("FAIL", fn.__name__, type(e).__name__, e)
    print("\nPASS %d / FAIL %d" % (len(CASES) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
