# -*- coding: utf-8 -*-
"""三通道记忆与 EML 的统一门面（只存结构/读数，不存答案正文）。"""
from __future__ import annotations
import json
from pathlib import Path

from .unified_memory import UnifiedMemory

CHANNELS = ("content", "context", "self")


def channel_metrics(views: dict, pools: dict, quality: dict | None = None) -> dict:
    v = views or {}
    pools = pools or {}
    cats = 0
    amps = 0
    threads = 0
    for e in ("0", "1", "both", "all"):
        x = v.get(e) or {}
        cats += len(x.get("candidates") or [])
        amps += len(x.get("amps") or [])
        threads += len(x.get("threads") or [])
    cites = 0
    for e in ("0", "1", "both", "all"):
        x = v.get(e) or {}
        for sq in (x.get("sub_questions") or []):
            cites += len(sq.get("citations") or sq.get("evidence") or [])
        cites += len(x.get("provenance") or [])
    web = len(((pools.get("1") or {}).get("web_results") or []))
    flags = list((quality or {}).get("flags") or [])
    self_flags = [f for f in flags if any(k in f for k in (
        "rephrase", "self", "duty", "stagnation", "drift", "probe"))]
    return {
        "content": {"candidates": cats, "amps": amps, "threads": threads,
                    "score": cats + amps},
        "context": {"citations": cites, "web_results": web,
                    "score": cites + web},
        "self": {"flags": self_flags[:8], "score": len(self_flags)},
    }


class ChannelMemory:
    """EML 数值先验 + 三通道结构读数的单一读写门面。"""

    VERSION = "channel_memory/v1"

    def __init__(self, *, eml_path: str | Path | None = None,
                 channel_path: str | Path | None = None,
                 enabled: bool = True, allow_production: bool = False):
        self.eml = UnifiedMemory(v2_events_path=eml_path,
                                 enabled=enabled,
                                 allow_production=allow_production)
        self.channel_path = Path(channel_path) if channel_path else None
        self._channels: list = []

    def record_run(self, *, run_id: str, views: dict, pools: dict,
                   quality: dict | None = None) -> dict:
        m = channel_metrics(views, pools, quality)
        row = {"run_id": str(run_id or ""), "channels": m,
               "contains_content": False}
        if self.channel_path is not None:
            self.channel_path.parent.mkdir(parents=True, exist_ok=True)
            with self.channel_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._channels.append(row)
        return row

    def read_channels(self) -> dict:
        rows = list(self._channels)
        if self.channel_path is not None and self.channel_path.exists():
            for line in self.channel_path.read_text(encoding="utf-8").splitlines():
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        out = {}
        for c in CHANNELS:
            vals = [r["channels"][c]["score"] for r in rows
                    if isinstance(r.get("channels"), dict) and c in r["channels"]]
            out[c] = {"n": len(vals),
                      "mean_score": round(sum(vals) / len(vals), 4) if vals else 0.0,
                      "last_score": vals[-1] if vals else 0.0}
        return {"version": self.VERSION, "channels": out,
                "contains_content": False, "n_runs": len(rows)}

    def priors(self) -> dict:
        return self.eml.read_priors()

    def record_outcome(self, **kw):
        return self.eml.record_outcome(**kw)


__all__ = ["CHANNELS", "channel_metrics", "ChannelMemory"]
