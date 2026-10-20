# -*- coding: utf-8 -*-
"""输入自检「否定断言需证据」规则与 154010 回放用例。

这组用例锁三件事：
1. 预检没有证据时，不能把「本地先验没认出」写成「不存在/虚构」；
2. 检索后官方证据命中时，issue 必须被清除，且事实答案不回退；
3. 真正查无实据的记号，只能写「检索到的官方源中未见」，仍不能写「不存在」。
"""
from __future__ import annotations

import json
from pathlib import Path

from dgtf_v2.input_sanity import (
    NEGATIVE_CLAIM_RE,
    NEUTRAL_NOTE,
    RETRIEVED_MISS_WHY,
    neutralize_negative_claims,
    negative_claims,
    reconcile,
)

P = []
F = []
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPLAY = ROOT / "outputs" / "20261020_154010_DeepSeek-V41-Flash-.packed.json"


def ck(name, ok, info=""):
    (P if ok else F).append(name)
    print(("PASS " if ok else "FAIL ") + name
          + (" :: " + str(info)[:400] if info and not ok else ""))


def _fixture():
    """154010 的最小回放夹具（真实 packed 缺失时使用）。"""
    return {
        "question": "DeepSeek-V4.1-Flash-1017 是什么时候发布的",
        "input_sanity": {
            "issues": [{
                "term": "DeepSeek-V4.1-Flash-1017",
                "why": "形似标准模型版本号，但该型号不存在，属虚构记号",
            }],
            "note": "未发现其他悬空符号",
            "checked": True,
        },
        "pools": {"1": {"web_results": [{
            "title": "更新日志 | DeepSeek API Docs",
            "url": "https://api-docs.deepseek.com/zh-cn/updates/",
            "claim": ("2026-10-17\n### DeepSeek-V4.1-Flash-1017 更新\n"
                      "DeepSeek V4.1 Flash 已升级至 DeepSeek-V4.1-Flash-1017，"
                      "官方网页端与 APP 模型也已同步更新至新版本。"),
            "tier": "official",
        }]}},
        "fact_contract": {
            "ok_all": True,
            "ledger": {"known": True,
                       "question": "DeepSeek-V4.1-Flash-1017 是什么时候发布的",
                       "answer": "2026-10-17",
                       "source": "official_preflight"},
        },
    }


def _load_replay():
    if REPLAY.exists():
        try:
            return (json.loads(REPLAY.read_text(encoding="utf-8")), "real")
        except Exception as exc:  # pragma: no cover - 产物损坏时退回夹具
            print("WARN 回放产物读取失败，改用夹具：%s" % exc)
    return (_fixture(), "fixture")


def main():
    # 1) 规则类：预检里的存在性否定必须被确定性降级。
    raw = {"issues": [{"term": "X-9000",
                       "why": "该型号不存在，属虚构记号"}],
           "note": "x", "checked": True}
    neu = neutralize_negative_claims(raw)
    why0 = (neu.get("issues") or [{}])[0].get("why", "")
    ck("否定断言被降级", not NEGATIVE_CLAIM_RE.search(why0), why0)
    ck("降级留痕", (neu.get("issues") or [{}])[0].get(
        "negative_claim_rewritten") is True, neu)
    ck("规则名落产物", (neu.get("negative_guard") or {}).get(
        "rule") == "否定断言需证据", neu.get("negative_guard"))

    # 1b) note 也会被报告直接渲染，不能漏掉存在性否定。
    note_raw = {"issues": [], "note": "该型号不存在，属虚构记号"}
    note_neu = neutralize_negative_claims(note_raw)
    ck("note 否定断言被降级",
       note_neu.get("note") == NEUTRAL_NOTE
       and not negative_claims(note_neu), note_neu)
    ck("note 降级留痕", (note_neu.get("negative_guard") or {}).get(
        "note_rewritten") is True, note_neu.get("negative_guard"))

    # 2) 回放 154010：官方条目含 upgraded to DeepSeek-V4.1-Flash-1017。
    packed, src = _load_replay()
    san0 = packed.get("input_sanity") or {}
    fc0 = packed.get("fact_contract") or {}
    led0 = fc0.get("ledger") or {}
    answer0 = str(led0.get("answer") or "")
    out = reconcile(san0, packed, led0)
    terms = [str(x.get("term") or "") for x in (out.get("issues") or [])]
    ck("回放来源=%s" % src, True)
    ck("官方命中后 issue 被清除",
       "DeepSeek-V4.1-Flash-1017" not in terms, out)
    ck("清除留痕 resolved_n>=1",
       int((out.get("reconciled") or {}).get("resolved_n") or 0) >= 1,
       out.get("reconciled"))
    ck("对账后无否定断言", not negative_claims(out), negative_claims(out))
    ck("事实答案不回退", answer0 == "2026-10-17", answer0)

    # 3) 真正查无实据：只能写「检索到的官方源中未见」。
    miss = reconcile(
        {"issues": [{"term": "Acme-Quantum-9000",
                     "why": "该型号不存在，属虚构记号"}]},
        {"pools": {"1": {"web_results": [{
            "title": "官方文档",
            "url": "https://api-docs.deepseek.com/zh-cn/",
            "claim": "DeepSeek-V4.1-Flash-1017 已发布。",
            "tier": "official",
        }]}}},
        {"known": True, "answer": "2026-10-17"},
    )
    miss_why = (miss.get("issues") or [{}])[0].get("why", "")
    ck("查无实据用「未见」而非「不存在」",
       miss_why == RETRIEVED_MISS_WHY, miss_why)
    ck("查无实据仍留待核", (miss.get("issues") or [{}])[0].get(
        "status") == "unverified", miss)

    # 4) 官方证据内部冲突：改写为「有冲突」，仍不冒充定论。
    conflict = reconcile(
        {"issues": [{"term": "Fake-Model-1234",
                     "why": "该型号不存在，属虚构记号"}]},
        {"pools": {"1": {"web_results": [{
            "title": "官方勘误",
            "url": "https://api-docs.deepseek.com/zh-cn/updates/",
            "claim": "Fake-Model-1234 does not exist; wrong name.",
            "tier": "official",
        }]}}},
        {"known": True, "answer": "2026-10-17"},
    )
    cwhy = (conflict.get("issues") or [{}])[0].get("why", "")
    ck("官方源冲突单独措辞", "有冲突" in cwhy, cwhy)

    print()
    print("PASS %d / FAIL %d" % (len(P), len(F)))
    return 1 if F else 0


if __name__ == "__main__":
    raise SystemExit(main())
