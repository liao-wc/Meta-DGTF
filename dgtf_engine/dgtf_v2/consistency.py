# -*- coding: utf-8 -*-
"""检索结论 vs 推理结论的一致性判定（V2 参考实现，**纯确定性**）。

四种判定（互斥，按序判定）：

- match     检索与推理给出同一结论：字符高度重合，且检索结论里的
            关键项（数字 / 英文编号 / 带单位数值）在推理里**一个不缺**；
- partial   大体重合，但推理少了检索结论里的关键项，或字符重合中等；
- mismatch  矛盾（同上下文数值不同 / 否定相反 / 与官方证据数值矛盾），
            或两者毫不相干；
- not_comp  不可比（检索 no_record/unknown、检索自身 conflict、推理无结论）。

不调 LLM、不联网：只做字符、数值、否定词的机械比较。
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .evidence import extract_numeric_claims, find_numeric_conflicts

#: 四种判定（封闭集合；出集合即判据红）。
VERDICTS = ("match", "partial", "mismatch", "not_comp")

#: 判定阈值（写死；改动必须先改测试里的正反例）。
MATCH_SIM = 0.80
PARTIAL_SIM = 0.50
PARTIAL_LOW_SIM = 0.30
NEG_SIM = 0.80

_NEG_CHARS = "不未没无非否"


@dataclass
class ConsistencyReport:
    """一次「检索 vs 推理」比较的完整读数。"""

    verdict: str = "not_comp"
    retrieval_answer: str = ""
    reasoning_answer: str = ""
    similarity: float = 0.0
    matched_terms: list = field(default_factory=list)
    missing_terms: list = field(default_factory=list)
    contradicting: list = field(default_factory=list)
    evidence_ids: list = field(default_factory=list)
    reasons: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.verdict == "match"

    def to_dict(self) -> dict:
        return {"verdict": self.verdict,
                "retrieval_answer": self.retrieval_answer,
                "reasoning_answer": self.reasoning_answer,
                "similarity": round(float(self.similarity), 4),
                "matched_terms": list(self.matched_terms),
                "missing_terms": list(self.missing_terms),
                "contradicting": [dict(c) if isinstance(c, dict) else c
                                  for c in self.contradicting],
                "evidence_ids": list(self.evidence_ids),
                "reasons": list(self.reasons),
                "ok": bool(self.ok)}


# ============================================================ 输入归一化
def _text_of(value, keys) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for k in keys:
            v = value.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        claims = value.get("claims")
        if isinstance(claims, (list, tuple)):
            return "；".join(str(c).strip() for c in claims if str(c).strip())
        return ""
    for k in keys:
        v = getattr(value, k, None)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _retrieval_parts(retrieval) -> tuple[str, str, list]:
    """检索侧取 (answer, status, evidence_ids)；支持 str / dict / FactCard 对象。"""
    if isinstance(retrieval, str):
        return retrieval.strip(), "", []
    if isinstance(retrieval, dict):
        status = str(retrieval.get("status") or "").strip()
        answer = _text_of(retrieval, ("answer", "conclusion", "decision",
                                      "retrieval_answer", "text"))
        ids = [str(x) for x in (retrieval.get("evidence_ids") or [])
               if str(x).strip()]
        if not answer:
            answer = _text_of(retrieval.get("fact_card") or {}, ("answer",))
        return answer, status, ids
    status = str(getattr(retrieval, "status", "") or "").strip()
    answer = _text_of(retrieval, ("answer", "conclusion", "decision",
                                  "retrieval_answer", "text"))
    ids = [str(x) for x in (getattr(retrieval, "evidence_ids", None) or [])
           if str(x).strip()]
    return answer, status, ids


def _reasoning_answer(reasoning) -> str:
    return _text_of(reasoning, ("answer", "conclusion", "decision", "claim",
                                "reasoning_answer", "text"))


def _evidence_items(evidence) -> list:
    if evidence is None:
        return []
    if hasattr(evidence, "items") and not isinstance(evidence, (list, tuple)):
        return list(getattr(evidence, "items") or [])
    return list(evidence or [])


def _official_snippets(evidence) -> list:
    out: list[tuple[str, str]] = []
    for it in _evidence_items(evidence):
        if isinstance(it, dict):
            official = bool(it.get("official"))
            snippet = str(it.get("snippet") or it.get("text") or "").strip()
            eid = str(it.get("evidence_id") or "")
        else:
            official = bool(getattr(it, "official", False))
            snippet = str(getattr(it, "snippet", "") or "").strip()
            eid = str(getattr(it, "evidence_id", "") or "")
        if official and snippet:
            out.append((snippet, eid))
    return out


# ============================================================ 文本信号
def _norm_chars(text) -> set:
    s = unicodedata.normalize("NFKC", str(text or "")).lower()
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "", s)
    return set(s)


def char_similarity(left, right) -> float:
    """字符集 Jaccard（中文短句换语序仍高；ASCII 不区分大小写）。"""
    a, b = _norm_chars(left), _norm_chars(right)
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def material_terms(text) -> list:
    """关键项：英文编号 / 数字（带 % 保留）——这些是「事实题」的硬信息。"""
    out: list[str] = []
    for m in re.finditer(r"[A-Za-z]+|\d+(?:\.\d+)?%?", str(text or "")):
        t = m.group(0).lower()
        if t not in out:
            out.append(t)
    return out


def key_bigrams(text) -> list:
    """中文二元组 + 关键项，用于报告「命中 / 缺失」哪些词。"""
    out: list[str] = []
    s = re.sub(r"[^\u4e00-\u9fff]+", " ", str(text or ""))
    for seg in s.split():
        for i in range(len(seg) - 1):
            bg = seg[i:i + 2]
            if bg not in out:
                out.append(bg)
    for t in material_terms(text):
        if t not in out:
            out.append(t)
    return out


def _has_negation(text) -> bool:
    return any(ch in str(text or "") for ch in _NEG_CHARS)


def _strip_negation(text) -> str:
    return "".join(ch for ch in str(text or "") if ch not in _NEG_CHARS)


def negation_opposite(left, right) -> bool:
    """否定极性相反：一方有否定词、另一方没有，且去掉否定词后高度重合。"""
    if _has_negation(left) == _has_negation(right):
        return False
    return char_similarity(_strip_negation(left),
                           _strip_negation(right)) >= NEG_SIM


# ============================================================ 主判定
def _ctx_bigrams(context: str) -> set:
    """上下文的中文二元组集合（用于「同一指标的不同措辞」是否兼容）。"""
    out: set = set()
    for seg in re.split(r"[^\u4e00-\u9fff]+", str(context or "")):
        for i in range(len(seg) - 1):
            out.add(seg[i:i + 2])
    return out


def _ctx_compatible(left: str, right: str) -> bool:
    """两个数值上下文是否在说同一个量。

    口径（确定性、宁少报）：
      1) 一方是另一方的子串 ⇒ 兼容；
      2) 否则看中文二元组：「较短上下文」的二元组要有 ≥70% 落在长上下文里。
    这样 "年GDP增长" 与 "年中国GDP增长" 兼容（共享 "增长"），
    而 "美国GDP增长" 与 "中国GDP增长" 不兼容（各自国家二元组互不包含）。
    """
    a, b = str(left or ""), str(right or "")
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    A, B = _ctx_bigrams(a), _ctx_bigrams(b)
    if not A or not B:
        return False
    short, long = (A, B) if len(A) <= len(B) else (B, A)
    return len(short & long) / float(len(short)) >= 0.7


def _num_conflicts_relaxed(left: str, right: str) -> list:
    """答案间数值矛盾：先用 evidence 的**严格**口径（上下文完全相等），
    再补一层「同时间锚 + 同单位 + 上下文包含」的放宽口径。

    为什么要放宽：检索结论与推理结论是两段独立生成的中文，
    「2023年GDP增长5.2%」与「2023年中国GDP增长6.8%」的上下文不会逐字相等；
    严格口径会漏报这类真矛盾。放宽只在「短上下文被长上下文包含」时生效，
    且要求同一时间锚、同一单位 —— 宁少报（不把不同国家/指标的口号并起来）。
    """
    out = [dict(c) for c in find_numeric_conflicts(left, right)]
    seen = {(str(c.get("term")), str(c.get("unit"))) for c in out}
    la = extract_numeric_claims(left)
    lb = extract_numeric_claims(right)
    for a in la:
        for b in lb:
            if (a.get("anchor"), a.get("unit")) != (b.get("anchor"),
                                                    b.get("unit")):
                continue
            if float(a.get("value")) == float(b.get("value")):
                continue
            ca = str(a.get("context") or "")
            cb = str(b.get("context") or "")
            if not ca or not cb:
                continue
            if not _ctx_compatible(ca, cb):
                continue
            short = ca if len(ca) <= len(cb) else cb
            term = (str(a.get("anchor")) + " " if a.get("anchor") else "") + short
            key = (term, str(a.get("unit")))
            if key in seen:
                continue
            seen.add(key)
            out.append({"term": term, "unit": str(a.get("unit")),
                        "left_values": [a.get("value")],
                        "right_values": [b.get("value")]})
    return out


def compare_retrieval_vs_reasoning(retrieval, reasoning, evidence=None
                                   ) -> ConsistencyReport:
    """比较「检索给出的结论」与「推理给出的结论」。

    retrieval  : str / dict（FactCard.to_dict 形状：status/answer/evidence_ids）
                 / 带 answer/status 属性的对象（如 fact_flow.FactCard）。
    reasoning  : str / dict（answer/conclusion/decision/claims）/ 带同名属性的对象。
    evidence   : 可选证据列表（Evidence 对象或 dict）；给了就额外检查
                 「推理是否与官方证据的数值矛盾」。
    """
    r_answer, r_status, r_ids = _retrieval_parts(retrieval)
    g_answer = _reasoning_answer(reasoning)
    report = ConsistencyReport(retrieval_answer=r_answer,
                               reasoning_answer=g_answer,
                               evidence_ids=list(r_ids))
    if r_status == "conflict":
        return _finish(report, "not_comp",
                       ["检索状态 conflict：检索自身冲突，没有单一结论可比"])
    if r_status in ("no_record", "unknown"):
        return _finish(report, "not_comp",
                       ["检索状态 %s：检索没有结论" % r_status])
    if not r_answer:
        return _finish(report, "not_comp", ["检索无结论文本"])
    if not g_answer:
        return _finish(report, "not_comp", ["推理无结论文本"])

    report.similarity = round(char_similarity(r_answer, g_answer), 4)
    conflicts = _num_conflicts_relaxed(r_answer, g_answer)
    if conflicts:
        report.contradicting = [dict(c) for c in conflicts]
        reasons = ["数值矛盾：" + _fmt_conflict(c) for c in conflicts]
        return _finish(report, "mismatch", reasons)

    if negation_opposite(r_answer, g_answer):
        report.contradicting = [{
            "term": "否定极性", "left_values": [_strip_negation(r_answer)],
            "right_values": [_strip_negation(g_answer)]}]
        return _finish(report, "mismatch",
                       ["否定/肯定相反（去否定词后相似度 %.2f）"
                        % char_similarity(_strip_negation(r_answer),
                                          _strip_negation(g_answer))])

    off_conf = []
    for snippet, eid in _official_snippets(evidence):
        for c in _num_conflicts_relaxed(snippet, g_answer):
            item = dict(c)
            item["against_evidence_id"] = eid
            off_conf.append(item)
            if eid and eid not in report.evidence_ids:
                report.evidence_ids.append(eid)
    if off_conf:
        report.contradicting = off_conf
        return _finish(report, "mismatch",
                       ["推理与官方证据数值矛盾：" + _fmt_conflict(c)
                        for c in off_conf])

    sim = report.similarity
    g_lower = g_answer.lower()
    mats = material_terms(r_answer)
    missing_material = [t for t in mats if t not in g_lower]
    coverage = (1.0 - len(missing_material) / float(len(mats))
                if mats else 1.0)
    matched = [bg for bg in key_bigrams(r_answer) if bg.lower() in g_lower][:4]
    missing = list(missing_material)
    for bg in key_bigrams(r_answer):
        if len(missing) >= 4:
            break
        if bg.lower() not in g_lower and bg not in missing:
            missing.append(bg)
    report.similarity = sim
    report.matched_terms = matched
    report.missing_terms = missing[:4]

    if sim >= MATCH_SIM and not missing_material:
        return _finish(report, "match",
                       ["字符相似度 %.2f、关键项齐全 ⇒ 一致" % sim])
    if sim >= PARTIAL_SIM or (sim >= PARTIAL_LOW_SIM and coverage >= 0.5):
        return _finish(report, "partial",
                       ["部分一致（相似度 %.2f；推理缺少关键项：%s）"
                        % (sim, "、".join(report.missing_terms) or "无")])
    return _finish(report, "mismatch",
                   ["不一致（相似度 %.2f，字符与关键项重合不足）" % sim])


def _fmt_conflict(conflict: dict) -> str:
    term = str(conflict.get("term") or "?")
    unit = str(conflict.get("unit") or "")
    left = conflict.get("left_values") or conflict.get("values") or []
    right = conflict.get("right_values") or []
    return "%s %s：%s ≠ %s" % (term, unit, left, right)


def _finish(report: ConsistencyReport, verdict: str, reasons: list
            ) -> ConsistencyReport:
    if verdict not in VERDICTS:
        raise ValueError("非法一致性判定：%r（允许 %r）"
                         % (verdict, list(VERDICTS)))
    report.verdict = verdict
    report.reasons = list(reasons)
    return report


__all__ = ["VERDICTS", "MATCH_SIM", "PARTIAL_SIM", "PARTIAL_LOW_SIM",
           "NEG_SIM", "ConsistencyReport", "char_similarity",
           "material_terms", "key_bigrams", "negation_opposite",
           "compare_retrieval_vs_reasoning"]
