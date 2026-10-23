# -*- coding: utf-8 -*-
"""EML v2：双时态、事件溯源、带论证状态与不确定性的记忆湖。

它是 V2 三平面架构里的「知识面」：
  · 只提供**调度先验**（priors）与可追溯证据，不提供答案内容；
  · 事件不可变，修正/击败都是追加（bitemporal + event sourcing）；
  · 检索用 BM25 + 词面近邻 + 时近/置信/tier 的 RRF，再用 MMR 去冗余；
  · 冲突用 Dung 风格的 defeated/undecided 标签保留，不删行。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional


def _tokens(text: str) -> list[str]:
    s = str(text or "").lower()
    out = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", s)
    # 中文二元组：单字粒度太碎，二元组对短语更稳。
    zh = [ch for ch in s if "\u4e00" <= ch <= "\u9fff"]
    out.extend("".join(zh[i:i + 2]) for i in range(len(zh) - 1))
    return out


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Event:
    id: str
    run_id: str
    plane: str                 # episodic / semantic / procedural
    layer: str
    kind: str
    key: str
    payload: dict
    event_time: float
    ingest_time: float
    valid_from: float
    valid_to: Optional[float]
    tx_time: float
    provenance: list[str] = field(default_factory=list)
    confidence: float = 0.5
    support: list[str] = field(default_factory=list)
    defeaters: list[str] = field(default_factory=list)
    supersedes: Optional[str] = None

    def text(self) -> str:
        return self.key + " " + json.dumps(self.payload, ensure_ascii=False,
                                           sort_keys=True)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(**d)


class MemoryLake:
    """事件溯源记忆湖；逻辑时钟保证双时态查询可复现。"""

    def __init__(self, path: Optional[str | Path] = None):
        self.events: list[Event] = []
        self.path = Path(path) if path else None
        self._clock = 0.0
        self._seq = 0
        if self.path and self.path.exists():
            self.load(self.path)

    # ── 时钟 / 追加 ────────────────────────────────────────────
    def tick(self, dt: float = 1.0) -> float:
        self._clock += float(dt)
        return self._clock

    def now(self) -> float:
        return self._clock

    def append(self, *, run_id: str, plane: str, layer: str, kind: str,
               key: str, payload: dict, event_time: Optional[float] = None,
               valid_from: Optional[float] = None,
               valid_to: Optional[float] = None,
               provenance: Optional[Iterable[str]] = None,
               confidence: float = 0.5,
               support: Optional[Iterable[str]] = None,
               defeaters: Optional[Iterable[str]] = None,
               supersedes: Optional[str] = None) -> Event:
        self._seq += 1
        t = self.tick()
        ev = Event(
            id="evt-%06d" % self._seq,
            run_id=str(run_id),
            plane=str(plane),
            layer=str(layer),
            kind=str(kind),
            key=str(key),
            payload=dict(payload or {}),
            event_time=float(event_time if event_time is not None else t),
            ingest_time=t,
            valid_from=float(valid_from if valid_from is not None else t),
            valid_to=(float(valid_to) if valid_to is not None else None),
            tx_time=t,
            provenance=list(provenance or []),
            confidence=max(0.0, min(1.0, float(confidence))),
            support=list(support or []),
            defeaters=list(defeaters or []),
            supersedes=supersedes,
        )
        self.events.append(ev)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")
        return ev

    # ── 双时态查询 ────────────────────────────────────────────
    def as_of(self, tx_time: float) -> list[Event]:
        return [e for e in self.events if e.tx_time <= float(tx_time)]

    def _latest(self, events: list[Event],
                cutoff: Optional[float] = None) -> dict[str, Event]:
        cut = self._clock if cutoff is None else float(cutoff)
        out: dict[str, Event] = {}
        for e in sorted(events, key=lambda x: (x.tx_time, x.id)):
            if e.plane != "semantic":
                continue
            if e.valid_to is not None and e.valid_to <= cut:
                continue
            out[e.key] = e
        return out

    def beliefs(self, as_of: Optional[float] = None,
                include_defeated: bool = False) -> dict[str, Event]:
        evs = self.as_of(as_of) if as_of is not None else list(self.events)
        out = self._latest(evs, as_of if as_of is not None else self._clock)
        if not include_defeated:
            out = {k: v for k, v in out.items() if not v.defeaters}
        return out

    # ── 修正 / 支持 / 击败（追加，不删）──────────────────────
    def revise(self, key: str, payload: dict, *, run_id: str, layer: str,
               reason: str = "", provenance: Optional[Iterable[str]] = None,
               confidence: float = 0.7) -> Event:
        cur = self.beliefs(include_defeated=True).get(key)
        return self.append(
            run_id=run_id, plane="semantic", layer=layer, kind="revision",
            key=key, payload=payload, provenance=provenance,
            confidence=confidence, supersedes=(cur.id if cur else None),
        )

    def support(self, key: str, by: str, *, run_id: str, layer: str = "1",
                delta: float = 0.05) -> Event:
        cur = self.beliefs(include_defeated=True).get(key)
        if cur is None:
            raise KeyError("未知信念：" + key)
        return self.append(
            run_id=run_id, plane="semantic", layer=layer, kind="support",
            key=key, payload=dict(cur.payload),
            provenance=list(cur.provenance) + [by],
            confidence=min(1.0, cur.confidence + float(delta)),
            support=list(cur.support) + [by],
            defeaters=list(cur.defeaters),
            supersedes=cur.id,
        )

    def defeat(self, key: str, by: str, *, run_id: str, layer: str = "both",
               reason: str = "") -> Event:
        cur = self.beliefs(include_defeated=True).get(key)
        if cur is None:
            raise KeyError("未知信念：" + key)
        return self.append(
            run_id=run_id, plane="semantic", layer=layer, kind="defeat",
            key=key, payload=dict(cur.payload),
            provenance=list(cur.provenance),
            confidence=max(0.0, cur.confidence - 0.2),
            support=list(cur.support),
            defeaters=list(cur.defeaters) + [by],
            supersedes=cur.id,
        )

    # ── 检索：BM25 + 时近 + tier + RRF + MMR ─────────────────
    def retrieve(self, query: str, k: int = 8,
                 as_of: Optional[float] = None,
                 trust_floor: float = 0.0) -> list[dict]:
        beliefs = self.beliefs(as_of=as_of, include_defeated=False)
        docs = list(beliefs.values())
        docs += [e for e in (self.as_of(as_of) if as_of is not None
                             else self.events)
                 if e.plane == "episodic"][-40:]
        if not docs:
            return []
        q = set(_tokens(query))
        toks = [set(_tokens(d.text())) for d in docs]
        n = len(docs)
        df: dict[str, int] = {}
        for ts in toks:
            for t in ts:
                df[t] = df.get(t, 0) + 1
        avgdl = sum(len(t) for t in toks) / max(1, n)
        bm25: list[float] = []
        for d, ts in zip(docs, toks):
            dl = len(ts)
            s = 0.0
            for t in q:
                if t not in ts:
                    continue
                idf = math.log(1 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
                tf = sum(1 for x in _tokens(d.text()) if x == t)
                s += idf * (tf * 2.5) / (tf + 1.5 * (0.25 + 0.75 * dl / max(1.0, avgdl)))
            bm25.append(s)
        rec = []
        trust = []
        for d in docs:
            age = max(0.0, self._clock - d.valid_from)
            rec.append(1.0 / (1.0 + age / 100.0))
            tier = d.payload.get("tier") if isinstance(d.payload, dict) else None
            try:
                trust.append(1.0 / max(1.0, float(tier)))
            except (TypeError, ValueError):
                trust.append(0.5)
        def _rank(vals: list[float]) -> list[int]:
            order = sorted(range(n), key=lambda i: -vals[i])
            r = [0] * n
            for pos, i in enumerate(order, 1):
                r[i] = pos
            return r
        rb, rr, rt = _rank(bm25), _rank(rec), _rank(trust)
        fused = [1.0 / (60 + rb[i]) + 1.0 / (60 + rr[i]) + 1.0 / (60 + rt[i])
                 for i in range(n)]
        order = sorted(range(n), key=lambda i: -fused[i])
        # MMR：先取最高分，再在「相关 - 重复」之间折中。
        chosen: list[int] = []
        while order and len(chosen) < k:
            best_i = None
            best_v = -1e9
            for i in order:
                if i in chosen:
                    continue
                rel = fused[i]
                dup = max([_jaccard(toks[i], toks[j]) for j in chosen] or [0.0])
                v = 0.7 * rel - 0.3 * dup
                if v > best_v:
                    best_v, best_i = v, i
            if best_i is None:
                break
            chosen.append(best_i)
            order.remove(best_i)
        out = []
        for i in chosen:
            d = docs[i]
            out.append({
                "id": d.id, "key": d.key, "payload": dict(d.payload),
                "score": round(fused[i], 6), "confidence": d.confidence,
                "trust": round(trust[i], 3),
                "defeated": bool(d.defeaters),
                "provenance": list(d.provenance),
                "plane": d.plane,
            })
        return [x for x in out if x["trust"] >= float(trust_floor)]

    # ── 巩固 / 遗忘 / 调度先验 ────────────────────────────────
    def consolidate(self, run_id: str, min_support: int = 2) -> list[Event]:
        groups: dict[str, list[Event]] = {}
        for e in self.events:
            if e.run_id == run_id and e.plane == "episodic":
                groups.setdefault(e.key, []).append(e)
        made: list[Event] = []
        for key, evs in groups.items():
            if len(evs) < min_support:
                continue
            texts = [e.text() for e in evs]
            toks = [set(_tokens(t)) for t in texts]
            sim = 0.0
            pairs = 0
            for i in range(len(toks)):
                for j in range(i + 1, len(toks)):
                    sim += _jaccard(toks[i], toks[j])
                    pairs += 1
            sim = sim / max(1, pairs)
            surprise = 1.0 - sim
            retention = math.exp(-max(0.0, self._clock - evs[-1].valid_from) / 1000.0)
            made.append(self.append(
                run_id=run_id, plane="semantic", layer=evs[-1].layer,
                kind="consolidation", key=key,
                payload={"kind": "macro", "support_n": len(evs),
                         "surprise": round(surprise, 4),
                         "retention": round(retention, 4)},
                provenance=[e.id for e in evs],
                confidence=min(0.95, 0.4 + 0.1 * len(evs)),
                support=[e.id for e in evs],
            ))
        return made

    def scheduler_priors(self) -> dict:
        """只返回数值先验；绝不把 claim/answer 文本交给调度器。"""
        agg: dict[str, dict] = {}
        for e in self.events:
            if e.plane != "procedural" or e.kind != "schedule_outcome":
                continue
            tpl = str(e.payload.get("template") or "")
            if not tpl:
                continue
            row = agg.setdefault(tpl, {"alpha": 1.0, "beta": 1.0,
                                       "calls": [], "tokens": [],
                                       "quality": []})
            try:
                row["alpha"] += 1.0 if e.payload.get("success") else 0.0
                row["beta"] += 0.0 if e.payload.get("success") else 1.0
                row["calls"].append(float(e.payload.get("calls") or 0))
                row["tokens"].append(float(e.payload.get("tokens") or 0))
                row["quality"].append(float(e.payload.get("quality") or 0))
            except (TypeError, ValueError):
                pass
        out_tpl: dict[str, dict] = {}
        for k, v in agg.items():
            n = max(1, len(v["quality"]))
            out_tpl[k] = {
                "mean_success": round(v["alpha"] / (v["alpha"] + v["beta"]), 4),
                "n": n,
                "mean_calls": round(sum(v["calls"]) / max(1, len(v["calls"])), 3),
                "mean_tokens": round(sum(v["tokens"]) / max(1, len(v["tokens"])), 3),
                "mean_quality": round(sum(v["quality"]) / max(1, len(v["quality"])), 4),
            }
        return {"templates": out_tpl, "n_events": len(self.events),
                "source": "eml", "contains_content": False}

    def record_outcome(self, *, run_id: str, template: str, quality: float,
                       calls: int, tokens: int, success: bool) -> Event:
        return self.append(
            run_id=run_id, plane="procedural", layer="scheduler",
            kind="schedule_outcome", key="schedule:" + template,
            payload={"template": template, "quality": float(quality),
                     "calls": int(calls), "tokens": int(tokens),
                     "success": bool(success)},
            confidence=0.6,
        )

    def forget(self, now: Optional[float] = None,
               half_life: float = 2000.0) -> list[dict]:
        t = self._clock if now is None else float(now)
        out = []
        for key, e in self.beliefs(include_defeated=True).items():
            age = max(0.0, t - e.valid_from)
            retention = math.exp(-math.log(2) * age / max(1.0, half_life))
            if retention < 0.35:
                out.append({"key": key, "retention": round(retention, 4),
                            "defeated": bool(e.defeaters)})
        return out

    def stats(self) -> dict:
        by_plane: dict[str, int] = {}
        for e in self.events:
            by_plane[e.plane] = by_plane.get(e.plane, 0) + 1
        return {"events": len(self.events), "by_plane": by_plane,
                "beliefs": len(self.beliefs(include_defeated=True)),
                "active_beliefs": len(self.beliefs()),
                "clock": self._clock}

    # ── 持久化 ────────────────────────────────────────────────
    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            for e in self.events:
                f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")

    def load(self, path: str | Path) -> None:
        p = Path(path)
        if not p.exists():
            return
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = Event.from_dict(json.loads(line))
            self.events.append(e)
            self._seq = max(self._seq, int(str(e.id).split("-")[-1]))
            self._clock = max(self._clock, e.tx_time, e.ingest_time)
