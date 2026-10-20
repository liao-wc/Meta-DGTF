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

def refresh_knowledge_http(queries, path: str = DEFAULT_KNOWLEDGE) -> list:
    """不依赖引擎配置：直接调 DeepSeek Search/Fetch，写技术知识库。"""
    import os as _os
    import urllib.request as _ur
    key = _os.getenv("DGTF_API_KEY", "") or _os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        return []
    out = []
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
            out.append({"query": str(q)[:200], "title": title, "url": url,
                        "claim": str(it.get("summary") or it.get("content")
                                     or "")[:400],
                        "content": content, "fetched": bool(content)})
    if out:
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            for it in out:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
    return out
