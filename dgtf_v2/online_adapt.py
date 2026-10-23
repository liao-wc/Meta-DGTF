# -*- coding: utf-8 -*-
"""在线自适应：有界、可回滚的运行时配置自修改（不写源码）。"""
from __future__ import annotations
import json
from pathlib import Path

_SPEC = {
    "spiral.all_extra_rounds": (0, 3, int),
    "spiral.round_stall_limit": (2, 20, int),
    "spiral.soft_max": (1, 24, int),
    "stop.anytime_alpha": (0.0, 0.5, float),
    "web_search.enabled": (False, True, bool),
    "auto.fact_flow.rounds_max": (0, 4, int),
    "external_input.facet_queries": (1, 6, int),
    "web_search.fetch": (False, True, bool),
    "web_search.fetch_per_run": (1, 8, int),
    "api.multi_turn.enabled": (False, True, bool),
    "api.tools.enabled": (False, True, bool),
}


def _set(cfg: dict, key: str, val) -> None:
    parts = key.split(".")
    cur = cfg
    for p in parts[:-1]:
        if not isinstance(cur.get(p), dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = val


def _get(cfg: dict, key: str):
    cur = cfg
    for p in key.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


class OnlineAdapter:
    VERSION = "online_adapt/v1"

    def __init__(self, path=None, enabled: bool = True):
        self.path = Path(path) if path else None
        self.enabled = bool(enabled)
        self.history = []

    def load(self) -> dict:
        if not (self.enabled and self.path and self.path.exists()):
            return {}
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            return dict((d or {}).get("overrides") or {})
        except Exception:
            return {}

    def apply(self, cfg: dict) -> dict:
        ov = self.load()
        applied = {}
        for k, v in ov.items():
            if k not in _SPEC:
                continue
            lo, hi, typ = _SPEC[k]
            try:
                v = typ(v)
            except Exception:
                continue
            if not (lo <= v <= hi):
                continue
            _set(cfg, k, v)
            applied[k] = v
        return applied

    def propose(self, result: dict) -> dict:
        if not self.enabled:
            return {"applied": {}, "skipped": "disabled"}
        sf = (result or {}).get("self_feedback") or {}
        sig = sf.get("signals") or {}
        ch = sig.get("channels") or {}
        allg = sig.get("all") or {}
        before = self.load()
        out = dict(before)
        _layers = sig.get("layers") or {}
        _duty_short = any(
            (v.get("duty") is not None and float(v.get("duty") or 0) < 0.35)
            for v in _layers.values() if isinstance(v, dict))
        if _duty_short or "duty_short" in (sig.get("flags") or []):
            out["spiral.soft_max"] = min(24, int(out.get(
                "spiral.soft_max", 0) or 0) + 1)
        if (ch.get("self") or {}).get("noisy"):
            out["stop.anytime_alpha"] = min(0.5, round(float(out.get(
                "stop.anytime_alpha", 0.0) or 0.0) + 0.01, 3))
        # 有界规则：闭环不干净 ⇒ 元层额外圈；context 弱 ⇒ 开联网；0 层弱 ⇒ soft_max 不降。
        if (not allg.get("clean")) or int(allg.get("leftover") or 0) > 0:
            out["spiral.all_extra_rounds"] = min(3, int(out.get(
                "spiral.all_extra_rounds", 0) or 0) + 1)
        if (ch.get("context") or {}).get("weak"):
            out["web_search.enabled"] = True
        _facets = sig.get("facets") or {}
        if not _facets:
            out["external_input.facet_queries"] = min(
                6, int(out.get("external_input.facet_queries", 3) or 3) + 1)
        if (ch.get("content") or {}).get("weak"):
            out["spiral.soft_max"] = min(24, int(out.get(
                "spiral.soft_max", 0) or 0) + 1)
        try:
            from dgtf_v2.api_policy import decide as _apidec
            out.update(_apidec(sig) or {})
        except Exception:
            pass
        # 只保留白名单/边界内，最多 8 项
        clean = {}
        for k, v in out.items():
            if k not in _SPEC:
                continue
            lo, hi, typ = _SPEC[k]
            try:
                v = typ(v)
            except Exception:
                continue
            if lo <= v <= hi:
                clean[k] = v
        clean = dict(list(clean.items())[:8])
        self.history.append({"run": (result or {}).get("id"),
                             "before": before, "after": clean})
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(
                {"version": self.VERSION, "overrides": clean,
                 "history": self.history[-20:]}, ensure_ascii=False, indent=1),
                encoding="utf-8")
        return {"applied": clean, "before": before, "after": clean,
                "n": len(clean)}

    def rollback(self) -> dict:
        self.history.append({"rollback": True})
        if self.path is not None and self.path.exists():
            self.path.unlink()
        return {"rolled_back": True}


__all__ = ["OnlineAdapter", "_SPEC"]
