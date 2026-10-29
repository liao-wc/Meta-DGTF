# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 个人工作台读数（只读）。

把散在 outputs/ 里的三类痕迹聚成「我到底跑了多少、跑得怎样」的读数：

  *.md            主产物 / 层产物（层产物 = `<stamp>.<层>.md`，一次跑会多落几份）
  *.packed.json   该轮的 `llm_calls` / `llm_tokens` / `rounds`（引擎自己记的账）
  *.run.json      通过本工作台启动的那次跑（问题 / 状态 / 耗时 / 产物名）

全部是**纯函数 + 读盘**，不写任何文件、不碰引擎主文件。

★ 覆盖率必须报出来：packed.json 与 run.json 都是「后来才加的」，历史产物
  大量缺失。宁可显示「N/M 轮有读数」，也不要拿部分当成全体去报累计值。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# 层产物的后缀（`_archive_layers` 落 <stamp>.<层>.md）
_LAYER_SUFFIX_RE = re.compile(r"\.(修行|研究|对撞|元)$")
# `20261010_125123_xxx.md` —— 主产物的一贯命名
_STAMP_RE = re.compile(r"^\d{8}_\d{6}_")
# 头部 `**停止**：自然 4 层 / 被截断（体力耗尽）0 层`
_STOP_NAT_RE = re.compile(r"自然\s*(\d+)\s*层")
_STOP_CUT_RE = re.compile(r"被截断[（(][^）)]*[）)]\s*(\d+)\s*层")

_HEADER_SCAN_BYTES = 16000

_CACHE: dict = {"key": None, "data": None}


def _read_head(path: Path, n: int = _HEADER_SCAN_BYTES) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(n)
    except OSError:
        return ""


def _sig() -> tuple:
    """目录签名：文件名 + mtime 集合，变了才重扫。"""
    if not OUTPUTS_DIR.is_dir():
        return ()
    out = []
    for pat in ("*.md", "*.packed.json", "*.run.json"):
        try:
            for p in OUTPUTS_DIR.glob(pat):
                try:
                    out.append((p.name, p.stat().st_mtime))
                except OSError:
                    pass
        except OSError:
            pass
    return tuple(sorted(out))


def classify(names: list[str]) -> tuple[list[str], list[str]]:
    """把产物文件名分成（主产物, 层产物）。层产物不单独算作「跑了一轮」。"""
    main, layer = [], []
    for n in names:
        if not n.endswith(".md"):
            continue
        stem = n[:-3]
        if _LAYER_SUFFIX_RE.search(stem):
            layer.append(n)
        elif _STAMP_RE.match(n):
            main.append(n)
    return main, layer


def parse_stop(text: str) -> dict:
    """解析头部「停止」那一行 → {'natural':n, 'cut':n, 'shallow':bool}。

    ★ 这是仓库里已有的**浅跑判据**（见 2026-10-10 记忆）：
      「被截断（体力耗尽）」= 预算耗尽被切掉，不是想清楚了才停。
    """
    m = re.search(r"\*\*停止\*\*\s*[:：]\s*(.+)", text)
    if not m:
        return {"natural": 0, "cut": 0, "shallow": False, "known": False}
    line = m.group(1)
    nat = _STOP_NAT_RE.search(line)
    cut = _STOP_CUT_RE.search(line)
    n = int(nat.group(1)) if nat else 0
    c = int(cut.group(1)) if cut else 0
    return {"natural": n, "cut": c, "shallow": c > 0, "known": True}


def sum_packed(records: list[dict]) -> dict:
    """累计 packed.json 里的调用数与 token —— **纯函数**，records 由调用方喂。

    返回值带 `covered`（有读数的轮数），前端要把它和总数一起显示。
    """
    calls = tokens = 0
    covered = 0
    for r in records:
        c, t = r.get("llm_calls"), r.get("llm_tokens")
        if c is None and t is None:
            continue
        covered += 1
        calls += int(c or 0)
        tokens += int(t or 0)
    return {"calls": calls, "tokens": tokens, "covered": covered}


def _load_packed(name: str) -> dict:
    p = OUTPUTS_DIR / Path(name).name
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _load_run(name: str) -> dict:
    p = OUTPUTS_DIR / Path(name).name
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _to_ts(v, default: float = 0.0) -> float:
    """created_at 兼容 float/字符串（历史归档可能是 'YYYY-mm-dd HH:MM:SS'）。"""
    try:
        return float(v)
    except (TypeError, ValueError):
        try:
            import time as _t
            return float(_t.mktime(_t.strptime(str(v).strip(), "%Y-%m-%d %H:%M:%S")))
        except Exception:  # noqa: BLE001
            return float(default)


