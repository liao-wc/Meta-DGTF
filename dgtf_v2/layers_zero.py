# -*- coding: utf-8 -*-
"""F5 · 0 层（修行）审计 / 延期契约包。

0 层的职责是发散，不是回答：给出 aspect_map / probes / suspensions，
可选给 novelty_curve；不回答、不裁决、不闭合。F5 按融合设计（§3.1 / §6.3）
**延期**，即不接 L0-v2 机制（actions.l0_v2_curate 保持 false）；本模块只读
审计已有 0 层产物，deferred 恒为 True。

判据口径（与 core_duty / contracts 一致）：
- aspects：显式计数优先，其次 aspect_map，最后按 bridge 口径 |candidates|+|amps|；
- probes / suspensions 至少一个非空，否则 0 层没有继续/悬置项；
- actions / not_do 属于 all 层，出现在 0 层即越权，记 gap；
- novelty_curve 当前 bridge 恒输出 []（docs/v1240_phase5_fusion.md §3.1），
  空只表示 novelty 读数延期，**不**记 gap；
- 只有原生齐全（aspects>0 且 probes/suspensions 至少一个非空）且无 gap 才 ok。

只读已有产物，不生成新句子；缺项写 gap，不补空话。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

# 0 层禁止的输出：行动/不做属于 all 层（contracts.LAYER_CONTRACTS["0"]）。
_OVERREACH_KEYS = ("actions", "_actions", "not_do", "_not_do")


@dataclass
class ZeroLayerPackage:
    aspects: int = 0
    probes: int = 0
    suspensions: int = 0
    novelty_curve: list = field(default_factory=list)
    novelty_measured: bool = False
    no_actions: bool = True
    gaps: list = field(default_factory=list)
    contract_completeness: float = 0.0
    ok: bool = False
    deferred: bool = True

    def to_dict(self) -> dict:
        return {
            "aspects": int(self.aspects),
            "probes": int(self.probes),
            "suspensions": int(self.suspensions),
            "novelty_curve": list(self.novelty_curve),
            "novelty_measured": bool(self.novelty_measured),
            "no_actions": bool(self.no_actions),
            "gaps": list(self.gaps),
            "contract_completeness": round(float(self.contract_completeness), 4),
            "ok": bool(self.ok),
            "deferred": bool(self.deferred),
        }


def _as_dict(raw) -> dict:
    """容错：视图/读数可能是 dict，也可能是 JSON 字符串。"""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            d = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        if isinstance(d, dict):
            return d
    return {}


def _as_list(raw) -> list:
    """容错：列表或 JSON 列表字符串；其余按空列表处理。"""
    if isinstance(raw, (list, tuple)):
        return [x for x in raw if x is not None]
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        try:
            d = json.loads(s)
        except (TypeError, ValueError):
            return []
        if isinstance(d, (list, tuple)):
            return [x for x in d if x is not None]
    return []


def _present(raw) -> bool:
    """字段是否「有值」：空列表 / 空串 / 0 / None 都算没有。"""
    if raw is None or raw is False:
        return False
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return False
        try:
            return _present(json.loads(s))
        except (TypeError, ValueError):
            return True
    if isinstance(raw, (list, tuple, dict)):
        return bool(raw)
    if isinstance(raw, (int, float)):
        return raw != 0
    return bool(raw)


def _count(raw) -> int:
    """计数容错：数字、数字字符串、JSON 列表/字典、原生列表/字典。"""
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return max(0, raw)
    if isinstance(raw, float):
        return max(0, int(raw))
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return 0
        try:
            d = json.loads(s)
        except (TypeError, ValueError):
            try:
                return max(0, int(float(s)))
            except (TypeError, ValueError):
                return 0
        return _count(d)
    if isinstance(raw, (list, tuple, dict)):
        return len(raw)
    return 0


def _item_count(view: dict, keys: tuple) -> int:
    """按候选键依次取计数；跳过空值，全空则 0。"""
    for key in keys:
        if key in view:
            n = _count(view[key])
            if n:
                return n
    return 0


def _aspects(view: dict) -> int:
    # 1) 显式计数（含数字字符串）；2) 显式 aspect_map；3) bridge 口径 candidates+amps。
    for key in ("aspects", "aspect_count"):
        if key in view:
            n = _count(view[key])
            if n:
                return n
    n = _count(view.get("aspect_map"))
    if n:
        return n
    return _count(view.get("candidates")) + _count(view.get("amps"))


def _novelty_curve(view: dict, quality: dict) -> list:
    """novelty 读数：视图优先，quality 只作只读补充；空就是延期，不是 gap。"""
    curve = _as_list(view.get("novelty_curve"))
    if not curve:
        curve = _as_list(quality.get("novelty_curve"))
    out = []
    for x in curve:
        if isinstance(x, bool):
            out.append(float(x))
        elif isinstance(x, (int, float)):
            out.append(float(x))
        elif isinstance(x, dict):
            hit = None
            for k in ("novelty", "value", "rate"):
                if isinstance(x.get(k), (int, float)):
                    hit = float(x[k])
                    break
            out.append(hit if hit is not None else dict(x))
        elif isinstance(x, str):
            out.append(x)
    return out


def _overreach(view: dict) -> list:
    """返回越权字段名：0 层出现 actions/not_do（含 decidable_product 嵌套）。"""
    hits = []
    for key in _OVERREACH_KEYS:
        if _present(view.get(key)):
            hits.append(key)
    dp = view.get("decidable_product")
    if isinstance(dp, dict):
        for key in ("actions", "not_do"):
            if _present(dp.get(key)):
                hits.append("decidable_product.%s" % key)
    return hits


def assemble_zero_package(zero_view: dict | str | None = None,
                          quality: dict | str | None = None) -> ZeroLayerPackage:
    """从已有 0 层产物组装审计包；不生成新句子、不补空话。"""
    view = _as_dict(zero_view)
    q = _as_dict(quality)
    pkg = ZeroLayerPackage()

    pkg.aspects = _aspects(view)
    pkg.probes = _item_count(view, ("probes", "probe_queue"))
    pkg.suspensions = _item_count(view, ("suspensions",))
    pkg.novelty_curve = _novelty_curve(view, q)
    pkg.novelty_measured = bool(pkg.novelty_curve)
    over = _overreach(view)
    pkg.no_actions = not over
    pkg.deferred = True  # F5 按设计延期；不接 L0-v2

    if pkg.aspects <= 0:
        pkg.gaps.append("缺 aspects（0 层 aspect_map 为空）")
    if pkg.probes <= 0 and pkg.suspensions <= 0:
        pkg.gaps.append("缺 probes/suspensions（0 层无继续/悬置项）")
    for key in over:
        pkg.gaps.append("0 层越权：%s（行动/不做属于 all）" % key)

    native = [pkg.aspects > 0, (pkg.probes > 0 or pkg.suspensions > 0)]
    pkg.contract_completeness = (sum(1 for hit in native if hit)
                                 / float(len(native)))
    pkg.ok = pkg.contract_completeness == 1.0 and not pkg.gaps
    return pkg
