# -*- coding: utf-8 -*-
"""输入自检的「否定断言需证据」规则与检索后对账。

背景（2026-10-20 154010 真跑）：问题里的 ``DeepSeek-V4.1-Flash-1017``
在检索前被输入自检判成「该型号不存在，属虚构记号」，而同一次跑的事实
预检已经用官方源 18 条确认该型号存在、发布日期 2026-10-17。根因不是
模型判错，而是**把「本地先验没认出」升级成了「存在性否定」**。

本模块把这条边界固化成两层确定性规则：

1. ``neutralize_negative_claims``：输入自检发生在任何检索之前，只有
   问题字符串、没有证据。凡是「不存在 / 虚构 / 捏造 / 伪造 / 查无此物」
   这类存在性否定，一律降级为「本地先验未识别，待证据核验」，并打上
   ``negative_claim_rewritten`` / ``evidence_required`` 留痕。
2. ``reconcile``：检索完成后用官方证据与 fact_contract 对账。
   - 官方证据命中该记号 ⇒ 标记 resolved，从告警区移除；
   - 官方证据明确否认 ⇒ 改写为「官方源对该型号的命名/存在性有冲突」；
   - 有官方检索但未命中 ⇒ 只写「检索到的官方源中未见该记号，存在性待核」，
     **仍然不是「不存在」**。

这样「预检没认出」最多是一条待核提示，不会在报告里和「官方事实答案」
同时出现、互相打架。
"""
from __future__ import annotations

import re
from typing import Any

# 存在性否定词：出现这些词就说明检查者在没有证据地下结论。
NEGATIVE_CLAIM_RE = re.compile(
    r"不存在|并不存在|不存在该|虚构|捏造|伪造|子虚乌有|"
    r"查无此(?:物|型号|人)|非真实|假的|没有这个(?:型号|东西)|"
    r"未发布|尚未发布|没有发布|未推出|尚未推出|未上线"
)

# 中性措辞：只表达「本地先验没认出」，不表达「不存在」。
NEUTRAL_WHY = "本地先验未识别，待证据核验"
NEUTRAL_NOTE = "已检查：先验未识别的记号一律待证据核验"
# 检索后仍未命中：把「没找到」和「不存在」分开。
RETRIEVED_MISS_WHY = "检索到的官方源中未见该记号，存在性待核"
# 官方证据命中：不应再留在告警区。
RESOLVED_WHY = "已由官方证据确认存在"
# 官方证据内部互相矛盾时的措辞。
CONFLICT_WHY = "官方源对该型号的命名/存在性有冲突"

# 官方证据里可能出现的否定表述（用于识别「官方源自己冲突」）。
_OFFICIAL_NEG_RE = re.compile(
    r"不存在|并不存在|not\s+(?:released|exist)|does\s+not\s+exist|"
    r"no\s+such\s+model|wrong\s+name|misnomer|虚构|未发布|尚未发布",
    re.I,
)


def _norm(s: Any) -> str:
    return re.sub(r"\s+", "", str(s or "")).lower()


def _item_text(item: dict) -> str:
    keys = ("title", "claim", "content", "snippet", "url", "source")
    return " ".join(str(item.get(k) or "") for k in keys)


def is_official_item(item: dict) -> bool:
    """一条证据是否官方/权威源。

    优先看显式 ``official`` / ``tier``；打包产物里很多官方页只有 URL，
    所以再用 ``dgtf_v2.evidence.is_official_source`` 的域名白名单兜底。
    """
    if not isinstance(item, dict):
        return False
    if item.get("official") is True:
        return True
    if str(item.get("tier") or "").strip().lower() == "official":
        return True
    url = str(item.get("url") or item.get("source") or "")
    if not url:
        return False
    try:
        from dgtf_v2.evidence import is_official_source
        return bool(is_official_source(url))
    except Exception:  # pragma: no cover - 只作降级兜底
        return ("deepseek.com" in url) or ("deepseek.ai" in url)


def official_evidence(packed: Any) -> list:
    """从打包产物里收集官方证据（web_results / web_arbitration）。"""
    if not isinstance(packed, dict):
        return []
    out = []
    seen = set()
    for pool in (packed.get("pools") or {}).values():
        if not isinstance(pool, dict):
            continue
        for key in ("web_results", "web_arbitration"):
            for item in (pool.get(key) or []):
                if not is_official_item(item):
                    continue
                text = _item_text(item)
                fp = (str(item.get("id") or ""), _norm(text)[:160])
                if fp in seen:
                    continue
                seen.add(fp)
                out.append(item)
    return out


def _term_in_text(term: str, text: str) -> bool:
    """记号是否出现在证据文本里（大小写不敏感，允许空白差异）。"""
    t = str(term or "").strip()
    if not t:
        return False
    if _norm(t) and _norm(t) in _norm(text):
        return True
    # 短记号（如 PN）按词边界匹配，避免命中 token 中间。
    pat = r"(?<![\w.\-])" + re.escape(t) + r"(?![\w.\-])"
    return re.search(pat, str(text or ""), re.I) is not None


def _has_conflict(term: str, text: str) -> bool:
    """官方证据在记号附近是否自己说了「不存在/没发布」。"""
    t = str(term or "")
    if not t or not text:
        return False
    low = str(text)
    for m in re.finditer(re.escape(t), low, re.I):
        left = max(0, m.start() - 90)
        right = min(len(low), m.end() + 90)
        if _OFFICIAL_NEG_RE.search(low[left:right]):
            return True
    return False


