# -*- coding: utf-8 -*-
"""evidence / consistency 离线判据（纯确定性；不调 LLM、不联网）。

覆盖：
- 官方源白名单（正反例 + 自定义白名单）
- URL 归一化 / 文本指纹 / 证据集指纹（同文不同写法判同、顺序无关）
- 注入检索结果归一化（dict / str 混排、空条目跳过）
- 去重（URL 跟踪参数、同文不同 url）与预算（条数 / 单域名 / 总字符）
- 数值冲突（正例；同值/不同年份/不同单位/一方多值等负对照）
- 证据缺口（无证据 / 无官方源 / 单一来源 / 未覆盖项 / 冲突 / 预算截断）
- 引用绑定（显式 E-id / 无效 id / 覆盖度回退 / 绑不上）
- 检索 vs 推理一致性（match / partial / mismatch / not_comp + 官方证据矛盾）
- 确定性（同输入重复运行逐字相同）与 to_dict JSON 往返
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.consistency import (VERDICTS,  # noqa: E402
                                 char_similarity,
                                 compare_retrieval_vs_reasoning)
from dgtf_v2.evidence import (OFFICIAL_DOMAINS,  # noqa: E402
                              EvidenceBudget, answer_from_evidence,
                              apply_budget, bind_citations, collect_evidence,
                              dedup_evidence, detect_conflicts, detect_gaps,
                              domain_of, extract_numeric_claims,
                              find_numeric_conflicts, fingerprint_text,
                              from_search_hits, is_official_source,
                              normalize_url, question_terms, set_fingerprint)

OFFICIAL = {"title": "国家统计局", "url": "https://www.stats.gov.cn/sj/gdp",
            "snippet": "2023年中国GDP增长5.2%"}
OFFICIAL2 = {"title": "另一份统计公报", "url": "https://www.stats.gov.cn/b",
             "snippet": "2023年中国GDP增长6.8%"}
UNOFFICIAL_A = {"title": "某资讯", "url": "https://a.example.com/1",
                "snippet": "2023年中国GDP增长5.2%"}
UNOFFICIAL_B = {"title": "另一资讯", "url": "https://b.example.org/2",
                "snippet": "2023年中国GDP增长5.2%"}


# ---------------------------------------------------------------- 来源 / URL / 指纹
def case_official_whitelist():
    assert is_official_source("https://www.stats.gov.cn/a")
    assert is_official_source("http://stats.gov.cn")
    assert is_official_source("https://nasa.gov/x")
    assert is_official_source("https://www.who.int/news")
    assert is_official_source("https://www.tsinghua.edu.cn/a")
    # 反向后缀 / 无关站点 / 空串：一律不算
    assert not is_official_source("https://example.gov.cn.evil.com/a")
    assert not is_official_source("https://example.com/a")
    assert not is_official_source("")
    # 自定义白名单可替换默认表（测试注入）
    assert is_official_source("https://example.com/a", whitelist=["example.com"])
    assert not is_official_source("https://www.stats.gov.cn/a",
                                  whitelist=["example.com"])
    assert domain_of("https://WWW.Stats.GOV.cn/a") == "www.stats.gov.cn"
    assert "gov.cn" in OFFICIAL_DOMAINS


def case_normalize_url():
    raw = "HTTPS://WWW.Stats.gov.cn/a/?utm_source=x&b=2&a=1#frag"
    assert normalize_url(raw) == "https://www.stats.gov.cn/a?a=1&b=2"
    assert normalize_url("www.stats.gov.cn/a/") == \
        "https://www.stats.gov.cn/a"
    assert normalize_url("") == ""
    # 跟踪参数不同、fragment 不同 ⇒ 同一归一化结果
    assert normalize_url("https://example.com/x?utm_source=a") == \
        normalize_url("https://example.com/x?utm_source=b#f")


def case_fingerprints():
    a = fingerprint_text("2023年  GDP 增长 5.2%")
    b = fingerprint_text("2023年 GDP 增长 5.2%")
    c = fingerprint_text("2023年GDP下降5.2%")
    assert a == b and a != c
    assert len(a) == 16 and len(fingerprint_text("x", size=8)) == 8
    # 证据集指纹与元素顺序无关
    assert set_fingerprint(["b", "a", "a"]) == set_fingerprint(["a", "b"])
    assert set_fingerprint(["a"]) != set_fingerprint(["b"])


# ---------------------------------------------------------------- 归一化 / 去重 / 预算
def case_from_search_hits():
    hits = [OFFICIAL, "纯文本证据", {"title": "", "snippet": ""},
            123, {"note": "x"}]
    items = from_search_hits(hits, query="q1")
    assert [e.evidence_id for e in items] == ["E1", "E2"]
    assert items[0].official is True and items[0].domain == "www.stats.gov.cn"
    assert items[0].query == "q1" and items[0].rank == 1
    assert items[1].url == "" and items[1].official is False
    assert items[1].snippet == "纯文本证据"
    # snippet 截断（预算里的 max_snippet_chars）
    short = from_search_hits([dict(OFFICIAL, snippet="x" * 100)],
                             budget=EvidenceBudget(max_snippet_chars=10))
    assert len(short[0].snippet) == 10


def case_dedup():
    items = from_search_hits([
        {"title": "a", "url": "https://example.com/x?utm_source=1",
         "snippet": "同一条证据文本"},
        {"title": "b", "url": "https://example.com/x?utm_source=2",
         "snippet": "另一段文本"},
        {"title": "c", "url": "https://other.example.com/y",
         "snippet": "同一条证据文本"},
        {"title": "d", "url": "https://example.com/z",
         "snippet": "独立的一段"},
    ])
    kept, dropped = dedup_evidence(items)
    assert [e.evidence_id for e in kept] == ["E1", "E4"], kept
    reasons = sorted(d["reason"] for d in dropped)
    assert reasons == ["dup_text", "dup_url"], dropped
    assert dropped[0]["against"] == "E1"


def case_budget():
    items = from_search_hits([
        {"title": "official-1", "url": "https://www.stats.gov.cn/1",
         "snippet": "s1"},
        {"title": "official-2", "url": "https://www.who.int/2",
         "snippet": "s2"},
        {"title": "unofficial-3", "url": "https://example.com/3",
         "snippet": "s3"},
    ])
    kept, dropped = apply_budget(items, EvidenceBudget(max_items=2,
                                                      max_per_domain=1))
    assert [e.evidence_id for e in kept] == ["E1", "E2"], kept
    assert dropped and dropped[0]["reason"] == "budget_items"
    # 官方优先：预算只够一条时，先留官方源（哪怕它在输入里靠后）
    items2 = from_search_hits([
        {"title": "u", "url": "https://example.com/u", "snippet": "u"},
        OFFICIAL,
    ])
    kept2, _ = apply_budget(items2, EvidenceBudget(max_items=1))
    assert kept2[0].official is True, kept2
    # 总字符预算：第一条必留，第二条因字符超限被丢
    kept3, dropped3 = apply_budget(items, EvidenceBudget(
        max_items=8, max_per_domain=8, max_total_chars=1))
    assert len(kept3) == 1 and dropped3
    assert dropped3[0]["reason"] == "budget_chars"


# ---------------------------------------------------------------- 冲突
def case_detect_conflicts():
    items = from_search_hits([OFFICIAL, OFFICIAL2])
    conflicts = detect_conflicts(items)
    assert len(conflicts) == 1, conflicts
    c = conflicts[0]
    assert c["values"] == [5.2, 6.8] and c["unit"] == "%"
    assert c["evidence_ids"] == ["E1", "E2"]
    # 负对照 ①：同一数值不冲突
    same = from_search_hits([OFFICIAL, dict(OFFICIAL2,
                                            snippet=OFFICIAL["snippet"])])
    assert detect_conflicts(same) == []
    # 负对照 ②：不同年份锚不冲突
    y1 = from_search_hits([{"title": "2022", "url": "https://a.example.com/1",
                            "snippet": "2022年中国GDP增长3.0%"}])
    y2 = from_search_hits([{"title": "2023", "url": "https://a.example.com/2",
                            "snippet": "2023年中国GDP增长5.2%"}])
    assert detect_conflicts(y1 + y2) == []
    # 负对照 ③：单位不同不冲突
    u1 = from_search_hits([{"title": "pct", "url": "https://a.example.com/3",
                            "snippet": "2023年中国GDP增长5.2%"}])
    u2 = from_search_hits([{"title": "points", "url": "https://a.example.com/4",
                            "snippet": "2023年中国GDP增长6.8个百分点"}])
    assert detect_conflicts(u1 + u2) == []


def case_find_numeric_conflicts():
    got = find_numeric_conflicts("2023年GDP增长5.2%", "2023年GDP增长6.8%")
    assert got and got[0]["left_values"] == [5.2]
    assert got[0]["right_values"] == [6.8]
    # 不同年份不算矛盾
    assert find_numeric_conflicts("2022年GDP增长3.0%",
                                  "2023年GDP增长5.2%") == []
    # 一方多提一个数值不算矛盾（可能在对照历史）
    assert find_numeric_conflicts("2023年GDP增长5.2%",
                                  "2023年GDP增长5.2%，上年6.8%") == []
    assert extract_numeric_claims("") == []


def case_extract_claims():
    claims = extract_numeric_claims("2023年GDP增长5.2%")
    assert len(claims) == 1, claims
    c = claims[0]
    assert c["anchor"] == "2023" and c["unit"] == "%" and c["value"] == 5.2
    # 年份只当锚，不算被主张的数值
    assert all(c["unit"] != "年" for c in claims)
    # 分句沿用前面的年份锚（同句后半句没有年份）
    cs = extract_numeric_claims("2023年GDP增长5.2%，出口增长3.1%")
    assert [c["anchor"] for c in cs] == ["2023", "2023"], cs
    assert sorted(c["value"] for c in cs) == [3.1, 5.2]


# ---------------------------------------------------------------- 缺口 / 答案
def case_detect_gaps():
    assert detect_gaps("q", []) == ["no_evidence"]
    one = from_search_hits([UNOFFICIAL_A])
    gaps = detect_gaps("2023年中国GDP增长多少", one)
    assert "no_official_source" in gaps and "single_source" in gaps, gaps
    # 未覆盖关键项（证据讲 GDP，题面问奥运）
    one_off = from_search_hits([OFFICIAL])
    g2 = detect_gaps("2008年北京奥运会中国获得多少枚金牌", one_off)
    assert any(x.startswith("uncovered:") for x in g2), g2
    # 冲突缺口
    both = from_search_hits([OFFICIAL, OFFICIAL2])
    g3 = detect_gaps("2023年中国GDP增长多少", both,
                     conflicts=detect_conflicts(both))
    assert "conflict_unresolved" in g3
    # 预算截断缺口
    dropped = [{"evidence_id": "E9", "reason": "budget_items"}]
    g4 = detect_gaps("q", one, dropped=dropped)
    assert any(x.startswith("budget_truncated:") for x in g4), g4
    # min_official=2 但只有 1 条官方
    g5 = detect_gaps("q", one_off, min_official=2)
    assert any(x.startswith("official_source_short:") for x in g5), g5
    assert question_terms("") == []
    assert question_terms("Python 中 len() 函数的作用是什么？") == ["Python", "len"]


def case_answer_from_evidence():
    items = from_search_hits([
        UNOFFICIAL_A,
        OFFICIAL,
    ])
    assert answer_from_evidence(items) == OFFICIAL["snippet"]
    assert answer_from_evidence([]) == ""


def case_answer_relevance_gate():
    junk = from_search_hits([{
        "title": "CTF writeup", "url": "https://ctf.example.com/a",
        "snippet": "flag 在控制台里，把字符串反转即可"}])
    assert answer_from_evidence(junk, "HTTP 404 状态码表示什么？") == ""
    no_url = from_search_hits([{
        "title": "DeepSeek docs", "url": "https://api-docs.deepseek.com/",
        "snippet": "import OpenAI; baseURL: '  "}])
    assert answer_from_evidence(no_url,
                                "DeepSeek API 的 base URL 是什么？") == ""
    good = from_search_hits([{
        "title": "DeepSeek docs", "url": "https://api-docs.deepseek.com/",
        "snippet": "baseURL: 'https://api.deepseek.com'"}])
    assert "https://api.deepseek.com" in answer_from_evidence(
        good, "DeepSeek API 的 base URL 是什么？")


# ---------------------------------------------------------------- 引用绑定
def case_bind_citations_explicit():
    items = from_search_hits([OFFICIAL, OFFICIAL2])
    rep = bind_citations(["2023年GDP增长5.2% [E1]", "结论引用 E9"], items)
    assert rep.bindings[0].evidence_ids == ["E1"]
    assert rep.bindings[0].mode == "explicit"
    assert rep.invalid_ids == ["E9"], rep.invalid_ids
    assert rep.bindings[1].mode == "none" and rep.unbound
    assert rep.coverage == 0.5 and rep.ok is False
    assert rep.to_dict()["coverage"] == 0.5
    # 多引用
    rep2 = bind_citations(["综合 [E1][E2]"], items)
    assert rep2.bindings[0].evidence_ids == ["E1", "E2"]
    assert rep2.ok is True


def case_bind_citations_overlap():
    items = from_search_hits([OFFICIAL])
    rep = bind_citations(["GDP 增长 5.2%", "火星殖民计划"], items)
    assert rep.bindings[0].mode == "overlap"
    assert rep.bindings[0].evidence_ids == ["E1"]
    assert rep.bindings[1].mode == "none"
    assert rep.unbound == ["火星殖民计划"]
    assert rep.coverage == 0.5
    assert bind_citations([], items).coverage == 0.0


# ---------------------------------------------------------------- 一致性
def case_consistency_match():
    r = compare_retrieval_vs_reasoning("北京是中国的首都", "中国的首都是北京")
    assert r.verdict == "match" and r.ok is True, r.reasons
    assert r.similarity >= 0.99
    r2 = compare_retrieval_vs_reasoning("2023年中国GDP增长5.2%",
                                        "2023年中国GDP增长5.2%")
    assert r2.verdict == "match" and not r2.missing_terms


def case_consistency_partial():
    r = compare_retrieval_vs_reasoning("该政策2020年发布，覆盖A、B",
                                       "该政策2020年发布，覆盖A")
    assert r.verdict == "partial", r.reasons
    assert "b" in r.missing_terms, r.missing_terms
    assert not r.contradicting


def case_consistency_mismatch():
    r = compare_retrieval_vs_reasoning("2023年GDP增长5.2%",
                                       "2023年GDP增长6.8%")
    assert r.verdict == "mismatch", r.reasons
    assert r.contradicting
    assert any("数值矛盾" in x for x in r.reasons), r.reasons
    # 否定相反
    r2 = compare_retrieval_vs_reasoning("该方案可行", "该方案不可行")
    assert r2.verdict == "mismatch", r2.reasons
    assert any("否定" in x for x in r2.reasons), r2.reasons
    # 负对照：无关文本判 mismatch 而不是 match
    r3 = compare_retrieval_vs_reasoning("苹果是一种水果", "量子纠缠是物理现象")
    assert r3.verdict == "mismatch"


def case_consistency_not_comp():
    for retrieval in ({"status": "no_record", "answer": ""},
                      {"status": "unknown", "answer": ""},
                      {"status": "conflict", "answer": "a"},
                      "", None):
        r = compare_retrieval_vs_reasoning(retrieval, "x")
        assert r.verdict == "not_comp", (retrieval, r.verdict)
    # 推理侧无结论
    assert compare_retrieval_vs_reasoning("a", "") .verdict == "not_comp"


def case_consistency_official_evidence():
    # 检索与推理互相一致，但**推理与官方证据**数值矛盾 ⇒ 仍判 mismatch
    ev = from_search_hits([OFFICIAL2])
    r = compare_retrieval_vs_reasoning("2023年GDP增长5.2%",
                                       "2023年GDP增长5.2%", evidence=ev)
    assert r.verdict == "mismatch", r.reasons
    assert r.evidence_ids == ["E1"], r.evidence_ids
    assert any("官方证据" in x for x in r.reasons), r.reasons
    # 负对照：推理与官方证据一致 ⇒ 不因证据检查翻成 mismatch
    ev2 = from_search_hits([OFFICIAL])
    r2 = compare_retrieval_vs_reasoning("2023年GDP增长5.2%",
                                        "2023年GDP增长5.2%", evidence=ev2)
    assert r2.verdict == "match", r2.reasons
    # 非官方证据不参与「官方证据矛盾」检查
    ev3 = from_search_hits([UNOFFICIAL_A])
    r3 = compare_retrieval_vs_reasoning("2023年GDP增长5.2%",
                                        "2023年GDP增长6.8%，官方数据",
                                        evidence=ev3)
    assert r3.verdict == "mismatch"  # 由检索 vs 推理数值矛盾判，不是官方证据


def case_consistency_determinism():
    a = compare_retrieval_vs_reasoning("2023年GDP增长5.2%",
                                       "2023年GDP增长6.8%")
    b = compare_retrieval_vs_reasoning("2023年GDP增长5.2%",
                                       "2023年GDP增长6.8%")
    assert json.dumps(a.to_dict(), ensure_ascii=False, sort_keys=True) == \
        json.dumps(b.to_dict(), ensure_ascii=False, sort_keys=True)
    assert a.verdict in VERDICTS
    assert json.loads(json.dumps(a.to_dict(), ensure_ascii=False))
    assert char_similarity("a", "a") == 1.0 and char_similarity("", "x") == 0.0


# ---------------------------------------------------------------- 采集入口
def case_collect_evidence_paths():
    rep = collect_evidence(["q"], None)
    assert rep.items == [] and "search_unavailable" in rep.errors
    assert rep.gaps == ["no_evidence"] and rep.ok is False
    # 空 query 列表也能返回结构化报告
    rep2 = collect_evidence([], lambda q: [])
    assert rep2.searches == 0 and rep2.items == []
    # 抛错 / 返回非 list：留痕不崩
    def boom(q):
        raise ValueError("bad")
    rep3 = collect_evidence(["q"], boom)
    assert any("search_error" in e for e in rep3.errors), rep3.errors
    rep4 = collect_evidence(["q"], lambda q: 42)
    assert any("search_bad_return" in e for e in rep4.errors), rep4.errors
    # 去重 + 预算后仍可 JSON 序列化
    hits = [OFFICIAL, OFFICIAL, UNOFFICIAL_A, UNOFFICIAL_B]
    rep5 = collect_evidence(["q"], lambda q: hits, question="2023年GDP增长多少",
                            budget=EvidenceBudget(max_items=2))
    assert len(rep5.items) <= 2
    assert json.loads(json.dumps(rep5.to_dict(), ensure_ascii=False))
    assert rep5.set_fingerprint
    # 证据集指纹与输入顺序无关（同集合不同顺序；不设预算，避免
    # 预算的「官方优先 + rank」选择本身带顺序性）
    rep6 = collect_evidence(["q"], lambda q: list(reversed(hits)),
                            question="2023年GDP增长多少")
    rep7 = collect_evidence(["q"], lambda q: list(hits),
                            question="2023年GDP增长多少")
    assert rep6.set_fingerprint == rep7.set_fingerprint


CASES = [
    case_official_whitelist,
    case_normalize_url,
    case_fingerprints,
    case_from_search_hits,
    case_dedup,
    case_budget,
    case_detect_conflicts,
    case_find_numeric_conflicts,
    case_extract_claims,
    case_detect_gaps,
    case_answer_from_evidence,
    case_answer_relevance_gate,
    case_bind_citations_explicit,
    case_bind_citations_overlap,
    case_consistency_match,
    case_consistency_partial,
    case_consistency_mismatch,
    case_consistency_not_comp,
    case_consistency_official_evidence,
    case_consistency_determinism,
    case_collect_evidence_paths,
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