def list_chats(limit: int = 80) -> list[dict]:
    """历次「会话」= 一次提交，按时间倒序；给「历史对话」用（只读）。

    两个来源合并、按 output_name / id 去重：
      · `outputs/*.run.json` 归档 —— **服务重启后仍在**（历史对话靠它不丢）；
      · 内存里的任务（`engine_runner.list_tasks()`）—— 有实时日志、可继续跟随，
        同一条会**覆盖**归档那份并把 `live` 置 True。
    """
    chats: dict[str, dict] = {}

    # ① 归档（先铺底）
    for jp in OUTPUTS_DIR.glob("*.run.json"):
        stamp = jp.name[: -len(".run.json")]
        meta = _load_run(jp.name)
        if not meta:
            continue
        out = str(meta.get("output_name") or "")
        chats[out or stamp] = {
            "id": str(meta.get("id") or stamp),
            "question": str(meta.get("question") or stamp),
            "status": str(meta.get("status") or ""),
            "partial": bool(meta.get("partial")),
            "mock": bool(meta.get("mock")),
            "created_at": _to_ts(meta.get("created_at")),
            "started_at": meta.get("started_at"),
            "ended_at": meta.get("ended_at"),
            "output_name": out,
            # ★ 中断/失败的任务要能**看到原因**（用户明确要求「标注状态原因」）。
            "error": str(meta.get("error") or ""),
            "duration_sec": meta.get("duration_sec"),
            "archive_log": f"{stamp}.run.log",
            "archive_json": jp.name,
            "live": False,
        }

    # ② 内存里的任务（活的那份覆盖归档）
    try:
        import engine_runner as _R          # 延迟导入：避免与 server 的启动顺序纠缠
        for t in _R.list_tasks():
            out = str(t.get("output_name") or "")
            key = out or str(t.get("id") or "")
            if not key:
                continue
            row = chats.get(key) or {"archive_log": "", "archive_json": ""}
            row.update({
                "id": str(t.get("id") or key),
                "question": str(t.get("question") or ""),
                "status": str(t.get("status") or ""),
                "partial": bool(t.get("partial")),
                "mock": bool(t.get("mock")),
                "created_at": float(t.get("created_at") or 0.0),
                "started_at": t.get("started_at"),
                "ended_at": t.get("ended_at"),
                "output_name": out,
                "error": str(t.get("error") or ""),
                "duration_sec": (round(t["ended_at"] - t["started_at"], 1)
                                 if t.get("started_at") and t.get("ended_at") else None),
                "live": True,
            })
            chats[key] = row
    except Exception:  # noqa: BLE001   读不到内存任务不影响归档那部分
        pass

    rows = sorted(chats.values(),
                  key=lambda r: r.get("created_at") or 0.0, reverse=True)
    return rows[:limit]


def scan(force: bool = False) -> dict:
    """全量读数。带缓存（目录签名不变就复用）。"""
    key = _sig()
    if not force and _CACHE["key"] == key and _CACHE["data"]:
        return _CACHE["data"]

    mds: list[tuple[str, float]] = []
    packs: list[str] = []
    runs: list[str] = []
    if OUTPUTS_DIR.is_dir():
        try:
            for p in OUTPUTS_DIR.glob("*.md"):
                try:
                    mds.append((p.name, p.stat().st_mtime))
                except OSError:
                    pass
            packs = sorted(x.name for x in OUTPUTS_DIR.glob("*.packed.json"))
            runs = sorted(x.name for x in OUTPUTS_DIR.glob("*.run.json"))
        except OSError:
            pass

    main, layer = classify([n for n, _ in mds])
    mtime = dict(mds)
    now = time.time()

    # 主产物按时间倒序 + 最近窗口内的轮数
    main_sorted = sorted(main, key=lambda n: mtime.get(n, 0), reverse=True)
    d7 = sum(1 for n in main if now - mtime.get(n, 0) <= 7 * 86400)
    d30 = sum(1 for n in main if now - mtime.get(n, 0) <= 30 * 86400)

    # 停止判据：只看有该字段的主产物，覆盖率单报
    stop_known = stop_shallow = 0
    for n in main_sorted:
        s = parse_stop(_read_head(OUTPUTS_DIR / n))
        if s["known"]:
            stop_known += 1
            if s["shallow"]:
                stop_shallow += 1

    packed_recs = []
    for n in packs:
        d = _load_packed(n)
        if d:
            packed_recs.append(d)

    hist = []
    for n in runs:
        d = _load_run(n)
        if not d:
            continue
        hist.append({
            "id": d.get("id", ""),
            "question": d.get("question", ""),
            "status": d.get("status", ""),
            "mock": bool(d.get("mock")),
            "engine": d.get("engine", ""),
            "duration_sec": d.get("duration_sec"),
            "ended_at": d.get("ended_at"),
            "output_name": d.get("output_name"),
            "error": d.get("error", ""),
        })
    hist.sort(key=lambda r: r.get("ended_at") or 0, reverse=True)

    total_bytes = 0
    for n, _ in mds:
        try:
            total_bytes += (OUTPUTS_DIR / n).stat().st_size
        except OSError:
            pass

    data = {
        "counts": {
            "main": len(main),
            "layer": len(layer),
            "total_files": len(mds),
            "total_mb": round(total_bytes / 1024 / 1024, 1),
            "d7": d7,
            "d30": d30,
        },
        "packed": sum_packed(packed_recs),
        "stop": {
            "known": stop_known,
            "shallow": stop_shallow,
            "natural": stop_known - stop_shallow,
        },
        "history": hist[:20],
        "latest": [
            {"name": n, "mtime": mtime.get(n, 0)} for n in main_sorted[:8]
        ],
    }
    _CACHE["key"] = key
    _CACHE["data"] = data
    return data


def invalidate() -> None:
    _CACHE["key"] = None
    _CACHE["data"] = None


if __name__ == "__main__":
    print(json.dumps(scan(), ensure_ascii=False, indent=2)[:2000])
