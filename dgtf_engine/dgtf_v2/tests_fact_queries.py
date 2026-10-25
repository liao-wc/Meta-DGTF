# -*- coding: utf-8 -*-
"""Round 16 判据：HTTP 状态码官方站内检索 query（中文紧邻数字的 \\b 修复）。"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from dgtf_v2.fact_flow import extract_queries  # noqa: E402

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


def main():
    q1 = "HTTP 404状态码表示什么？"
    qs1 = extract_queries(q1)
    ck("① 「404状态码」（中文紧邻）加入 MDN 站内检索",
       any("site:developer.mozilla.org" in x and "404" in x for x in qs1), qs1)
    ck("② 原问题 query 仍在首位", qs1 and qs1[0] == q1, qs1[:2])

    qs2 = extract_queries("HTTP 500是什么错误")
    ck("③ 500 同时加入 MDN 与 RFC 站内检索",
       any("site:developer.mozilla.org" in x for x in qs2)
       and any("site:rfc-editor.org" in x for x in qs2), qs2)

    qs3 = extract_queries("HTTP协议怎么工作")
    ck("④ 无状态码（HTTP 协议）→ 不注入站内检索",
       not any("site:" in x for x in qs3), qs3)

    qs4 = extract_queries("1404年发生了什么")
    ck("⑤ 4 位年份（1404）→ 不误注入 1-5xx 站内检索",
       not any("site:" in x for x in qs4), qs4)

    qs5 = extract_queries("HTTP 404状态码表示什么？")
    ck("⑥ 确定性：两次结果一致", qs1 == qs5)

    ck("⑦ 查询数受 max(1, limit) 约束",
       len(extract_queries("HTTP 404状态码表示什么？", limit=2)) <= 2,
       extract_queries("HTTP 404状态码表示什么？", limit=2))

    qs6 = extract_queries("我国法定结婚年龄是多少岁？")
    ck("⑧ 法定类补「现行 民法典」查询",
       any("民法典" in x for x in qs6), qs6)
    qs7 = extract_queries("2024年中国贸易顺差是多少亿美元？")
    ck("⑨ 贸易口径类补海关总署查询",
       any("海关总署" in x for x in qs7), qs7)
    ck("⑩ 扩展不越界（HTTP 协议题仍无 site:）",
       not any("site:" in x for x in qs3))

    qs8 = extract_queries("联合国的总部设在哪个城市？")
    ck("⑪ 国际组织类补官方站内查询（un.org）",
       any("site:un.org" in x for x in qs8), qs8)
    ck("⑫ 国际组织扩展不干扰普通题",
       not any("site:un.org" in x for x in qs3))
    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())
