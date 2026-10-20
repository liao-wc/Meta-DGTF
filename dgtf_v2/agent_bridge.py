# -*- coding: utf-8 -*-
"""把元DGTF自反馈转成 DSH Agent 可消费任务；Search/Fetch 知识刷新。"""
from __future__ import annotations
import hashlib, json, time
from pathlib import Path

DEFAULT_QUEUE = "dgtf_memory/agent_tasks.jsonl"
DEFAULT_KNOWLEDGE = "dgtf_memory/agent_knowledge.jsonl"


def _fp(s: str) -> str:
    return hashlib.sha1(str(s).encode("utf-8")).hexdigest()[:12]


def build_tasks(packed: dict, run_id: str = "") -> list:
    p = packed or {}
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
    t.setdefault("id", _fp(t.get("kind", "task") + "|" + t.get("title", "")))
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
        try:
            res, _ = client.search(str(q)[:200], max_n=3)
        except Exception:
            res = []
        for it in (res or [])[:2]:
            url = str(it.get("url") or "")
            page = {}
            if url:
                try:
                    page = client.fetch(url) or {}
                except Exception:
                    page = {}
            items.append({
                "run": run_id, "query": str(q)[:200],
                "title": str(it.get("title") or page.get("title") or ""),
                "url": url, "claim": str(it.get("claim") or "")[:400],
                "content": str(page.get("content") or "")[:4000],
                "fetched": bool(page.get("content")),
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
    """下载论文 PDF 到 dgtf_memory/agent_knowledge_pdfs；返回路径/文件名。"""
    import hashlib as _h
    import os as _os
    import urllib.request as _ur
    if not pdf_url:
        return {}
    root = Path(__file__).resolve().parent.parent
    d = root / "dgtf_memory" / "agent_knowledge_pdfs"
    d.mkdir(parents=True, exist_ok=True)
    name = _h.sha1(pdf_url.encode("utf-8")).hexdigest()[:16] + ".pdf"
    p = d / name
    try:
        if not p.exists() or p.stat().st_size < 1024:
            req = _ur.Request(pdf_url, headers={"User-Agent": "Mozilla/5.0"})
            with _ur.urlopen(req, timeout=60) as r:
                data = r.read(25 * 1024 * 1024)
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


def refresh_knowledge_http(queries, path: str = DEFAULT_KNOWLEDGE,
                           return_stats: bool = False):
    """不依赖引擎配置：直接调 DeepSeek Search/Fetch，写技术知识库（入库去重）。"""
    import os as _os
    import urllib.request as _ur
    key = _os.getenv("DGTF_API_KEY", "") or _os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        return {"items": [], "skipped_duplicates": 0} if return_stats else []
    out, skipped = [], 0
    seen = set()
    try:
        _p = Path(path)
        if _p.exists():
            for _ln in _p.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    _d = json.loads(_ln)
                    seen.update(_knowledge_keys(_d))
                except Exception:
                    pass
    except Exception:
        pass
    for q in (queries or [])[:4]:
        body = json.dumps({"query": str(q)[:128], "count": 3,
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
        for it in res[:2]:
            url = str(it.get("url") or "")
            content, title = "", str(it.get("title") or "")
            if url:
                fb = json.dumps({"url": url}).encode("utf-8")
                fr = _ur.Request("https://api.deepseek.com/v1/tools/fetch",
                                 data=fb, headers={
                                     "Content-Type": "application/json",
                                     "Authorization": "Bearer " + key})
                try:
                    with _ur.urlopen(fr, timeout=45) as r:
                        pg = json.loads(r.read().decode("utf-8"))
                    content = str(pg.get("content") or "")[:4000]
                    title = title or str(pg.get("title") or "")
                except Exception:
                    pass
            claim = str(it.get("summary") or it.get("content") or "")[:400]
            base = {"title": title, "url": url, "claim": claim, "content": content}
            keys = _knowledge_keys(base)
            if keys and (keys & seen):
                skipped += 1
                continue
            seen.update(keys)
            pdf_url = str(it.get("pdf_url") or it.get("pdfUrl") or "") or _paper_pdf_url(url)
            pdf = _download_paper_pdf(pdf_url) if pdf_url else {}
            zh_note = _zh_annotation(title, content or claim, url, key)
            item = {"query": str(q)[:200], "title": title, "url": url,
                    "claim": claim, "content": content, "fetched": bool(content),
                    "pdf_url": pdf_url, "zh_note": zh_note}
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
