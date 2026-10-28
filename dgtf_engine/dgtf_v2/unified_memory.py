# -*- coding: utf-8 -*-
"""统一记忆读写：V1 playbook（playbook.jsonl）+ V2 EML events（v2_events.jsonl）。

定位：知识面只出**数值先验**，不读答案正文。
  · read_priors()   ：把 V1 playbook 的 active 条目与 V2 的 schedule_outcome
                      合并成同一份先验；跨源按 (run_id, template) 去重。
  · record_outcome()：把跑次读数写成 V2 事件；可选镜像一条 V1 兼容的
                      playbook 记录（默认不写，避免污染引擎自有文件）。
  · 无答案正文      ：payload/extra 里出现 answer/decision/rendered/text… 直接拒绝；
                      template 必须是短代码（禁止把长文本塞进模板位）。
  · 测试隔离        ：写入生产目录（dgtf_memory/）必须显式 allow_production=True；
                      测试用 for_tests(tmp) / from_records(...)。
纯确定性：不调 LLM、不联网、不读系统时钟、不用随机数。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from .memory import Event, MemoryLake

ROOT = Path(__file__).resolve().parents[1]
PROD_MEMORY_DIR = (ROOT / "dgtf_memory").resolve()
V2_EVENTS_FILE = "v2_events.jsonl"
V1_PLAYBOOK_FILE = "playbook.jsonl"

# 答案正文类字段：只认键名（宁严勿松），命中即拒写。
FORBIDDEN_KEYS = frozenset({
    "answer", "answer_text", "final_answer", "decision", "decision_text",
    "rendered", "output", "output_text", "claim", "claims", "content",
    "text", "text_body", "manifest", "manifest_text", "synthesis",
})
TEMPLATE_RE = re.compile(r"^[0-9A-Za-z_:.\-]{1,64}$")
TEST_RUN_PREFIXES = ("E2E_", "test", "smoke", "pytest", "v2-", "probe", "anon")


# ── JSONL 读写（容错：坏行跳过并计数，不中断）────────────────
def _read_jsonl(path: Optional[Path]) -> tuple[list, int]:
    rows: list = []
    bad = 0
    if path is None or not Path(path).exists():
        return rows, bad
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return rows, bad
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            bad += 1
            continue
        if isinstance(obj, dict):
            rows.append(obj)
        else:
            bad += 1
    return rows, bad


def _append_jsonl(path: Path, row: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _scan_forbidden(obj: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = ("%s.%s" % (path, k)) if path else str(k)
            if str(k).lower() in FORBIDDEN_KEYS:
                found.append(p)
            found.extend(_scan_forbidden(v, p))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            found.extend(_scan_forbidden(v, "%s[%d]" % (path, i)))
    return found


def _mean(xs: list) -> float:
    return (sum(float(x) for x in xs) / len(xs)) if xs else 0.0


def _is_production(path: Optional[Path]) -> bool:
    if path is None:
        return False
    try:
        p = Path(path).resolve()
    except OSError:
        return False
    try:
        return p == PROD_MEMORY_DIR or PROD_MEMORY_DIR in p.parents
    except (TypeError, ValueError):
        return False


def _num(x: Any, *, name: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError("读数 %s 必须是数值，收到 %r" % (name, x))
    v = float(x)
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError("读数 %s 必须是有限数值" % name)
    return v


# ── 统一记忆 ────────────────────────────────────────────────
class UnifiedMemory:
    """V1 playbook + V2 EML 的统一门面（数值先验 / 读数写入 / 去重 / 隔离）。"""

    VERSION = "unified_memory/v1"

    def __init__(self, *, v2_events_path: Optional[str | Path] = None,
                 playbook_path: Optional[str | Path] = None,
                 enabled: bool = True, allow_production: bool = False,
                 allow_anon: bool = True, load: bool = True,
                 persist: bool = True):
        self.enabled = bool(enabled)
        self.allow_production = bool(allow_production)
        self.allow_anon = bool(allow_anon)
        # persist=False ⇒ 纯内存（不落盘；from_records 用）。
        # 否则默认路径 = 生产记忆库；测试请显式传 tmp 路径（见 for_tests）。
        self.v2_events_path: Optional[Path] = (
            Path(v2_events_path) if v2_events_path is not None
            else ((PROD_MEMORY_DIR / V2_EVENTS_FILE)
                  if (self.enabled and persist) else None))
        self.playbook_path: Optional[Path] = (
            Path(playbook_path) if playbook_path is not None
            else ((PROD_MEMORY_DIR / V1_PLAYBOOK_FILE)
                  if (self.enabled and persist) else None))
        self._lake = MemoryLake(None)
        self._playbook: list = []
        self._bad_v2 = 0
        self._bad_v1 = 0
        if load:
            self._load()

    # ── 构造器（测试用）─────────────────────────────────────
    @classmethod
    def for_tests(cls, tmpdir: str | Path, **kwargs) -> "UnifiedMemory":
        """测试隔离：所有读写都落在 tmpdir，绝不碰生产目录。"""
        base = Path(tmpdir)
        kwargs.setdefault("allow_anon", True)
        return cls(v2_events_path=base / V2_EVENTS_FILE,
                   playbook_path=base / V1_PLAYBOOK_FILE,
                   enabled=True, allow_production=False, **kwargs)

    @classmethod
    def from_records(cls, *, v2_events: Optional[list] = None,
                     playbook: Optional[list] = None,
                     enabled: bool = True, allow_anon: bool = True,
                     allow_production: bool = False) -> "UnifiedMemory":
        """无文件模式：直接注入记录（单测/回放用）。"""
        mem = cls(v2_events_path=None, playbook_path=None,
                  enabled=bool(enabled), allow_production=allow_production,
                  allow_anon=allow_anon, load=False, persist=False)
        mem._inject_events(v2_events or [])
        mem._playbook = [dict(x) for x in (playbook or [])
                         if isinstance(x, dict)]
        return mem

    def _inject_events(self, rows: list) -> None:
        for row in rows or []:
            try:
                ev = Event.from_dict(dict(row))
            except (TypeError, ValueError):
                self._bad_v2 += 1
                continue
            self._lake.events.append(ev)
            try:
                self._lake._seq = max(self._lake._seq,
                                      int(str(ev.id).split("-")[-1]))
            except (TypeError, ValueError):
                pass
            self._lake._clock = max(self._lake._clock, ev.tx_time,
                                    ev.ingest_time)

    # ── 装载 ────────────────────────────────────────────────
    def _load(self) -> None:
        rows, bad = _read_jsonl(self.v2_events_path)
        self._bad_v2 = int(bad)
        self._inject_events(rows)
        pb, bad2 = _read_jsonl(self.playbook_path)
        self._bad_v1 = int(bad2)
        self._playbook = [r for r in pb if isinstance(r, dict)]

    def reload(self) -> dict:
        self._lake = MemoryLake(None)
        self._playbook = []
        self._load()
        return self.stats()

    # ── 写保护 ──────────────────────────────────────────────
    def _guard_write(self, path: Optional[Path]) -> None:
        if path is None:
            return
        if _is_production(path) and not self.allow_production:
            raise PermissionError(
                "拒绝写入生产记忆库（%s）。测试请用 for_tests(tmp)/from_records；"
                "确需生产写入请显式 allow_production=True。" % path)

    # ── 读数写入 ────────────────────────────────────────────
    def record_outcome(self, *, run_id: str, template: str, quality: float,
                       calls: int, tokens: int, success: bool,
                       mirror_playbook: bool = False,
                       extra: Optional[dict] = None) -> dict:
        """记录一次排程读数：写 V2 事件；mirror_playbook=True 时再写 V1 兼容条目。

        只接受数值读数；template 必须是短代码；任何答案正文类字段直接拒绝。
        """
        if not self.enabled:
            return {"enabled": False, "recorded": False, "deduped": False,
                    "contains_content": False}
        run_id = str(run_id or "")
        tmpl = str(template or "")
        if not TEMPLATE_RE.match(tmpl):
            raise ValueError(
                "template 必须是短代码（^[0-9A-Za-z_:.-]{1,64}$），"
                "不得写入长文本/答案正文：%r" % tmpl[:40])
        if not run_id:
            raise ValueError("run_id 不能为空")
        if not self.allow_anon and any(
                run_id.lower().startswith(p.lower()) for p in TEST_RUN_PREFIXES):
            return {"enabled": True, "recorded": False, "skipped": "anon",
                    "why": "测试/匿名 run 不写生产记忆：%s" % run_id,
                    "contains_content": False}
        q = _num(quality, name="quality")
        c = _num(calls, name="calls")
        t = _num(tokens, name="tokens")
        if extra is not None:
            if not isinstance(extra, dict):
                raise ValueError("extra 必须是 dict")
            bad = _scan_forbidden(extra)
            if bad:
                raise ValueError("禁止写入答案正文类字段：%s" % ",".join(bad[:4]))

        rows, _meta = self._outcome_rows()
        key = self._dedup_key(run_id, tmpl)
        if any(self._dedup_key(r["run_id"], r["template"]) == key for r in rows):
            return {"enabled": True, "recorded": False, "deduped": True,
                    "run_id": run_id, "template": tmpl,
                    "why": "同一 (run_id, template) 已在记忆库中",
                    "contains_content": False}

        payload = {"template": tmpl, "quality": round(q, 4),
                   "calls": int(round(c)), "tokens": int(round(t)),
                   "success": bool(success)}
        if extra:
            # 只追加已校验的结构读数；不覆盖 quality/template 等核心字段。
            for _k, _v in extra.items():
                if _k not in payload:
                    payload[_k] = _v
        ev = self._lake.append(
            run_id=run_id, plane="procedural", layer="scheduler",
            kind="schedule_outcome", key="schedule:" + tmpl,
            payload=payload,
            provenance=["unified_memory"], confidence=0.6)
        written = ["v2_events"]
        self._guard_write(self.v2_events_path)
        if self.v2_events_path is not None:
            _append_jsonl(self.v2_events_path, ev.to_dict())
        if mirror_playbook:
            self._guard_write(self.playbook_path)
            entry = self._playbook_entry(run_id=run_id, template=tmpl,
                                         quality=q, calls=c, tokens=t,
                                         success=success)
            if self.playbook_path is not None:
                _append_jsonl(self.playbook_path, entry)
            self._playbook.append(entry)
            written.append("v1_playbook")
        return {"enabled": True, "recorded": True, "deduped": False,
                "run_id": run_id, "template": tmpl, "sources": written,
                "contains_content": False,
                "stats": self.stats()}

    def _playbook_entry(self, *, run_id: str, template: str, quality: float,
                        calls: float, tokens: float, success: bool) -> dict:
        return {
            "id": "U%04d" % (len(self._playbook) + 1),
            "kind": "schedule_outcome",
            "cond": {"run_id": run_id, "template": template},
            "action": {"key": template},
            "readings": {"before": 0.0, "quality": round(quality, 4),
                         "calls": int(round(calls)),
                         "tokens": int(round(tokens)),
                         "success": bool(success)},
            "why": "numeric schedule outcome (unified_memory)",
            "evidence": [run_id], "n_evidence": 1,
            "status": "shadow", "weight": 1.0, "contra": 0,
            "t_written": 0.0, "t_last": 0.0, "t_used": [],
            "source": "unified_memory",
            "cost_delta": 0.0, "quality_delta": 0.0,
        }

    # ── 读数读取 / 去重 ─────────────────────────────────────
    def _dedup_key(self, run_id: str, template: str) -> tuple:
        rid = str(run_id or "")
        tpl = str(template or "")
        if rid and tpl:
            return (rid, tpl)
        return ("?", tpl, rid)

    def _outcome_rows(self) -> tuple[list[dict], dict]:
        rows: list[dict] = []
        for e in self._lake.events:
            if e.plane != "procedural" or e.kind != "schedule_outcome":
                continue
            p = dict(e.payload or {})
            tmpl = str(p.get("template") or "")
            if not tmpl:
                continue
            rows.append({
                "source": "v2", "run_id": str(e.run_id or ""),
                "template": tmpl,
                "quality": _safe_float(p.get("quality")),
                "calls": _safe_int(p.get("calls")),
                "tokens": _safe_int(p.get("tokens")),
                "success": bool(p.get("success")),
                "ref": str(e.id),
            })
        for ent in self._playbook:
            if not isinstance(ent, dict):
                continue
            if str(ent.get("kind") or "") != "schedule_outcome":
                continue
            cond = ent.get("cond") or {}
            act = ent.get("action") or {}
            rd = ent.get("readings") or {}
            tmpl = str(cond.get("template") or act.get("key") or "")
            if not tmpl:
                continue
            ev = ent.get("evidence") or []
            rid = str(cond.get("run_id") or (ev[0] if ev else "") or "")
            rows.append({
                "source": "v1", "run_id": rid, "template": tmpl,
                "quality": _safe_float(rd.get("quality")),
                "calls": _safe_int(rd.get("calls")),
                "tokens": _safe_int(rd.get("tokens")),
                "success": bool(rd.get("success")),
                "ref": str(ent.get("id") or ""),
            })
        dedup: dict = {}
        duplicates = 0
        conflicts = 0
        for r in rows:
            key = self._dedup_key(r["run_id"], r["template"])
            cur = dedup.get(key)
            if cur is None:
                dedup[key] = r
                continue
            duplicates += 1
            if cur["source"] != "v2" and r["source"] == "v2":
                dedup[key] = r
            elif (cur["quality"] != r["quality"]
                  or cur["calls"] != r["calls"]
                  or cur["tokens"] != r["tokens"]):
                conflicts += 1
        out = sorted(dedup.values(),
                     key=lambda r: (r["template"], r["run_id"]))
        meta = {"rows_raw": len(rows), "rows_deduped": len(out),
                "duplicates_dropped": duplicates, "conflicts": conflicts}
        return out, meta

    def scheduler_priors(self) -> dict:
        """Scheduler 兼容别名：统一先验（数值，无正文）。"""
        return self.read_priors()

    def read_priors(self) -> dict:
        """统一先验：只有数值，绝不含答案正文（contains_content 恒 False）。"""
        rows, meta = self._outcome_rows()
        templates: dict[str, dict] = {}
        for r in rows:
            t = templates.setdefault(r["template"], {
                "n": 0, "success_n": 0, "sum_quality": 0.0,
                "sum_calls": 0.0, "sum_tokens": 0.0, "sources": set()})
            t["n"] += 1
            t["success_n"] += 1 if r["success"] else 0
            t["sum_quality"] += r["quality"]
            t["sum_calls"] += r["calls"]
            t["sum_tokens"] += r["tokens"]
            t["sources"].add(r["source"])
        out_tpl: dict[str, dict] = {}
        for k in sorted(templates):
            t = templates[k]
            n = max(1, t["n"])
            out_tpl[k] = {
                "mean_success": round(t["success_n"] / n, 4),
                "n": t["n"],
                "mean_calls": round(t["sum_calls"] / n, 3),
                "mean_tokens": round(t["sum_tokens"] / n, 3),
                "mean_quality": round(t["sum_quality"] / n, 4),
                "sources": sorted(t["sources"]),
            }

        # V1 playbook active 条目 → 动作键级先验（只数值）
        agg: dict[str, dict] = {}
        active = 0
        for ent in self._playbook:
            if not isinstance(ent, dict) or ent.get("status") != "active":
                continue
            key = str((ent.get("action") or {}).get("key") or "")
            if not key or not TEMPLATE_RE.match(key):
                continue
            active += 1
            row = agg.setdefault(key, {"n": 0, "ev": [], "w": [],
                                       "qd": [], "cd": []})
            row["n"] += 1
            row["ev"].append(_safe_float(ent.get("n_evidence")))
            row["w"].append(_safe_float(ent.get("weight"), 1.0))
            row["qd"].append(_safe_float(ent.get("quality_delta")))
            row["cd"].append(_safe_float(ent.get("cost_delta")))
        out_pb: dict[str, dict] = {}
        for k in sorted(agg):
            row = agg[k]
            out_pb[k] = {"n": row["n"],
                         "mean_evidence": round(_mean(row["ev"]), 3),
                         "mean_weight": round(_mean(row["w"]), 3),
                         "mean_quality_delta": round(_mean(row["qd"]), 4),
                         "mean_cost_delta": round(_mean(row["cd"]), 4)}
        priors = {
            "version": self.VERSION,
            "source": "unified",
            "templates": out_tpl,
            "playbook": out_pb,
            "sources": {"v2_events": len(self._lake.events),
                        "v1_playbook": len(self._playbook),
                        "v1_active": active,
                        "outcomes_raw": meta["rows_raw"]},
            "dedup": meta,
            "n_events": len(self._lake.events),
            "contains_content": False,
            "enabled": self.enabled,
        }
        return priors

    def stats(self) -> dict:
        rows, meta = self._outcome_rows()
        return {"version": self.VERSION,
                "enabled": self.enabled,
                "v2_events": len(self._lake.events),
                "v1_playbook": len(self._playbook),
                "skipped_v2_lines": self._bad_v2,
                "skipped_v1_lines": self._bad_v1,
                "outcome_rows": len(rows),
                "dedup": meta,
                "v2_events_path": str(self.v2_events_path or ""),
                "playbook_path": str(self.playbook_path or ""),
                "allow_production": self.allow_production,
                "contains_content": False}


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    if v != v or v in (float("inf"), float("-inf")):
        return default
    return v


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(round(float(x)))
    except (TypeError, ValueError):
        return default
