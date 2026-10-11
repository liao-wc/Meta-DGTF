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

# ★ R22：产物库不再只有 `*.md` —— **日志（`.run.log`）与 json（`*.json`）也入产物**。
#   每份都带 `kind`（md/log/json）与 `layer`（总/修行/研究/对撞/元）两个分类标签。
#   注：`*.packed.json` 是打包快照（实现细节、且与主产物重复），**不作为产物收录**。
_KINDS = ("md", "log", "json")
_LAYERS = ("修行", "研究", "对撞", "元")


def _strip_suffix(name: str) -> str:
    """去掉「种类 + 层」后缀，得到产物戳（`YYYYMMDD_HHMMSS_<问题>`）。"""
    base = name
    for suf in (".run.log", ".run.json", ".md", ".json"):
        if base.endswith(suf):
            base = base[: -len(suf)]
            break
    for lay in _LAYERS:
        if base.endswith("." + lay):
            base = base[: -len(lay) - 1]
            break
    return base


def kind_of(name: str) -> str:
    if name.endswith(".run.log"):
        return "log"
    if name.endswith(".json"):
        return "json"
    return "md"


def layer_of(name: str) -> str:
    base = name
    for suf in (".run.log", ".run.json", ".md", ".json"):
        if base.endswith(suf):
            base = base[: -len(suf)]
            break
    for lay in _LAYERS:
        if base.endswith("." + lay):
            return lay
    return "总"



