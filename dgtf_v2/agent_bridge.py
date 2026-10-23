# -*- coding: utf-8 -*-
"""把元DGTF自反馈转成 DSH Agent 可消费任务；Search/Fetch 知识刷新。"""
from __future__ import annotations
import hashlib, json, time
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_QUEUE = "dgtf_memory/agent_tasks.jsonl"
DEFAULT_KNOWLEDGE = "dgtf_memory/agent_knowledge.jsonl"

# 夹具/测试跑不能进生产 Agent 队列（与 decision_policy/unified_memory 同源）。
FIXTURE_RUN_PREFIXES = ("E2E_", "test", "smoke", "pytest", "v2-", "probe",
                        "anon", "rs4", "fixture")


def _fp(s: str) -> str:
    return hashlib.sha1(str(s).encode("utf-8")).hexdigest()[:12]


def _is_fixture_run(run_id: str) -> bool:
    rid = str(run_id or "").strip().lower()
    return (not rid) or any(rid.startswith(p.lower()) for p in FIXTURE_RUN_PREFIXES)


def build_tasks(packed: dict, run_id: str = "") -> list:
    p = packed or {}
    # 夹具空跑/测试跑不产出生产任务，避免 RS4、rounds=0 污染队列。
    if _is_fixture_run(run_id) or p.get("mock") or p.get("fixture"):
        return []
    out = []
    sf = p.get("self_feedback") or {}
    for c in (sf.get("eml_candidates") or []):
        act = c.get("action") or {}
        out.append({
            "kind": "eml_candidate",
            "severity": "med",
            "title": "验证/应用 EML 候选：%s" % (act.get("key") or c.get("kind")),
            "detail": json.dumps(c, ensure_ascii=False)[:1200],
            "source_run": run_id,
        })
    aud = p.get("decidability_audit") or {}
    for r in (aud.get("rows") or []):
        if str(r.get("status") or "") in ("bad", "unverified", "empty"):
            out.append({"kind": "audit_gap", "severity": "high",
                        "title": "研究判定缺口：%s" % (r.get("claim") or "")[:60],
                        "detail": json.dumps(r, ensure_ascii=False)[:1200],
                        "source_run": run_id})
    pl = p.get("process_ledger") or {}
    for e, r in (pl.get("layers") or {}).items():
        if not r.get("standard_ok"):
            out.append({"kind": "process_gap", "severity": "high",
                        "title": "层 %s 过程标准未达标" % e,
                        "detail": json.dumps(r, ensure_ascii=False)[:1200],
                        "source_run": run_id})
    for f in ((p.get("quality") or {}).get("flags") or [])[:12]:
        out.append({"kind": "quality_flag", "severity": "low",
                    "title": "质量线索：%s" % str(f)[:80],
                    "detail": str(f), "source_run": run_id})
    api = p.get("api_usage") or {}
    if api and not api.get("tools_calls"):
        out.append({"kind": "api_gap", "severity": "med",
                    "title": "Tool Calls 未触发，排查预检/配置",
                    "detail": json.dumps(api, ensure_ascii=False), "source_run": run_id})
    for t in out:
        t["id"] = _fp(t.get("kind", "") + "|" + t.get("title", ""))
    return out


def enqueue(packed: dict, run_id: str = "", path: str = DEFAULT_QUEUE) -> dict:
    q = Path(path)
    q.parent.mkdir(parents=True, exist_ok=True)
    old = set()
    if q.exists():
        for ln in q.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                old.add(json.loads(ln).get("id"))
            except Exception:
                pass
    added = []
    with q.open("a", encoding="utf-8") as f:
        for t in build_tasks(packed, run_id):
            if t["id"] in old:
                continue
            t.setdefault("ts", time.time())
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
            added.append(t)
    return {"added": len(added), "path": str(q), "tasks": added}


