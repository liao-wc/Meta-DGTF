# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 本地资料库（锚点快照）与联网检索库（历史命中）。

- **本地资料库**：扫项目根与 `docs/` 下像「锚点快照」的 JSON
  （含 `anchors` 列表，或条目里带 `id`/`claim`，或文件名带 anchor）——
  列出 / 查看 / 选用（选用 = 告诉用户该填进 `external_anchor.path`）。
- **联网检索库**：两路来源 —— ①产物 md 头部那行
  `**外部锚点 · 联网**（web_search）：**开** —— 收 N 条（…；M 个环节；tier 3×N）`
  （汇总历次跑圈的联网读数）；②`outputs/_web_hits.jsonl` 的逐条命中
  （引擎 v1.23.22 起落盘），由 `group_hits()` **按检索问题聚合、同链接去重**
  成「结果库」。只读。
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import docparse
import outputs_index as oi

PROJECT_ROOT = oi.PROJECT_ROOT
OUTPUTS_DIR = oi.OUTPUTS_DIR

_ANCHOR_HINT = re.compile(r"anchor|锚", re.I)
# **外部锚点 · 联网**（`web_search`）：**开** —— 收 18 条（…）
_WEB_RE = re.compile(r"\*\*外部锚点 · 联网\*\*（`web_search`）：\*\*(开|关)\*\*\s*(.*)$")


def _anchor_items(obj) -> int:
    """粗略判断是不是锚点快照：返回条目数（0 = 不像）。"""
    if isinstance(obj, dict):
        a = obj.get("anchors")
        if isinstance(a, list):
            return len(a)
        if "id" in obj or "claim" in obj:
            return 1
        return 0
    if isinstance(obj, list):
        return sum(1 for it in obj
                   if isinstance(it, dict) and ("id" in it or "claim" in it))
    return 0


