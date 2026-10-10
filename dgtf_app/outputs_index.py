# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 产物索引与检索（只读）。

扫描 `outputs/*.md`（引擎的真跑产物），把头部那一段元数据
（`**时间**` / `**调度**` / `**停止**` / `**可判定性**` / `**取向**` / …）
解析成结构化记录，供前端做列表、筛选与关键词检索。

只读：本模块不写任何产物、不碰引擎主文件。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# 头部元数据都挤在文件开头，只读前若干字节即可
_HEADER_SCAN_BYTES = 16000

# `**键**：值`  —— 半角/全角冒号都要认（v1.23.14 踩过：只写全角命中 0 条）
_KV_RE = re.compile(r"^\*\*(?P<k>[^*]+?)\*\*\s*[:：]\s*(?P<v>.*)$")
_TITLE_RE = re.compile(r"^#\s*(?:元\s*)?DGTF\s*[·:：]\s*(?P<t>.+?)\s*$")
_FNAME_RE = re.compile(r"^(?P<ts>\d{8}_\d{6})_(?P<q>.+)\.md$")

# 缓存：文件集合 + 各自 mtime 不变就复用
_CACHE: dict = {"key": None, "records": []}

# 前端筛选用到的维度 → 头部元数据键
FACET_KEYS = {
    "decidability": "可判定性",
    "orientation": "取向",
    "parallel": "并行模式",
    "stop": "停止",
}


def _read_head(path: Path, n: int = _HEADER_SCAN_BYTES) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(n)
    except OSError:
        return ""


def _parse_header(text: str) -> tuple[str, dict]:
    """从头部文本里取标题与元数据键值对。"""
    lines = text.splitlines()
    title = ""
    if lines:
        m = _TITLE_RE.match(lines[0].strip())
        if m:
            title = m.group("t").strip()

    meta: dict[str, str] = {}
    pending_key: str | None = None
    for raw in lines[1:]:
        s = raw.strip()
        if not s:
            continue
        m = _KV_RE.match(s)
        if m:
            k, v = m.group("k").strip(), m.group("v").strip()
            if k not in meta:
                meta[k] = v
                pending_key = k if not v else None
            continue
        # 缩进子项 → 并入上一个键的值（如「**分层目标**：」下面的层明细）
        if raw[:1] in (" ", "\t") and pending_key:
            meta[pending_key] = (meta[pending_key] + " " + s).strip()
            continue
        if s[:1] in ("-", "*", "•"):  # 头部里的项目符号行（可判定清单等）
            continue
        # 既不是 KV、也不是列表/缩进 → 正文开始了
        break
    return title, meta


def _parse_one(path: Path) -> dict:
    st = path.stat()
    head = _read_head(path)
    title, meta = _parse_header(head)

    fname_q = ""
    m = _FNAME_RE.match(path.name)
    if m:
        fname_q = m.group("q").replace("_", " ").strip()

    question = title or fname_q or path.stem
    ts = meta.get("时间", "")
    packed = path.with_suffix(".packed.json")
    return {
        "name": path.name,
        "title": title or question,
        "question": question,
        "time": ts,
        "mtime": st.st_mtime,
        "size": st.st_size,
        "has_packed": packed.exists(),
        "meta": meta,
    }


def _dir_signature() -> tuple:
    if not OUTPUTS_DIR.is_dir():
        return ()
    sig = []
    try:
        for p in sorted(OUTPUTS_DIR.glob("*.md")):
            try:
                sig.append((p.name, p.stat().st_mtime))
            except OSError:
                pass
    except OSError:
        pass
    return tuple(sig)


def scan(force: bool = False) -> list[dict]:
    """返回全部产物记录，按时间倒序。带缓存的只读扫描。"""
    sig = _dir_signature()
    if not force and _CACHE["key"] == sig:
        return _CACHE["records"]

    records = []
    for p in OUTPUTS_DIR.glob("*.md"):
        try:
            records.append(_parse_one(p))
        except OSError:
            continue
    records.sort(key=lambda r: r["mtime"], reverse=True)
    _CACHE["key"] = sig
    _CACHE["records"] = records
    return records


def read_body(name: str, limit: int | None = None) -> str:
    """读取某份产物正文（整篇；limit 为字符上限）。"""
    p = OUTPUTS_DIR / Path(name).name  # 只取文件名，挡目录穿越
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit) if limit else f.read()
    except OSError:
        return ""


def _snippet(text: str, q: str, width: int = 180) -> str:
    low, ql = text.lower(), q.lower()
    i = low.find(ql)
    if i < 0:
        return ""
    a = max(0, i - width // 2)
    b = min(len(text), i + len(q) + width // 2)
    s = text[a:b].replace("\n", " ").strip()
    return ("…" if a else "") + s + ("…" if b < len(text) else "")


def _pass_filters(rec: dict, filters: dict) -> bool:
    if not filters:
        return True
    days = filters.get("days")
    if days:
        try:
            if time.time() - rec["mtime"] > float(days) * 86400:
                return False
        except (TypeError, ValueError):
            pass
    for fkey, mkey in FACET_KEYS.items():
        want = filters.get(fkey)
        if want:
            have = rec["meta"].get(mkey, "")
            if want.lower() not in have.lower():
                return False
    if filters.get("has_packed") and not rec["has_packed"]:
        return False
    return True


def search(query: str = "", *, with_body: bool = False,
           filters: dict | None = None, limit: int = 300) -> list[dict]:
    """关键词检索（默认搜标题 + 头部元数据；with_body=True 时再搜正文）。"""
    q = (query or "").strip()
    out: list[dict] = []
    for rec in scan():
        if not _pass_filters(rec, filters or {}):
            continue
        if not q:
            out.append(dict(rec))
            continue
        head_hay = rec["title"] + "\n" + json.dumps(rec["meta"], ensure_ascii=False)
        if q.lower() in head_hay.lower():
            r = dict(rec)
            r["snippet"] = _snippet(head_hay, q)
            r["matched_in"] = "head"
            out.append(r)
            continue
        if with_body:
            body = read_body(rec["name"])
            if q.lower() in body.lower():
                r = dict(rec)
                r["snippet"] = _snippet(body, q)
                r["matched_in"] = "body"
                out.append(r)
        if len(out) >= limit:
            break
    return out[:limit]


def facets() -> dict:
    """给前端下拉框用的可选值集合。"""
    from collections import Counter
    counters = {k: Counter() for k in FACET_KEYS}
    for rec in scan():
        for fkey, mkey in FACET_KEYS.items():
            v = rec["meta"].get(mkey, "")
            if v:
                counters[fkey][v] += 1
    return {k: [{"value": v, "count": n} for v, n in c.most_common()]
            for k, c in counters.items()}


def stats() -> dict:
    recs = scan()
    total_bytes = sum(r["size"] for r in recs)
    return {
        "count": len(recs),
        "total_mb": round(total_bytes / 1024 / 1024, 1),
        "packed": sum(1 for r in recs if r["has_packed"]),
        "latest": recs[0]["title"] if recs else "",
        "latest_time": recs[0]["time"] if recs else "",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "search":
        for r in search(" ".join(sys.argv[2:]) or ""):
            print(f"- {r['time']}  {r['title']}")
    else:
        print(json.dumps(stats(), ensure_ascii=False, indent=2))
