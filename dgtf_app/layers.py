# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 按「层」切分日志与产物（只读，不改引擎）。

四层（顺序即运行顺序）：

    修行 = entry `0`  ·  研究 = `1`  ·  对撞 = `both`  ·  元 = `all`

- **日志**：以层界行切分，兼容**两种**引擎输出形态：
  ① 老式进度条 —— `━━━ 修行 · 第 1/3 圈 · 摊开 · view ━━━`
    （并行模式是 `━━━ 修行 · <并行标签> 第 r/…`）；
  ② ★ 现行（实测 `元DGTF-V1.23.22.py`）每层开头打一行 —— **`【0】修行 DGTF（螺旋上限 4 圈）`**
    （`:13850`，`entry` ∈ `0/1/both/all`，label ∈ 修行/研究/对撞/元；**不再保证**有 ① 的进度条）。
  界之前的行归「共有」。
- **产物 md**：以层小标题为界 —— 形如 `### 修行层`（后面跟着该层的 entry）。
  界之前的行归「共有头部」（标题 + 元数据 + 非层段落）。

为什么这么切：老版（`…V1.23.20.py`）每圈都打 `━━━` 进度条；**新版取消了它**（`if self.verbose`
那两处进度条在层 runner 上 verbose 已被置 False），只剩 `【entry】label DGTF` 的层 banner 与
`↻ 第 r/N 圈 · role` 的圈标。两种形态都要认，否则真跑的日志会**整段落进「共有头」、四层全空**
（实测：应用里真跑日志区只显示占位「等待该层开始输出…」）。
"""

from __future__ import annotations

import re

# 层定义：(中文名, entry 标识)
LAYERS = (("修行", "0"), ("研究", "1"), ("对撞", "both"), ("元", "all"))
LAYER_NAMES = [n for n, _ in LAYERS]
LAYER_OF_ENTRY = {e: n for n, e in LAYERS}
ENTRY_OF_LAYER = {n: e for n, e in LAYERS}

# 日志层界：━━━ 修行 · 第 1/3 圈 … ━━━  （老式进度条）
_LOG_LAYER_RE = re.compile(r"━{3,}\s*(修行|研究|对撞|元)\s*[·・]")
# ★ 现行层界：`【0】修行 DGTF（螺旋上限 4 圈）`（实测 V1.23.22，`:13850`）
_LOG_LAYER_BANNER_RE = re.compile(r"^\s*【\s*(0|1|both|all)\s*】\s*(修行|研究|对撞|元)\s*DGTF")
# 备用形态（mock / 其它）：[修行层] 第 1 圈
_LOG_LAYER_ALT_RE = re.compile(r"^\s*\[(修行|研究|对撞|元)层\]")
# 产物 md 的层小标题：### 修行层 `0`
_MD_LAYER_RE = re.compile(r"^#{2,4}\s+(修行|研究|对撞|元)层\b", re.M)


def layer_of_line(line: str) -> str | None:
    """这一行是否开启某一层？是则返回层名。"""
    m = _LOG_LAYER_RE.search(line)
    if m:
        return m.group(1)
    m = _LOG_LAYER_BANNER_RE.match(line)
    if m:
        return m.group(2)
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
