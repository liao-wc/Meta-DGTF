# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 按「层」切分日志与产物（只读，不改引擎）。

四层（顺序即运行顺序）：

    修行 = entry `0`  ·  研究 = `1`  ·  对撞 = `both`  ·  元 = `all`

- **日志**：以进度条行为界 —— `━━━ 修行 · 第 1/3 圈 · 摊开 · view ━━━`
  （并行模式是 `━━━ 修行 · <并行标签> 第 r/…`）。界之前的行归「共有」。
- **产物 md**：以层小标题为界 —— 形如 `### 修行层`（后面跟着该层的 entry）。
  界之前的行归「共有头部」（标题 + 元数据 + 非层段落）。

为什么这么切：实测（`元DGTF-V1.23.20.py`）引擎每圈都会打那行进度条
（`:10348` / `:11374`，`print` 输出、不受 `--quiet` 影响），
而产物 md 的「附：逐层明细」下每个层都是独立 `###` 段。
"""

from __future__ import annotations

import re

# 层定义：(中文名, entry 标识)
LAYERS = (("修行", "0"), ("研究", "1"), ("对撞", "both"), ("元", "all"))
LAYER_NAMES = [n for n, _ in LAYERS]
LAYER_OF_ENTRY = {e: n for n, e in LAYERS}
ENTRY_OF_LAYER = {n: e for n, e in LAYERS}

# 日志层界：━━━ 修行 · 第 1/3 圈 … ━━━
_LOG_LAYER_RE = re.compile(r"━{3,}\s*(修行|研究|对撞|元)\s*[·・]")
# 备用形态（mock / 其它）：[修行层] 第 1 圈
_LOG_LAYER_ALT_RE = re.compile(r"^\s*\[(修行|研究|对撞|元)层\]")
# 产物 md 的层小标题：### 修行层 `0`
_MD_LAYER_RE = re.compile(r"^#{2,4}\s+(修行|研究|对撞|元)层\b", re.M)


def layer_of_line(line: str) -> str | None:
    """这一行是否开启某一层？是则返回层名。"""
    m = _LOG_LAYER_RE.search(line)
    if m:
        return m.group(1)
    m = _LOG_LAYER_ALT_RE.match(line)
    return m.group(1) if m else None


def split_log(text: str) -> dict[str, str]:
    """日志按层切开。返回 {"__head__": 共有头, "修行": …, "研究": …, …}。"""
    buf: dict[str, list[str]] = {"__head__": []}
    for n in LAYER_NAMES:
        buf[n] = []
    cur = "__head__"
    for line in (text or "").splitlines():
        name = layer_of_line(line)
        if name:
            cur = name
        buf[cur].append(line)
    return {k: "\n".join(v) for k, v in buf.items()}


def split_md(text: str) -> dict[str, str]:
    """产物 md 按层小标题切开。

    返回 {"__head__": 共有头部, "修行": 该层段, …}；
    头部 = 第一个层小标题之前的全部内容（标题 + 元数据 + 非层段落）。
    """
    text = text or ""
    ms = list(_MD_LAYER_RE.finditer(text))
    out: dict[str, str] = {"__head__": text if not ms else text[: ms[0].start()]}
    for n in LAYER_NAMES:
        out[n] = ""
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        seg = text[m.start():end]
        # 同名层若出现多次，保留最长的（更可能是「附：逐层明细」里的正式段）
        if len(seg) > len(out.get(m.group(1), "")):
            out[m.group(1)] = seg
    return out


def layer_stats(log_text: str, md_text: str) -> dict[str, dict]:
    """每层的行数 / 字符数，给面板与 json 用。"""
    lg = split_log(log_text)
    md = split_md(md_text)
    out: dict[str, dict] = {}
    for n in LAYER_NAMES:
        body = lg.get(n, "")
        # 从 `… · 第 N/M 圈 · …` 里取当前圈与上限（取最后一个 = 最新）
        round_no = cap = 0
        for a, b in re.findall(r"第\s*(\d+)\s*/\s*(\d+)\s*圈", body):
            round_no, cap = int(a), int(b)
        out[n] = {
            "entry": ENTRY_OF_LAYER[n],
            "log_lines": len([l for l in body.splitlines() if l.strip()]),
            "log_chars": len(body),
            "md_chars": len(md.get(n, "")),
            "round": round_no,
            "rounds_cap": cap,
        }
    return out
