# -*- coding: utf-8 -*-
"""API 能力自反馈策略：从 run 读数决定下一跑的 Fetch/多轮/工具开关。"""
from __future__ import annotations


def decide(signals: dict) -> dict:
    s = signals or {}
    soul = s.get("process_ledger", {}).get("soul", {}) if isinstance(
        s.get("process_ledger"), dict) else {}
    official = int(soul.get("external_official") or 0)
    refs = int(soul.get("external_reference") or 0)
    fetch_calls = int(s.get("fetch_calls") or 0)
    kn = s.get("knowledge") or {}
    kn_n = int(kn.get("n") or 0)
    facets = s.get("facets") or {}
    audit = s.get("research_audit") or {}
    out = {}
    # 官方/证据不足，或只拿到参考：下一跑加强 Fetch。
    if refs > 0 or official < 2 or not facets or kn_n == 0:
        out["web_search.fetch"] = True
        out["web_search.fetch_per_run"] = min(8, max(4, fetch_calls + 2))
    # 审计有未证/空：下一跑保留多轮复盘。
    if str(audit.get("status") or "") in ("mixed", "unverified", "empty"):
        out["api.multi_turn.enabled"] = True
    # 过程账本未全达标：工具适配器保持关闭（避免自由工具破坏审计），
    # 只在多轮/结构补齐后再开。
    pl = s.get("process_ledger") or {}
    if pl and not pl.get("standard_all"):
        out["api.tools.enabled"] = False
    return out


__all__ = ["decide"]
