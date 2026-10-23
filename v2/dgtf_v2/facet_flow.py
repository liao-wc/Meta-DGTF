# -*- coding: utf-8 -*-
"""0 层侧面挖掘：事实题不只看日期，还要挖历史/改动/功能/命名/权重等侧面。"""
from __future__ import annotations
import re

_FACETS = (
    ("release_date", "发布日期/上线日期", "官方发布 更新日志 日期"),
    ("history", "此前的模型版本", "上一版本 前代版本 历史版本"),
    ("changes", "相对前版的改动", "相比上一版本 改动 升级 变化"),
    ("features", "新功能/能力", "新功能 能力 提升 基准 测试"),
    ("naming", "命名/API 调用名", "模型名 API 调用名 版本号 命名规则"),
    ("weights", "权重/开源/部署", "权重 开源 发布 部署 模型卡"),
)


def _token(q: str) -> str:
    m = re.search(r"([A-Za-z][A-Za-z0-9._-]*\d{4})", str(q or ""))
    return m.group(1) if m else ""


def plan_facets(question: str, *, max_queries: int = 4) -> list:
    q = str(question or "").strip()
    tok = _token(q)
    base = q
    out = []
    for key, label, hint in _FACETS:
        if key == "release_date":
            query = "%s 官方 发布 日期" % (tok or base)
        elif tok:
            query = "%s %s" % (tok, hint)
        else:
            query = "%s %s" % (base, hint)
        if key == "release_date" and tok:
            query = "%s site:api-docs.deepseek.com" % tok
        out.append({"facet": key, "label": label, "query": query,
                    "priority": {"release_date": 1, "history": 2,
                                 "changes": 3, "features": 4,
                                 "naming": 5, "weights": 6}[key]})
    out.sort(key=lambda x: x["priority"])
    return out[:int(max_queries)]


def source_confidence(hit: dict) -> dict:
    url = str((hit or {}).get("url") or "").lower()
    official = any(d in url for d in ("api-docs.deepseek.com",
                                      "deepseek.com", "deepseek.ai"))
    high = any(d in url for d in (".gov", ".edu", "reuters.com",
                                  "bloomberg.com", "xinhuanet.com"))
    if official:
        conf, tier = 0.9, "official"
    elif high:
        conf, tier = 0.7, "high_authority"
    else:
        conf, tier = 0.4, "reference"
    return {"confidence": conf, "tier": tier, "official": official,
            "used_as": "evidence" if official else "reference"}


def annotate_hits(hits: list, facet: str) -> list:
    out = []
    for h in (hits or []):
        if not isinstance(h, dict):
            continue
        d = dict(h)
        d["facet"] = facet
        d.update(source_confidence(d))
        out.append(d)
    return out


__all__ = ["plan_facets", "source_confidence", "annotate_hits"]
