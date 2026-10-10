# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 把 `dgtf_config.yaml` 摊成可调参数（给「高级参数」面板）。

为什么：改配置以前要开 yaml 文件手动编辑。这里把 yaml **扁平化**成
`a.b.c → 值` 的列表交给前端渲染，用户改了以后由 `build_temp_config()`
生成一份**临时副本**用 `--config` 传给引擎 —— 原件不动。
"""

from __future__ import annotations

from pathlib import Path

import yaml

import outputs_index as oi

CFG = oi.PROJECT_ROOT / "dgtf_config.yaml"

# 分组中文名（顺序即展示顺序；没列到的按字母排后面）
GROUP_LABEL = [
    ("api", "模型与 API"),
    ("runtime", "运行档位"),
    ("web_search", "联网检索"),
    ("external_anchor", "外部锚点"),
    ("auto", "自适应调度"),
    ("output", "输出"),
    ("memory", "记忆通道"),
    ("spiral", "螺旋与停止"),
    ("probe", "探针"),
    ("actions", "动作开关"),
]
_ORDER = {k: i for i, (k, _) in enumerate(GROUP_LABEL)}

# 几个「枚举」键给下拉选项（其余按值类型渲染输入框）
OPTIONS = {
    "api.default_model": ["deepseek-flash", "deepseek-reasoner", "deepseek-chat"],
    "api.reasoner_model": ["deepseek-flash", "deepseek-reasoner", "deepseek-chat"],
    "web_search.backend": ["tavily", "snapshot"],
    "external_anchor.retriever": ["snapshot", "tavily"],
    "runtime.web": ["auto", "on", "off"],
    "runtime.thinking": ["auto", "on", "off"],
    "runtime.effort": ["auto", "low", "medium", "high", "max"],
}
# 置顶项（面板最先看到的几个）
PINNED = ("api.default_model", "web_search.backend", "runtime.thinking",
          "runtime.effort", "web_search.enabled")


def _flatten(d, prefix: str = "") -> dict:
    out: dict = {}
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "."))
        else:
            out[key] = v
    return out


def _item(key: str, val) -> dict:
    it = {"key": key, "value": val}
    if isinstance(val, bool):
        it["type"] = "bool"
    elif isinstance(val, (int, float)):
        it["type"] = "number"
    else:
        it["type"] = "str"
    if key in OPTIONS:
        it["type"] = "select"
        it["options"] = OPTIONS[key]
    if key in PINNED:
        it["pinned"] = True
    return it


def load_params() -> dict:
    """返回 {groups:[{key,label,items:[…]}], total}。"""
    try:
        raw = yaml.safe_load(CFG.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception:  # noqa: BLE001
        raw = {}
    flat = _flatten(raw)
    groups: dict[str, list] = {}
    for k, v in flat.items():
        groups.setdefault(k.split(".")[0], []).append(_item(k, v))
    out = []
    for top, items in groups.items():
        items.sort(key=lambda x: (0 if x.get("pinned") else 1, x["key"]))
        out.append({"key": top,
                    "label": dict(GROUP_LABEL).get(top, top),
                    "items": items})
    out.sort(key=lambda g: (_ORDER.get(g["key"], 99), g["key"]))
    return {"groups": out, "total": len(flat)}


def build_temp_config(overrides: dict, out_path: Path) -> str | None:
    """把 `{扁平键: 值}` 覆盖到 yaml 副本上，返回可传给 `--config` 的路径。"""
    overrides = overrides or {}
    try:
        raw = yaml.safe_load(CFG.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception:  # noqa: BLE001
        return None
    for k, v in overrides.items():
        node = raw
        parts = str(k).split(".")
        ok = True
        for p in parts[:-1]:
            nxt = node.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                node[p] = nxt
            node = nxt
        if ok:
            node[parts[-1]] = v
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
            encoding="utf-8", newline="")
        return str(out_path)
    except OSError:
        return None