def append_task(task: dict, path: str = DEFAULT_QUEUE) -> dict:
    q = Path(path); q.parent.mkdir(parents=True, exist_ok=True)
    t = dict(task or {})
    title = str(t.get("title") or "").strip()
    # 空标题、乱码占位、自指任务不进队列。
    if (not title) or title.count("?") >= 2 or title in (
            "根据生成的提案执行任务", "app ????", "?? Tool Calls ??"):
        return {"rejected": "invalid_title", "task": t}
    if _is_fixture_run(str(t.get("source_run") or "")) and t.get("kind") in (
            "process_gap", "quality_flag", "api_gap", "eml_candidate"):
        return {"rejected": "fixture_run", "task": t}
    t["title"] = title
    t.setdefault("id", _fp(t.get("kind", "task") + "|" + title))
    old = read_tasks(path, 100000)
    if any(str(x.get("id")) == str(t["id"]) or
           str(x.get("title") or "").strip() == title for x in old):
        return {"rejected": "duplicate", "task": t}
    t.setdefault("ts", time.time())
    with q.open("a", encoding="utf-8") as f:
        f.write(json.dumps(t, ensure_ascii=False) + "\n")
    return t


def read_tasks(path: str = DEFAULT_QUEUE, limit: int = 100) -> list:
    q = Path(path)
    if not q.exists():
        return []
    out = []
    for ln in q.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out[-max(1, int(limit)):]


def read_knowledge(path: str = DEFAULT_KNOWLEDGE, limit: int = 20) -> list:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(ln)
            if d.get("fetched") or d.get("content"):
                out.append(d)
        except Exception:
            pass
    return out[-max(1, int(limit)):]


def knowledge_stats(path: str = DEFAULT_KNOWLEDGE) -> dict:
    ks = read_knowledge(path, 200)
    domains = {}
    for x in ks:
        u = str(x.get("url") or "")
        d = u.split("/")[2] if "://" in u else ""
        domains[d] = domains.get(d, 0) + 1
    return {"n": len(ks), "fetched": sum(1 for x in ks if x.get("fetched")),
            "domains": domains, "last_url": (ks[-1].get("url") if ks else "")}


