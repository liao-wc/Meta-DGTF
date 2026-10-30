# -*- coding: utf-8 -*-
"""层1 可判定化：可选自动最小圈数（V2.2.92）。

背景：研究层需 3 个逐圈点才能判「连续不涨」；默认 2 圈 ⇒ 判据样本不足。
本模块提供 **默认关闭** 的 opt-in：spiral.min_rounds_judgeable=true 时，
把指定层的最小圈数/计划圈数抬到 target（默认 3），让层1 目标可判定。
默认 false ⇒ 零行为差。
"""
from __future__ import annotations

DEFAULT_LAYERS = ("1", "both")
DEFAULT_TARGET = 3


def _spiral(config) -> dict:
    return dict((config or {}).get("spiral") or {})


def enabled(config) -> bool:
    return bool(_spiral(config).get("min_rounds_judgeable"))


def layers(config) -> list:
    sp = _spiral(config)
    raw = sp.get("min_rounds_judgeable_layers") or list(DEFAULT_LAYERS)
    return [str(x) for x in raw]


def target(config) -> int:
    sp = _spiral(config)
    try:
        return max(1, int(sp.get("min_rounds_judgeable_target")
                          or DEFAULT_TARGET))
    except (TypeError, ValueError):
        return DEFAULT_TARGET


def judgeable_rounds_plan(config, rounds_map) -> tuple[dict, bool]:
    """返回 (新 rounds_map, 是否改动)；默认关闭时原样返回。"""
    out = dict(rounds_map or {})
    if not enabled(config):
        return out, False
    tgt = target(config)
    changed = False
    for e in layers(config):
        try:
            cur = int(out.get(e) or 0)
        except (TypeError, ValueError):
            cur = 0
        if cur < tgt:
            out[e] = tgt
            changed = True
    return out, changed


def judgeable_min_rounds(config, entry: str, existing=None) -> dict:
    """返回合并后的 min_rounds；默认关闭或非目标层原样返回。"""
    out = dict(existing or {})
    if not enabled(config) or str(entry) not in layers(config):
        return out
    tgt = target(config)
    try:
        cur = int(out.get(str(entry)) or 0)
    except (TypeError, ValueError):
        cur = 0
    out[str(entry)] = max(cur, tgt)
    return out
