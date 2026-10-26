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
    # ★ [Round 24] 国家级科研/科普权威域（科学类事实题常只召回这些）
    "cas.cn", "kepu.net.cn", "kepuchina.cn", "cma.gov.cn", "most.gov.cn",
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
    后到的记 dropped = {evidence_id, reason, against}。

    ★ [V2.2.3 Round 8] 官方源优先：同一 URL/文本多渠道时，若保留者是非官方、
    后到者是官方源，则**用官方源替换保留者**（旧项记 dedup_prefer_official）。
    否则事实门会因「官方源被当重复丢掉」出现假性 no_official_source/unverified。
    """
    kept: list[Evidence] = []
    dropped: list[dict] = []
    seen_url: dict[str, str] = {}
    seen_fp: dict[str, str] = {}
    kept_idx: dict[str, int] = {}
    for it in list(items or []):
        u = normalize_url(it.url)
        dup_id = seen_url.get(u) if u else None
        if dup_id is None and it.fingerprint:
            dup_id = seen_fp.get(it.fingerprint)
        if dup_id is not None:
            old = kept[kept_idx[str(dup_id)]] if str(dup_id) in kept_idx else None
            if (old is not None and bool(getattr(it, "official", False))
                    and not bool(getattr(old, "official", False))):
                # 官方源顶替非官方保留者（保持原位置，审计留痕）
                dropped.append({"evidence_id": str(old.evidence_id),
                                "reason": "dedup_prefer_official",
                                "against": str(it.evidence_id)})
                kept[kept_idx[str(dup_id)]] = it
                if u and seen_url.get(u) == str(dup_id):
                    seen_url[u] = it.evidence_id
                if it.fingerprint and seen_fp.get(it.fingerprint) == str(dup_id):
                    seen_fp[it.fingerprint] = it.evidence_id
                kept_idx.pop(str(dup_id), None)
                kept_idx[str(it.evidence_id)] = len(kept) - 1
                continue
            dropped.append({"evidence_id": it.evidence_id,
                            "reason": "dup_url" if u and u in seen_url
                            else "dup_text",
                            "against": dup_id})
            continue
        if u:
            seen_url[u] = it.evidence_id
        if it.fingerprint:
            seen_fp[it.fingerprint] = it.evidence_id
        kept_idx[str(it.evidence_id)] = len(kept)
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
    r"(%|％|mmHg|毫米汞柱|万亿美元|亿美元|亿斤|亿|亿元|万亿元|万美元|万元|万人|万辆|万|周岁|岁|年|个|倍|天|"
    r"小时|公里|千米|米|元|"
    r"美元|人|条|项|分|秒|次|度)?")
_STRIP_CTX = " \t\u3000，,：:是为达到了约共计有"
_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})\s*年")


def _norm_unit(unit: str) -> str:
    u = str(unit or "").strip()
    return "%" if u in ("%", "％") else u


_CN_DIGIT = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000}


def cn_num_to_int(s: str):
    """中文数字转整数（支持 十八/二十/二十二/一百零五 等常见写法）。"""
    s = str(s or "").strip()
    if not s:
        return None
    total = 0
    section = 0
    num = 0
    for ch in s:
        if ch in _CN_DIGIT:
            num = _CN_DIGIT[ch]
        elif ch in _CN_UNIT:
            if num == 0:
                num = 1
            section += num * _CN_UNIT[ch]
            num = 0
        else:
            return None
    return total + section + num


def extract_numeric_claims(text: str) -> list:
    """从一段文本里抽「数值主张」：{context, unit, value, anchor, raw}。

    - anchor：同句的年份时间锚（不同年份的同一句式**不判冲突**）；
    - context：去掉数字后的上下文（谁在说哪个量）；
    - 年份（1900–2100 且单位「年」）只当时间锚，不算被主张的数值。
    """
    # ★ [Round 41] 千分位归一：384,399 → 384399（仅「逗号后恰好三位数字」，
    #   不误伤「1, 2」这类列表分隔）
    _txt = str(text or "")
    _prev = None
    while _prev != _txt:
        _prev = _txt
        _txt = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", _txt)
    out: list[dict] = []
    last_anchor = ""
    prev_raw = ""
    for clause in _CLAUSE_RE.split(_txt):
        clause = clause.strip()
        if not clause:
            continue
        _prev = prev_raw
        prev_raw = clause
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
            # ★ [Round 33] 「分别」句式：按数字出现序号区分（产/销、进口/出口…）
            if "分别" in clause:
                _seq = [mm.start() for mm in _NUM_RE.finditer(clause)]
                try:
                    ctx = ctx + "|ord%d" % _seq.index(m.start())
                except ValueError:
                    pass
            # ★ [Round 19] 短尾分句（如「比上年增长%」）需要主语残留：拼上一分句
            #   的主语，否则 GDP/第一产业/人均收入 的不同数值会被归到同一桶成假冲突。
            if len(ctx) < 8 and _prev:
                _p = re.sub(r"[\d.\-]", "", str(_prev))
                _p = re.sub(r"\s+", "", _p).strip(_STRIP_CTX)[:24]
                if _p:
                    ctx = _p + "|" + ctx
            out.append({"context": ctx, "unit": unit, "value": val,
                        "anchor": anchor, "raw": m.group(0)})
    # ★ [Round 35] 中文数字（法条/古文献常见：二十二周岁、二十岁）
    _cn_re = re.compile(r"([一二两三四五六七八九十百千零]{1,6})(周岁|岁)")
    _txt = str(text or "")
    for _m in _cn_re.finditer(_txt):
        _val = cn_num_to_int(_m.group(1))
        if _val is None or not (0 < _val < 200):
            continue
        _ctx = _txt[max(0, _m.start() - 60):_m.start()]
        _ctx = re.sub(r"[\d.\-]", "", _ctx)
        _ctx = re.sub(r"\s+", "", _ctx).strip(_STRIP_CTX)
        out.append({"context": (_ctx + "|cn" + _m.group(2)) if _ctx
                    else "cn|" + _m.group(2),
                    "unit": _m.group(2), "value": float(_val),
                    "anchor": "", "raw": _m.group(0)})
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
        # ★ [Round 19] 裸数字（无单位+无上下文）不是同一事实主张——即使带年份锚，
        #   也不能把 R&D 支出里的 4.0 与 GDP 的 5.0 判成冲突（GDP 真实反例）。
        if key[1] in ("", "number", "num") and not key[2]:
            continue
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


_TERM_SPLIT_RE = re.compile(
    r"每分钟|哪些|哪几|哪|的|是|多少|什么|几|了|吗|呢|有|次|规定|成年|？|\?|"
    r"，|,|\s+|在|中(?!国)")
_OVERALL_UNIT_MARKERS: tuple[str, ...] = (
    "全长", "总长", "总长度", "长度", "最高", "海拔", "最宽", "宽度",
    "最深", "深度", "距离", "速度", "面积", "重量", "总计", "合计",
    "整体", "总里程", "总高度",
)


#: 整体量词项的近义覆盖（题面「长度」被证据「全长/总长」覆盖是正常表述）。
_SEG_ALIASES: dict[str, tuple[str, ...]] = {
    "长度": ("长度", "全长", "总长", "总长度", "长"),
    "高度": ("高度", "高程", "海拔", "高"),
    "宽度": ("宽度", "宽"),
    "深度": ("深度", "深"),
    "距离": ("距离", "远"),
    "速度": ("速度", "快慢"),
    "面积": ("面积", "占地"),
    "重量": ("重量", "质量", "重"),
    "大小": ("大小", "规模"),
    "增速": ("增速", "增长", "增长率", "同比增"),
    "增长": ("增长", "增速", "增长率"),
    "GDP": ("GDP", "gdp", "国内生产总值", "国内生产总值"),
    "CPI": ("CPI", "cpi", "居民消费价格"),
    "PPI": ("PPI", "ppi", "工业生产者出厂价格"),
    "千米": ("千米", "公里", "km", "KM", "Km"),
    "公里": ("公里", "千米", "km", "KM", "Km"),
    "米": ("米", "meter", "m"),
}


def _seg_covered(seg: str, corpus: str) -> bool:
    if seg in corpus:
        return True
    return any(a in corpus for a in _SEG_ALIASES.get(seg, ()))


_TERM_TOKEN_RE = re.compile(r"[A-Za-z0-9._]+|[\u4e00-\u9fa5]+")


def _term_tokens_covered(term: str, corpus: str) -> bool:
    """末级判定：把词项切成中/英数片段，逐段命中（含近义）即视为覆盖。

    真实反例（GDP 题）：词项「2024年中国GDP增速最新数据」在证据里永远找不到
    整短语；但「2024」「中国」「GDP」「增速→增长」都已出现 ⇒ 应算覆盖。
    """
    raw_pieces = [x for x in _TERM_TOKEN_RE.findall(str(term or "")) if x]
    pieces = []
    for x in raw_pieces:
        if x.isdigit() or re.fullmatch(r"[A-Za-z0-9._]+", x):
            if len(x) >= 2:
                pieces.append(x)
            continue
        # 中文片段：按功能字切分，再去泛化后缀
        subs = [y for y in re.split(r"[年的了是与和在对为]", x) if len(y) >= 2]
        for y in (subs or [x]):
            _trim = re.sub(r"(最新数据|数据|数值|是多少|多少|是什么|最新)$", "",
                           y)
            if _trim and len(_trim) >= 2:
                y = _trim
            pieces.append(y)
    pieces = [x for x in pieces if len(x) >= 2]
    if not pieces:
        return False
    for pc in pieces:
        if pc in corpus:
            continue
        # 数字/年份片段：未出现则不算覆盖
        if pc.isdigit():
            return False
        if _seg_covered(pc, corpus):
            continue
        # ★ [Round 31] 长复合词（≥4 字）：2-gram 覆盖率 ≥80% 视为覆盖
        #   （「中国现行宪法」被「中国/现行/宪法」覆盖；随机切分会因比例不足被拒）
        if len(pc) >= 4:
            _grams = [pc[_i:_i + 2] for _i in range(len(pc) - 1)]
            _hit = sum(1 for _g in _grams if _g in corpus)
            if _grams and _hit / len(_grams) >= 0.8:
                continue
        return False
    return True


def _term_covered(term: str, corpus: str) -> bool:
    """词项覆盖判定：整短语命中优先；否则按语气词切片段，全片段（含近义）命中即可。"""
    term = str(term or "").strip()
    corpus = str(corpus or "")
    if not term:
        return True
    if term in corpus:
        return True
    parts = [x.strip() for x in _TERM_SPLIT_RE.split(term) if x.strip()]
    parts = [x for x in parts if len(x) >= 2]
    if len(parts) < 1:
        # 全为问句标记（如「次每分钟」）⇒ 无实质词项可验，视为覆盖
        return True
    def _part_ok(x: str) -> bool:
        if _seg_covered(x, corpus):
            return True
        # ★ [Round 40] 长片段（≥4 字）2-gram 覆盖率 ≥80% 也视为覆盖：
        #   「奥林匹克五环」被 奥林匹克/五环 覆盖（语料里常写作「奥林匹克…五环」）
        if len(x) >= 4:
            _g = [x[_i:_i + 2] for _i in range(len(x) - 1)]
            _h = sum(1 for _gg in _g if _gg in corpus)
            if _g and _h / len(_g) >= 0.8:
                return True
        return False

    if all(_part_ok(x) for x in parts):
        return True
    # ★ [Round 19] 末级：token 级覆盖（中/英数分段 + 近义 + 去泛化后缀）
    return _term_tokens_covered(term, corpus)


#: 题面「整体量」问法（问全长/总高，而不是分段值）
_Q_OVERALL: tuple[str, ...] = (
    "长度", "多长", "全长", "总长", "总长度", "高度", "多高", "海拔",
    "宽度", "多宽", "深度", "多深", "距离", "多远", "速度", "多快",
    "面积", "重量", "多重", "多大", "总里程",
)


def _overall_quantity_bonus(text: str, question: str) -> float:
    """题面问整体量时，整体量标记证据加分（区分「全长」与「河段长」）。

    权重取 1.0：黄河真实跑次里官方「河段长3472千米」的相关度 0.8 + 官方 0.15
    = 0.95，必须让「黄河全长约5464公里」的口径语义优先（+1.0）反超。
    """
    q = str(question or "")
    if not any(k in q for k in _Q_OVERALL):
        return 0.0
    txt = str(text or "")
    return 1.0 if any(k in txt for k in _OVERALL_UNIT_MARKERS) else 0.0


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
                 if str(t) and not _term_covered(str(t), corpus)]
    for t in uncovered[:3]:
        gaps.append("uncovered:" + t)
    return gaps


_DATE_RE = re.compile(
    r"(?:19|20)\d{2}[-/年]\d{1,2}[-/月]\d{1,2}(?:日)?")


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
    # ★ [Round 13] 数值型问句：优先返回含「数值+单位」的句子（必须早于
    #   日期句分支，否则带日期的无数值首句会先返回，答案丢失目标数值）。
    if any(k in _q for k in ("多少", "几", "多长", "多高", "多重", "多远",
                             "多深", "多宽", "多大", "多快", "千米", "公里",
                             "米", "%", "海拔", "速度", "面积", "重量")):
        _NUM_UNIT_PAT = re.compile(
            r"\d+(?:\.\d+)?\s*(?:多|余|约|近)?\s*(?:千米|公里|米|厘米|"
            r"毫米|%|℃|吨|公斤|kg|年|小时|分钟|秒|万)")
        _concepts = re.findall(r"[A-Za-z]{2,}|[\u4e00-\u9fa5]{2,}", _q)
        _cmp = ("比", "慢约", "快约", "高约", "低约", "相差", "差异", "差约",
                "只比", "约慢", "约快")
        _cands = []
        for _idx, part in enumerate(re.split(r"[。；;\n]", s)):
            if not _NUM_UNIT_PAT.search(part):
                continue
            _hit = sum(1 for c in _concepts if c in part)
            _cmp_pen = 1 if any(c in part for c in _cmp) else 0
            _cands.append((_hit, -_cmp_pen, -_idx, part))
        if _cands:
            _cands.sort(reverse=True)
            return _cands[0][3].strip()[:240]
    # ★ [Round 55] 列举问句（哪几种/哪些/列举）：优先顿号列举句
    if any(k in _q for k in ("哪几种", "哪些", "有哪", "列举")):
        _cands = []
        for _idx, part in enumerate(re.split(r"[。；;\n]", s)):
            _comma = part.count("、")
            if _comma < 1:
                continue
            _hit = sum(1 for c in re.findall(r"[\u4e00-\u9fa5]{2,}", _q)
                       if c in part)
            _cands.append((_comma, _hit, -_idx, part))
        if _cands:
            _cands.sort(reverse=True)
            return str(_cands[0][3]).strip()[:240]
    # ★ [Round 47] 命名问句：优先返回含命名动词的句子
    if any(k in _q for k in ("名字", "名称", "叫什么", "命名", "代号")):
        _cands = []
        for _idx, part in enumerate(re.split(r"[。；;\n]", s)):
            if not any(k in part for k in ("命名为", "被命名", "称为", "名为",
                                           "代号", "全称", "简称")):
                continue
            _hit = sum(1 for c in re.findall(r"[\u4e00-\u9fa5]{2,}", _q)
                       if c in part)
            _cands.append((_hit, -_idx, part))
        if _cands:
            _cands.sort(reverse=True)
            return str(_cands[0][2]).strip()[:240]
    # ★ [Round 45] 范围型问句（多少次/范围/每分钟）：优先返回含「A-B次」区间的句子
    if any(k in _q for k in ("多少次", "范围", "每分钟", "区间")):
        _rng = re.compile(r"\d+(?:\.\d+)?\s*[-—~～至到]\s*\d+(?:\.\d+)?"
                          r"\s*(?:次/分|次每分钟|次|岁|米|%|分钟|秒)")
        _cands = []
        for _idx, part in enumerate(re.split(r"[。；;\n]", s)):
            if not _rng.search(part):
                continue
            _hit = sum(1 for c in re.findall(r"[\u4e00-\u9fa5]{2,}", _q)
                       if c in part)
            _cands.append((_hit, -_idx, part))
        if _cands:
            _cands.sort(reverse=True)
            return str(_cands[0][2]).strip()[:240]
    # ★ [Round 43] 地点问句优先于日期句分支（避免被历史日期句截走）
    _loc_q2 = any(k in _q for k in ("哪个城市", "哪座城市", "哪个国家", "何地",
                                    "哪里", "在什么地方", "位于", "设在"))
    if _dates and not _loc_q2:
        # ★ [Round 30] 日期句也加题面概念排序（避免取到无关文书的日期）
        _dc = re.findall(r"[A-Za-z]{2,}", _q)
        _dc += [str(_q[_i:_i + 2]) for _i in range(len(_q) - 1)
                if "\u4e00" <= _q[_i] <= "\u9fa5"
                and "\u4e00" <= _q[_i + 1] <= "\u9fa5"]
        _cands = []
        for _idx, part in enumerate(re.split(r"[。；;\n]", s)):
            if not _DATE_RE.search(part):
                continue
            _hit = sum(1 for c in _dc if c in part)
            _cands.append((_hit, -_idx, part))
        if _cands:
            _cands.sort(reverse=True)
            return str(_cands[0][2]).strip()[:240]
    # ★ [Round 43] 地点问句：优先返回含「城市/位于/设在」的短句
    if _loc_q2:
        _lc = re.findall(r"[A-Za-z]{2,}|[\u4e00-\u9fa5]{2,}", _q)
        _cands = []
        for _idx, part in enumerate(re.split(r"[。；;\n]", s)):
            if not (re.search(r"[\u4e00-\u9fa5]{2,6}市", part)
                    or "位于" in part or "设在" in part):
                continue
            _hit = sum(1 for c in _lc if c in part)
            _city = 1 if re.search(r"[\u4e00-\u9fa5]{2,6}市", part) else 0
            _addr = 1 if any(k in part for k in ("地址", "位于", "设在")) else 0
            _cands.append((_city + _addr, _hit, -_idx, part))
        if _cands:
            _cands.sort(reverse=True)
            return str(_cands[0][3]).strip()[:240]
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


_RECENCY_CUES: tuple[str, ...] = (
    "最新", "当前", "现在", "目前", "截至", "如今", "现行", "updated",
    "latest", "current",
)


def _text_date_score(text: str) -> float:
    """从文本里抽最近日期（YYYY-MM-DD / YYYY年/月）用于时效排序；无则 -1。"""
    import re as _re
    s = str(text or "")
    best = -1.0
    # 年份只认 1800-2099，且要求前面不是数字（避免把 8844.43 这类小数的
    # 「8844.」当成 8844 年）；月/日可选。
    pat = (r"(?<!\d)(1[89]\d{2}|20\d{2})"
           r"(?:[-/年.](0?[1-9]|1[0-2]))?"
           r"(?:[-/月.](0?[1-9]|[12]\d|3[01]))?")
    for mt in _re.finditer(pat, s):
        y = mt.group(1)
        m = mt.group(2)
        d = mt.group(3)
        try:
            yv = float(y)
        except (TypeError, ValueError):
            continue
        mv = float(m) if m else 6.0
        dv = float(d) if d else 15.0
        score = yv * 10000 + mv * 100 + dv
        best = max(best, score)
    return best


def answer_from_evidence(items: Iterable, question: str = "",
                         prefer_recent: bool = False) -> str:
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
    _asks_date_q = any(k in q for k in ("哪一年", "哪年", "何时", "什么时候",
                                        "年份"))
    _asks_loc_q = any(k in q for k in ("哪个城市", "哪座城市", "哪个国家", "何地",
                                       "哪里", "在什么地方", "位于"))
    _asks_name_q = any(k in q for k in ("名字", "名称", "叫什么", "命名", "代号",
                                        "全称", "简称"))
    scored = []
    _recent = bool(prefer_recent) and any(k in q for k in _RECENCY_CUES)
    _dates = [_text_date_score(str(getattr(e, "snippet", "") or ""))
              for e in evs] if _recent else []
    _max_date = max(_dates) if _dates else -1.0
    for _i, e in enumerate(evs):
        text = str(getattr(e, "snippet", "") or "")
        score = _answer_relevance(text, q)
        if bool(getattr(e, "official", False)):
            score += 0.15
        # ★ [Round 93] 命名问句：定义句加分；「它/其中/包括…」描述句减分
        if any(k in str(question or "") for k in ("是什么", "哪个", "哪座",
                                                   "哪条", "是谁", "叫什么")):
            if re.search(r"[\u4e00-\u9fa5]{2,10}(?:高原|平原|盆地|河|湖|山|峰|"
                         r"器官|国家|城市|岛|海)是", text):
                score += 0.4
            if text.strip().startswith(("...", "…", "它", "其", "它包括")):
                score -= 0.2
        # ★ [Round 88] 辟谣/流言证据降权（避免把「说法并不科学」当答案）
        if any(k in text for k in ("流言", "谣言", "辟谣", "并不科学", "不科学",
                                   "并非", "误传", "错误说法")):
            score -= 0.7
        # ★ [Round 47] 命名问句：含命名动词的证据加分
        if _asks_name_q and any(k in text for k in (
                "命名为", "被命名", "称为", "名为", "代号", "全称", "简称")):
            score += 0.5
        # ★ [Round 43] 地点问句：城市句式/地址句式证据加分
        if _asks_loc_q:
            _city_n = len(re.findall(r"[\u4e00-\u9fa5]{2,6}市", text))
            if _city_n or "位于" in text or "设在" in text:
                score += 0.6 + 0.15 * min(_city_n, 3)
            _head = str(text or "")[:90]
            if any(k in _head for k in ("地址", "位于", "设在", "总部")):
                score += 0.4
        # ★ [Round 31] 日期问句：同时含题面 2-gram 与年份的证据额外加权
        if _asks_date_q and re.search(r"(?:19|20)\d{2}", text):
            _qg = [q[_i:_i + 2] for _i in range(len(q) - 1)
                   if "\u4e00" <= q[_i] <= "\u9fa5"
                   and "\u4e00" <= q[_i + 1] <= "\u9fa5"]
            _hits = sum(1 for g in _qg if g in text)
            score += 0.35 * min(_hits, 3)
        score += _overall_quantity_bonus(text, q)
        if _recent and _max_date > 0 and _i < len(_dates) \
                and _dates[_i] == _max_date:
            # 时效题：最新日期证据加权（0.5 足以反超非最新官方源的 0.15）
            score += 0.5
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
