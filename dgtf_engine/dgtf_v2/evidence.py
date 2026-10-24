# -*- coding: utf-8 -*-
"""事实题证据层（V2 参考实现，**纯确定性**）。

本模块只做机械动作，不产出「新知识」：

- 官方源白名单（来源分级）
- 证据指纹（单条文本指纹 / 证据集指纹）
- 去重（URL 归一化 + 文本指纹）
- 预算（条数 / 单域名 / 总字符）
- 证据缺口检测（无证据 / 无官方源 / 单一来源 / 冲突 / 未覆盖关键项）
- 数值冲突检测（同上下文同单位、不同来源给出不同数值）
- 引用绑定（显式 E-id 优先，退化为字符包含度匹配）

三条边界（与项目红线一致）：

1. **不调 LLM、不联网**：检索结果必须由调用方注入；
   collect_evidence(queries, search) 里的 search 是 Callable[[str], list]，
   测试用 fake search（可抛错、可返回空、可返回编造条目）。
2. **不补写证据**：只搬已有字段（title/snippet/url），不生成新句子。
3. **确定性**：同一输入 → 同一输出（无随机、无时间、无网络；集合输出一律排序）。

典型用法（离线）：

>>> def fake_search(q):
...     return [{"title": "国家统计局", "url": "https://www.stats.gov.cn/a",
...              "snippet": "2023年中国GDP增长5.2%"}]
>>> rep = collect_evidence(["2023年中国GDP增长多少"], fake_search,
...                        question="2023年中国GDP增长多少")
>>> rep.ok, rep.official_count
(True, 1)
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable
from urllib.parse import parse_qsl, urlsplit, urlunsplit

# ── 官方源白名单 ──────────────────────────────────────────────────────────────
# 规则：域名 == 条目，或域名以 ".条目" 结尾（子域命中）。
#   · "gov.cn" 命中 www.stats.gov.cn；"gov" 命中 nasa.gov；
#   · "example.gov.cn.evil.com" **不命中**（反向后缀不算）。
# 调用方可用 is_official_source(url, whitelist=...) 替换成自己的表；
# 默认表只覆盖「公开统计/监管/国际组织/教育科研」这几类，不追求全。
OFFICIAL_DOMAINS: tuple[str, ...] = (
    "gov.cn", "stats.gov.cn", "nhc.gov.cn", "moe.gov.cn", "moj.gov.cn",
    "court.gov.cn", "edu.cn", "ac.cn",
    "gov", "gov.uk", "gov.au", "gov.jp", "gov.hk",
    "europa.eu", "un.org", "who.int", "worldbank.org", "imf.org",
    "oecd.org", "wto.org", "nih.gov", "cdc.gov", "nasa.gov",
    "sec.gov", "bls.gov", "census.gov",
    "deepseek.com", "deepseek.ai",
    # 技术标准/官方文档源（用于 HTTP/RFC/W3C/Python 类事实题）
    "rfc-editor.org", "ietf.org", "w3.org", "iana.org",
    "developer.mozilla.org", "python.org", "docs.python.org",
    "nodejs.org", "openai.com", "anthropic.com",
)

#: URL 里要丢掉的跟踪参数前缀（归一化 / 去重用）。
_TRACKING_PREFIXES: tuple[str, ...] = (
    "utm_", "gclid", "fbclid", "yclid", "spm", "from", "ref", "source",
    "share", "share_token", "scene",
)

#: 每条证据默认最多保留的 snippet 字符数（防单条吃满预算）。
DEFAULT_SNIPPET_CHARS = 300


# ============================================================ URL / 指纹
def domain_of(url: str) -> str:
    """取 URL 的宿主域名（小写，去首尾点）；取不到返回空串。

    允许不带 scheme 的写法（www.stats.gov.cn/a）。
    """
    s = str(url or "").strip()
    if not s:
        return ""
    if "://" not in s:
        s = "//" + s
    try:
        host = urlsplit(s).hostname or ""
    except ValueError:
        return ""
    return host.lower().strip(".")


def normalize_url(url: str) -> str:
    """URL 归一化（指纹 / 去重口径）：小写 scheme+host、去默认端口、
    去 fragment、去跟踪参数、query 排序、去尾部斜杠。"""
    s = str(url or "").strip()
    if not s:
        return ""
    if "://" not in s:
        s = "//" + s
    try:
        parts = urlsplit(s)
    except ValueError:
        return s.lower()
    scheme = (parts.scheme or "https").lower()
    host = (parts.hostname or "").lower().strip(".")
    port = parts.port
    if port and not ((scheme == "http" and port == 80)
                     or (scheme == "https" and port == 443)):
        host = "%s:%d" % (host, port)
    path = parts.path or ""
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
         if not k.lower().startswith(_TRACKING_PREFIXES)]
    query = "&".join("%s=%s" % (k, v) for k, v in sorted(q))
    return urlunsplit((scheme, host, path, query, ""))


def is_official_source(url: str, whitelist: Iterable[str] | None = None) -> bool:
    """URL 是否属于官方/权威源白名单（子域命中，反向后缀不算）。"""
    dom = domain_of(url)
    if not dom:
        return False
    table = OFFICIAL_DOMAINS if whitelist is None else whitelist
    for raw in table:
        w = str(raw or "").strip().lower().strip(".")
        if not w:
            continue
        if dom == w or dom.endswith("." + w):
            return True
    return False


def fingerprint_text(text: str, size: int = 16) -> str:
    """单条文本证据指纹：NFKC、小写、去标签、压空白、去标点后 sha256 前缀。

    目的只是「判同」：同一条证据换个 query 回来、或多一个空格，指纹应相同。
    """
    s = unicodedata.normalize("NFKC", str(text or "")).lower()
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[\s\u3000]+", " ", s).strip()
    s = re.sub(r"[^\w\u4e00-\u9fff%]+", "", s)
    n = int(size) if str(size).isdigit() else 16
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:max(4, n)]


def set_fingerprint(fingerprints: Iterable[str], size: int = 16) -> str:
    """证据集指纹：对**排序去重后**的子指纹取 hash ⇒ 与输入顺序无关。"""
    items = sorted({str(x) for x in (fingerprints or []) if str(x)})
    n = int(size) if str(size).isdigit() else 16
    return hashlib.sha256(("\n".join(items)).encode("utf-8")).hexdigest()[:max(4, n)]


# ============================================================ 数据结构
@dataclass
class EvidenceBudget:
    """证据预算（去重之后、进卡片之前的一道硬上限）。"""

    max_items: int = 8
    max_per_domain: int = 3
    max_total_chars: int = 4000
    max_snippet_chars: int = DEFAULT_SNIPPET_CHARS

    def to_dict(self) -> dict:
        return {"max_items": int(self.max_items),
                "max_per_domain": int(self.max_per_domain),
                "max_total_chars": int(self.max_total_chars),
                "max_snippet_chars": int(self.max_snippet_chars)}


@dataclass
class Evidence:
    """一条归一化后的证据。id 在去重/预算前后保持不变（便于引用绑定）。"""

    evidence_id: str = ""
    query: str = ""
    title: str = ""
    url: str = ""
    snippet: str = ""
    domain: str = ""
    official: bool = False
    fingerprint: str = ""
    rank: int = 0

    @property
    def text(self) -> str:
        return (self.title + " " + self.snippet).strip()

    def to_dict(self) -> dict:
        return {"evidence_id": self.evidence_id, "query": self.query,
                "title": self.title, "url": self.url,
                "snippet": self.snippet, "domain": self.domain,
                "official": bool(self.official),
                "fingerprint": self.fingerprint, "rank": int(self.rank)}


@dataclass
class CitationBinding:
    """一条结论的引用绑定结果。"""

    claim: str = ""
    evidence_ids: list = field(default_factory=list)
    mode: str = "none"          # explicit / overlap / none

    def to_dict(self) -> dict:
        return {"claim": self.claim, "evidence_ids": list(self.evidence_ids),
                "mode": self.mode}


@dataclass
class CitationReport:
    claims: list = field(default_factory=list)
    bindings: list = field(default_factory=list)
    invalid_ids: list = field(default_factory=list)
    unbound: list = field(default_factory=list)
    coverage: float = 0.0

    @property
    def ok(self) -> bool:
        return bool(self.claims) and not self.invalid_ids and not self.unbound

    def to_dict(self) -> dict:
        return {"claims": list(self.claims),
                "bindings": [b.to_dict() if hasattr(b, "to_dict") else b
                             for b in self.bindings],
                "invalid_ids": list(self.invalid_ids),
                "unbound": list(self.unbound),
                "coverage": round(float(self.coverage), 4),
                "ok": bool(self.ok)}


@dataclass
class EvidenceReport:
    question: str = ""
    queries: list = field(default_factory=list)
    searches: int = 0
    items: list = field(default_factory=list)
    dropped: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    budget: dict = field(default_factory=dict)
    set_fingerprint: str = ""
    official_count: int = 0
    domains: list = field(default_factory=list)

    def __post_init__(self) -> None:
        """就地派生只读读数（引擎侧会**直接构造** EvidenceReport 再读它们）。"""
        items = list(self.items or [])
        if items:
            if not self.official_count:
                self.official_count = sum(
                    1 for e in items if bool(getattr(e, "official", False)))
            if not self.domains:
                self.domains = sorted({str(getattr(e, "domain", "") or "")
                                       for e in items} - {""})
            if not self.set_fingerprint:
                self.set_fingerprint = set_fingerprint(
                    getattr(e, "fingerprint", "") for e in items)

    @property
    def ok(self) -> bool:
        """有证据、且没有「无证据 / 未消解冲突」这两类致命缺口。"""
        return bool(self.items) and ("no_evidence" not in self.gaps) \
            and ("conflict_unresolved" not in self.gaps)

    def to_dict(self) -> dict:
        return {"question": self.question, "queries": list(self.queries),
                "searches": int(self.searches),
                "items": [e.to_dict() if hasattr(e, "to_dict") else e
                          for e in self.items],
                "dropped": [dict(d) if isinstance(d, dict) else d
                            for d in self.dropped],
                "errors": list(self.errors),
                "conflicts": [dict(c) if isinstance(c, dict) else c
                              for c in self.conflicts],
                "gaps": list(self.gaps),
                "budget": dict(self.budget),
                "set_fingerprint": self.set_fingerprint,
                "official_count": int(self.official_count),
                "domains": list(self.domains),
                "ok": bool(self.ok)}


# ============================================================ 归一化 / 去重 / 预算
def from_search_hits(hits: Iterable, query: str = "", start_id: int = 1,
                     budget: EvidenceBudget | None = None) -> list:
    """把**注入的检索结果**归一化成 Evidence 列表（dict / str 混排都吃）。

    兼容字段：title/name、url/link/href、
    snippet/text/content/description/summary。空条目直接跳过（不占 id）。
    """
    b = budget or EvidenceBudget()
    out: list[Evidence] = []
    n = max(1, int(start_id))
    for i, hit in enumerate(list(hits or [])):
        if isinstance(hit, str):
            title, url, snippet = "", "", hit
        elif isinstance(hit, dict):
            title = str(hit.get("title") or hit.get("name") or "").strip()
            url = str(hit.get("url") or hit.get("link")
                      or hit.get("href") or "").strip()
            snippet = str(hit.get("snippet") or hit.get("text")
                          or hit.get("content") or hit.get("description")
                          or hit.get("summary") or "").strip()
        else:
            continue
        if not (title or snippet):
            continue
        snippet = snippet[:max(1, int(b.max_snippet_chars))]
        # 文本指纹以**正文**为准：标题是来源元数据，同一段正文换个标题
        # 仍是同一条证据（判重不靠标题）。
        fp_basis = snippet if snippet else title
        out.append(Evidence(
            evidence_id="E%d" % n, query=str(query or ""), title=title,
            url=url, snippet=snippet, domain=domain_of(url),
            official=is_official_source(url),
            fingerprint=fingerprint_text(fp_basis), rank=i + 1))
        n += 1
    return out


def dedup_evidence(items: Iterable) -> tuple[list, list]:
    """证据去重：先按归一化 URL、再按文本指纹；保留**首次出现**，
    后到的记 dropped = {evidence_id, reason, against}。"""
    kept: list[Evidence] = []
    dropped: list[dict] = []
    seen_url: dict[str, str] = {}
    seen_fp: dict[str, str] = {}
    for it in list(items or []):
        u = normalize_url(it.url)
        if u and u in seen_url:
            dropped.append({"evidence_id": it.evidence_id, "reason": "dup_url",
                            "against": seen_url[u]})
            continue
        if it.fingerprint and it.fingerprint in seen_fp:
            dropped.append({"evidence_id": it.evidence_id, "reason": "dup_text",
                            "against": seen_fp[it.fingerprint]})
            continue
        if u:
            seen_url[u] = it.evidence_id
        if it.fingerprint:
            seen_fp[it.fingerprint] = it.evidence_id
        kept.append(it)
    return kept, dropped


def apply_budget(items: Iterable, budget: EvidenceBudget | None = None
                 ) -> tuple[list, list]:
    """证据预算：官方源优先、其次按原始 rank；超出条数 / 单域名 / 总字符的丢弃。

    排序键固定 (非官方, rank, evidence_id) ⇒ 同一输入每次结果相同。
    """
    b = budget or EvidenceBudget()
    order = sorted(list(items or []),
                   key=lambda e: (0 if e.official else 1, int(e.rank),
                                  str(e.evidence_id)))
    kept: list[Evidence] = []
    dropped: list[dict] = []
    per_domain: dict[str, int] = {}
    chars = 0
    for it in order:
        if len(kept) >= max(1, int(b.max_items)):
            dropped.append({"evidence_id": it.evidence_id,
                            "reason": "budget_items"})
            continue
        dom = it.domain or "(no_domain)"
        if per_domain.get(dom, 0) >= max(1, int(b.max_per_domain)):
            dropped.append({"evidence_id": it.evidence_id,
                            "reason": "budget_domain"})
            continue
        cost = len(it.title) + len(it.snippet)
        if kept and chars + cost > max(1, int(b.max_total_chars)):
            dropped.append({"evidence_id": it.evidence_id,
                            "reason": "budget_chars"})
            continue
        kept.append(it)
        per_domain[dom] = per_domain.get(dom, 0) + 1
        chars += cost
    return kept, dropped


# ============================================================ 数值冲突
_CLAUSE_RE = re.compile(r"[。；;！!？?，,、\n]+")
_NUM_RE = re.compile(
    r"(?<![\d.])(-?\d+(?:\.\d+)?)\s*"
    r"(%|％|亿元|万元|万人|万|亿|岁|年|个|倍|天|小时|公里|千米|米|元|美元|"
    r"人|条|项|分|秒|次|度)?")
_STRIP_CTX = " \t\u3000，,：:是为达到了约共计有"
_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})\s*年")


def _norm_unit(unit: str) -> str:
    u = str(unit or "").strip()
    return "%" if u in ("%", "％") else u


def extract_numeric_claims(text: str) -> list:
    """从一段文本里抽「数值主张」：{context, unit, value, anchor, raw}。

    - anchor：同句的年份时间锚（不同年份的同一句式**不判冲突**）；
    - context：去掉数字后的上下文（谁在说哪个量）；
    - 年份（1900–2100 且单位「年」）只当时间锚，不算被主张的数值。
    """
    out: list[dict] = []
    last_anchor = ""
    for clause in _CLAUSE_RE.split(str(text or "")):
        clause = clause.strip()
        if not clause:
            continue
        anchors = _YEAR_RE.findall(clause)
        # 同句内后续分句沿用前面的年份锚（"2023年GDP…，增长5.2%"）。
        if anchors:
            last_anchor = anchors[0]
        anchor = anchors[0] if anchors else last_anchor
        for m in _NUM_RE.finditer(clause):
            raw = m.group(1)
            unit = _norm_unit(m.group(2))
            try:
                val = float(raw)
            except (TypeError, ValueError):
                continue
            if unit == "年" and 1900 <= val <= 2100:
                continue
            # 版本/日期尾号常写成 -1017；负四位数字不是可比较的数值主张。
            if raw.startswith("-") and 1000 <= abs(val) <= 9999:
                continue
            ctx = clause[:m.start()] + clause[m.end():]
            ctx = re.sub(r"[\d.\-]", "", ctx)
            ctx = re.sub(r"\s+", "", ctx).strip(_STRIP_CTX)
            # 只有数字+单位、没有额外上下文时，用单位作为最小上下文；
            # 否则「100 条 / 200 条」这类跨来源数值冲突会被静默漏掉。
            if not ctx:
                ctx = unit or "number"
            out.append({"context": ctx, "unit": unit, "value": val,
                        "anchor": anchor, "raw": m.group(0)})
    return out


def _bucket_claims(claims: Iterable) -> dict:
    buckets: dict[tuple, set] = {}
    for c in claims or []:
        key = (str(c.get("anchor") or ""), str(c.get("context") or ""),
               str(c.get("unit") or ""))
        buckets.setdefault(key, set()).add(float(c.get("value")))
    return buckets


def find_numeric_conflicts(left: str, right: str) -> list:
    """两段文本之间「同上下文同单位、数值不同」的冲突（确定性、排序输出）。

    保守口径：只报**双方各有、且互不相同**的数值（一方多提一个数值不算矛盾，
    那可能是在做对比或引用历史）。
    """
    la = _bucket_claims(extract_numeric_claims(left))
    lb = _bucket_claims(extract_numeric_claims(right))
    out: list[dict] = []
    for key in sorted(set(la) & set(lb)):
        lv, rv = la[key], lb[key]
        if not (lv - rv) or not (rv - lv):
            continue
        out.append({"term": (key[0] + " " if key[0] else "") + key[1],
                    "unit": key[2],
                    "left_values": sorted(lv), "right_values": sorted(rv)})
    return out


def detect_conflicts(items: Iterable) -> list:
    """**跨证据**数值冲突：同一 (时间锚, 上下文, 单位) 上，不同来源给出不同数值。

    同一条证据内部出现多个数值不算（它可能在引用两个年份的对照）。
    """
    buckets: dict[tuple, dict[float, set]] = {}
    for it in list(items or []):
        # 只用正文比数值：标题是**来源**不是**主张**（"统计局"/"另一个局"
        # 会让同一句话的上下文各不相同 ⇒ 假阴性）。
        text = str(getattr(it, "snippet", "") or getattr(it, "title", "")
                   or it or "")
        eid = getattr(it, "evidence_id", "")
        for c in extract_numeric_claims(text):
            key = (str(c["anchor"]), str(c["context"]), str(c["unit"]))
            buckets.setdefault(key, {}).setdefault(
                float(c["value"]), set()).add(str(eid))
    out: list[dict] = []
    for key in sorted(buckets):
        # 日期类词条不做裸数值冲突（10月17日 ≠ 10 与 17 两个值）。
        _term = (key[0] + " " if key[0] else "") + key[1]
        if any(k in _term for k in ("月", "日", "date", "日期")):
            continue
        # ★ [V2.2.0 fix] 裸数字（无 anchor/context/unit）不是同一事实主张；
        #   “1..30 个任务/步骤”这类页面计数会被误判成数值冲突。
        #   只对带上下文或单位的数字做跨证据冲突判定。
        if not key[0] and (key[1] in ("", "number", "num") or not key[2]):
            continue
        value_map = buckets[key]
        if len(value_map) < 2:
            continue
        ids = sorted({i for s in value_map.values() for i in s if i})
        if len(ids) < 2:
            continue
        out.append({"term": (key[0] + " " if key[0] else "") + key[1],
                    "unit": key[2], "values": sorted(value_map),
                    "evidence_ids": ids})
    return out


# ============================================================ 缺口 / 答案
_QUESTION_STOP_PHRASES = (
    "请问", "请帮我", "帮我", "想知道", "想了解", "能否", "可以",
    "是多少", "是什么", "有哪些", "有多少", "哪一年", "是什么时候",
    "为什么", "怎么样", "怎么", "如何", "谁", "哪里", "哪些", "哪个",
    "是否", "多少", "吗", "呢", "？", "?",
    # 通用提问/泛化词不当作事实项；否则英文官方证据会被中文泛化词误判未覆盖。
    "的作用", "作用", "函数", "方法", "表示什么", "表示", "含义",
    "是什么作用", "状态码", "的返回值", "返回值", "返回什么",
)


def question_terms(question: str, limit: int = 3) -> list:
    """题面关键项（确定性启发式，只用于「证据覆盖没覆盖」的读数）。

    去掉常见提问句式后，按非词字符切分；汉字串（≥2 字）与字母数字串
    （≥2 字符）作为候选。**不追求语义完备** —— 它只回答「证据里根本没出现
    这些字面项」，不回答「答没答到」。
    """
    s = str(question or "").strip()
    if not s:
        return []
    s = re.sub(r"[？?！!。；;，,、\s]+", " ", s)
    for w in _QUESTION_STOP_PHRASES:
        s = s.replace(w, " ")
    out: list[str] = []
    for tok in re.split(r"[^\w\u4e00-\u9fff]+", s):
        tok = tok.strip()
        if not tok:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", tok):
            if len(tok) >= 2 and tok not in out:
                out.append(tok)
        elif len(tok) >= 2 and tok not in out:
            out.append(tok)
    return out[:max(0, int(limit))]


def detect_gaps(question: str, items: Iterable,
                budget: EvidenceBudget | None = None,
                dropped: Iterable | None = None,
                conflicts: Iterable | None = None,
                min_official: int = 1,
                min_independent: int = 2,
                required_terms: Iterable | None = None) -> list:
    """证据缺口（确定性、去重保序）。返回的是**代码串**，前几类固定：

    - no_evidence：一条都没有
    - no_official_source：有证据但没有官方/白名单源
    - single_source：独立域名数 < min_independent
    - conflict_unresolved：证据间数值冲突
    - budget_truncated:<n>：预算丢掉了 n 条
    - uncovered:<term>：题面关键项没在证据文本里出现
    """
    evs = list(items or [])
    gaps: list[str] = []
    if not evs:
        gaps.append("no_evidence")
        return gaps
    official = [e for e in evs if bool(getattr(e, "official", False))]
    if min_official > 0 and not official:
        gaps.append("no_official_source")
    elif len(official) < int(min_official):
        gaps.append("official_source_short:%d/%d" % (len(official),
                                                     int(min_official)))
    domains = sorted({str(getattr(e, "domain", "") or "").strip()
                      for e in evs} - {""})
    if len(domains) < int(min_independent):
        gaps.append("single_source")
    if list(conflicts or []):
        gaps.append("conflict_unresolved")
    budget_dropped = [d for d in (dropped or [])
                      if isinstance(d, dict)
                      and str(d.get("reason") or "").startswith("budget_")]
    if budget_dropped:
        gaps.append("budget_truncated:%d" % len(budget_dropped))
    terms = (list(required_terms) if required_terms is not None
             else question_terms(question))
    corpus = " ".join(
        (str(getattr(e, "title", "")) + " " + str(getattr(e, "snippet", "")))
        for e in evs)
    corpus = unicodedata.normalize("NFKC", corpus)
    uncovered = [str(t) for t in terms
                 if str(t) and str(t) not in corpus]
    for t in uncovered[:3]:
        gaps.append("uncovered:" + t)
    return gaps


_DATE_RE = re.compile(
    r"20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}(?:日)?")


def _short_answer(text: str, question: str = "") -> str:
    """把长网页/标题正文压成可用短答；有日期优先给日期句。只摘原文。"""
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if not s:
        return ""
    _q = str(question or "")
    _toks = re.findall(r"\d{4}", _q)
    _dates = _DATE_RE.findall(s)
    if _toks:
        # 找同时含问题 token 和日期的句子/片段
        for part in re.split(r"[。；;\n]", s):
            if any(t in part for t in _toks):
                dd = _DATE_RE.findall(part)
                if dd:
                    return dd[0]
        if not any(t in s for t in _toks):
            return ""
        # 同一段落里同时有 token 和日期：直接给日期，避免把整篇正文当答案。
        if _dates:
            return _dates[0]
    if _dates:
        # 优先取日期所在短句
        for part in re.split(r"[。；;\n]", s):
            if _DATE_RE.search(part):
                return part.strip()[:240]
        return _dates[0]
    return s[:240]


def _answer_relevance(text: str, question: str) -> float:
    """题面相关度：ASCII 技术词加权，命中开头/函数签名再加分。

    典型修复：问「len() 的作用」时，中文 list() 页面虽然也出现 Python/函数，
    但开头不是 len 的定义；应让开头给出 len(object, /) 的官方段胜出。
    """
    terms = question_terms(question, limit=6)
    if not terms:
        return 0.0
    low = str(text or "").lower()
    head = low[:180]
    total = 0.0
    hit = 0.0
    for t in terms:
        w = 2.0 if re.fullmatch(r"[A-Za-z0-9_.]+", t or "") else 1.0
        total += w
        if t.lower() in low:
            hit += w
            if t.lower() in head:
                hit += w * 0.6
    qfunc = re.findall(r"([A-Za-z_]\w{1,30})\s*\(", str(question or ""))
    for fn in qfunc:
        if fn.lower() in low:
            hit += 0.5
            if re.search(r"(?:^|\W)" + re.escape(fn) + r"\s*\(", head,
                         re.I):
                hit += 0.4
    if not total:
        return 0.0
    return hit / total


def answer_from_evidence(items: Iterable, question: str = "") -> str:
    """从已有证据里挑一条最可用的短答（题面相关优先、官方优先）。

    只摘原文，不改写；长网页会压到日期/相关短句，避免把整页当答案。
    有题面时，没有题面词命中的非官方证据不配当答案；URL 类问题还要求
    答案里真的出现 URL，防止把截断代码块当地址。
    """
    evs = list(items or [])
    if not evs:
        return ""
    q = str(question or "").strip()
    if not q:
        order = sorted(evs, key=lambda e: (0 if bool(getattr(e, "official", False))
                                           else 1, int(getattr(e, "rank", 0)),
                                           str(getattr(e, "evidence_id", ""))))
        return _short_answer(str(getattr(order[0], "snippet", "") or ""), q)
    wants_url = bool(re.search(r"(?:base\s*url|base_url|接口地址|访问地址|url)",
                               q, re.I))
    scored = []
    for e in evs:
        text = str(getattr(e, "snippet", "") or "")
        score = _answer_relevance(text, q)
        if bool(getattr(e, "official", False)):
            score += 0.15
        scored.append((score, -int(getattr(e, "rank", 0)), e))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    for score, _neg_rank, e in scored:
        text = str(getattr(e, "snippet", "") or "")
        if wants_url and not re.search(r"https?://[^\s'\"<>]+", text):
            continue
        if score <= 0 and not bool(getattr(e, "official", False)):
            continue
        ans = _short_answer(text, q)
        if wants_url and not re.search(r"https?://[^\s'\"<>]+", ans):
            continue
        return ans
    return ""


# ============================================================ 引用绑定
_CITE_RE = re.compile(r"(?<![A-Za-z])(E\d+)(?!\d)")


def _char_coverage(claim: str, evidence_text: str) -> float:
    """结论字符被证据覆盖的比例（只看 claim 的字符集，够用即可）。"""
    def _chars(s: str) -> set:
        s = unicodedata.normalize("NFKC", str(s or "")).lower()
        s = re.sub(r"[^\w\u4e00-\u9fff]+", "", s)
        return set(s)
    a, b = _chars(claim), _chars(evidence_text)
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a))


def bind_citations(claims: Iterable, items: Iterable,
                   threshold: float = 0.25) -> CitationReport:
    """把结论绑定到证据 id。

    优先认**显式引用**（E1 / [E2]）；没有显式引用时按字符覆盖度
    （claim 的字符被证据覆盖 ≥ threshold）挑一条，同分取 rank 小者。
    显式 id 不存在 ⇒ 记 invalid_ids；绑不上的结论记 unbound。
    """
    claim_list = ([str(c) for c in claims] if isinstance(claims, (list, tuple))
                  else [str(claims)] if claims else [])
    evs = list(items or [])
    index = {str(getattr(e, "evidence_id", "")): e for e in evs}
    report = CitationReport(claims=list(claim_list))
    for claim in claim_list:
        explicit = [m.group(1) for m in _CITE_RE.finditer(claim)]
        valid = [i for i in explicit if i in index]
        invalid = [i for i in explicit if i not in index]
        for i in invalid:
            if i not in report.invalid_ids:
                report.invalid_ids.append(i)
        if valid:
            uniq = []
            for i in valid:
                if i not in uniq:
                    uniq.append(i)
            report.bindings.append(CitationBinding(claim=claim,
                                                   evidence_ids=uniq,
                                                   mode="explicit"))
            continue
        best, best_score = None, 0.0
        for ev in sorted(evs, key=lambda e: int(getattr(e, "rank", 0))):
            score = _char_coverage(claim, str(getattr(ev, "text", "")))
            if score > best_score:
                best, best_score = ev, score
        if best is not None and best_score >= float(threshold):
            report.bindings.append(CitationBinding(
                claim=claim, evidence_ids=[str(best.evidence_id)],
                mode="overlap"))
        else:
            report.bindings.append(CitationBinding(claim=claim,
                                                   evidence_ids=[],
                                                   mode="none"))
            report.unbound.append(claim)
    bound = sum(1 for b in report.bindings if b.evidence_ids)
    report.coverage = (bound / float(len(claim_list))) if claim_list else 0.0
    return report


# ============================================================ 采集入口
def collect_evidence(queries: Iterable, search: Callable[[str], Any] | None,
                     question: str = "",
                     budget: EvidenceBudget | None = None) -> EvidenceReport:
    """注入式检索 → 归一化 → 去重 → 预算 → 冲突 → 缺口，返回完整证据报告。

    search(query) 由调用方注入；它是**唯一**外部入口：
      · 返回 None / 空 list ⇒ 视为「查了但没记录」；
      · 抛异常 ⇒ 记进 errors，不中断（失败留痕，不静默）；
      · 返回值不是 list/tuple ⇒ 记错误，不崩。
    本函数不发任何网络请求。
    """
    b = budget or EvidenceBudget()
    qlist = [str(q).strip() for q in (queries or []) if str(q).strip()]
    report = EvidenceReport(question=str(question or ""),
                            queries=list(qlist),
                            budget=b.to_dict())
    if search is None:
        report.errors.append("search_unavailable")
        report.gaps = detect_gaps(question, [], budget=b)
        return report
    collected: list[Evidence] = []
    for q in qlist:
        report.searches += 1
        try:
            hits = search(q)
        except Exception as e:  # noqa: BLE001 —— 失败留痕，不静默
            report.errors.append("search_error:%s:%s"
                                 % (type(e).__name__, e))
            hits = []
        if hits is None:
            hits = []
        if not isinstance(hits, (list, tuple)):
            report.errors.append("search_bad_return:%s"
                                 % type(hits).__name__)
            hits = []
        collected.extend(from_search_hits(hits, query=q,
                                          start_id=len(collected) + 1,
                                          budget=b))
    kept, dropped_dedup = dedup_evidence(collected)
    kept, dropped_budget = apply_budget(kept, b)
    dropped = list(dropped_dedup) + list(dropped_budget)
    conflicts = detect_conflicts(kept)
    gaps = detect_gaps(question, kept, budget=b, dropped=dropped_budget,
                       conflicts=conflicts)
    report.items = kept
    report.dropped = dropped
    report.conflicts = conflicts
    report.gaps = gaps
    report.official_count = sum(1 for e in kept if e.official)
    report.domains = sorted({e.domain for e in kept if e.domain})
    report.set_fingerprint = set_fingerprint(e.fingerprint for e in kept)
    return report


__all__ = [
    "OFFICIAL_DOMAINS", "DEFAULT_SNIPPET_CHARS",
    "domain_of", "normalize_url", "is_official_source",
    "fingerprint_text", "set_fingerprint",
    "EvidenceBudget", "Evidence", "CitationBinding", "CitationReport",
    "EvidenceReport", "from_search_hits", "dedup_evidence", "apply_budget",
    "extract_numeric_claims", "find_numeric_conflicts", "detect_conflicts",
    "question_terms", "detect_gaps", "answer_from_evidence",
    "bind_citations", "collect_evidence",
]
