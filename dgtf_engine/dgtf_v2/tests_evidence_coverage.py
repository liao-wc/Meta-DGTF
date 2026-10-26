# -*- coding: utf-8 -*-
"""Round 12 判据：uncovered 片段级覆盖 + 整体量语义加权（零 API）。

真实依据：黄河长度真跑 aq=needs_evidence，gaps=['uncovered:黄河的长度']
（原文是「黄河…全长约5464公里」），且答案取了官方「河段长3472千米」而非
多源「全长约5464公里」。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.evidence import (Evidence, EvidenceReport,  # noqa: E402
                              extract_numeric_claims,
                              is_official_source,
                              _overall_quantity_bonus,
                              _short_answer, _term_covered,
                              answer_from_evidence, detect_gaps)
from dgtf_v2.fact_flow import (_compact_numeric_answer,  # noqa: E402
                                     _looks_like_choice,
                                     _numeric_claim_answer,
                                     build_fact_card)

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


def ev(eid, snippet, official=False):
    return Evidence(evidence_id=eid, query="q", title="", url="u/" + eid,
                    snippet=snippet, domain="d" + eid, official=official,
                    fingerprint="fp_" + eid, rank=0)


def main():
    # ── A：片段级覆盖 ─────────────────────────────
    ck("A1 整短语命中仍算覆盖",
       _term_covered("黄河的长度", "黄河的长度为5464千米") is True)
    ck("A2 片段全命中算覆盖（黄河 + 长度）",
       _term_covered("黄河的长度", "黄河全长约5464公里，长度居全国第二") is True)
    ck("A3 缺片段不算覆盖（只有黄河、无长度近义）",
       _term_covered("黄河的长度", "黄河流域面积广阔") is False)
    ck("A4 缺片段不算覆盖（只有长度没有黄河）",
       _term_covered("黄河的长度", "河流长度排名") is False)
    ck("A5 空词项视为覆盖", _term_covered("", "x") is True)

    gaps = detect_gaps("黄河的长度是多少千米",
                       [ev("E1", "黄河全长约5464公里，中国第二长河"),
                        ev("E2", "黄河全长约5464公里", True)])
    ck("A6 detect_gaps 不再误报 uncovered（长度←全长近义覆盖）",
       not any(str(g).startswith("uncovered:") for g in gaps), gaps)

    gaps2 = detect_gaps("黄河的面积是多少平方千米",
                        [ev("E1", "黄河全长约5464公里，中国第二长河")])
    ck("A7 真缺目标项仍报 uncovered",
       any(str(g).startswith("uncovered:") for g in gaps2), gaps2)

    # ── A2：口语量词数值句（Round 15）────────────────
    ck("A8 「5400多公里」句子被识别为数值句",
       "5400" in _short_answer("黄河，我国第二大河。全长5400多公里。",
                               "黄河的长度是多少千米"))
    ck("A9 「约5464公里」句子被识别为数值句",
       "5464" in _short_answer("说明一段话。它全长约5464公里。",
                               "黄河有多长"))
    ck("A10 「5400余公里」句子被识别为数值句",
       "5400" in _short_answer("一些背景。全长5400余公里。",
                               "黄河的长度是多少千米"))

    # ── A3：展示紧凑的弱量词过滤（Round 15）──────────
    d1 = _compact_numeric_answer("黄河的长度是多少千米",
                                 "黄河流经9个省（区），全长5400多公里")
    ck("A11 展示不取弱量词「9个」（不得只给 9个）",
       d1 != "9个" and ("5400" in d1 or "公里" in d1), d1)
    d2 = _compact_numeric_answer("长江的长度是多少千米", "长江总长6280千米。")
    ck("A12 展示取强单位「6280千米」", "6280千米" in d2, d2)

    # ── A4：claim 级数值答案（Round 20）──────────────
    _gdp = ev("E1", "这其中，国内生产总值超过134万亿元，"
                     "按不变价格计算，比上年增长5.0%。")
    _gdp2 = ev("E2", "居民人均可支配收入实际增长5.3%。")
    ck("A13 GDP 增速取 5.0%（非人均收入 5.3%）",
       "5.0" in _numeric_claim_answer("2024年中国GDP增速是多少？",
                                     [_gdp, _gdp2]),
       _numeric_claim_answer("2024年中国GDP增速是多少？", [_gdp, _gdp2]))
    _hj = [ev("E3", "黄河上游河段长3472千米；中游1206千米；下游786千米。"),
           ev("E4", "黄河全长约5464千米，流域面积约79.5万平方千米。")]
    ck("A14 黄河长度取全长 5464（非分段 786/3472）",
       "5464" in _numeric_claim_answer("黄河的长度是多少千米？", _hj),
       _numeric_claim_answer("黄河的长度是多少千米？", _hj))
    ck("A15 非数值题 → 空（回退原答案逻辑）",
       _numeric_claim_answer("黄河发源于哪里？", _hj) == "")
    d3 = _compact_numeric_answer("2024年中国GDP增速是多少",
                                 "国内生产总值超过134万亿元，比上年增长5.0%")
    ck("A16 展示层增速题优先 %（非 134万）", "5.0%" in d3, d3)

    # ── A5：科学权威域白名单（Round 24）──────────────
    ck("A17 中科院域官方", is_official_source("https://ciomp.cas.cn/x") is True)
    ck("A18 科普中国/科普博览官方",
       is_official_source("https://www.kepu.net.cn/x") is True
       and is_official_source("https://cloud.kepuchina.cn/x") is True)
    ck("A19 商业博客仍非官方（负对照）",
       is_official_source("https://blog.csdn.net/x") is False)
    # ── A6：数值短答比较句过滤（Round 24）────────────
    _sa = _short_answer("光进入水中会变慢：只比真空中慢约90公里/秒。在水中光速减至约22.5万公里/秒。",
                      "光在水中传播的速度是多少")
    ck("A20 数值短答跳过比较句（取目标量）",
       ("22.5" in _sa) or ("22.4" in _sa), _sa)
    ck("A21 比较句数值不被当作答案", "90公里/秒" not in _sa, _sa)
    ck("A22 「光在水中传播的速度」词项片段覆盖（在/中切分）",
       _term_covered("光在水中传播的速度",
                     "光可以在水中传播，传播速度约22.4万公里/秒") is True)
    ck("A23 「中国」不被 中(?!国) 切坏（负对照）",
       _term_covered("中国GDP", "中国 GDP 总量 134 万亿元") is True)
    # ── A7：修订期感知（Round 28）────────────────────
    _prelim = ev("E1", "初步核算，2024年全年国内生产总值1349084亿元，比上年增长5.0%。")
    _final = ev("E2", "经最终核实，2024年国内生产总值1348066亿元，比上年增长5.0%。")
    _ans_rev = _numeric_claim_answer("2024年GDP总量最终核实是多少亿元？", [_prelim, _final])
    ck("A24 修订期感知：最终核实数值 1348066 优先",
       "1348066" in _ans_rev, _ans_rev)
    _ans_norm = _numeric_claim_answer("2024年GDP总量是多少亿元？", [_prelim, _final])
    ck("A25 非修订问句也取最新核实值（官方最新口径）",
       "1348066" in _ans_norm, _ans_norm)
    _ans_only_prelim = _numeric_claim_answer("2024年GDP总量是多少亿元？", [_prelim])
    # ── A8：日期类答案（Round 30）──────────────────
    _sa_date = _short_answer(
        "中华人民共和国立法法 2000年通过。1982年宪法是现行宪法，"
        "1982年12月4日通过。", "中国现行宪法是哪一年颁布的")
    ck("A27 19xx 日期可识别（1982 年宪法句）",
       "1982" in _sa_date and "宪法" in _sa_date, _sa_date)
    ck("A28 日期句按题面概念排序（不取无关文书日期）",
       "立法法" not in _sa_date, _sa_date)

    ck("A26 仅有初步核算时回退初步值（不空）",
       "1349084" in _ans_only_prelim, _ans_only_prelim)
    # ── A9：长复合词 2-gram 覆盖 + 日期证据加权（Round 31）──
    ck("A29 长复合词 2-gram 覆盖（中国现行宪法）",
       _term_covered("中国现行宪法是",
                     "1982年宪法是现行宪法，中国宪法颁布实施至今") is True)
    ck("A29b 2-gram 覆盖有防护：无关长词不通过",
       _term_covered("量子纠缠超距作用验证",
                     "1982年宪法颁布实施") is False)
    _policy_ev = [
        ev("E1", "中华人民共和国立法法 2000年通过，与宪法相关。"),
        ev("E2", "1982年12月4日，五届全国人大五次会议通过了现行有效的宪法。"),
    ]
    ck("A30 日期问句证据加权（取含 1982 的宪法页）",
       "1982" in answer_from_evidence(_policy_ev,
                                      "中国现行宪法是哪一年颁布的？"),
       answer_from_evidence(_policy_ev, "中国现行宪法是哪一年颁布的？"))
    # ── A10：日期问句展示收窄（Round 31）─────────────
    _date_ans = _compact_numeric_answer(
        "中国现行宪法是哪一年颁布的？",
        "1949年10月中华人民共和国成立后，先后制定、颁布了四部宪法，"
        "现行宪法为1982年宪法，并历经多次修正。")
    ck("A31 日期问句 display 收窄为 1982年", _date_ans == "1982年", _date_ans)

    # ── A11：年度口径优先（Round 32）──────────────────
    _cpi_ev = [
        ev("E1", "12月份，全国CPI环比持平，同比上涨0.1%。"),
        ev("E2", "扣除食品和能源价格的核心CPI同比上涨0.5%。"),
        ev("E3", "国家统计局：2024年全年CPI同比上涨0.2%。"),
    ]
    _cpi_ans = _numeric_claim_answer("2024年中国CPI涨幅是多少？", _cpi_ev)
    ck("A32 年度口径优先（取全年 0.2%，非月度/核心项）",
       "0.2" in _cpi_ans and "0.5" not in _cpi_ans, _cpi_ans)

    # ── A12：年份不一致拒答（Round 32）──────────────
    _rep_2023 = EvidenceReport(question="2024年中国CPI涨幅是多少？", queries=["q"], searches=1,
        items=[ev("E1", "2023年全年CPI上涨0.7%（官方）")],
        conflicts=[], gaps=["single_source"])
    _card_bad = build_fact_card("2024年中国CPI涨幅是多少？", _rep_2023)
    ck("A33 题面 2024 而证据只有 2023 → 拒答 unknown/year_mismatch",
       _card_bad.status == "unknown" and "year_mismatch" in _card_bad.gaps,
       (_card_bad.status, _card_bad.gaps))
    _rep_2024 = EvidenceReport(question="2024年中国CPI涨幅是多少？", queries=["q"], searches=1,
        items=[ev("E1", "国家统计局：2024年全年CPI同比上涨0.2%（官方）", official=True)],
        conflicts=[], gaps=["single_source"])
    _card_ok = build_fact_card("2024年中国CPI涨幅是多少？", _rep_2024)
    ck("A34 对应年份证据 → 正常 answered",
       _card_ok.status == "answered" and "0.2" in _card_ok.answer,
       (_card_ok.status, _card_ok.answer))
    # ── A13：分别序位/官方权威/万人（Round 33）──────────
    _nev_snip = ("2024年，我国汽车产销量分别达3128.2万辆和3143.6万辆；"
                "其中，新能源汽车产销量分别达1288.8万辆和1286.6万辆。")
    _nev_ans = _numeric_claim_answer("2024年中国新能源汽车产量是多少万辆？",
                                     [ev("E1", _nev_snip, official=True)])
    ck("A35 分别句按题面取产量（1288.8，非汽车总量/销量）",
       "1288.8" in _nev_ans and "3128" not in _nev_ans, _nev_ans)
    _pop_ans = _numeric_claim_answer("2024年中国出生人口是多少万人？",
                                     [ev("E2", "2024年全年出生人口954万人。",
                                         official=True)])
    ck("A36 「万人」单位可作答案（954 万人）", "954" in _pop_ans, _pop_ans)
    # 官方权威冲突消解：非官方口径冲突 + 官方可答 → answered + 标记
    _rep_nev = EvidenceReport(
        question="2024年中国新能源汽车产量是多少万辆？",
        queries=["q"], searches=2,
        items=[ev("E1", _nev_snip, official=True),
               ev("E2", "2023年新能源汽车产量958.7万辆。")],
        conflicts=[{"term": "2024 产量", "unit": "万",
                    "values": [1288.8, 958.7],
                    "evidence_ids": ["E1", "E2"]}],
        gaps=[])
    _card_nev = build_fact_card("2024年中国新能源汽车产量是多少万辆？",
                                _rep_nev)
    ck("A37 官方权威消解冲突 → answered + 标记",
       _card_nev.status == "answered"
       and "conflict_resolved_official_authority" in _card_nev.gaps,
       (_card_nev.status, _card_nev.gaps))
    # ── A14：周岁/现行性口径（Round 34）──────────────
    _claims = extract_numeric_claims("民法典规定结婚年龄男不得早于22周岁，女不得早于20周岁")
    ck("A38 周岁单位可被抽取",
       any(c.get("unit") == "周岁" and float(c.get("value")) == 22
           for c in _claims), _claims)
    _legal_ans = _numeric_claim_answer("我国法定结婚年龄是多少岁？",
        [ev("E1", "1931年施行的国民政府民法亲属编规定婚龄男18岁女16岁。",
            official=False),
         ev("E2", "现行民法典规定结婚年龄男不得早于22周岁，女不得早于20周岁。",
            official=True)])
    ck("A39 现行法优先（取 22/20 周岁，非 1931 旧规）",
       "22" in _legal_ans and "1931" not in _legal_ans, _legal_ans)
    # ── A15：历史旧规拒答（Round 34）──────────────
    _rep_old = EvidenceReport(
        question="我国法定结婚年龄是多少岁？", queries=["q"], searches=1,
        items=[ev("E1", "1931年施行的国民政府民法亲属编规定婚龄男18岁女16岁。",
                  official=True)], conflicts=[], gaps=["single_source"])
    _card_old = build_fact_card("我国法定结婚年龄是多少岁？", _rep_old)
    ck("A40 现行性问句遇历史旧规 → 拒答 (unknown/historical_answer_rejected)",
       _card_old.status == "unknown"
       and "historical_answer_rejected" in _card_old.gaps,
       (_card_old.status, _card_old.gaps))

    # ── A16：亿美元/贸易口径（Round 36）──────────────
    _trade_claims = extract_numeric_claims("2024年，我国贸易顺差9922亿美元。")
    ck("A41 亿美元单位可抽取",
       any(c.get("unit") == "亿美元" and float(c.get("value")) == 9922
           for c in _trade_claims), _trade_claims)

    # ── A17：比较年份不误判（Round 38）──────────────
    _rep_cmp = EvidenceReport(question="2024年中国贸易顺差是多少亿美元？", queries=["q"],
        searches=1,
        items=[ev("E1", "2024年我国国际收支口径货物贸易顺差7679亿美元，较2023年增长29%。", official=True)], conflicts=[], gaps=["single_source"])
    _card_cmp = build_fact_card("2024年中国贸易顺差是多少亿美元？", _rep_cmp)
    ck("A42 比较年份（较2023年）不算错配 → answered",
       _card_cmp.status == "answered" and "7679" in _card_cmp.answer,
       (_card_cmp.status, _card_cmp.answer))
    _rep_bad = EvidenceReport(question="2024年中国贸易顺差是多少亿美元？", queries=["q"],
        searches=1,
        items=[ev("E1", "2023年，我国进出口顺差8221亿美元。", official=True),
               ev("E2", "据海关统计，2023年我国贸易顺差8221亿美元，同比回落。",
                  official=True)], conflicts=[], gaps=[])
    _card_bad = build_fact_card("2024年中国贸易顺差是多少亿美元？", _rep_bad)
    ck("A43 真错年份（只给2023）仍拒答 year_mismatch",
       _card_bad.status == "unknown"
       and "year_mismatch" in _card_bad.gaps,
       (_card_bad.status, _card_bad.gaps))
    # ── A19：地点问句收窄（Round 43）──────────────────
    _loc_ans = _short_answer("1945年，美国国会同意邀请联合国将总部设在美国。""联合国总部位于纽约市曼哈顿。", "联合国的总部设在哪个城市？")
    ck("A46 地点问句取城市句（纽约市）",
       "纽约市" in _loc_ans and "1945" not in _loc_ans, _loc_ans)
    _loc_disp = _compact_numeric_answer("联合国的总部设在哪个城市？",
                                         "此次会议决定将联合国总部的地址设在纽约市附近")
    ck("A47 地点 display 收窄为纽约市", _loc_disp == "纽约市", _loc_disp)
    # ── A20：范围/复合单位/标记词项（Round 44）────────
    ck("A48 「次每分钟」全标记词项视为覆盖",
       _term_covered("次每分钟", "正常成年人每分钟心跳60到100次") is True)
    _fx = extract_numeric_claims("外汇储备连续12个月高于3.2万亿美元")
    ck("A49 万亿美元复合单位可抽取",
       any(c.get("unit") == "万亿美元" and abs(float(c.get("value")) - 3.2) < 1e-6
           for c in _fx), _fx)
    _rng_disp = _compact_numeric_answer("成年人正常心率是多少次每分钟？",
        "正常成人心率为60-100次/分，通常为70-80次/分。")
    ck("A50 范围型 display 收窄（60-100次/分）",
       _rng_disp == "60-100次/分", _rng_disp)
    # ── A21：范围型答案收窄（Round 45）──────────────
    _rng_ans = _short_answer("心率是指正常人安静状态下每分钟心跳的次数。""正常成人心率为60-100次/分。", "成年人正常心率是多少次每分钟？")
    ck("A51 范围型问句取区间句（60-100次/分）",
       "60-100" in _rng_ans, _rng_ans)
    # ── A22：亿美元精确值 display（Round 45）──────────
    _fx_disp = _compact_numeric_answer(
        "2024年末中国外汇储备是多少亿美元？",
        "截至2024年12月末，我国外汇储备规模为32024亿美元，较11月末下降635亿美元。")
    ck("A52 亿美元精确值 display（32024亿美元）",
       _fx_disp == "32024亿美元", _fx_disp)

    # ── A23：命名型答案收窄（Round 47）──────────────
    _name_ans = _short_answer("日前发布空间站名称。经征名，空间站命名为“天宫”，货运飞船命名为“天舟”。",
                            "中国空间站的名字是什么？")
    ck("A53 命名型问句取命名句（天宫）",
       "天宫" in _name_ans and "命名为" in _name_ans, _name_ans)
    # ── A24：全长口径 display（Round 48）──────────────
    _whole_disp = _compact_numeric_answer(
        "港珠澳大桥全长多少公里？",
        "香港口岸至珠海口岸全长约42公里。再加上约13.4公里长的珠海接线，"
        "总长度为55公里。")
    ck("A54 全长问句 display 取总长 55公里（非分段 42）",
       _whole_disp == "55公里", _whole_disp)

    # ── A25：亿斤单位（Round 51）──────────────────
    _grain_claims = extract_numeric_claims("2024年全国粮食总产量14130亿斤，增长1.6%。")
    ck("A55 亿斤复合单位可抽取",
       any(c.get("unit") == "亿斤" and float(c.get("value")) == 14130
           for c in _grain_claims), _grain_claims)
    _grain_disp = _compact_numeric_answer("2024年我国粮食总产量是多少亿斤？",
        "全国粮食总产量14130亿斤，比上年增长1.6%。")
    ck("A56 粮食题 display 取亿斤值（非 1.6%）",
       "14130" in _grain_disp and "亿斤" in _grain_disp, _grain_disp)
    # ── A26：成年年龄语境（Round 52）──────────────
    _adult_ans = _numeric_claim_answer("民法典规定多少岁成年？",
        [ev("E1", "民法典规定：十八周岁以上的自然人为成年人。八周岁以上的未成年人为限制民事行为能力人。",
            official=True)])
    ck("A57 成年题取成年人语境（十八周岁）",
       "十八" in _adult_ans or "18" in _adult_ans, _adult_ans)
    # ── A27：列举型答案收窄（Round 55）──────────────
    _enum_ans = _short_answer("奥林匹克标志最早设计。起初采用蓝、黄、黑、绿、红色作为五环的颜色。",
                           "奥林匹克五环的颜色有哪几种？")
    ck("A58 列举问句取顿号列举句",
       "蓝、黄、黑、绿、红" in _enum_ans, _enum_ans)
    _enum_disp = _compact_numeric_answer("奥林匹克五环的颜色有哪几种？",
        "起初采用蓝、黄、黑、绿、红色作为五环的颜色。")
    ck("A59 列举 display 收窄（颜色列举短语）",
       "蓝、黄、黑、绿、红" in _enum_disp, _enum_disp)
    # ── A28：地点国家名 display（Round 59）──────────
    _country_disp = _compact_numeric_answer("联合国总部设在哪个国家？",
        "联合国总部设在美国纽约，是最大的国际组织。")
    ck("A60 国家名 display 收窄（美国）",
       _country_disp == "美国", _country_disp)
    # ── A29：复合双值展示（Round 62）────────────────
    _dual_disp = _compact_numeric_answer("我国法定结婚年龄是多少岁？",
        "我国婚姻法第六条明确规定，结婚年龄，男不得早于二十二周岁，女不得早于二十周岁。")
    ck("A61 结婚年龄双值展示（男22周岁、女20周岁）",
       _dual_disp == "男22周岁、女20周岁", _dual_disp)
    # ── A31：成年年龄 sanity（Round 85）──────────────
    _rep_adult = EvidenceReport(
        question="民法典规定多少岁成年？", queries=["q"], searches=1,
        items=[ev("E1", "民法典第十七条：十八周岁以上的自然人为成年人。",
                  official=True)], conflicts=[], gaps=["single_source"])
    _card_adult = build_fact_card("民法典规定多少岁成年？", _rep_adult)
    ck("A63 成年题取十八周岁（display 收窄）",
       _card_adult.status == "answered"
       and "十八周岁" in _card_adult.answer
       and _card_adult.to_dict().get("answer_display") == "十八周岁",
       (_card_adult.status, _card_adult.answer,
        _card_adult.to_dict().get("answer_display")))
    # ── A34：选择题 uncovered 豁免（Round 91）──────────────
    ck("A67 选项题 gaps 过滤 uncovered/no_official_source",
       _looks_like_choice("以下哪项属于可再生能源？"
                          "A. 煤炭 B. 太阳能 C. 石油 D. 天然气") is True)

    # ── A32：选择题官方源豁免（Round 86）──────────────
    ck("A64 选择题识别（A./B./C./D. ≥2）",
       _looks_like_choice("以下哪项属于可再生能源？"
                          "A. 煤炭 B. 太阳能 C. 石油 D. 天然气") is True)
    ck("A65 非选择题不识别", _looks_like_choice("水的沸点是多少摄氏度？") is False)

    # ── A33：辟谣证据降权（Round 88）──────────────
    _debunk_ans = answer_from_evidence([
        ev("E1", "间质是人体最大的器官？专家：说法并不科学，属流言。",
           official=True),
        ev("E2", "皮肤是人体最大的器官，成年人皮肤面积约1.5–2平方米。",
           official=True)],
        "人体最大的器官是什么？")
    ck("A66 辟谣证据降权（取皮肤而非流言文）",
       "皮肤" in _debunk_ans and "流言" not in _debunk_ans, _debunk_ans)
    # ── A36：进出口整体量不被出口/进口子项误伤（Round 92）──────
    _rep_tr = EvidenceReport(
        question="2024年我国货物贸易进出口总值是多少万亿元？",
        queries=["q"], searches=1,
        items=[ev("E1", "2024年我国货物贸易进出口总值43.85万亿元，同比增长5%。", official=True)],
        conflicts=[], gaps=[])
    _ans_tr = _numeric_claim_answer(
        "2024年我国货物贸易进出口总值是多少万亿元？",
        list(_rep_tr.items))
    ck("A70 进出口整体量取 43.85万亿元", "43.85" in _ans_tr and "万亿" in _ans_tr,
       _ans_tr)

    # ── A38：命名问句不被数值主张劫持（Round 93）──────────
    ck("A72 命名问句不走数值答案",
       _numeric_claim_answer(
           "世界上海拔最高的高原是什么？",
           [ev("E1", "青藏高原平均海拔4000米以上。", official=True)]) == "")
    # ── A37：命名问句定义句优先（Round 93）──────────────
    _name_ans = answer_from_evidence([
        ev("E1", "... 它包括中国藏自治区全部和青海省、新疆维吾尔自治区…总面积250万平方千米", official=True),
        ev("E2", "青藏高原是世界上海拔最高的高原，平均海拔4000米以上。", official=True),
    ], "世界上海拔最高的高原是什么？")
    ck("A71 命名问句取定义句（青藏高原）",
       "青藏高原" in _name_ans and "它包括" not in _name_ans, _name_ans)

    # ── A39：万亿元单位抽取（Round 104）──────────────
    from dgtf_v2.evidence import extract_numeric_claims as _enc
    _wc = _enc("2024年我国货物贸易进出口总值43.85万亿元")
    ck("A73 万亿元单位抽取",
       any(str(c.get("unit")) == "万亿元" and abs(float(c.get("value")) - 43.85) < 1e-6
           for c in _wc), _wc)

    # ── A40：法定例外条款（Round 105）──────────────
    _edu_ev = EvidenceReport(
        question="我国义务教育法规定小学入学年龄是多少岁？",
        queries=["q"], searches=1,
        items=[ev("E1", "义务教育法第五条规定，凡年满六周岁的儿童，应当入学接受义务教育；"
                            "条件不具备的地区，可以推迟到七周岁入学。", official=True),
               ev("E2", "义务教育法第十一条规定，凡年满六周岁的儿童，其父母或者其他法定"
                            "监护人应当送其入学接受并完成义务教育。", official=True)],
        conflicts=[],
        gaps=["uncovered:我国义务教育法规定小学入学年龄"])
    _edu_card = build_fact_card(
        "我国义务教育法规定小学入学年龄是多少岁？", _edu_ev)
    ck("A74 法定例外条款取六周岁（年满/应当优先）",
       _edu_card.status == "answered" and "六周岁" in str(_edu_card.answer)
       and "七周岁" not in str(_edu_card.answer)
       and not any(str(g).startswith("uncovered:") for g in _edu_card.gaps),
       (_edu_card.status, _edu_card.answer, _edu_card.gaps))

    # ── A41：血压标准 / 外语城市展示（Round 106）──────────
    ck("A75 血压标准 140/90mmHg 展示",
       _compact_numeric_answer(
           "我国成年人高血压的诊断标准是多少？",
           "我国高血压诊断标准为收缩压≥140mmHg和/或舒张压≥90mmHg。")
       == "140mmHg和/或舒张压≥90mmHg" or "140" in _compact_numeric_answer(
           "我国成年人高血压的诊断标准是多少？",
           "我国高血压诊断标准为收缩压≥140mmHg和/或舒张压≥90mmHg。"))
    ck("A76 外语城市地点展示（日内瓦）",
       _compact_numeric_answer(
           "世界卫生组织总部设在哪个城市？",
           "世卫组织的全球办事处设在瑞士日内瓦")
       == "日内瓦",
       _compact_numeric_answer(
           "世界卫生组织总部设在哪个城市？",
           "世卫组织的全球办事处设在瑞士日内瓦"))

    # ── A42：法定节假日 13 天（改前 11 天降权，Round 106）──────
    _hol_ev = EvidenceReport(
        question="我国现行法定节假日一年共有多少天？",
        queries=["q"], searches=1,
        items=[ev("E1", "改前我国全体公民放假的节日共11天。此次修改后13个节日共放假13天。",
                   official=True)], conflicts=[], gaps=[])
    _hol = _numeric_claim_answer(
        "我国现行法定节假日一年共有多少天？", list(_hol_ev.items))
    ck("A77 节假日取 13 天（改前 11 天降权）",
       "13天" in _hol and "11天" not in _hol.split("13天")[0], _hol)

    # ── A43：地点 uncovered 豁免（Round 106）──────────────
    _who_ev = EvidenceReport(
        question="世界卫生组织总部设在哪个城市？",
        queries=["q"], searches=1,
        items=[ev("E1", "世卫组织的全球办事处设在瑞士日内瓦。", official=True),
               ev("E2", "世界卫生组织总部位于瑞士日内瓦。", official=True)],
        conflicts=[], gaps=["uncovered:城市"])
    _who_card = build_fact_card("世界卫生组织总部设在哪个城市？", _who_ev)
    ck("A78 地点 uncovered 豁免",
       _who_card.status == "answered"
       and not any(str(g).startswith("uncovered:")
                   for g in _who_card.gaps),
       (_who_card.status, _who_card.gaps))

    # ── A44：节假日逐项聚合（Round 107）──────────────
    _fest_ev = EvidenceReport(
        question="我国现行法定节假日一年共有多少天？",
        queries=["q"], searches=1,
        items=[
            ev("E1", "2025年起施行的放假办法：元旦，放假1天；春节，放假4天。", official=True),
            ev("E2", "清明节，放假1天；劳动节，放假2天；端午节，放假1天。", official=True),
            ev("E3", "中秋节，放假1天；国庆节，放假3天。", official=True),
        ], conflicts=[], gaps=[])
    _fest = _numeric_claim_answer(
        "我国现行法定节假日一年共有多少天？", list(_fest_ev.items))
    ck("A79 节假日逐项聚合=13天", "13天" in _fest, _fest)

    # ── A45：万公里/舱段展示（Round 108）──────────────
    ck("A80 万公里展示",
       _compact_numeric_answer(
           "截至2024年底我国高速公路总里程是多少万公里？",
           "高速公路里程19.07万公里、增加0.70万公里") == "19.07万公里",
       _compact_numeric_answer(
           "截至2024年底我国高速公路总里程是多少万公里？",
           "高速公路里程19.07万公里、增加0.70万公里"))
    ck("A81 舱段数量展示",
       _compact_numeric_answer(
           "中国空间站由几个舱段组成？",
           "三舱组合体质量约66吨，设计寿命不小于10年") == "三舱",
       _compact_numeric_answer(
           "中国空间站由几个舱段组成？",
           "三舱组合体质量约66吨，设计寿命不小于10年"))

    # ── B：整体量语义加权 ────────────────────────
    ck("B1 问长度 + 全长标记 → 加分",
       _overall_quantity_bonus("黄河全长约5464公里", "黄河的长度是多少千米") > 0)
    ck("B2 非整体量题 → 不加分",
       _overall_quantity_bonus("黄河全长约5464公里", "中国GDP增长多少") == 0
       and _overall_quantity_bonus("黄河全长约5464公里", "如何提高GDP") == 0)
    ck("B3 河段长文本（含「长」但无整体量标记）→ 不加分",
       _overall_quantity_bonus("河段长3472千米", "黄河的长度是多少千米") == 0)

    off_wrong = ev("E3", "黄河上游河段长3472千米", official=True)
    uno_right = ev("E1", "黄河全长约5464公里")
    ans = answer_from_evidence([off_wrong, uno_right],
                               "黄河的长度是多少千米")
    ck("B4 官方分段值 vs 非官方全长值 → 取全长 5464（语义加权反超官方 0.15）",
       "5464" in ans, ans)
    ans2 = answer_from_evidence([off_wrong, uno_right], "黄河有多长")
    ck("B5 同义问法也生效", "5464" in ans2, ans2)

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
