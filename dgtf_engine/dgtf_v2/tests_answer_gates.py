# -*- coding: utf-8 -*-
"""答案门判据（`dgtf_v2/answer_gates.py`）。

这套判据的历史很重要：本模块第一版把「α 低」当阻断依据，用真实产物一跑
**误杀 108 个正确答案**（黄河 5464 千米、HTTP 404 Not Found 全被判死）。
所以判据的重点不是「能抓坏样本」，而是**同时证明它不误杀**：

  1. 正例：三个人工确认的「答非所问」必须 blocked
  2. ★ 反例（防误杀）：真实正确答案必须**不** blocked —— 这是上一版翻车的地方
  3. α 永远只警示不阻断（拿不出证据的不能当降级依据）
  4. 默认 block=false ⇒ 对外 answer_ready 不变（零行为差）
  5. ★ 真实产物回归：全量扫一遍，blocked 且 ready 的必须 ≤ 5 个
"""
from __future__ import annotations

import glob
import json
import os
import pathlib
import re
import sys

V2 = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(V2.parent))

from dgtf_v2 import answer_gates as G  # noqa: E402

PASS, FAIL = [], []


def ck(n, ok, info=""):
    (PASS if ok else FAIL).append(n)
    print(("  OK  " if ok else "  FAIL") + " " + n + (("  — " + str(info)) if info else ""))


def main():
    # ── 1. 正例：三个实测「答非所问」──
    cases = [
        ("成年人正常心率是多少次每分钟？",
         "心率是指正常人安静状态下每分钟心跳的次数"),
        ("HTTP 301状态码表示什么？",
         "下面有不同的方式来指定哪个网址是规范的"),
        ("HTTP 503状态码表示什么？",
         "Retry-After 在 HTTP 协议中，响应首部Retry-After 表示用户代理需要"
         "等待多长时间之后才能继续发送请求"),
    ]
    for q, a in cases:
        g = G.evaluate(q, a)
        ck("★ 正例被抓：%s" % q[:16], g["verdict"] == "blocked", g["relevance"]["reason"])

    # ── 2. 反例：正确答案不许被骂 ──
    good = [
        ("黄河的长度是多少千米？", "5464千米"),
        ("珠穆朗玛峰的海拔是多少米？", "8844.43米"),
        ("2024年中国GDP增速最新数据是多少？", "5.0%"),
        ("我国法定结婚年龄是多少岁？", "二十二周岁"),
        ("中国空间站由几个舱段组成？", "三舱"),
        ("HTTP 404状态码表示什么？",
         "404 Not Found HTTP 响应状态码404 Not Found 指的是服务器找不到请求的资源"),
        ("HTTP 500状态码表示什么？", "500 Internal Server Error HTTP500 Internal"),
        ("HTTP 201状态码表示什么？", "201 Created HTTP201 Created 成功回應狀態碼"),
    ]
    for q, a in good:
        g = G.evaluate(q, a)
        ck("★ 反例不误杀：%s" % q[:16], g["verdict"] != "blocked",
           "%s / %s" % (g["verdict"], g["relevance"]["reason"]))

    # ── 3. α 永不阻断 ──
    for al in (-0.9, 0.0, 0.3, None):
        g = G.evaluate("HTTP 404状态码表示什么？", "404 Not Found 找不到资源", al)
        ck("α=%r 时不阻断（只警示）" % (al,), g["verdict"] != "blocked",
           "%s/%s" % (g["verdict"], g["agreement"]["verdict"]))
    g = G.evaluate("HTTP 404状态码表示什么？", "404 Not Found", -0.5)
    ck("α 极低 ⇒ 记 low 且 verdict=caveat",
       g["agreement"]["verdict"] == "low" and g["verdict"] == "caveat", g["verdict"])

    # ── 4. 边界 ──
    ck("空答案判 empty", G.relevance("黄河多长？", "   ")["verdict"] == "empty")
    ck("年份不作答案锚（GDP 题不因缺 2024 被判 suspect）",
       G.relevance("2024年中国GDP增速是多少？", "5.0%")["verdict"] == "ok")
    ck("数值题缺数值 ⇒ suspect",
       G.relevance("心率是多少次每分钟？", "心率是心脏跳动的次数")["verdict"] == "suspect")
    ck("实体题未提实体 ⇒ suspect",
       G.relevance("HTTP 301表示什么？", "一种重定向方式")["verdict"] == "suspect")
    ck("无锚题面 ⇒ weak（放行，不硬判）",
       G.relevance("随便问问", "随便答答")["verdict"] == "weak")
    ck("「表示什么」优先于「多少」（混合问法走实体判据）",
       G.question_kind("HTTP 431 表示什么，最多几个头？") == "entity")

    # ── 5. 引擎接线（静态 + 默认零行为差）──
    engs = sorted(V2.glob("engine/Meta-DGTF-V*.py"),
                  key=lambda p: [int(x) for x in re.findall(r"\d+", p.stem)[:3]])
    eng = engs[-1]
    src = eng.read_text(encoding="utf-8")
    ck("引擎接入 answer_gates（最新版 %s）" % eng.name,
       "from dgtf_v2.answer_gates import" in src)
    ck("默认配置登记 answer_gates 且 block 默认 False",
       '"answer_gates": {"enabled": True, "block": False}' in src)
    ck("产物出口含 quality.answer_gates",
       '_q0["answer_gates"] = _ag' in src)

    # ── 6. ★ 真实产物回归：不许大批误杀 ──
    #   ★ 路径必须相对**仓库根**：本判据由 run_v2_tests 在任意 cwd 下起子进程，
    #     用相对 "outputs/" 会静默找不到文件 ⇒ 这条防误杀的判据被 SKIP 掉
    #     （第一版就踩了：25 项全绿但最关键的那条没跑）。
    root = V2.parent.parent
    rows = []
    for p in glob.glob(str(root / "outputs" / "*.packed.json")):
        b = os.path.basename(p)
        if not re.match(r"^\d{8}_\d{6}_", b):
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        q = d.get("quality") or {}
        asm = q.get("answer_summary") or {}
        rows.append((str(d.get("question") or ""),
                     str(asm.get("answer") or ""),
                     bool(q.get("answer_ready")), q.get("tri_alpha")))
    if rows:
        hit = []
        for qq, aa, ready, al in rows:
            g = G.evaluate(qq, aa, al)
            if g["verdict"] == "blocked" and ready:
                hit.append((qq[:26], aa[:34]))
        ck("★ 真实产物回归：被拦且原本就绪的 ≤ 5 个（防误杀）",
           len(hit) <= 5, "命中 %d/%d：%s" % (len(hit), len(rows), hit[:4]))
        ck("★ 且确有命中（判据不是空转）", len(hit) >= 1, len(hit))
    else:
        print("  · SKIP 真实产物回归（无 outputs 回放数据）")

    print("\nPASS %d / FAIL %d" % (len(PASS), len(FAIL)))
    for f in FAIL:
        print("  - " + f)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