def local_anchors(limit: int = 200) -> list[dict]:
    """扫候选锚点文件。返回 [{name, path, size, items, mtime}]。"""
    out: list[dict] = []
    seen: set[str] = set()
    for root in (PROJECT_ROOT, PROJECT_ROOT / "docs"):
        if not root.is_dir():
            continue
        for p in sorted(root.glob("*.json"), key=lambda x: x.stat().st_mtime,
                        reverse=True):
            if p.name in seen or len(out) >= limit:
                continue
            seen.add(p.name)
            try:
                st = p.stat()
                if st.st_size > 4_000_000:
                    continue
                obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except (OSError, ValueError):
                continue
            n = _anchor_items(obj)
            if n <= 0 and not _ANCHOR_HINT.search(p.name):
                continue
            out.append({
                "name": p.name,
                "path": str(p.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "size": st.st_size,
                "items": n,
                "mtime": st.st_mtime,
            })
    return out


def read_local(name: str, limit: int = 200_000) -> str | None:
    """读候选锚点文件（只允许项目根 / docs 下的一层文件名，挡目录穿越）。"""
    base = Path(name).name
    for root in (PROJECT_ROOT, PROJECT_ROOT / "docs"):
        p = root / base
        if p.is_file():
            try:
                return p.read_text(encoding="utf-8", errors="replace")[:limit]
            except OSError:
                return None
    return None


# ── 本地导入：把本地文件变成「外部证据锚点」────────────────────
ANCHORS_DIR = oi.APP_DIR / "anchors"
ANCHOR_FILE = ANCHORS_DIR / "external_anchor.json"
RAW_DIR = ANCHORS_DIR / "_raw"                      # 原始文件留档（解析失败也不丢原件）

# ★ R44：用户定的上限 —— 单次最多 50 个、单文件 100MB。
MAX_FILES = 50
MAX_FILE_BYTES = 100 * 1024 * 1024
# 长文档按块进锚点（引擎一次能读的量有限；分块后长文的覆盖面才够）
CHUNK_CHARS = 2000
MAX_CHUNKS_PER_FILE = 40


def imported_files() -> list[dict]:
    """已导入的原始资料文件。"""
    if not ANCHORS_DIR.is_dir():
        return []
    out = []
    for p in sorted(ANCHORS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if not p.is_file() or p.name == ANCHOR_FILE.name:
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        out.append({"name": p.name, "size": st.st_size, "mtime": st.st_mtime})
    return out


def _rebuild_anchor() -> None:
    """扫导入目录 → 重建合并的锚点快照（引擎认这个格式）。

    ★ R44：**长文档分块**（原来每份只取前 2000 字）—— 一份 5 万字的资料，
    原来进锚点的只有开头那一屏；现在按 `CHUNK_CHARS` 切成多块（每份最多
    `MAX_CHUNKS_PER_FILE` 块），`id` 形如 `L3-2`、`part` 标明第几块，
    「运行时可读入」对长文才真的成立。`_raw/` 是目录，`is_file()` 天然跳过。
    """
    items = []
    if ANCHORS_DIR.is_dir():
        for i, p in enumerate(sorted(ANCHORS_DIR.iterdir()), 1):
            if not p.is_file() or p.name == ANCHOR_FILE.name:
                continue
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            chunks = [txt[j:j + CHUNK_CHARS] for j in range(0, len(txt), CHUNK_CHARS)] \
                or [""]
            chunks = chunks[:MAX_CHUNKS_PER_FILE]
            for k, ch in enumerate(chunks, 1):
                items.append({
                    "id": f"L{i}-{k}" if len(chunks) > 1 else f"L{i}",
                    "claim": ch.strip()[:400],
                    "content": ch,
                    "source": p.name,
                    "part": k,
                    "parts": len(chunks),
                    "kind": "local",
                    "tier": 2,
                })
    ANCHOR_FILE.write_text(
        json.dumps({"anchors": items}, ensure_ascii=False, indent=2),
        encoding="utf-8", newline="")


def _decode_entry(f: dict) -> tuple[bytes, str]:
    """把一条入参还原成**原始字节**。

    两种形态都收：
      · `{name, b64}`   ← 前端现在这么发（二进制安全，PDF / 图片必须走这条）
      · `{name, content}` ← 老的文本入参（`selftest.py` 在用，保持兼容）
    """
    if isinstance(f.get("b64"), str) and f["b64"]:
        return base64.b64decode(f["b64"], validate=False), ""
    if isinstance(f.get("content"), str):
        return f["content"].encode("utf-8"), ""
    return b"", "既没给 b64 也没给 content"


def import_files(files: list[dict]) -> dict:
    """导入本地资料：**解析成文本** → 存进锚点目录 → 重建合并快照。

    参数：`files=[{name, b64} | {name, content}, …]`（见 `_decode_entry`）。
    返回：`{saved, skipped, results, anchor_file}` ——
      `saved/skipped` 是老字段（兼容），`results` 是**逐文件**的明细：
      `{name, ok, kind, chars, error, saved_as}`（失败也留痕，绝不静默）。

    ★ 上限：单次 ≤ `MAX_FILES` 个、单文件 ≤ `MAX_FILE_BYTES`（100MB）。
    ★ 原始文件一律留档到 `anchors/_raw/`：解析失败时**原件还在**，用户能换工具再试。
    ★ 纯文本类直接按原名存（人看着舒服）；富格式存 `<原名>.txt`（解析稿）+ `_raw/<原名>`。
    """
    ANCHORS_DIR.mkdir(exist_ok=True)
    RAW_DIR.mkdir(exist_ok=True)
    saved: list[str] = []
    skipped: list[str] = []
    results: list[dict] = []

    for f in (files or [])[:MAX_FILES]:
        f = f or {}
        n = Path(str(f.get("name") or "")).name
        if not n or n == ANCHOR_FILE.name or n.startswith("."):
            skipped.append(n or "(无名)")
            results.append({"name": n or "(无名)", "ok": False, "kind": "", "chars": 0,
                            "error": "文件名非法", "saved_as": ""})
            continue
        data, why = _decode_entry(f)
        if why:
            skipped.append(n)
            results.append({"name": n, "ok": False, "kind": "", "chars": 0,
                            "error": why, "saved_as": ""})
            continue
        if len(data) > MAX_FILE_BYTES:
            skipped.append(n)
            results.append({"name": n, "ok": False, "kind": "", "chars": 0,
                            "error": "文件 %.1fMB 超过单文件上限 100MB"
                                     % (len(data) / 1048576.0), "saved_as": ""})
            continue

        ext = Path(n).suffix.lower()
        textish = ext in docparse.TEXT_EXT or not ext
        parsed = docparse.extract(n, data)
        # 原件留档（解析失败也留 —— 「失败留痕」且可回退）
        try:
            (RAW_DIR / n).write_bytes(data)
        except OSError:
            pass
        if not parsed["ok"]:
            skipped.append(n)
            results.append({"name": n, "ok": False, "kind": parsed["kind"],
                            "chars": 0, "error": parsed["error"],
                            "saved_as": ""})
            continue
        saved_as = n if textish else n + ".txt"
        try:
            (ANCHORS_DIR / saved_as).write_text(parsed["text"], encoding="utf-8",
                                                newline="")
        except OSError as e:
            skipped.append(n)
            results.append({"name": n, "ok": False, "kind": parsed["kind"], "chars": 0,
                            "error": "写盘失败：%s" % e, "saved_as": ""})
            continue
        saved.append(saved_as)
        results.append({"name": n, "ok": True, "kind": parsed["kind"],
                        "chars": parsed["chars"], "error": "",
                        "saved_as": saved_as})

    _rebuild_anchor()
    return {
        "saved": saved,
        "skipped": skipped,
        "results": results,
        "limits": {"max_files": MAX_FILES, "max_file_mb": 100},
        "anchor_file": str(ANCHOR_FILE.relative_to(oi.PROJECT_ROOT)).replace("\\", "/"),
    }


def delete_imported(name: str) -> bool:
    """删掉一个已导入文件，并重建锚点快照。

    ★ 删不掉时**退到「移走」**：某些隔离环境（本机 sandbox）会拦 unlink，
      但允许 move —— 从列表看效果一样（文件不在导入目录了）。
    """
    n = Path(name).name
    if not n or n == ANCHOR_FILE.name:
        return False
    p = ANCHORS_DIR / n
    if not p.is_file():
        return False
    # ★ R44：富格式导入时原件留档在 `_raw/<原文件名>`，解析稿是 `<原名>.txt`
    #   ⇒ 删的时候**两边一起删**，否则「列表里删了、原件还占着盘」。
    _extras = [RAW_DIR / n]
    if n.endswith(".txt"):
        _extras.append(RAW_DIR / n[:-4])
    for _x in _extras:
        try:
            if _x.is_file():
                _x.unlink()
        except Exception:  # noqa: BLE001
            try:
                trash = ANCHORS_DIR / "_removed"
                trash.mkdir(exist_ok=True)
                _x.replace(trash / _x.name)
            except Exception:  # noqa: BLE001
                pass
    try:
        p.unlink()
    except Exception:  # noqa: BLE001  删除被拦 → 退到移走
        try:
            trash = ANCHORS_DIR / "_removed"
            trash.mkdir(exist_ok=True)
            p.replace(trash / n)
        except Exception:  # noqa: BLE001
            return False
    _rebuild_anchor()
    return True


WEB_HITS_FILE = OUTPUTS_DIR / "_web_hits.jsonl"


def web_hits(limit: int = 800) -> list[dict]:
    """读联网命中 JSONL（引擎 v1.23.22 起落盘）。倒序返回最近 limit 条。"""
    if not WEB_HITS_FILE.is_file():
        return []
    out: list[dict] = []
    try:
        for ln in WEB_HITS_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            if isinstance(rec, dict):
                out.append(rec)
    except OSError:
        return []
    out.sort(key=lambda r: r.get("ts") or 0, reverse=True)
    return out[:limit]


def group_hits(records: list[dict]) -> list[dict]:
    """把联网命中**按检索问题聚合成组、组内按 url 去重**（结果库）。

    纯函数（不吃全局状态），便于用合成样本验证「去重」真生效。
    去重键：url 非空就用 url，否则退化成 claim 前 80 字。
    返回 [{query, total(去重前), uniq(去重后), latest, items}]，按最新时间倒序。
    """
    groups: dict[str, dict] = {}
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        q = str(rec.get("query") or "").strip() or "(无检索问题)"
        g = groups.get(q)
        if g is None:
            g = {"query": q, "total": 0, "uniq": 0, "latest": 0,
                 "items": [], "_seen": set()}
            groups[q] = g
        g["total"] += 1
        key = (str(rec.get("url") or "").strip()
               or ("claim:" + str(rec.get("claim") or "")[:80]))
        if key in g["_seen"]:
            continue
        g["_seen"].add(key)
        g["uniq"] += 1
        g["items"].append(rec)
        g["latest"] = max(g["latest"], rec.get("ts") or 0)
    out = []
    for g in groups.values():
        g.pop("_seen", None)
        out.append(g)
    out.sort(key=lambda x: x["latest"], reverse=True)
    return out


def web_hits_grouped(limit: int = 800) -> list[dict]:
    """联网命中**结果库**：按问题/关键词聚合 + 同链接去重。"""
    return group_hits(web_hits(limit))


def web_results(limit: int = 300) -> list[dict]:
    """汇总历次产物的联网命中读数。"""
    out: list[dict] = []
    for rec in oi.scan()[:limit]:
        head = oi.read_body(rec["name"], limit=8000)
        m = None
        for ln in head.splitlines():
            mm = _WEB_RE.search(ln)
            if mm:
                m = mm
                break
        if not m:
            continue
        out.append({
            "name": rec["name"],
            "title": rec["title"],
            "time": rec["time"],
            "open": m.group(1) == "开",
            "detail": m.group(2).strip().rstrip("；"),
        })
    return out