def refresh_knowledge(queries, client, run_id: str = "",
                      path: str = DEFAULT_KNOWLEDGE) -> list:
    """Search+Fetch 官方/技术页，写入知识库；返回条目。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    items = []
    for q in (queries or [])[:4]:
        t_search = time.time()
        try:
            res, _ = client.search(str(q)[:200], max_n=3)
        except Exception:
            res = []
        for it in (res or [])[:2]:
            url = str(it.get("url") or "")
            page = {}
            t_fetch = None
            if url:
                try:
                    page = client.fetch(url) or {}
                    t_fetch = time.time()
                except Exception:
                    page = {}
            content = str(page.get("content") or "")
            items.append({
                "run": run_id, "query": str(q)[:200],
                "title": str(it.get("title") or page.get("title") or ""),
                "url": url, "claim": str(it.get("claim") or "")[:400],
                "content": content[:4000],
                "fetched": bool(content),
                # 检索时间 = Search 调用时间；爬取时间 = Fetch 完成时间。
                # 没抓到正文时 fetched_at 留空，前端标「未爬取正文」。
                "retrieved_at": t_search,
                "fetched_at": t_fetch if content else None,
            })
    if items:
        with p.open("a", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
    return items


__all__ = ["build_tasks", "enqueue", "append_task", "read_tasks", "read_knowledge", "knowledge_stats", "refresh_knowledge", "refresh_knowledge_http",
           "DEFAULT_QUEUE", "DEFAULT_KNOWLEDGE"]

def _paper_pdf_url(url: str) -> str:
    """把论文页/摘要页解析成可下载 PDF；非论文返回空。"""
    u = str(url or "").strip()
    if not u:
        return ""
    low = u.lower()
    if "arxiv.org/abs/" in low:
        return "https://arxiv.org/pdf/" + u.split("/abs/", 1)[1].split("?")[0].strip("/") + ".pdf"
    if "arxiv.org/pdf/" in low:
        return u.split("?")[0]
    if "openreview.net/forum" in low and "id=" in low:
        rid = u.split("id=", 1)[1].split("&")[0]
        return "https://openreview.net/pdf?id=" + rid
    if low.endswith(".pdf") or ".pdf?" in low:
        return u
    if "semanticscholar.org/paper/" in low:
        try:
            import urllib.request as _ur
            import re as _re2
            tail = u.split("/paper/", 1)[1].split("#")[0].rstrip("/")
            parts = [x for x in tail.split("/") if x]
            pid = next((x for x in parts if _re2.fullmatch(r"[0-9a-f]{32,}", x)),
                       (parts[0] if parts else ""))
            api = ("https://api.semanticscholar.org/graph/v1/paper/"
                   + pid + "?fields=openAccessPdf,externalIds,title")
            req = _ur.Request(api, headers={"User-Agent": "Mozilla/5.0"})
            with _ur.urlopen(req, timeout=25) as r:
                d = json.loads(r.read().decode("utf-8"))
            p = (d.get("openAccessPdf") or {}).get("url") or ""
            if p:
                return p
            ax = ((d.get("externalIds") or {}).get("ArXiv") or "")
            if ax:
                return "https://arxiv.org/pdf/" + str(ax) + ".pdf"
        except Exception:
            return ""
    return ""


def _download_paper_pdf(pdf_url: str) -> dict:
    """下载论文 PDF 到 dgtf_memory/agent_knowledge_pdfs；返回路径/文件名。

    走 dgtf_v2.net_policy：只允许公网 http(s)、阻断私网/回环/非标准端口、
    重定向逐跳校验、25MB 上限；外部检索结果不能把本机当抓取目标。
    """
    import hashlib as _h
    import os as _os
    from dgtf_v2.net_policy import open_public, UnsafeURL
    if not pdf_url:
        return {}
    root = Path(__file__).resolve().parent.parent
    d = root / "dgtf_memory" / "agent_knowledge_pdfs"
    d.mkdir(parents=True, exist_ok=True)
    name = _h.sha1(pdf_url.encode("utf-8")).hexdigest()[:16] + ".pdf"
    p = d / name
    try:
        if not p.exists() or p.stat().st_size < 1024:
            data, _final_url, _ctype = open_public(
                pdf_url, timeout=60, max_bytes=25 * 1024 * 1024,
                headers={"User-Agent": "Mozilla/5.0"})
            if not data.startswith(b"%PDF"):
                return {}
            p.write_bytes(data)
        return {"pdf_path": str(p), "pdf_name": name, "pdf_url": pdf_url}
    except Exception:
        return {}


def _zh_annotation(title: str, text: str, url: str, key: str) -> str:
    """用 DeepSeek 给论文/技术正文生成中文注释（保留原文，另附注释）。"""
    import urllib.request as _ur
    if not key:
        return ""
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是元DGTF技术知识助手。只输出中文注释，保留论文/技术专有名词原文。"},
            {"role": "user", "content": (
                "阅读以下技术资料，输出中文注释（≤350字）：\n"
                "1. 核心贡献/结论；\n2. 对多智能体、自进化、知识管理、检索增强的可迁移点；\n"
                "3. 风险或局限。\n\n"
                "标题：" + str(title or "")[:200] + "\nURL：" + str(url or "")[:300] +
                "\n正文：" + str(text or "")[:5000])},
        ],
        "temperature": 0.2,
        "max_tokens": 700,
    }).encode("utf-8")
    req = _ur.Request("https://api.deepseek.com/chat/completions",
                      data=body, headers={
                          "Content-Type": "application/json",
                          "Authorization": "Bearer " + key})
    try:
        with _ur.urlopen(req, timeout=90) as r:
            d = json.loads(r.read().decode("utf-8"))
        return str((((d.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()
    except Exception:
        return ""


def _canon_url(url: str) -> str:
    import urllib.parse as _up
    try:
        u = _up.urlsplit(str(url or "").strip())
        if not u.netloc:
            return ""
        drop = {"ref", "source", "utm_source", "utm_medium", "utm_campaign",
                "utm_term", "utm_content", "spm"}
        q = [(k, v) for k, v in _up.parse_qsl(u.query, keep_blank_values=True)
             if k.lower() not in drop]
        path = (u.path or "/").rstrip("/") or "/"
        return _up.urlunsplit((u.scheme.lower(), u.netloc.lower(), path,
                               _up.urlencode(q), ""))
    except Exception:
        return ""


def _knowledge_keys(it: dict) -> set:
    import hashlib as _h
    import re as _re
    keys = set()
    u = _canon_url(it.get("url"))
    if u:
        keys.add("u:" + u)
    title = _re.sub(r"\s+", " ", str(it.get("title") or "")).strip().lower()
    if title:
        keys.add("t:" + title[:160])
    body = (str(it.get("content") or "") + " " + str(it.get("claim") or "")).strip()
    if body:
        keys.add("f:" + _h.sha1(body[:1200].encode("utf-8")).hexdigest())
    return keys


def _dedupe_records(records):
    """保留每个重复键的最新一条（反向扫描后还原顺序）。"""
    out, seen = [], set()
    for it in reversed(list(records or [])):
        ks = _knowledge_keys(it)
        if ks and (ks & seen):
            continue
        seen.update(ks)
        out.append(it)
    out.reverse()
    return out


def dedupe_knowledge(path: str = DEFAULT_KNOWLEDGE) -> dict:
    p = Path(path)
    if not p.exists():
        return {"before": 0, "after": 0, "removed": 0}
    rows = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(ln)
            if isinstance(d, dict):
                rows.append(d)
        except Exception:
            pass
    keep = _dedupe_records(rows)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in keep),
                 encoding="utf-8")
    return {"before": len(rows), "after": len(keep),
            "removed": max(0, len(rows) - len(keep))}


_OFFICIAL_HOSTS = ("deepseek.com", "api-docs.deepseek.com", "platform.deepseek.com",
                   "github.com/deepseek-ai", "huggingface.co/deepseek-ai")
_PAPER_HOSTS = ("arxiv.org", "openreview.net", "aclanthology.org",
                "semanticscholar.org", "paperswithcode.com", "ieeexplore.ieee.org")
_COMMUNITY_HOSTS = ("github.com", "huggingface.co", "stackoverflow.com",
                    "news.ycombinator.com", "reddit.com", "zhihu.com",
                    "juejin.cn", "medium.com", "dev.to", "infoq.cn")


def _host_of(url: str) -> str:
    try:
        import urllib.parse as _up
        return (_up.urlsplit(str(url or "")).netloc or "").lower()
    except Exception:
        return ""


def _source_type(url: str, pdf_url: str = "") -> str:
    h = _host_of(url)
    ul = str(url or "").lower()
    if "github.com/deepseek-ai" in ul or any(x in h for x in _OFFICIAL_HOSTS):
        return "official"
    if pdf_url or any(x in h for x in _PAPER_HOSTS):
        return "paper"
    if any(x in h for x in _COMMUNITY_HOSTS):
        return "community"
    return "other"


def _recency_score(date_s: str) -> int:
    try:
        import datetime as _dt
        s = str(date_s or "").strip().replace("Z", "+00:00")
        d = _dt.datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=_dt.timezone.utc)
        days = max(0, (_dt.datetime.now(_dt.timezone.utc) - d).days)
        if days <= 90:
            return 30
        if days <= 365:
            return 20
        if days <= 730:
            return 8
        return 0
    except Exception:
        return 0


def _candidate_score(it: dict, pdf_url: str = "") -> int:
    url = str(it.get("url") or "")
    h = _host_of(url)
    ul = str(url or "").lower()
    score = 0
    if "github.com/deepseek-ai" in ul or any(x in h for x in _OFFICIAL_HOSTS):
        score += 60
    if pdf_url:
        score += 25
    if any(x in h for x in _PAPER_HOSTS):
        score += 35
    if any(x in h for x in _COMMUNITY_HOSTS):
        score += 15
    score += _recency_score(str(it.get("date") or it.get("published") or ""))
    try:
        score += int(round(float(it.get("rerank_score") or 0) * 3))
    except Exception:
        pass
    try:
        score += int(it.get("authority") or 0)
    except Exception:
        pass
    return score


def refresh_knowledge_http(queries, path: str = DEFAULT_KNOWLEDGE,
                           return_stats: bool = False, limit: int = 3):
    """按官方/PDF论文/高置信社区排序，取可获取的最新前沿内容并写库（入库去重）。"""
    import os as _os
    import urllib.request as _ur
    from dgtf_v2.net_policy import display_url_allowed
    key = _os.getenv("DGTF_API_KEY", "") or _os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        return {"items": [], "skipped_duplicates": 0} if return_stats else []
    seen = set()
    try:
        _p = Path(path)
        if _p.exists():
            for _ln in _p.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    seen.update(_knowledge_keys(json.loads(_ln)))
                except Exception:
                    pass
    except Exception:
        pass
    limit = max(1, min(6, int(limit or 3)))
    candidates, cand_seen, skipped = [], set(), 0
    for q in (queries or [])[:4]:
        t_search = time.time()
        body = json.dumps({"query": str(q)[:128], "count": 6,
                           "need_content": False}).encode("utf-8")
        req = _ur.Request("https://api.deepseek.com/v1/tools/search",
                          data=body, headers={
                              "Content-Type": "application/json",
                              "Authorization": "Bearer " + key})
        try:
            with _ur.urlopen(req, timeout=45) as r:
                res = (json.loads(r.read().decode("utf-8"))
                       .get("results") or [])
        except Exception:
            res = []
        for it in res:
            url = str(it.get("url") or "").strip()
            if not url or not display_url_allowed(url):
                skipped += 1
                continue
            title = str(it.get("title") or "")
            claim = str(it.get("summary") or it.get("content") or "")[:1200]
            base = {"title": title, "url": url, "claim": claim, "content": ""}
            ks = _knowledge_keys(base)
            if ks and (ks & seen or ks & cand_seen):
                skipped += 1
                continue
            cand_seen.update(ks)
            pv = str(it.get("pdf_url") or it.get("pdfUrl") or "")
            if not pv and "semanticscholar.org" not in url.lower():
                pv = _paper_pdf_url(url)
            item = {"query": str(q)[:200], "title": title, "url": url,
                    "claim": claim, "summary": claim,
                    "published": str(it.get("date") or it.get("published") or ""),
                    "authority": it.get("authority") or 0,
                    "pdf_url": pv, "retrieved_at": t_search}
            item["score"] = _candidate_score(it, pv)
            item["source_type"] = _source_type(url, pv)
            candidates.append(item)
    candidates.sort(key=lambda x: int(x.get("score") or 0), reverse=True)
    out = []
    for cand in candidates:
        if len(out) >= limit:
            break
        url = cand["url"]
        title = cand["title"]
        pdf_url = cand.get("pdf_url") or _paper_pdf_url(url)
        _host = (urlparse(url).hostname or "").lower()
        if not pdf_url and (_host == "semanticscholar.org"
                            or _host.endswith(".semanticscholar.org")):
            pdf_url = _paper_pdf_url(url)
        cand["pdf_url"] = pdf_url
        content = ""
        fb = json.dumps({"url": url}).encode("utf-8")
        fr = _ur.Request("https://api.deepseek.com/v1/tools/fetch",
                         data=fb, headers={
                             "Content-Type": "application/json",
                             "Authorization": "Bearer " + key})
        try:
            with _ur.urlopen(fr, timeout=45) as r:
                pg = json.loads(r.read().decode("utf-8"))
            content = str(pg.get("content") or "")[:8000]
            title = str(pg.get("title") or title)
        except Exception:
            pass
        pdf = _download_paper_pdf(pdf_url) if pdf_url else {}
        if not content and not pdf:
            skipped += 1
            continue
        claim = str(cand.get("claim") or "")[:500]
        base = {"title": title, "url": url, "claim": claim, "content": content}
        ks = _knowledge_keys(base)
        if ks and (ks & seen):
            skipped += 1
            continue
        seen.update(ks)
        zh_note = _zh_annotation(title, content or claim, url, key)
        stype = _source_type(url, pdf_url)
        confidence = 0.95 if stype == "official" else (
            0.92 if pdf else (0.85 if stype == "paper" else 0.72))
        item = {"query": cand.get("query") or "", "title": title, "url": url,
                "claim": claim, "content": content, "fetched": bool(content),
                "pdf_url": pdf_url, "zh_note": zh_note,
                "published": cand.get("published") or "",
                "authority": cand.get("authority") or 0,
                "score": cand.get("score") or 0,
                "source_type": stype, "confidence": confidence,
                # 检索时间沿用该候选的 Search 调用时间；
                # 爬取时间 = Fetch/PDF 都完成后的时间，没抓到内容则留空。
                "retrieved_at": cand.get("retrieved_at") or time.time(),
                "fetched_at": time.time() if (content or pdf) else None}
        item.update(pdf)
        out.append(item)
    if out:
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            for it in out:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
    if return_stats:
        return {"items": out, "skipped_duplicates": skipped}
    return out
