# -*- coding: utf-8 -*-
"""F4 · both 对撞层原生论证包 BothArgumentPackage。

both 层的职责是把 0/1 的产物放进同一论证场，显式保留败方与悬置：

- 原生：both_view 自带 argument_graph，且 synthesis / defeated / undecided 齐全；
- 桥接：缺项由 manifest / collision / adjudications / threads 等旧字段映射补齐——
  契约形式可以齐全，但语义不算原生，必须 native=False、synthesis_origin="bridge"、
  gaps 记 "bridge_only"；
- 原生缺项只记 gap（与 "bridge_only" 并列，不掩盖桥接来源），不生成新句子；
  conflict_resolution 只读已有产物。

本模块只用标准库，兼容 str / dict / list 三种产物形态。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

# 原生论证图必须自带的三个语义字段（contracts.py: both 只强校验 synthesis 非空、
# argument_graph 含 defeated/undecided 两键；这里把三者的「有内容」都当契约项）。
REQUIRED_FIELDS = ("synthesis", "defeated", "undecided")
GRAPH_FIELDS = ("synthesis", "defeated", "undecided", "conflict_resolution")

MISSING_GAPS = {
    "synthesis": "缺 synthesis",
    "defeated": "缺 defeated",
    "undecided": "缺 undecided",
}
BRIDGE_GAP = "bridge_only"
CONFLICT_KEYS = ("conflict_resolution", "settlement", "resolutions")


@dataclass
class BothArgumentPackage:
    argument_graph: dict = field(default_factory=dict)
    native: bool = False
    synthesis_origin: str = "none"
    gaps: list = field(default_factory=list)
    contract_completeness: float = 0.0
    ok: bool = False

    def to_dict(self) -> dict:
        return {
            "argument_graph": self.argument_graph,
            "native": self.native,
            "synthesis_origin": self.synthesis_origin,
            "gaps": self.gaps,
            "contract_completeness": round(float(self.contract_completeness), 4),
            "ok": self.ok,
        }


def _present(value) -> bool:
    """字段是否有内容：空串/空容器/None 都算缺。"""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _parse_json(raw: str):
    text = raw.strip()
    if not text or text[0] not in "{[":
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _view_dict(raw) -> dict:
    """both_view 兼容 dict / JSON 字符串 / 列表 / 纯文本。"""
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        parsed = _parse_json(raw)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"adjudications": list(parsed)}
        # 纯文本 = 旧产物里的综合/碰撞文本，按桥接源读，不当原生图。
        text = raw.strip()
        return {"manifest": text} if text else {}
    if isinstance(raw, list):
        return {"adjudications": list(raw)}
    return {}


def _graph_dict(raw) -> dict:
    """argument_graph 兼容 dict / JSON 字符串 / 列表 / 纯文本。"""
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        parsed = _parse_json(raw)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"defeated": list(parsed)}
        text = raw.strip()
        return {"synthesis": text} if text else {}
    if isinstance(raw, list):
        return {"defeated": list(raw)}
    return {}


_TEXT_KEYS = ("text", "synthesis", "summary", "desc", "claim", "answer",
              "title", "content")


def _text(raw) -> str:
    """取既有文本，不生成新句子。"""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        for key in _TEXT_KEYS:
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        try:
            return json.dumps(raw, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            return str(raw)
    if isinstance(raw, (list, tuple)):
        parts = [_text(x) for x in raw]
        return "；".join(part for part in parts if part)
    return str(raw).strip()


def _raw_items(raw) -> list:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        parsed = _parse_json(text)
        if isinstance(parsed, list):
            return list(parsed)
        return [text]
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, (list, tuple, set)):
        return list(raw)
    return [raw]


_CLAIM_KEYS = ("claim", "tension", "desc", "text", "how", "target", "aspect",
               "summary", "content")


def _claim_text(raw) -> str:
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        for key in _CLAIM_KEYS:
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        try:
            return json.dumps(raw, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            return str(raw)
    if isinstance(raw, (list, tuple)):
        return "；".join(part for part in (_claim_text(x) for x in raw) if part)
    return str(raw).strip()


def _claim_lines(raw) -> list:
    out = []
    for item in _raw_items(raw):
        text = _claim_text(item)
        if text:
            out.append(text)
    return out


def _origin_hint(graph: dict, view: dict) -> str:
    """引擎若显式标注论证图来源（§3.3「明确标注这是桥接合成」），必须认。"""
    values = (graph.get("origin"), graph.get("synthesis_origin"),
              view.get("argument_graph_origin"), view.get("synthesis_origin"))
    for value in values:
        if isinstance(value, str) and value.strip().lower() in ("native", "bridge"):
            return value.strip().lower()
    return ""


def _conflict_resolution(graph: dict, view: dict, research_view=None,
                         all_view=None):
    """只读回退：argument_graph → both 视图 → 下游 all 视图 → 上游 research 视图。"""
    for source in (graph, view, all_view, research_view):
        if not isinstance(source, dict):
            continue
        for key in CONFLICT_KEYS:
            value = source.get(key)
            if _present(value):
                return value
    return {}


def assemble_both_package(both_view, research_view=None,
                          all_view=None) -> BothArgumentPackage:
    """从已有 both/1/all 产物组装原生论证包；不生成新句子。

    native=True 只认 both_view.argument_graph 自带的 synthesis/defeated/undecided；
    任何一项靠旧字段映射补齐，都标桥接并记 "bridge_only"；gaps 同时保留原生缺项。
    """
    view = _view_dict(both_view)
    graph = _graph_dict(view.get("argument_graph"))

    out = {
        "synthesis": _text(graph.get("synthesis")),
        "defeated": _claim_lines(graph.get("defeated")),
        "undecided": _claim_lines(graph.get("undecided")),
        "conflict_resolution": _conflict_resolution(graph, view,
                                                    research_view, all_view),
    }
    missing = [name for name in REQUIRED_FIELDS if not _present(out[name])]

    bridged = False
    if "synthesis" in missing:
        # 与 bridge.py:166-174 一致：synthesis 取 manifest 或 collision 的既有文本。
        text = (_text(view.get("manifest")) or _text(view.get("collision"))
                or _text(view.get("synthesis")))
        if text:
            out["synthesis"] = text
            bridged = True
    if "defeated" in missing:
        # 与 bridge.py 一致：defeated 由 adjudications 映射；defeated_claims 是
        # 契约声明的 both 原生输出，可作次选桥接源。
        claims = (_claim_lines(view.get("adjudications"))
                  or _claim_lines(view.get("defeated_claims"))
                  or _claim_lines(view.get("defeated")))
        if claims:
            out["defeated"] = claims
            bridged = True
    if "undecided" in missing:
        # 与 bridge.py 一致：undecided 由 threads 映射；tension_set 为次选。
        claims = (_claim_lines(view.get("threads"))
                  or _claim_lines(view.get("undecided"))
                  or _claim_lines(view.get("tension_set")))
        if claims:
            out["undecided"] = claims
            bridged = True

    # 引擎显式标注为桥接的论证图，即使字段齐全也不算原生。
    if _origin_hint(graph, view) == "bridge":
        bridged = True

    pkg = BothArgumentPackage(argument_graph=out)
    # gap 记的是「原生缺项」；即使随后由桥接补齐，也必须留痕。
    for name in missing:
        pkg.gaps.append(MISSING_GAPS[name])

    # contract_completeness 量的是「最终论证图三件套是否齐全」（契约形式），
    # native 量的是「是否 both 层原生」（语义来源）：形式通过 != 语义通过。
    present = sum(1 for name in REQUIRED_FIELDS if _present(out[name]))
    pkg.contract_completeness = present / float(len(REQUIRED_FIELDS))

    any_content = any(_present(out[name]) for name in GRAPH_FIELDS)
    if bridged:
        pkg.native = False
        pkg.synthesis_origin = "bridge"
        pkg.gaps.append(BRIDGE_GAP)
    elif not missing:
        pkg.native = True
        pkg.synthesis_origin = "native"
    elif any_content:
        pkg.native = False
        pkg.synthesis_origin = "partial"
    else:
        pkg.native = False
        pkg.synthesis_origin = "none"
    pkg.ok = not pkg.gaps
    return pkg
