# -*- coding: utf-8 -*-
"""研究层判定审计：可判定必须有证据；不可判定不得与外部证据相反。"""
from __future__ import annotations
import re

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{2,}")


def _text(x):
    return str(x or "").strip()


def _terms(s):
    return [t.lower() for t in _TOKEN.findall(_text(s))]


def audit_view(view: dict, evidence=None, fact_answer: str = "") -> dict:
    ev = [e for e in (evidence or []) if isinstance(e, dict)]
    blob = " ".join(_text(e.get("claim") or e.get("snippet") or
                         e.get("title") or "") for e in ev).lower()
    sqs = (view or {}).get("sub_questions") or []
    rows = []
    n_ok = n_bad = 0
    for sq in sqs:
        st = str(sq.get("decidability") or sq.get("status") or "").lower()
        q = _text(sq.get("question") or sq.get("q"))
        cites = list(sq.get("citations") or sq.get("evidence") or [])
        hit = any(t in blob for t in _terms(q)[:4]) if blob else False
        issue = ""
        new_st = st
        if st in ("decidable", "可判定", "true"):
            if not cites:
                issue, new_st = "decidable_without_evidence", "partial"
            else:
                n_ok += 1
        elif st in ("undecidable", "不可判定", "false"):
            if hit:
                issue, new_st = "undecidable_but_evidence_exists", "partial"
            else:
                n_ok += 1
        elif st == "partial":
            if cites or hit:
                n_ok += 1
            else:
                issue = "partial_without_evidence"
        if issue:
            n_bad += 1
            sq["audit_issue"] = issue
            if new_st != st:
                sq["status_before_audit"] = st
                sq["decidability"] = new_st
                sq["status"] = new_st
        rows.append({"id": sq.get("id"), "before": st,
                     "after": str(sq.get("decidability") or st),
                     "issue": issue, "citations": len(cites),
                     "evidence_term_hit": bool(hit)})
    # 没有结构化子问题时，审计研究产物本身：有外部证据却答“无法”，
    # 或未引用已核实事实，都要记为未证。
    if not sqs:
        dp = (view or {}).get("decidable_product")
        if not isinstance(dp, dict):
            dp = {}
        if isinstance(view, dict):
            view["decidable_product"] = dp
        txt = _text(dp.get("answer") or (view or {}).get("manifest"))
        cannot = any(k in txt for k in ("无法", "不可判定", "未提供",
                                        "未确认", "无法确认", "没有来源"))
        # 「不存在/未出现/无公开落点」是**有证据的否定结论**，不是研究层摆烂；
        # 不能因为它同时含「无法合成」这类结论词就判未证。
        negative_conclusion = any(k in txt for k in (
            "不存在", "未出现", "无公开", "无独立落点", "无主题块重叠",
            "不能互证", "无法合成"))
        has_fact = bool(fact_answer) and _text(fact_answer) in txt
        if cannot and ev:
            if fact_answer:
                # 已核实事实存在：研究层必须吃掉事实与外部证据，不能只标红。
                _eids = [str(e.get("id")) for e in ev if e.get("id")]
                dp["answer"] = (
                    "已核实：%s（官方源）。外部证据 %d 条已入池%s；"
                    "原研究判断降级为参考：%s"
                    % (fact_answer, len(ev),
                       ("（" + "、".join(_eids[:6]) + "）") if _eids else "",
                       txt))
                dp["status_before_audit"] = "unverified"
                dp["verification_repaired"] = True
                dp["external_evidence_ids"] = _eids[:8]
                rows.append({"id": "research_product", "before": "claim",
                             "after": "repaired_with_fact",
                             "issue": "research_ignores_available_evidence",
                             "citations": 0, "evidence_term_hit": True})
                n_ok += 1
            elif negative_conclusion:
                rows.append({"id": "research_product", "before": "claim",
                             "after": "verified_negative",
                             "issue": "", "citations": 0,
                             "evidence_term_hit": True})
                n_ok += 1
            else:
                rows.append({"id": "research_product", "before": "claim",
                             "after": "partial",
                             "issue": "research_ignores_available_evidence",
                             "citations": 0, "evidence_term_hit": True})
                n_bad += 1
        elif has_fact:
            rows.append({"id": "research_product", "before": "claim",
                         "after": "verified_with_fact",
                         "issue": "", "citations": 0,
                         "evidence_term_hit": True})
            n_ok += 1
        elif not txt and fact_answer:
            _eids = [str(e.get("id")) for e in ev if e.get("id")]
            dp["answer"] = ("已核实：%s（官方源）。外部证据 %d 条已入池%s；"
                            "研究层原产物为空，已由事实与证据补齐，"
                            "其余未证项保留为待研究。"
                            % (fact_answer, len(ev),
                               ("（" + "、".join(_eids[:6]) + "）")
                               if _eids else ""))
            dp["verification_repaired"] = True
            dp["external_evidence_ids"] = _eids[:8]
            rows.append({"id": "research_product", "before": "empty",
                         "after": "repaired_with_fact",
                         "issue": "empty_product_repaired",
                         "citations": 0, "evidence_term_hit": True})
            n_ok += 1
        elif not txt:
            rows.append({"id": "research_product", "before": "empty",
                         "after": "empty", "issue": "empty_product",
                         "citations": 0, "evidence_term_hit": False})
            n_bad += 1
        total = 1 if rows else 0

    total = len(sqs) if sqs else total
    status = ("verified" if total and n_bad == 0 else
              "mixed" if n_ok else "unverified" if total else "empty")
    return {"status": status, "n": total, "ok": n_ok, "bad": n_bad,
            "rows": rows, "evidence_n": len(ev)}


def annotate(view: dict, evidence=None, fact_answer: str = "") -> dict:
    r = audit_view(view, evidence, fact_answer=fact_answer)
    if isinstance(view, dict):
        view["decidability_audit"] = r
        dp = view.get("decidable_product")
        if isinstance(dp, dict):
            dp["verification"] = {"status": r["status"],
                                  "ok": r["ok"], "bad": r["bad"]}
    return r


__all__ = ["audit_view", "annotate"]
