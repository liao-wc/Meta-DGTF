# -*- coding: utf-8 -*-
"""研究层拆解失败时的确定性回退（V2.2.90）。

背景：_decompose_from_pool 依赖 LLM 输出严格 JSON；本地 0.5B 链路经常
解析失败 -> sub_questions 为空 -> settlement.total=0（层1 永远「未测出」）。
回退策略：用修行层已有的探针/悬空线头确定性生成子问题（不调 LLM、
不补写新知识），保守标 partial，交由后续三态判决/清算覆盖。
"""
from __future__ import annotations


def fallback_subquestions(probes=None, threads=None, limit: int = 5) -> list[dict]:
    """从探针（首选）与线头生成子问题；无可用来源返回 []。"""
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
    return out
