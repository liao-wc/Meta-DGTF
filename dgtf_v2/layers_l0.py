# -*- coding: utf-8 -*-
"""Phase 5 · L0-v2：修行层的质量-多样性机制。

不生成内容；对 0 层候选做：
  · MAP-Elites 档案（polarity × 关键词桶，每格保留最优）；
  · novelty = 1 - 与档案最近邻的 token Jaccard；
  · Heaps 饱和 + novelty stall 的停止读数；
  · Thompson sampling 选探针（Beta 后验）。
先作为独立内核回放真实 packed，验证有判别力后再接引擎 flag。
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path


def tokens(text: str) -> set[str]:
    s = str(text or "").lower()
    out = set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", s))
    zh = [c for c in s if "\u4e00" <= c <= "\u9fff"]
    out |= {"".join(zh[i:i + 2]) for i in range(len(zh) - 1)}
    return out


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a and b) else 0.0


def _bucket(desc: str, n_buckets: int = 12) -> str:
    ts = sorted(tokens(desc), key=lambda x: (-len(x), x))
    if not ts:
        return "other"
    h = hashlib.md5(ts[0].encode("utf-8")).hexdigest()
    return "b%02d" % (int(h[:8], 16) % n_buckets)


@dataclass
class Elite:
    desc: str
    polarity: str
    score: float
    cell: str


class MapElitesArchive:
    def __init__(self, capacity: int = 32, n_buckets: int = 12):
        self.capacity = int(capacity)
        self.n_buckets = int(n_buckets)
        self.cells: dict[str, Elite] = {}
        self._toks: dict[str, set] = {}

    def cell_of(self, desc: str, polarity: str) -> str:
        return "%s|%s" % (str(polarity or "?"), _bucket(desc, self.n_buckets))

    def novelty(self, desc: str) -> float:
        t = tokens(desc)
        if not self._toks:
            return 1.0
        return 1.0 - max(jaccard(t, x) for x in self._toks.values())

    def add(self, desc: str, polarity: str, score: float) -> bool:
        cell = self.cell_of(desc, polarity)
        cur = self.cells.get(cell)
        if cur is not None and float(score) <= cur.score:
            return False
        self.cells[cell] = Elite(str(desc), str(polarity), float(score), cell)
        self._toks[cell] = tokens(desc)
        if len(self.cells) > self.capacity:
            worst = min(self.cells.values(), key=lambda e: e.score)
            self.cells.pop(worst.cell, None)
            self._toks.pop(worst.cell, None)
        return True

    def stats(self) -> dict:
        return {"cells": len(self.cells), "capacity": self.capacity,
                "top": sorted((round(e.score, 3), e.desc[:40])
                              for e in self.cells.values())[-3:]}


class L0V2Strategy:
    def __init__(self, *, capacity: int = 32, elite_quota: int = 8,
                 novelty_floor: float = 0.25, seed: int = 7):
        self.archive = MapElitesArchive(capacity)
        self.elite_quota = int(elite_quota)
        self.novelty_floor = float(novelty_floor)
        self._rng = random.Random(seed)
        self.history: list[dict] = []

    def curate(self, candidates: list[dict], round_no: int = 1) -> dict:
        accepted = []
        rows_n = 0
        seen_cells = set()
        # 顺序处理：novelty 必须对「已接收档案」算，不能对本批全量算，
        # 否则同批所有候选 novelty 都是 1.0，等于没做多样性。
        for c in candidates or []:
            desc = str(c.get("desc") or "").strip()
            if not desc:
                continue
            rows_n += 1
            if len(accepted) >= self.elite_quota:
                continue
            pol = str(c.get("position") or c.get("polarity") or "?")
            cell = self.archive.cell_of(desc, pol)
            nov = self.archive.novelty(desc)
            row = {"desc": desc, "polarity": pol, "novelty": nov,
                   "raw": c, "cell": cell}
            if nov < self.novelty_floor and cell in seen_cells:
                continue
            seen_cells.add(cell)
            accepted.append(row)
            self.archive.add(desc, pol,
                             nov + (0.1 if pol == "both" else 0))
        nov_mean = sum(r["novelty"] for r in accepted) / max(1, len(accepted))
        self.history.append({"round": int(round_no), "accepted": len(accepted),
                             "novelty": round(nov_mean, 4),
                             "cells": len(self.archive.cells)})
        return {"accepted": accepted, "rejected": rows_n - len(accepted),
                "novelty_mean": round(nov_mean, 4),
                "archive": self.archive.stats(),
                "history": list(self.history)}

    def observe(self, candidates: list[dict], round_no: int = 1,
                untouched: list | None = None) -> dict:
        """v2-safe：不裁剪；观察全量候选，只有停滞/极性缺口才返回提示。

        修复点（旧 guide 失败根因）：
        - 旧版每圈都注入“不要重复/优先补未覆盖”，把生成压窄；
        - 新版前两圈不提示，只有 novelty 低或三态极性缺口才提示；
        - 提示是“可选检查”，不是硬约束，不删候选、不要求换词。
        """
        rows = []
        pol_counts = {}
        for c in candidates or []:
            desc = str(c.get("desc") or "").strip()
            if not desc:
                continue
            pol = str(c.get("position") or c.get("polarity") or "?")
            pol_counts[pol] = pol_counts.get(pol, 0) + 1
            cell = self.archive.cell_of(desc, pol)
            nov = self.archive.novelty(desc)
            rows.append({"desc": desc, "polarity": pol,
                         "cell": cell, "novelty": nov})
            if cell not in self.archive.cells or nov >= self.novelty_floor:
                self.archive.add(desc, pol, nov)
        nov_mean = (sum(r["novelty"] for r in rows) / max(1, len(rows)))
        missing = [p for p in ("阳", "阴", "both") if pol_counts.get(p, 0) == 0]
        # 前两圈不引导；之后只在停滞/极性缺口时给可选提示。
        should_guide = bool(
            int(round_no) >= 3
            and (nov_mean < 0.55 or bool(missing)
                 or len(self.archive.cells) < 3))
        dirs = []
        for u in (untouched or []):
            t = str((u.get("desc") if isinstance(u, dict) else u) or "").strip()
            if t:
                dirs.append(t)
        # 档案只作可选去重参考；不再把 top elite 当“禁止重复”。
        archive_dirs = [e.desc for e in sorted(
            self.archive.cells.values(), key=lambda e: -e.score)[:3]]
        self.history.append({"round": int(round_no), "accepted": len(rows),
                             "novelty": round(nov_mean, 4),
                             "cells": len(self.archive.cells)})
        return {"observed": len(rows), "novelty_mean": round(nov_mean, 4),
                "cells": len(self.archive.cells),
                "directions": (dirs or archive_dirs),
                "archive_dirs": archive_dirs, "missing_polarity": missing,
                "should_guide": should_guide,
                "history": list(self.history)}

    def should_stop(self, window: int = 3, novelty_floor: float = 0.12,
                    slope_floor: float = 0.08) -> bool:
        h = self.history
        if len(h) < window:
            return False
        recent = h[-window:]
        if sum(1 for x in recent if x["accepted"] == 0) >= window:
            return True
        if all(x["novelty"] < novelty_floor for x in recent):
            return True
        return heaps_slope(h) < slope_floor


def heaps_slope(history: list[dict]) -> float:
    """累计唯一 cell 数对 log(round) 的斜率；越小越饱和。"""
    xs, ys = [], []
    seen = set()
    for i, row in enumerate(history, 1):
        seen.add((row.get("round"), row.get("cells")))
        xs.append(math.log(i + 1.0))
        ys.append(math.log(max(1, int(row.get("cells") or 1))))
    if len(xs) < 2:
        return 1.0
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 1e-12:
        return 1.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


class ThompsonProbeSelector:
    def __init__(self, seed: int = 7):
        self._rng = random.Random(seed)
        self.alpha: dict[str, float] = {}
        self.beta: dict[str, float] = {}

    def pick(self, probes: list[dict], k: int = 2) -> list[dict]:
        scored = []
        for p in probes or []:
            key = str(p.get("id") or p.get("question") or "")
            a = self.alpha.get(key, 1.0)
            b = self.beta.get(key, 1.0)
            scored.append((self._rng.betavariate(a, b), key, p))
        scored.sort(key=lambda x: -x[0])
        return [p for _, _, p in scored[:max(1, int(k))]]

    def update(self, key: str, success: bool) -> None:
        k = str(key)
        self.alpha[k] = self.alpha.get(k, 1.0) + (1.0 if success else 0.0)
        self.beta[k] = self.beta.get(k, 1.0) + (0.0 if success else 1.0)


def evaluate_packed(path: str, quota: int = 8) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    v = (d.get("views") or {}).get("0") or {}
    cands = list(v.get("candidates") or [])
    strat = L0V2Strategy(elite_quota=quota)
    out = strat.curate(cands, 1)
    return {"run": Path(path).name, "candidates": len(cands),
            "accepted": len(out["accepted"]), "rejected": out["rejected"],
            "novelty_mean": out["novelty_mean"],
            "archive": out["archive"]}
