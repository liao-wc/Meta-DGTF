# -*- coding: utf-8 -*-
"""F5 · 0 层（修行）审计 / 生成契约包。

0 层的职责是发散，不是回答：给出 aspect_map / probes / suspensions，
可选给 novelty_curve；不回答、不裁决、不闭合。V2.0.0 起 F5 已完成：
从问题/研究分解生成 aspect_map / probes / suspensions / novelty_curve，
并只读审计已有 0 层产物。deferred 默认 False。

判据口径（与 core_duty / contracts 一致）：
- aspects：显式计数优先，其次 aspect_map，最后按 bridge 口径 |candidates|+|amps|；
- probes / suspensions 至少一个非空，否则 0 层没有继续/悬置项；
- actions / not_do 属于 all 层，出现在 0 层即越权，记 gap；
- novelty_curve 由 F5 生成器从 aspect/问题计算；空只表示无读数，**不**记 gap；
- 只有原生齐全（aspects>0 且 probes/suspensions 至少一个非空）且无 gap 才 ok。

生成器只补契约字段（aspect/probe/suspension/novelty），不生成
answer/decision/action；审计仍可独立只读运行，缺项写 gap。
"""
from __future__ import annotations

import json
import re
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
    deferred: bool = False

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



_F5_SPLIT = re.compile(r"[，。；;,！？!?\n]+")


def _text(value) -> str:
    return str(value or "").strip()


def _unique_texts(values, limit: int = 32) -> list:
    out = []
    seen = set()
    for raw in values or []:
        text = _text(raw)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _research_texts(research) -> list:
    """从研究层视图里提取子问题/缺口/悬置的文本，供 F5 生成。"""
    out = []
    keys = {"subquestions", "questions", "question_set", "decompose",
            "aspects", "aspect_map", "gaps", "suspensions", "probes",
            "answer_set", "abstentions", "coverage"}

    def walk(node, depth=0):
        if depth > 5 or len(out) >= 24:
            return
        if isinstance(node, str):
            if node.strip():
                out.append(node)
            return
        if isinstance(node, (list, tuple)):
            for x in node:
                walk(x, depth + 1)
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if str(k) in keys or isinstance(v, (dict, list, tuple)):
                    walk(v, depth + 1)

    walk(research)
    return _unique_texts(out, 24)


def _novelty_for(question: str, aspect: str) -> float:
    def grams(text):
        text = re.sub(r"\s+", "", _text(text).lower())
        if not text:
            return set()
        if len(text) < 2:
            return {text}
        return {text[i:i + 2] for i in range(len(text) - 1)}
    q = grams(question)
    a = grams(aspect)
    if not q or not a:
        return 0.5
    return round(1.0 - len(q & a) / float(len(q | a)), 3)


def generate_zero_layer(question: str, research=None,
                        max_aspects: int = 8, max_probes: int = 5) -> dict:
    """F5 生成机制：从问题与研究分解生成 0 层契约字段。

    只生成 aspect_map / probes / suspensions / novelty_curve；
    绝不生成 answer / decision / actions / final_claim。
    """
    q = _text(question) or "未命名问题"
    candidates = _unique_texts(
        [x.strip() for x in _F5_SPLIT.split(q) if len(x.strip()) >= 2])
    if not candidates:
        candidates = [q[:80]]
    candidates += _research_texts(research)
    candidates = _unique_texts(candidates, max(1, int(max_aspects)))
    aspects = []
    for i, aspect in enumerate(candidates, 1):
        aspects.append({
            "id": "A%d" % i,
            "aspect": aspect[:120],
            "polarity": "both",
            "source": "f5_generated",
            "novelty": _novelty_for(q, aspect),
        })
    probes = []
    for i, a in enumerate(aspects[:max(1, int(max_probes))], 1):
        probes.append({
            "id": "P%d" % i,
            "question": "围绕「%s」还需要验证什么边界、反例或证据？" % a["aspect"][:80],
            "aspect": a["aspect"][:120],
            "priority": i,
        })
    suspensions = []
    if re.search(r"吗|是否|如何|怎么|为什么|多少|哪些|能否|该不该", q):
        suspensions.append({
            "id": "S1", "status": "active", "question": q[:120],
            "reason": "问题包含未决/判断词，等待证据与边界",
        })
    if not suspensions:
        suspensions.append({
            "id": "S1", "status": "open", "question": q[:120],
            "reason": "F5 保留一个未决边界，避免把发散误当结论",
        })
    curve = [{"round": 0, "novelty": a["novelty"], "aspect": a["aspect"][:80]}
             for a in aspects]
    return {
        "aspect_map": aspects,
        "probes": probes,
        "suspensions": suspensions,
        "novelty_curve": curve,
        "zero_generation": "f5",
        "deferred": False,
    }


def merge_zero_generation(view, generated) -> dict:
    """把 F5 生成字段合并进 0 层视图；显式已有字段优先，不覆盖。"""
    out = dict(view or {})
    gen = _as_dict(generated)
    for key in ("aspect_map", "probes", "probe_queue", "suspensions",
                "novelty_curve"):
        if not _present(out.get(key)) and _present(gen.get(key)):
            out[key] = gen[key]
    out["zero_generation"] = gen.get("zero_generation") or "f5"
    out["deferred"] = False
    return out


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
    pkg.deferred = bool(view.get("deferred", False))

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
