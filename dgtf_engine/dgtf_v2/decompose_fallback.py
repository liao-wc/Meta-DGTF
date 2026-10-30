# -*- coding: utf-8 -*-
"""研究层拆解失败/全不可判定时的确定性回退（V2.2.90 / V2.2.96）。

V2.2.90：LLM 输出为空 -> 用探针/线头生成 partial 子问题（让分母存在）。
V2.2.96：LLM 有输出但**全部不可判定** -> 追加探针/线头派生的 partial 子问题，
保留原判定（不篡改），只补可答分母（source 前缀 FB: 便于审计）。
V2.2.97：探针/线头也为空时，用修行层 candidates 兜底（source C#；题面前缀"候选判定："），
覆盖「LLM 空输出 + 探针/线头全空」的整跑 unmeasured 路径。
"""
from __future__ import annotations


def fallback_subquestions(probes=None, threads=None, candidates=None,
                          limit: int = 5) -> list[dict]:
    """从探针/线头/candidates 生成子问题；无可用来源返回 []。"""
    out: list[dict] = []
    seen: set[str] = set()

    def _add(text: str, source: str) -> None:
        q = str(text or "").strip()
        if len(q) < 4 or q in seen:
            return
        seen.add(q)
        out.append({"id": len(out) + 1, "question": q[:200],
                    "weight": 0.5, "decidability": "partial",
                    "status": "open", "depth": 1.0, "source": source})

    for i, p in enumerate(list(probes or [])[:10], 1):
        if isinstance(p, dict):
            _add(p.get("question") or p.get("desc") or "", "P%d" % i)
        if len(out) >= limit:
            return out
    for i, t in enumerate(list(threads or [])[:10], 1):
        if isinstance(t, dict):
            _add(t.get("desc") or t.get("question") or "", "T%d" % i)
        if len(out) >= limit:
            return out
    # ★ [V2.2.97] 最后兜底：层 candidates（探针/线头都为空时的整跑 unmeasured 路径）。
    for i, cand in enumerate(list(candidates or [])[:10], 1):
        if isinstance(cand, dict):
            desc = cand.get("desc") or cand.get("question") or ""
            if desc:
                _add("候选判定：" + str(desc), "C%d" % i)
        if len(out) >= limit:
            return out
    return out


def answerable_fallback(subs, probes=None, threads=None, candidates=None,
                        limit: int = 2) -> list[dict]:
    """V2.2.96：已有子问题但**没有一条可答**时，补探针/线头 partial。

    - 只要已有任一 decidable/partial ⇒ 返回 []（不打扰正常拆解）；
    - 返回的每条 source 前缀 FB:，并避开与已有题面重复；
    - 原 subs 的判定不被修改（想改由调用方自行合并）。
    """
    cur = [s for s in (subs or []) if isinstance(s, dict)]
    if any(str(s.get("decidability")) in ("decidable", "partial") for s in cur):
        return []
    existing = {str(s.get("question") or "").strip() for s in cur}
    fb = []
    for i, s in enumerate(
            fallback_subquestions(probes, threads, candidates, limit), 1):
        if s["question"] in existing:
            continue
        s = dict(s)
        s["id"] = len(cur) + len(fb) + 1
        s["source"] = "FB:" + s.get("source", "?")
        fb.append(s)
        if len(fb) >= limit:
            break
    return fb
