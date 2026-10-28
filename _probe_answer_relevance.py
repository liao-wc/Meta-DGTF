# -*- coding: utf-8 -*-
"""答案相关性检测：答案有没有回答**这个问题**。

动机（实测）：当前产物里出现「答非所问但过程门全过」——
  · 「HTTP 301 表示什么」→ 答案「下面有不同的方式来指定哪个网址是规范的」
  · 「HTTP 401 表示什么」→ 答案主句讲 100 状态码，401 只在括号里
这两个都 `answer_ready=True`、`answer_quality=verified`。
⇒ 过程门（四层标准）+ 证据门（official evidence）都过了，但没人校验
   「答案说的是不是题问的那件事」。

方法（可复算、不引入外部判断）：
  1. 从题目抽"标识型 token"：数字串、英文缩写、引号内术语、中文名词块
  2. 检查答案是否命中**最强 token**（最长数字串 / 首个英文缩写）
  3. 命不中就标 suspect —— 只作线索，最终由人看原文
"""
from __future__ import annotations

import glob
import json
import os
import re
from collections import Counter

NUM = re.compile(r"\d{2,5}")
ABBR = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]{1,}")
CJK = re.compile(r"[\u4e00-\u9fa5]{2,}")

#: 题面里常见但不具标识性的词（出现不算命中）
STOP = {
    "什么", "表示", "是否", "多少", "哪些", "如何", "为什么", "怎么", "介绍",
    "解释", "说明", "作用", "意思", "含义", "状态", "代码", "状态码", "协议",
    "请问", "一下", "有", "的", "是", "在", "和", "与",
}


def key_tokens(question: str):
    """返回 (数字 token, 英文缩写 token, 中文 token) 三组。

    ★ 年份不是答案锚：题面「2024年中国GDP增速是多少」里 2024 是**限定条件**，
      答案「5.0%」不含 2024 依然完全正确。第一版没排除年份 ⇒ 11 个正确样本
      被判 suspect（方向错的判据比没判据更危险）。这里把 1900–2099 剔除；
      只有题面**除年份外没有别的数字**时才允许年份兜底。
    """
    raw_nums = NUM.findall(question)
    # ★ 剔除年份后**不要兜底填回**：题面只有年份的数值题（「2024年GDP增速」），
    #   答案本就不含年份 ⇒ 用年份当锚会 100% 误判。让它落到中文/单位锚上。
    nums = [n for n in raw_nums if not (len(n) == 4 and 1900 <= int(n) <= 2099)]
    abbrs = [a for a in ABBR.findall(question)
             if not re.fullmatch(r"\d+", a) and a.lower() not in
             ("http", "https", "the", "a", "an", "is", "of", "in", "to")]
    cj = [c for c in CJK.findall(question) if c not in STOP and len(c) >= 2]
    return nums, abbrs, cj


NUMERIC_Q = re.compile(r"多少|几[个项种]|多大|多高|多长|百分之|几成|占比|增速|涨幅|总量")
DIGIT = re.compile(r"[0-9]|[一二三四五六七八九十百千万亿两]{1,}")


def check_answer(question: str, answer: str):
    """返回 (verdict, 依据)。verdict ∈ ok / suspect / weak_no_key / empty。

    ★ 必须按题型分叉（第一版没分，11 个正确的数值题被判 suspect）：
      · 数值型题（多少/几/多大/增速…）：答案**本来就该是纯数字**，
        不含题目任何 token 是正常的 ⇒ 判据 = 答案里有数字，不比 token。
      · 实体型题（X 表示什么 / 是什么）：答案应提到题干实体 ⇒ 才比 token。
    ★ 本检测的能力边界（如实写在结论里）：它只能抓「答案完全没提题目实体」，
      **抓不到「提了实体但主句答错」**（如 401 的答案主句讲 100、401 只在括号里）。
      后者需要语义判官，不是 token 能解决的。
    """
    ans = answer or ""
    if not ans.strip():
        return "empty", "答案为空"
    if NUMERIC_Q.search(question) and not re.search(r"表示什么|是什么|的定义", question):
        return ("ok" if DIGIT.search(ans) else "suspect"), "数值题·看是否给数"
    nums, abbrs, cj = key_tokens(question)
    if nums:
        anchor = max(nums, key=len)
        return ("ok" if anchor in ans else "suspect"), "数字锚 %r" % anchor
    if abbrs:
        anchor = abbrs[0]
        if len(anchor) <= 2:          # A. / B. 这类选项标号不是实体
            return "weak_no_key", "锚太弱 %r" % anchor
        return ("ok" if anchor.lower() in ans.lower() else "suspect"), \
            "缩写锚 %r" % anchor
    if cj:
        anchor = max(cj, key=len)[:4]
        return ("ok" if anchor in ans else "weak_no_key"), "中文锚 %r" % anchor
    return "weak_no_key", "题面无可用锚"


def main():
    rows = []
    for p in glob.glob("outputs/*.packed.json"):
        b = os.path.basename(p)
        if not re.match(r"^\d{8}_\d{6}_", b):
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        q = d.get("quality") or {}
        asm = q.get("answer_summary") or {}
        rows.append({
            "file": b,
            "day": b[:8],
            "question": str(d.get("question") or ""),
            "answer": str(asm.get("answer") or ""),
            "ready": bool(q.get("answer_ready")),
            "cov": q.get("coverage"),
            "aq": (d.get("decision_trace") or {}).get("answer_quality"),
        })
    rows.sort(key=lambda r: r["file"])

    res = Counter()
    bad = []
    for r in rows:
        v, why = check_answer(r["question"], r["answer"])
        r["verdict"], r["why"] = v, why
        res[(v, r["ready"])] += 1
        if v in ("suspect", "empty"):
            bad.append(r)

    print("=" * 74)
    print("答案相关性检测 · %d 个真跑次" % len(rows))
    print("=" * 74)
    print("\n(判据结果, 对外 answer_ready) → 次数")
    for k, v in sorted(res.items(), key=lambda x: -x[1]):
        print("   %-22s ready=%-5s → %3d" % (k[0], k[1], v))

    miss = [r for r in bad if r["ready"]]
    print("\n★ 答非所问但被判 ready：%d 个" % len(miss))
    for r in miss[:12]:
        print("   %s  cov=%.2f  %s" % (r["file"][:34], r["cov"] or 0, r["why"]))
        print("      Q: %s" % r["question"][:52])
        print("      A: %s" % r["answer"].replace("\n", " ")[:88])

    print("\n★ 全部 suspect/empty（含未 ready）：%d 个" % len(bad))
    for r in bad[:8]:
        print("   ready=%-5s %s | %s" % (r["ready"], r["file"][:30],
                                         r["why"]))

    # 分日对比
    print("\n按日：suspect 占该日比例")
    byday = Counter()
    totday = Counter()
    for r in rows:
        totday[r["day"]] += 1
        if r["verdict"] in ("suspect", "empty"):
            byday[r["day"]] += 1
    for day in sorted(totday):
        print("   %s  %2d/%-3d  %3.0f%%" % (day, byday[day], totday[day],
                                           100 * byday[day] / totday[day]))

    out = {"n": len(rows), "suspect": len(bad),
           "suspect_but_ready": len(miss),
           "details": [{k: r[k] for k in ("file", "question", "verdict",
                                          "why", "ready", "cov")}
                       for r in bad]}
    json.dump(out, open("docs/答案相关性检测_20261028.json", "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n写出 docs/答案相关性检测_20261028.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
