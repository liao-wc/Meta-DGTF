# -*- coding: utf-8 -*-
"""Round 19 判据：假冲突修复（主语残留/裸数字）+ 词项 token 级覆盖（零 API）。

真实反例：「2024年中国GDP增速最新数据是多少？」被 3 处数值冲突打成 conflict：
5.3 其实是人均可支配收入、3.5 是第一产业、4.0 是 R&D 支出——都因分句短尾
「比上年增长%」丢主语而被归到同一桶。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.evidence import (Evidence, _term_covered,  # noqa: E402
                              detect_conflicts)

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
    # ① GDP vs 第一产业（不同主语、短尾分句）→ 不再假冲突
    t = ("2024年，国内生产总值比上年增长5.0%。第一产业增加值比上年增长3.5%。")
    c = detect_conflicts([ev("E1", t)])
    ck("① 同文 GDP 5.0% 与第一产业 3.5% 不判冲突", len(c) == 0, c)

    # ② 同一主语不同值 → 仍判冲突（负对照）
    c2 = detect_conflicts([
        ev("E1", "2024年，国内生产总值比上年增长5.0%。"),
        ev("E2", "2024年，国内生产总值比上年增长4.8%。"),
    ])
    ck("② 同主语 5.0% vs 4.8% 仍判冲突", len(c2) == 1, c2)

    # ③ 跨证据 GDP 与第一产业 → 不冲突
    c3 = detect_conflicts([
        ev("E1", "2024年，国内生产总值比上年增长5.0%。"),
        ev("E2", "2024年，第一产业增加值比上年增长3.5%。"),
    ])
    ck("③ 跨证据 GDP vs 第一产业不判冲突", len(c3) == 0, c3)

    # ④ 裸数字（无单位无上下文）不算可比较主张
    c4 = detect_conflicts([
        ev("E1", "2024年R&D经费支出36130亿元，投入强度4.0"),
        ev("E2", "2024年国内生产总值增长5.0%"),
    ])
    ck("④ 裸数字（4.0 无单位）不参与冲突", len(c4) == 0, c4)

    # ⑤ 词项 token 级覆盖（GDP 题）
    corpus = ("2024年中国国内生产总值增长5.0%，第一产业增加值增长3.5%；"
              "全年居民人均可支配收入实际增长5.3%。")
    ck("⑤ 词项「2024年中国GDP增速最新数据」被 token 级覆盖",
       _term_covered("2024年中国GDP增速最新数据", corpus) is True)
    ck("⑥ 负对照：缺 GDP 词项则不覆盖",
       _term_covered("2024年中国CPI涨幅最新数据", corpus) is False,
       )
    ck("⑦ 增速近义（增长）算覆盖",
       _term_covered("中国GDP增速", "中国GDP同比增长5.0%") is True)

    # ⑧ 确定性
    a = detect_conflicts([ev("E1", t)])
    b = detect_conflicts([ev("E1", t)])
    ck("⑧ 确定性：两次结果一致", a == b)

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