def invalidate() -> None:
    """主动让缓存失效：下一次 scan() 必重建（删/改了产物文件后调）。"""
    _CACHE["key"] = None

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

    kind = kind_of(path.name)
    layer = layer_of(path.name)
    stamp = _strip_suffix(path.name)

    fname_q = ""
    m = _FNAME_RE.match(path.name)
    if m:
        fname_q = m.group("q").replace("_", " ").strip()
    if not fname_q and re.match(r"^\d{8}_\d{6}_", stamp):
        fname_q = stamp[16:].replace("_", " ").strip()
    # 日志/json 没有 `**时间**` 头 ⇒ 从文件名戳里取
    if not meta.get("时间") and re.match(r"^\d{4}\d{2}\d{2}_\d{6}", stamp):
        meta.setdefault("时间", "%s-%s-%sT%s:%s:%s" % (
            stamp[0:4], stamp[4:6], stamp[6:8], stamp[9:11], stamp[11:13], stamp[13:15]))

    question = title or fname_q or path.stem
    ts = meta.get("时间", "")
    packed = path.with_suffix(".packed.json")

    # 该产物的运行状态：跑完/终止/部分 / mock，取自同名的 `.run.json`（归档元信息）。
    # 用户要求「产物要标注状态」—— 中途终止的产物 status="cancelled"、partial=true。
    status, partial, mock = "", False, False
    # ★ 老产物没有 .run.json，只能**看内容**：mock 引擎的产物里有这几句，真引擎从不写。
    #   （★ 之前这段「看内容判 mock」写在下面 run.json 块**之前**、又被紧接着的
    #    `status, partial, mock = "", False, False` 整行重置抹掉 —— 等于白写。
    #    顺序必须改成：先重置 → 再看内容 → 再读 run.json（用 or 叠加）。）
    if ("mock_engine.py" in head or "这是 mock 产物" in head
            or "（mock）" in head or "(mock)" in head or "[mock]" in head):
        mock = True
    # ★ 日志 / json 自己没有 `**状态**` 头，也不一定带得到 mock 标记 ——
    #   统一按「同一戳的总产物 `.run.json`」判一次（逐层产物与旁挂文件都靠这条）。
    _base_run = OUTPUTS_DIR / (stamp + ".run.json")
    if _base_run.exists() and _base_run != path:
        try:
            _bj = json.loads(_base_run.read_text(encoding="utf-8"))
            if isinstance(_bj, dict) and _bj.get("mock"):
                mock = True
            if isinstance(_bj, dict):
                status = status or str(_bj.get("status") or "")
                partial = partial or bool(_bj.get("partial"))
        except (OSError, ValueError):
            pass
    runjson = path.with_suffix(".run.json")
    if runjson.exists():
        try:
            j = json.loads(runjson.read_text(encoding="utf-8"))
            status = str(j.get("status") or "")
            partial = bool(j.get("partial"))
            mock = bool(j.get("mock")) or mock
        except (OSError, ValueError):
            pass
    else:
        # ★ 逐层产物（`X.<层>.md`）没有 `X.<层>.run.json`，只有 `X.<层>.json`；
        #   靠它里面的 `output_name` 回指总产物的 `.run.json`，才拿得到 mock/status/partial。
        layerjson = path.with_suffix(".json")
        if layerjson.exists():
            try:
                lj = json.loads(layerjson.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                lj = {}
            if isinstance(lj, dict):
                mock = bool(lj.get("mock")) or mock
                status = status or str(lj.get("status") or "")
                oname = str(lj.get("output_name") or "")
                base_run = (OUTPUTS_DIR / (oname[:-3] + ".run.json")
                            if oname.endswith(".md") else None)
                if base_run is not None and base_run.exists():
                    try:
                        bj = json.loads(base_run.read_text(encoding="utf-8"))
                        mock = bool(bj.get("mock")) or mock
                        status = status or str(bj.get("status") or "")
                        partial = partial or bool(bj.get("partial"))
                    except (OSError, ValueError):
                        pass

    return {
        "name": path.name,
        "kind": kind,
        "layer": layer,
        "stamp": stamp,
        "title": (title or question) + ("" if kind == "md" else
                                        " · " + ("运行日志" if kind == "log" else "json")),
        "question": question,
        "time": ts,
        "mtime": st.st_mtime,
        "size": st.st_size,
        "has_packed": packed.exists(),
        "status": status,
        "partial": partial,
        "mock": mock,
        "meta": meta,
    }


def _dir_signature() -> tuple:
    if not OUTPUTS_DIR.is_dir():
        return ()
    sig = []
    try:
        for p in sorted(list(OUTPUTS_DIR.glob("*.md"))
                        + list(OUTPUTS_DIR.glob("*.run.log"))
                        + list(OUTPUTS_DIR.glob("*.json"))):
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
    seen: set = set()
    files = (list(OUTPUTS_DIR.glob("*.md"))
             + list(OUTPUTS_DIR.glob("*.run.log"))
             + [p for p in sorted(OUTPUTS_DIR.glob("*.json"))
                if not p.name.endswith(".packed.json")])
    for p in files:
        if p.name in seen:
            continue
        seen.add(p.name)
        try:
            rec = _parse_one(p)
        except OSError:
            continue
        if rec.get("mock"):
            continue          # ★ 演练/验收（mock）产物不入库
        records.append(rec)
    records.sort(key=lambda r: r["mtime"], reverse=True)
    _CACHE["key"] = sig
    _CACHE["records"] = records
    return records


_REAP_MARK = [0.0]          # 上次回收时间（限流用）


def reap_mock(max_age: float = 300.0, min_interval: float = 60.0) -> int:
    """删掉**过了保留期**的 mock（演练 / 验收）产物及其同名旁挂文件。

    用户要求「临时入库的 5 分钟后自动删除」。只动 `run.json` 里 `mock: true` 的那批，
    真跑的产物一根汗毛都不碰；带 60s 限流，别每次请求都扫盘。
    """
    now = time.time()
    if now - _REAP_MARK[0] < min_interval:
        return 0
    _REAP_MARK[0] = now
    n = 0
    for jp in OUTPUTS_DIR.glob("*.run.json"):
        try:
            meta = json.loads(jp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not (isinstance(meta, dict) and meta.get("mock")):
            continue
        try:
            if now - jp.stat().st_mtime < max_age:
                continue
        except OSError:
            continue
        stamp = jp.name[: -len(".run.json")]
        for f in OUTPUTS_DIR.glob(stamp + "*"):
            try:
                f.unlink()
                n += 1
            except OSError:
                pass
    # 再扫一遍**没有 run.json** 的产物：内容里带 mock 标记的（历史测试残留）同样按龄回收
    for md in OUTPUTS_DIR.glob("*.md"):
        try:
            if now - md.stat().st_mtime < max_age:
                continue
            head = _read_head(md)
        except OSError:
            continue
        if ("mock_engine.py" not in head and "这是 mock 产物" not in head
                and "（mock）" not in head and "(mock)" not in head):
            continue
        stamp = md.name[:-3]
        for f in OUTPUTS_DIR.glob(stamp + "*"):
            try:
                f.unlink()
                n += 1
            except OSError:
                pass
    if n:
        invalidate()
    return n


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
    # ★ R22 分类标签：kind（md/log/json）与 layer（总/修行/研究/对撞/元）
    for key, field in (("kind", "kind"), ("layer", "layer")):
        want = filters.get(key)
        if want and want != "全部" and rec.get(field) != want:
            return False
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
