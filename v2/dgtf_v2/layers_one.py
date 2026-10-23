# -*- coding: utf-8 -*-
"""F3 · 1 层 AnswerSetPackage（契约收口，不改算法）。

1 层的职责是“筛选/研究”，不是给行动：
- 每条子问题一个合法三态标签 decidable/partial/undecidable；
- decidable 必须带 citations/evidence（不能空口）；
- 1 层不得出现 actions/not_do（越权属于 all）；
- coverage 只作读数；三态一致率是标签定义，不是质量门。

本模块只做契约组装/审计，不生成新句子；缺项记 gap，不补空话。
"""
from __future__ import annotations

from dataclasses import dataclass, field

LABELS = ("decidable", "partial", "undecidable")
ANSWERABLE = ("decidable", "partial")


@dataclass
class AnswerSetPackage:
    answers: list = field(default_factory=list)
    coverage: float = 0.0
    tri_distribution: dict = field(default_factory=dict)
    citations_ok: bool = False
    no_actions: bool = True
    gaps: list = field(default_factory=list)
    contract_completeness: float = 0.0
    ok: bool = False

    def to_dict(self) -> dict:
        return {
            "answers": self.answers,
            "coverage": round(float(self.coverage), 4),
            "tri_distribution": self.tri_distribution,
            "citations_ok": self.citations_ok,
            "no_actions": self.no_actions,
            "gaps": self.gaps,
            "contract_completeness": round(float(self.contract_completeness), 4),
            "ok": self.ok,
        }


def _citations(item: dict) -> list:
    c = item.get("citations") or item.get("evidence") or []
    if isinstance(c, str):
        c = [c]
    return [str(x) for x in c if str(x).strip()]


def _build_answers(research_view: dict) -> list:
    rv = research_view or {}
    subs = list(rv.get("sub_questions") or rv.get("subs") or [])
    if not subs and isinstance(rv.get("decidable_product"), dict):
        dp = rv["decidable_product"]
        subs = [{"id": "dp", "question": rv.get("question") or "decidable_product",
                 "decidability": ("decidable" if dp.get("answer") else "partial"),
                 "answer": dp.get("answer") or "",
                 "citations": dp.get("evidence") or dp.get("citations") or []}]
    # 若 decidable 子问题自身没带 citations，但 1 层 decidable_product 有
    # evidence，则把**已有证据**下放到该条（只复用，不生成新句子）。
    dp_ev = []
    if isinstance(rv.get("decidable_product"), dict):
        dp_ev = _citations(rv["decidable_product"])
    out = []
    for i, s in enumerate(subs, 1):
        if not isinstance(s, dict):
            continue
        cits = _citations(s)
        src = ""
        if not cits and dp_ev and str(s.get("decidability") or "").lower() == "decidable":
            cits = list(dp_ev)
            src = "decidable_product"
        out.append({
            "id": s.get("id") or i,
            "question": str(s.get("question") or ""),
            "label": str(s.get("decidability") or "").lower(),
            "answer": str(s.get("answer") or ""),
            "citations": cits,
            "citations_source": src,
        })
    return out


def assemble_answer_set(research_view: dict | None = None,
                        quality: dict | None = None) -> AnswerSetPackage:
    """从 1 层已有产物组装 AnswerSetPackage；不生成新句子。"""
    rv = research_view or {}
    q = quality or {}
    pkg = AnswerSetPackage()
    pkg.answers = _build_answers(rv)

    if not pkg.answers:
        pkg.gaps.append("缺 answers（1 层无子问题）")
        pkg.ok = False
        return pkg

    dist = {k: 0 for k in LABELS}
    for a in pkg.answers:
        dist[a["label"]] = dist.get(a["label"], 0) + 1
        if a["label"] not in LABELS:
            pkg.gaps.append("非法三态标签：%s" % (a["label"] or "空"))
        if a["label"] == "decidable" and not a["citations"]:
            pkg.gaps.append("decidable 缺 citations：%s" % a["id"])
    pkg.tri_distribution = dist

    # 1 层越权：actions/not_do 不允许出现在本层（源头已上移，这里守）
    for k in ("actions", "_actions", "not_do", "_not_do"):
        if rv.get(k):
            pkg.no_actions = False
            pkg.gaps.append("1 层越权：%s 不为空" % k)
    dp = rv.get("decidable_product")
    if isinstance(dp, dict) and (dp.get("actions") or dp.get("not_do")):
        pkg.no_actions = False
        pkg.gaps.append("1 层越权：decidable_product.actions/not_do")

    answerable = sum(1 for a in pkg.answers if a["label"] in ANSWERABLE)
    pkg.coverage = (float(q.get("coverage"))
                    if isinstance(q.get("coverage"), (int, float))
                    else (answerable / float(len(pkg.answers)) if pkg.answers else 0.0))
    pkg.citations_ok = all(a["citations"] for a in pkg.answers
                           if a["label"] == "decidable")
    valid = sum(1 for a in pkg.answers if a["label"] in LABELS)
    pkg.contract_completeness = valid / float(len(pkg.answers)) if pkg.answers else 0.0
    pkg.ok = not pkg.gaps and pkg.contract_completeness == 1.0
    return pkg