def _evidence_ref(term: str, item: dict) -> dict:
    return {"term": str(term or ""),
            "url": str(item.get("url") or item.get("source") or ""),
            "title": str(item.get("title") or "")[:120]}


def neutralize_negative_claims(sanity: Any) -> dict:
    """[否定断言需证据] 把输入自检里的存在性否定降级为「待核」。

    只改措辞、不改问题；重复调用幂等。
    """
    if not isinstance(sanity, dict):
        return {}
    out = dict(sanity)
    issues = []
    for raw in (sanity.get("issues") or []):
        if not isinstance(raw, dict):
            continue
        it = dict(raw)
        why = str(it.get("why") or "")
        if NEGATIVE_CLAIM_RE.search(why):
            it["why"] = NEUTRAL_WHY
            it["negative_claim_rewritten"] = True
            it["evidence_required"] = True
            it["status"] = "unverified"
        else:
            it.setdefault("evidence_required", True)
            it.setdefault("status", "unverified")
        issues.append(it)
    out["issues"] = issues
    guard = dict(out.get("negative_guard") or {})
    guard["rule"] = "否定断言需证据"
    guard["rewritten"] = sum(
        1 for it in issues if it.get("negative_claim_rewritten"))
    # note 也会被报告直接渲染（issues 为空时尤其显眼），不能漏。
    note = str(out.get("note") or "")
    if NEGATIVE_CLAIM_RE.search(note):
        out["note"] = NEUTRAL_NOTE
        guard["note_rewritten"] = True
    out["negative_guard"] = guard
    return out


def reconcile(sanity: Any, packed: Any = None, ledger: Any = None) -> dict:
    """检索后对账：官方证据命中则清除 issue，未命中只写「未见」。

    ``packed`` 用于读 pools 里的官方证据；``ledger`` 是 fact_contract 的
    事实账本（``known`` / ``answer`` / ``source``）。两者都可缺省，
    缺省时仍会执行「否定断言需证据」降级。
    """
    out = neutralize_negative_claims(sanity)
    issues = list(out.get("issues") or [])
    if not issues:
        return out

    official = official_evidence(packed)
    led = ledger if isinstance(ledger, dict) else {}
    known = bool(led.get("known")) and bool(str(led.get("answer") or "").strip())
    if not known and isinstance(packed, dict):
        fc_led = (packed.get("fact_contract") or {}).get("ledger") or {}
        if isinstance(fc_led, dict):
            known = bool(fc_led.get("known")) and bool(
                str(fc_led.get("answer") or "").strip())

    kept = []
    resolved = list(out.get("resolved_issues") or [])
    conflict_n = 0
    unresolved_n = 0
    for it in issues:
        if not isinstance(it, dict):
            continue
        if it.get("resolved"):
            continue
        term = str(it.get("term") or "")
        hits = [e for e in official if _term_in_text(term, _item_text(e))]
        if hits:
            if any(_has_conflict(term, _item_text(e)) for e in hits):
                it = dict(it)
                it["why"] = CONFLICT_WHY
                it["status"] = "conflict"
                it["evidence_required"] = True
                it["evidence"] = [_evidence_ref(term, e) for e in hits[:3]]
                kept.append(it)
                conflict_n += 1
                continue
            # 官方证据命中：清除 issue，移出告警区，但保留对账留痕。
            it = dict(it)
            it["status"] = "resolved"
            it["resolved"] = True
            it["why"] = RESOLVED_WHY
            it["evidence_required"] = False
            it["evidence"] = [_evidence_ref(term, e) for e in hits[:3]]
            resolved.append(it)
            continue
        if official:
            # 有官方检索但没有命中 —— 不能说「不存在」，只能说「未见」。
            it = dict(it)
            it["why"] = RETRIEVED_MISS_WHY
            it["status"] = "unverified"
            it["evidence_required"] = True
            unresolved_n += 1
        else:
            unresolved_n += 1
        kept.append(it)

    out["issues"] = kept
    out["resolved_issues"] = resolved[-20:]
    out["reconciled"] = {
        "official_n": len(official),
        "fact_known": bool(known),
        "resolved_n": len(resolved),
        "conflict_n": int(conflict_n),
        "unverified_n": int(unresolved_n),
        "checked_after_retrieval": bool(official or known),
    }
    if resolved and not kept:
        out["note"] = "已与官方证据对账：先验未识别的记号已确认存在"
    return out


def negative_claims(sanity: Any) -> list:
    """返回仍含存在性否定的 issue / note 文本（供出口互斥闸与测试用）。"""
    if not isinstance(sanity, dict):
        return []
    out = [str(it.get("why") or "") for it in (sanity.get("issues") or [])
           if isinstance(it, dict)
           and NEGATIVE_CLAIM_RE.search(str(it.get("why") or ""))]
    note = str(sanity.get("note") or "")
    if NEGATIVE_CLAIM_RE.search(note):
        out.append(note)
    return out


__all__ = [
    "NEGATIVE_CLAIM_RE",
    "NEUTRAL_WHY",
    "NEUTRAL_NOTE",
    "RETRIEVED_MISS_WHY",
    "CONFLICT_WHY",
    "is_official_item",
    "official_evidence",
    "neutralize_negative_claims",
    "reconcile",
    "negative_claims",
]
