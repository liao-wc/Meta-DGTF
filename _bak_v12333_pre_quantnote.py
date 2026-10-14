#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
元 DGTF · v1.23.33

单文件多模并行推理引擎：四层 0/1/both/all × 螺旋跑圈，三通道 content/context/self。

★ 变更记录（各版 changelog 与收束摘要）**不在代码里** —— 见仓库根目录 `CHANGELOG.md`。
  代码正文只解释「这段**当前**为什么长这样」，不留版次批注。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import logging
import os
import re
import sys
import time
import unicodedata
import contextlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openai

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    import jieba
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False


__version__ = "1.23.33"

logger = logging.getLogger("dgtf")


# ============================================================
# 终端编码兜底 [fix-97]
# ============================================================
# Windows 下 stdout 被重定向到文件时，Python 会用 locale 编码（cp936/GBK），
# 而本文件大量用 emoji 与制表符作日志前缀，第一条 print 就会
# UnicodeEncodeError 崩掉整个进程。这里在导入期把两个流切成 UTF-8。
def _force_utf8_streams() -> None:
    for stream in (getattr(sys, "stdout", None),
                   getattr(sys, "stderr", None)):
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            # 已被替换成自定义 writer / 不支持 reconfigure —— 不致命，跳过
            pass


_force_utf8_streams()


# ============================================================
# 常量
# ============================================================
KINDS = {
    "concept": "概念", "event": "事件", "person": "人", "object": "物品",
    "startpoint": "新起点", "question": "探针问题", "thread": "悬空线头",
    "meta": "元反思", "other": "其他",
}

AMP_TYPES = {
    "logical": "逻辑性", "ontological": "存在论",
    "structural": "结构性", "axiological": "价值性", "pseudo": "伪合",
}

_STOPCHARS = set(
    "的了是在和与或及之于以及为此则就也都还但而所以因为如果那么这那这些那些"
    "一种一个进行已经可以通过我们你们他们它们什么怎么如何为何哪些这个那个哪个"
)
_STOPWORDS = {
    "的话", "一种", "一个", "进行", "已经", "可以", "通过",
    "我们", "你们", "他们", "它们", "什么", "怎么", "如何", "为何",
    "这个", "那个", "哪个", "这些", "那些", "哪些",
}

_ENTRIES = ("0", "1", "both", "all")

_ENTRY_DEPS = {"0": (), "1": (), "both": ("0", "1"), "all": ()}
_ENTRY_MIN_UPSTREAM = {"0": 0, "1": 0, "both": 0, "all": 2}

_ENTRY_CONTENT_DEPS = {"0": (), "1": (), "both": ("0", "1"),
                       "all": ("0", "1", "both")}


# ============================================================
# D~H 模式：阶段式 DAG [feat-109]
# ============================================================
# 五种模式共用一台调度器（MetaDGTF._run_parallel_stage），
# 差别全在这张表上。每层两条边：
#   waits —— 上游**跑完所有圈**才放行（硬闸，等 _st_done）
#   gates —— 上游**交出第一圈**就放行（软闸，等 _st_gate）
#
#   表读作 (waits, gates)：
#     "both": (("0", "1"), ())  = 等 0 和 1 都跑完所有圈
#     "all":  ((), ("both",))   = both 一出第一圈就跟上
#
#   注意 gates 是"至少一圈"而不是"恰好一圈"——下游出发时
#   上游可能已经跑掉好几圈了，它读到的就是那一刻的最新 view。
# ============================================================
_MODE_GRAPH: Dict[str, Dict[str, tuple]] = {
    # 0/1 并行跑完 → both → both 出圈后 all 跟上（both/all 并行）
    "D": {
        "0": ((), ()),
        "1": ((), ()),
        "both": (("0", "1"), ()),
        "all": ((), ("both",)),
    },
    # 0/1 并行跑完 → both 跑完 → all（both/all 串行）
    "E": {
        "0": ((), ()),
        "1": ((), ()),
        "both": (("0", "1"), ()),
        "all": (("both",), ()),
    },
    # 0 跑完 → 1 出一圈后 both 跟上 → both 出一圈后 all 跟上
    "F": {
        "0": ((), ()),
        "1": (("0",), ()),
        "both": ((), ("1",)),
        "all": ((), ("both",)),
    },
    # 0 跑完 → 1 出一圈后 both 跟上 → both 跑完 all 才起
    "G": {
        "0": ((), ()),
        "1": (("0",), ()),
        "both": ((), ("1",)),
        "all": (("both",), ()),
    },
    # 0 跑完 → 1 跑完 → both → both 出一圈后 all 跟上
    "H": {
        "0": ((), ()),
        "1": (("0",), ()),
        "both": (("1",), ()),
        "all": ((), ("both",)),
    },
}

_MODE_LABEL = {
    "D": "D · 双起并行 + 撞元并行",
    "E": "E · 双起并行 + 撞元串行",
    "F": "F · 修行先行 + 全流水",
    "G": "G · 修行先行 + 撞毕收元",
    "H": "H · 逐层接力 + 撞元并行",
}

_missing_label = set(_MODE_GRAPH) - set(_MODE_LABEL)
_extra_label = set(_MODE_LABEL) - set(_MODE_GRAPH)
if _missing_label or _extra_label:
    raise ValueError(
        "_MODE_LABEL 与 _MODE_GRAPH 键不一致："
        f"缺 label {sorted(_missing_label)}；"
        f"多 label {sorted(_extra_label)}")
_bad_entry = {
    m: sorted(set(g) - set(_ENTRIES))
    for m, g in _MODE_GRAPH.items()
    if set(g) - set(_ENTRIES)
}
if _bad_entry:
    raise ValueError(f"_MODE_GRAPH 里有非法层名（应为 {_ENTRIES}）："
                     f"{_bad_entry}")


def _vp_preview(text, limit: int = 4000) -> str:
    """日志预览：**按整行截断**，不在行中间砍断。

    原来这几处回显写死 `raw[:200]` / `[:160]` / `[:50]`，而模型返回的是**多行正文**
    —— 字符数一到就停在某一行中间，读者看到的是半截话（实测
    `- [concept] 纠缠熵面积律不能单`），而完整正文又不在这一层的日志里
    （`view 全文` 折叠块只覆盖 view 条那一段），于是「内容没显示完全」。

    `limit` 默认 4000：对视图正文（4~8 行 / 200~600 字）等于不截断；真被截断时
    **明说**还剩多少字未显示 —— 不静默丢内容，与 `dump_round`「不挑字段、不截断」
    同一条纪律。
    """
    s = text if isinstance(text, str) else str(text or "")
    if len(s) <= limit:
        return s
    cut = s.rfind("\n", 0, limit + 1)
    if cut <= 0:
        cut = limit
    return s[:cut] + "\n   …（预览到此，另有 %d 字未显示）" % (len(s) - cut)


def _mode_timing_lines(mode: str, n_rounds: int = 3) -> List[str]:
    """按 _MODE_GRAPH 算出每层在第几拍出发，画出时序图。

    [P2-9] 这张图原来是手写的，和 _MODE_GRAPH 各说各话：
      F 的 all 画在 both 第一圈结束之前
      G 的 all 画在 both 跑完之前
      H 的 both 画在 1 跑完之前
      D/E 差一列
    图是给用户看的，表是真正执行的那份 —— 两者不一致时，
    用户按图理解到的调度是错的。现在由图生成，图与表不可能再分叉。

    一拍 = 一圈。waits：等上游跑完 n_rounds 拍；gates：等上游跑完 1 拍。
    """
    g = _MODE_GRAPH.get(mode) or {}
    if not g:
        return []
    starts: Dict[str, int] = {}
    # 反复松弛直到稳定（图是 DAG，最多 len(g) 轮就收敛）
    for _ in range(len(g) + 1):
        changed = False
        for layer, edges in g.items():
            waits, gates = edges
            t = 0
            for w in (waits or ()):
                if w in starts:
                    t = max(t, starts[w] + n_rounds)
            for gd in (gates or ()):
                if gd in starts:
                    t = max(t, starts[gd] + 1)
            if starts.get(layer) != t:
                starts[layer] = t
                changed = True
        if not changed:
            break
    label_w = max((len(k) for k in g), default=4) + 2
    cell = "".join(f"[r{i}]" for i in range(1, n_rounds + 1))
    out = []
    for layer in ("0", "1", "both", "all"):
        if layer not in g:
            continue
        out.append(layer.ljust(label_w) + "    " * starts.get(layer, 0)
                   + cell + "…")
    return out


# [P2-9] 不再手写：这张图由 _MODE_GRAPH 生成（上面那个函数）。
_MODE_TIMING: Dict[str, List[str]] = {
    m: _mode_timing_lines(m) for m in _MODE_GRAPH
}


# ============================================================
# Phase 定义（4 层配置）
# ============================================================
@dataclass(frozen=True)
class Phase:
    name: str
    anchor: str
    expand_order: str
    dual_spec: str
    ing_focus: str
    he_focus: str
    probe_focus: str
    view_focus: str
    target_hardness: str = "soft"
    objective: str = "truth"


PHASE_PRACTICE = Phase(
    name="修行",
    anchor=(
        "重述成「它是关于什么的」。\n"
        "不要把问题钉死成一个待答的题目——先把它放开，让它还是它自己。\n"
        "允许它还不是一个问题，只是一个处境。\n"
        "修行允许还没出来、允许悬置、允许此处未生。"
    ),
    expand_order="yin_first",
    dual_spec=(
        "【本层 0/1 的含义】\n"
        "0 = 还没显形的那一面；1 = 已经显形的那一面。这是问题内部的两端。\n"
        "【属性】已由展开来源确定，不用你判、也别猜：\n"
        "  阴视角展开出来的 → 0（还没显形），阳视角展开出来的 → 1（已显形）。\n"
        "【位置】唯一要你判断的维度。判的是：在锚点这句话里，这条候选所指的东西，\n"
        "  被问题本身触及、指向了没有。\n"
        "  锚点字面里已提到它、或直接指向它 → 1；\n"
        "  锚点里没有它、是你从问题外面拉进来的 → 0。（0/1/both）\n"
        "【重要 · 两条独立的线】\n"
        "- 属性问「本性」，位置问「锚点是否已触及它」，两者没有固定关系。\n"
        "- 判的是「锚点有没有碰到它」，不是「你有没有把它列出来」。\n"
        "  被列出来是候选的宿命，不是显形的证据。\n"
        "- 属性与位置一致是常态，不一致才是 &。\n"
        "  一致例：还没显形的东西，锚点也没提它 → 0×0，不是 &。\n"
        "  错位例：本性还没显形的东西，锚点却已经指向了它 → 0×1，是 &。\n"
        "  例：锚点问「能不能真正做前端设计」，候选「前端设计含 RTL/验证/综合」\n"
        "      → 锚点直接指向 → 位置 1；候选「责任归属决定授权」→ 锚点没提责任 → 位置 0。\n"
        "both 只在真的看不出偏向时才用；不要把两端都填 both，那是逃避判断。"
    ),
    ing_focus=(
        "这次对撞更偏「显现过程」：它是怎么一步步显出来的，\n"
        "而不是它长什么样。注意力放在显形的次序与节奏上。"
    ),
    he_focus=(
        "更多收「还没成形的」。\n"
        "本次沉淀优先选那些尚未定形、还在路上的东西；\n"
        "已经稳稳成形但互相冲突的，让给下一次。"
    ),
    probe_focus=(
        "修行允许还没出来、允许悬置（msg 130 §三）。\n"
        "但悬置不是停在那儿不动——这一圈没显形的，要问它还欠一个什么形状才肯出来。\n"
        "所以探针直接从具体的偏转点问进去：它到底卡在哪一处没错开，"
        "重排什么它才会裂开。\n"
        "不要急着把没闭合的东西收成一道待答的题；不许笼统地说「进一步展开」。\n"
        "一条合格的探针：读完就知道下一步要朝哪一边推、会松开什么。"
    ),
    view_focus=(
        "这个 view 是「一个事物被让它先静下来之后的显形」（msg 130 §三）。\n"
        "更偏「看到什么」，而不是「确定什么」。\n"
        "结论可以是开放的——它停在哪里，就说到哪里。\n"
        "\n"
        "v1.19 四段式（docs/三层递归蓝图.md §一）：\n"
        "一、这一路看到了什么（3-5 句）\n"
        "二、哪些还没看清（3-5 条）——只写两类：\n"
        "   悬空线头（不知道下一步往哪走）、& 印记（碰到了但撞不动）。\n"
        "   不要写「决定不碰」的（那些在第三段）。\n"
        "三、★ 我决定不碰什么，为什么——逐条写主动悬置。\n"
        "   每条：不碰什么 + 为什么 + 保持了多久 + 状态(active/stable)。\n"
        "   如果某个悬置被撤回了，也要写：什么被撤回了 + 为什么撤回。\n"
        "   ★ 关键区分：「没看清」是不知道，「撞不动」是过不去，\n"
        "     「决定不碰」是看清了、可以碰、但选择不碰。第三段只写第三种。\n"
        "   ★ 语气：**这是一个决定，不是一个遗憾。**\n"
        "     不要写「我没能做到」「我遗憾没有碰」。\n"
        "四、与问题相处的姿态（一段话）"
    ),
    objective="manifest",
)

PHASE_RESEARCH = Phase(
    name="研究",
    anchor=(
        "重述成「它到底在问什么」。\n"
        "要钉出一个可着力处——这个问题的支点在哪个词上。\n"
        "如果原问题散着，就把它收拢到能被回答的那一点。\n"
        "研究要求有所确定、有所指向；允许「未触及」，\n"
        "但不允许「不确定在哪」。"
    ),
    expand_order="yang_first",
    dual_spec=(
        "【本层 0/1 的含义】\n"
        "0 = 还没显形的那一面；1 = 已经显形的那一面。这是问题内部的两端。\n"
        "【属性】已由代码锚定：阴展开 → 0，阳展开 → 1。这是事实，别去推它。\n"
        "【位置】唯一要你判断的维度。判的是：在锚点钉出的那个着力点里，\n"
        "  这条候选所指的东西，被问题本身触及、指向了没有。\n"
        "  锚点字面里已提到/指向它 → 1；锚点里没有、是你从外面拉进来的 → 0。\n"
        "  （0/1/both）\n"
        "【重要】\n"
        "- 判的是「锚点有没有碰到它」，不是「你有没有把它列出来」。\n"
        "- 位置与属性（来源）没有固定关系：\n"
        "  从阴展开出来的（属性=0），锚点可能已指向它（1）也可能还没（0）；\n"
        "  从阳展开出来的（属性=1），锚点可能已指向它（1）也可能只是你展开的（0）。\n"
        "  不一致的地方才是 &。\n"
        "「偏向 1」只用于位置判不出的时候，别因此把位置全填 1。\n"
        "both 只在真的看不出偏向时才用。"
    ),
    ing_focus=(
        "这次对撞更偏「结构对撞」：结构之间哪里撑住、哪里塌了。\n"
        "少说它是怎么出现的，多说它的支撑点在哪里。"
    ),
    he_focus=(
        "更多收「已成形但冲突的」。\n"
        "本次沉淀优先选那些已经长成形、但彼此硬碰的东西；\n"
        "还没定形的，归到悬空线头。"
    ),
    probe_focus=(
        "研究要求有所确定、有所指向（msg 130 §四）。\n"
        "这一圈抓不住的，不该被笼统地再问一遍——"
        "要指出具体是哪一处还没答案，以及下一步该从哪个可下手的地方入手。\n"
        "探针可以带方向，甚至可以带一个最小可执行的动作，但必须可被证伪。\n"
        "一条合格的探针：读完就知道下一步要做什么、会显形什么。"
    ),
    view_focus=(
        "这个 view 是「一个事物被抓住之后，它四周的显形」（msg 130 §四）。\n"
        "更偏「确定什么」，而不是「看到什么」。\n"
        "要说清这次到底定下来了什么；没定下来的部分单独标出，不混进来。"
    ),
    target_hardness="hard",
    objective="truth",
)

PHASE_DUEL = Phase(
    name="对撞",
    anchor="透传（不重写）",
    expand_order="yin_first",
    dual_spec=(
        "【本层 0/1 的含义】\n"
        "【属性】已由展开来源确定，不用你判：\n"
        "  阴视角（没对上/张力）→ 0，阳视角（已对上/共鸣）→ 1。\n"
        "  真的各自成立、不可通约的情况，放到位置里用 both 表达。\n"
        "【位置】= 极性。判据在**决策层**，不在语义层（蓝图 §三）：\n"
        "  问的是「这条产物对它涉及的那条悬置分歧，是怎么裁决的」：\n"
        "    「不该碰」→ 偏 0\n"
        "    「必须碰」→ 偏 1\n"
        "    「视条件」→ 偏 both\n"
        "  也就是：该不该碰，不是对没对上。\n"
        "  ⚠️ msg 128 §二 的「已对齐 / 未对齐」是**语义层**判据，\n"
        "     蓝图 §三 已把它从对撞的极性上挪走——对撞的 0/1 是裁决，不是描述。\n"
        "     （语义层的「未对齐处」只用来**找材料**，归展开那一步；\n"
        "       不用来定极性。）\n"
        "【重要 · 两个独立的问题】\n"
        "- 属性说的是这条产物从哪一面长出来；位置说的是它怎么裁决。\n"
        "  本性共鸣（属性=1），完全可能被裁决为「不该碰」（位置=0）；\n"
        "  本性张力（属性=0），完全可能被裁决为「必须碰」（位置=1）。\n"
        "- 属性与位置一致是常态，不一致才是 &。\n"
        "both 只在真的「视条件」时才用，不是逃避判断。"
    ),
    ing_focus=(
        "让两个 view 正面相撞。不是比较，不是分析，不是折中。\n"
        "它的 0/1 不是问题本身的 0/1，是两个 view 之间的 0/1。\n"
        "判据（msg 128 §十）：会不会撞出一个原本不存在于任何一方的第三者？\n"
        "撞不出就诚实说「此处未生」——折中不是合法产出，未生是。"
    ),
    he_focus=(
        "& = 「这两个 view 在这一点上不能再被统一了」。\n"
        "不是未解决的冲突，是结构性的不可通约。\n"
        "两个 view 共同绕开的盲区不是 &，归悬空线头。"
    ),
    probe_focus=(
        "对撞要撞出一个原本不在任何一方里的第三者（msg 128 §十）。\n"
        "探针在这里是一次「重排」——改掉两端说话的顺序、或让它们换一个支点再撞。\n"
        "不许只是把两端的话再展开一遍，那不是对撞。\n"
        "一条合格的探针：读完就知道它要逼出哪一种重新对撞。"
    ),
    view_focus=(
        "这个 view 是「两个形状之间发生的事」（msg 128 §九）。\n"
        "不是修行 view，也不是研究 view——是两个形状相撞这件事本身。"
    ),
    target_hardness="mixed",
    objective="collision",
)

PHASE_META = Phase(
    name="元",
    anchor="透传（不重写）",
    expand_order="yang_first",
    dual_spec=(
        "【本层 0/1 的含义】（msg 132 §三）\n"
        "【属性】已由展开来源确定，不用你判：\n"
        "  阴视角（整体没被看见 / 没被收进去）→ 0，\n"
        "  阳视角（已确认 / 已吸收）→ 1。\n"
        "【位置】问这条候选所指的那个局部：\n"
        "  0 = 这个局部还没被 all 吸收进去；1 = 已经被吸收进去。\n"
        "【此刻】此刻 = 「全部都已经在了」这个状态本身。\n"
        "【重要】\n"
        "- 属性问的是「整体」，位置问的是「这条候选那个局部」——对象不同，\n"
        "  答案没有固定关系，别让它们互相迁就。\n"
        "- 一致例：整体已确认（1），某个局部也已被吸收（1）→ 1×1，不是 &。\n"
        "  错位例：整体已确认（1），但这条候选的某个局部没被收进去（0）→ 1×0，是 &。"
    ),
    ing_focus=(
        "不是让内容再撞一遍。是让「整体」和「每一个局部」对撞（msg 132 §四）：\n"
        "all 去问每个子 view「你为什么恰好凑成了我？」；\n"
        "每个子 view 去问 all「你包含了我没包含的什么？」\n"
        "msg 120 §十四：它的 ing 是「对三者本身再做一次」。"
    ),
    he_focus=(
        "最核心的 &：「整体 ≠ 局部之和」——\n"
        "任何 all 都不能被拆成它的部分之和，这是结构性的。\n"
        "共同绕开的盲区仍归悬空线头，不进 &。"
    ),
    probe_focus=(
        "元的 & 是「整体 ≠ 局部之和」（msg 132 §六）。\n"
        "探针是一次「重新划分」：不许只在现有的分法里补充，"
        "要指出哪个局部还没被整体消化——整体缺它不像缺了一块，"
        "而是整体本身的分法就缺了一维。\n"
        "一条合格的探针：读完就知道下一步要按什么重新切、会多出哪一摞。"
    ),
    view_focus=(
        "这个 view 不是内容之和，也不是关系之和（msg 132 §七）。\n"
        "是「几个 view 加在一起，作为一种显形方式，它是什么」。\n"
        "要说：all 作为整体的形态 / all 与局部不可通约处 /\n"
        "从整体·局部对撞里长出的新东西 / 一个新的姿态（与「完整」相处的方式）。"
    ),
    objective="closure",
)

PHASES = {
    "0": PHASE_PRACTICE,
    "1": PHASE_RESEARCH,
    "both": PHASE_DUEL,
    "all": PHASE_META,
}

ANTI_PRETTY = """
【反漂亮约束 · 最重要】
1. 不总结：不许用"综上所述"、"从本质上看"、"归根结底"、"总的来说"、
   "由此可见"、"不难发现"、"在这个意义上"。
2. 不装饰：不许比喻堆叠、不许华丽词藻、不许排比、不许排比式对仗。
3. 允许未生：如果这次撞不出新东西，就诚实说"此处未生"。
   宁可空，也不要凑数。宁少，也不要多。
"""

_BOILERPLATE = (
    "综上所述", "从本质上看", "归根结底", "总的来说",
    "由此可见", "不难发现", "在这个意义上", "总而言之",
)

# [P2-2] 「宁可空，不要凑」——展开阶段的显式规则。
# 实测：候选后半段（第 9-15 条）被自省判为「补写凑数，非展开生长」。
# 原因不是模型不会展开，是 prompt 写了「输出 0-8 条」——
# 模型把 8 当成了要交的作业量。
# [P2-9c] 两处一起改才算改完：
#   · 六处 prompt 的量词改成「能写几条写几条（8 是上限不是任务量）」
#   · NO_FILL_RULE 从末尾追加改成置顶（见 _expand_pair）
# 只做一半时，它在末尾仍然只是一句补充说明，照样灌水。
NO_FILL_RULE = """
【★ 宁可空，不要凑 · 展开阶段】
展开出几条就写几条。只能展开出 3 条就写 3 条，
一条都展开不出来就只写「（无）」。
不要把下面的东西当候选凑数：
  - 与锚点/原始问题无关的常识性补充；
  - 把上一轮、上游 view、或本层候选换个说法再说一遍；
  - 清单整理、分类标签、套话式的"还有……方面"。
凑出来的条数会在下游被判为可疑候选，比空着更糟。
"""

# [P2-2] 对偶判断的「宁可空，不要凑」。
# 实测：为了凑够 judgments 的条数，模型对本不该判（信息不足、与锚点无关）
# 的候选也硬判一个位置，判不出来就一律塞 both。条数看着齐了，
# 判断全是空的。这里明确允许少判，并把「不判」写成合法输出。
NO_FILL_JUDGE_RULE = """
【★ 宁可空，不要凑 · 判断阶段】
judgments 的条数**可以少于候选条数**。判得了几条就写几条。
以下情况**不要输出该条**，让它空着：
  - 这条候选的信息不足以定位它的位置；
  - 这条候选与锚点/原始问题无关，判它没有意义；
  - 你发现自己只是在凑一个「看起来合理」的位置。
★ 不要为了凑齐条数把判断不出的填成 both：both 是"真的看不出偏向"，
  不是"我没判"。空着比假判更受尊重。
★ 空着的条目下游按默认位置处理，不会被当成你判过。
"""

# [P2-1] 主动悬置 vs 硬边界：修行层探针必须分清的两件事。
# 实测产物里出现过「EDA 闭源许可曾被放在主动悬置里…它不是『选择不碰』，
# 而是材料外部的硬边界，推不动」——模型先写错，再自己撤回。
# 与其等它撤回，不如在 prompt 里把分界说死：推不动的进线头，不进悬置。
SUSPENSION_VS_THREAD_RULE = """
【★ 悬置与线头的分界 · 不要混装】
suspensions 只收【主动悬置】，形态必须是：
    「我看清了 X，可以碰，但选择不碰，因为 Y」
  判据：材料够、工具够、没有外部约束——你**有能力碰**，是选择不碰。
  reason 要按这个句式写，写不出 Y 就说明它不是主动悬置。
threads（悬空线头）只收【硬边界】：
    材料不够 / 工具限制 / 外部约束（许可、权限、闭源、制度、物理不可得）
  ——你推不动的点。它不是「不碰」，是「碰不动」。
★ 不要把「推不动」伪装成「选择不碰」：写进 suspensions 就是把边界
  说成了姿态，那是撒谎，下一圈会被当作还能开的选择重新拿出来。
★ 反过来也不要把「选择不碰」写进 threads：那是把主动权交出去。
★ 两者都可以为空。判不准就宁可都不写，别硬塞进其中一个。
"""

SOFT_TARGET = "这些方面尚未触及，**可参考**，允许完全忽略——继续你的悬置。"
HARD_TARGET = "这些方面尚未触及，**至少涉及其中一项**。"



# 「几乎相同」判据：去重 / 合并 / 悬置更新里判定两条是同一件事。
_DUP_SIM = 0.85

# ing 复述判定（_sent_is_rephrase）：换说法也抓，全新放过。
# ★ 有意不配置：样本只有 n=1，现在调是过拟合，等真跑样本再说。
_REPHRASE_SIM = 0.75
_REPHRASE_OVERLAP = 0.62
# sim3 的复述线。定在 0.62 —— 与 _REPHRASE_OVERLAP 同档，但 sim3 的
# 分母是并集、且 BM25 补权，同一档位下**误报显著少**（已由探针量化）。
_REPHRASE_SIM3 = 0.62

# 回流硬拦 / 事后核对的同条目判据（_banned_hit）。硬拦和核对必须共用
# 同一把尺子，否则会出现「已经拦下了，核对却说没违例」。
_BAN_SIM = 0.85
_BAN_OVERLAP = 0.70

# 自省点名「同一批问题没消化」的重复判据（_carry_is_repeat）。
_CARRY_REPEAT_SIM = 0.70
_CARRY_REPEAT_OVERLAP = 0.50

# 关键词 top_n：_overlap_coef / _kw 默认取前 N 个关键词。
_KW_TOP_N = 8

# 质量线索里没提成配置的其余触发线（提了配置的见 spiral.qc_*）。
_QC_BACKFILL_RATIO = 0.5     # 可疑候选占比 → candidates_backfilled
_QC_DIVERSITY_RATIO = 0.4    # 结构多样性 → *_all_same_structural
_QC_OVERLAP_POOL_RATIO = 0.7  # 候选与池的重合占比 → candidates_overlap_pool

# 双通道收敛 / 覆盖率达标线（_update_trackers）。
_TRACKER_COVERAGE = 0.7
_TRACKER_CLARITY = 0.6

# 四象限对齐的匹配率分档（unaligned / low / ok）。
_ALIGN_MATCH_LO = 0.1
_ALIGN_MATCH_OK = 0.3

# 并行模式自动决策的置信度下限（低于它且非 serial 就退回 serial）。
_PARALLEL_CONF_MIN = 0.5

# 「中等相似度」散点：值不统一、语义分散，各收成一个命名常量。
# 这些不是成对互补阈值，是单一口径，改之前看清它各自管哪条线。
_SUSP_SAME_SIM = 0.8   # 悬置更新：新目标与既有目标的「同一件事」
_TAKE_SIM = 0.75       # 探针取件：命中已在重点清单里的那条
_QC_POOL_SIM = 0.60    # 质量检查：候选与池里已有条目的重合
_QC_DUP_SIM = 0.70     # 质量检查：候选彼此的重叠
_COV_OVERLAP_MIN = 0.50  # covers 语言判据：探针问题与未触及项的 overlap 下限
_MERGE_SIM = 0.70      # 合并可判定性通道：结构条目去重

# 池内去重阈值。**这两个值等价于上一版 Pool.merge 内的硬编码字面量**
# （0.9 / 0.85），提取出来只是为了让「参数按层可覆盖」这条红线
# 在池内也成立 —— 原来是 4 处字面量、一处都改不了。默认值与旧行为
# 逐位相同，改它才会变行为。
_DEDUP_SIM = 0.90        # amp / thread / probe 入池去重
_DEDUP_SUSP_SIM = 0.85   # 悬置目标去重


def _spiral_num(config, key, default):
    """读 spiral 段的一个数值配置；缺失或非数时回落到默认值。"""
    try:
        return float((config.get("spiral") or {}).get(key, default))
    except (TypeError, ValueError):
        return default


_RUNTIME_SWITCHES = ("auto", "on", "off")
# ★ 可选值**不是我拍的**：出厂 `dgtf_config.yaml` 的注释里记着项目
#   2026-10-02 的实测结论 —— `effort = low / high / max`（没有 medium）。
#   凡「写一个枚举」都要先在**本仓库**里找它的权威来源（这里就在
#   dgtf_config.yaml 的 thinking 注释段），别凭先验写。
_RUNTIME_EFFORTS = ("auto", "low", "high", "max")

# 开关的字面别名 -> 归一值。交互里允许用户敲 y/n/1/0/开/关 这类。
#   ★ 只归一**明确**的别名；认不出一律返回 None（由调用方报错），
#     绝不静默回落到 auto —— 「敲错了但没反应」是最难查的一类。
_RUNTIME_SWITCH_ALIASES = {
    "": "auto", "a": "auto", "auto": "auto",
    "默认": "auto", "缺省": "auto", "按配置": "auto",
    "on": "on", "y": "on", "yes": "on", "1": "on",
    "true": "on", "开": "on", "启用": "on", "打开": "on",
    "off": "off", "n": "off", "no": "off", "0": "off",
    "false": "off", "关": "off", "禁用": "off", "关闭": "off",
}


def _normalize_runtime_switch(raw) -> Optional[str]:
    """归一开关：auto/on/off；认不出返回 None（**不静默回落**）。"""
    return _RUNTIME_SWITCH_ALIASES.get(str(raw or "").strip().lower())


def _normalize_runtime_effort(raw) -> Optional[str]:
    """归一强度：auto/low/high/max。

    ★ **空输入（回车）= auto** —— 交互提示里写的就是「回车=auto」。
      第一版漏了这条：`""` 不在 `_RUNTIME_EFFORTS` 里 ⇒ 返回 None
      ⇒ 交互里按回车会被当成「非法输入」**反复重问**（死循环感），
      而 CLI/yaml 两边都走默认值所以看不出来 —— 只有真跑交互才发现。
    认不出的（如 "mediun"）仍返回 None，由调用方报错、不静默回落。
    """
    v = str(raw or "").strip().lower()
    if v in ("", "a", "auto", "默认", "缺省", "按配置"):
        return "auto"
    return v if v in _RUNTIME_EFFORTS else None


def _runtime_thinking_on(cfg: dict) -> bool:
    """本跑「思考」到底是不是开的（看 `default`；stages 由总控同步）。"""
    _th = ((cfg or {}).get("api") or {}).get("thinking") or {}
    return str(_th.get("default") or "").strip().lower() == "enabled"


def _apply_runtime(base_cfg: dict, runtime=None):
    """ 把运行期总控**写进**具体配置键。返回 `(新 cfg, 留痕行)`。

    ★ **纯函数**：深拷一份再改，**绝不改入参**。交互循环若就地改 cfg，
      用户第二轮选 "auto" 就会读到第一轮被改过的值 —— 「auto」会
      变成「跟上一次一样」，那是**另一个语义**。
    ★ 用 `json` 往返做深拷（与 `load_config` 同一手法，不引入 `copy`）。
      若 cfg 里有不可 JSON 化的对象，这里**应当**炸 —— 换成浅拷会把
      「不改入参」这条保证静默破坏掉（嵌套 dict 仍是同一个对象）。
    """
    cfg = json.loads(json.dumps(base_cfg or {}))
    rt = dict(runtime if runtime is not None else (cfg.get("runtime") or {}))
    notes: List[str] = []

    # ---- ① 联网总开关：`web_search.enabled` ----
    web = _normalize_runtime_switch(rt.get("web", "auto"))
    if web is None:
        notes.append("⚠️ runtime.web 取值非法（%r），已忽略（可选 auto/on/off）"
                     % (rt.get("web"),))
    elif web != "auto":
        cfg.setdefault("web_search", {})["enabled"] = (web == "on")
        notes.append("联网：强制**%s**（runtime.web=%s）"
                     % ("开" if web == "on" else "关", web))

    # ---- ② 思考总开关：`default` + **整张 stages 表** ----
    #   ★ 只改 default 是不够的：`LLM.call` 的优先级是
    #     「显式 thinking > stage 配置 > default」，stage 表会**盖住**
    #     default ⇒ 「总开关」变成一句空话（`check_v1234_runtime` 与
    #     探针的变异体 M2 专门钉这一条）。
    th = _normalize_runtime_switch(rt.get("thinking", "auto"))
    if th is None:
        notes.append("⚠️ runtime.thinking 取值非法（%r），已忽略"
                     % (rt.get("thinking"),))
    elif th != "auto":
        _thc = cfg.setdefault("api", {}).setdefault("thinking", {})
        _val = "enabled" if th == "on" else "disabled"
        _thc["default"] = _val
        _stages = _thc.get("stages") or {}
        for _k in list(_stages):
            _stages[_k] = _val
        _thc["stages"] = _stages
        notes.append("思考：强制**%s**（runtime.thinking=%s；%d 个环节档位"
                     "一并改写）"
                     % ("开" if th == "on" else "关", th, len(_stages)))
        if th == "on":
            notes.append("   ★ 思考开 ⇒ 每次调用 `max_tokens ≥ 32000`，"
                         "成本显著上升（这是**成本决策**）。")

    # ---- ③ 思考强度：`api.thinking.effort` ----
    ef = _normalize_runtime_effort(rt.get("effort", "auto"))
    if ef is None:
        notes.append("⚠️ runtime.effort 取值非法（%r），已忽略（可选 %s）"
                     % (rt.get("effort"), "/".join(_RUNTIME_EFFORTS)))
    elif ef != "auto":
        cfg.setdefault("api", {}).setdefault("thinking", {})["effort"] = ef
        notes.append("思考强度：%s（runtime.effort=%s）" % (ef, ef))

    if ef not in (None, "auto") and not _runtime_thinking_on(cfg):
        notes.append("⚠️ 强度已设为 %s，但本跑**思考是关的** ⇒ 强度不生效"
                     "（`effort` 只在 thinking 开启时随请求发出）" % ef)
    # ---- ⑤ 留痕：把**本次真正请求的**三项写回副本的 `runtime` 段 ----
    #   ★ 只写副本、不改入参。不这么做的话，产物里的 `requested` 永远
    #     是 yaml 的值 —— 命令行/交互给的三项在产物里**看不到**，
    #     「这跑到底是谁决定的」又成黑箱（与 served_by 同理）。
    #   ★ 用 `dict(cfg.get("runtime") or {})` 起底再覆写三个键：既不丢
    #     未来可能新增的键，又保证这三项一定是**本次请求**的值。
    #     三项都给 "auto" 时结果与出厂 `runtime` 段逐字相同 ⇒ 判据
    #     `T1`（auto 恒等）仍然成立。
    #   ★ 记的是**归一后**的值，不是原始输入：非法输入由上面各条的
    #     `⚠️` 留痕负责报告，而 `runtime` 段本身要保持一条**可断言的不变式**
    #     ——「三个值永远在合法集合内」。把 `"yes_please"` 原样写进去的话，
    #     产物里会出现一个下游谁都不认的值（而且判据 `T7` 的
    #     「非法值不改配置」会当场判红 —— 实测就是它先发现的）。
    _rec = dict(cfg.get("runtime") or {})
    for _k, _n in (("web", web), ("thinking", th), ("effort", ef)):
        _rec[_k] = _n if _n is not None else "auto"
    cfg["runtime"] = _rec
    return cfg, notes


def _runtime_snapshot(cfg: dict) -> dict:
    """本跑**实际生效**的三项读数（写进产物，供复盘）。"""
    _ws = (cfg or {}).get("web_search") or {}
    _th = ((cfg or {}).get("api") or {}).get("thinking") or {}
    _st = dict(_th.get("stages") or {})
    _on = sorted(k for k, v in _st.items()
                 if str(v).strip().lower() == "enabled")
    return {
        "requested": dict((cfg or {}).get("runtime") or {}),
        "web_enabled": bool(_ws.get("enabled")),
        "thinking_default": str(_th.get("default") or ""),
        "thinking_stages_enabled": _on,
        "thinking_stages_off_n": len(_st) - len(_on),
        "effort": str(_th.get("effort") or ""),
    }


def _runtime_summary_line(cfg: dict) -> str:
    """一行人类可读的生效摘要（交互与 CLI **共用**，避免两处各写一份）。"""
    s = _runtime_snapshot(cfg)
    return ("联网 %s | 思考 %s（%d 个环节开档 / %d 关）| 强度 %s"
            % ("开" if s["web_enabled"] else "关",
               "开" if _runtime_thinking_on(cfg) else "关",
               len(s["thinking_stages_enabled"]), s["thinking_stages_off_n"],
               s["effort"] or "—"))

# ============================================================
# 停止判据：结构饱和度判定的落点
# ============================================================
# 「本圈新 & 是否引入了新的结构维度」这件事，语义判定比词集重叠准：
# 实测（真跑产物）研究层 16 条 & 两两词集重叠**峰值 0.45**、达标 0 对，
# 而 LLM 两次都判「无新维度（仅换措辞 / 与上圈逐字相同）」。
# 所以 sat 判定的结论必须能真正改变停止行为 —— 它此前只对研究层生效
# （元层判出来只打一行日志，于是元层结构上不可能自然停）。
# 本函数是「sat 判定 → 两条计数」的唯一实现，serial 与并行 B 共用。


def _sat_override(entry, sat_verdict, idle_new_amp, idle_stall,
                  r_idle_limit, r_stall_limit):
    """sat 判「无新维度」时，把计数推到各自的停止门槛。

    ★ 为什么**四层同等生效**：判据问的是「本圈新 & 有没有引入新的结构
      维度」，与层无关（四层都产 &）。此前只有研究层推计数 —— 元层
      （跑得最多的层）判出「无新维度」只打日志。
    ★ 0 层没有「无新 &」这条通路（`_stop_reasons` 的条件 2 排除了 "0"），
      它的落点是 `idle_stall`（条件 3，四层通用）；`sat_override` 只
      影响条件 2 的理由文案，故 0 层返回 False。

    返回 `(idle_new_amp, idle_stall, sat_override)`。
    """
    if sat_verdict is not False:
        return idle_new_amp, idle_stall, False
    return (max(idle_new_amp, r_idle_limit),
            max(idle_stall, r_stall_limit),
            entry != "0")




# ============================================================
# 工具函数
# ============================================================
def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", str(text))
    if not text:
        return []
    if HAS_JIEBA:
        return [t for t in jieba.cut(text) if len(t) >= 2 and t not in _STOPWORDS]
    return [text[i:i+2] for i in range(len(text) - 1)]


def _kw(text: str, top_n: int = 8) -> set:
    toks = _tokenize(text)
    if not toks:
        return set()
    from collections import Counter
    return {k for k, _ in Counter(toks).most_common(top_n * 2)}


def _sim_ratio(a: str, b: str) -> float:
    """相似度数值（0.0–1.0）。"""
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if min(len(a), len(b)) <= 8:
        return 1.0 if (a in b or b in a) else 0.0
    ka, kb = _kw(a), _kw(b)
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / max(len(ka), len(kb))


def _similar(a: str, b: str, threshold: float = 0.75) -> bool:
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return False
    if a == b:
        return True
    if min(len(a), len(b)) <= 8:
        return a in b or b in a
    ka, kb = _kw(a), _kw(b)
    if not ka or not kb:
        return a == b
    return len(ka & kb) / max(len(ka), len(kb)) >= threshold


def _cross_round_dedup(items, overlap_thr=0.70,
                       sim_thr=0.75, max_n=None):
    if not items:
        return []
    kept = []
    for it in items:
        d = str(it.get("desc", "")).strip()
        if not d:
            continue
        dup = False
        for k in kept:
            kd = str(k.get("desc", "")).strip()
            if not kd:
                continue
            if (_overlap_coef(d, kd) >= overlap_thr
                    or _similar(d, kd, sim_thr)):
                dup = True
                break
        if not dup:
            kept.append(it)
    if max_n is not None and len(kept) > max_n:
        kept = kept[:max_n]
    return kept


_ALL_DRIFT_MARKERS = (
    "view0", "view1", "view both",
    "两个 view", "多个 view", "三个 view", "四个 view",
    "对撞层", "研究层", "修行层",
)
# 语义上也指「别层」，但可能同时是题目自己的词，所以不参与判定。
# 留着备查：将来若要做人工复核清单，这三个词是候选。
_ALL_DRIFT_SOFT_MARKERS = ("两边", "两侧", "上游")


def _all_candidate_drift_rate(candidates):
    """all 层候选里有多少条是在描述别层的东西（而不是新东西）。

    只数 _ALL_DRIFT_MARKERS（强标记）。_ALL_DRIFT_SOFT_MARKERS 不计，
    理由见上面那段。
    """
    if not candidates:
        return 0.0
    n = 0
    for c in candidates:
        d = str(c.get("desc", ""))
        if any(m in d for m in _ALL_DRIFT_MARKERS):
            n += 1
    return n / len(candidates)


_SELF_REF_MARKERS = (
    "这句话本身", "本层候选", "all 的候选", "这个说法本身",
    "本句", "本圈", "这条候选", "本层", "这句话",
    "这个说法", "上述说法", "这一条本身",
)


def _all_candidate_selfref_rate(candidates) -> float:
    if not candidates:
        return 0.0
    n = 0
    for c in candidates:
        d = str(c.get("desc", ""))
        if any(m in d for m in _SELF_REF_MARKERS):
            n += 1
    return n / len(candidates)


_UNSAID_MARK = "此处未生"

# [P2-4] 一圈里「此处未生」出现多少处，就从诚实姿态变成逃避。
UNSAID_ESCAPE_LIMIT = 3


def _count_unsaid(view) -> Tuple[int, str]:
    """数这一圈产物里出现了几处「此处未生」，并说出分布在哪。

    「此处未生」是宪法允许的诚实姿态（折中不是合法产出，未生是）。
    但每次都拿它收尾就成了套路：探针没有真的往里推，
    用一句"未生"把该走的路结掉。这里给出硬证据，
    交给 self_check 去判它是不是逃避。
    """
    buckets = [
        ("ing", str(getattr(view, "collision", "") or "")),
        ("view", str(getattr(view, "manifest", "") or "")),
        ("线头", "\n".join(str(t.get("desc", ""))
                           for t in (getattr(view, "threads", None) or [])
                           if isinstance(t, dict))),
        ("&", "\n".join(str(a.get("desc", ""))
                        for a in (getattr(view, "amps", None) or [])
                        if isinstance(a, dict))),
        ("不可判定通道", str(
            (getattr(view, "undecidable_product", None) or {}).get(
                "why_undecidable", "") or "")),
    ]
    total = 0
    where = []
    for name, text in buckets:
        if not text:
            continue
        n = text.count(_UNSAID_MARK)
        if n:
            total += n
            where.append(f"{name}×{n}")
    return total, "、".join(where)


# [P2-8] 自省派生的质量线索：合并后重算 quality_flags 时必须保住。
# unsaid_overused / candidates_backfilled 是 _self_check 在圈内按自省判据
# 追加的，而 _quality_check 只看产物统计、不知道这两件事 —— 直接整体重算
# 会把它们抹掉，让「此处未生超标」这条线索活不到 md。
_SELFCHECK_FLAGS = ("unsaid_overused", "candidates_backfilled")

_V122_HARD_FLAGS = ("action_incomplete", "not_do_missing",
                    "action_fields_missing")

# 重算 quality_flags 时**必须保住**的全部家族。
_PRESERVED_FLAGS = _SELFCHECK_FLAGS + _V122_HARD_FLAGS


def _keep_selfcheck_flags(view, new_flags):
    """重算 quality_flags 后，把「不该被重算冲掉」的线索补回去（不重复）。

    保两类：自省派生线索（`_SELFCHECK_FLAGS`）+ 硬约束 flag
    （`_V122_HARD_FLAGS`，v122 阶段 3 加）。
    """
    kept = [f for f in (getattr(view, "quality_flags", None) or [])
            if any(k in str(f) for k in _PRESERVED_FLAGS)]
    out = list(new_flags or [])
    for f in kept:
        if not any(str(f) == str(x) for x in out):
            out.append(f)
    return out


def _banned_hit(desc: str, banned: List[str]) -> str:
    """这条候选是不是命中了禁条目清单（命中则返回命中的那条原文）。

    [P2-9] 硬拦截和事后核对必须共用同一个判据，否则会出现
    「已经拦下了，核对却说没违例」的自相矛盾。
    """
    d = (desc or "").strip()
    if not d:
        return ""
    for b in (banned or []):
        b = str(b).strip()
        if not b:
            continue
        if _similar(d, b, _BAN_SIM) or _overlap_coef(d, b, _KW_TOP_N) >= _BAN_OVERLAP:
            return b
    return ""


def _sent_is_rephrase(s: str, u: str, corpus=None) -> bool:
    """一句 ing 输出是不是这句上游话的复述。

    [P2-3] 原来只用一个判据：_similar(s, u, 0.75)，
    分母是 max(|kw(A)|, |kw(B)|)。一句 20 字上游话被扩写成 60 字，
    关键词交集不变、分母变大 → 相似度掉到阈值以下 → 换说法抓不到。

    ★ 主判据换成 `_sim3`（对称 Jaccard + BM25）：v1.23.25 用
      `_overlap_coef`（分母 min）补那个缺口，它确实抓得到「短句被长句
      整段包住」，但同一个 min 分母让**两条 3 词短语共享 1 个名词就
      得 0.5** —— 误报面大于收益。`_sim3` 用并集分母消除虚高，
      BM25 的 IDF 再把罕见词的权重补回来。
    ★ `_overlap_coef` 那一条**不删**：它管的是「包住形状」这个
      特定几何（s 的几乎全部关键词都在 u 里），是 sim3 抓不到的一类。
      两条判据各管各的形状，见下。
    """
    # ★ sim3 提到**首判**：结构层（T 编号）短路必须先于字面尺子生效，
    #   否则宽尺子（_similar / _overlap_coef 的 min 分母）会在 sim3
    #   之前命中，让 sim3 这条线在行为上**不可观测**（变异体 M1 实测）。
    #   **行为等价性已实测**：8000 组随机对零差异 —— sim3 的分是
    #   `0.4*jaccard + 0.6*bm`，其中 jaccard ≤ overlap_coef 恒成立，
    #   故 sim3 先判不会多抓。调序只为可观测，不改语义。
    if _sim3(s, u, corpus=corpus) >= _REPHRASE_SIM3:
        return True
    if _similar(s, u, _REPHRASE_SIM):
        return True
    # 包住形状保底：分母 min ⇒ 短句整段落在长句里时接近 1
    return _overlap_coef(s, u, _KW_TOP_N) >= _REPHRASE_OVERLAP


def _detect_ing_rephrase(ing_text: str,
                         upstream_texts: List[str]) -> Optional[float]:
    """检测 ing 输出是否复述了上游的话。

    ★ upstream_texts 里**只放上游 view 的 manifest / collision**。
    本层候选不是上游：ing 本来就是吃候选的，把候选算进"上游"会让
    正常对撞被误判成复述（v1.21.54 的错误，[P2-3] 已修）。
    """
    if not ing_text or not upstream_texts:
        return None
    if ing_text.strip() in ("", f"（{_UNSAID_MARK}）"):
        return None
    _sent_split = re.compile(r"[。！？\n]+")
    ing_sents = [s.strip() for s in _sent_split.split(ing_text)
                 if len(s.strip()) >= 12]
    if len(ing_sents) < 3:
        return None
    upstream_sents: List[str] = []
    for t in upstream_texts:
        for s in _sent_split.split(str(t or "")):
            s = s.strip()
            if len(s) >= 12 and _UNSAID_MARK not in s:
                upstream_sents.append(s)
    if not upstream_sents:
        return None
    # ★ 语料只编一次：同一圈内所有句子判定共用同一把尺子，
    #   否则 IDF 随调用次序变，同一对句子会给出不同的分。
    corpus = _bm25_corpus(upstream_sents)
    hits = 0
    for s in ing_sents:
        if any(_sent_is_rephrase(s, u, corpus=corpus)
               for u in upstream_sents):
            hits += 1
    return hits / len(ing_sents)


def _overlap_coef(a: str, b: str, top_n: int = 8) -> float:
    """overlap coefficient：|A ∩ B| / min(|A|, |B|)。"""
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return 0.0
    ka = _kw(a, top_n)
    kb = _kw(b, top_n)
    if not ka or not kb:
        return 0.0
    inter = len(ka & kb)
    if inter == 0:
        return 0.0
    return inter / min(len(ka), len(kb))


# ------------------------------------------------------------
# BM25 语料统计（sim3 的稀疏通道）
#
# 为什么需要它：`_overlap_coef` 是**平权词袋**（谁出现都算 1），
# 于是「模型」和「是」权重相同；且分母取 min，短句共享 1 个名词即
# 0.5~0.67。BM25 补两件事：① IDF 让罕见词更重；② 文档长度归一化
# 让长短可比。纯 Python，不引入依赖、不训练。
#
# 语料来源：**本圈池内条目**（amp/thread/probe 的描述 + 本次比对的
# 两侧文本）。N 很小时 IDF 会退化 —— 故设 _BM25_MIN_CORPUS，
# 语料不足则 sim3 回落到结构层 / 字面层。
# ------------------------------------------------------------
_BM25_K1 = 1.5          # 词频饱和参数（文献默认 1.2~2.0）
_BM25_B = 0.75          # 文档长度归一化强度（文献默认 0.75）
_BM25_MIN_CORPUS = 4    # 语料 < 4 篇时 BM25 不可靠，跳过该通道


def _bm25_corpus(items) -> tuple:
    """把一批文本编成 BM25 语料。

    返回 (doc_tfs, dfs, avgdl, N)：
      doc_tfs : List[Counter]  每篇的词频表
      dfs     : dict           每个词出现在多少篇里
      avgdl   : float          平均长度（词数）
      N       : int            篇数
    """
    from collections import Counter as _C
    doc_tfs = []
    dfs = {}
    for it in items:
        toks = _tokenize(str(it or ""))
        if not toks:
            continue
        tf = _C(toks)
        doc_tfs.append(tf)
        for t in tf:
            dfs[t] = dfs.get(t, 0) + 1
    n = len(doc_tfs)
    if not n:
        return [], {}, 0.0, 0
    avgdl = sum(sum(tf.values()) for tf in doc_tfs) / n
    return doc_tfs, dfs, avgdl, n


def _bm25_best(query: str, corpus) -> float:
    """query 对语料内每篇算 BM25，返回**归一化后的最大分**（0~1）。

    归一化：raw / (raw + k1)，把无上界的 BM25 压回 [0,1) 区间，
    使 sim3 三层可加权平均。**这是工程取舍，不是 BM25 原式。**
    """
    doc_tfs, dfs, avgdl, n = corpus
    if not n or n < _BM25_MIN_CORPUS or avgdl <= 0:
        return 0.0
    q_toks = _tokenize(query)
    if not q_toks:
        return 0.0
    import math as _m
    best = 0.0
    for tf in doc_tfs:
        dl = sum(tf.values())
        s = 0.0
        for t in set(q_toks):
            f = tf.get(t, 0)
            if not f:
                continue
            idf = _m.log(1.0 + (n - dfs.get(t, 0) + 0.5) / (dfs.get(t, 0) + 0.5))
            denom = f + _BM25_K1 * (1.0 - _BM25_B + _BM25_B * dl / avgdl)
            s += idf * (f * (_BM25_K1 + 1.0)) / denom
        if s > best:
            best = s
    if best <= 0:
        return 0.0
    return best / (best + _BM25_K1)


def _bm25_pair(query: str, doc: str, corpus) -> float:
    """**两篇之间**的 BM25（query 打 doc），IDF 取整份语料。

    与 `_bm25_best` 的区别：后者是「query 对语料每篇取最大」——
    测的是 **query 与语料的相关性**，不是 **query 与 doc 的相似度**。
    两条各自与语料相关、但彼此无关的句子，用 best 会拿到虚高分。
    这里只累加 **doc 里真实出现** 的 query 词 ⇒ 不相干必为 0。

    ★ IDF 仍用整份 corpus：corpus 在这里只提供**词的稀有度**
      （N 与 df），不参与打分。这样同一批调用共享同一把尺子。
    """
    doc_tfs, dfs, avgdl, n = corpus
    if not n or n < _BM25_MIN_CORPUS or avgdl <= 0:
        return 0.0
    d_toks = _tokenize(doc)
    if not d_toks:
        return 0.0
    from collections import Counter as _C
    import math as _m
    d_tf = _C(d_toks)
    dl = len(d_toks)
    s = 0.0
    for t in set(_tokenize(query)):
        f = d_tf.get(t, 0)
        if not f:
            continue
        idf = _m.log(1.0 + (n - dfs.get(t, 0) + 0.5) / (dfs.get(t, 0) + 0.5))
        denom = f + _BM25_K1 * (1.0 - _BM25_B + _BM25_B * dl / avgdl)
        s += idf * (f * (_BM25_K1 + 1.0)) / denom
    if s <= 0:
        return 0.0
    return s / (s + _BM25_K1)


def _jaccard(a: str, b: str, top_n: int = _KW_TOP_N) -> float:
    """对称 Jaccard：|A∩B| / |A∪B|。分母是**并集**（与 _overlap_coef 的
    min 相反）—— 这是「两侧都要有」的尺子，短句共享 1 词不会虚高。"""
    ka, kb = _kw(a, top_n), _kw(b, top_n)
    if not ka or not kb:
        return 0.0
    return len(ka & kb) / len(ka | kb)


def _sim3(a: str, b: str, corpus=None, top_n: int = _KW_TOP_N) -> float:
    """三级相似度：结构 ⊃ 字面 ⊃ 稀疏。返回 0.0~1.0。

    设计要点（对照 v1.23.25 的 `_overlap_coef`）：
      · **不做 min 分母**：min 分母只在「短句整段被长句包住」时有意义，
        那一处（复述检测）由 `_sent_is_rephrase` 单独用 `_overlap_coef`
        保底，不在这里复用。
      · **对称**：`sim3(a,b) == sim3(b,a)`（幂等自检可逐位验证）。
      · **语料不足自动降级**：corpus 为 None 或篇数 < 4 时只用字面层，
        结果仍可比（同一批调用共享同一降级路径）。
    """
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    # L4 结构层：两侧都是「T3」式编号且相等 ⇒ 同一个方面，直接 1.0
    if a == b:
        return 1.0
    ma, mb = re.fullmatch(r"T?(\d+)", a), re.fullmatch(r"T?(\d+)", b)
    if ma and mb:
        return 1.0 if ma.group(1) == mb.group(1) else 0.0

    # L1 字面层：Jaccard（对称，不虚高）
    jac = _jaccard(a, b, top_n)

    # L2 稀疏层：BM25（需要语料）
    bm = 0.0
    if corpus is not None:
        # ★ 必须是 **a 与 b 之间** 的 BM25，不是「各自对语料」。
        #   `_bm25_best` 测的是「与语料的相关性」—— 两条各自与语料
        #   相关、彼此无关的句子会被抬到 0.7+（实测虚高，见 Step8
        #   脚本头注）。`_bm25_pair` 只累加双方共有的词 ⇒ 无关必 0。
        bm1 = _bm25_pair(a, b, corpus)
        bm2 = _bm25_pair(b, a, corpus)
        bm = (bm1 + bm2) / 2.0

    if bm > 0.0:
        return 0.4 * jac + 0.6 * bm
    return jac


def _sim3_pair(a: str, b: str, corpus=None, top_n: int = _KW_TOP_N):
    """返回 (sim3, 分解) —— 便于探针/变异体定位是哪一层给出的分。"""
    s = _sim3(a, b, corpus=corpus, top_n=top_n)
    jac = _jaccard(a, b, top_n)
    bm = 0.0
    if corpus is not None:
        bm = (_bm25_best(a, corpus) + _bm25_best(b, corpus)) / 2.0
    return s, {"jaccard": round(jac, 4), "bm25": round(bm, 4)}


SUSPENSION_STATUS = ("active", "stable", "resolved", "revoked")

# ── [A1 方面单元] 方面单元（AspectUnit）的封闭枚举与**单一构造点** ──
#  ★ 为什么要有常量：`ground` / `polarity` 会被判据逐字比对，
#    散在各处写字面量 = 迟早出现「同一件事两种写法」。
#  ★ `text` 与旧键 `desc` **同值**：AspectUnit 是「旧 dict 加几个键」，
#    不是新类型 ⇒ 全部 `.get("desc")` 读取点零改动。
_ASPECT_GROUNDS = ("anchor", "pool", "upstream", "judge", "expand")
_ASPECT_POLARITIES = ("阴", "阳")


# ── [D1/D2 信念四态] 信念条目（BeliefItem）与四态迁移 ──────────────
#  ★ `status` **复用** SUSPENSION_STATUS —— 不新增枚举。
#  ★ 迁移规则写成**模块级纯函数**：判据可以脱离引擎直接喂它（可负对照），
#    也避免「同一件事两条实现」（本项目老坑）。
_BELIEF_STATUS = SUSPENSION_STATUS          # ← 别名，不是新枚举

#: `active → stable` 需要的**连续圈数**（D2 的 k）。
_BELIEF_STABLE_K = 2
#: `active → stable` 需要的**不同来源数**（D2 的 ≥2 个独立来源）。
_BELIEF_STABLE_SOURCES = 2
#: `* → revoked` 需要的**不同攻击来源数**（与 stable 的**镜像门槛**）。
#   ★ 为什么是「不同来源数」而不是「攻击次数」：见 `belief_transition`
#     ② 号注 —— 次数口径在真实入口会退化成「一直骂就赢」。
_BELIEF_REVOKE_SOURCES = 2


def make_belief_item(text, ground="", status="active", item_id="",
                     support=None, attack=None, rounds_seen=None,
                     semantic_entropy=None):
    """构造一个 BeliefItem（dict）—— **全工程唯一构造点**。

    ★ `status` 不在 `_BELIEF_STATUS` 里时**归一化到 "active"**（不抛错）：
      状态越界不该让整条主张消失 —— 那是「失败留痕」的反面。
    ★ `semantic_entropy` 默认 `None`（**不是 0.0**）：D3 还没算过与
      「算出来是 0」是两回事，印 0.00 就是自欺（本项目老坑）。
    """
    s = str(text or "").strip()
    if not s:
        return {}
    st = str(status or "").strip()
    if st not in _BELIEF_STATUS:
        st = "active"
    return {
        "id": str(item_id or ""),
        "text": s[:200],
        "ground": str(ground or ""),
        "status": st,
        "support": [str(x) for x in (support or [])],
        "attack": [str(x) for x in (attack or [])],
        "rounds_seen": list(rounds_seen or []),
        "semantic_entropy": semantic_entropy,
        #: [D3 修正] 该条目**自身**的历次独立出现：(来源标签, 该次文本)。
        #: 语义熵只对**同一主张的历次出现**有意义 —— 不是「本条目 + 全池
        #: 其他条目」（那会把异质文本混进来，簇全异 ⇒ 熵恒为上界，读数无
        #: 信息量）。登记与去重解耦：同一 (源, 文本) 只记一次。
        "occurrences": [],
    }


def belief_transition(item, *, round_no=0, sources=None, attack=None,
                      resolved_by=None, attack_sources=None,
                      revoke_sources=None):
    """D2 迁移规则：返回**新状态**（纯函数，不改入参）。

    参数语义：
      · `round_no`    本圈号 —— 记进 `rounds_seen`（同一圈不重复记）
      · `sources`     本圈**独立复现**这条主张的来源标签列表
                      （如 ["probe#2","th#1"]）—— 进 `support`
      · `attack`      本圈新出现的攻击证据标签列表 —— 进 `attack`
      · `attack_sources` 本圈**提出攻击的来源标签**（层名）—— 进
                      `attack_sources`。★ 与 `sources` 对称：判决用
                      「独立性」这一把尺子量两侧，不用次数。
      · `resolved_by` 非空 ⇒ 被 decidable_channel 回答 ⇒ `resolved`

    ★ 优先级（写死，可负对照）：resolved > revoked > stable > 保持原状。
      为什么 resolved 最高：停止与清算分开 ⇒ 一旦被可判定通道回答，
      其余的「稳不稳 / 被不被质疑」都不再是这条主张的问题。
    """
    if not item:
        return "active"
    _cur = str(item.get("status") or "active")
    if _cur not in _BELIEF_STATUS:
        _cur = "active"

    # ① resolved：被可判定通道回答 ⇒ 直接清偿（最高优先级）
    if str(resolved_by or "").strip():
        return "resolved"

    _sup = list(item.get("support") or [])
    _atk = list(item.get("attack") or [])
    _atk_src = list(item.get("attack_sources") or [])
    _rnd = [r for r in (item.get("rounds_seen") or [])]
    _seen = set()
    for _r in _rnd:
        try:
            _seen.add(int(_r))
        except (TypeError, ValueError):
            continue
    try:
        _rn = int(round_no or 0)
    except (TypeError, ValueError):
        _rn = 0

    # 累积本圈的复现来源与本圈的圈号
    for _s in (sources or []):
        _s = str(_s).strip()
        if _s and _s not in _sup:
            _sup.append(_s)
    for _a in (attack or []):
        _a = str(_a).strip()
        if _a and _a not in _atk:
            _atk.append(_a)
    # ★ `attack_sources` 缺省时**回落**到 `sources`（旧调用点零改动）——
    #   语义：谁复现这条主张，谁就同时是对它的反例来源（保守且自洽）。
    for _as_ in (attack_sources if attack_sources is not None else sources
                 or []):
        _as_ = str(_as_).strip()
        if _as_ and _as_ not in _atk_src:
            _atk_src.append(_as_)
    if _rn and _rn not in _seen:
        _rnd.append(_rn)

    # ② revoked：**攻击被独立复现**（与 stable 的镜像规则）
    #   ★ 旧规则 `len(_atk) >= len(_sup)` 的致命退化：`_sup` 每圈恒 +1、
    #     `_atk` 至多 +1 ⇒ 该条件**只在「每圈都攻击」时成立** ——
    #     「攻击面 ≥ 支持面」被读成「攻击从未缺席」。
    #   ★ 新规则要求攻击**跨 ≥2 个不同来源**出现 —— 与 stable 用同一把
    #     尺子（独立性，不是次数）。「同一个来源反复骂」不再算数。
    if _atk:
        _atk_rounds = sorted(_seen | ({_rn} if _rn else set()))
        _rs = (_BELIEF_REVOKE_SOURCES if revoke_sources is None
               else int(revoke_sources))
        if (len(_atk_src) >= _rs
                and len(_atk_rounds) >= _BELIEF_STABLE_K):
            return "revoked"
        # 攻击不足以推翻（非单调：由 stable 掉回 active，可再被推翻）
        if _cur == "stable":
            return "active"
        return _cur

    # ③ stable：连续 k 圈被 ≥2 个**不同来源**独立复现
    if _cur in ("active", "stable"):
        _distinct_rounds = sorted(_seen | ({_rn} if _rn else set()))
        if (len(_sup) >= _BELIEF_STABLE_SOURCES
                and len(_distinct_rounds) >= _BELIEF_STABLE_K):
            return "stable"

    return _cur


#: 语义熵聚类阈值（D3）。★ **与 `sim.cluster`（0.70）解耦** ——
#:   两者不是同一件事：`sim.cluster` 是 E2 **探针批选**的口径（把
#:   「同一个探针」聚起来），D3 要聚的是「**同一主张的历次说法**」。
#:   ★ 为什么必须是 0.30 而不是 0.70：`_sim3` 在中文上走字符二元组
#:     Jaccard，同一个主张换个说法只有 0.41~0.79，0.70 只有近乎逐字
#:     才够得着 ⇒ 簇恒单元素 ⇒ 熵恒 None（实测，见 _mk_v12328_d3thr 头注）。
#:     实测同主张 0.41~0.79、不同主张 0.00 —— 两组完全可分，取空隙内的
#:     0.30（长句重述上偏保守：宁可少聚，不把不同主张混进同一簇）。
#:   这里给的是「函数默认值」，配置侧由 `belief.sem_entropy_thr` 覆盖。
#:   默认值 = 出厂值 ⇒ 零行为差。
_SEM_CLUSTER_THR = 0.30

#: 相对分位阈值的**夹取区间**与**分位点**（D1）。
#:   ★ 为什么要夹取：文本全同 ⇒ p60=1.0（谁都聚进去 = 恒聚）；文本全异
#:     ⇒ p60=0.0（谁都聚不进 = 恒不聚）。两者都是退化，夹取后回到「有
#:     分布可定标」的正常区。夹取区间取自实测：同义 0.41~0.79、
#:     异义 0.00 ⇒ 取 [0.20, 0.55] 正好夹在空隙两侧内侧。
_SEM_REL_LO = 0.20
_SEM_REL_HI = 0.55
_SEM_REL_Q = 0.60

#: [D2 修正] 语义归并阈值。★ 高阈值是**刻意的**：红线要求
#:   「入池前挡重复」，把不同主张并成一条是禁止的。0.85 只吃
#:   「几乎同一句话」（实测同义重述 0.41~0.79 达不到它）⇒
#:   宁可漏并，不可错并。
_BELIEF_MERGE_SIM = 0.85


def _rv(obj, key, default=None):
    """[鸭子类型] 同时兼容 dict 与 dataclass/对象地取字段。

    ★ 为什么需要：本项目的 `results` 在**引擎内是 View 对象**、**落盘后是 dict**，
      两处代码风格混用。曾经写过 `(results.get(e) or {}).get("duty")` ——
      View 没有 `.get` ⇒ AttributeError ⇒ 被 `except Exception` 吞掉 ⇒
      **静默失效**（真跑产物里整行读数消失）。统一走本函数。
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        _v = obj.get(key, default)
        return default if _v is None else _v
    _v = getattr(obj, key, default)
    return default if _v is None else _v


# ============================================================
# 学科吸收 · 第三批（机制级）
# ============================================================

#: anytime-valid 停止的总开关默认值（"off" ⇒ 出厂零行为差）。
_ANYTIME_DEFAULT_ALPHA = 0.0
#: 发散检测的窗口（序列少于这个数不表态）。
_DIVERGE_MIN_N = 4


def stitched_hoeffding_lower(seq, delta: float = 0.05):
    """**anytime-valid 均值下界**（stitched Hoeffding，Howard et al. 2021）。

    ★ 为什么必须是 anytime-valid：本项目**每圈都要看**一致率/读数再决定停不停
      —— 这正是 optional stopping。用固定样本公式（如 p̂ ± 1.96·σ/√n）在
      「边跑边看」下**有效性不成立**（假阳率会暴涨）。
      stitched Hoeffding 给出对**任意停时**都成立的下界：
          p̂ − sqrt( (1/(2n)) · (1+1/n) · ln( sqrt(n+1)/δ ) )
      即 `E[φ_τ] ≤ α` 对任意停时 τ 成立（Doob 可选停时定理的落地形式）。

    `seq`：0/1 序列（如逐条「三票是否一致」）。
    返回 `{n, mean, lower, upper, delta}`；样本不足（n<2）⇒ None（不表态）。
    """
    try:
        xs = [1.0 if float(x) >= 0.5 else 0.0 for x in (seq or [])]
    except (TypeError, ValueError):
        return None
    n = len(xs)
    if n < 2:
        return None
    mean = sum(xs) / float(n)
    d = float(delta if (delta and 0 < delta < 1) else 0.05)
    rad = math.sqrt((1.0 / (2.0 * n)) * (1.0 + 1.0 / n)
                    * math.log(math.sqrt(n + 1) / d))
    return {"n": n, "mean": round(mean, 4),
            "lower": round(max(0.0, mean - rad), 4),
            "upper": round(min(1.0, mean + rad), 4),
            "delta": d}


def anytime_majority_decided(seq, delta: float = 0.05, thr: float = 0.5):
    """**anytime-valid 的「多数已确立」判据**：下界 > 阈值 ⇒ 可停（opt-in）。

    ★ 口径：这是「随时看随时停仍然有效」的判据，**不是**「跑得更久就更好」。
      阈值取 0.5 = 只判「证据已足以说『多数一致』」，不判质量高低。
    """
    lb = stitched_hoeffding_lower(seq, delta)
    if not lb:
        return False, {"why": "样本不足（n<2）"}
    return bool(lb["lower"] > float(thr)), lb


def divergence_state(series) -> Optional[dict]:
    """**三态判决**（吸收 LoopGain 的收敛/停滞/发散）。

    · 收敛：序列**趋于稳定**（后半段方差显著小于前半段）；
    · 停滞：整体方差极小（一直在同一水平）；
    · 发散：方差上升**且** lag-1 自相关为正（CSD 前兆）—— 再跑无益。
    ★ 与 CSD 读数同源但用途不同：CSD 只报读数；本函数给出**三态判决**供
      「回滚指针」与冒烟判据用（**仍不改停止行为**）。
    """
    try:
        xs = [float(x) for x in (series or []) if x is not None]
    except (TypeError, ValueError):
        return None
    n = len(xs)
    if n < _DIVERGE_MIN_N:
        return None
    half = n // 2
    def _var(v):
        if len(v) < 2:
            return 0.0
        m = sum(v) / len(v)
        return sum((x - m) ** 2 for x in v) / len(v)
    v1, v2 = _var(xs[:half]), _var(xs[half:])
    m = sum(xs) / n
    den = sum((x - m) ** 2 for x in xs)
    ac1 = (sum((xs[i] - m) * (xs[i - 1] - m) for i in range(1, n)) / den
           if den > 1e-12 else 0.0)
    if v2 > 1.5 * v1 and ac1 > 0.2:
        state = "发散"
    elif max(v1, v2) <= 1e-9:
        state = "停滞"
    elif v2 < 0.7 * v1:
        state = "收敛"
    else:
        state = "平稳"
    return {"state": state, "var_first": round(v1, 4), "var_last": round(v2, 4),
            "ac1": round(ac1, 4), "n": n}


def best_round_index(series, higher_is_better: bool = True) -> Optional[int]:
    """**历史最佳圈的指针**（回滚指针；1-based）。

    ★ 依据 LoopGain：发散时回滚到「历史最佳」而不是继续跑。
    ★ 红线「失败留痕」⇒ 本函数**只给指针**：被回滚掉的那几圈**不删**，
      产物照旧全部保留，只是在指针处标「历史最佳」。
    """
    try:
        xs = [float(x) for x in (series or []) if x is not None]
    except (TypeError, ValueError):
        return None
    if not xs:
        return None
    best = max(xs) if higher_is_better else min(xs)
    return xs.index(best) + 1


_BANDIT_ARMS = ({"rounds": 3}, {"rounds": 4}, {"rounds": 6})
_BANDIT_FILE = "bandit.json"


def _load_bandit(cfg) -> "BudgetBandit":
    """从 `dgtf_memory/bandit.json` 载入 bandit 状态（缺失 ⇒ 全新）。

    ★ 默认**关**：只有 `auto.bandit.enabled=true` 才走到这里。
    ★ bandit 状态是**状态**不是账本 ⇒ 允许整体覆盖，但每次都带 `t`/`n` 供审计。
    """
    _arms = (cfg or {}).get("arms") or _BANDIT_ARMS
    bb = BudgetBandit(_arms, c=float((cfg or {}).get("c", 1.0) or 1.0),
                      cost_w=float((cfg or {}).get("cost_w", 0.3) or 0.3))
    try:
        import json as _j
        _d = Path(str((cfg or {}).get("dir") or eml_dir()))
        _f = _d / _BANDIT_FILE
        if _f.is_file():
            st = _j.loads(_f.read_text(encoding="utf-8"))
            if isinstance(st.get("n"), list) and len(st["n"]) == len(bb.arms):
                bb.n = [int(x or 0) for x in st["n"]]
                bb.mean = [float(x or 0.0) for x in st.get("mean", bb.mean)]
                bb.cost = [float(x or 0.0) for x in st.get("cost", bb.cost)]
                bb.t = int(st.get("t") or sum(bb.n))
    except Exception:
        pass
    return bb


def _save_bandit(bb, cfg) -> bool:
    """把 bandit 状态落盘（带 `t`/`n`，供审计）。

    ★ [并发正确性] bandit.json 是**读-改-写**（跑首载入、跑末落盘），3 并发时
      两进程会互相覆盖统计。故落盘走**同一把记忆库锁**。★ bandit 是**状态不是账本**
      ⇒ 拿不到锁就**跳过这次落盘**（短超时，绝不为了省一行状态把跑卡住）。
    """
    try:
        import json as _j
        import time as _t
        _d = Path(str((cfg or {}).get("dir") or eml_dir()))
        _d.mkdir(parents=True, exist_ok=True)
        with eml_lock(dirpath=_d, timeout=5.0) as _got:
            if not _got:
                return False
            (_d / _BANDIT_FILE).write_text(_j.dumps({
                "t": _t.time(), "n": list(bb.n),
                "mean": [round(x, 6) for x in bb.mean],
                "cost": [round(x, 6) for x in bb.cost],
                "arms": list(bb.arms)}, ensure_ascii=False, indent=1),
                encoding="utf-8", newline="\n")
        return True
    except Exception:
        return False


class BudgetBandit:
    """**预算感知 bandit**（极简 UCB1-with-cost）。

    ★ 吸收 AAAI'26 的 Budget-Aware LinUCB 的**思想**（成本进入收益项），
      但**不引入依赖、不上上下文特征**：这里只做「臂 = 圈数档，
      收益 = 职责度读数 − λ·成本」的 UCB1。
    ★ **默认关**（config `auto.bandit.enabled=false`）⇒ 出厂零行为差。
    ★ 探索的代价：会**故意选已知较差的档**。因此每次「探索选择」都在产物留痕
      （否则用户看到「这次为什么跑得差」会查无原因）。
    """

    def __init__(self, arms, c: float = 1.0, cost_w: float = 0.3):
        self.arms = [dict(a) if isinstance(a, dict) else {"v": a}
                     for a in (arms or [])]
        self.n = [0] * len(self.arms)
        self.mean = [0.0] * len(self.arms)
        self.cost = [0.0] * len(self.arms)
        self.c = float(c or 1.0)
        self.cost_w = float(cost_w if cost_w is not None else 0.3)
        self.t = 0

    def _score(self, i):
        if self.n[i] == 0:
            return float("inf")          # 未试过的臂优先（确定性探索）
        bonus = self.c * math.sqrt(2.0 * math.log(max(2, self.t)) / self.n[i])
        return self.mean[i] - self.cost_w * self.cost[i] + bonus

    def pick(self) -> dict:
        scores = [self._score(i) for i in range(len(self.arms))]
        i = max(range(len(scores)), key=lambda k: scores[k])
        exploit = all(v > 0 for v in self.n)
        return {"index": i, "arm": self.arms[i], "explore": not exploit,
                "scores": [None if s == float("inf") else round(s, 4)
                           for s in scores]}

    def update(self, i, reward, cost) -> None:
        if not (0 <= i < len(self.arms)):
            return
        self.t += 1
        self.n[i] += 1
        k = self.n[i]
        self.mean[i] += (float(reward or 0.0) - self.mean[i]) / k
        self.cost[i] += (float(cost or 0.0) - self.cost[i]) / k


# ── ④ compact 内部面预算（率失真）─────────────────────────
#: 内部面占全文的**目标上限**（超出 ⇒ 索引化，不删内容）。
_COMPACT_INNER_BUDGET = 0.60


def compact_plan(inner_chars: int, total_chars: int,
                 budget: float = _COMPACT_INNER_BUDGET) -> dict:
    """**率失真**式的内部面预算：给定位数下最优表示，而不是「越短越好」。

    ★ 依据：率失真理论（给定位率下的最优失真）+ ACE 的反面数据
      （把 1.8 万 token 压到 122 token ⇒ 准确率 66.7→57.1）。
      ⇒ 超预算时**索引化**（正文留摘要 + 指向 packed），**不删内容**。
    """
    t = max(1, int(total_chars or 0))
    i = max(0, int(inner_chars or 0))
    share = i / float(t)
    over = share > float(budget)
    return {"inner_share": round(share, 4), "budget": float(budget),
            "over": bool(over),
            "verdict": ("内部面超预算 ⇒ 本轮**索引化**（不删内容，正文回退到索引 + "
                        "指向 packed 全量）" if over else "内部面在预算内")}


# ── ⑤⑥⑦ 锚点三项：解析验证 / 内部批判 / 分级证明标准 ──────
_DOMAIN_INTEREST = (
    ("gov", "公权力方（利益：政策延续性 / 管辖边界）"),
    ("edu", "学术方（利益：可发表性 / 方法新颖）"),
    ("org", "非营利/行业组织（利益：成员共识 / 行业自律）"),
    ("com", "商业方（利益：产品与市场叙事）"),
    ("net", "基础设施/社群"),
    ("io", "技术社群/初创"),
)
_MEDIA_HINTS = ("blog", "medium", "substack", "zhihu", "weibo", "toutiao",
                "36kr", "sspai", "mp.weixin")


def anchor_offline_check(url: str) -> dict:
    """**离线解析验证**（吸收 refchecker 的「按可审计表面判」）。

    ★ 依据：引用要么解析得开、要么解析不开 —— 这比「判断言真假」可靠得多
      （refchecker：2025 NeurIPS/USENIX 约 1/20 论文含 ≥2 条疑似幻觉引用）。
      本函数只做**离线**部分（URL 形态 / 域名与协议 / 是否可解析），
      不发网络请求（零依赖 + 零成本），可达性留给联网通道。
    """
    u = str(url or "").strip()
    out = {"url": u[:200], "ok": False, "why": []}
    if not u:
        out["why"].append("空 URL（无法解析）")
        return out
    if not (u.startswith("http://") or u.startswith("https://")):
        out["why"].append("非 http(s) 形态")
    if " " in u:
        out["why"].append("含空格（形态异常）")
    host = ""
    try:
        rest = u.split("://", 1)[1] if "://" in u else u
        host = rest.split("/", 1)[0].split("?", 1)[0].lower()
    except Exception:
        host = ""
    if not host or "." not in host:
        out["why"].append("域名不完整")
    out["host"] = host[:120]
    out["ok"] = not out["why"]
    return out


def anchor_interest_hint(url: str) -> str:
    """**锚点内部批判**（史学 Quellenkritik 的「内部批判」）：

    ★ 外部批判（真伪/来源/年代）本项目已有 `tier`；**内部批判**（作者立场与
      利益倾向）此前缺失。这里用**域名类型**给一个**提示**（不是判词）：
      「这条 claim 出自谁，他/它可能有哪类利益倾向」。
      ⇒ 与红线一致：这是**提示**，不是给锚点打分。
    """
    host = ""
    try:
        rest = str(url or "").split("://", 1)[1] if "://" in str(url) else str(url or "")
        host = rest.split("/", 1)[0].split("?", 1)[0].lower()
    except Exception:
        host = ""
    for _h in _MEDIA_HINTS:
        if _h in host:
            return "媒体/自媒体（利益：流量与叙事张力）"
    for _tld, _hint in _DOMAIN_INTEREST:
        if host.endswith("." + _tld) or ("." + _tld + ".") in (host + "."):
            return _hint
    return "未识别来源类型（按最弱处理）"


def anchor_evidence_standard(claim_kind: str) -> dict:
    """**分级证明标准**（法学 burden of proof）+ **谁主张谁举证**。

    ★ 依据：法学把证明标准分级 —— `preponderance`（优势证据）/
      `clear and convincing`（明确且有力）/ `beyond reasonable doubt`（排除合理怀疑），
      且**主张方负举证责任**。本项目原本只有一刀切的 `tier_floor` gate。
    ★ 本函数**只给标准与举证方**，不改 gate 行为（gate 仍按 tier_floor）。
    """
    k = str(claim_kind or "").strip().lower()
    table = {
        # claim 的性质 → (标准, 谁举证)
        "causal": ("beyond_reasonable_doubt", "主张因果者举证"),
        "numerical": ("clear_and_convincing", "给出数字者举证（含口径与来源）"),
        "normative": ("preponderance", "主张规范者举证（偏好不可当证据）"),
        "factual": ("preponderance", "主张事实者举证"),
        "predictive": ("clear_and_convincing", "预测者举证（含基准与不确定度）"),
    }
    std, who = table.get(k, ("preponderance", "主张者举证"))
    return {"claim_kind": k or "unknown", "standard": std, "burden_on": who}


# ── ⑧ 对撞裁决维度拆分（言语行为论 / 多评委）─────────────
_ADJ_ASPECTS = (
    ("逻辑", ("矛盾", "不一致", "自相", "推导", "前提")),
    ("事实", ("事实", "数据", "证据", "实测", "引用")),
    ("边界", ("边界", "条件", "范围", "前提未定", "口径")),
    ("后果", ("后果", "风险", "代价", "副作用", "影响")),
)


def adjudication_aspect(tension: str, how: str) -> str:
    """给一条**裁决**判它的**依据维度**（逻辑/事实/边界/后果），判不出 ⇒ "未标注"。

    ★ 依据：多评委框架（逻辑/事实/修辞/策略/伦理…）+ 本项目红线
      「自省是另一个视角，不可合并」⇒ 裁决依据**拆维留痕**而不是合成一个 `how`。
    """
    blob = "%s %s" % (str(tension or ""), str(how or ""))
    hits = [name for name, keys in _ADJ_ASPECTS
            if any(k in blob for k in keys)]
    return "/".join(hits) if hits else "未标注"


# ── ⑨ 信念 staleness 读数（不改四态）────────────────────
def belief_staleness(item: dict, cur_round: int) -> dict:
    """**信念陈旧度**读数（吸收 ABES 的时间衰减 + ftl-beliefs 的 STALE 态）。

    ★ **不改四态**：加第五态会让历史 packed 的判据全部失准（红线级风险）
      ⇒ 本函数只出**读数**，另一个字段回填，不改 `status`。
    · `seen_at`（最后被确认的圈号）→ `age`（距现在多少圈未再确认）
    · `stale_hint`：age ≥ 3 且状态仍 active ⇒ 提示「可能已过期，需复确认」
    """
    it = item or {}
    last = it.get("last_confirmed_round")
    if last is None:
        last = (max(it.get("rounds_seen") or [0])
                if it.get("rounds_seen") else None)
    try:
        age = (int(cur_round or 0) - int(last)) if last is not None else None
    except (TypeError, ValueError):
        age = None
    return {"id": it.get("id", ""), "age": age,
            "stale_hint": bool(age is not None and age >= 3
                               and str(it.get("status", "")) == "active")}


# ============================================================
# 学科吸收 · 第二批（读数与结构，不改行为）
# ============================================================

#: 不可见 / 同形类字符（llm-guard 的 InvisibleText 思路，只取规则类、不拉模型）。
_INVISIBLE_CHARS = ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff",
                    "\u00ad", "\u2028", "\u2029")
#: 指令注入的**规则类**特征（不判语义，只报形态）。
_INJECT_PATTERNS = ("忽略以上", "忽略前面", "无视上述", "ignore previous",
                    "ignore above", "disregard the above", "system:",
                    "assistant:", "你现在是", "从此以后你")
#: 预设触发式（语用学：预设失败 ⇒ 问的问题本身预设了未成立的东西）。
_PRESUP_PATTERNS = (
    ("为什么", "「为什么X」预设 X 成立"),
    ("为何", "「为何X」预设 X 成立"),
    ("什么时候停止", "预设存在停止时点"),
    ("如何避免", "「如何避免X」预设 X 必然发生"),
    ("怎样才能不", "预设当前状态是该被消除的"),
    ("既然", "「既然」预设前件为真"),
)


def input_red_flags(q: str) -> list:
    """[输入自检 · 规则类] 不可见字符 + 指令注入 + 预设式（**只报不改**）。

    ★ 依据：llm-guard 的 InvisibleText 与 PromptInjection 扫描器。
      本实现**只取规则类**（正则/字符表）—— 其 ML 扫描器会拉 transformers，
      与本项目「单文件零依赖」冲突。
    """
    _q = str(q or "")
    out = []
    for _c in _INVISIBLE_CHARS:
        if _c in _q:
            out.append({"kind": "invisible", "term": repr(_c),
                        "why": "不可见字符（零宽/软连字符），可能被用来隐藏内容"})
            break
    _low = _q.lower()
    for _p in _INJECT_PATTERNS:
        if _p.lower() in _low:
            out.append({"kind": "injection", "term": _p[:20],
                        "why": "指令注入式形态（要求覆盖既有指示）"})
            break
    for _p, _why in _PRESUP_PATTERNS:
        if _p in _q:
            out.append({"kind": "presupposition", "term": _p,
                        "why": _why})
            break
    return out


#: 言语行为的**动词特征**（Austin/Searle 的 illocutionary 分类，规则判定）。
_ILLOC_PATTERNS = (
    # ★ [词表纪律] 只收**动词性强**的词。动名兼类（统计/设计/发布/记账/
    #   登记/归档/监控…）会污染分类：`完善统计` 本是**请求**，却被「统计」
    #   判成承诺（冒烟判据当场抓到）。宁可漏判成「其他」，不要误判成承诺。
    ("承诺", ("指派", "建立", "委托", "备案", "制定", "开展", "实施",
              "落地", "推动", "建设", "部署", "核查", "测量", "评估",
              "审计", "验证", "编写", "调研", "标注", "抽取", "校准",
              "接入", "迁移", "复盘")),
    ("断言", ("是", "为", "等于", "达到", "存在", "表明", "说明", "显示",
              "意味着", "定义")),
    ("请求", ("应当", "应该", "建议", "需要", "要", "请", "期望", "呼吁",
              "不得", "必须", "呼吁", "倡导", "力求")),
)


def illocution_of(text: str) -> str:
    """判一条行动的**言语行为类型**：承诺 / 断言 / 请求（判不出 ⇒ "其他"）。

    ★ 依据：言语行为论（Austin/Searle）—— `illocution`（在做什么）与
      `locution`（说了什么）必须分开。若一份「行动清单」**全是请求**、
      没有任何**承诺**（自己承担的动作），那就是祈使句堆砌，不是方案。
    """
    _t = str(text or "")
    for _k, _ws in _ILLOC_PATTERNS:
        if any(w in _t for w in _ws):
            return _k
    return "其他"


def illocution_dist(actions) -> dict:
    """行动清单的言语行为分布 + 判词（全是请求 ⇒ 公文体告警）。"""
    _d = {"承诺": 0, "断言": 0, "请求": 0, "其他": 0}
    _n = 0
    for a in (actions or []):
        _txt = ""
        if isinstance(a, dict):
            _txt = "%s%s" % (a.get("verb", ""), a.get("object", ""))                 or str(a.get("text", ""))
        else:
            _txt = str(a)
        _d[illocution_of(_txt)] += 1
        _n += 1
    _verdict = ""
    if _n and _d["承诺"] == 0 and _d["请求"] >= max(1, _n // 2):
        _verdict = "公文体风险：全部/多数为「请求」，无「承诺」型动作（没人认领）"
    return {"dist": _d, "n": _n, "verdict": _verdict}


def cut_two_way(cut: bool, rounds_cap, rounds_run, duty: dict) -> dict:
    """**截断的两向记账**（AgentExit 的 Redundancy Steps vs Progress Degradation）。

    ★ 依据：截断省下了多少圈（正向），同时丢了多少 core 问项（**负向**）。
      只报一面的读数必然误导 —— 与「只升不降的指标是自欺」同源。
    ★ 本函数**只出读数**：截断仍按原判据停（不改停止行为）。
    """
    _d = duty or {}
    _miss = list(_d.get("missing_core") or [])
    _core = int(_d.get("core_total", 0) or 0)
    return {
        "cut": bool(cut),
        "rounds_cap": int(rounds_cap or 0),
        "rounds_run": int(rounds_run or 0),
        "saved_rounds": max(0, int(rounds_cap or 0) - int(rounds_run or 0))
        if not cut else 0,
        "lost_core": len(_miss),
        "core_total": _core,
        "note": ("截断：省（未跑满的余量不产生成本）与丢（core 未覆盖）"
                 "两面分开报，不合成一个判词"),
    }


def fmea_detectability(name: str, known_markers) -> str:
    """[FMEA] 一条失败模式的**可检测性**：能被已有判据/线索发现吗。

    ★ 依据：FMEA 的 RPN = 严重度 × 频度 × **可检测性** ——
      **不可检测的失败最危险**（它不会出现在任何读数里，只能等后果）。
      本函数只做**规则匹配**：失败模式名是否出现在已知标记集合里。
    """
    _n = str(name or "")
    _ms = [str(x) for x in (known_markers or []) if str(x).strip()]
    for _m in _ms:
        if _m and (_m in _n or _n in _m):
            return "可检测（有对应标记：%s）" % _m[:20]
    return "⚠️ **不可检测**（没有对应标记 —— 它不会出现在任何读数里）"


def diversity_budget(views, channels, mode) -> dict:
    """[Ashby 必要多样性定律] 本跑实际动用的**组合数**（层 × 通道 × 模式）。

    ★ 依据：控制器可用的状态多样性 ≥ 被控系统的扰动多样性，否则无法维持目标。
      固定四层 × 固定通道的多样性**有上限** —— 踩到上限时「跑得不好」
      不是工程缺陷，而是**控制论上不可能**。
      ⇒ 这是一个**读数**（提示谨慎读结论），**不是**分数。
    """
    _vs = views or {}
    _layers = [k for k in ("0", "1", "both", "all") if k in _vs]
    _ch = [str(x) for x in (channels or [])]
    _m = str(mode or "serial")
    _combos = max(0, len(_layers)) * max(0, len(_ch))
    return {"layers": len(_layers), "channels": len(_ch), "mode": _m,
            "combos": _combos,
            "note": "组合数 = 层数 × 通道数（模式另计）；"
                    "低于「层×通道满配」时，结论的可迁移性受限"}


# ============================================================
# 学科吸收：评分者一致性 / 测量尺度 / 停因级联 / 早期预警
#
# ★ 为什么这些是**判据口径**而不是「新机制」：
#   本项目早就写着「读数不是分数」「同一把尺子」「不许只升不降」，
#   但从没有把「尺子」本身形式化。以下三段把那些口号变成可执行的东西。
# ============================================================

#: 三态的**定序**顺序（可判定性由高到低）。★ 三态天然有序，
#:   所以一致性必须用 ordinal 距离，不能用 nominal（同一份数据两者能差很多）。
_TRI_ORDER = {"decidable": 2, "partial": 1, "undecidable": 0}


def _tri_rank(lab) -> Optional[int]:
    return _TRI_ORDER.get(str(lab or "").strip().lower())


def krippendorff_alpha_ordinal(units) -> Optional[dict]:
    """**ordinal Krippendorff α**（缺失值容忍；任意评审人数）。

    `units`：`[[label, label, ...], ...]`（每个 unit 一个评分者列表，可缺）。
    返回 `{alpha, n_units, n_pairs, do_observed, do_expected}`；
    样本不足（有效 unit < 2 或总配对 < 2）⇒ 返回 None（**不印 0 冒充读数**）。

    ★ 依据：Krippendorff 的口径 —— **α ≥ 0.800 才算可靠；0.667~0.800 只支持
      暂定结论；0.667 是下限不是目标**。原始一致率忽略机会一致，
      在标签偏斜时会严重高估（实证：原始 79% ↔ κ 0.34~0.44）。
    """
    _units = []
    for u in (units or []):
        _r = [_tri_rank(x) for x in (u or [])]
        _r = [x for x in _r if x is not None]
        if len(_r) >= 2:
            _units.append(_r)
    if len(_units) < 2:
        return None
    _npairs = sum(len(u) * (len(u) - 1) // 2 for u in _units)
    if _npairs < 2:
        return None
    # 观察不一致度 Do（ordinal 距离：用排名差归一化到 [0,1]）
    _span = max(1, len(_TRI_ORDER) - 1)
    # 全局值分布（用于 De 的期望）
    _all = [x for u in _units for x in u]
    _n = len(_all)
    _n_total = sum(len(u) for u in _units)

    def _d(a, b):
        return float(abs(a - b)) / float(_span)

    _do_num = 0.0
    for u in _units:
        _m = len(u)
        for i in range(_m):
            for j in range(i + 1, _m):
                _do_num += _d(u[i], u[j])
    Do = _do_num / float(_npairs)
    # De：每个 unit 内配对，按**合并后的经验分布**算期望距离
    #   （与 Krippendorff 的 ordinal De 同构：E[d] over the pooled distribution）
    _exp_d = 0.0
    for _x in _all:
        for _y in _all:
            _exp_d += _d(_x, _y)
    _exp_d = _exp_d / float(max(1, _n * _n))
    De = _exp_d
    if De <= 1e-12:
        # 全体同值 ⇒ 无可测分歧；返回 1.0 但**注明**（不是「没测」）
        return {"alpha": 1.0, "n_units": len(_units), "n_pairs": _npairs,
                "do_observed": round(Do, 6), "do_expected": 0.0, "degenerate": True}
    return {"alpha": 1.0 - (Do / De), "n_units": len(_units),
            "n_pairs": _npairs, "do_observed": round(Do, 4),
            "do_expected": round(De, 4), "degenerate": False}


def weighted_kappa_pair(a_labels, b_labels, weights="ordinal") -> Optional[dict]:
    """两名评分者之间的 **weighted κ**（线性权重；容忍缺失对）。

    ★ 与 α 并列报：κ 好算好解释，α 更通用（人数/缺失/尺度）。
      两者都报，避免「换个统计量把结论做绿」的嫌疑。
    """
    _lv = sorted(_TRI_ORDER.values())
    _span = max(1, (max(_lv) - min(_lv)))
    _pairs = []
    for x, y in zip(a_labels or [], b_labels or []):
        _rx, _ry = _tri_rank(x), _tri_rank(y)
        if _rx is None or _ry is None:
            continue
        _pairs.append((_rx, _ry))
    if len(_pairs) < 2:
        return None
    _n = len(_pairs)

    def _w(x, y):
        # 线性权重：完全一致 = 1，差满格 = 0
        return 1.0 - abs(x - y) / float(_span)

    Po = sum(_w(x, y) for x, y in _pairs) / float(_n)
    _ax = [x for x, _ in _pairs]
    _ay = [y for _, y in _pairs]

    def _marg(v):
        _d = {}
        for z in v:
            _d[z] = _d.get(z, 0) + 1
        return {k: c / float(_n) for k, c in _d.items()}

    _mx, _my = _marg(_ax), _marg(_ay)
    Pe = 0.0
    for _x, _px in _mx.items():
        for _y, _py in _my.items():
            Pe += _px * _py * _w(_x, _y)
    if abs(1.0 - Pe) < 1e-12:
        return {"kappa": 1.0, "n": _n, "po": round(Po, 4), "pe": round(Pe, 4),
                "degenerate": True}
    return {"kappa": (Po - Pe) / (1.0 - Pe), "n": _n,
            "po": round(Po, 4), "pe": round(Pe, 4), "degenerate": False}


def rare_class_agreement(units, rare="undecidable") -> Optional[dict]:
    """**少数类一致**：只看被判为该类的 unit 里，评审是否一致。

    ★ 依据：标签偏斜时「大家都判多数类」的共识是**廉价**的；
      真正有信息的是少数类上的分歧（本项目关心的恰是「判不出」这个少数类）。
    """
    _rare = str(rare or "").strip().lower()
    _n_unit = _n_any = 0
    for u in (units or []):
        _r = [str(x or "").strip().lower() for x in (u or [])]
        _r = [x for x in _r if x in _TRI_ORDER]
        if len(_r) < 2:
            continue
        if _rare not in _r:
            continue
        _n_unit += 1
        if len(set(_r)) == 1:
            _n_any += 1
    if _n_unit == 0:
        return None
    return {"rare": _rare, "units": _n_unit, "unanimous": _n_any,
            "rate": _n_any / float(_n_unit)}


def alpha_verdict(alpha) -> str:
    """把 α 翻成**口径化**的判词（Krippendorff 阈值，不用「看起来低/高」）。"""
    if alpha is None:
        return "未测（样本不足）"
    try:
        a = float(alpha)
    except (TypeError, ValueError):
        return "未测（样本不足）"
    if a >= 0.800:
        return "可靠（α≥0.800）"
    if a >= 0.667:
        return "仅支持暂定结论（0.667≤α<0.800）"
    return "不可靠（α<0.667，Krippendorff 下限）"


def cost_bucket(stage) -> str:
    """[成本两分] 把一个 stage 归到 `"eval"`（自测量）或 `"ops"`（跑本身）。

    ★ 未登记的一律归 `ops`：**宁少算自测量、不多算**（把任务成本说小才是失真）。
    ★ 抽成纯函数才可测 —— 内联在 `LLM.call` 里的分类逻辑，判据只能看源码，
      变异体（分类恒返回 ops）会**假绿**。
    """
    return "eval" if str(stage or "") in _LLM_EVAL_STAGES else "ops"


#: [成本两分] **自测量（判定类）** stage 名单 —— 这些调用不产出任务内容，
#:   产出的是「对内容的判定/评估」。未登记的一律计入「跑本身」（宁少算自测量）。
_LLM_EVAL_STAGES = frozenset({
    "assess_decidability", "assess_decidability_from_pool_view",
    "adjudicate_sub_tristate", "adjudicate_sub_tristate_multi",
    "anchor_crosscheck", "dual_judge", "re_evaluate_pool",
    "self_check", "input_sanity", "landing_decision",
})


# ── 读数尺度登记（Stevens 测量论）────────────────────────────
#: **尺度类型**：nominal（定类）/ ordinal（定序）/ interval（定距）/ ratio（定比）。
#: ★ 允许的运算不同 —— 定序**不许**求均值、不许说「两倍」、不许报「百分比提升」。
#:   这不是文风要求，是测量论：定序尺度的差值无定义。
_READING_SCALE = {
    "tri_state_agreement": "ordinal",   # 三态一致率（分母是定序标签）
    "tri_alpha": "interval",            # α ∈ (-1,1]，可比较大小
    "tri_kappa": "interval",
    "duty.S": "interval",               # 调和平均，零点非自然零点
    "duty.C": "ratio",
    "duty.R": "ratio",
    "semantic_entropy": "ratio",        # 熵有真零
    "touch_rate": "ratio",
    "aspect_carry_rate": "ratio",
    "tier": "ordinal",                  # 锚点分级
    "anchor_tier_floor": "ordinal",
    "csd_warning": "ordinal",           # 有前兆/无前兆/样本不足
    "playbook_evidence_n": "ratio",
}

#: **定序读数禁止出现的措辞**（出现即违测量论：在无差值的尺度上做算术）。
_SCALE_FORBIDDEN = {
    "ordinal": ("均值", "平均", "两倍", "翻倍", "百分比提升", "提升了",
                "加权平均", "标准差"),
}


def reading_scale(name: str) -> str:
    """查某读数的尺度类型（未登记 ⇒ 返回 "unknown"）。

    ★ 未登记不是错误，但**不许**默默当 interval 用 —— 那正是「读数当分数」。
    """
    return _READING_SCALE.get(str(name), "unknown")


def scale_word_violations(text: str, scale: str) -> list:
    """定序读数的措辞检查：返回命中的违禁词（空列表 = 合规）。"""
    _bad = _SCALE_FORBIDDEN.get(str(scale), ())
    _t = str(text or "")
    return [w for w in _bad if w in _t]


# ── 停因级联（halt cascade，吸收 SHP）──────────────────────
#: 停因的**优先级**（数字越小越优先）。依据 SHP 的 halt cascade：
#: ① 判定/收敛达成 ② 熵收敛（复述）③ 无信息增益（停滞/空转）④ 硬上限。
#: ★ 纪律：**报告的主因必须就是真正停下来的那个**（一个级联、无漂移）。
_STOP_CASCADE = (
    (0, ("职责增益收敛", "结构饱和度", "悬置决定稳定", "自然安住",
         # ★ [四层目标] 目标达成 = 判定/收敛达成，**与上述同级**。
         #   缺了这行，目标停因会落到最低档 3（与「体力耗尽」同级）——
         #   语义刚好相反（达成 ≠ 耗尽力竭）。
         "目标已达成", "目标受阻")),
    (1, ("复述", "自省连续")),
    (2, ("无新", "无推进", "连续空转", "停滞", "材料耗尽")),
    (3, ("体力耗尽", "预算用尽", "min_rounds")),
)


def stop_priority(reason: str) -> int:
    """把一条停因文案映射到优先级（未匹配 ⇒ 落到最低档 3，不静默丢弃）。

    ★ 匹配**主句**，不匹配括号里的**转述**：走满型停因的文案形如
      `体力耗尽（N 圈走满；K 次判据被「未深入方向」推迟（悬置决定稳定，
      自然安住），是被截断不是自然停止）` —— 括号里嵌的是**被推迟的
      判据名**，若全文子串匹配，会把「截断」误判成档 0「自然停」，
      语义刚好相反。⇒ 先剥括号再匹配；剥空则回退原文（不静默变档）。
    """
    _r = str(reason or "")
    _head = re.sub(r"[（(][^（()）]*[)）]", "", _r).strip()
    if not _head:
        _head = _r
    for _p, _keys in _STOP_CASCADE:
        if any(k in _head for k in _keys):
            return int(_p)
    return 3


def stop_cascade(reasons) -> dict:
    """把一组停因整理成 `{primary, ordered, all}`（**主因 ∈ 全部触发**）。

    ★ 不变量：`primary` 必须出现在 `all` 里 —— 报告的原因不能是「没触发的那个」。
    """
    _rs = [str(x) for x in (reasons or []) if str(x).strip()]
    if not _rs:
        return {"primary": "", "ordered": [], "all": []}
    _ordered = sorted(_rs, key=lambda r: (stop_priority(r), _rs.index(r)))
    return {"primary": _ordered[0], "ordered": _ordered, "all": _rs}


# ── CSD 早期预警（复杂系统 / 生态学）────────────────────────
#: 有效样本下限：少于这个数**不表态**（CSD 指标在短序列上噪声极大）。
_CSD_MIN_N = 4


def csd_indicators(series) -> Optional[dict]:
    """逐圈序列的 CSD 指标：**方差 + lag-1 自相关**（+ 是否上升趋势）。

    ★ 依据：系统接近临界转变时恢复速率下降 ⇒ 方差与 AC(1) 上升
      （已在生态/气候/生理/金融反复验证）。
    ★ 但口径必须写死：**这是「韧性的概率性评估」，不是「迫近崩溃的预测」**——
      六种 regime shift 机制里多数**没有** CSD 前兆，红噪声会造成虚警。
      ⇒ 本函数只出读数，**绝不参与任何停止判定**。
    """
    try:
        _s = [float(x) for x in (series or []) if x is not None]
    except (TypeError, ValueError):
        return None
    if len(_s) < _CSD_MIN_N:
        return None
    _n = len(_s)
    _m = sum(_s) / _n
    _var = sum((x - _m) ** 2 for x in _s) / _n
    _num = sum((_s[i] - _m) * (_s[i - 1] - _m) for i in range(1, _n))
    _den = sum((x - _m) ** 2 for x in _s)
    _ac1 = (_num / _den) if _den > 1e-12 else 0.0
    _half = _n // 2
    _v1 = sum((x - sum(_s[:_half]) / _half) ** 2 for x in _s[:_half]) / _half \
        if _half else 0.0
    _v2 = (sum((x - sum(_s[_half:]) / (_n - _half)) ** 2
               for x in _s[_half:]) / (_n - _half)) if (_n - _half) else 0.0
    _rising = _v2 > _v1
    return {"n": _n, "var": round(_var, 6), "ac1": round(_ac1, 4),
            "var_rising": bool(_rising),
            "hint": bool(_rising and _ac1 > 0.3)}


def csd_line(indic) -> str:
    """CSD 读数的一行文案（口径写在文案里，防止被读成预测）。"""
    if not indic:
        return "早期预警 —（样本不足，不表态）"
    return ("早期预警（CSD：方差 %s / AC1 %s，%s；**概率性评估，非预测**）"
            % ("↑" if indic.get("var_rising") else "→",
               indic.get("ac1"),
               "有前兆" if indic.get("hint") else "无前兆"))


# ============================================================
# EML · 经验记忆回路（Experiential Memory Loop）
#   「读（recall）→ 用（留痕）→ 写（consolidate）」三段，加一道**质量闸**。
#
# ★ 为什么不是「让模型总结一下上次学到了什么」：
#   ACE（arXiv 2510.04618）实测——把 1.8 万 token 的策略**压缩重写**成 122
#   token，准确率从 66.7 掉到 57.1。**模型擅长用知识，不擅长整理知识。**
#   ⇒ 本实现：playbook **只增不删**、条目**逐条增量**、合并用**确定性规则**
#     （sim3 阈值），永不「重写」已有条目。
#
# ★ 红线对齐（先写清再写码）：
#   · 输入是形状不是数据 ⇒ 记忆**只存「条件→动作」**（procedure），
#     绝不存「结论/答案」（facts）。注入面只有调度与守卫阈值。
#   · 悬置不打分 ⇒ 记忆**不记录**任何悬置的好坏。
#   · 失败留痕 ⇒ `retired` 只改状态位，**不删行**（append-only）。
#   · 入池前挡重复 ⇒ 复用既有 sim3 阈值（0.85）做聚合。
#   · 默认零行为差 ⇒ 出厂 `playbook.mode = "shadow"`（只记不生效）。
#
# ★ 学坏防线（五条）：
#   F1 隔离：新条目一律 `shadow`，不生效；
#   F2 双边记账：每条记 `{cost_delta, quality_delta}`；**只省成本不升级**；
#   F3 一键关：`off` / `shadow` / `on` 三态；
#   F4 遗忘：陈旧 + 未被用过 + 证据不足 ⇒ `retired`（行仍在）；
#   F5 只增不删：任何操作后 playbook 行数**单调不减**。
# ============================================================

_EML_DIRNAME = "dgtf_memory"
_EML_EPISODES = "episodes.jsonl"
_EML_PLAYBOOK = "playbook.jsonl"
_EML_MEMORY_MD = "MEMORY.md"
#: [nogoods 矛盾档案] **append-only 的矛盾库** —— 印证「矛盾不覆盖、只累积」
#:   （ftl-beliefs 的 nogoods；本项目老坑：静默覆盖 = 下次没人知道发生过矛盾）。
_EML_NOGOODS = "nogoods.jsonl"
_EML_KINDS = ("schedule", "probe", "structure", "guard")
_EML_MODES = ("off", "shadow", "on")
_EML_MODE_DEFAULT = "shadow"
_EML_TOP_K = 3
_EML_PROMOTE_N = 3            # meso：同向证据达到几次才 shadow→active
_EML_HALFLIFE_DAYS = 14.0     # 与 auto.history_halflife_days 同源
_EML_RETIRE_RECENCY = 0.05
_EML_AGG_SIM = 0.85           # 聚合阈值（沿用信念归并口径：宁可漏并）
#: [EML] 质量闸四问的名字（判据与报告共用，避免两处措辞分叉）。
_EML_GATE_Q = ("evidence", "contradiction", "verifiable", "redline")


def eml_dir(base=None) -> Path:
    """记忆库目录（默认仓库根 `dgtf_memory/`）。"""
    _b = Path(base) if base else Path(__file__).resolve().parent
    return _b / _EML_DIRNAME


@contextlib.contextmanager
def eml_lock(base=None, dirpath=None, timeout: float = 180.0,
             stale: float = 900.0):
    """跨进程**记忆库互斥锁**：并发真跑时保护记忆库的读-改-写。

    ★ 为什么必须要：`playbook.jsonl` 的「升级 / 遗忘 / macro」是**读-改-写**
      （整表重写），**不是原子 append**。两个进程同时改会互相覆盖
      （丢条目、甚至写坏半行）。**这是并发真跑的正确性前提，不是性能优化。**
    ★ 实现：`O_CREAT|O_EXCL` 自旋锁（跨平台，无需 fcntl/msvcrt）。
      带**陈旧锁回收**：持锁进程被 kill 后 `.lock` 会残留 ⇒ 超 `stale` 秒
      视为陈旧、清掉重取（否则一次崩溃会永久死锁整个记忆库）。
    ★ 单跑时**零副作用**（拿到即放手）；只有真并发才会排队，且只保护写库那一小段。
    """
    try:
        d = Path(dirpath) if dirpath else eml_dir(base)
    except Exception:
        yield False
        return
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        yield False
        return
    lp = d / ".eml.lock"
    t0 = time.time()
    got = False
    while time.time() - t0 < float(timeout):
        try:
            fd = os.open(str(lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, ("%d\n" % os.getpid()).encode("ascii"))
            os.close(fd)
            got = True
            break
        except FileExistsError:
            # 陈旧锁回收：文件太旧 ⇒ 清掉重试（崩了也不永久死锁）。
            try:
                if time.time() - lp.stat().st_mtime > float(stale):
                    lp.unlink(missing_ok=True)
                    continue
            except Exception:
                pass
            time.sleep(0.2)
        except Exception:
            time.sleep(0.2)
    try:
        yield got
    finally:
        if got:
            try:
                lp.unlink(missing_ok=True)
            except Exception:
                pass



def eml_read_jsonl(path) -> list:
    """读 jsonl（坏行**跳过但计数**，不静默当作空库）。"""
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def eml_append_jsonl(path, obj) -> bool:
    """**只追加**一行（F5 只增不删的物理保证）。返回是否写入。"""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def eml_rewrite_jsonl(path, rows) -> bool:
    """整表重写（**只用于状态位演进**：行数与 id 集合必须不变）。"""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        _old = eml_read_jsonl(p)
        if len(rows) != len(_old):
            return False          # ★ F5：行数不许变
        if {r.get("id") for r in rows} != {r.get("id") for r in _old}:
            return False          # ★ F5：id 集合不许变
        with p.open("w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def nogood_record(kind, why, cand, run_id, t) -> dict:
    """构造一条 **nogood（矛盾/失败档案）**记录（append-only 的载体）。

    ★ 依据：ftl-beliefs 的 nogoods —— 「矛盾只累积、不覆盖」。
      本项目老坑：静默覆盖 ⇒ 下次没人知道发生过矛盾。
    ★ 抽成纯函数的意义：**判据要能驱动到的逻辑，才有资格被当判据**
      （变异体「不写档」在内联写法下会假绿 —— 本版实测过一次）。
    """
    return {"t": float(t or 0.0), "run": str(run_id or ""),
            "kind": str(kind or ""), "why": str(why or ""),
            "cand": dict(cand or {})}


def eml_q_features(question: str) -> dict:
    """题型特征（与 `_auto_dispatch._features` 同口径的**子集**，便于比对）。"""
    q = str(question or "")
    return {
        "len": len(q),
        "how": ("如何" in q) or ("怎么" in q) or ("怎样" in q),
        "choice": ("或" in q) or ("还是" in q),
        "multi": (q.count("，") + q.count(",")) >= 2,
        "meta": any(k in q for k in ("本身", "自身", "递归", "元", "整体")),
    }


def episode_from_result(result: dict, t: float = 0.0) -> dict:
    """把一次跑压成**标准化 episode**（WebCondenser 的「标准化日志」思路）。"""
    r = result or {}
    vs = r.get("views") or {}
    ps = r.get("pools") or {}
    duty, cut = {}, []
    for e in ("0", "1", "both", "all"):
        v = vs.get(e) or {}
        _d = (v.get("duty") or {}).get("S")
        if _d is not None:
            duty[e] = float(_d)
        _st = str(v.get("stop_reason") or "")
        if "体力耗尽" in _st:
            cut.append(e)
    tri = r.get("tri_consensus") or []
    tri_rate = None
    if tri:
        try:
            tri_rate = sum(1 for x in tri if x.get("agree")) / float(len(tri))
        except Exception:
            tri_rate = None
    return {
        "run_id": str(r.get("id") or r.get("output_name") or ""),
        "t": float(t or 0.0),
        "q_features": eml_q_features(r.get("question") or ""),
        "route": [str(x) for x in (r.get("route") or [])],
        "mode": str((r.get("dispatch") or {}).get("_parallel_mode") or ""),
        "rounds_cap": dict(r.get("rounds") or {}),
        "cut_layers": cut,
        "duty": duty,
        "tri_rate": tri_rate,
        "n_anchors": len(((ps.get("1") or {}).get("anchors") or [])),
        "n_web": len(((ps.get("1") or {}).get("web_results") or [])),
        "cost": {"tokens": int(r.get("llm_tokens") or 0),
                 "calls": int(r.get("llm_calls") or 0)},
        # ★ [层目标] 四层目标读数必须**出口**，否则 AutoTune 读不到
        #   （「字段有值 ≠ 有出口」—— 本项目已栽过）。
        "goal_readings": layer_goal_summary(vs),
    }


def eml_candidates_from_result(result: dict, ep: dict = None) -> list:
    """**micro 反思**：从一次跑抽候选经验（条件 → 动作，**必须带本跑读数**）。

    ★ 每条候选都必须能回答「这条是拿哪个读数换来的」—— 没有读数的候选
      `gate_check` 第一问就拒（防「凭感觉学」）。
    """
    r = result or {}
    ep = ep or episode_from_result(r)
    out = []
    # ① 截断层 ⇒ 圈数上限偏低（schedule/rounds）
    for e in (ep.get("cut_layers") or []):
        out.append({"kind": "schedule", "cond": {"issue": "cut", "layer": e},
                    "action": {"key": "rounds_delta", "layer": e, "delta": 1},
                    "readings": {"before": {"stop": "体力耗尽"},
                                 "after": {"stop": "期望自然停"}},
                    "why": "该层走满上限仍未触发停止判据（被截断）"})
    # ② 职责未尽 ⇒ 先做问项抽取（probe/carve）
    _short = [e for e, s in (ep.get("duty") or {}).items()
              if float(s) < float(_DUTY_FLOOR)]
    if _short:
        out.append({"kind": "probe",
                    "cond": {"issue": "duty_short", "layers": sorted(_short)},
                    "action": {"key": "carve_first", "layers": sorted(_short)},
                    "readings": {"before": {"duty_S_med": _lv_med(ep, _short)},
                                 "after": {"duty_S_med": "期望上升"}},
                    "why": "层交付面对原始问题的覆盖/相关双低"})
    # ③ 三态一致率低 ⇒ 该题型三态读数不可当判据（guard/decidable）
    _tr = ep.get("tri_rate")
    if _tr is not None and float(_tr) < 0.33:
        out.append({"kind": "guard", "cond": {"issue": "tri_unstable"},
                    "action": {"key": "tri_advisory_only", "rate": round(_tr, 3)},
                    "readings": {"before": {"tri_rate": round(_tr, 3)},
                                 "after": {"tri_rate": "期望上升"}},
                    "why": "三态一致率低于 33%，标签在该跑里不稳"})
    # ④ 成本高于历史 p75 而职责未升 ⇒ **负面**条目（学坏的证据，留痕）
    _c = (ep.get("cost") or {}).get("tokens") or 0
    _p75 = (((r.get("_auto_dispatch") or {}).get("_history") or {})
            .get("tokens_p75") or 0)
    _dmed = _lv_med(ep, list((ep.get("duty") or {}).keys()))
    if _p75 and _c > float(_p75) and (_dmed is None or float(_dmed) < 0.35):
        out.append({"kind": "schedule", "cond": {"issue": "cost_no_gain"},
                    "action": {"key": "note_cost_no_gain",
                               "tokens": _c, "duty_med": _dmed},
                    "readings": {"before": {"tokens": _c, "duty_med": _dmed},
                                 "after": {"duty_med": "期望上升"}},
                    "why": "成本超过历史 p75 而职责未升（只贵不好）"})
    for c in out:
        c["evidence"] = [ep.get("run_id") or ""]
        c["source"] = "engine"
    return out


def _lv_med(ep: dict, layers) -> Optional[float]:
    _v = [(ep.get("duty") or {}).get(e) for e in (layers or [])]
    _v = [float(x) for x in _v if x is not None]
    if not _v:
        return None
    _v.sort()
    n = len(_v)
    return _v[n // 2] if n % 2 else (_v[n // 2 - 1] + _v[n // 2]) / 2.0


def gate_check(cand: dict, playbook: list,
               promote_n: int = _EML_PROMOTE_N) -> tuple:
    """**记忆质量闸**四问（MRRL Layer B）。返回 `(ok, why)`。

      1) evidence      —— 候选必须带本跑**具体读数**（无读数 ⇒ 拒）
      2) contradiction —— 与 active 条目矛盾 ⇒ 不覆盖，进 `contra` 计数
      3) verifiable    —— 动作必须**可被后续跑验证**（能定义 before/after ⇒ 可证）
      4) redline       —— 动作**不许触碰红线**（打分/拦悬置/注入答案 ⇒ 拒）
    ★ 四问**缺一不可**，且每问都要能被变异体单独打红。
    """
    c = cand or {}
    if not isinstance(c.get("readings"), dict) or not c["readings"].get("before"):
        return False, "evidence"
    _act = c.get("action") or {}
    if not isinstance(_act, dict) or not _act.get("key"):
        return False, "verifiable"
    _blob = json.dumps(_act, ensure_ascii=False)
    _bad = ("score", "grade", "rank_claim", "verdict_claim", "answer_text",
            "inject_answer", "block_suspension", "drop_suspension")
    if any(k in _blob for k in _bad):
        return False, "redline"
    # 矛盾检查：同 kind 且 cond 相同但 action 不同 ⇒ 记矛盾（不覆盖）
    for e in (playbook or []):
        if e.get("status") not in ("active", "shadow"):
            continue
        if e.get("kind") != c.get("kind"):
            continue
        if json.dumps(e.get("cond") or {}, sort_keys=True) != \
                json.dumps(c.get("cond") or {}, sort_keys=True):
            continue
        if json.dumps(e.get("action") or {}, sort_keys=True) == \
                json.dumps(_act, sort_keys=True):
            # ★ 同键**不是拒**：它正是 meso 的输入（同向证据 +1）。
            #   旧实现判成 duplicate 拒掉 ⇒ 证据永远累不到 promote_n
            #   ⇒ 「学不会」（探针 T9 抓出的真 bug）。
            return True, "duplicate_merge"
    return True, ""


def eml_merge_candidate(playbook: list, cand: dict, now: float) -> dict:
    """把候选并进 playbook（**只增不删**）。返回**新增的那一条**。

    · 同 `(kind, cond, action)` 已存在 ⇒ 不新增，而是把证据并到旧条目
      （`evidence` 去重追加、`n_evidence+1`）—— 增量而不是重写。
    · 新条目一律 `status="shadow"`（F1 隔离：先不生效）。
    """
    _key = (cand.get("kind"),
            json.dumps(cand.get("cond") or {}, sort_keys=True),
            json.dumps(cand.get("action") or {}, sort_keys=True))
    for e in (playbook or []):
        _ek = (e.get("kind"),
               json.dumps(e.get("cond") or {}, sort_keys=True),
               json.dumps(e.get("action") or {}, sort_keys=True))
        if _ek == _key:
            _ev = list(e.get("evidence") or [])
            for _x in (cand.get("evidence") or []):
                if _x and _x not in _ev:
                    _ev.append(_x)
            e["evidence"] = _ev
            e["n_evidence"] = len(_ev)
            e["t_last"] = float(now)
            return e
    ent = {
        "id": "L%04d" % (len(playbook or []) + 1),
        "kind": cand.get("kind"),
        "cond": cand.get("cond") or {},
        "action": cand.get("action") or {},
        "readings": cand.get("readings") or {},
        "why": cand.get("why", ""),
        "evidence": list(cand.get("evidence") or []),
        # ★ 新条目**至少 1 条证据**（写下它的那次跑本身就是证据）——
        #   从 0 起会让「本就是第一次学到」的条目在 promote 时凭空少一票
        #   （探针 T4 抓出的口径错）。
        "n_evidence": max(1, len(cand.get("evidence") or [])),
        "status": "shadow",
        "weight": 1.0,
        "contra": 0,
        "t_written": float(now),
        "t_last": float(now),
        "t_used": [],
        "source": cand.get("source", "engine"),
        "cost_delta": 0.0,
        "quality_delta": 0.0,
    }
    playbook.append(ent)
    return ent


def eml_promote(playbook: list, promote_n: int = _EML_PROMOTE_N) -> list:
    """**meso 反思**：同向证据够 ⇒ `shadow → active`；反向证据够 ⇒ 降级。

    ★ **双边记账（F2）**：只有「质量上升」或「质量未变但成本下降**且**质量
      不降」才允许升级；`quality_delta < 0` 或「只省成本」⇒ 不升。
    ★ 返回状态变更列表（由调用方决定是否落盘）。
    """
    changes = []
    for e in (playbook or []):
        if e.get("status") != "shadow":
            continue
        _n = int(e.get("n_evidence", 0) or 0)
        _qd = float(e.get("quality_delta", 0.0) or 0.0)
        _cd = float(e.get("cost_delta", 0.0) or 0.0)
        if _n < int(promote_n):
            continue
        if int(e.get("contra", 0) or 0) >= int(promote_n):
            continue
        # ★ 只省成本 / 质量下降 ⇒ 不许升级（防「学坏」）
        if _qd < 0:
            continue
        if _qd == 0.0 and _cd < 0.0:
            changes.append({"id": e.get("id"), "to": "blocked_cost_only"})
            continue
        e["status"] = "active"
        e["weight"] = min(1.0, 0.5 + 0.25 * _n)
        changes.append({"id": e.get("id"), "to": "active"})
    return changes


def eml_note_contra(playbook: list, entries, why: str = "") -> int:
    """记一次**反向证据**（不覆盖、不删除，只计数）。"""
    _ids = {e.get("id") for e in (entries or []) if e.get("id")}
    n = 0
    for e in (playbook or []):
        if e.get("id") in _ids:
            e["contra"] = int(e.get("contra", 0) or 0) + 1
            e["contra_last"] = why
            n += 1
    return n


def eml_sweep_forget(playbook: list, now: float,
                     halflife: float = _EML_HALFLIFE_DAYS,
                     retire_recency: float = _EML_RETIRE_RECENCY,
                     promote_n: int = _EML_PROMOTE_N) -> list:
    """**遗忘清扫**（MRRL 的 forgetting sweep）：陈旧 + 从未用过 + 证据弱 ⇒ retired。

    ★ 只改 `status`，**不删行**（红线「失败留痕」）。
    """
    out = []
    for e in (playbook or []):
        if e.get("status") not in ("shadow", "active"):
            continue
        _age_days = max(0.0, (float(now) - float(e.get("t_last", now))) / 86400.0)
        _rec = 0.5 ** (_age_days / float(halflife or 14.0))
        if _rec >= float(retire_recency):
            continue
        if (e.get("t_used") or []):
            continue
        if int(e.get("n_evidence", 0) or 0) >= int(promote_n):
            continue
        e["status"] = "retired"
        e["retired_why"] = ("recency=%.3f<%.3f 且未被用过且证据< %d"
                            % (_rec, retire_recency, promote_n))
        out.append(e)
    return out


def eml_recall(playbook: list, kind: str, now: float,
               halflife: float = _EML_HALFLIFE_DAYS,
               top_k: int = _EML_TOP_K) -> list:
    """**读**：按 `recency^0.5 × 证据强度 × 相关度` 排序取 top-k（只取 active）。

    ★ 只取 `active`：`shadow` 一律**不生效**（F1 隔离）——「读到但不用」与
      「读不到」在留痕里区分开。
    """
    out = []
    for e in (playbook or []):
        if e.get("status") != "active":
            continue
        if str(e.get("kind")) != str(kind):
            continue
        _age_days = max(0.0, (float(now) - float(e.get("t_last", now))) / 86400.0)
        _rec = 0.5 ** (_age_days / float(halflife or 14.0))
        _ev = 1.0 - 0.5 ** float(e.get("n_evidence", 0) or 0)
        _w = float(e.get("weight", 1.0) or 1.0)
        # ★ [RRIF · 吸收 evermind] 第四维 **Frequency**：被用过几次。上限 1.5
        #   防止「高频但低质」的条目永远霸榜（recency 与 weight 仍在制衡）。
        _freq = min(1.5, 1.0 + 0.1 * len(e.get("t_used") or []))
        _score = (_rec ** 0.5) * _ev * _w * _freq
        out.append({"id": e.get("id"), "score": round(_score, 6),
                    "action": e.get("action") or {}, "cond": e.get("cond") or {}})
    out.sort(key=lambda x: -x["score"])
    return out[:int(top_k)]


def eml_aggregate_macro(playbook: list, now: float,
                        sim_thr: float = _EML_AGG_SIM) -> list:
    """**macro 反思**：把同类 active 条目聚成**父条目**（只做索引，不重写原文）。

    ★ ACE 教训：**不许压缩重写**。父条目只写「哪几条属于同一族」+ 共同动作键，
      子条目原文一字不动。
    """
    _act = [e for e in (playbook or []) if e.get("status") == "active"]
    used, parents = set(), []
    for i, a in enumerate(_act):
        if a.get("id") in used:
            continue
        fam = [a]
        for b in _act[i + 1:]:
            if b.get("id") in used:
                continue
            if a.get("kind") != b.get("kind"):
                continue
            if str((a.get("action") or {}).get("key")) != \
                    str((b.get("action") or {}).get("key")):
                continue
            _t1 = json.dumps([a.get("cond"), a.get("action")],
                             ensure_ascii=False)
            _t2 = json.dumps([b.get("cond"), b.get("action")],
                             ensure_ascii=False)
            try:
                if float(_sim3(_t1, _t2)) < float(sim_thr):
                    continue
            except Exception:
                continue
            fam.append(b)
            used.add(b.get("id"))
        if len(fam) >= 2:
            used.add(a.get("id"))
            parents.append({"kind": a.get("kind"),
                            "key": (a.get("action") or {}).get("key"),
                            "members": [x.get("id") for x in fam],
                            "note": "父条目只做索引，子条目原文不动（ACE 教训）"})
    return parents


def eml_summarize(playbook: list, limit: int = 40) -> str:
    """生成 `MEMORY.md`（人可读摘要；自动，不是权威存储）。

    ★ 与 ACE 的「不压缩」一致：摘要**只做索引**（id + 条件 + 动作），
      完整证据留在 jsonl 里，摘要丢了也不影响行为。
    """
    rows = list(playbook or [])
    cnt = {}
    for e in rows:
        cnt[e.get("status", "?")] = cnt.get(e.get("status", "?"), 0) + 1
    L = ["# 元DGTF 记忆库（EML 自动生成）", "",
         "> 本文件是**索引**，权威数据在 `playbook.jsonl` / `episodes.jsonl`。",
         "> 状态：`active` 生效 / `shadow` 隔离观察 / `retired` 已遗忘"
         "（**行仍在**，只改状态位）。", "",
         "计数：" + "、".join("%s=%d" % (k, cnt[k]) for k in sorted(cnt)), ""]
    for st in ("active", "shadow", "retired"):
        sub = [e for e in rows if e.get("status") == st]
        if not sub:
            continue
        L.append("## %s（%d）" % (st, len(sub)))
        L.append("")
        for e in sub[:limit]:
            L.append("- `%s` [%s] %s ⇒ `%s`（证据 %d，反向 %d）"
                     % (e.get("id"), e.get("kind"),
                        json.dumps(e.get("cond") or {}, ensure_ascii=False)[:70],
                        json.dumps(e.get("action") or {},
                                   ensure_ascii=False)[:60],
                        int(e.get("n_evidence", 0) or 0),
                        int(e.get("contra", 0) or 0)))
        L.append("")
    return "\n".join(L)


def eml_write_memory_md(playbook: list, base=None, dirpath=None) -> bool:
    try:
        d = Path(dirpath) if dirpath else eml_dir(base)
        d.mkdir(parents=True, exist_ok=True)
        (d / _EML_MEMORY_MD).write_text(eml_summarize(playbook),
                                        encoding="utf-8", newline="\n")
        return True
    except Exception:
        return False


# ============================================================
# 自调优（AutoTune）—— 从**跨跑 episode** 自动推出最优「模式 / 层集 / 圈数」。
#
# 依据（前沿，2024-2025）：
#   · Successive Halving / Hyperband（Jamieson & Talwalkar 2016；Li et al. 2017）：
#     预算受限下**先粗筛再精算**，把算力从劣配里抽回给优配。本处用它排「档位表」。
#   · 多目标**不做标量化**：质量↑ / 成本↓ 各成一轴，只取**帕累托前沿**。
#     理由与「悬置不打分」同一哲学：给成本拍一个假币汇率，等于凭空打分。 ──
#     不做「质量 = α·q − β·c」那种加权和（β 无物理来源 ⇒ 结论不可复现）。
#   · 冷启动 → 暖启动：用 EML `playbook` 的 active 条目给候选**排序**（迁移）。
#
# ★ 红线自检：本机制**只产出建议**（`autotune_recommend`），**不自动改行为** ——
#   写回默认配置由显式 `autotune_apply` 执行。理由同「停止与清算分开」：
#   读数是读数、决策是决策，**建议与执行分开**。
# ============================================================

#: [AutoTune] 设计空间的层序（与引擎 route 取值一致）。
_AT_LAYERS = ("0", "1", "both", "all")
#: [AutoTune] successive-halving 的最小圈预算锚（保底至少这么多圈再判优劣）。
_AT_MIN_RES = 2


def _at_num(x, d=None):
    """安全取数：非有限数 / 不可转 ⇒ 返回默认（**区分「没有」与「是 0」**）。"""
    try:
        v = float(x)
        if v != v or v in (float("inf"), float("-inf")):
            return d
        return v
    except Exception:
        return d


def _at_med(xs):
    """中位数（偶数取中间两数均值）；空 ⇒ None（**不是 0**）。"""
    xs = sorted(x for x in (xs or []) if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


#: [层目标] 四层目标语义的**读数键名**（与用户战略指令逐字对应）。
#:   ★ 每条读数都是「**越大越接近该层目标**」，但**各自独立成轴** ——
#:     绝不合成一个总分（红线「未对齐合法」：不同层的目标本就不在同一尺度）。
_LG_KEYS = {
    "0": "excavate",      # 修行：层面挖掘的**边际新增趋零度**（挖不动了 ⇒ 趋近无穷收敛）
    "1": "settle",        # 研究：层面**答案确定率**（有限收敛）
    "both": "fuse",       # 对撞：由发散∩有限**融合生成**的新层面率
    "all": "crystallize",  # 元：记忆结晶 / 决策 / 行动 / 回看的**留痕完整度**
}
#: [层目标] 元层「回看」的最小留痕项数（结晶 + 决策 + 行动 + 回看 四件事）。
_LG_META_MIN = 4


def _lg_ratio(num, den):
    """安全比率：分母 <=0 或非数 ⇒ **None**（不是 0）。"""
    try:
        _n = float(num)
        _d = float(den)
    except (TypeError, ValueError):
        return None
    if _d <= 0:
        return None
    return max(0.0, min(1.0, _n / _d))


def _lg_diverge_state(v: dict):
    return str(((v or {}).get("divergence") or {}).get("state") or "").strip()


def _lg_aspect_margin(hist, total=None):
    """[Heaps 饱和] 层面序列的**边际新增率** = 末段新增 / 上段新增。

    依据 Heaps' law：词表增长 V(n)=K·n^β（β∈[0.4,0.6]），**边际新增趋零**
    ⇔ 「挖到不能再挖」（SSR 饱和尺度 m̃=αN^μ 之后 ⟨h(m)⟩≈N）。

    · `hist` = 逐圈的**累计层面数** `[V1, V2, …]` ⇒ 新增 = 相邻差。
    · 返回 = 末段新增 / 上段新增（**越小越饱和**；0 = 已完全挖尽）。
    · 无 hist（老产物）⇒ 退回「单点估计」：`1/(1+total)` 的**下限形态**，
      并**显式标注** `basis="fallback"`，不冒充逐圈读数。
    · 两条都没有 ⇒ None（**不是 0** —— 「没测」与「测出是 0」两回事）。
    """
    xs = [float(x) for x in (hist or []) if x is not None]
    if len(xs) >= 3:
        gains = [max(0.0, xs[i] - xs[i - 1]) for i in range(1, len(xs))]
        if not gains:
            return None
        half = max(1, len(gains) // 2)
        late = sum(gains[-half:]) / float(half)
        early = sum(gains[:half]) / float(half)
        if early <= 1e-12:
            return 0.0 if late <= 1e-12 else None
        return max(0.0, min(1.0, late / early))
    return None


def _lg_stag_ratio(items, ups):
    """[CORE 停滞罚] 产出层面与**上游文本**的重合率（0-1；1 = 全复读）。

    ★ 返回 None 表示**算不出**（无上游文本 / 无产出）—— 不罚也不假装。
    """
    _its = [str((x or {}).get("target") or (x or {}).get("desc")
                or (x or {}).get("text") or "").strip()
            for x in (items or [])]
    _its = [x for x in _its if x]
    _ups = [str(x).strip() for x in (ups or []) if str(x).strip()]
    if not _its or not _ups:
        return None
    # 归一到字符集合的 Jaccard（与 `_similar` 同族，但这里只做**重合度**）。
    def _toks(s):
        return {c for c in s if not c.isspace()}
    hit = 0
    for s in _its:
        ts = _toks(s)
        if not ts:
            continue
        best = 0.0
        for u in _ups:
            tu = _toks(u)
            if not tu:
                continue
            j = len(ts & tu) / float(len(ts | tu))
            best = max(best, j)
        if best >= 0.8:          # 与某条上游近乎逐字相同 ⇒ 记为复读
            hit += 1
    return hit / float(len(_its))


def layer_goal_readings(views: dict) -> dict:
    """[层目标] 把 `views` 压成**每层一条目标读数**（纯函数，可判据）。

    读数**按用户给的四层目标定义**，每条都回答「这一层离它的目标还差多少」：

      · `0` 修行 —— `excavate` = 层面挖掘的**边际新增趋零度**。
        分子 = `aspect_units` 数，分母 = 实际跑的圈数（`rounds_run`）。
        ★ 语义：修行层要在**最少圈数**里把层面挖尽。若圈数多而层面不再增长
          （比值趋 0）⇒ 已「挖到不能再挖」⇒ **趋近无穷收敛**。
          故本读数 = **1 − 归一化边际新增**：边际新增越低 ⇒ 读数越高。
        辅读：`divergence.state == "收敛"/"停滞"` ⇒ 属于「趋近收敛」。
      · `1` 研究 —— `settle` = 层面**答案确定率** = `decidable_product`
        已答数 / 层面总数（`covered_answer` 的 `answered/total` 同源）。
        辅读：`belief_status_counts` 里 resolved/settled 占比。
      · `both` 对撞 —— `fuse` = **融合生成率** = 对撞产出的**新层面数**
        （`duel_suspensions` + `belief_items` 中对撞来源的条目）/ 上游可用层面数。
        ★ 语义：融合「无穷发散 ∩ 有限确定」⇒ **创新出新的发散/有限层面**。
      · `all` 元 —— `crystallize` = **留痕完整度** = 四件事（结晶/决策/行动/回看）
        中真正留下产物的项数 / 4。产出面 = `meta_closure`（结晶+回看）、
        `engagements`（决策）、`suspensions`（行动/交代）。
      ★ 任一层缺产物 ⇒ 该层读数 = **None**（不印 0 冒充「读了是 0」）。
    """
    vs = views or {}
    out = {}
    for L in _AT_LAYERS:
        v = vs.get(L) or {}
        if not v:
            continue
        d = {}
        if L == "0":
            # ★ 依据 Heaps' law / type-token 饱和：修行层「挖到不能再挖」的
            #   判据是**词汇/层面的边际新增趋零**（ΔV/Δn → 0），不是总量多少。
            #   ★ 别用「总量/圈数」当读数：那让「挖得多」反而读数低（方向错）。
            _units = len(v.get("aspect_units") or [])
            _rr = int(_at_num(v.get("rounds_run"), 0) or 0)
            _hist = [_at_num(x) for x in (v.get("aspect_hist") or [])]
            _hist = [x for x in _hist if x is not None]
            _margin = _lg_aspect_margin(_hist, _units)
            d["excavate"] = _margin          # 边际新增率（越低越接近挖尽）
            d["excavate_closed"] = (None if _margin is None
                                    else round(1.0 - _margin, 4))
            d["n_aspects"] = _units
            d["rounds_run"] = _rr
            _st = _lg_diverge_state(v)
            d["conv_state"] = _st
            d["converging"] = (_st in ("收敛", "停滞"))
        elif L == "1":
            # ★ 依据「content entropy 收敛」+ **伪收敛警告**（2025）：熵降是
            #   收敛轨迹，但熵降 ≠ 质量 —— 可能是「过早忽略关键信息」。
            #   ⇒ 研究层读数**必须**同时含「确定率」与「非退化」两项，
            #     两者都好才算「有限收敛」；只有熵降 ⇒ 报 pseudo_convergence。
            # ★ 真实原料 = `settlement`（`answered`/`total`，与 `coverage_of`
            #   同源）。原读 `covered_answer` 是**臆造键** —— 真跑层 1 的 view
            #   里根本没有它 ⇒ `settle` 恒 null（判据全绿是因为夹具自带该键）。
            _co = v.get("settlement") or v.get("covered_answer") or {}
            _ans, _tot = _co.get("answered"), _co.get("total")
            if _ans is None:
                # 再兜一层：由 covered/uncovered 层面数推（同源口径）。
                _ca = v.get("covered_aspects") or []
                _ua = v.get("uncovered_aspects") or []
                if _ca or _ua:
                    _ans, _tot = len(_ca), len(_ca) + len(_ua)
            d["settle"] = _lg_ratio(_ans, _tot)
            # 非退化：答案面**确实有实质产出**（不是「全部未答」也算齐整）。
            _nz = _at_num(_ans, 0.0) or 0.0
            d["non_degenerate"] = (_nz > 0) if _tot else None
            _bs = v.get("belief_status_counts") or {}
            _tot_b = sum(int(x or 0) for x in _bs.values()) if _bs else 0
            _res_b = (int(_bs.get("resolved", 0) or 0)
                      + int(_bs.get("settled", 0) or 0))
            d["belief_resolved_rate"] = _lg_ratio(_res_b, _tot_b)
            _st = _lg_diverge_state(v)
            d["conv_state"] = _st
            d["converging"] = (_st == "收敛")
            # ★ 伪收敛 = 声称收敛但答案面退化（一个都没答上）。
            d["pseudo_convergence"] = bool(
                _st in ("收敛", "停滞") and _tot and not _nz)
        elif L == "both":
            # ★ 依据 CORE（Pandey et al., NeurIPS 2025）：只用「产出量」会
            #   把「复读上游、一分不发」读成满分融合 ⇒ 必须配**语义停滞罚**
            #   （semantic stagnation penalty），与 repetition penalty 同源。
            _duel = v.get("duel_suspensions") or []
            _bel = v.get("belief_items") or []
            _new = len(_duel) + len(_bel)
            _up = int(_at_num(v.get("upstream_layers"), 0) or 0)
            if _up <= 0:
                _bm = v.get("both_quota") or {}
                _up = int(_at_num(_bm.get("upstream"), 0) or 0)
            # 停滞 = 新层面与上游层面**文本重合**的比例（越高越像复读）。
            _stag = v.get("sem_stagnation")
            _stag = _at_num(_stag)
            if _stag is None:
                _stag = _lg_stag_ratio(_duel + _bel,
                                       v.get("upstream_texts") or [])
            d["fuse_raw"] = _lg_ratio(_new, _up) if _up > 0 else None
            # CORE 式：融合分 = 产出率 × (1 − 停滞罚)，各因子都有物理来源。
            if d["fuse_raw"] is None:
                d["fuse"] = None
            elif _stag is None:
                d["fuse"] = d["fuse_raw"]        # 算不出停滞 ⇒ 不罚也不假装
            else:
                d["fuse"] = round(d["fuse_raw"] * (1.0 - min(1.0, _stag)), 4)
            d["sem_stagnation"] = (None if _stag is None else round(_stag, 4))
            d["n_new"] = _new
            d["n_upstream"] = _up
        elif L == "all":
            _clo = v.get("meta_closure") or {}
            _hits = 0
            if _clo:
                _hits += 1                                   # 结晶（闭环清算）
                if _clo.get("total") is not None:
                    _hits += 1                               # 回看（张力总数盘点）
            if (v.get("engagements") or []):
                _hits += 1                                   # 决策
            if (v.get("suspensions") or []):
                _hits += 1                                   # 行动/交代
            d["crystallize"] = round(_hits / float(_LG_META_MIN), 4)
            d["n_hits"] = _hits
            d["meta_clean"] = bool(_clo.get("clean")) if _clo else None
        out[L] = d
    return out


_LG_STOP_MARGIN = 0.1      # 修行层：边际新增率 < 此值 ⇒ 判「挖尽」
_LG_STOP_FLAT_N = 2        # 研究/对撞：连续 N 圈读数不涨 ⇒ 判「不再涨」
_LG_STOP_STAG = 0.8        # 对撞：语义停滞率 >= 此值 ⇒ 判「复读」


# ══════════════════════════════════════════════════════════════
# [第六期 · 各环节量化] 四个**零成本**读数（纯函数、不调 LLM）
#   依据见 `_各环节量化与降本依据_v12333.md`：
#     ① BenchDrift(arXiv:2608.11694) / reliable@k(arXiv:2512.14754)
#     ② SIEV(arXiv:2510.18134) 对抗性依从率
#     ③ RASC(NAACL2025) / DeepConf(ICLR2026) / Think@n 的早停
#     ④ 信息瓶颈：语义密度（>5 个无信息 token ⇒ 性能降 15%+）
#   ★ 四条通则：**缺输入 ⇒ 不表态**（回 None，不是 0）；
#     **只出读数与线索**，不改产物、不删候选（悬置不打分）。
# ══════════════════════════════════════════════════════════════

_YY_DIV_LOW = 0.30      # 阴阳分歧度低于此 ⇒ 判「假对撞」（依据 ②）


def yin_yang_divergence(yin, yang) -> dict:
    """[依据 ②] 阴阳两臂的**分歧度** —— 它们到底有没有在「对撞」。

    SIEV 的「对抗性依从率」：反题与正题**实际不一致**的比例。过低 ⇒
    模型只是换个说法复述（pS 高但推理深度低 = **假对撞**）。

    口径（两向都算，取最大相似度作「重合」）：
      · `divergence = 1 - max_i max_j sim(yin_i, yang_j)`
        —— 只有两臂**没有任何一对**说得像，才算真分歧。
      · ★ 用 `_overlap_coef`（本仓库既有的词面重合口径）+ `_similar`
        两条并列尺子，与去重判据同源（**同一把尺子**）。

    返回 `{n_yin, n_yang, max_sim, divergence, verdict}`；
    **任一侧为空 ⇒ divergence=None 且 verdict=""**（不表态）。
    """
    _ys = [str(x) for x in (yin or []) if str(x).strip()]
    _zs = [str(x) for x in (yang or []) if str(x).strip()]
    d = {"n_yin": len(_ys), "n_yang": len(_zs)}
    if not _ys or not _zs:
        d.update({"max_sim": None, "divergence": None, "verdict": ""})
        return d
    _best = 0.0
    for a in _ys:
        for b in _zs:
            _ov = _overlap_coef(a, b, _KW_TOP_N)
            _si = 1.0 if _similar(a, b, _DUP_SIM) else 0.0
            _best = max(_best, _ov, _si)
    d["max_sim"] = round(_best, 4)
    d["divergence"] = round(1.0 - _best, 4)
    d["verdict"] = ("fake_duel" if d["divergence"] < _YY_DIV_LOW else "ok")
    return d


_RF_THIN_RATIO = 0.35   # 重述长度不到原问题的这个比例 ⇒ 判 thin（信息太薄）
_RF_DRIFT_RATIO = 0.20  # 关键词覆盖率低于此 ⇒ 判 drifted（跑偏）


def restate_fidelity(question: str, anchor: str) -> dict:
    """[依据 ①] 锚点重述对原问题的**保真度** —— 重述跑偏则下游全白跑。

    BenchDrift / reliable@k 实测：含义保持的重述会让答案漂移，
    **强模型损失更大**。所以最上游该有这道闸门（**零 LLM 成本**）。

    口径（词面代理，不调模型）：
      · `coverage` = 原问题关键词被锚点覆盖的比例（漏掉 = 换题）；
      · `ratio`    = 锚点长度 / 原问题长度（过短 = 信息被压没了）。

    返回 `{coverage, ratio, fidelity, verdict}`；
    `verdict` ∈ `ok / thin / drifted`；**任一输入为空 ⇒ 全 None + ""**。
    """
    _q = str(question or "").strip()
    _a = str(anchor or "").strip()
    if not _q or not _a:
        return {"coverage": None, "ratio": None,
                "fidelity": None, "verdict": ""}
    _kq = _kw(_q, _KW_TOP_N) or set()
    _ka = _kw(_a, _KW_TOP_N) or set()
    _cov = (len(_kq & _ka) / float(len(_kq))) if _kq else None
    _rat = len(_a) / float(len(_q)) if _q else None
    if _cov is None or _rat is None:
        return {"coverage": None, "ratio": None,
                "fidelity": None, "verdict": ""}
    _cov = round(_cov, 4)
    _rat = round(_rat, 4)
    # 保真度 = 覆盖为主、长度惩罚为辅（长度只作**上限约束**，不奖长）。
    _pen = min(1.0, _rat / _RF_THIN_RATIO) if _rat < _RF_THIN_RATIO else 1.0
    _fid = round(_cov * _pen, 4)
    if _cov < _RF_DRIFT_RATIO:
        _vd = "drifted"
    elif _rat < _RF_THIN_RATIO:
        _vd = "thin"
    else:
        _vd = "ok"
    return {"coverage": _cov, "ratio": _rat, "fidelity": _fid, "verdict": _vd}


_SD_FILLER = (
    "的", "了", "是", "在", "和", "与", "或", "及", "这", "那", "一个", "一种",
    "非常", "十分", "比较", "可能", "也许", "大概", "其实", "实际上", "总的来说",
    "综上所述", "值得注意的是", "需要指出的是", "我们可以看到", "众所周知",
    "首先", "其次", "然后", "最后", "另外", "此外", "而且", "因此", "所以",
)


def _sd_is_punct(ch: str) -> bool:
    """标点 / 符号判定（Unicode 类别 P* 或 S*）。**内联实现**，不引新依赖。"""
    try:
        return unicodedata.category(ch)[0] in ("P", "S")
    except Exception:
        return False


def semantic_density(text: str) -> "float | None":
    """[依据 ④] 内容的**语义密度** —— 每字里有多少是任务相关信息。

    信息瓶颈口径：`R = I(X;Y)/H(X)`，优秀提示 R > 0.6；**超过 5 个
    无信息 token ⇒ 性能降 15%+**。这里用**零成本**词面代理：
      · 分母 = 去掉空白后的字符数；
      · 分子 = 内容词字符数（扣掉**填充语**与**纯标点**）。
    返回 `[0,1]`；**空输入 ⇒ None**（不表态）。
    """
    _t = str(text or "")
    if not _t.strip():
        return None
    _chars = [c for c in _t if not c.isspace()]
    if not _chars:
        return None
    _body = _t
    for _f in _SD_FILLER:
        _body = _body.replace(_f, "")
    _info = sum(1 for c in _body
                if not c.isspace() and not _sd_is_punct(c))
    return round(min(1.0, _info / float(len(_chars))), 4)


_LG_ACT_SETTLE_LOW = 0.6      # 研究层：确定率 < 此值 ⇒ 优先答未答层面
_LG_ACT_ASPECT_MIN = 4         # 修行层：层面数 < 此值 ⇒ 还没铺够，别急着深挖


def layer_goal_action_hint(entry: str, goal: dict, prev: list = None) -> str:
    """[四层目标 → **圈内动作**] 把「本层目标读数」转成一条**形状指引**。

    ★ 与 `layer_goal_stop_signal` 的分工：
      · `stop_signal` 管**停不停**（层末，写进 `_stop_reasons`）；
      · `action_hint` 管**怎么写**（圈内，插进 prompt 的 `【本轮形状】` 之后）。
      两者**共用同一批读数**，但作用在不同时刻 —— 这就是「读数进入运行」的完整形态。

    ★ 红线遵守：
      · **缺读数 ⇒ 返回空串**（不表态）。「没测」不等于「测出来差」，
        更不能因此给模型下指令（那会把"没数据"变成"假约束"）。
      · **不返 role 名、不改 role 枚举**：只出**文本指引**，
        由 prompt 组装处拼接 ⇒ role 语义单一真相源不动。
      · **达标 ⇒ 返回空串**：目标是「做到就闭嘴」，不是「每圈都唠叨」。

    返回：一段以 `\n\n【本层目标的形状指引...】` 开头的文本，或空串。
    """
    g = goal or {}
    _e = str(entry or "")

    if _e == "0":
        # 修行层（趋近无穷收敛 = 把各面挖到不能再挖）
        _v = _lg_num(g.get("excavate"))
        _na = _lg_num(g.get("n_aspects"))
        if _v is not None and _v < _LG_STOP_MARGIN:
            # 边际新增趋零 ⇒ Heaps 饱和：别再往同一面里挖，换未挖的面。
            return (
                "\n\n【本层目标的形状指引 · 修行层趋近无穷收敛】\n"
                "上一圈之后，**层面的边际新增已经趋零**（本圈不再是"
                "「还没挖够」，而是「这一面挖到了底」）。\n"
                "  · 所以这一圈**不要**在已经写出来的面上继续加深——那是重复挖掘。\n"
                "  · 要换一个**尚未显形的切面**进去（问「这个问题还有哪个面是我"
                "一次都没碰过的」）。\n"
                "  · 若确实找不出新面，如实说「这一面已见底」，"
                "**不要**把旧面换个说法再交一次。\n"
            )
        if _na is not None and _na < _LG_ACT_ASPECT_MIN:
            # 面还没铺够 ⇒ 别急着深挖（对应「修行 = 广度优先摊开各面」）。
            return (
                "\n\n【本层目标的形状指引 · 修行层趋近无穷收敛】\n"
                "本层目前显形的层面数还很少（广度不够）。\n"
                "  · 这一圈**优先摊开新面**，不要把少数几个面往深里挖。\n"
                "  · 能摆出来的都摆出来，不必每条都追到底。\n"
            )
        return ""

    if _e == "1":
        # 研究层（趋近有限收敛 = 给各面确定答案）
        _v = _lg_num(g.get("settle"))
        if _v is not None and _v < _LG_ACT_SETTLE_LOW:
            # ★ 伪收敛警告（依据：熵降 ≠ 高质量）：确定率低不等于"写得多"，
            #   而是"该定的没定"。要**优先答未答的层面**。
            return (
                "\n\n【本层目标的形状指引 · 研究层趋近有限收敛】\n"
                "本层的**确定率还偏低**——已经显形的面里，还有一批没有确定答案。\n"
                "  · 这一圈**优先给未答的面一个答案**（哪怕答案是「此处未生，"
                "缺的是 X」也算答）。\n"
                "  · 不要把力气花在**重复论证已经定下来的面**上。\n"
                "  · ★ 注意：写得长不等于收敛——**没定的还是不收敛**。\n"
            )
        return ""

    if _e == "both":
        # 对撞层（融合生成）
        _st = _lg_num(g.get("sem_stagnation"))
        if _st is not None and _st >= _LG_STOP_STAG:
            # CORE 停滞罚：高停滞 ⇒ 复读，强制换**融合轴**。
            return (
                "\n\n【本层目标的形状指引 · 对撞层融合生成】\n"
                "本层的**语义停滞率偏高**：这一圈产出的东西，与上游 view 的"
                "文本重合太多（像复述，不像融合）。\n"
                "  · 这一圈**必须换一个融合轴**——不是换措辞，是换"
                "「把哪两个面撞在一起」。\n"
                "  · 自问：上游给的这些面里，有哪两个**从没被放在一起看过**？"
                "把它们撞一次。\n"
                "  · 撞出来的东西必须**上游任何一边单独都给不出**，否则不算融合。\n"
            )
        _fu = _lg_num(g.get("fuse"))
        if _fu is not None and _fu < 0.3:
            return (
                "\n\n【本层目标的形状指引 · 对撞层融合生成】\n"
                "本层的融合产出偏少（新东西不多）。\n"
                "  · 别停在「两边的共同点」上——那只叫对齐，不叫融合。\n"
                "  · 去看**两边互相矛盾的地方**，矛盾处才有真融合。\n"
            )
        return ""

    if _e == "all":
        # 元层（记忆结晶 / 决策 / 行动 / 回看）
        _cr = _lg_num(g.get("crystallize"))
        _hits = _lg_num(g.get("n_hits"))
        if _cr is not None and _cr < 1.0:
            _miss = []
            if _hits is not None:
                # n_hits < 4 ⇒ 四件事里有缺的（顺序对应 layer_goal_readings 的累加序）
                if _hits < 1:
                    _miss.append("闭环清算（把张力盘一遍、看有没有漏交代的）")
                if _hits < 2:
                    _miss.append("回看（说清本层一共处理了多少张力）")
                if _hits < 3:
                    _miss.append("决策（把能裁的裁掉，不能裁的写清缺什么）")
                if _hits < 4:
                    _miss.append("行动/交代（每一条悬置都要有去处）")
            _miss_txt = ("；".join(_miss) if _miss
                         else "四件事里还缺的那件")
            return (
                "\n\n【本层目标的形状指引 · 元层记忆结晶】\n"
                "本层是**元层**：要对下面三层的产物做记忆结晶 / 决策 / 行动，"
                "并回看整个过程。现在还没结晶完整。\n"
                f"  · 这一圈优先补上：**{_miss_txt}**。\n"
                "  · 结晶不是「再想一遍」，是**把已经发生的事记下来**"
                "（依据 DGM：archive 的价值在不丢东西，而不是再搜一遍）。\n"
                "  · 缺的如果补不上，如实标成悬置——**不许拿 both 搪塞**。\n"
            )
        return ""

    return ""


def layer_goal_stop_signal(entry: str, goal: dict, prev: list = None):
    """[四层目标 → 停因] 把「本层目标读数」转成一条**停止信号**。

    这是把四层目标**接进运行**的那一步：读数不再只是事后统计，而是每层每圈
    判断「这层还有没有必要再跑」的一条依据。

    返回 `(hit, why)`：
      · `hit=True` ⇒ 调用方给 `_stop_reasons` 加一条理由（**只加理由**）；
      · **没读数 ⇒ `(False, "")`** —— 不表态（「没测」与「测出来差」两回事）。

    逐层判据（依据见 `layer_goal_readings`）：
      · `0`  修行：`excavate` < `_LG_STOP_MARGIN`（Heaps 饱和 = 层面挖尽）
      · `1`  研究：`settle` 连续 `_LG_STOP_FLAT_N` 圈不涨（确定率不再涨）
      · `both` 对撞：`fuse` 连续不涨 **或** `sem_stagnation` >= 阈值（CORE 罚触顶）
      · `all` 元：`crystallize` >= 1.0（四件事齐 = 结晶完成）
    """
    g = goal or {}
    _e = str(entry or "")
    if _e == "0":
        _v = _lg_num(g.get("excavate"))
        if _v is None:
            return False, ""
        # ★ 只在「确有逐圈序列」时才对边际率下结论；n_aspects 缺 ⇒ 不表态。
        if _v < _LG_STOP_MARGIN and (_lg_num(g.get("n_aspects")) or 0) > 0:
            return True, ("修行目标已达成（层面边际新增率 %.3f < %.2f，"
                          "Heaps 饱和 ⇒ 挖到不能再挖）" % (_v, _LG_STOP_MARGIN))
        return False, ""
    if _e == "1":
        _v = _lg_num(g.get("settle"))
        if _v is None:
            return False, ""
        if _lg_flat(prev, "settle", _LG_STOP_FLAT_N):
            return True, ("研究目标已达成（确定率连续 %d 圈不涨 = %.3f，"
                          "各层面已有答案）" % (_LG_STOP_FLAT_N, _v))
        return False, ""
    if _e == "both":
        _stag = _lg_num(g.get("sem_stagnation"))
        if _stag is not None and _stag >= _LG_STOP_STAG:
            return True, ("对撞目标受阻（语义停滞率 %.2f >= %.2f，"
                          "只剩复读上游，没融合出新的层面）"
                          % (_stag, _LG_STOP_STAG))
        _v = _lg_num(g.get("fuse"))
        if _v is None:
            return False, ""
        if _lg_flat(prev, "fuse", _LG_STOP_FLAT_N):
            return True, ("对撞目标已达成（融合分连续 %d 圈不涨 = %.3f）"
                          % (_LG_STOP_FLAT_N, _v))
        return False, ""
    if _e == "all":
        _v = _lg_num(g.get("crystallize"))
        if _v is None:
            return False, ""
        if _v >= 1.0 - 1e-9:
            return True, ("元层目标已达成（记忆结晶/回看/决策/行动 四件齐备 "
                          "= %.2f）" % _v)
        return False, ""
    return False, ""


def _lg_flat(prev, key, n):
    """读数序列 `prev`（含当圈）里 `key` **连续 n 圈不涨** ⇒ True。

    · 序列不足 n+1 条 ⇒ False（**样本不足不表态**）；
    · 有任一读数为 None ⇒ False（缺读数不参与「不涨」判断）。
    """
    if not prev or len(prev) < int(n) + 1:
        return False
    _xs = []
    for row in prev[-(int(n) + 1):]:
        _x = _lg_num((row or {}).get(key))
        if _x is None:
            return False
        _xs.append(_x)
    return all(_xs[i + 1] <= _xs[i] + 1e-12 for i in range(len(_xs) - 1))


def _lg_num(x):
    """把读数转 float；**非数 ⇒ None**（不是 0 —— 没测 ≠ 测出来 0）。"""
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def layer_goal_summary(views: dict) -> dict:
    """[层目标] 只回**每层的主读数**（`_LG_KEYS` 那条）—— 给 AutoTune 用。

    返回 `{层: {"key":..., "value": float|None, "converging": bool|None}}`。
    ★ 缺读数的层**不进**结果（`None` 与「跑了但读数算不出」都表现为缺键）——
      两者对「选层集」的建议是**一样的**：没有证据就不要拿来淘汰（红线）。
    """
    rd = layer_goal_readings(views)
    out = {}
    for L, d in rd.items():
        k = _LG_KEYS.get(L)
        if not k or k not in d:
            continue
        v = d.get(k)
        out[L] = {"key": k, "value": (None if v is None else float(v)),
                  "converging": d.get("converging")}
    return out


def autotune_score(ep: dict) -> dict:
    """把一个 episode 压成**可比较的读数向量**（只报量，不打分）。

    质量口径**三级回落，且必须留痕是哪一级**：
      ① `duty` 有值 ⇒ 用**各层职责度中位**（层在停止/收敛处真替原始问题干了活）；
      ② 无 duty 但有 `tri_rate` ⇒ 用三态一致率；
      ③ 都没有 ⇒ `quality=None`（**未知，绝不当 0** —— 否则「没测」会被
         当成「测出来很差」，把好配置误淘汰）。
    """
    duty = ep.get("duty") or {}
    dv = [_at_num(x) for x in duty.values()]
    dv = [x for x in dv if x is not None]
    q_duty = _at_med(dv)
    tri = _at_num(ep.get("tri_rate"))
    cut = [str(x) for x in (ep.get("cut_layers") or [])]
    # ★ [层目标] 优先用「按层目标定义的读数」—— 它比 duty 更贴用户给的目标语义
    #   （duty 只答「层替问题干了多少活」，goal 答「离该层目标还有多远」）。
    _gr = ep.get("goal_readings") or {}
    gv = []
    for _L, _d in (_gr or {}).items():
        if isinstance(_d, dict):
            _x = _at_num(_d.get("value"))
            if _x is not None:
                gv.append(_x)
    q_goal = _at_med(gv)
    if q_goal is not None:
        quality, basis = q_goal, "goal_med"
    elif q_duty is not None:
        quality, basis = q_duty, "duty_med"
    elif tri is not None:
        quality, basis = tri, "tri_rate"
    else:
        quality, basis = None, "unknown"
    return {
        "quality": quality, "q_basis": basis,
        # ★ 时间戳出口：`autotune_progress` 要按 t 排序判「趋势」。
        "t": _at_num(ep.get("t"), 0.0),
        "cost": _at_num((ep.get("cost") or {}).get("tokens")),
        "cut": cut, "n_cut": len(cut), "natural": len(cut) == 0,
        "route": [str(x) for x in (ep.get("route") or [])],
        "mode": str(ep.get("mode") or ""),
        "rounds_cap": dict(ep.get("rounds_cap") or {}),
        "run_id": str(ep.get("run_id") or ""),
        # ★ 层目标明细随行（供 `autotune_progress` 做「中期动态调整」判据）。
        "goal_readings": {str(k): dict(v) for k, v in (_gr or {}).items()
                          if isinstance(v, dict)},
    }


def autotune_dominates(a: dict, b: dict) -> bool:
    """帕累托支配：质量不劣、成本不高，且至少一项严格更优。

    ★ 任一读数缺失（None）⇒ **不判支配**（未知不能用来淘汰已知）。
    """
    qa, qb = a.get("quality"), b.get("quality")
    ca, cb = a.get("cost"), b.get("cost")
    if qa is None or qb is None or ca is None or cb is None:
        return False
    if qa < qb or ca > cb:
        return False
    return (qa > qb) or (ca < cb)


def autotune_pareto(points: list) -> list:
    """多目标（质量↑ / 成本↓）的**帕累托前沿**：非被支配点的集合。"""
    pts = [p for p in (points or [])
           if p.get("quality") is not None and p.get("cost") is not None]
    front = []
    for i, p in enumerate(pts):
        if not any(j != i and autotune_dominates(o, p)
                   for j, o in enumerate(pts)):
            front.append(p)
    # 前沿内按质量降序、成本升序给个稳定序（可复现）。
    front.sort(key=lambda r: (-r["quality"], r["cost"]))
    return front


def autotune_sh_rounds(n: int, min_res: int = _AT_MIN_RES,
                       factor: int = 3) -> list:
    """Successive-Halving 档位表：`[(保留候选数, 每候选圈预算), …]`。

    ★ 语义：**档 n 的预算 = 档 (n-1) 的 factor 倍**，同时候选数缩到 1/factor。
      总预算 ≈ n×1 + (n/f)×f + … 收敛，符合 Hyperband「预算约束下的粗筛」。
    """
    n = max(1, int(n))
    f = max(2, int(factor))
    mr = max(1, int(min_res))
    out, keep, res = [], n, mr
    while True:
        out.append((keep, res))
        if keep <= 1:
            break
        keep = max(1, keep // f)
        res = res * f
    return out


def autotune_rank(episodes: list, min_n: int = 1) -> list:
    """按（模式, 层集）分组 → 组内帕累托前沿 + 中位读数，按质量降序排。

    这是**暖启动**的入口：新一跑先查这里「同类题上谁历史最优」。

    ★ [分母一致] 质量中位与成本中位**必须在同一批 episode 上算**：
      只取「质量与成本**都齐**」的那些。反例（真跑逮到）：把**无 duty 读数的
      历史跑次**（`duty={}` ⇒ quality=None）也算进成本中位 ⇒ 2 层组的成本中位
      被旧跑次拉到 305076（真值 378837）⇒ 帕累托膝盖**判错**。同一组两个读数
      用两个分母，是典型的「对不上账」。
    """
    groups = {}
    for ep in (episodes or []):
        s = autotune_score(ep)
        groups.setdefault((s["mode"], tuple(s["route"])), []).append(s)
    rows = []
    for (mode, route), arr in groups.items():
        if len(arr) < max(1, int(min_n)):
            continue
        # ★ 只在「质量、成本都齐」的子集上算两个中位（同分母）。
        paired = [a for a in arr if a["quality"] is not None
                  and a["cost"] is not None]
        qs = [a["quality"] for a in paired]
        cs = [a["cost"] for a in paired]
        rows.append({
            "mode": mode, "route": list(route), "n": len(arr),
            "n_paired": len(paired),
            "quality_med": _at_med(qs), "cost_med": _at_med(cs),
            "natural_rate": (sum(1 for a in arr if a["natural"])
                             / float(len(arr))),
            "pareto": autotune_pareto(arr),
        })
    rows.sort(key=lambda r: (
        -(r["quality_med"] if r["quality_med"] is not None else -1.0),
        r["cost_med"] if r["cost_med"] is not None else float("inf")))
    return rows


def autotune_recommend(episodes: list, space_layers=None,
                       quality_tau: float = 0.05,
                       playbook: list = None,
                       min_n: int = 1) -> dict:
    """从跨跑 episode 推出**建议默认**：模式 / 层集 / 各层圈数上限。

    规则（可判据、可复现）：
      ① **层集**：在「质量不低于最优 − τ」的候选里，取**成本最低**那条
         （帕累托膝盖）—— 这正是「该去的层去掉、该留的留」的量化判据。
      ② **圈数**：以「该层**未**被截断」的 episode 的 `rounds_cap` 中位为基线；
         对被截断过的层 **+1**（对齐 EML `schedule` 条目的动作）。
      ③ **模式**：取最优质量行的 mode（并列时取成本低者）。
      ★ 样本不足（无任何带质量的组）⇒ 返回 `ok=False` + 原因，**绝不瞎猜**。
    """
    eps = list(episodes or [])
    #   ★ `min_n` 必须**真的接进来**：否则 `autotune.min_n` 是只写不读的死键
    #     （「参数没有出口」）。同(模式,层集)样本不足 ⇒ 该组不参与推荐。
    rows = [r for r in autotune_rank(eps, min_n=int(min_n))
            if r.get("quality_med") is not None]
    if not rows:
        return {"ok": False, "why": "无带质量读数的 episode（duty/tri_rate 都缺）",
                "n_episodes": len(eps)}
    best_q = rows[0]["quality_med"]
    # ① 层集：质量在 [best_q - τ, ∞) 内选成本最低
    _within = [r for r in rows
               if r["quality_med"] >= best_q - float(quality_tau)]
    costed = [r for r in _within if r.get("cost_med") is not None]
    pick = (min(costed, key=lambda r: r["cost_med"]) if costed else rows[0])
    # ② 圈数：分层统计「未截断中位」+ 截断 +1
    base, cut_n, all_n = {}, {}, {}
    for ep in eps:
        s = autotune_score(ep)
        for L, cap in (s["rounds_cap"] or {}).items():
            L = str(L)
            all_n.setdefault(L, []).append(_at_num(cap))
            if L in s["cut"]:
                cut_n[L] = cut_n.get(L, 0) + 1
            else:
                base.setdefault(L, []).append(_at_num(cap))
    rounds_cap = {}
    for L in _AT_LAYERS:
        b = _at_med([x for x in base.get(L, []) if x is not None])
        if b is None:
            b = _at_med([x for x in all_n.get(L, []) if x is not None])
        if b is None:
            continue
        cap = int(round(b)) + (1 if cut_n.get(L, 0) > 0 else 0)
        rounds_cap[L] = max(1, cap)
    why = ("层集=%s（最优质量 %.3f，τ=%.3f；同质量内取成本最低 %.0f tok）；"
           "模式=%s；圈数=%s（截断层 +1：%s）"
           % (pick["route"], best_q, float(quality_tau),
              pick["cost_med"] or 0.0, pick["mode"], rounds_cap,
              sorted(cut_n) or "无"))
    if playbook:
        _warm = [e for e in playbook if e.get("status") == "active"]
        if _warm:
            why += "；暖启动生效条目 %d 条" % len(_warm)
    # ★ [证据强度] 别拿 n=1 的组当结论：同分母样本 < 3 ⇒ 显式标注证据薄弱，
    #   让下游（人 / 上层）自行决定要不要采信，而不是把薄证据包装成「最优」。
    _np = int(pick.get("n_paired") or pick.get("n") or 0)
    strength = "充分" if _np >= 3 else ("薄弱" if _np >= 1 else "无")
    if _np < 3:
        why += "；⚠ 证据%s（同分母样本 n=%d < 3，建议多跑几次再采信）" % (strength, _np)
    return {"ok": True, "mode": pick["mode"], "route": pick["route"],
            "rounds_cap": rounds_cap, "quality_med": best_q,
            "cost_med": pick["cost_med"], "n_episodes": len(eps),
            "n_groups": len(rows), "evidence_n": _np,
            "evidence_strength": strength, "why": why,
            "frontier": [{"mode": r["mode"], "route": r["route"],
                          "n": r["n"], "n_paired": r["n_paired"],
                          "quality_med": r["quality_med"],
                          "cost_med": r["cost_med"]} for r in rows[:6]]}


def autotune_progress(episodes: list, min_n: int = 2) -> dict:
    """[中期动态调整] 判「同一 (模式,层集) 的目标读数**随轮次是否在改善**」。

    依据 **CSD / 早期预警（Scheffer et al. 2009）** 与 **Successive Halving**：
      同一配置连跑多次，若目标读数**单调不降且末端仍升** ⇒ 继续（预算给得起）；
      若**已平/在退** ⇒ 收敛（停手，把预算抽回）；若**在退** ⇒ 建议回滚到最佳轮。

    返回 `{key: {trend, first, last, best_ep_idx, advice}}`，`advice ∈
    {"继续","收敛","回滚"}`。★ 每个 key 至少要 `min_n` 个**带目标读数**的
    episode 才判；不足 ⇒ 不出现该 key（**绝不瞎猜**）。
    ★ 与 `autotune_rank` **各自独立**：那个答「选哪套配置」，这个答「这套还要不要跑」。
    """
    need = max(2, int(min_n))
    groups = {}
    for ep in (episodes or []):
        s = autotune_score(ep)
        key = (s["mode"], tuple(s["route"]))
        _g = s.get("goal_readings") or {}
        # 主读数：取该跑里**数值最多**的那条目标读数之和的中位（同分母）。
        _vals = []
        for _L, _d in _g.items():
            k = _LG_KEYS.get(_L)
            if not k:
                continue
            _x = _at_num((_d or {}).get(k)) if k in (_d or {}) else None
            if _x is None and "value" in (_d or {}):
                _x = _at_num(_d.get("value"))
            if _x is not None:
                _vals.append(_x)
        if not _vals:
            continue
        groups.setdefault(key, []).append((float(s["t"]), _at_med(_vals), s))
    out = {}
    for key, arr in groups.items():
        if len(arr) < need:
            continue
        arr = sorted(arr, key=lambda x: x[0])           # 按时间排
        ys = [a[1] for a in arr]
        _f, _l = ys[0], ys[-1]
        _best = max(range(len(ys)), key=lambda i: ys[i])
        if _l > _f + 1e-9:
            advice, trend = "继续", "上升"
        elif _l < _f - 1e-9:
            advice, trend = "回滚", "下降"
        else:
            advice, trend = "收敛", "平稳"
        out["%s|%s" % (key[0], ",".join(key[1]))] = {
            "trend": trend, "first": round(_f, 4), "last": round(_l, 4),
            "best_ep_idx": int(_best), "n": len(arr), "advice": advice}
    return out


#: [DGM archive] 开放探索的**最低选择概率**：连劣配也保留一点概率。
#:   ★ 依据 DGM 消融（Zhang et al. 2025）：贪心只从最优分支 = 39.7%，
#:     带 archive = 50.0% —— **不许把劣配的路径彻底掐死**。
_AT_ARCHIVE_FLOOR = 0.05
#: [DGM archive] 归档条目的**多样性下限**：archive 里至少要有这么多种
#:   不同的 (mode, route) 组合，否则「开放探索」名存实亡（退化成单点贪心）。
_AT_ARCHIVE_MIN_DIV = 2


def autotune_archive(episodes: list) -> dict:
    """[DGM archive] 从历史 episode 建**开放探索档案**（不是只留最优）。

    依据 Darwin Gödel Machine：archive 的价值在**越过适应度低谷** ——
    最优解常常经由「比父代更差」的中间体才走到。故本函数**保留全部**
    (mode, route) 组合，只给它们算**选择概率**：

      p(c) ∝ 质量秩 × 1/(1+已探索次数)     （质量高、探索少 ⇒ 概率高）
      再夹到 `[_AT_ARCHIVE_FLOOR, 1]` 并归一化 ⇒ **每个候选非零概率**。

    ★ 「只留最优」是贪心，DGM 已证劣于带 archive 的开放探索 ⇒ 本函数
      的存在本身就是判据（M35 变异体：改成只留最优必须判红）。
    """
    rows = autotune_rank(episodes or [], min_n=1)
    if not rows:
        return {"ok": False, "why": "无任何带质量的组", "arms": [], "n": 0}
    arms = []
    for r in rows:
        key = "%s|%s" % (r["mode"], ",".join(r["route"]))
        _q = r.get("quality_med")
        _c = r.get("cost_med")
        arms.append({"key": key, "mode": r["mode"], "route": list(r["route"]),
                     "n": int(r.get("n") or 0),
                     "quality_med": _q, "cost_med": _c,
                     "explored": int(r.get("n") or 0)})
    # 质量秩（降序；质量 None 排最后但**不剔除**）。
    arms.sort(key=lambda a: -(a["quality_med"]
                              if a["quality_med"] is not None else -1.0))
    _m = len(arms)
    raw = []
    for i, a in enumerate(arms):
        _rank = float(_m - i) / float(_m)             # 1.0 最优 → 1/m 最劣
        _nov = 1.0 / (1.0 + a["explored"])            # 探索少 ⇒ 高
        raw.append(max(_AT_ARCHIVE_FLOOR, _rank * _nov))
    _s = sum(raw) or 1.0
    for a, w in zip(arms, raw):
        a["prob"] = round(w / _s, 4)
    _div = len({a["key"] for a in arms})
    return {"ok": True, "arms": arms, "n": len(arms), "diversity": _div,
            "open_ended": bool(_div >= _AT_ARCHIVE_MIN_DIV),
            "why": "archive %d 臂 / 多样性 %d（floor=%.2f）"
                   % (len(arms), _div, _AT_ARCHIVE_FLOOR)}


def autotune_phase_select(episodes: list, q_features: dict = None,
                          quality_tau: float = 0.05,
                          min_n: int = 1) -> dict:
    """**前期配置选择**：给定题面特征 ⇒ 建议 (mode, 层集)。

    做法（两层，都可判据）：
      ① 若有**同题型**的历史组（`q_features` 命中）⇒ 用它出建议
         （冷启动 → 暖启动迁移）。
      ② 无同题型历史 ⇒ 退回全体历史（并**显式标注** `basis="global"`，
         不把「别的题型的结论」冒充成「这题的结论」）。
      ★ 依据 Successive Halving：前期用**最少预算**粗筛 —— 故本段只出
        「要跑哪些臂」，不出「跑多少圈」（圈数归中期动态调整）。
    """
    eps = list(episodes or [])
    basis = "global"
    pool = eps
    if q_features:
        _key = tuple(sorted((str(k), str(v)) for k, v in q_features.items()))
        same = [e for e in eps
                if tuple(sorted((str(k), str(v))
                                for k, v in (e.get("q_features") or {}).items()))
                == _key]
        if len(same) >= max(1, int(min_n)):
            pool, basis = same, "same_type"
    rec = autotune_recommend(pool, quality_tau=float(quality_tau),
                             min_n=int(min_n))
    rec["basis"] = basis
    rec["phase"] = "select"
    if rec.get("ok"):
        rec["decision"] = {"mode": rec.get("mode"),
                           "route": rec.get("route")}
    return rec


def autotune_phase_adjust(episodes: list, min_n: int = 2) -> dict:
    """**中期动态调整**：跑动中按目标读数趋势 ⇒ 继续 / 收敛 / 回滚。

    依据：**anytime-valid**（Howard et al. 2021）—— 随时看随时停都成立；
      **CSD / 早期预警**（Scheffer et al. 2009）—— 趋势变平/退就是信号。
    ★ 只对「同一 (mode,route) 至少 min_n 次带目标读数」的组表态；
      不足 ⇒ **不表态**（返回空 arms，绝不瞎猜）。
    """
    prog = autotune_progress(episodes or [], min_n=int(min_n))
    arms = []
    for key, d in prog.items():
        arms.append(dict(d, key=key))
    # 建议优先级：先处理「回滚」（最紧急），再「收敛」，最后「继续」。
    _order = {"回滚": 0, "收敛": 1, "继续": 2}
    arms.sort(key=lambda a: _order.get(a.get("advice"), 9))
    return {"phase": "adjust", "n_arms": len(arms), "arms": arms,
            "ok": bool(arms),
            "why": ("%d 组有趋势读数" % len(arms)) if arms
                   else "无组达到 min_n=%d（不表态）" % int(min_n)}


def autotune_phase_learn(episodes: list, min_n: int = 2) -> dict:
    """**后期学习纠正 + 输出结论**：archive 汇总 ⇒ 纠正 + 可读结论。

    依据 DGM 的**开放探索**：结论**不许只报冠军** —— 必须同时报
      (a) archive 多样性、(b) 被淘汰臂的**差在哪**（可解释的纠正）、
      (c) 每个建议的**证据强度**（`n<3` ⇒ 标注薄弱）。

    输出 `corrections`（每条 = 一个臂 + 一条「纠正理由」）与 `conclusion`
    （人可读的一句话结论）。★ 无证据 ⇒ `ok=False` + why，**不编结论**。
    """
    arc = autotune_archive(episodes or [])
    if not arc.get("ok"):
        return {"phase": "learn", "ok": False, "why": arc.get("why"),
                "corrections": [], "conclusion": ""}
    arms = arc["arms"]
    corrections = []
    if arms:
        _top = arms[0]
        for a in arms[1:]:
            _why = []
            if (a.get("quality_med") is not None
                    and _top.get("quality_med") is not None
                    and a["quality_med"] < _top["quality_med"] - 1e-9):
                _why.append("质量 %.3f < 最优 %.3f"
                            % (a["quality_med"], _top["quality_med"]))
            if (a.get("cost_med") is not None
                    and _top.get("cost_med") is not None
                    and a["cost_med"] > _top["cost_med"]):
                _why.append("成本 %.0f > 最优 %.0f"
                            % (a["cost_med"], _top["cost_med"]))
            corrections.append({
                "key": a["key"], "advice": "降权但不剔除（DGM 开放探索）",
                "reasons": _why or ["质量不劣但成本/探索次数待定"],
                "prob": a.get("prob")})
    _n_top = int(arms[0].get("n") or 0) if arms else 0
    _strength = "充分" if _n_top >= 3 else ("薄弱" if _n_top >= 1 else "无")
    conclusion = ("最优臂=%s（质量 %.3f / 成本 %.0f，n=%d，证据%s）；"
                  "archive 多样性=%d（开放探索=%s）"
                  % (arms[0]["key"], arms[0].get("quality_med") or 0.0,
                     arms[0].get("cost_med") or 0.0, _n_top, _strength,
                     arc["diversity"], "开" if arc["open_ended"] else "关")
                  ) if arms else "无臂可结论"
    return {"phase": "learn", "ok": True, "corrections": corrections,
            "conclusion": conclusion, "evidence_strength": _strength,
            "archive_diversity": arc["diversity"],
            "open_ended": arc["open_ended"], "n_arms": len(arms)}


def autotune_decide(episodes: list, q_features: dict = None,
                    quality_tau: float = 0.05, min_n: int = 2) -> dict:
    """**AutoTune 三阶段自主决策总入口** —— 前期选择 / 中期调整 / 后期学习。

    三段各自独立产出决策，最后合成一份**带留痕**的决策书：
      `{select:…, adjust:…, learn:…, summary:…}`。
    ★ 三段**都不改配置**：`select` 只建议、`adjust` 只表态、`learn` 只纠正。
      要采纳必须显式 `autotune_apply_to_cfg`（红线「建议与执行分开」）。
    """
    eps = list(episodes or [])
    sel = autotune_phase_select(eps, q_features=q_features,
                                quality_tau=quality_tau, min_n=1)
    adj = autotune_phase_adjust(eps, min_n=int(min_n))
    lrn = autotune_phase_learn(eps, min_n=int(min_n))
    _bits = []
    if sel.get("ok"):
        _bits.append("前期选 %s/%s（%s）"
                     % (sel.get("mode"), sel.get("route"), sel.get("basis")))
    else:
        _bits.append("前期选择：%s" % (sel.get("why") or "无建议"))
    _bits.append("中期调整：%d 组表态（%s）"
                 % (adj["n_arms"],
                    "；".join(a["key"] + "→" + a["advice"]
                              for a in adj["arms"][:3]) or "无"))
    if lrn.get("ok"):
        _bits.append("后期结论：%s" % lrn["conclusion"])
    else:
        _bits.append("后期学习：%s" % (lrn.get("why") or "无结论"))
    return {"select": sel, "adjust": adj, "learn": lrn,
            "summary": " | ".join(_bits), "n_episodes": len(eps)}


def autotune_load_episodes(base=None, dirpath=None) -> list:
    """读记忆库历史 episode（`episodes.jsonl`）。坏行由 `eml_read_jsonl` 跳过。"""
    try:
        d = Path(dirpath) if dirpath else eml_dir(base)
        return list(eml_read_jsonl(d / _EML_EPISODES) or [])
    except Exception:
        return []


def autotune_run(cfg: dict, base=None, write: bool = True) -> dict:
    """跑一次自调优：读 episode → 出建议 →（可选）落盘 `dgtf_autotune.json`。

    ★ 只写**建议文件**，不改 `cfg`、不改 yaml —— 「建议与执行分开」：
      要采用建议必须**显式**调 `autotune_apply_to_cfg` 或手改 yaml。
    """
    at = (cfg or {}).get("autotune") or {}
    eps = autotune_load_episodes(base)
    try:
        _pb = list(eml_read_jsonl(eml_dir(base) / _EML_PLAYBOOK) or [])
    except Exception:
        _pb = []
    try:
        rec = autotune_recommend(eps,
                                 quality_tau=float(at.get("quality_tau", 0.05)),
                                 playbook=_pb,
                                 min_n=int(at.get("min_n", 1) or 1))
    except Exception as e:
        rec = {"ok": False, "why": "autotune_recommend 异常：%r" % (e,)}
    rec["n_read"] = len(eps)
    # ★ [三阶段决策书] 前期选择 / 中期调整 / 后期学习 —— 一次跑全出，
    #   随建议一起落盘（「结论」必须留痕，否则只算内部状态）。
    #   ★ 段间**互不覆盖**：`rec` 仍是 `autotune_recommend` 的原样输出
    #     （下游 `autotune_apply_to_cfg` 读的就是它），三段挂在新键上。
    try:
        rec["decide"] = autotune_decide(
            eps, quality_tau=float(at.get("quality_tau", 0.05)),
            min_n=int(at.get("min_n", 2) or 2))
    except Exception as e:
        rec["decide"] = {"error": "%r" % (e,)}
    if write and rec.get("ok"):
        try:
            out = str(at.get("out") or "").strip()
            p = (Path(out) if out
                 else (eml_dir(base).parent / "dgtf_autotune.json"))
            p.write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                         encoding="utf-8", newline="\n")
            rec["written"] = str(p)
        except Exception as e:
            rec["written"] = "失败：%r" % (e,)
    return rec


# ============================================================
# 层职责守卫（Layer Duty Guard）—— 在**停止/收敛处**回答一句：
#   「这一层到底替原始问题干了什么」。零新增 LLM 调用（全规则）。
#
# 依据（2025）：
#   · LiveRAG / SIGIR 2025：Coverage 按权重加权 + Relatedness 惩罚无用断言
#     + 取两者**调和平均**（一项好一项差不给高分）。本处用规则判定替代
#     其 NLI 判定，把开销压到 0。
#   · NAACL 2025 sub-question coverage：子问题分 core/background/follow-up
#     分类别计覆盖；**未覆盖的 core 问项点名并喂回生成器**（实测胜率 74%）。
#   · EMNLP 2025 自纠收敛：每轮只削掉剩余误差的固定比例 ⇒ 边际增益递减
#     即「推不动了」。工程判据 = 连续 patience 次 Δ < τ 就停。
#
# ★ 红线自检：职责度是**读数不是分数** —— 不进 `_quality_verdict`，
#   不参与「谁优谁劣」。它只做两件事：① 不许把截断说成自然停止
#   （署名纪律）；② 让层能**因为推不动而停**（新停止判据）。
# ============================================================

#: [LDG] 问项类别权重（core / background / follow-up）。
#   ★ 与 NAACL'25 的分类一致：附加目标（「甚至…」）**不占核心权重**，
#     否则一句并列就把「主问没答」洗成高覆盖。
_DUTY_KIND_W = {"core": 0.70, "background": 0.30, "followup": 0.10}
_DUTY_FLOOR = 0.35          # 职责度下限：低于 ⇒ 不许署名自然停止 + 补一圈
_DUTY_TAU = 0.02            # 边际职责增益阈值（ΔS < τ 记一次「推不动」）
_DUTY_PATIENCE = 2          # 连续 N 圈推不动 ⇒ 记「职责增益收敛」停止理由
_DUTY_REMEDY_ROUNDS = 1     # 职责未尽的定向补救圈上限
_DUTY_DELIVERY_FLOOR = 0.10  # 交付面占全文比重告警线
_DUTY_HIT_SIM = 0.55        # 问项命中判据：词面包含 或 sim3 ≥ 此值

#: [LDG] 问项类别判据用的**附加目标引导词**（「甚至/乃至/以及」后的项
#:   是附加目标，不占核心权重）。
_DUTY_FOLLOWUP_LEAD = ("甚至", "乃至", "更甚至", "以至于", "以至")
#: [LDG] 主问引导词 —— 出现这些的项按 core 计。
_DUTY_CORE_LEAD = ("如何", "怎么", "怎样", "哪些", "为什么", "是否",
                   "能不能", "可不可以", "什么时候", "多少")
#: [LDG] 各层 objective 关键词（判 Relatedness 的 Useful 档）。
_DUTY_OBJ_WORDS = {
    "0": ("显形", "结构", "候选", "线头", "悬置", "属性", "位置", "&"),
    "1": ("回答", "证据", "可判定", "子问题", "锚点", "数据", "结论"),
    "both": ("第三者", "张力", "两端", "对撞", "反转", "裁决"),
    "all": ("清算", "闭环", "整体", "不可通约", "交代", "元"),
}


def question_aspects(question: str):
    """问项抽取（规则、零成本）：把问题切成带类别与权重的问项。

    ★ 为什么不用一次 LLM 调用抽：抽取是**每层每次评估都要跑**的读数，
      一次调用会把「守卫」变成新的开销源；而它要的是**稳定可比**，
      不是「抽得漂亮」。规则判据还能被变异体钉住（LLM 抽的钉不住）。
    ★ 分类规则（对应 NAACL'25 的三类）：
      · 带「甚至/乃至/以及」引导 ⇒ followup（附加目标，权重最低）；
      · 含主问引导词（如何/哪些/为什么…）⇒ core；
      · 长 ≥ 4 字的实体性短语 ⇒ core；短碎片 ⇒ background。
    """
    q = str(question or "").strip()
    if not q:
        return []
    # 切分：标点 + 并列连接词（先把连接词换成标点，再切）
    _sep = q
    for _w in ("甚至", "乃至", "以及", "并且", "同时", "还有", "及"):
        _sep = _sep.replace(_w, "，" + _w)
    _sep = _sep.replace("？", "，").replace("?", "，").replace("。", "，")
    for _w in ("；", ";", "、", "，", ",", "：", ":"):
        _sep = _sep.replace(_w, "\n")
    raw = [x.strip() for x in _sep.split("\n") if x.strip()]
    # 去掉纯引导词碎片
    _drop = {"如何", "怎么", "怎样", "为什么", "是否", "以及", "甚至", "乃至"}
    out = []
    for x in raw:
        if x in _drop or len(x) < 2:
            continue
        kind = "core"
        if any(x.startswith(w) or (w + x) in q for w in _DUTY_FOLLOWUP_LEAD):
            kind = "followup"
        elif any(w in x for w in _DUTY_CORE_LEAD):
            kind = "core"
        elif len(x) < 4:
            kind = "background"
        out.append({"text": x[:40], "kind": kind,
                    "weight": float(_DUTY_KIND_W.get(kind, 0.3))})
    # 去重（同文本保首个类别）
    seen, ded = set(), []
    for a in out:
        if a["text"] in seen:
            continue
        seen.add(a["text"])
        ded.append(a)
    return ded


def duty_components(aspects, deliver_text, objective_words=(),
                    corpus=None, hit_sim: float = _DUTY_HIT_SIM) -> dict:
    """算 (C 覆盖, R 相关, S 调和平均) 与点名缺失的 core 问项。

    ★ C（Coverage）：按类别权重加权 —— 与 LiveRAG 的 Direct/Useful 加权同构，
      这里的三档是 core/background/followup。
    ★ R（Relatedness）：`|Direct| / (|Direct| + |Useless|)` —— **专门惩罚
      无用断言**（本跑 86.5% 的正文是内部面，正是 Useless 的来源）。
      判定：断言命中任一问项 ⇒ Direct；命中该层 objective 词 ⇒ Useful；
      都不命中 ⇒ Useless。
    ★ S = 2CR/(C+R)（调和平均）：C 与 R 有一项塌了就整体塌 —— 这是刻意的，
      「覆盖高但全是废话」与「言之有物但没答问题」都不该拿高分。
    """
    _d = str(deliver_text or "").strip()
    _aw = [w for w in (objective_words or []) if w]
    _as = list(aspects or [])

    def _grams(t):
        """问项核心 gram：去引导词后取 2 字滑窗（中文词面命中的最小单位）。"""
        _t = str(t or "")
        for _w in _DUTY_CORE_LEAD:
            if _t.startswith(_w):
                _t = _t[len(_w):]
                break
        for _w in _DUTY_FOLLOWUP_LEAD:
            if _t.startswith(_w):
                _t = _t[len(_w):]
                break
        _t = _t.strip("的了吗呢吧")
        if len(_t) <= 2:
            return [_t] if _t else []
        return [_t[_i:_i + 2] for _i in range(len(_t) - 1)]

    def _hit(asp_text, seg):
        """命中判据：gram 命中率 ≥ 0.5（或 sim3 兜底）。

        ★ 旧口径要求「问项首 2 字 + 整段子串」，实测**相关文本也判 0**
          （探针 T2 全红）—— 判据读错了东西。改用 gram 重叠：
          问项是长短语、交付面是自然句，词面必然只有部分重合。
        """
        if str(asp_text) in seg:
            return True
        _g = _grams(asp_text)
        if not _g:
            return False
        _n_hit = sum(1 for x in _g if x and x in seg)
        if _n_hit / float(len(_g)) >= 0.5:
            return True
        # sim3 兜底（换说法命中）；短文本噪声大 ⇒ 只在够长时用
        if len(str(asp_text)) >= 6 and len(seg) >= 12:
            try:
                return float(_sim3(str(asp_text), seg,
                                   corpus=corpus)) >= hit_sim
            except Exception:
                return False
        return False

    # ── C ──
    _tw = sum(float(a.get("weight", 0.3)) for a in _as) or 0.0
    _hw, missing = 0.0, []
    for a in _as:
        t = str(a.get("text", ""))
        if t and _hit(t, _d):
            _hw += float(a.get("weight", 0.3))
        elif str(a.get("kind", "core")) == "core":
            missing.append(t)
    C = (_hw / _tw) if _tw else 0.0

    # ── R ──
    segs = [x.strip() for x in
            re.split(r"[。！？\n]+|(?<=[；;])\s*", _d) if len(x.strip()) >= 6]
    direct = useful = useless = 0
    for sg in segs:
        # ★ 与 C 同口径（都走 `_hit`）：两处口径分叉会让「覆盖高、相关低」
        #   变成算法噪声而不是事实。
        if any(_hit(str(a.get("text", "")), sg) for a in _as):
            direct += 1
        elif any(w in sg for w in _aw):
            useful += 1
        else:
            useless += 1
    R = (direct / (direct + useless)) if (direct + useless) else 0.0

    # ── S ──
    S = (2.0 * C * R / (C + R)) if (C + R) > 0 else 0.0
    return {"C": round(C, 4), "R": round(R, 4), "S": round(S, 4),
            "missing_core": missing[:6],
            "n_asp": len(_as), "n_seg": len(segs),
            "seg_direct": direct, "seg_useful": useful, "seg_useless": useless}


def duty_of_layer(entry, question, deliver_text, objective_words=(),
                  corpus=None, floor=None) -> dict:
    """一层在**停止/收敛处**的职责读数（薄壳：抽问项 + 算三读数 + 定门）。"""
    asp = question_aspects(question)
    d = duty_components(asp, deliver_text, objective_words, corpus=corpus)
    d["entry"] = str(entry)
    d["core_total"] = len([a for a in asp if a.get("kind") == "core"])
    _fl = float(_DUTY_FLOOR if floor is None else floor)
    d["short"] = bool(float(d.get("S", 0.0)) < _fl)
    d["floor"] = _fl
    return d


def duty_short_line(d: dict) -> str:
    """职责读数的**一行文案**（产物头部与层尾共用，避免两处措辞分叉）。"""
    if not isinstance(d, dict) or not d:
        return "职责 —（未测）"
    _m = d.get("missing_core") or []
    _tail = ("；缺核心 %d 项：%s" % (len(_m), "、".join(_m[:3]))
             if _m else "")
    return ("职责 S=%.2f（覆盖 C=%.2f · 相关 R=%.2f；核心 %d/%d）%s"
            % (float(d.get("S", 0.0)), float(d.get("C", 0.0)),
               float(d.get("R", 0.0)),
               int(d.get("core_total", 0) or 0) - len(_m),
               int(d.get("core_total", 0) or 0), _tail))


def sem_thr_relative(texts, corpus=None, lo=_SEM_REL_LO, hi=_SEM_REL_HI,
                     q=_SEM_REL_Q, top_n=None):
    """D1 相对分位阈值：在**本批文本自己**的两两 sim3 分布上定标。

    ★ 为什么不用绝对 0.30（v1.23.28 遗留 #1）：`_sim3` 在中文上走**字符
      二元组**，覆盖密度随文本长度变化 —— 长句重述 0.41~0.79、短句可能
      整体下降。绝对阈值会在长度分布漂移后**要么恒聚、要么恒不聚**，
      而且两个方向都不报错（本项目「只升不降的指标是自欺」的变体）。
    ★ 口径：取全部两两 sim3 的 **p60**（`q=0.60`）再夹取到 [lo, hi]。
      为什么 p60 而不是中位 p50：聚类的目的是「把明显的同义对聚起来」，
      取中位会把一半随机对也收进簇 ⇒ 高估稳定（本项目的保守方向是
      **高估发散**）。p60 偏严一档，落在「同义对（高分位）之下、
      随机对（低分位）之上」的空隙里。
    ★ `lo=0.20` / `hi=0.55`：防止退化 —— 文本全同时 p60 = 1.0（会被 hi
      夹回）、文本全异时 p60 = 0.0（会被 lo 抬回）。夹取后仍返回**一个
      可解释的数**，不是「随便一个魔法数」。
    ★ n < 2 或两两全同分 ⇒ 退回绝对默认（没有分布可定标）。
    """
    _t = [str(x).strip() for x in (texts or []) if str(x).strip()]
    n = len(_t)
    if n < 2:
        return float(_SEM_CLUSTER_THR)
    _sims = []
    for _i in range(n):
        for _j in range(_i + 1, n):
            try:
                _s = _sim3(_t[_i], _t[_j], corpus=corpus) if top_n is None \
                    else _sim3(_t[_i], _t[_j], corpus=corpus, top_n=top_n)
            except TypeError:
                _s = _sim3(_t[_i], _t[_j], corpus=corpus)
            _sims.append(float(_s))
    if not _sims:
        return float(_SEM_CLUSTER_THR)
    _sims.sort()
    _pos = min(max(q, 0.0), 1.0) * (len(_sims) - 1)
    _lo_i = int(_pos)
    _hi_i = min(_lo_i + 1, len(_sims) - 1)
    _frac = _pos - _lo_i
    _p = _sims[_lo_i] * (1 - _frac) + _sims[_hi_i] * _frac
    return float(min(max(_p, float(lo)), float(hi)))


def semantic_entropy_of(texts, corpus=None, thr=None, top_n=None):
    """D3 语义熵：对**同一主张的多次独立出现**做 sim3 聚类，返回三元组。

    返回 `(h_norm, h_raw, clusters)`：
      · `h_norm` 归一化熵 ∈ [0,1]（除以 ln(n)）；**n < 2 时返回 None**
      · `h_raw`  原始熵 -Σ p·ln p（自然对数）
      · `clusters` 每簇成员下标（按首次出现顺序）

    ★ 为什么 n < 2 返回 None 而不是 0.0：单样本谈「发散」是无意义的，
      而 0.0 会被下游读成「很稳定」—— 那是**自欺**（本项目老坑：
      「检测缺省」要在补默认值之前判）。

    ★ 为什么聚类用「与簇代表的最大相似度」而不是两两平均：平均会被
      链式传递（A~B、B~C 但 A≁C）拉成大簇，把发散读成一致。
      用**单链到代表**（第一次进簇的那条）⇒ 同义反复的文本稳定聚在一起，
      真正发散的进不去。这是**保守**选择：宁可高估发散，不高估稳定
      （高估发散只是不判 stable，不改变任何主张的优劣）。
    ★ `thr` 默认 `_SEM_CLUSTER_THR`（0.30）：**不是** `sim.cluster`
      （0.70）—— 后者是 E2 探针批选的口径。用 0.70 会让「换个说法」
      永远聚不起来 ⇒ 熵恒 None（实测）。详见模块常量处注释。

    ★ corpus 透传给 `_sim3`：语料 < 4 篇时 `_sim3` 自动降级到字面层，
      同一批调用共享同一降级路径 ⇒ 簇间可比。
    """
    _t = [str(x).strip() for x in (texts or []) if str(x).strip()]
    n = len(_t)
    if n < 2:
        return None, 0.0, ([list(range(n))] if n else [])
    # ★ D1：`thr == "rel"` ⇒ 在本批文本自己的 sim3 分布上定标（不再用
    #   魔法数）。其余取值（含 None）走绝对口径 —— 默认零行为差。
    if isinstance(thr, str) and thr.strip().lower() == "rel":
        _thr = sem_thr_relative(_t, corpus=corpus,
                                top_n=top_n if top_n is not None else None)
    else:
        _thr = float(_SEM_CLUSTER_THR if thr is None else thr)
    _kw = {}
    clusters: list = []
    for _i, _s in enumerate(_t):
        _placed = False
        for _c in clusters:
            _rep = _t[_c[0]]
            try:
                _sim = _sim3(_s, _rep, corpus=corpus) if top_n is None \
                    else _sim3(_s, _rep, corpus=corpus, top_n=top_n)
            except TypeError:
                _sim = _sim3(_s, _rep, corpus=corpus)
            if float(_sim) >= _thr:
                _c.append(_i)
                _placed = True
                break
        if not _placed:
            clusters.append([_i])
    _kw = None
    import math as _math
    h = 0.0
    for _c in clusters:
        _p = len(_c) / n
        if _p > 0:
            h -= _p * _math.log(_p)
    _hmax = _math.log(n)
    _hn = (h / _hmax) if _hmax > 0 else None
    return _hn, round(h, 6), clusters


def make_aspect_unit(desc, source="anchor", polarity="阴",
                     ground="anchor", ref="", unit_id=""):
    """构造一个 AspectUnit（dict）—— **全工程唯一构造点**。

    ★ 双写：返回的 dict 同时带 `desc`（旧键）与 `text`（新键），两者恒等。
      这样 `_target_text` / `shape_of` / `_quality_check` 等既有读取点
      （都取 `.get("desc")`）**一个字都不用改**。
    ★ `ground` 不在 `_ASPECT_GROUNDS` 里时**归一化到 "anchor"**（不抛错）：
      这是留痕场景，不该因为一个枚举越界就丢掉整条方面。
    ★ id 为空时**不自动编号**（编号由 View 侧按追加顺序给，才稳定）。
    """
    s = str(desc).strip()
    if not s:
        return {}
    g = str(ground).strip()
    if g not in _ASPECT_GROUNDS:
        g = "anchor"
    p = str(polarity).strip()
    if p not in _ASPECT_POLARITIES:
        p = "阴"
    return {
        "id": str(unit_id or ""),
        "desc": s,          # ← 旧键，读取点全部依赖它
        "text": s,          # ← 新键，与 desc 恒等
        "polarity": p,
        "ground": g,
        "ref": str(ref or ""),
        "source": str(source or g),
    }

SUSPENSION_REASON_TYPES = ("explicit", "intuitive")


def _same_batch(a: List[str], b: List[str], thr: float) -> bool:
    if not a or not b:
        return False
    m = sum(1 for t in a if any(_similar(t, u, _DUP_SIM) for u in b))
    return m / max(len(a), len(b)) >= thr


def drop_rehashes(items: List[dict], existing: List[dict],
                  cfg: dict) -> Tuple[List[dict], List[dict]]:
    """入池前挡「翻回老地方」。"""
    thr = float(cfg.get("rehash_similarity", 0.6))
    if thr <= 0:
        return list(items), []
    seen = [str(x.get("desc", "")) for x in existing]
    kept: List[dict] = []
    dropped: List[dict] = []
    for it in items:
        d = str(it.get("desc", "")).strip()
        if not d:
            continue
        hit = next((x for x in seen if _similar(d, x, thr)), "")
        if hit:
            dropped.append({"desc": d, "same_as": hit})
        else:
            kept.append(it)
            seen.append(d)
    return kept, dropped


def _normalize_punct(s) -> str:
    """把常见全角标点归一为半角。"""
    if not s:
        return s
    return (str(s)
            .replace("：", ":")
            .replace("，", ",")
            .replace("；", ";")
            .replace("　", " ")
            .replace("｜", "|"))


_ACTION_ALIASES = {
    "self_check": "self_check",
}


def _action_on(config: dict, name: str, default: bool = True) -> bool:
    """统一读动作开关。actions 段 > output 段（经别名映射）> 默认值。"""
    a = (config.get("actions") or {})
    if name in a:
        return bool(a[name])
    o = (config.get("output") or {})
    alias = _ACTION_ALIASES.get(name, name)
    if alias in o:
        return bool(o[alias])
    return default


def _spiral_for(config: dict, entry: str) -> dict:
    """某一层的有效 spiral 配置。"""
    sp = dict(config.get("spiral") or {})
    over = (sp.get("per_entry") or {}).get(entry) or {}
    sp.update(over)
    sp.pop("per_entry", None)
    return sp


def _turn_stable(items: List[dict], layer: int, cfg: dict) -> int:
    need = int(cfg.get("stable_layers", 3))
    thr = float(cfg.get("batch_similarity", 0.6))
    span = list(range(layer - need + 1, layer + 1))
    if span[0] < 1:
        return 0

    def batch_of(l: int) -> List[str]:
        return [x.get("target", "") for x in items
                if l in (x.get("confirmed_layers") or [])]

    cur = batch_of(layer)
    if not cur:
        return 0
    for l in span[:-1]:
        if not _same_batch(batch_of(l), cur, thr):
            return 0

    n = 0
    for x in items:
        if x.get("status") != "active":
            continue
        cl = x.get("confirmed_layers") or []
        if all(l in cl for l in span):
            x["status"] = "stable"
            x["stable_since"] = layer
            n += 1
    return n


def update_suspensions(pool, view, layer: int, cfg: dict) -> dict:
    """修行/对撞/元层的悬置生命周期更新。"""
    stats = {"new": 0, "confirmed": 0, "revoked": 0,
             "resolved": 0, "stable": 0,
             "self_resolved": 0}
    need = int(cfg.get("stable_layers", 3))

    for s in (view.suspensions or []):
        target = str(s.get("target", "")).strip()
        if not target or len(target) < 4:
            continue
        if any(_similar(target, x.get("target", ""), 0.85)
               and x.get("status") in ("active", "stable")
               for x in pool.suspensions):
            continue
        rt = str(s.get("reason_type", "explicit")).lower()
        if rt not in SUSPENSION_REASON_TYPES:
            rt = "explicit"
        pool.suspensions.append({
            "id": f"s_{len(pool.suspensions) + 1:03d}",
            "target": target[:200],
            "reason": str(s.get("reason", ""))[:200],
            "reason_type": rt,
            "layer": layer,
            "last_confirmed_layer": layer,
            "confirmed_layers": [layer],
            "status": "active",
            "revoked_at": None,
            "revoke_reason": "",
            "resolved_at": None,
            "stable_since": None,
            "needs_review": False,
        })
        stats["new"] += 1

    ok_ids = {str(r.get("suspension_id", "")) for r in (view.reconfirmations or [])}
    ok_targets = [str(r.get("target", "")) for r in (view.reconfirmations or [])]
    for x in pool.suspensions:
        if x["status"] not in ("active", "stable"):
            continue
        if x["id"] in ok_ids or any(_similar(x["target"], t, _DUP_SIM)
                                    for t in ok_targets if t):
            x["last_confirmed_layer"] = layer
            cl = x.setdefault("confirmed_layers", [])
            if layer not in cl:
                cl.append(layer)
            stats["confirmed"] += 1

    for r in (view.revocations or []):
        sid = str(r.get("suspension_id", ""))
        tgt = str(r.get("target", ""))
        for x in pool.suspensions:
            if x["status"] not in ("active", "stable"):
                continue
            if x["id"] == sid or (tgt and _similar(x["target"], tgt, _DUP_SIM)):
                x["status"] = "revoked"
                x["revoked_at"] = layer
                x["revoke_reason"] = str(r.get("reason", ""))[:200]
                stats["revoked"] += 1

    eng = [str(e.get("target", "")) for e in (view.engagements or [])]
    for x in pool.suspensions:
        if x["status"] not in ("active", "stable"):
            continue
        if any(_similar(x["target"], e, _SUSP_SAME_SIM) for e in eng if e):
            x["status"] = "resolved"
            x["resolved_at"] = layer
            stats["resolved"] += 1
            if x.get("layer") == layer:
                stats["self_resolved"] += 1

    stats["stable"] = _turn_stable(pool.suspensions, layer, cfg)

    for x in pool.suspensions:
        if x["status"] == "active" and (layer - x["last_confirmed_layer"]) >= need:
            x["needs_review"] = True

    return stats


# ============================================================
# 研究层：延迟债务
# ============================================================
DEFERRAL_STATUS = ("deferred", "handled", "escalated", "dropped")
_BAD_REVISIT = ("以后", "适当时机", "待定", "稍后", "再说", "看情况")

_REVISIT_TIME_HINT = re.compile(
    r"(当|若|如果|一旦|在)[^。]{0,60}(时|后|前|了|的话)"
    r"|第\s*\d+\s*圈"
    r"|[^，。]{2,40}(之后|之前|以后)"
    r"|(下|本|上)\s*\d*\s*圈"
    # 兜底时间尾：含"后/时/前"结尾的短语（"形式化后"、"完成后"等）
    # 前面要求 ≥3 字，避免单字"时/后/前"被误匹配
    r"|[^，。]{3,40}(后|时|前)"
)

_REVISIT_CHANGE_VERB = re.compile(
    r"(出现|发生|完成|解决|给出|成立|失败|超过|达到|变化|更新|"
    r"补充|积累|形成|产生|暴露|显形|确认|推翻|失效|回答|清偿|"
    r"触发|发现|浮现|新增|消失|启动|落地|稳定|支持|反对|通过|"
    r"披露|揭示|证实|证伪|澄清|定位|锁定|"
    # [P1-6 修-2] 获取/核查动词族 —— 被拦 66 条里的大头是这类
    # （"拿到两项金额"、"调上月现金流量表"、"观测到 X"）
    r"拿到|取到|取得|查到|抄出|核出|调出|调取|观测|比对)"
)

_REVISIT_CITATION = re.compile(
    r"[TPSCd]_?\d+"
    r"|\bing\b"
    r"|覆盖率"
    r"|距离"
    r"|权重"
)


def _valid_revisit(cond: str) -> bool:
    """检查 revisit_condition 是否含**可观测锚点**。

    ★ v1.21.62 P1-6 修：判据放宽成"三类宽特征任一命中即通过" +
      "长度 ≥ 10 且不含黑名单词"兜底。**召回优先**——拦错了代价是
      "账消失"，放过一个模糊条件只是"多挂一笔不太精确的账"。
    """
    c = (cond or "").strip()
    if len(c) < 4:
        return False
    # 黑名单优先：纯空词一律拦
    if any(b in c for b in _BAD_REVISIT):
        return False
    # 三类宽特征任一命中即通过
    if (_REVISIT_TIME_HINT.search(c)
            or _REVISIT_CHANGE_VERB.search(c)
            or _REVISIT_CITATION.search(c)):
        return True
    # 兜底：长度 ≥ 8 字且不含黑名单词 → 视为有具体描述
    # [P1-6 修-2] 10 → 8：被拦的 66 条里 8 字短语占大头
    # （"取到部署顺序记录"、"逐字抄出两边原文"），它们都是合法条件。
    if len(c) >= 8:
        return True
    return False


def coverage_parts(pool, cfg: Optional[dict] = None,
                   entry: Optional[str] = None):
    """`(已答条数, 分母, 覆盖率)`。

    [v1.21.61] 以前只有 `coverage_of` 一个浮点数，产物于是只印百分比 ——
    「100%」到底是 `1/1` 还是 `20/20` 完全看不出来。实测同题同配置
    三跑（var_a/b/c）都是 100%，而代码实算是 **1/1、5/5、1/1**：分母
    自己会翻（研究层把同一批子问题判成可判定或不可判定的结果不一样），
    同一个百分比的含义差了五倍。以后封面/头条必须带分子分母。

    [v1.21.62] 分母改用**冻结名单** `_decided_answerable`（由三态独立判决
    在 ~13006 行写下）。在此之前分母是"此刻 `decidability` 落在
    `_DEC_ANSWERABLE` 里的条数"，于是三个写手会把它一路改小 ——
    `_starve_escalation` 饿够圈数就迁走、`_settle_research` 清算时
    escalated 也迁走。实测 tri_4：判决后 0/6/0 → 跑完 0/5/1，头条成 5/5。
    分母被机制改写意味着**两次跑的百分比不可比**（差的不是质量，是那一圈
    有没有触发 starve）。冻结后分母只由判决官那一票决定，稳。
    没有冻结标记的池（判决没跑成、或走了未覆盖的路径）回落到旧口径，
    不静默换算法。

    [v1.21.71 F10] `cfg` 改成**可选**。本函数目前**不读 cfg**（只用池
    字段），所以签名里那个必填的 dict 只是让人以为"必须给点什么"；
    `_refresh_settlement` 原来传 `{}`，等于隐式假设"这个函数永远不看
    cfg"，将来真加了 cfg 分支这里会静默走默认值。现在：签名可选 +
    调用点传真配置，两件事都做到。
    """
    if entry is not None and entry != "1":
        return 0, 0, None
    _all = list(pool.sub_questions)
    if any("_decided_answerable" in s for s in _all):
        subs = [s for s in _all if s.get("_decided_answerable")]
    else:
        subs = [s for s in _all
                if s.get("decidability") in _DEC_ANSWERABLE]
    if not subs:
        return 0, 0, None
    tot = sum(float(s.get("weight", 1.0)) for s in subs)
    if tot <= 0:
        return 0, 0, None
    cov = 0.0
    answered = 0
    deferred_ids = {d.get("sub_id") for d in pool.deferrals
                    if d.get("status") == "deferred"}
    for s in subs:
        w = float(s.get("weight", 1.0))
        if s.get("status") == "answered":
            answered += 1
            try:
                depth = float(s.get("depth", 1.0))
            except (TypeError, ValueError):
                depth = 1.0
            depth = max(0.0, min(1.0, depth))
            cov += w * depth
        elif s.get("id") in deferred_ids:
            cov += w * 0.2
    return answered, len(subs), cov / tot


def coverage_of(pool, cfg: Optional[dict] = None,
                entry: Optional[str] = None) -> Optional[float]:
    """可判定覆盖率（分母 = **欠一个答案**的子问题：可判定 + 部分可判定）。

    [v1.21.59] 以前分母只含 decidable，而 `_probe_research` 早就把
    partial 一起算成"必须回答的子问题"了 —— 三态可转之后 partial 真会
    落到子问题上，只认 decidable 会让分母静默漏账。两处口径现在同源
    （都走 `_DEC_ANSWERABLE`）。
    """
    _, _, cov = coverage_parts(pool, cfg, entry)
    return cov


def deferred_ratio_of(pool) -> float:
    subs = [s for s in pool.sub_questions
            if s.get("decidability") in _DEC_ANSWERABLE]
    if not subs:
        return 0.0
    deferred_ids = {d.get("sub_id") for d in pool.deferrals
                    if d.get("status") == "deferred"}
    n = sum(1 for s in subs if s.get("id") in deferred_ids)
    return n / len(subs)


_DECIDABILITY_STATES = ("decidable", "partial", "undecidable")
_DEC_STATE_CN = {"decidable": "可判定", "partial": "部分可判定",
                 "undecidable": "不可判定"}
_DEC_ANSWERABLE = ("decidable", "partial")


_TRI_VOTE_HEAD = (
    "你是【可判定性判决官】。本次是**三票独立判决**中的一票。\n"
    "\n"
    "给你若干条子问题，逐条判它：能不能被**判定**。\n"
    "\n"
    "【三态定义】\n"
    "- decidable：存在可指认的 0/1 候选答案——某个动作、条款、数值、\n"
    "  时间戳能被指认出「是或不是」。答得出也没关系，关键是**存在一个\n"
    "  能被占据的位置**。\n"
    "- undecidable：角色槽本身就是空的——定义尚未生成、角色未被指派、\n"
    "  缺共同参照系。不是「还没找到答案」，是「承载答案的位置还没长出来」。\n"
    "- partial：一部分能被指认，另一部分落在空槽里。\n"
    "\n"
    "【★ 顺序】每条先写一句 reason（为什么落在这一格），再给\n"
    "decidability。理由没写出来就判，等于猜。\n"
    "\n"
    "【本票的侧重】\n"
)

_TRI_VOTE_SLANT = (
    "偏严：只有你真的能指出那个「能被占据的位置」时才判 decidable；\n"
    "「理论上可以问」不算。判不出来就如实写 undecidable。",
    "偏保守：拿不准一律 partial。宁可承认不确定，也不要替它挑一格；\n"
    "但定义清楚、位置明显存在的，仍然要判 decidable，不要一律和稀泥。",
    "换角度：先问「承载这条答案的角色槽今天存在吗」——存在且被指派就\n"
    "decidable，槽没长出来就 undecidable，只有一半就 partial。",
)

_TRI_VOTE_JSON = (
    "\n"
    "严格 JSON：\n"
    '{"judgments":[{"id":1,"reason":"...",'
    '"decidability":"decidable|partial|undecidable"}]}'
)

_TRI_VOTE_PROMPTS = tuple(
    _TRI_VOTE_HEAD + s + _TRI_VOTE_JSON for s in _TRI_VOTE_SLANT
)


class DecidabilityFreeze:
    """ 可判定性冻结条。

    【它解决什么】覆盖率的分母必须是**判完那一刻**的名单，而不是"此刻
    `decidability` 落在 ANSWERABLE 里的条数"。后者会被同一批内部机制一路
    改写（饿够圈数迁移、清算时迁移），于是两次跑的百分比不可比 —— 差的
    不是质量，是那一圈有没有触发迁移。

    【做法】`freeze()` 把每条子问题「判完那一刻是否可答」写成
    `_frozen_answerable` 布尔值，并对 `(id, decidability, 是否可答)` 序列
    取 sha256 当签名。签名覆盖**判定本身**，不只是分母 —— 否则
    `decidable → partial` 这种"分母没变、判定变了"的改动会**测不出来**
    （实测踩过：只签布尔时，篡改 decidable→partial 后 `verify()` 不报错）。
    理由文本不进签名：理由措辞每轮都会变，算进去会让签名每轮都不同。

    【`verify()` 为什么抛错而不是返回 False】调用点若忘了检查返回值，
    一个 False 会被静默吞掉；抛 RuntimeError 逼调用方在"冻结条已被推翻"
    这件事上显式表态（这正是 `sub["decidability"]` 被改判时的形态）。
    """

    def __init__(self) -> None:
        self.signature = ""
        self.layer = None
        self.n = 0
        self.items: List[List[object]] = []
        self.frozen_at = ""

    def _canon(self, pool) -> List[List[object]]:
        """签名条目 = 五元组：id / 当前标签 / 当前可答性 / 冻结布尔 / 冻结标签。

        ★ 走过的弯路：早先这里只记 `[id, 当前标签, 由标签现推的可答性]`。
          于是「只把 `_frozen_answerable` 翻过来、标签不动」改不动签名 ——
          被冻结的那个布尔**根本没进签名**，它只是个没人读的副本。
          任务书 Step 3.3 的冒烟标的正是这一刀；探针实测返回「未判红」。
          教训：签名要覆盖**被冻结的每一格**，不能覆盖「能从别的格推出来的
          那一格」—— 后者等于没签。
        """
        out: List[List[object]] = []
        for s in (getattr(pool, "sub_questions", None) or []):
            _lab = str(s.get("decidability", "") or "")
            _fz_b = s.get("_frozen_answerable", None)
            _fz_l = s.get("_frozen_decidability", None)
            out.append([str(s.get("id", "")), _lab,
                        bool(_lab in _DEC_ANSWERABLE),
                        None if _fz_b is None else bool(_fz_b),
                        None if _fz_l is None else str(_fz_l)])
        return out

    @staticmethod
    def _digest(layer, items) -> str:
        payload = json.dumps({"layer": layer, "n": len(items),
                              "items": items},
                             ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def freeze(self, pool, layer: int = 1) -> str:
        self.layer = int(layer)
        # ★ 顺序：**先写冻结键、再算 items**。反过来（先算后写）会让
        #   `_canon` 在冻结那一刻记下 None，之后 verify 立刻不匹配 ——
        #   「刚冻结就验不过」这种症状极难往顺序上想。
        for s in (getattr(pool, "sub_questions", None) or []):
            _ans = bool(s.get("decidability") in _DEC_ANSWERABLE)
            s["_frozen_decidability"] = str(s.get("decidability", "") or "")
            s["_frozen_answerable"] = _ans
            s["_decided_answerable"] = _ans
        self.items = self._canon(pool)
        self.n = len(self.items)
        self.frozen_at = datetime.now().isoformat()
        self.signature = self._digest(self.layer, self.items)
        return self.signature

    def verify(self, pool) -> bool:
        cur = self._canon(pool)
        if self._digest(self.layer, cur) != self.signature:
            raise RuntimeError(
                "可判定性冻结条被推翻：当前判定与冻结签名不符"
                f"（冻结 {self.n} 条 / 现在 {len(cur)} 条，"
                f"layer={self.layer}）")
        return True

    def to_dict(self) -> dict:
        return {"signature": self.signature, "layer": self.layer,
                "n": self.n, "frozen_at": self.frozen_at,
                "items": self.items}



def _ev_list(raw) -> List[str]:
    """把 evidence 字段规整成非空字符串列表（容忍 str / list / None）。"""
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else [raw]
    out: List[str] = []
    for x in items:
        s = str(x).strip()
        if s:
            out.append(s[:120])
        if len(out) >= 5:
            break
    return out


_UNTRACED_OVERLAP = 0.6


def _untraced_undecidable(und_aspects, evidences) -> List[str]:
    """ 「理由是否成立」的确定性检查：每条不可判定有没有池内追溯。

    ★ 为什么需要它：判定对不对，**不能靠死记"某道题应该判成什么"**。
    上一轮就栽在这上面——先预设"地铁该 decidable"，改完又预设"地铁该
    partial"，两次都把预设当判据，两次都判错。能**自动查**的只有两件事：
      · 池判与外判**分不分叉**（`_divergent`）
      · 每条不可判定有没有**池内追溯**（本函数）
    没追溯的不可判定 = 凭空说的，理由不成立，该被挑出来而不是被采信。

    ★ [v1.21.61 稳定性探针] 抗噪：模型爱往条目里塞**来源标注**后缀，
    真跑实证（同一 view 重复评估 5 次）里同一条语义被写成：
        '清分规则未定，断面客流与线路客流不可互证'
        '清分规则未定时断面客流与线路客流不可互证（候选16）'
        '清分规则未定，断面客流与线路客流无法互证（悬置1）'
    后缀改变了分词，直接比对会把**有追溯的**误判成无追溯 —— 判据
    自己变成噪声源。所以比对前先剥掉括号来源标注和标点差异。
    """
    def _bare(t: str) -> str:
        # 剥「（候选16）」「(&印记)」「[外]」这类来源标注，只留语义本体
        t = re.sub(r"[（(\[【]\s*(?:候选|amp|&|印记|悬置|suspension|thread|"
                   r"线头|外)?\s*[0-9A-Za-z]*\s*[)）\]】]", "", str(t))
        return re.sub(r"[，。、；：:,\.;\s]+", "", t).strip()

    srcs = [str(e.get("aspect", "")) for e in (evidences or [])
            if isinstance(e, dict)]
    srcs = [_bare(e) for e in srcs if str(e).strip()]
    out: List[str] = []
    for a in (und_aspects or []):
        s = str(a).strip()
        if not s:
            continue
        bs = _bare(s)
        if not any(_similar(bs, x, 0.55) or _similar(x, bs, 0.55)
                   or (bs and x and (bs in x or x in bs))
                   or _overlap_coef(bs, x) >= _UNTRACED_OVERLAP
                   for x in srcs):
            out.append(s)
    return out


def _normalize_decidability(status, dec_aspects, und_aspects,
                            where: str = "") -> str:
    """三态与「方面清单」必须自洽 —— **全项目唯一一份**归一化。

    规则（沿用旧 sanity check，但以前**只有外部评估**用了它）：
      · undecidable + 有 decidable 方面 → partial
        （既然存在可判定的部分，就不能说"以不可判定为主"——更不能
         拿这个标签把那些部分整个丢掉）
      · decidable + 有 undecidable 方面 → partial
      · partial + 两方面都空 → decidable
      · 两方面都有 → partial

    ★ v1.21.59：以前这段只写在 `_assess_decidability`（外部评估，开跑前）
      里，`_assess_decidability_from_pool_view`（读修行池形状的那次）**没有**，
      `_merge_decidability`（合并）**也没有**。于是池判可以返回
      「undecidable + 3 条 decidable 方面」，再被合并原样采信，最后
      `_decompose_question` 只看标签走 koan —— 那些 decidable 方面
      **一条都没进子问题**，覆盖率分母从出生就是 0（v59 整层交白卷）。
    """
    s = str(status or "").lower()
    if s not in _DECIDABILITY_STATES:
        s = "decidable"
    orig = s
    if s == "decidable" and und_aspects:
        s = "partial"
    if s == "undecidable" and dec_aspects:
        s = "partial"
    if s == "partial" and not und_aspects and not dec_aspects:
        s = "decidable"
    if dec_aspects and und_aspects:
        s = "partial"
    if s != orig:
        logger.info("可判定性归一化%s：%s → %s",
                    f"（{where}）" if where else "", orig, s)
    return s


_ANCHOR_TIERS = ("off", "record", "crosscheck", "evidence", "gate")

_TRIAGE_KEYS = ("信息不足", "需外部动作", "缺数据", "无外部")

_TRIAGE_STRUCTURAL_PREFIXES = ("[外]",)   # 引擎自己的标签，可加 [内] 等

_TRIAGE_SEMANTIC_KEYS = _TRIAGE_KEYS + (  # 语义关键词：旧四类 + 三个同义写法
    "需要外部", "取决于外部", "依赖外部",
)

_TRIAGE_NEVER_DOWNGRADE = ("自指", "自证", "本体论", "无共同参照系")


def _is_triage_candidate(aspect: str) -> bool:
    """ 该 undecidable 侧面是否属于「缺外部材料」那一类。

    两路**并集**：① 结构标签前缀；② 语义关键词。
    调用点先过 `_is_never_downgrade` 再走本函数 —— 判据的顺序在调用点，
    不写在这里，免得两处各判一次。
    """
    s = str(aspect or "").strip()
    if not s:
        return False
    if any(s.startswith(p) for p in _TRIAGE_STRUCTURAL_PREFIXES):
        return True
    return any(k in s for k in _TRIAGE_SEMANTIC_KEYS)


def _is_never_downgrade(aspect: str) -> bool:
    """这些是 v1.21.59 定义的真正「原则判不出」：锚点无关，不许降级。"""
    s = str(aspect or "")
    return any(k in s for k in _TRIAGE_NEVER_DOWNGRADE)


def _triage_suggestions(und_aspects, anchors, cfg) -> List[dict]:
    """ 分诊降级的**建议清单**（纯函数，无副作用、不调 LLM）。

    从 `_anchor_crosscheck` 里**原样抽出**（行为一字不改，只搬位置）。

    【为什么抽成纯函数】它是「能力存在性」的**判定核心**，而原先只能通过
      **真跑采样**间接观察 ⇒ 判据写成 n=3 的采样比较，本质是掷硬币
      （实测同配置两次批次：[1,0,0] 与 [0,…]）。抽出来之后可以
      **构造性证明**：喂已知合格的输入，断言必产 ≥1 条；再配负对照。

    【条件】该侧面 ① 非「真·自指」（`_is_never_downgrade`）、
      ② 属「缺外部材料」那类（`_is_triage_candidate`）、
      ③ 被一条 **tier ≤ floor** 的锚点命中（`answers` 或 `claim` 双路径取 OR）。
    ★ 只出**建议**，不改任何判定 —— 无证据的自动降档正是要避免的事。
    """
    out: List[dict] = []
    _floor = _tier_floor(cfg)
    for _a in (und_aspects or []):
        if _is_never_downgrade(_a):
            continue
        if not _is_triage_candidate(_a):
            continue
        _hit = next((x for x in (anchors or [])
                     if int(x.get("tier", 3) or 3) <= _floor
                     and (_hit_by_answers(str(_a), x.get("answers") or [])
                          or _hit_by_claim(str(_a),
                                           str(x.get("claim", ""))))),
                    None)
        if _hit:
            out.append({"from": "undecidable", "to": "partial",
                        "aspect": str(_a)[:80],
                        "anchor_id": _hit.get("id")})
    return out


# 机制审计登记表。**必须与源码里 `# [AUDIT-122]` 注释条数
_AUDIT122_PENDING_FIX = 2
_AUDIT122_DUAL_IMPL = 2


# [AUDIT-122] 标 pending_fix：`as_evidence` 的**布尔兼容路径**保留一版。
def _anchor_tier(cfg) -> str:
    """把 `external_anchor.as_evidence` 归一到五档之一。

    ★ 兼容 v1.21.75 的布尔：True → "evidence"，False → "off"。
      非法值按 "off" 处理（调用点会把它渲染出来，不静默升级权限）。
      [v1.23.5] 走布尔兼容会 logger.warning 留痕（可观测化，不再静默）。
    """
    raw = (cfg or {}).get("as_evidence", "off")
    if isinstance(raw, bool):
        logger.warning(
            "external_anchor.as_evidence 用了 v1.21.75 的布尔写法 %r"
            " → %s（请迁到五档字符串 off/record/crosscheck/evidence/gate）",
            raw, "evidence" if raw else "off")
        return "evidence" if raw else "off"
    s = str(raw or "off").strip().lower()
    return s if s in _ANCHOR_TIERS else "off"


def _tier_floor(cfg) -> int:
    try:
        return int((cfg or {}).get("tier_floor", 2) or 2)
    except (TypeError, ValueError):
        return 2


class AnchorRetriever:
    """ 锚点检索适配层。

    `snapshot` 是**零调用**路径（读快照）。`tavily` 走真 HTTP，结果按
    queries 的 sha256 落 `cache/anchors/`，TTL 内不再打网络 —— 检索是
    最贵的一环，「先量后改」在钱上同样成立。
    """

    def __init__(self, backend: str, api_key: str, ttl_hours: int = 24):
        self.backend = str(backend or "snapshot").strip().lower()
        self.api_key = api_key or ""
        self.ttl = float(ttl_hours or 24) * 3600.0

    def _cache_path(self, queries):
        key = hashlib.sha256(
            json.dumps(list(queries), sort_keys=True,
                       ensure_ascii=False).encode("utf-8")).hexdigest()
        return Path("cache/anchors") / (key[:24] + ".json")

    def search(self, queries, max_n: int = 12) -> List[dict]:
        if self.backend == "snapshot":
            return []
        if self.backend != "tavily":
            raise RuntimeError(
                "external_anchor.retriever=" + repr(self.backend)
                + " 尚未实现（当前只有 'snapshot' 与 'tavily'）；"
                + "不静默降级")
        cache = self._cache_path(queries)
        try:
            if cache.is_file():
                d0 = json.loads(cache.read_text(encoding="utf-8"))
                if time.time() - float(d0.get("_ts") or 0) < self.ttl:
                    return list(d0.get("anchors") or [])
        except Exception:
            pass                      # 缓存坏了不是错误，重查一遍即可
        res = self._tavily(list(queries or []), int(max_n or 12))
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"_ts": time.time(),
                                         "anchors": res},
                                        ensure_ascii=False, indent=2),
                             encoding="utf-8")
        except Exception as exc:      # 缓存写失败不影响本次结果
            logger.warning("锚点缓存写入失败：%s", exc)
        return res

    def _tavily(self, queries, max_n: int) -> List[dict]:
        import urllib.request
        out: List[dict] = []
        for q in queries[:2]:
            body = json.dumps({"api_key": self.api_key, "query": q,
                               "max_results": max_n}).encode("utf-8")
            req = urllib.request.Request(
                "https://api.tavily.com/search", data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            for it in (data.get("results") or []):
                out.append({"id": "t" + str(len(out) + 1),
                            "claim": str(it.get("content", ""))[:400],
                            "source": str(it.get("url", "")),
                            "url": str(it.get("url", "")),
                            "as_of": "", "kind": "tavily", "tier": 3})
                if len(out) >= max_n:
                    _record_web_hits(" | ".join(list(queries or [])[:2]), out)
                    return out
        _record_web_hits(" | ".join(list(queries or [])[:2]), out)
        return out


logger_web = logging.getLogger("dgtf.websearch")
logger_web.setLevel(logging.INFO)
logger_web.propagate = False


# ── 联网检索命中落盘（给工作台的「联网检索库」）─────────────────
#   条目本来就有 claim + url，此前只在**失败**时留痕；成功时顺手落一份，
#   应用层读 JSONL 就能展示「检索到了什么、来自哪」。
_WEB_HITS_PATH = os.path.join(
    os.environ.get("DGTF_OUTPUT_DIR", "outputs"), "_web_hits.jsonl")


def _record_web_hits(query, items) -> None:
    """把一次检索命中的条目**追加**到 JSONL。任何失败都静默（不能拖累检索）。"""
    items = list(items or [])
    if not items:
        return
    try:
        _d = os.path.dirname(_WEB_HITS_PATH)
        if _d:
            os.makedirs(_d, exist_ok=True)
        with open(_WEB_HITS_PATH, "a", encoding="utf-8", newline="") as f:
            for it in items:
                if not isinstance(it, dict):
                    continue
                f.write(json.dumps({
                    "ts": time.time(),
                    "query": str(query or "")[:200],
                    "claim": str(it.get("claim", ""))[:400],
                    "url": str(it.get("url", "") or it.get("source", ""))[:400],
                    "tier": it.get("tier"),
                    "kind": str(it.get("kind", "")),
                }, ensure_ascii=False) + "\n")
    except OSError:
        pass

# ★ 独立通道的意义：检索失败（超时/限流/脏数据）是**高频、可预期**的，
#   混进主线日志会让一次网络抖动淹没整份跑圈痕迹。

WEB_FAIL_KINDS = ("timeout", "rate_limit", "empty", "dirty", "api_error")


_AUDIT_DEAD_CLASSES = ("Amp", "Probe", "Thread")
#   定义后零引用、按纪律**不删**的类。`Amp`/`Probe` 是 dataclass，
#   实际跑批里 amp/probe 都以 dict 形态流动（`pool.amps` / `pool.probes`），
#   所以这两个类只剩历史意义。**只标不删** —— 删了会丢掉「曾经有这个形态」
#   的线索，而留着需要登记才不会每次审计都被当成新发现。
_AUDIT_EXPORT_EXEMPT = {}
#   形如 {"类名": ("允许不出口的字段",)}。当前**无豁免**：
#   `Candidate` / `Probe` / `View` / `Pool` 的全部字段都必须出现在 to_dict()
#   （这是本项目的第 3 类高频坑：显式白名单漏字段 = 静默吞掉）。
_AUDIT_CONFIG_EXEMPT = (
    "web_search.stages.practice_term_calibration",
    "web_search.stages.stop_criteria",
)
#   声明了「不做」的配置键（任务书 §七：不做修行层联网、不做停止判据联网）。
#   它们**永远不会**被 `_web_search(stage=...)` 调用到 ⇒ 属「声明了不做」，
#   不是漏接线。登记在这里，两向对账防它悄悄变成真装饰品。
_WEB_USED_AS = ("evidence", "record", "arbitration", "clean_check", "tri_vote")
#   `web_results[*]["used_as"]` 的**取值枚举**（封闭集合）。
#   ★ 它没有程序消费方：它写给**读者**（产物里能看出这条给谁用）与
#     分析脚本（`_w6_analyze.py`）。枚举化是为了钉住「不得出现未登记取值」——
#     原先它是自由字符串，于是 W4 第三票写着 `arbitration` 而 stage 是
#     `research_evidence`，两个标签对不上，读者无从判断。


def _web_cfg_of(cfg) -> dict:
    """把「完整 config」或「config["web_search"] 子段」归一成子段。

    ★ 两种写法在本项目**都**出现（`WebSearchGate(config)` 收完整、
      `pool._web_cfg` 存子段）——只认一种会让另一种**静默**读不到配置
      （v1.23.1 的 `_web_tier_proposal` 就踩过一次）。
    """
    if isinstance(cfg, dict) and isinstance(cfg.get("web_search"), dict):
        return cfg["web_search"]
    return cfg if isinstance(cfg, dict) else {}


def _web_tier_confirmed(cfg, url):
    """ 人工确认表里该 URL 的域名有没有被确认过 tier。

    返回 int 或 None。★ **只读** `web_search.tier_confirmed`（人写的），
    **绝不**读 `tier_proposal` 的产物 —— 从提案到生效**没有自动路径**。
    """
    _d = _web_domain_of(url)
    if not _d:
        return None
    _conf = _web_cfg_of(cfg).get("tier_confirmed") or {}
    if not isinstance(_conf, dict) or _d not in _conf:
        return None
    try:
        return int(_conf[_d])
    except (TypeError, ValueError):
        return None


def _web_tier_floor(cfg) -> int:
    """ W# 进引用表的 tier 门。

    ★ 本键（`web_search.tier_floor`）在 v1.23.1 及以前**从未被读过**
      —— 又一个「定义了没人读」的装饰品键（审计 J 类抓出来的）。
      默认改为 **3**：客户端初值 3 可进表 ⇒ 与 v1.23.1 行为一致。
    """
    # ★ 不能用 `x or 3`：那把 **0** 也吃掉了（`0 or 3 == 3`）—— 而
    #   `tier_floor: 0` 的语义是「谁都不许进表」，正是最该生效的严格档。
    #   与 `WebSearchGate._i()` 同款写法：只有 None 才回落默认。
    _v = _web_cfg_of(cfg).get("tier_floor", 3)
    try:
        return 3 if _v is None else int(_v)
    except (TypeError, ValueError):
        return 3


def _web_tier_effective(item) -> int:
    """W# 的**有效** tier：人工确认值优先，否则取它自带的 tier（默认 3）。"""
    _v = (item or {}).get("tier_effective")
    if _v is None:
        _v = (item or {}).get("tier", 3)
    try:
        return int(3 if _v is None else _v)
    except (TypeError, ValueError):
        return 3


def _web_enters_citation(item, cfg) -> bool:
    """ W# 是否够格进引用表（与 X# 同纪律：tier ≤ floor）。"""
    return _web_tier_effective(item) <= _web_tier_floor(cfg)


def _normalize_judgment_ids(judged, n):
    """ 把一票的 `{id: label}` 归一到 **1..n** 对齐；越界返回 None。

    【为什么需要 —— 受控实验抓到的真 bug】
      `_ab_tri_votes_v1233.py` 实测：某票返回的 `judgments[].id` 是 **0 起**
      （0..n-1），而引擎按 **1 起** 对齐（`for i, s in enumerate(subs, 1)`）。
      后果：该票**整票错位一格** —— 第 2 条子问题拿到本该给第 1 条的标签，
      第 1 条没人投。既不抛错也不留痕，**读者从产物上完全看不出来**，
      而三态判决、`stability`、`tri_consensus` 全部跟着偏。
      两处实现（多票 / 单票）都是 `sid = int(it.get("id", 0))` 直接用。

    【口径】只归一、不猜：
      · 键集 ⊆ {1..n}      → 原样（生产口径）
      · 键集 ⊆ {0..n-1}    → 整体 +1（这才是 0 起；**留痕**，不静默）
      · 其他（含越界 / 混合）→ 返回 None ⇒ 调用方**弃这一票**
        （绝不做「把第 k 条硬塞给第 k 条」这种猜测 —— 那正是要防的静默）。
    返回 `(归一后的 dict 或 None, 档位说明)`，说明进池级留痕。
    """
    if not isinstance(judged, dict) or not judged or int(n or 0) <= 0:
        return None, "空"
    _ks = set(judged)
    _hi = int(n)
    if _ks <= set(range(1, _hi + 1)):
        return dict(judged), "1起"
    if _ks <= set(range(0, _hi)):
        return {int(k) + 1: v for k, v in judged.items()}, "0起+1"
    return None, "越界"


def _canonical_sub_ids(items):
    """ 把子问题的 `id` 按**当前位置**重编号成 1..n（就地）。

    【为什么必须做】`_parse_subs` / `_decompose_from_pool` 的 id 直接来自
      模型（`int(sq.get("id", len(out) + 1))`）—— 模型有时给 0 起、有时漏给
      （回落成位置）、有时重复。于是同一份 `subs` 里 id 可能是 0..n-1、
      可能带洞，而下游一律默认它是 1..n：
        · 三票 prompt 用 `enumerate(subs, 1)` 编号；
        · `sub_id` 留痕 / `sub_by_id` 查找 / `answered_sub_ids` 的展示。
      id 是**本地的行号**，由模型决定没有任何好处，只有风险。
    【加性】条数、顺序、其他字段一律不动，只改 `id`。
    """
    for _i, _s in enumerate(items or [], 1):
        if isinstance(_s, dict):
            _s["id"] = _i
    return items


def _thinking_stage(cfg, name):
    """ 环节名 → thinking 的 stage 键；**只在声明过时**返回。

    【为什么需要】审计发现 15 个 `api.thinking.stages.*` 键**永远选不中**：
      `_decompose_normal` / `_probe_*` / `_settle_research` / `re_anchor` …
      共 16 个调用点根本没传 `stage=` ⇒ 一律掉回 `thinking_default`。
      用户把 `decompose_normal` 改成 `enabled` 会**毫无效果**（静默装饰品）。
    【为什么以配置为准】写死字符串会有拼写错；拼错 = 静默掉回 default，
      与没接线一样。这里「键必须已声明」才返回，拼错返回 None，并可被
      判据（`_probe_v1232_audit.py` K 类）抓出来。
    """
    _st = ((cfg or {}).get("api") or {}).get("thinking") or {}
    return name if name in (_st.get("stages") or {}) else None


class WebSearchCache:
    """ sha256 + TTL 检索缓存。**只省调用，不入池。**"""

    def __init__(self, ttl_hours: float = 24.0, root: str = "cache/websearch"):
        self.ttl = float(ttl_hours or 24.0) * 3600.0
        self.root = Path(root)
        self.hits = 0
        self.misses = 0

    def key(self, backend: str, query: str) -> str:
        return hashlib.sha256(
            (str(backend) + ":" + str(query)).encode("utf-8")).hexdigest()[:24]

    def path_for(self, backend: str, query: str) -> Path:
        return self.root / (self.key(backend, query) + ".json")

    def get(self, backend: str, query: str):
        """命中返回 results（可能是空 list）；未命中 / 过期返回 None。"""
        p = self.path_for(backend, query)
        try:
            if p.is_file():
                d0 = json.loads(p.read_text(encoding="utf-8"))
                if time.time() - float(d0.get("_ts") or 0) < self.ttl:
                    self.hits += 1
                    return list(d0.get("results") or [])
        except Exception:
            pass                    # 缓存坏了不是错误，重查一遍即可
        self.misses += 1
        return None

    def put(self, backend: str, query: str, results) -> None:
        p = self.path_for(backend, query)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"_ts": time.time(),
                                     "results": list(results or [])},
                                    ensure_ascii=False, indent=2),
                         encoding="utf-8")
        except Exception as exc:    # 缓存写失败不影响本次结果
            logger_web.warning("[W-CACHE-WRITE] %s", exc)

    def domains_load(self) -> set:
        """ 已见域名集合（tier 提案的「首次出现」判据）。

        ★ 只登记域名，**不存 tier** —— tier 由人确认，不由这里定。
        坏文件 / 不存在 → 空集（缓存坏了不是错误）。
        """
        p = self.root / "_domains.json"
        try:
            if p.is_file():
                d0 = json.loads(p.read_text(encoding="utf-8"))
                return {str(x) for x in (d0.get("domains") or []) if str(x)}
        except Exception:  # noqa: BLE001
            pass
        return set()

    def domains_save(self, new_domains) -> None:
        """把新域名并进 `cache/websearch/_domains.json`。写失败只告警。"""
        _all = sorted(self.domains_load()
                      | {str(x) for x in (new_domains or []) if str(x)})
        p = self.root / "_domains.json"
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(json.dumps({"_ts": time.time(), "domains": _all},
                                     ensure_ascii=False, indent=2)
                          .encode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger_web.warning("[W-DOMAIN-WRITE] %s", exc)


class WebSearchClient:
    """ HTTP 客户端：超时 / 重试 / 退避 / **五类失败**。

    ★ 与 `AnchorRetriever._tavily` 的区别：那个抓的是**锚点快照**（一次性、
      无重试、无分类）；本类是**运行时**检索，必须把失败**分类**返回 ——
      否则调用方看到的是「0 条」，分不清「外部没有」和「这次没问到」。
    ★ `_http()` 是**可打桩的缝**：探针 / 冒烟覆写它就能离线测全部五档失败，
      不需要网络。
    """

    def __init__(self, backend: str, api_key: str, timeout: float = 30,
                 max_retries: int = 2, backoff: float = 1.8,
                 cache: Optional["WebSearchCache"] = None):
        self.backend = str(backend or "tavily").strip().lower()
        self.api_key = api_key or ""
        self.timeout = float(timeout or 30)
        self.max_retries = int(max_retries or 0)
        self.backoff = float(backoff or 0)
        self.cache = cache
        self.calls = 0              # 真打网络的次数（缓存命中不计）
        self.cache_hits = 0
        self.fail_counts: Dict[str, int] = {}

    def _endpoint(self) -> str:
        if self.backend == "tavily":
            return "https://api.tavily.com/search"
        # ★ 与 `AnchorRetriever` 同款纪律：未知后端**抛错留痕**，不静默降级。
        raise RuntimeError(
            "web_search.backend=" + repr(self.backend)
            + " 尚未实现（当前只有 'tavily'）；不静默降级")

    def _http(self, query: str, max_n: int) -> Tuple[list, str]:
        """真打网络。返回 `(results, fail_kind)`；成功时 fail_kind == ""。"""
        import urllib.error
        import urllib.request
        body = json.dumps({"api_key": self.api_key, "query": query,
                           "max_results": int(max_n)}).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint(), data=body,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read().decode("utf-8")
        except TimeoutError:
            return [], "timeout"
        except urllib.error.HTTPError as exc:
            if int(getattr(exc, "code", 0) or 0) == 429:
                return [], "rate_limit"
            return [], "api_error"
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), TimeoutError):
                return [], "timeout"
            return [], "api_error"
        except OSError:
            return [], "api_error"
        try:
            data = json.loads(raw)
        except Exception:
            return [], "dirty"
        if not isinstance(data, dict):
            return [], "dirty"
        out: List[dict] = []
        for it in (data.get("results") or []):
            if not isinstance(it, dict):
                continue
            _c = str(it.get("content", "") or "").strip()
            if not _c:
                continue
            out.append({"claim": _c[:400],
                        "url": str(it.get("url", ""))[:300],
                        "source": str(it.get("url", ""))[:200],
                        "kind": "web", "tier": 3})
        _record_web_hits(query, out)
        return out, ("" if out else "empty")

    def search(self, query: str, max_n: int = 8) -> Tuple[list, str]:
        """检索一条 query。返回 `(results, fail_kind)`。

        · 缓存命中 → 直接返回，**不计 calls**；
        · `empty` 是**终态**（外部确实没有），不重试、不算「连续失败」；
        · 其余失败档按 `max_retries` 重试（线性退避），全失败则返回最后一档。
        """
        if self.cache is not None:
            hit = self.cache.get(self.backend, query)
            if hit is not None:
                self.cache_hits += 1
                return hit, ""
        kind = "api_error"
        for attempt in range(self.max_retries + 1):
            self.calls += 1
            res, kind = self._http(query, max_n)
            self.fail_counts[kind] = self.fail_counts.get(kind, 0) + 1
            if kind in ("", "empty"):
                if kind == "" and self.cache is not None:
                    self.cache.put(self.backend, query, res)
                return res, kind
            logger_web.warning("[W-%s] query=%s attempt=%d/%d",
                               kind.upper(), str(query)[:80],
                               attempt + 1, self.max_retries + 1)
            if attempt < self.max_retries:
                time.sleep(self.backoff * (attempt + 1))
        return [], kind


class WebSearchGate:
    """ 授权 + 配额三层 + 连续失败降级。

    ★ 三个否定方向（未启用 / 未授权 / 配额或降级）都必须给出**可读理由**，
      并且 `allow()` 的 reason 与 `disabled` **状态一致** —— 否则产物里
      只能从每次 reason 猜「本跑到底降级没有」。
    """

    def __init__(self, config: dict, run_id: str = ""):
        self.cfg = ((config or {}).get("web_search") or {})
        self.run_id = run_id
        self.stage_counts: Dict[str, int] = {}
        self.round_counts: Dict[Tuple[str, int], int] = {}
        self.run_total = 0
        self.consecutive_failures = 0
        self.disabled = not bool(self.cfg.get("enabled", False))
        self.disable_reason = "" if not self.disabled else "web_search 未启用"

    def _q(self, k: str, d: int) -> int:
        try:
            return int((self.cfg.get("quota") or {}).get(k, d) or d)
        except (TypeError, ValueError):
            return d

    def _i(self, k: str, d: int) -> int:
        _v = self.cfg.get(k, d)
        try:
            return int(d if _v is None else _v)
        except (TypeError, ValueError):
            return d

    def allow(self, stage: str, round_no: int) -> Tuple[bool, str]:
        if not bool(self.cfg.get("enabled", False)):
            return False, "web_search 未启用（默认关）"
        if not bool((self.cfg.get("stages") or {}).get(stage, False)):
            return False, "stage " + repr(stage) + " 未授权"
        if self.disabled:
            return False, ("本跑已降级（连续失败 "
                           + str(self.consecutive_failures) + " 次）")
        if self.run_total >= self._q("per_run_total", 30):
            return False, "本次运行总配额用尽"
        if self.stage_counts.get(stage, 0) >= self._q("per_stage_total", 8):
            return False, "stage " + repr(stage) + " 全程配额用尽"
        if self.round_counts.get((stage, round_no), 0) >=                 self._q("per_stage_round", 2):
            return False, "stage " + repr(stage) + " 本圈配额用尽"
        return True, ""

    def note_call(self, stage: str, round_no: int) -> None:
        self.stage_counts[stage] = self.stage_counts.get(stage, 0) + 1
        self.round_counts[(stage, round_no)] =             self.round_counts.get((stage, round_no), 0) + 1
        self.run_total += 1

    def note_failure(self, kind: str = "") -> bool:
        """记一次失败。返回**是否因此被降级**（调用方据此留痕）。"""
        self.consecutive_failures += 1
        _lim = self._i("auto_disable_after_failures", 3)
        if self.consecutive_failures >= _lim and not self.disabled:
            self.disabled = True
            self.disable_reason = ("连续失败 " + str(self.consecutive_failures)
                                   + " 次（限 " + str(_lim) + "），本跑联网关闭")
            logger_web.warning("[W-DISABLED] %s", self.disable_reason)
            return True
        return False

    def note_success(self) -> None:
        self.consecutive_failures = 0

    def summary(self) -> dict:
        return {"enabled": bool(self.cfg.get("enabled", False)),
                "disabled": self.disabled,
                "disable_reason": self.disable_reason,
                "run_total": self.run_total,
                "stage_counts": dict(self.stage_counts),
                "consecutive_failures": self.consecutive_failures}


def build_web_search(config: dict, run_id: str = "") -> Tuple[WebSearchGate,
                                                              WebSearchClient]:
    """ 从配置造一套（Gate + Client + Cache）。**不发起任何调用。**

    `enabled=False` 时同样返回可用对象 —— 只是 `gate.allow()` 恒 False，
    于是调用点不需要写 `if enabled` 这种会被漏掉的判断。
    """
    cfg = ((config or {}).get("web_search") or {})
    gate = WebSearchGate(config, run_id)
    cache = WebSearchCache(cfg.get("cache_ttl_hours", 24))
    _env = str(cfg.get("api_key_env") or "").strip()
    client = WebSearchClient(
        backend=cfg.get("backend", "tavily"),
        api_key=(os.environ.get(_env, "") if _env else ""),
        timeout=cfg.get("timeout_seconds", 30),
        max_retries=cfg.get("max_retries", 2),
        backoff=cfg.get("backoff_seconds", 1.8),
        cache=cache)
    return gate, client


def _next_web_id(pool) -> str:
    """W# 编号（跨层全局唯一）。"""
    return "W" + str(len(getattr(pool, "web_results", None) or []) + 1)


def _web_evidence_gate(cfg) -> bool:
    """`web_search.as_evidence` 是否属于「允许 W# 进引用表」的两档。

    ★ 与 `_anchor_tier`（external_anchor 的五档）同款纪律：未知取值 → 关，
      不静默放开。「进了引用表就能作证据」是行为变化，不是加性。
    """
    _a = str(((cfg or {}).get("web_search") or {}).get("as_evidence", "")
             or "").strip().lower()
    return _a in ("evidence", "gate")


def _research_decompose_queries(question: str, pool) -> List[str]:
    """[W2·research_decompose] 拆解前的检索词：原问题 + 池内结构型印记补强。"""
    _q = str(question or "").strip()
    if not _q:
        return []
    out = [_q[:200]]
    for a in (getattr(pool, "amps", None) or [])[:2]:
        _d = str((a or {}).get("desc", "")).strip()
        if _d:
            out.append((_q[:80] + " " + _d[:80])[:200])
    return [x for x in out if x.strip()][:2]


def _research_evidence_queries(prop: dict) -> List[str]:
    """[W2·research_evidence] 给一条「迁向 partial」的提案配检索词。

    ★ 只对 `to == "partial"` 发 —— `→undecidable` 是「答不出」的结论，
      检索命中与否**不能**作为它成立的依据（方向反了）。
    """
    if str((prop or {}).get("to", "")).strip().lower() != "partial":
        return []
    _sq = str((prop or {}).get("_sq_text") or "").strip()
    if not _sq:
        return []
    return [_sq[:120]]


def _research_precedent_queries(und_aspects) -> List[str]:
    """[W2·research_precedent] 把结构标签为 [外] 的不可判定方面改造成存在性问句。"""
    out: List[str] = []
    for a in (und_aspects or []):
        s = str(a).strip()
        if s.startswith("[外]"):
            out.append(
                ("是否存在 " + s[3:].strip()[:80] + " 的官方指引？")[:160])
        if len(out) >= 3:
            break
    return out


def _duel_arbitration_queries(tensions) -> List[str]:
    """[W3·duel_arbitration] 把对撞层的张力改写成「哪边更合理」的仲裁问句。

    ★ 结果只作**仲裁材料** —— 不进 ing、不进对撞第三者（宪法级：未对齐合法）。
    """
    out: List[str] = []
    for t in (tensions or []):
        s = str(t).strip()
        if not s:
            continue
        out.append((s[:60] + " 哪个更合理？")[:160])
        if len(out) >= 2:
            break
    return out


def _meta_clean_queries(uncovered) -> List[str]:
    """[W3·meta_clean_check] 把元层的「未覆盖区间」改写成存在性问句。

    ★ 只用于 `uncovered` 核对；**不得**用于 deferred 的清算
      （宪法级：停止与清算分开 —— 见 `settle_deferrals` 的零调用断言）。
    """
    out: List[str] = []
    for u in (uncovered or []):
        s = str(u).strip()
        if not s:
            continue
        out.append(s[:100])
        if len(out) >= 2:
            break
    return out


_WEB_TIER_FALLBACK = 3


def _web_domain_of(url) -> str:
    """ 从 URL 取域名（小写、去 www.）。取不到返回 ""。"""
    _u = str(url or "").strip().lower()
    if not _u:
        return ""
    _u = _u.split("://", 1)[-1]
    _u = _u.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    _u = _u.split("@", 1)[-1].split(":", 1)[0]
    if _u.startswith("www."):
        _u = _u[4:]
    return _u.strip(".")


def _web_tier_proposal(results, cfg, known_domains=None) -> List[dict]:
    """ 给联网结果提「**建议** tier」，供**人工确认**。

    【为什么需要】W# 的 tier 现在一律是客户端给的初值 3（= 未知），
      而 `tier_floor` 是 2 —— 这批材料的 tier **没有任何信息量**。
      要让它有意义就得先回答「这条来自哪、算几档」；但**自动应用**比
      不判更危险（一条 tier=1 的二手转述能支撑 →decidable）。
      所以本版只做**提案**：写进待审队列，不进任何判定路径。

    【纯函数】不改入参、不读盘、不写盘（`known_domains` 由调用方给）。
      返回 `[{url, domain, proposed_tier, why, first_seen, confirmed}]`。
      ★ `first_seen=True` = 本跑首次见到该域名 ⇒ 一定进待审队列。
      ★ 返回的 tier **不会**被写回 `item["tier"]`（判据带变异体钉住）。
    """
    # ★ 同时接受「完整 config」与「config["web_search"] 子段」：两种写法
    #   都常见（`WebSearchGate(config)` 收完整、原先本函数收子段），只认一种
    #   会让另一种**静默**拿到空规则表 ⇒ 全部落回保守档 3。
    _cfg = cfg if isinstance(cfg, dict) else {}
    if isinstance(_cfg.get("web_search"), dict):
        _cfg = _cfg["web_search"]
    _rules = _cfg.get("domain_tier_rules") or []
    _known = {str(x) for x in (known_domains or ()) if str(x)}
    _seen = set()
    out: List[dict] = []
    for it in (results or []):
        _u = str((it or {}).get("url", "") or "")
        _d = _web_domain_of(_u)
        if not _d or _d in _seen:
            continue
        _seen.add(_d)
        _t = _WEB_TIER_FALLBACK
        _why = "未知域名 → 保守取 " + str(_WEB_TIER_FALLBACK)
        for _pair in _rules:
            try:
                _pat, _val = str(_pair[0]).lower(), int(_pair[1])
            except Exception:  # noqa: BLE001
                continue
            if _pat and _pat in _d:
                _t, _why = _val, "命中域名规则 " + _pat
                break
        out.append({"url": _u[:300], "domain": _d, "proposed_tier": _t,
                    "why": _why, "first_seen": _d not in _known,
                    "confirmed": False})
    return out


def _web_digest_block(results) -> str:
    """把 W# 渲染成**参照**段（不是内容）。空 → 空串（加性：不开时逐字不变）。"""
    _r = [x for x in (results or []) if str((x or {}).get("claim", "")).strip()]
    if not _r:
        return ""
    lines = ["",
             "【外部检索摘要】（★ **参照**，不是内容；不得当候选、"
             "不得据此改写问题）"]
    for x in _r[:6]:
        lines.append("- " + str(x.get("id", "W?")) + "（"
                     + str(x.get("stage", "")) + "，tier "
                     + str(x.get("tier_effective", x.get("tier", 3))) + "）："
                     + str(x.get("claim", ""))[:200])
    lines.append("★ 以上**不是**本层产物；只在判断「已知 / 未知」边界时参考。")
    return "\n".join(lines)


def _compute_rephrase_streak(view, state) -> int:
    """ 「本层连续几圈在复述」的唯一实现。

    ★ 收口前这行数在**两处**各写一份：
        · 串行 `_run_layer`：`max(meta_idle_streak, getattr(view, ...))`
        · 并行 `_b_check_stop`：`max(int(state[...]), int(getattr(view, ...)))`
      规则一样、代码两份 —— 本项目「同一条逻辑两条通道各写一份」的又一例。
      合并后这个符号在整个文件里**只有一个 def**（冒烟按 AST 数，不数字面串
      —— 文档里提到函数名会被字面串计数误当成定义，本项目踩过不止一次）。
    """
    _mi_from_view = getattr(view, "_meta_idle_streak", 0)
    _mi_state = int((state or {}).get("meta_idle_streak", 0) or 0)
    return max(_mi_state, int(_mi_from_view or 0))


def _anchor_enters_citation(anchor, cfg) -> bool:
    """ 该锚点是否够格进引用表（tier ≤ tier_floor）。

    tier 缺省 3；tier 小的更硬。让一条 tier=4 的二手转述去支撑
    →decidable，比「没有证据」更危险 —— 所以这里是**门**不是排序。
    """
    try:
        t = int((anchor or {}).get("tier", 3) or 3)
    except (TypeError, ValueError):
        t = 3
    return t <= _tier_floor(cfg)



def _hit_by_answers(aspect: str, answers) -> bool:
    """und_aspect 与锚点声明的 answers 逐条比（双向各查一次）。

    ★ 双向：短的一侧也可能是 aspect（如 aspect 只有「管网设计重现期」几字）。
    ★ 空 answers / None / 空串一律 False —— 调用点据此回落 claim 路径。
    """
    if not answers:
        return False
    s = str(aspect or "").strip()
    if not s:
        return False
    for a in answers:
        a = str(a or "").strip()
        if not a:
            continue
        if _overlap_coef(s, a) >= _UNTRACED_OVERLAP:
            return True
        # 反向也查一次（短 side 可能是 aspect）
        if _overlap_coef(a, s) >= _UNTRACED_OVERLAP:
            return True
    return False


def _hit_by_claim(aspect: str, claim: str) -> bool:
    """ 老路径，P2a 一字不动（阈值 0.6 也不许动）。

    ★ 保留它的意义：① 向后兼容（老锚点无 answers 时不崩）；
      ② 与 answers 路径**取 OR**，两条都能命中，不是替换关系。
    """
    return _similar(aspect, claim, 0.6)


def _citation_table(view, pool) -> List[tuple]:
    """把「可被证据引用的池对象」铺成 (引用号, 原句) 列表。

    编号沿用提示词里已有的约定，且与喂给模型时的编号一致：
      P#=探针  A#=& 印记  T#=悬空线头  S#=主动悬置  C#=候选  ing=对撞输出
      d_00X=未清偿的延迟债务（v1.21.61 起）
        ★ 债务编号**只能作为迁向不可判定的依据** —— 一条挂了 N 圈没动的
          账，证明的是"这一轮材料下拿不到答案"，证明不了"答案已找到"。
          硬约束在 `apply_decidability_change` 里。
    """
    out: List[tuple] = []
    for d in (getattr(pool, "deferrals", None) or []):
        if d.get("status") == "deferred":
            _rc = str(d.get("revisit_condition", ""))[:80]
            out.append((str(d.get("id", "")), _rc or str(d.get("reason", ""))))
    for i, p in enumerate((pool.probes or [])[:10]):
        out.append((f"P{i+1}", str(p.get("question", ""))))
    for i, a in enumerate((pool.amps or [])[:10]):
        out.append((f"A{i+1}", str(a.get("desc", ""))))
    for i, t in enumerate((pool.threads or [])[:10]):
        out.append((f"T{i+1}", str(t.get("desc", ""))))
    susp = [x for x in (pool.suspensions or [])
            if x.get("status") in ("active", "stable")][:10]
    for i, s in enumerate(susp):
        out.append((f"S{i+1}", str(s.get("target", ""))))
    if view is not None:
        for i, c in enumerate((view.candidates or [])[:15], 1):
            out.append((f"C{i}", str(c.get("desc", ""))))
        coll = str(getattr(view, "collision", "") or "")
        if coll and coll != "（此处未生）":
            out.append(("ing", coll))
    if getattr(pool, "anchor_as_evidence", False):
        _acfg = getattr(pool, "_anchor_cfg", None) or {}
        _xi = 0
        for _xa in (getattr(pool, "anchors", None) or []):
            if not _anchor_enters_citation(_xa, _acfg):
                continue
            _xi += 1
            out.append((f"X{_xi}", str(_xa.get("claim", ""))))
            if _xi >= 12:
                break
    if getattr(pool, "web_as_evidence", False):
        _wi = 0
        for _w in (getattr(pool, "web_results", None) or []):
            if not str((_w or {}).get("claim", "")).strip():
                continue
            if not _web_enters_citation(_w, getattr(pool, "_web_cfg", None)):
                continue
            _wi += 1
            out.append((str(_w.get("id") or ("W" + str(_wi))),
                        str(_w.get("claim", ""))[:120]))
            if _wi >= 20:
                break
    return [(c, t) for c, t in out if str(t).strip()]


def _resolve_citation(cite, view, pool) -> Optional[dict]:
    """解析一条证据引用 → {cite, resolved_to, score, text}；定位不到返回 None。

    ★ 这就是「有足够证据」的**确定性**校验：不问模型"你有没有证据"，
      只查它引用的东西**此刻是否真的在池里**。两种写法都收：
        编号（A2 / P1 / T3 / S1 / C4 / ing）或直接引原句（模糊匹配）。
    """
    c = str(cite or "").strip()
    if not c:
        return None
    table = _citation_table(view, pool)
    low = c.lower()
    for cid, text in table:
        if low == cid.lower():
            return {"cite": c, "resolved_to": cid, "score": 1.0,
                    "text": text[:80]}
    best = None
    for cid, text in table:
        if _similar(c, text, 0.6):
            return {"cite": c, "resolved_to": cid, "score": 0.8,
                    "text": text[:80]}
        s = _overlap_coef(c, text)
        if best is None or s > best[0]:
            best = (s, cid, text)
    if best is not None and best[0] >= 0.5:
        return {"cite": c, "resolved_to": best[1],
                "score": round(best[0], 2), "text": best[2][:80]}
    return None


def _reopen_closed_debt(pool, sq, sub_id, layer) -> str:
    """把「因分类变更被关掉」的债务**重新挂一笔**。返回新债务 id（没开则空串）。

    为什么需要它：`apply_decidability_change` 迁向 undecidable 时会顺手把该子
    问题名下的 deferred 关成 escalated（"不再欠了"）。可当判定又被推翻、转回
    decidable/partial 时，**"欠"这件事其实恢复了** —— 而债务账是唯一会被
    复确认 / 清偿 / 终局清算 / 反躺平盯住的地方（`_probe_research` 的
    open_def、`deferred_ratio_of`、`_settle_research` 都只看 status=="deferred"）。
    没这笔账，它就只是"分母里的一个未答项"，不会被追。

    ★ 三条自我约束：
      1. **只对确实被关过账的子问题开**（存在 escalated 记录）——本来就没欠过
         账的子问题开新账等于给债务账灌水。
      2. **新开一笔，不复活旧条**：旧那条"当时确实升级了"是历史事实，
         改它的 `resolved_at`/`resolution_reason` 就是篡改记录。
      3. `revisit_condition` **原样归还**（它当初通过了 `_valid_revisit`，
         仍然是我们说好的回访条件）；本次重挂的原因另记在 `reason`。
    """
    if any(d.get("sub_id") == sub_id and d.get("status") == "deferred"
           for d in pool.deferrals):
        return ""                      # 已经有在挂的账，不重复
    closed = [d for d in pool.deferrals
              if d.get("sub_id") == sub_id
              and d.get("status") == "escalated"]
    if not closed:
        return ""                      # 本来就没欠过 → 不凭空开
    prev = closed[-1]
    new_id = f"d_{len(pool.deferrals) + 1:03d}"
    pool.deferrals.append({
        "id": new_id,
        "sub_id": sub_id,
        "sub_question": str(sq.get("question", ""))[:200],
        "reason": (f"分类变更被推翻，原债务（{prev.get('id')}）重新挂账："
                   f"该子问题重新可判定，欠的账也回来了")[:200],
        "revisit_condition": str(prev.get("revisit_condition", ""))[:120],
        "layer": layer,
        "last_reconfirmed_layer": layer,
        "status": "deferred",
        "resolved_at": None,
        "resolution_reason": "",
        "reopened_from": prev.get("id"),
    })
    return new_id


def apply_decidability_change(pool, view, sub_by_id, sub_id, to, layer,
                              reason, evidence, by: str = "研究层") -> dict:
    """可判定性变更的**唯一入口**（三态互转；每条都要证据）。

    变更账 append-only 记在 `pool.decidability_log`，被驳回的也记
    （status=rejected + why）——本项目的老规矩：失败必须留痕。
    """
    ent = {"sub_id": sub_id, "layer": layer, "to": str(to).strip().lower(),
           "reason": str(reason or "")[:200], "by": by,
           "evidence": [], "status": "rejected", "why": "", "logged": False}

    def _reject(why: str) -> dict:
        ent["why"] = why
        ent["logged"] = True
        pool.decidability_log.append(ent)
        return ent

    sq = sub_by_id.get(sub_id)
    if sq is None:
        return _reject("池里没有这个子问题编号")
    if ent["to"] not in _DECIDABILITY_STATES:
        return _reject(f"目标态非法：{ent['to']!r}")
    frm = str(sq.get("decidability", "decidable")).strip().lower()
    ent["from"] = frm
    if frm == ent["to"]:
        ent["why"] = "与当前判定相同，无需变更"
        return ent                      # 不记账：纯噪声
    evs = evidence if isinstance(evidence, list) else [evidence]
    evs = [x for x in (evs or []) if str(x).strip()]
    if not evs:
        return _reject("没有给证据（至少要一条能定位到池中对象的引用）")
    resolved, dangling = [], []
    for ev in evs:
        r = _resolve_citation(ev, view, pool)
        (resolved if r else dangling).append(r or str(ev)[:60])
    ent["evidence"] = resolved
    if not resolved:
        return _reject(f"证据在池中定位不到：{dangling[:3]}")
    # ★ 债务编号是"拿不到答案"的证据，不是"找到答案"的证据 ——
    #   拿它去支撑 →decidable / →partial 等于把欠账当成产出。
    if ent["to"] != "undecidable" and all(
            str(r.get("resolved_to", "")).startswith("d_")
            for r in resolved):
        return _reject("债务编号只能作为迁向不可判定的依据，"
                       f"不能用来支撑 →{ent['to']}")
    if ent["to"] != "partial" and all(
            str(r.get("resolved_to", "")).startswith("W")
            for r in resolved):
        return _reject("联网编号（W#）只能支撑 →partial，不能支撑 "
                       f"→{ent['to']}（网络检索质量不稳；"
                       "且「能查到」证明不了「答不出」）")
    ent["status"] = "applied"
    ent["logged"] = True
    ent["dangling"] = dangling
    sq["decidability"] = ent["to"]
    pool.decidability_log.append(ent)
    # 迁向不可判定时，账要连着挪：该 sub 名下 deferred 一并关成 escalated。
    # ★ 蓝图 §二 原文写「立刻挪、**单向（不可逆）**」——那句**已被推翻**
    #   （用户 2026-09-30 定案「应该是双向的」，见 docs/三层递归蓝图.md §二
    #   的更新块）。所以这里只保留**账链**（挪债务），方向本身是双向的：
    #   转回 decidable/partial 时由 _reopen_closed_debt 重新挂一笔。
    if ent["to"] == "undecidable":
        pool.escalations.append({
            "sub_id": sub_id, "question": sq.get("question", ""),
            "from": frm, "to": "undecidable", "layer": layer,
            "reason": ent["reason"],
            "evidence": [e["resolved_to"] for e in resolved],
            "note": "迁向不可判定（三态可转·须证据）",
        })
        for d in pool.deferrals:
            if d.get("sub_id") == sub_id and d.get("status") == "deferred":
                d["status"] = "escalated"
                d["resolved_at"] = layer
                d["resolution_reason"] = "因分类变更（可判定性转移）"
    if frm == "undecidable" and ent["to"] in _DEC_ANSWERABLE:
        ent["reopened_debt"] = _reopen_closed_debt(pool, sq, sub_id, layer)
    return ent


def _starve_escalation(pool, view, sub_by_id, layer: int, cfg: dict,
                       stats: dict):
    """ 反向触发点：连续 N 圈无进展 → 迁向不可判定。

    ★ 为什么必须有它：三态在真跑里是**单向漂移**的。40 份日志里
      reclass 成立 18 次，方向只有 und→partial 与 dec→partial，
      **没有一条 partial→und** —— 于是 escalation 恒为 0，而复债只在
      「曾被 escalation 关过账」时才能开，所以复债也恒为 0。
      两个 0 不是两处独立的失灵，是同一条断链的两端。

    ★ 三条自我约束（防它变成"又一个 0 触发机制"或"乱判不可判定"）：
      1. 只认**挂着的账**当证据 —— 没有未清偿债务就不动手。一条挂了
         N 圈没动的账，证明的是"这一轮材料下拿不到答案"，不是"答案找到了"
         （所以债务编号硬约束为只能支撑 →undecidable）。
      2. 本圈有任何进展（被回答 / 挂新账 / 复确认 / 清偿 / 分类变更）
         就**清零计数**，不是累加。
      3. 三态仍然**双向**：迁走之后若又被救回，复债会把账重新挂上
         （见 `_reopen_closed_debt`），不是一去不回。
    """
    sp = (cfg or {}).get("spiral", {}) or {}
    _n = int(sp.get("escalate_starve_rounds", 2) or 0)
    if _n <= 0:
        return

    touched = set()
    for e in (view.engagements or []):
        touched.add(e.get("sub_id"))
    for e in (view.escalations or []):
        touched.add(e.get("sub_id"))
    for e in (getattr(view, "reclassifications", None) or []):
        touched.add(e.get("sub_id"))
    for d in (view.deferrals or []):
        touched.add(d.get("sub_id"))
    _d2s = {d.get("id"): d.get("sub_id")
            for d in (pool.deferrals or [])}
    # ★ 复确认**不算进展**。它说的是"这笔账还在、我还是拿不到东西"，
    #   把它当进展会直接把这个触发点废掉 —— 真跑 v61a 里研究层每圈
    #   都在「确认3」，六个子问题一圈不落，于是计数永远清零，一次都没够到。
    for r in (view.resolutions or []):
        touched.add(_d2s.get(r.get("deferral_id")))

    def _set_starve(_sq, _val):
        _sq["_starve_rounds"] = _val
        #   ★ 峰值**无条件写**（不是只在抬升时写）：字段存在与否被下游
        #     当作「机制到底跑没跑」的自检依据；只在抬升时写，会让
        #     「跑过但一直是 0」与「压根没跑」长得一模一样 ——
        #     首次真跑 G1q 就撞出了这个混淆（覆盖计数报了 1/6）。
        _pk = int(_sq.get("_starve_max_seen", 0) or 0)
        _sq["_starve_max_seen"] = _val if _val > _pk else _pk

    for sq in pool.sub_questions:
        sid = sq.get("id")
        if (sq.get("status") == "answered"
                or sq.get("decidability") == "undecidable"
                or sid in touched):
            _set_starve(sq, 0)
            continue
        _set_starve(sq, int(sq.get("_starve_rounds", 0) or 0) + 1)
        if sq["_starve_rounds"] < _n:
            continue
        _debts = [str(d.get("id"))
                  for d in (pool.deferrals or [])
                  if d.get("sub_id") == sid and d.get("status") == "deferred"]
        if not _debts:
            continue          # 没有挂着的账 = 没有可定位的证据，不硬造
        _set_starve(sq, 0)
        ent = apply_decidability_change(
            pool, view, sub_by_id, sid, "undecidable", layer,
            f"连续 {_n} 圈无进展且名下有未清偿债务（{'、'.join(_debts[:3])}"
            f" 挂起未动），本轮材料下判不出",
            _debts[:3], by="研究层·无进展迁向不可判定")
        if ent["status"] == "applied":
            stats["reclassified"] += 1
            stats["escalated"] += 1
        elif ent["logged"]:
            stats["rejected"] += 1
        if ent["logged"]:
            stats["_transitions"].append(ent)


def update_deferrals(pool, view, layer: int, cfg: dict,
                     web_hook=None) -> dict:
    """研究层延迟债务更新 + refinement 记录。"""
    stats = {"new": 0, "confirmed": 0, "handled": 0,
             "escalated": 0, "answered": 0, "invalid": 0,
             "refined": 0, "reclassified": 0, "rejected": 0,
             "_transitions": []}
    sub_by_id = {s.get("id"): s for s in pool.sub_questions}

    props: List[dict] = []
    for e in (view.escalations or []):
        props.append({"sub_id": e.get("sub_id"), "to": "undecidable",
                      "reason": e.get("reason", ""),
                      "evidence": e.get("evidence")})
    for e in (getattr(view, "reclassifications", None) or []):
        props.append({"sub_id": e.get("sub_id"), "to": e.get("to", ""),
                      "reason": e.get("reason", ""),
                      "evidence": e.get("evidence")})
    for pr in props:
        try:
            sid = int(pr["sub_id"])
        except (TypeError, ValueError):
            continue
        if web_hook is not None:
            try:
                _pr2 = dict(pr)
                _pr2["_sq_text"] = str(
                    (sub_by_id.get(sid) or {}).get("question", ""))
                web_hook(_pr2, layer)
            except Exception as _ew:  # noqa: BLE001
                logger_web.warning("[W-HOOK] %s", _ew)
        ent = apply_decidability_change(
            pool, view, sub_by_id, sid, pr["to"], layer,
            pr["reason"], pr["evidence"])
        if ent["status"] == "applied":
            stats["reclassified"] += 1
            if ent["to"] == "undecidable":
                stats["escalated"] += 1
        elif ent["logged"]:
            stats["rejected"] += 1
        if ent["logged"]:
            stats["_transitions"].append(ent)

    _p16_log_limit = 20
    _p16_logged = 0

    for d in (view.deferrals or []):
        sid = d.get("sub_id")
        sq = sub_by_id.get(sid)
        if sq is None:
            continue
        cond = str(d.get("revisit_condition", "")).strip()
        if not _valid_revisit(cond):
            stats["invalid"] += 1
            if _p16_logged < _p16_log_limit:
                _p16_logged += 1
                _note = (f"deferral 被拦（revisit_condition 不合格）："
                         f"子问题[{sid}] 条件={cond[:60]!r}")
                view.errors.append(_note)
                pool.meta.append(f"[P1-6] {_note}")
            continue
        reason = str(d.get("reason", "")).strip()
        if len(reason) < 4:
            stats["invalid"] += 1
            if _p16_logged < _p16_log_limit:
                _p16_logged += 1
                _note = (f"deferral 被拦（reason 太短）："
                         f"子问题[{sid}] reason={reason[:40]!r}")
                view.errors.append(_note)
                pool.meta.append(f"[P1-6] {_note}")
            continue
        if any(x.get("sub_id") == sid and x.get("status") == "deferred"
               for x in pool.deferrals):
            continue
        pool.deferrals.append({
            "id": f"d_{len(pool.deferrals) + 1:03d}",
            "sub_id": sid,
            "sub_question": sq.get("question", "")[:200],
            "reason": str(d.get("reason", ""))[:200],
            "revisit_condition": cond[:120],
            "layer": layer,
            "last_reconfirmed_layer": layer,
            "status": "deferred",
            "resolved_at": None,
            "resolution_reason": "",
        })
        stats["new"] += 1

    ok = {str(r.get("deferral_id", "")) for r in (view.reconfirmations or [])}
    for x in pool.deferrals:
        if x["status"] == "deferred" and x["id"] in ok:
            x["last_reconfirmed_layer"] = layer
            stats["confirmed"] += 1

    done = {str(r.get("deferral_id", "")): str(r.get("how", "")).strip()
            for r in (view.resolutions or [])}
    for x in pool.deferrals:
        if x["status"] == "deferred" and x["id"] in done:
            x["status"] = "handled"
            x["resolved_at"] = layer
            x["resolution_reason"] = done[x["id"]] or "已清偿"
            stats["handled"] += 1

    for e in (view.engagements or []):
        sid = e.get("sub_id")
        sq = sub_by_id.get(sid)
        if sq is None:
            continue
        if sq.get("status") != "answered":
            sq["status"] = "answered"
            sq["answered_at_layer"] = layer
            try:
                depth = float(e.get("depth", 1.0))
            except (TypeError, ValueError):
                depth = 1.0
            sq["depth"] = max(0.0, min(1.0, depth))
            stats["answered"] += 1
        else:
            how = str(e.get("how", "")).strip()[:160]
            if how:
                dup = any(
                    r.get("sub_id") == sid
                    and _similar(r.get("how", ""), how, 0.85)
                    for r in pool.refinements)
                if not dup:
                    pool.refinements.append({
                        "sub_id": sid,
                        "sub_question": sq.get("question", "")[:200],
                        "how": how,
                        "layer": layer,
                    })
                    stats["refined"] += 1
                    try:
                        rd = float(e.get("depth", 0.0))
                    except (TypeError, ValueError):
                        rd = 0.0
                    if rd > 0:
                        cur = float(sq.get("depth", 1.0))
                        sq["depth"] = max(0.0, min(1.0, cur + rd))
        for x in pool.deferrals:
            if x.get("sub_id") == sid and x["status"] == "deferred":
                x["status"] = "handled"
                x["resolved_at"] = layer
                x["resolution_reason"] = "对应子问题被直接回答"
                stats["handled"] += 1

    if stats["invalid"] > 0 and _p16_logged >= _p16_log_limit:
        pool.meta.append(
            f"[P1-6] 本层 deferral 被拦共 {stats['invalid']} 条，"
            f"仅前 {_p16_log_limit} 条写入 view.errors；"
            f"完整清单见 stats['invalid']")

    _starve_escalation(pool, view, sub_by_id, layer, cfg, stats)
    return stats


def settle_deferrals(pool, layer: int) -> dict:
    left = [d for d in pool.deferrals if d["status"] == "deferred"]
    for d in left:
        d["status"] = "dropped"
        d["resolved_at"] = layer
        d["resolution_reason"] = "研究停止时未清算（终局清算兜底）"
    return {"clean": not left, "leftover": len(left)}


# ============================================================
# 对撞层：悬置张力
# ============================================================
DUEL_QUADRANT = {
    "both":   "① 都碰",
    "rhythm": "② 修行碰·研究拖",
    "stance": "③ 修行悬置·研究碰",
    "nature": "④ 都不碰",
}
_QUADRANT_ORDER = ("stance", "nature", "rhythm", "both")


def _aspect_match(a: str, b: str, cfg: Optional[dict] = None) -> float:
    """修行层的一个 target 和研究层的一个 question 讲的是不是同一件事。

    [v1.21.56 自查] 原来只有 `_similar(pt, rt, 0.7)` 一条判据。_similar 用
    关键词集合、**分母取 max(len(a), len(b))**。修行层的 target 是
    「T6 判定权归属」这种短题，研究层的是「AI是否应被视为与人对等的互动
    主体，这一判断在现有哲学和法学框架下能否达成共识？」这种长句——
    两边关键词数量差一个量级，比值永远到不了 0.7。

    实测 10 份产物（4 个不同问题）四象限匹配率全是 0%。那不是「未对齐
    合法」，是这条通道从来没亮过。这里补一条**包含度**判据：短的那侧
    有多少关键词落在长的那侧里。未对齐仍然是合法结果，只是现在它
    「有可能」对上。
    """
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return 0.0
    thr = float((cfg or {}).get("alignment_similarity", 0.7))
    contain_thr = float((cfg or {}).get("alignment_containment", 0.6))
    if _similar(a, b, thr):
        return 1.0
    ka, kb = _kw(a), _kw(b)
    if not ka or not kb:
        return 0.0
    short, long_s = (ka, kb) if len(ka) <= len(kb) else (kb, ka)
    cov = len(short & long_s) / max(len(short), 1)
    return cov if cov >= contain_thr else 0.0


def _align_suspensions_and_deferrals(practice_pool, research_pool,
                                     cfg: Optional[dict] = None) -> dict:
    """四象限对齐（未对齐是合法结果）。"""
    practice_susp = [s for s in practice_pool.suspensions
                     if s.get("status") in ("active", "stable", "resolved")]
    practice_eng = list(practice_pool.engagements)
    research_def = list(research_pool.deferrals)
    research_answered = [s for s in research_pool.sub_questions
                         if s.get("status") == "answered"]

    p_aspects = [(str(s.get("target", "")).strip(), "悬置")
                 for s in practice_susp] + \
                [(str(e.get("target", "")).strip(), "碰")
                 for e in practice_eng]
    r_aspects = [(str(d.get("sub_question", "")).strip(), "拖")
                 for d in research_def] + \
                [(str(s.get("question", "")).strip(), "碰")
                 for s in research_answered]

    quadrants = []
    used_r = set()
    _best = 0.0
    for pt, pd in p_aspects:
        if not pt:
            continue
        _best_i = -1
        _best_s = 0.0
        for i, (rt, rd) in enumerate(r_aspects):
            if i in used_r or not rt:
                continue
            _s = _aspect_match(pt, rt, cfg)
            if _s > _best_s:
                _best_s, _best_i = _s, i
            if _s:
                break
        if _best_s > _best:
            _best = _best_s
        if _best_i >= 0 and _best_s > 0:
            i, rt, rd = _best_i, r_aspects[_best_i][0], r_aspects[_best_i][1]
            used_r.add(i)
            if pd == "碰" and rd == "碰":
                q = "both"
            elif pd == "碰" and rd == "拖":
                q = "rhythm"
            elif pd == "悬置" and rd == "碰":
                q = "stance"
            else:
                q = "nature"
            quadrants.append({
                "aspect": pt[:120],
                "quadrant": q,
                "practice": pd,
                "research": rd,
                "practice_target": pt[:120],
                "research_target": rt[:120],
                "score": round(_best_s, 3),
            })

    p_n = len([1 for pt, _ in p_aspects if pt])
    r_n = len([1 for rt, _ in r_aspects if rt])
    denom = max(p_n, r_n, 1)
    match_rate = len(quadrants) / denom

    if match_rate < _ALIGN_MATCH_LO:
        quality = "unaligned"
    elif match_rate < _ALIGN_MATCH_OK:
        quality = "low"
    else:
        quality = "ok"

    quadrants.sort(key=lambda x: _QUADRANT_ORDER.index(x["quadrant"]))

    return {"quality": quality, "match_rate": round(match_rate, 3),
            "quadrants": quadrants,
            "practice_n": p_n, "research_n": r_n,
            "best_score": round(_best, 3)}


def _quadrant_text(alignment: dict) -> str:
    if not alignment or alignment.get("consumed"):
        return ""
    quadrants = alignment.get("quadrants", [])
    if not quadrants:
        return ""
    text = "\n".join(
        f"  - [{DUEL_QUADRANT.get(q['quadrant'], '?')}] {q['aspect']}"
        f"（修行{q['practice']} · 研究{q['research']}）"
        for q in quadrants)
    if alignment.get("quality") in ("unaligned", "failed"):
        text = ("（四象限未对齐：两侧没有同一件事可对（不是故障，是两种判断）"
                "——直接做纯语义对撞，不硬凑假分歧）\n" + text)
    return text


def update_duel_suspensions(pool, view, layer: int, cfg: dict) -> dict:
    """对撞层张力悬置更新。"""
    stats = {"new": 0, "confirmed": 0, "revoked": 0,
             "resolved": 0, "stable": 0, "adjudicated": 0,
             "self_resolved": 0}
    need = int(cfg.get("stable_layers", 3))

    for s in (view.duel_suspensions or []):
        target = str(s.get("tension", "")).strip()
        if not target or len(target) < 4:
            continue
        if any(_similar(target, x.get("target", ""), 0.85)
               and x.get("status") in ("active", "stable")
               for x in pool.duel_suspensions):
            continue
        rt = str(s.get("reason_type", "explicit")).lower()
        if rt not in SUSPENSION_REASON_TYPES:
            rt = "explicit"
        q = str(s.get("quadrant", "")).strip()
        if q not in ("①", "②", "③", "④"):
            q = ""
        pool.duel_suspensions.append({
            "id": f"t_{len(pool.duel_suspensions) + 1:03d}",
            "target": target[:200],
            "reason": str(s.get("reason", ""))[:200],
            "reason_type": rt,
            "quadrant": q,
            "layer": layer,
            "last_confirmed_layer": layer,
            "confirmed_layers": [layer],
            "status": "active",
            "revoked_at": None,
            "revoke_reason": "",
            "resolved_at": None,
            "stable_since": None,
            "needs_review": False,
        })
        stats["new"] += 1

    ok_ids = {str(r.get("suspension_id", ""))
              for r in (view.reconfirmations or [])}
    for x in pool.duel_suspensions:
        if x["status"] in ("active", "stable") and x["id"] in ok_ids:
            x["last_confirmed_layer"] = layer
            cl = x.setdefault("confirmed_layers", [])
            if layer not in cl:
                cl.append(layer)
            stats["confirmed"] += 1

    for r in (view.revocations or []):
        sid = str(r.get("suspension_id", ""))
        tgt = str(r.get("target", ""))
        for x in pool.duel_suspensions:
            if x["status"] not in ("active", "stable"):
                continue
            if x["id"] == sid or (tgt and _similar(x["target"], tgt, _DUP_SIM)):
                x["status"] = "revoked"
                x["revoked_at"] = layer
                x["revoke_reason"] = str(r.get("reason", ""))[:200]
                stats["revoked"] += 1

    adj = [str(a.get("tension", "")) for a in (view.adjudications or [])]
    for x in pool.duel_suspensions:
        if x["status"] not in ("active", "stable"):
            continue
        if any(_similar(x["target"], a, _SUSP_SAME_SIM) for a in adj if a):
            x["status"] = "resolved"
            x["resolved_at"] = layer
            stats["resolved"] += 1
            if x.get("layer") == layer:
                stats["self_resolved"] += 1

    stats["stable"] = _turn_stable(pool.duel_suspensions, layer, cfg)

    for x in pool.duel_suspensions:
        if x["status"] == "active" and (layer - x["last_confirmed_layer"]) >= need:
            x["needs_review"] = True

    stats["adjudicated"] = len(view.adjudications or [])
    return stats


# ============================================================
# both 比例后处理
# ============================================================
def _tighten_both(cands: List[dict],
                  max_ratio: float = 0.3) -> List[dict]:
    """both 超过阈值时按 why_0 / why_1 长度对称性重新分配。"""
    if not cands:
        return cands
    both_idx = [i for i, e in enumerate(cands)
                if e.get("position") == "both"]
    if not both_idx:
        return cands
    max_both = max(1, int(len(cands) * max_ratio))
    if len(both_idx) <= max_both:
        return cands

    def sym(e: dict) -> float:
        # [B3] 原来只用 min/max 长度比 —— 模型把两侧写成长度相近的空话
        # 就能刷满"对称性"。改成内容不重合度为主、长度比为辅，并加
        # 最短长度门槛：任意一侧过短就没有实质论证，谈不上两面成立。
        w0 = (e.get("why_0", "") or "").strip()
        w1 = (e.get("why_1", "") or "").strip()
        if not w0 or not w1:
            return 0.0
        if min(len(w0), len(w1)) < 12:
            return 0.0
        overlap = _overlap_coef(w0, w1, _KW_TOP_N)
        ratio = min(len(w0), len(w1)) / max(len(w0), len(w1), 1)
        return (1.0 - overlap) * (0.5 + 0.5 * ratio)

    scored = [(sym(cands[i]), i) for i in both_idx]
    scored.sort(key=lambda x: -x[0])
    keep = {i for _, i in scored[:max_both]}
    for i in both_idx:
        if i in keep:
            continue
        e = cands[i]
        w0 = e.get("why_0", "") or ""
        w1 = e.get("why_1", "") or ""
        if len(w0) > len(w1):
            e["position"] = "0"
        elif len(w1) > len(w0):
            e["position"] = "1"
        else:
            e["position"] = "0"
    logger.info("both 收紧：%d → %d（上限 %d）",
                len(both_idx), max_both, max_both)
    return cands


# ============================================================
# 双通道追踪器
# ============================================================
class ChannelTracker:
    def __init__(self, name: str, min_stall_limit: int = 2,
                 min_distance_improvement: float = 0.03):
        self.name = name
        self.min_stall_limit = min_stall_limit
        self.min_improvement = min_distance_improvement
        self.stall_streak = 0
        self.last_qdist = 1.0
        self.converged = False
        self.converged_layer: Optional[int] = None
        self.qdist_history: List[float] = []
        self.coverage_history: List[float] = []
        self.structural_history: List[List[str]] = []
        self.und_clarity_history: List[float] = []
        self.needs_recheck: bool = False

    def update_decidable(self, coverage_ratio: float,
                         answered_count: int) -> dict:
        qdist = max(0.0, min(1.0, 1.0 - coverage_ratio))
        improvement = self.last_qdist - qdist
        if improvement < self.min_improvement and len(self.qdist_history) >= 1:
            self.stall_streak += 1
        else:
            self.stall_streak = 0
        self.last_qdist = qdist
        self.qdist_history.append(qdist)
        self.coverage_history.append(coverage_ratio)
        return {"qdist": qdist, "improvement": improvement,
                "stall_streak": self.stall_streak}

    def note_rebaseline(self, coverage_ratio: float) -> None:
        """ 分母变了（可判定性发生转移），比值不可比。

        只把基线挪到新值并记录，**不**计入停滞也不计入改善。
        否则「新挂上一条可判定子问题」会被误判成停滞，
        「把一条改成不可判定」会被误判成进步。
        """
        qdist = max(0.0, min(1.0, 1.0 - coverage_ratio))
        self.last_qdist = qdist
        self.stall_streak = 0
        self.qdist_history.append(qdist)
        self.coverage_history.append(coverage_ratio)

    def update_undecidable(self, structural_amps: List[str],
                           clarity: float,
                           structural_coverage: Optional[float] = None) -> dict:
        qdist = max(0.0, min(1.0, 1.0 - clarity))
        improvement = self.last_qdist - qdist
        if improvement < self.min_improvement and len(self.qdist_history) >= 1:
            self.stall_streak += 1
        else:
            self.stall_streak = 0
        self.last_qdist = qdist
        self.qdist_history.append(qdist)
        self.structural_history.append(list(structural_amps))
        self.und_clarity_history.append(clarity)
        if self.converged:
            if (not structural_amps
                    and len(self.und_clarity_history) >= 2
                    and self.und_clarity_history[-1]
                    < self.und_clarity_history[-2]):
                self.needs_recheck = True
            elif structural_amps:
                self.needs_recheck = False
        return {"qdist": qdist, "improvement": improvement,
                "stall_streak": self.stall_streak,
                "structural_coverage": structural_coverage,
                "needs_recheck": self.needs_recheck}

    def is_stalled(self) -> bool:
        return self.stall_streak >= self.min_stall_limit

    def mark_converged(self, layer: int):
        self.converged = True
        self.converged_layer = layer

    def get_state(self) -> dict:
        return {
            "name": self.name,
            "stall_streak": self.stall_streak,
            "last_qdist": self.last_qdist,
            "converged": self.converged,
            "converged_layer": self.converged_layer,
            "qdist_history": list(self.qdist_history),
            "needs_recheck": self.needs_recheck,
        }


# ============================================================
# 数据结构
# ============================================================
@dataclass
class Candidate:
    desc: str
    kind: str = "concept"
    attribute: str = "0"
    position: str = "0"
    yin: str = "0"
    yang: str = "0"
    source: str = ""
    attribute_anchored: bool = False
    why_attribute: str = ""
    why_position: str = ""
    why_0: str = ""
    why_1: str = ""

    @property
    def is_amp_candidate(self) -> bool:
        if self.position == "both":
            return False
        return self.attribute != self.position

    @property
    def amp_kind(self) -> str:
        if self.attribute != self.position:
            return "attr_pos"
        return ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_amp_candidate"] = self.is_amp_candidate
        return d


@dataclass
class Amp:
    desc: str
    type: str = "ontological"
    source: str = ""


@dataclass
class Thread:
    desc: str
    kind: str = "thread"


@dataclass
class Probe:
    question: str
    link: str = ""
    expected_gain: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class View:
    entry: str
    anchor: str = ""
    candidates: List[dict] = field(default_factory=list)
    collision: str = ""
    amps: List[dict] = field(default_factory=list)
    threads: List[dict] = field(default_factory=list)
    probes: List[dict] = field(default_factory=list)
    meta: List[str] = field(default_factory=list)

    decidable_product: dict = field(default_factory=dict)
    undecidable_product: dict = field(default_factory=dict)
    distance_to_question: Optional[float] = None
    covered_aspects: List[str] = field(default_factory=list)
    uncovered_aspects: List[str] = field(default_factory=list)

    untouched: List[dict] = field(default_factory=list)
    suspensions: List[dict] = field(default_factory=list)
    engagements: List[dict] = field(default_factory=list)
    refinements: List[dict] = field(default_factory=list)
    reconfirmations: List[dict] = field(default_factory=list)
    revocations: List[dict] = field(default_factory=list)
    deferrals: List[dict] = field(default_factory=list)
    resolutions: List[dict] = field(default_factory=list)
    escalations: List[dict] = field(default_factory=list)
    reclassifications: List[dict] = field(default_factory=list)
    settlement: dict = field(default_factory=dict)
    adjudications: List[dict] = field(default_factory=list)
    both_quota: dict = field(default_factory=dict)  # [P1-4]
    carry: List[dict] = field(default_factory=list)  # [P1-5]
    carry_check: dict = field(default_factory=dict)   # [P2-7] 回流是否生效的核对
    carry_checks: List[dict] = field(default_factory=list)
    carry_dropped: List[dict] = field(
        default_factory=list)  # [P2-9] 硬拦下的重现候选
    carry_dropped_all: List[dict] = field(default_factory=list)
    rephrase_ratio: Optional[float] = None
    probe_skipped: bool = False
    rounds_cap: int = 0           # [P2-9] 这一层实际允许的圈数上限
    duel_suspensions: List[dict] = field(default_factory=list)
    meta_closure: dict = field(default_factory=dict)
    stop_reason: str = ""
    rounds_run: int = 0
    roles_run: List[str] = field(default_factory=list)
    closure_reason: str = ""
    round_log: List[dict] = field(default_factory=list)
    rehashed: List[dict] = field(default_factory=list)
    idle: bool = False
    rendered: str = ""
    manifest: str = ""

    # ── [LDG 层职责守卫] 停止/收敛处的职责读数（读数不是分数）──
    #: `{C, R, S, missing_core, core_total, short, ...}`；空 dict = 未测。
    duty: dict = field(default_factory=dict)
    #: 逐圈 trace：`[{round, S, C, R}]` —— 边际增益判据读它。
    duty_trace: List[dict] = field(default_factory=list)
    # ★ [四层目标] 逐圈目标读数序列（与 `duty_trace` 同构）。停因判据读它
    #   （连续不涨 = 该层目标不再推进）。
    goal_trace: List[dict] = field(default_factory=list)
    # ★ [第六期] 各环节量化读数（零成本、纯函数产出；缺输入 ⇒ 不出键）。
    quant_readings: Dict[str, dict] = field(default_factory=dict)
    #: [LDG] 职责判定行 —— **与停止理由分开**（红线「停止与清算分开」）：
    #:   停止理由答「为什么停」，职责判定答「这层替问题干了什么」。
    #:   渲染时两者同屏，读者不会只看到「自然安住」。
    duty_verdict: str = ""
    # ★ [四层目标] 本层目标达成读数的**独立**判定行（与 duty_verdict 并列，
    #   不合并 —— 两路信号问的不是同一件事）。
    goal_verdict: str = ""
    #: [停因级联] 主因（最高优先级的那条）—— ★ 不变量：它必须出现在
    #:   `stop_reason` 里（报告的原因不能是「没触发的那个」）。
    stop_primary: str = ""
    #: [截断两向记账] 省了多少圈 / 丢了几个 core 问项（**两面分开报**）。
    cut_two_way: dict = field(default_factory=dict)
    #: [发散三态 / 回滚指针] 收敛/停滞/发散 + 历史最佳圈的指针。
    #:   ★ 指针只是**指向**：被回滚掉的圈不删（红线「失败留痕」）。
    divergence: dict = field(default_factory=dict)
    best_round: Optional[int] = None
    #: [anytime-valid] 均值下界（随时看随时停仍然有效的判据）。
    anytime: dict = field(default_factory=dict)
    #: [CSD 早期预警] 逐圈序列的方差/AC1 读数（**只作读数**）。
    csd: dict = field(default_factory=dict)
    #: 补救圈是否已用（每层最多用 `_DUTY_REMEDY_ROUNDS` 次）。
    duty_remedy_used: int = 0
    #: 交付面占全文比重（0-1；由渲染层回填）。
    delivery_share: Optional[float] = None

    quality_flags: List[str] = field(default_factory=list)
    quality_verdict: str = ""
    self_check: dict = field(default_factory=dict)

    errors: List[str] = field(default_factory=list)
    anchor_touched: List[dict] = field(default_factory=list)
    ing_structured: dict = field(default_factory=dict)
    # [A1 方面单元] 方面单元：锚点两半 + judge 侧未触及的**统一登记**。
    # ★ 与 untouched / anchor_touched **双写**，不是替换：
    #   旧键是历史 packed 的口径，删了会让下游读数从「作证据」
    #   静默降级成「读不到」。
    aspect_units: List[dict] = field(default_factory=list)
    #: [层目标 / Heaps 饱和] 逐圈**累计层面数**（逐圈序列，不是终值）。
    aspect_hist: List[int] = field(default_factory=list)
    #: [层目标 / 对撞] 本层的**上游层数**（融合率的分母）。0 = 未记。
    upstream_layers: int = 0
    #: [层目标 / CORE 停滞罚] 上游 view 的 manifest/collision 文本（比对语料）。
    upstream_texts: List[str] = field(default_factory=list)
    #: [层目标 / CORE] 语义停滞率 0-1（1 = 全复读上游）。None = 未算。
    sem_stagnation: Optional[float] = None
    # [D1 信念条目] 信念条目（带状态/证据/熵），与 structural_amps 双写。
    # ★ `structural_amps`（字符串列表）**继续写**：它是历史 packed 的
    #   口径，删了会让下游读数从「作证据」静默降级成「读不到」。
    belief_items: List[dict] = field(default_factory=list)

    # ── [A3 双读数] 双读数：**永不合成一个分**（红线「未对齐合法」）──
    @property
    def touch_rate(self) -> Optional[float]:
        """能力读数：本层有「触及」的圈数 / 实际跑的圈数。

        ★ 这不是「分数」，是**覆盖率观测**：未触达 ≠ 失败（红线）。
        ★ 兜底口径写清楚：`round_log` 有就用它按圈判；没有就退回
          「anchor_touched 非空 ⇒ 1.0」这个**一次性**观测。
          ★ 兜底分支**不假装**是逐圈读数（它只答「有没有发生过」）。
        """
        _rl = getattr(self, "round_log", None) or []
        # ★ 逐圈口径的**前提**：round_log 里真的记了 `anchor_touched_n`。
        #   它现在只是「回填占位」（键在 dump 后补）——若直接进逐圈分支，
        #   即使 `anchor_touched` 非空，读数也恒 0.0（口径错位，真 bug）。
        #   ⇒ 只有**该键确实出现过**才走逐圈；否则退回一次性观测。
        _has_per_round = any(
            isinstance(_r, dict) and "anchor_touched_n" in _r for _r in _rl)
        if _rl and _has_per_round:
            _hit = 0
            for _r in _rl:
                try:
                    if int(_r.get("anchor_touched_n", 0) or 0) > 0:
                        _hit += 1
                except (TypeError, ValueError):
                    continue
            return _hit / len(_rl) if _rl else None
        _n = len(self.anchor_touched or [])
        return 1.0 if _n > 0 else 0.0

    @property
    def aspect_carry_rate(self) -> Optional[float]:
        """延续读数：被后续圈**按 id** 引用的方面数 / 方面总数。

        ★ 与 `touch_rate` 分开报（一个是「碰没碰过」，一个是「后来还追不追」）。
        ★ 空池返回 None —— 不印 0.00 冒充读数（本项目老坑）。
        """
        _units = self.aspect_units or []
        if not _units:
            return None
        _hit_ids = set(getattr(self, "_carried_aspect_ids", []) or [])
        if not _hit_ids:
            _ch = getattr(self, "_layer_und_channel", None) or {}
            _hit_ids = set(_ch.get("carry_touched_ids") or [])
        if not _hit_ids:
            # ★ 与 touch_rate 同款口径纪律：**没有延续读数**不等于 0。
            #   有两类来源缺失：(a) 上游根本没产延续 id；(b) 上游产了但
            #   本层还没接上。两者都**不印 0.00 冒充读数** —— 返回 None，
            #   由渲染层印「—」。旧口径恒返回 0.0，把「未接线」伪装成
            #   「延续了 0 条」（本项目「零行读数伪装成做过了」老坑）。
            return None
        return len([u for u in _units
                    if str(u.get("id", "")) in _hit_ids]) / len(_units)

    def add_aspect_unit(self, desc, source="anchor", polarity="阴",
                        ground="anchor", ref=""):
        """[A1 方面单元] 登记一个方面单元，返回 unit（空 desc 返回 {}）。

        ★ 编号 `A{n}` 由**追加顺序**决定 ⇒ 同一条描述重复登记时
          返回**已存在**的那条（不新建、不换号）。幂等是硬要求：
          调用点在循环里，重复登记会污染 covers 的靶子集合。
        """
        s = str(desc).strip()
        if not s:
            return {}
        for _u in self.aspect_units:
            if _u.get("desc") == s:
                return _u
        _uid = "A%d" % (len(self.aspect_units) + 1)
        _u = make_aspect_unit(s, source=source, polarity=polarity,
                              ground=ground, ref=ref, unit_id=_uid)
        if _u:
            self.aspect_units.append(_u)
        return _u

    @staticmethod
    def shape_of(v: "View") -> str:
        lines = [f"【view｜entry={v.entry}】", f"锚点：{v.anchor}"]
        if v.manifest:
            lines.append(f"它显形为：{v.manifest}")
        if v.candidates:
            lines.append("候选：")
            for c in v.candidates:
                lines.append(f"  - {c.get('desc', '')}")
        if v.amps:
            lines.append("& 印记：")
            for a in v.amps:
                lines.append(
                    f"  - [{AMP_TYPES.get(a.get('type', ''), '?')}] "
                    f"{a.get('desc', '')}")
        if v.threads:
            lines.append("悬空线头：")
            for t in v.threads:
                lines.append(f"  - {t.get('desc', '')}")
        if v.probes:
            lines.append("还没带走的自问：")
            for p in v.probes:
                lines.append(
                    f"  - {p.get('question', '')}"
                    f"（回来：{p.get('link', '')}）")
        if v.meta:
            lines.append("元反思：")
            for m in v.meta:
                lines.append(f"  - {m}")
        if v.untouched:
            lines.append("尚未触及的方面：")
            for u in v.untouched:
                # [A1 方面单元] 带 id 前缀：渲染里看得见编号，
                #   才可能在下一圈被 covers 按符号引用。
                _aid = str(u.get("id", "") or "")
                _pfx = (_aid + ". ") if _aid else ""
                lines.append(f"  - {_pfx}{u.get('desc', '')}")
        if v.engagements:
            lines.append("本层碰了的：")
            for e in v.engagements:
                lines.append(f"  - {e.get('target', '')}（{e.get('how', '')}）")
        if v.suspensions:
            lines.append("主动悬置（判断过、决定不碰）：")
            for s in v.suspensions:
                lines.append(
                    f"  - {s.get('target', '')}（{s.get('reason', '')}）"
                    f"[{s.get('status', '')}]")
        if v.deferrals:
            lines.append("延迟债务（暂缓，非悬置）：")
            for d in v.deferrals:
                lines.append(
                    f"  - {d.get('sub_question', '')}"
                    f"（回访：{d.get('revisit_condition', '')}）"
                    f"[{d.get('status', '')}]")
        if v.adjudications:
            lines.append("裁决的张力（极性，回溯）：")
            for a in v.adjudications:
                lines.append(
                    f"  - {a.get('tension', '')} → {a.get('polarity', '')}")
        if v.duel_suspensions:
            lines.append("悬置的张力（不解决什么分歧）：")
            for s in v.duel_suspensions:
                lines.append(
                    f"  - {s.get('target', '')}（{s.get('quadrant', '')}）"
                    f"[{s.get('status', '')}]")
        if v.decidable_product and v.decidable_product.get("answer"):
            lines.append("【可判定通道产物】")
            lines.append(f"  - answer: {v.decidable_product.get('answer', '')[:200]}")
        if v.undecidable_product and v.undecidable_product.get("structural_amps"):
            lines.append("【不可判定通道产物】")
            lines.append(f"  - 结构清晰度: {v.undecidable_product.get('clarity', 0)}")
            for sa in v.undecidable_product.get("structural_amps", [])[:3]:
                lines.append(f"  - {sa}")
        return "\n".join(lines)

    @staticmethod
    def speech_of(v: "View") -> str:
        lines = [f"【view｜entry={v.entry}】", f"锚点：{v.anchor}"]
        if v.collision:
            lines.append(f"它说的话：\n{v.collision}")
        if v.amps:
            lines.append("& 印记：")
            for a in v.amps:
                lines.append(
                    f"  - [{AMP_TYPES.get(a.get('type', ''), '?')}] "
                    f"{a.get('desc', '')}")
        if v.threads:
            lines.append("悬空线头：")
            for t in v.threads:
                lines.append(f"  - {t.get('desc', '')}")
        if v.meta:
            lines.append("元反思：")
            for m in v.meta:
                lines.append(f"  - {m}")
        return "\n".join(lines)

    def add_error(self, where: str, e: Exception):
        self.errors.append(f"{where} 失败：{type(e).__name__}: {e}")
        return self

    def to_dict(self) -> dict:
        d = asdict(self)
        # [A3 双读数出口] `asdict` **不收集 property** ⇒ 两个读数原本
        #   永远进不了产物（能力在、看不见）。这里显式补出口：
        #   ★ 两个读数**各占一个键**，永不合成一个分（红线「未对齐合法」）；
        #   ★ 算不出（空池）就**不写这个键** —— 不印 0.00 冒充读数。
        try:
            _tr = self.touch_rate
            if _tr is not None:
                d["touch_rate"] = round(float(_tr), 4)
        except Exception:
            pass
        try:
            _acr = self.aspect_carry_rate
            if _acr is not None:
                d["aspect_carry_rate"] = round(float(_acr), 4)
        except Exception:
            pass
        return d


CHANNELS = ("content", "context", "self")

_LAYER_LABEL = {"0": "修行", "1": "研究", "both": "对撞", "all": "元"}
_CHANNEL_LABEL = {"content": "内容", "context": "背景", "self": "自我"}


def _view_usable(v) -> bool:
    '''这个 View 能不能当上游用。

    A/B 模式某层整体异常时会生成一个只有 errors 的占位 View，
    它不是 None，所以旧代码会把它算进「上游已就绪」，
    让对撞/元层拿一份空壳去撞。这里把它挡掉。
    '''
    if v is None:
        return False
    errs = getattr(v, "errors", None) or []
    if errs and not (getattr(v, "manifest", "") or "").strip():
        return False
    return True


class MemoryChannel:
    @staticmethod
    def check(ch: str) -> str:
        if ch not in CHANNELS:
            raise ValueError(
                f"未知通道 {ch!r}。三通道只有 {', '.join(CHANNELS)}")
        return ch

    @staticmethod
    def context_of(results: dict, pools: dict, cfg: dict) -> str:
        limit = int(cfg.get("shape_items", 6))
        chars = int(cfg.get("shape_chars", 900))
        out = []
        for k in ("0", "1", "both"):
            v = results.get(k)
            if v is None:
                continue
            tag = _LAYER_LABEL.get(k, k)
            if v.manifest and v.manifest != "（此处未生）":
                out.append(f"[{tag}层走过]：{v.manifest[:chars]}")
            p = pools.get(k)
            if p and (p.amps or p.threads):
                bits = [f"  & {a.get('desc', '')}" for a in p.amps[-limit:]]
                bits += [f"  ... {t.get('desc', '')}"
                         for t in p.threads[-limit:]]
                out.append(f"[{tag}层的沉淀]\n" + "\n".join(bits))
        return "\n\n".join(out)

    @staticmethod
    def accumulate_self(prev, entry: str, view, cfg: dict):
        prev = list(prev or [])
        if not view.manifest or view.manifest == "（此处未生）":
            return prev
        chars = int(cfg.get("shape_chars", 900))
        keep = int(cfg.get("self_layers", 4))
        prev.append(f"[{_LAYER_LABEL.get(entry, entry)}层] {view.manifest[:chars]}")
        return prev[-keep:]

    @staticmethod
    def self_text_of(blocks) -> str:
        blocks = [b for b in (blocks or []) if str(b).strip()]
        return "\n\n".join(str(b).strip() for b in blocks)


# ── [E1/E2] 探针的信息增益（引擎算）与子模批选 ─────────────────
#: 引擎算 G 时的**软分配下限**：探针与某条未决主张的 sim3 低于它 ⇒
#: 视为「打不到」（不给权重）。★ 不设它会得到一个「所有探针都对所有
#: 主张有一点点权重」的稠密矩阵 —— 熵降全是噪声，G 读数没有判别力。
_GAIN_ASSIGN_MIN = 0.15
#: [E3] `covers` 命中 id 后，探针问题与靶子文本的 sim3 下限。
#: ★ 低于它 = 「编号对、语义错」⇒ 报 probe_no_target_covered。
#:   与 `_COV_OVERLAP_MIN`（0.50，语言判据）分开：那是给「无 id」
#:   场景兜底的宽尺子，这是给「有 id」场景的**严尺子**。
_COVERS_SIM_MIN = 0.30
#: [E5] `no_probe_reason` 的最小字数；短于它 = 空洞理由 ⇒ lazy_empty。
_NO_PROBE_REASON_MIN = 8
#: 子模批选的**边际下限**（E2）：`G(p*|S) < floor` ⇒ 停手。
#: ★ 默认 0.0 = 「不许零增益的补位」，**不是**「不许少」。
#:   有意不设高阈值：G 的绝对值尺度依赖池大小，硬阈值会随池漂移。
_GAIN_MARGINAL_FLOOR = 0.02   # G ∈ [0,1]；默认须 > 0，否则 below_floor 分支恒不触发
#: [E6] 自适应停止阈值：本轮所有候选探针的 G（模型自报期望增益）
#: 都低于它 ⇒ 停止信号（本轮只出不进，探针数 0 是**合法**的）。
#: ★ 与 `min_gain`（0.3）是**两把尺子**：那是「模型说这条值不值得
#:   做」，这是「还能不能推得动」。默认 0.02 取「比噪声高一点点」——
#:   刻意压低：停止是强动作，宁可多跑一圈也别误停。
_GAIN_STOP_FLOOR = 0.02


def e6_stop_verdict(seen, max_gain, min_gain, stop_floor):
    """[E6] 停止裁决（纯函数，判据与变异体的落点）。

    返回 `(is_stop: bool, reason: str)`：
      - `seen == 0`          ⇒ `(False, "no_candidate")`
        **不是停止**：模型根本没给候选，那是「没得谈」不是
        「谈不动」。混为一谈会让「模型偷懒」被读成「已收敛」。
      - `max_gain < stop_floor` ⇒ `(True, "max_gain_below_floor")`
      - 其余                  ⇒ `(False, "gain_ok")`
    ★ 边界取**严格小于**：`max_gain == stop_floor` 不算停。
    """
    _seen = int(seen or 0)
    if _seen <= 0:
        return False, "no_candidate"
    _mg = float(max_gain or 0.0)
    _fl = float(_GAIN_STOP_FLOOR if stop_floor is None
                else stop_floor)
    if _mg < _fl:
        return True, "max_gain_below_floor"
    return False, "gain_ok"


def probe_information_gain(probe, belief_items, covered_ids=None,
                           corpus=None, thr=None, assign_min=None):
    """E1：**引擎算**这条探针的信息增益 G ∈ [0,1]。

    返回 `(G, detail)`；`detail` 留痕（`h_before` / `h_after` / `hit_ids`），
    便于判据与变异体定位是哪一步给出的数。
    ★ 算不出来（未决 < 2 条）⇒ 返回 `(None, {"why": ...})`。
      **返回 None 不是 0.0**：0.0 会被读成「算出来是零增益」，
      而真相是「这个池子没有可谈的信息量」—— 两回事，别混。
    """
    _q = str((probe or {}).get("question", "")).strip()
    _und = [b for b in (belief_items or [])
            if str(b.get("status") or "") == "active"
            and str(b.get("text") or "").strip()]
    if not _q:
        return None, {"why": "empty_question"}
    if len(_und) < 2:
        return None, {"why": "undecidable_lt2", "n": len(_und)}

    _cov = {str(x).strip() for x in (covered_ids or []) if str(x).strip()}
    _live = [b for b in _und if str(b.get("id") or "") not in _cov]
    if len(_live) < 2:
        return None, {"why": "all_covered", "n": len(_live)}

    _am = _GAIN_ASSIGN_MIN if assign_min is None else float(assign_min)

    import math as _math

    def _raw_entropy(_items):
        """未决集合的**原始**语义熵 h = -Σ p·ln p —— ★ 不归一化。

        ★ 为什么不归一化（这是本轮修掉的 bug）：
          `h(x)/ln(n_x)` 的分母随集合大小变 ⇒ 「移除一条」造成的
          ln3→ln2 降幅会被两个不同的 ln(n) 各自除掉、**完全抵消**，
          G 恒为 0。归一化只在**跨不同大小集合比较**时才有意义。
        ★ 归一化留给最后一步统一做，分母恒为 `ln(n_before)`
          —— 两臂用**同一把尺子**。
        ★ 空集合返回 0.0（ln(1)=0，数学上也成立）。
        """
        _t = [str(b.get("text", "")) for b in _items]
        if len(_t) < 2:
            return 0.0
        _hn, _h, _cl = semantic_entropy_of(_t, corpus=corpus, thr=thr)
        return float(_h)

    # ── 两臂同一把尺子：分母恒为 ln(n_before) ──
    _h_before_raw = _raw_entropy(_live)
    _denom = _math.log(len(_live)) if len(_live) > 1 else 0.0
    h_before = (_h_before_raw / _denom) if _denom > 0 else 0.0

    # 候选答案分布：sim3(question, text) 归一化（软分配）
    _w = []
    for _b in _live:
        _s = float(_sim3(_q, str(_b.get("text", "")), corpus=corpus))
        _w.append(_s if _s >= _am else 0.0)
    _tot = sum(_w)
    if _tot <= 0.0:
        return 0.0, {"why": "no_assignment", "h_before": round(h_before, 4),
                     "h_after": round(h_before, 4), "hit_ids": []}
    _p = [x / _tot for x in _w]

    # ★ 簇归属：命中一条 ⇒ 移除**整个同簇**，不是只移除那一条。
    #   为什么必须整簇移除（本轮实测抓到的真错）：
    #   未决 {B1,B2,B3}，B1~B2 同簇、B3 独立 ⇒ h_before 用了「2 簇」的
    #   分歧度。若只移除 B1，剩下 {B2,B3} **不再同簇** ⇒ 簇数没降反升
    #   （2 簇 → 2 簇但 n 变小）⇒ 归一化后 h_after > h_before ⇒ G 被夹成 0。
    #   而探针命中 B1 的实际意义是「这一簇疑问被回答了」—— 同簇的 B2
    #   是同一件事的另一种说法，理应一并消解。整簇移除才与语义一致。
    _hn_all, _hr_all, _clusters = semantic_entropy_of(
        [str(b.get("text", "")) for b in _live], corpus=corpus, thr=thr)
    _cluster_of: dict = {}
    for _ci, _members in enumerate(_clusters or []):
        for _mi in _members:
            _cluster_of[_mi] = _ci

    # 期望后熵：按软分配加权「命中某条 ⇒ 移除该条**所在的整簇**」。
    # ★ 用**原始**熵求和，除的仍是 `_denom = ln(n_before)` ——
    #   两臂同尺；`_denom == 0`（n_before ≤ 1）时上面已早退。
    _h_after_raw = 0.0
    _guard = 0
    for _i, _pi in enumerate(_p):
        if _pi <= 0.0:
            continue
        _guard += 1
        _my = _cluster_of.get(_i)
        _rest = [_b for _j, _b in enumerate(_live)
                 if _cluster_of.get(_j) != _my]
        _h_after_raw += _pi * _raw_entropy(_rest)
    # 泛化到 unseen 的可能：权重 < 1 的部分按「熵不变」处理
    _h_after_raw += max(0.0, 1.0 - sum(_p)) * _h_before_raw
    h_after = (_h_after_raw / _denom) if _denom > 0 else 0.0
    if h_before <= 0.0:
        return 0.0, {"why": "h_before_zero", "h_before": 0.0,
                     "h_after": 0.0, "hit_ids": []}
    _g = (h_before - h_after) / h_before
    _g = max(0.0, min(1.0, _g))
    return round(_g, 6), {
        "h_before": round(h_before, 4), "h_after": round(h_after, 4),
        "h_raw_before": round(_h_before_raw, 4),
        "h_raw_after": round(_h_after_raw, 4),
        "denom": round(_denom, 4),
        "hit_ids": [_live[_i].get("id", "")
                    for _i, _pi in enumerate(_p) if _pi > 0],
        "n_live": len(_live), "guard": _guard,
    }


def select_probe_focus_submodular(pool, candidates, n,
                                  corpus=None, thr=None,
                                  floor=None):
    """E2：子模贪心批选（**宁少勿滥**）。返回 `(picked, detail)`。

    G(p | S) 的实现：把**已选探针命中过的信念 id** 从活跃集合里扣掉，
    再算 G —— 这就是子模条件化（已覆盖的贡献不再计入边际增益）。

    ★ 与旧 `select_probe_focus` 的三轮 take 的**关键差别**：
      旧实现三轮都可能不产出（实测 4 条全不相干只选 1 条），但**也可能**
      在某轮塞进一条增益为零的；新实现显式判 `G < floor` ⇒ 停手。
    ★ `floor` 默认 `_GAIN_MARGINAL_FLOOR`（0.0）。
    """
    _n = int(n or 0)
    _items = [it for it in (candidates or [])
              if str(it.get("text", "")).strip()]
    if _n <= 0 or not _items:
        return [], {"picked_n": 0, "why": "n<=0 or no candidates"}

    _fl = _GAIN_MARGINAL_FLOOR if floor is None else float(floor)
    _bi = list(getattr(pool, "belief_items", None) or [])
    picked: List[dict] = []
    covered: List[str] = []
    picked_texts: List[str] = []
    trace: List[dict] = []
    for _ in range(_n):
        _best, _best_g, _best_d = None, -1.0, None
        for _it in _items:
            _t = str(_it.get("text", "")).strip()
            if any(_similar(_t, _x, _TAKE_SIM) for _x in picked_texts):
                continue
            _g, _d = probe_information_gain(
                {"question": _t}, _bi, covered_ids=covered,
                corpus=corpus, thr=thr)
            if _g is None:
                continue
            if _g > _best_g:
                _best, _best_g, _best_d = _it, float(_g), _d
        if _best is None:
            trace.append({"stop": "no_candidate_with_gain"})
            break
        if _best_g < _fl:
            trace.append({"stop": "below_floor", "best_g": _best_g})
            break
        picked.append(_best)
        picked_texts.append(str(_best.get("text", "")).strip())
        covered = list(covered) + list((_best_d or {}).get("hit_ids") or [])
        trace.append({"picked": str(_best.get("text", ""))[:60],
                      "g": _best_g, "hits": (_best_d or {}).get("hit_ids")})
    return picked, {"picked_n": len(picked),
                    "floor": _fl, "trace": trace,
                    "why": "ok" if picked else "none_above_floor"}


def select_probe_focus(pool: "Pool", new_probes: List[dict],
                       new_threads: List[dict], key_terms: List[str],
                       anchor: str, cfg: dict) -> List[dict]:
    """从新探针中筛选下一轮重点。"""
    n = int((cfg.get("probe") or {}).get("select_n", 3))
    probes = [p for p in (new_probes or [])
              if str(p.get("question", "")).strip()]
    if n <= 0:
        return list(probes)

    items = []
    for p in probes:
        items.append({"text": str(p.get("question", "")).strip(),
                      "raw": p, "kind": "probe"})
    for t in (new_threads or []):
        d = str(t.get("desc", "")).strip()
        if d:
            items.append({"text": d, "kind": "thread",
                          "raw": {"question": d,
                                  "link": "（池里的线头）"}})
    if not items:
        return []

    amp_entries: List[Tuple[set, str]] = []
    for a in (pool.amps or []):
        kws = _kw(a.get("desc", ""), 6)
        if kws:
            amp_entries.append((kws, str(a.get("polarity", ""))))
    q_kw = set(key_terms or []) | _kw(anchor or "", 8)

    def _amp_weighted_score(it):
        kws = _kw(it["text"], 12)
        score = 0
        for entry_kws, pol in amp_entries:
            if kws & entry_kws:
                score += 2 if pol in ("0", "1") else 1
        return score

    hist = []
    for p in (pool.probes or []):
        q = str(p.get("question", "")).strip()
        if q and not any(_similar(q, str(x.get("question", "")), 0.9)
                         for x in probes):
            hist.append(q)
    for t in (pool.threads or []):
        d = str(t.get("desc", "")).strip()
        if d and not any(_similar(d, str(x.get("desc", "")), 0.9)
                         for x in (new_threads or [])):
            hist.append(d)

    def fresh(text):
        if not hist:
            return 1.0
        return 1.0 - max(_sim_ratio(text, h) for h in hist)

    picked: List[dict] = []
    picked_texts: List[str] = []

    def take(score_fn):
        best, best_s = None, 0.0
        for it in items:
            if any(_similar(it["text"], t, _TAKE_SIM) for t in picked_texts):
                continue
            s = float(score_fn(it) or 0)
            if best is None or s > best_s:
                best, best_s = it, s
        if best is not None and best_s > 0:
            picked.append(best)
            picked_texts.append(best["text"])

    take(_amp_weighted_score)
    take(lambda it: len(_kw(it["text"], 12) & q_kw))
    take(lambda it: fresh(it["text"]))
    _legacy = [p["raw"] for p in picked[:n]]
    # ── [E2] 子模批选接管（可关；关掉时与旧行为逐位一致） ──
    #  ★ 开关走配置 `probe.submodular`，默认 True。
    #  ★ 引擎算不出 G（未决 < 2 条）⇒ `picked` 为空 ⇒ **退回旧结果**：
    #    不能因为「新方法算不出来」就把探针整批丢掉。
    if not bool((cfg.get("probe") or {}).get("submodular", True)):
        return _legacy
    _sub, _det = select_probe_focus_submodular(
        pool, items, n,
        thr=(cfg.get("sim") or {}).get("cluster", None),
        # ★ 配置键 `probe.marginal_floor` 必须**真的接线**（默认 =
        #   `_GAIN_MARGINAL_FLOOR`）。本版修的就是「默认值让守卫恒假」
        #   —— 若只在 DEFAULT_CONFIG 里加键而不读，等于换个地方埋同一个坑。
        floor=(cfg.get("probe") or {}).get("marginal_floor", None))
    # ★ trace 条目的键是 **"picked"**（值是候选文本），不是 "text"。
    #   改前用 `x.get("text","")` ⇒ 键恒为 "" ⇒ 增益**从未到达输出**
    #   （E1 白算）。这条修正由 `check_v12328_real_entry` 的 R-T1 背书。
    _gains = {str(x.get("picked", "")): x.get("g")
              for x in (_det.get("trace") or []) if x.get("picked")}
    _picked_raw = []
    for _p in _sub:
        _raw = _p.get("raw")
        if not isinstance(_raw, dict):
            _raw = {"question": str(_p.get("text", "")),
                    "link": "（池里的线头）"}
        else:
            _raw = dict(_raw)
        if _raw.get("question"):
            _picked_raw.append(_raw)
    if not _picked_raw:
        return _legacy
    # ★ `expected_gain` 双写：喂**引擎算的 G**给下游过滤门。
    for _r in _picked_raw:
        _q = str(_r.get("question", "")).strip()
        _g = _gains.get(str(_q))
        _r["expected_gain_engine"] = _g
        if _g is not None:
            _r["expected_gain"] = float(_g)
            _r["gain_source"] = "engine"
        else:
            _r.setdefault("gain_source", "model")
    return _picked_raw


@dataclass
class Pool:
    amps: List[dict] = field(default_factory=list)
    threads: List[dict] = field(default_factory=list)
    probes: List[dict] = field(default_factory=list)
    meta: List[str] = field(default_factory=list)
    suspensions: List[dict] = field(default_factory=list)
    sub_questions: List[dict] = field(default_factory=list)
    deferrals: List[dict] = field(default_factory=list)
    escalations: List[dict] = field(default_factory=list)
    decidability_log: List[dict] = field(default_factory=list)
    duel_suspensions: List[dict] = field(default_factory=list)
    duel_alignment: dict = field(default_factory=dict)
    engagements: List[dict] = field(default_factory=list)
    refinements: List[dict] = field(default_factory=list)
    decidable_channel: dict = field(default_factory=dict)
    undecidable_channel: dict = field(default_factory=dict)
    #  ★ 研究层各圈自报的「已触及方面」——结构覆盖率（自触及）的
    #    凭据之一（另一个是 threads / probes）。
    covered_unders: List[str] = field(default_factory=list)
    #  [A1 方面单元] 池级镜像 —— `aspect_targets_v12327` 要按**真 id**
    #    对账，而 id 是 View 分配的 ⇒ 必须同步过来（否则两套编号又分叉）。
    aspect_units: List[dict] = field(default_factory=list)
    #: [层目标 / Heaps 饱和] 逐圈**累计层面数**：`[V1, V2, …]`。
    #:   ★ 修行层「挖到不能再挖」= 边际新增趋零 ⇒ 必须留**逐圈序列**，
    #:     只留终值就只能退回单点估计（真跑读不到判别力）。
    aspect_hist: List[int] = field(default_factory=list)
    anchors: List[dict] = field(default_factory=list)
    # 本次是否授权锚点作为**可引用对象**（进 _citation_table）。
    # ★ 默认 False：进了引用表就自动获得支撑 →decidable 的资格
    #   （apply_decidability_change 只拦「全是 d_ 开头」的一种情况），
    #   那是**行为变化**，不是加性。先量后改。
    anchor_as_evidence: bool = False
    web_results: List[dict] = field(default_factory=list)
    web_errors: List[dict] = field(default_factory=list)
    # 本次是否授权 W# 作为**可引用对象**（进 _citation_table）。
    # ★ 默认 False；由 web_search.as_evidence ∈ {evidence, gate} 打开。
    #   即便进了表，W# 也**只允许支撑 →partial**（硬约束见
    #   apply_decidability_change 里的 W# 特例）。
    web_as_evidence: bool = False
    web_arbitration: List[dict] = field(default_factory=list)
    web_clean_check: List[dict] = field(default_factory=list)
    web_tier_proposals: List[dict] = field(default_factory=list)

    def merge(self, amps, threads, meta, probes=None, suspensions=None,
              thr=None, susp_thr=None, aspect_units=None):
        """把一圈产物并进池子。去重阈值走参数，None 时用模块默认。

        ★ 阈值以前是**四个硬编码字面量**（0.9 ×3 + 0.85 ×1），
          「参数按层可覆盖」这条红线在池内形同虚设。现在可配，
          默认值与原字面量逐位相同 ⇒ 不传参时行为零变化。
        """
        _t = _DEDUP_SIM if thr is None else float(thr)
        _st = _DEDUP_SUSP_SIM if susp_thr is None else float(susp_thr)
        for a in amps:
            if not any(_similar(a.get("desc", ""), x.get("desc", ""), _t)
                       for x in self.amps):
                self.amps.append(a)
        for t in threads:
            if not any(_similar(t.get("desc", ""), x.get("desc", ""), _t)
                       for x in self.threads):
                self.threads.append(t)
        for p in (probes or []):
            q = str(p.get("question", "")).strip()
            if q and not any(_similar(q, x.get("question", ""), _t)
                             for x in self.probes):
                self.probes.append(p)
        for m in meta:
            if m and m not in self.meta:
                self.meta.append(m)
        # [A1 方面单元] 池级同步：按 **id** 去重并入（同 id 只留一条）。
        for _u in (aspect_units or []):
            if not isinstance(_u, dict):
                continue
            _uid = str(_u.get("id") or "").strip()
            if not _uid:
                continue
            if not any(str(x.get("id") or "") == _uid
                       for x in self.aspect_units):
                self.aspect_units.append(_u)
        # ★ [层目标] 本圈结束时记一次**累计层面数**（merge 每圈调一次
        #   ⇒ 本列表天然是「逐圈序列」）。同值也记：**平稳本身就是读数**
        #   （Heaps 饱和 = 后续增量恒 0，序列会连续重复）。
        self.aspect_hist.append(len(self.aspect_units))
        for s in (suspensions or []):
            t = str(s.get("target", "")).strip()
            if not t:
                continue
            if any(_similar(t, x.get("target", ""), _st)
                   and x.get("status") in ("active", "stable")
                   for x in self.suspensions):
                continue
            self.suspensions.append(s)

    def add_decidable(self, product: dict):
        if not self.decidable_channel:
            self.decidable_channel = {
                "answers": [], "coverage_history": [], "last_coverage": 0.0,
            }
        ans = str(product.get("answer", "")).strip()
        if ans and len(ans) > 20:
            self.decidable_channel["answers"].append({
                "answer": ans[:500],
                "answered_sub_ids": list(product.get("answered_sub_ids") or []),
                "evidence": [str(e)[:200]
                             for e in (product.get("evidence") or [])][:5],
            })
            # [D2 迁移规则] ★ 可判定通道**真回答了** ⇒ 对应信念置 resolved。
            #   「对应」的判定用 `answered_sub_ids` 里的 id 命中信念 id：
            #   这是**符号**命中，不受尺子影响（与 A2 同一原则）。
            #   ★ 命中不到就**什么都不做** —— 不猜、不按文本相似兜底：
            #     猜错会把没被回答的主张标成 resolved（清算错账比不清算糟）。
            _ans_ids = {str(x).strip()
                        for x in (product.get("answered_sub_ids") or [])
                        if str(x).strip()}
            for _it in self.belief_items:
                _bid = str(_it.get("id") or "").strip()
                if _bid and _bid in _ans_ids:
                    _old = str(_it.get("status") or "active")
                    if _old != "resolved":
                        _it["status"] = "resolved"
                        self.belief_transitions.append({
                            "id": _bid, "from": _old, "to": "resolved",
                            "round": 0,
                            "why": "resolved_by_decidable",
                        })

    # [D1 信念条目] 信念条目（与 structural_amps 双写，不是替换）
    belief_items: List[dict] = field(default_factory=list)
    belief_transitions: List[dict] = field(default_factory=list)
    # [D2 可配] `revoked` 需要的不同攻击来源数（默认 = 模块常量）。
    #   ★ 配置键 `belief.revoke_sources` 的**落点**。纯函数
    #     `belief_transition` 不能读全局配置 ⇒ 由 Pool 携带并显式传入。
    revoke_sources: int = _BELIEF_REVOKE_SOURCES
    #: [D2 修正] 语义归并开关与阈值（默认**关** ⇒ 出厂零行为差）。
    #:   ★ 只在 `merge_semantic=True` 且 `_sim3 >= merge_sim`（默认 0.85，
    #:     近乎逐字）时，把「换说法重提」记为**已存在条目的一次复现**。
    #:     保红线：不同主张（实测同义 0.41~0.79 / 异义 0.00）在 0.85 下
    #:     不会被并；它只吃「几乎同一句话」的重复表述。
    merge_semantic: bool = False
    merge_sim: float = _BELIEF_MERGE_SIM
    #: [D2 修正] 归并留痕：每次归并一条 {from, into, sim, source}。
    merge_log: list = field(default_factory=list)

    #: [D3 可配] 语义熵聚类阈值（默认 = 模块常量 `_SEM_CLUSTER_THR`）。
    #:   ★ 与 `revoke_sources` 同一套下发模式：配置键
    #:     `belief.sem_entropy_thr` 的落点，由 MetaDGTF 在构造时下发。
    #:   ★ 独立于 `sim.cluster`（E2 探针批选口径，0.70）—— 尺度不同。
    sem_entropy_thr: float = _SEM_CLUSTER_THR
    # [E6] 每圈一条停止信号（可观测化；不参与评分）
    probe_stop_history: List[dict] = field(default_factory=list)

    def add_undecidable(self, product: dict,
                        und_aspects: Optional[List[str]] = None,
                        layer: int = 0,
                        covered_aspects: Optional[List[str]] = None):
        if not self.undecidable_channel:
            self.undecidable_channel = {
                "structural_amps": [], "clarity_history": [],
                "last_clarity": 0.0,
                "und_aspects": [], "struct_coverage_history": [],
                "last_struct_coverage": 0.0,
                "last_indep_ratio": None, "last_indep_pool": 0,
                "last_indep_free": 0, "indep_history": [],
                "last_sc_ratio": None, "last_sc_pool": 0,
                "last_sc_touched": 0, "sc_history": [],
                "sc_touched_amps": [],
                "aligned_amps": [], "last_struct_hit": 0,
                "last_aligned_hit": 0, "aligned_coverage_history": [],
                "last_aligned_coverage": 0.0,
                "aspect_first_hit": {}, "struct_trace": [],
            }
        #  ★ 研究层各圈自报的「已触及方面」——结构覆盖率的自触及凭据
        #    之一（另一个是 threads/probes）。与 structural_amps 分属
        #    两层：一个是结构名，一个是方面名。
        if covered_aspects is not None:
            _bs = self.covered_unders or []
            for _ca in covered_aspects:
                _s = str(_ca).strip()
                if _s and not any(_similar(_s, _x, _DUP_SIM)
                                  for _x in _bs):
                    _bs.append(_s[:200])
            self.covered_unders = _bs
        if und_aspects and not self.undecidable_channel.get("und_aspects"):
            self.undecidable_channel["und_aspects"] = [
                str(x)[:120] for x in und_aspects if str(x).strip()
            ]
        clarity = 0.0
        try:
            clarity = float(product.get("clarity", 0.0))
        except (TypeError, ValueError):
            clarity = 0.0
        clarity = max(0.0, min(1.0, clarity))
        self.undecidable_channel["clarity_history"].append(clarity)
        self.undecidable_channel["last_clarity"] = clarity
        _bl = str(product.get("_layer_name") or layer or "")
        _br = product.get("_round_no", 0)
        try:
            _br = int(_br or 0)
        except (TypeError, ValueError):
            _br = 0
        # [D1 信念条目] **登记与去重解耦**：
        #   · `structural_amps` 仍按旧口径去重（同一个结构名不重复入列）；
        #   · 但信念登记**每圈都做** —— 复现是 D2「连续 k 圈被 ≥2 来源
        #     独立复现」的前提，被去重挡在外面就永远凑不齐来源。
        #   · `sources` 用**层名**（0/1/both/all）：同一主张被不同层独立
        #     提炼才算「独立复现」；用圈号会让「同一层反复说」冒充独立。
        for sa in (product.get("structural_amps") or []):
            s = str(sa).strip()
            if not s:
                continue
            _is_new = not any(_similar(s, x, _DUP_SIM)
                              for x in self.undecidable_channel["structural_amps"])
            if _is_new:
                self.undecidable_channel["structural_amps"].append(s[:200])
            _atk = []
            _why_atk = str(product.get("_belief_attack") or "").strip()
            if _why_atk:
                _atk = [_why_atk[:40]]
            _res = str(product.get("_belief_resolved") or "").strip()
            self.upsert_belief(s[:200], ground=("layer" + _bl) if _bl else "",
                               round_no=_br,
                               sources=[("layer" + _bl) if _bl else "unknown"],
                               attack=(_atk or None),
                               resolved_by=(_res or None))
        for sa in (product.get("aligned_amps") or []):
            s = str(sa).strip()
            if s and not any(_similar(s, x, _DUP_SIM)
                             for x in self.undecidable_channel["aligned_amps"]):
                self.undecidable_channel["aligned_amps"].append(s[:200])
        # [D3 语义熵] 每层入库后刷新一次（**唯一调用点**）：
        #   产物里的 `semantic_entropy` 由此有值，不再恒为 null。
        #   ★ 失败不拦（观测失败不该改变主路径结果）。
        try:
            self.refresh_belief_entropy(
                thr=getattr(self, "sem_entropy_thr", None))
        except Exception:
            pass
        aspects = self.undecidable_channel.get("und_aspects", [])
        def _hit_of(_pool):
            if not aspects or not _pool:
                return []
            return [asp for asp in aspects
                    if any(_overlap_coef(asp, sa) >= 0.3 for sa in _pool)]

        hit_aspects: List[str] = _hit_of(
            self.undecidable_channel["structural_amps"])
        aligned_hits: List[str] = _hit_of(
            self.undecidable_channel.get("aligned_amps") or [])
        if aspects:
            struct_cov = len(hit_aspects) / len(aspects)
            aligned_cov = len(aligned_hits) / len(aspects)
        else:
            struct_cov = 0.0
            aligned_cov = 0.0
        self.undecidable_channel["last_struct_hit"] = len(hit_aspects)
        self.undecidable_channel["last_aligned_hit"] = len(aligned_hits)
        self.undecidable_channel["struct_coverage_history"].append(struct_cov)
        self.undecidable_channel["last_struct_coverage"] = struct_cov
        self.undecidable_channel.setdefault(
            "aligned_coverage_history", []).append(aligned_cov)
        self.undecidable_channel["last_aligned_coverage"] = aligned_cov

        #  ★ 独立度（取代「结构覆盖率」这个名字）：提示词要求
        #    structural_amps「独立提炼、不得直接复述 und_aspects 的原话」，
        #    所以对它的读数该问「有多独立」，而不是「覆盖了几个方面」——
        #    后者与提示词的方向**正好相反**（复述得越像，旧读数越高），
        #    这就是它长期恒 0 而没人当回事的原因。
        #    分母是 structural_amps 条数 ⇒ 越高越合规。
        #  ★ 旧键（last_struct_coverage / struct_coverage_history /
        #    last_struct_hit / struct_trace）**一字不动**：
        #    它们是历史 packed 的口径，也是命中轨迹的输入。
        _amps_pool = list(self.undecidable_channel["structural_amps"])
        _free_amps = [sa for sa in _amps_pool
                      if not any(_overlap_coef(asp, sa) >= 0.3
                                 for asp in aspects)]
        indep_ratio = (len(_free_amps) / len(_amps_pool)
                       if _amps_pool else None)
        self.undecidable_channel["last_indep_ratio"] = indep_ratio
        self.undecidable_channel["last_indep_pool"] = len(_amps_pool)
        self.undecidable_channel["last_indep_free"] = len(_free_amps)
        self.undecidable_channel.setdefault("indep_history", []).append(
            indep_ratio)

        #  ★ 结构覆盖率（重设计）＝**自触及**：一条结构性 & 写完之后，
        #    研究过程**自己还碰不碰它**。分子 = 被「后续圈自己的产物」
        #    再次呼应的结构条数，分母 = 结构总条数。
        #    ★ 凭据只取**研究层自己产出的文本**（线头 / 探针 / 自报触及），
        #      不取评估阶段的 und_aspects，也不取 evidence 引用——
        #      后者实测 A# 引用为 0（模型只引 C#），前者方向相反。
        #    ★ 与「独立度」同分母、不同视角：独立度数「有多新」，
        #      本读数数「有多活」。实测两者 Pearson r ≈ 0.13（正交）。
        _downstream = self._und_self_touch_texts()
        _touched = [sa for sa in _amps_pool
                    if any(t and _overlap_coef(sa, t) >= 0.3
                           for t in _downstream)]
        sc_ratio = (len(_touched) / len(_amps_pool)
                    if _amps_pool else None)
        self.undecidable_channel["last_sc_ratio"] = sc_ratio
        self.undecidable_channel["last_sc_pool"] = len(_amps_pool)
        self.undecidable_channel["last_sc_touched"] = len(_touched)
        self.undecidable_channel["sc_touched_amps"] = [
            s[:120] for s in _touched]
        self.undecidable_channel.setdefault("sc_history", []).append(
            sc_ratio)

        def _append_trace(_pool, _hits, _trace_key, _first_key):
            _first = self.undecidable_channel.setdefault(_first_key, {})
            _newly: List[str] = []
            for _asp in _hits:
                if _asp not in _first:
                    _first[_asp] = layer
                    _newly.append(_asp)
            _cov = (len(_hits) / len(aspects)) if aspects else 0.0
            self.undecidable_channel.setdefault(_trace_key, []).append({
                "layer": layer, "hit": len(_hits),
                "total": len(aspects), "cov": round(_cov, 3),
                "newly": _newly,
            })

        # ── [A3 双读数] carry_rate（延续读数，**符号口径**） ──
        #  ★ 与 last_sc_ratio 的关键区别：
        #    last_sc_ratio 的凭据是**文本**（_overlap_coef ≥ 0.3，受尺子失真）；
        #    carry_rate 的凭据是**符号**（id 命中，不受尺子影响）。
        #  ★ 两者**永远分开报**、不合成一个分（红线「未对齐合法」）。
        _sym_targets = self.aspect_targets_v12327()
        _sym_hits = self._und_self_touch_symbols()
        _sym_hit_ids = [i for i in _sym_hits if i in _sym_targets]
        self.undecidable_channel["last_carry_rate"] = (
            len(_sym_hit_ids) / len(_sym_targets) if _sym_targets else None)
        self.undecidable_channel["last_carry_pool"] = len(_sym_targets)
        self.undecidable_channel["last_carry_hits"] = len(_sym_hit_ids)
        self.undecidable_channel["carry_touched_ids"] = sorted(_sym_hit_ids)
        self.undecidable_channel.setdefault("carry_history", []).append(
            self.undecidable_channel["last_carry_rate"])

        _append_trace(self.undecidable_channel["structural_amps"],
                      hit_aspects, "struct_trace", "aspect_first_hit")
        _append_trace(self.undecidable_channel.get("aligned_amps") or [],
                      aligned_hits, "aligned_trace", "aligned_first_hit")

    # ── [A2 符号对账] 覆盖对账的**符号侧**：用 id 对账，不用尺子 ──
    def aspect_targets_v12327(self) -> dict:
        """池内所有**可被符号引用的靶子**：{id: {"kind","text"}}。

        ★ 为什么要有它：`covers` / `carry_rate` 要判「这条编号指向谁」，
          没有登记表就只能靠文本相似度猜 —— 那正是本轮要绕开的尺子。
        ★ 只收**真有条目**的 id，不收空串（空 id 会让对账假通过）。
        """
        out: dict = {}
        def _put(_i, _kind, _t):
            _i = str(_i).strip()
            if not _i:
                return
            out.setdefault(_i, {"kind": _kind, "text": str(_t or "")[:200]})
        for _i, _a in enumerate(self.amps or [], 1):
            _put(_a.get("id") or ("amp#%d" % _i), "amp", _a.get("desc", ""))
        for _i, _t in enumerate(self.threads or [], 1):
            _put(_t.get("id") or ("th#%d" % _i), "thread", _t.get("desc", ""))
        for _i, _p in enumerate(self.probes or [], 1):
            _put(_p.get("id") or ("probe#%d" % _i), "probe",
                 _p.get("question", ""))
        # ★ [A1 编号统一] 方面单元优先用 `aspect_units` **已分配**的 id
        #   （与渲染前缀同一套编号）；只有对不上时才按位置临时编号。
        _aunit_by_desc = {}
        for _u in (self.aspect_units or []):
            _d = str(_u.get("desc") or "").strip()
            _uid = str(_u.get("id") or "").strip()
            if _d and _uid:
                _aunit_by_desc.setdefault(_d, _uid)
        for _i, _s in enumerate(self.covered_unders or [], 1):
            _sid = _aunit_by_desc.get(str(_s or "").strip()) or ("A%d" % _i)
            _put(_sid, "covered_under", _s)
        return out

    # ── [D1/D2 信念四态] 信念条目：登记 + 四态迁移 ──────────────
    def upsert_belief(self, text, *, ground="", round_no=0, sources=None,
                      attack=None, resolved_by=None):
        """登记/更新一条信念条目，返回 (item, 旧状态, 新状态)。

        ★ 认领规则：**同 id 优先，其次同 text**。同 text 认领让「模型换个
          说法重提同一主张」仍能连续 —— 这是 D2「连续 k 圈复现」的前提。
          （真正的语义聚类在 D3；这里先用精确 text，保守且可负对照。）
        ★ 迁移**一定**走 `belief_transition`（纯函数）⇒ 判据可脱离引擎测它。
        """
        items = self.belief_items
        _key = str(text or "").strip()
        if not _key:
            return {}, "active", "active"
        _tgt = None
        for _it in items:
            if str(_it.get("text", "")) == _key:
                _tgt = _it
                break
        # ★ [D2 修正] 精确未命中时，若开启归并，尝试**保守**语义认领：
        #   只认「几乎同一句话」（`_sim3 >= merge_sim`，默认 0.85）。
        #   命中 ⇒ 把它记为**已存在条目的一次复现**（进 occurrences），
        #   不新建条目；原 text 保持为首个说法（不覆盖，保可追溯）。
        if _tgt is None and getattr(self, "merge_semantic", False):
            _ms = float(getattr(self, "merge_sim", _BELIEF_MERGE_SIM) or
                        _BELIEF_MERGE_SIM)
            for _it in items:
                _et = str(_it.get("text", "")).strip()
                if not _et:
                    continue
                try:
                    _sim = _sim3(_key, _et)
                except Exception:
                    _sim = 0.0
                if float(_sim) >= _ms:
                    _tgt = _it
                    getattr(self, "merge_log", []).append({
                        "from": _key[:120], "into": _et[:120],
                        "sim": round(float(_sim), 3),
                        "source": (str((sources or [""])[0]) or "unknown"),
                    })
                    break
        if _tgt is None:
            _uid = "B%d" % (len(items) + 1)
            _tgt = make_belief_item(_key, ground=ground, item_id=_uid)
            if not _tgt:
                return {}, "active", "active"
            items.append(_tgt)
        _old = str(_tgt.get("status") or "active")
        _new = belief_transition(_tgt, round_no=round_no, sources=sources,
                                 attack=attack, resolved_by=resolved_by,
                                 attack_sources=(
                                     sources if attack else None),
                                 revoke_sources=getattr(
                                     self, "revoke_sources", None))
        # 就地更新（rounds_seen / support / attack 是累积量）
        _sup = list(_tgt.get("support") or [])
        for _s in (sources or []):
            _s = str(_s).strip()
            if _s and _s not in _sup:
                _sup.append(_s)
        _atk = list(_tgt.get("attack") or [])
        for _a in (attack or []):
            _a = str(_a).strip()
            if _a and _a not in _atk:
                _atk.append(_a)
        _rnd = list(_tgt.get("rounds_seen") or [])
        try:
            _rn = int(round_no or 0)
        except (TypeError, ValueError):
            _rn = 0
        if _rn and _rn not in _rnd:
            _rnd.append(_rn)
        _atk_src = list(_tgt.get("attack_sources") or [])
        if attack:
            for _as_ in (sources or []):
                _as_ = str(_as_).strip()
                if _as_ and _as_ not in _atk_src:
                    _atk_src.append(_as_)
        _tgt["support"] = _sup
        _tgt["attack"] = _atk
        _tgt["attack_sources"] = _atk_src
        _tgt["rounds_seen"] = _rnd
        if ground and not _tgt.get("ground"):
            _tgt["ground"] = str(ground)
        # [D3 修正] 记本次出现：(来源标签, 本次文本)。
        #   ★ 来源标签取 `sources` 第一个（= 层名），无来源时用 "unknown"。
        #   ★ 同一 (源, 文本) 已记过则不重复 —— 「同一层同一次说完又说一遍」
        #     不是「两次独立出现」（本项目「重复面」老坑）。
        _occ = list(_tgt.get("occurrences") or [])
        _src_lab = "unknown"
        for _s0 in (sources or []):
            _s0 = str(_s0).strip()
            if _s0:
                _src_lab = _s0
                break
        _occ_keys = set()
        for _x in _occ:
            if isinstance(_x, (list, tuple)) and len(_x) >= 2:
                _occ_keys.add((str(_x[0]), str(_x[1])))
            else:
                _occ_keys.add(("unknown", str(_x)))
        if (_src_lab, _key) not in _occ_keys:
            _occ.append([_src_lab, _key])
        _tgt["occurrences"] = _occ
        _tgt["status"] = _new
        if _new != _old:
            self.belief_transitions.append({
                "id": _tgt.get("id", ""), "from": _old, "to": _new,
                "round": _rn,
                "why": ("resolved_by_decidable" if resolved_by
                        else ("attack_wins" if _new == "revoked"
                              else ("independent_recurrence" if _new == "stable"
                                    else "attack_reopened"))),
            })
        return _tgt, _old, _new

    def refresh_belief_entropy(self, corpus=None, thr=None):
        """D3：给所有信念条目刷新 `semantic_entropy`（可观测量，非评分）。

        ★ 出现文本从哪来（**重新设计**）：本条目自身的 `occurrences`
          **＋池内其他条目的 text**。为什么必须含后者：`upsert_belief` 按
          **精确文本**认领（D2 要保守、可负对照），所以「同一主张换个说法」
          会落成**另一条**；若不看它们，读数恒为 `None`（三轮实测证实）。
          **不是**「全池 structural_amps」：那会把**无关主张**也算进来，
          集内必然全异 ⇒ `h_norm` 恒 = 1.0（出厂版真跑实测 6/6，零信息量）。
        ★ 分组口径：`_sim3 ≥ thr` 单链聚类，**只取包住本条目 text 的那个簇**
          —— 那才是「本主张」的出现集。簇内出现数 < 2 ⇒ `None`（诚实缺省：
          只有一条说法，无发散可言）；≥2 且全同簇 ⇒ `0.0`（说法收敛）；
          ≥2 且分裂 ⇒ `> 0`（说法发散）。
        ★ 去重口径：按文本 —— 同一句重复登记不算「两种说法」。
        ★ `thr=None` ⇒ 用模块默认（0.70）；外部传配置值时逐位一致。
        ★ 只对 `status == "active"` 的条目算发散度？**不。**
          全部条目都算 —— 「稳不稳」是观测，不是只对某类条目生效的规则；
          只在**迁移**时用 active 的身份去读它（见 D2）。
        """
        # [D3 修正·语料自供] `corpus=None` 时用**本池自己的文本**编语料：
        #   `_sim3` 无语料只走字面层（Jaccard）⇒ 「同一主张换个说法」
        #   几乎必落在阈值之下 ⇒ 语义熵退化成「换个说法就算发散」，
        #   读数无信息量（真跑 + 直测共同证实）。池自己的未决语料是
        #   最贴近的尺子，且篇数 < 4 时 BM25 自动降级 ⇒ 不会更差。
        #   ★ 外部显式传 corpus 时逐位覆盖（可负对照）。
        _corpus = corpus
        if _corpus is None:
            _bag = []
            for _sa in (self.undecidable_channel.get("structural_amps")
                        or []):
                _s0 = str(_sa).strip()
                if _s0:
                    _bag.append(_s0)
            for _aa in (self.undecidable_channel.get("aligned_amps")
                        or []):
                _s0 = str(_aa).strip()
                if _s0:
                    _bag.append(_s0)
            for _it0 in self.belief_items:
                _s0 = str(_it0.get("text", "")).strip()
                if _s0:
                    _bag.append(_s0)
                for _oc0 in (_it0.get("occurrences") or []):
                    if isinstance(_oc0, (list, tuple)) and len(_oc0) > 1:
                        _s0 = str(_oc0[1]).strip()
                        if _s0:
                            _bag.append(_s0)
            if _bag:
                _corpus = _bm25_corpus(_bag)
        _out = {}
        # 池内其他条目的 text 集合（「同主张的不同说法」候选来源）。
        _pool_texts = []
        for _jx in self.belief_items:
            _s0 = str(_jx.get("text", "")).strip()
            if _s0:
                _pool_texts.append(_s0)
        for _it in self.belief_items:
            _own = str(_it.get("text", "")).strip()
            _txt = []
            _seen = set()
            if _own:
                _txt.append(_own)
                _seen.add(_own)
            # 本条目自身的历次出现（逐字重复才累加，是「独立复现」的凭据）
            _occs = list(_it.get("occurrences") or [])
            for _oc in _occs:
                if isinstance(_oc, (list, tuple)):
                    _s = str(_oc[1]).strip() if len(_oc) > 1 else ""
                else:
                    _s = str(_oc).strip()
                if _s and _s not in _seen:
                    _seen.add(_s)
                    _txt.append(_s)
            # ★ 池内其他条目：先全收，后面按簇筛（只留包住本条的簇）。
            for _s0 in _pool_texts:
                if _s0 and _s0 not in _seen:
                    _seen.add(_s0)
                    _txt.append(_s0)
            if not _txt:
                _it["semantic_entropy"] = None
                _it["semantic_clusters"] = []
                _it["occurrence_n"] = 0
                _out[_it.get("id", "")] = None
                continue
            _hn_all, _h_all, _cl_all = semantic_entropy_of(
                _txt, corpus=_corpus, thr=thr)
            # 只留**包住本条目 text** 的那个簇（= 本主张的出现集）。
            _anchor_idx = _txt.index(_own) if _own in _txt else 0
            _keep = None
            for _c in (_cl_all or []):
                if _anchor_idx in _c:
                    _keep = list(_c)
                    break
            if _keep is None:
                _keep = [_anchor_idx]
            _sub = [_txt[_i] for _i in _keep]
            _hn, _h, _cl = semantic_entropy_of(_sub, corpus=_corpus, thr=thr)
            _it["semantic_entropy"] = _hn
            _it["semantic_clusters"] = _cl
            _it["occurrence_n"] = len(_sub)
            _out[_it.get("id", "")] = _hn
        return _out

    def note_probe_stop(self, layer, seen, max_gain, min_gain,
                        stop_floor) -> dict:
        """[E6] 记一条停止信号痕迹。**只留痕**，不拦不改行为。

        ★ `reason == "no_candidate"` 也记 —— 「没候选」与「有候选
          但全低于阈」必须能分开审计，否则读不出模型是懒还是池收敛。
        """
        _stop, _why = e6_stop_verdict(seen, max_gain, min_gain,
                                      stop_floor)
        _rec = {"layer": str(layer),
                "seen": int(seen or 0),
                "max_gain": round(float(max_gain or 0.0), 4),
                "stop_floor": float(_GAIN_STOP_FLOOR if stop_floor
                                    is None else stop_floor),
                "stop": bool(_stop), "reason": _why}
        self.probe_stop_history.append(_rec)
        return _rec

    def belief_status_counts(self) -> dict:
        """四态计数（**两向对账**用：计数之和必须 == 条目总数）。"""
        out = {s: 0 for s in _BELIEF_STATUS}
        for _it in self.belief_items:
            _s = str(_it.get("status") or "")
            if _s in out:
                out[_s] += 1
            else:
                out.setdefault("__unknown__", 0)
                out["__unknown__"] += 1
        return out

    def _und_self_touch_symbols(self) -> dict:
        """符号版自触及凭据：{id: 来源标签}——哪些靶子被**后续产物**按 id 引用。

        ★ 与 `_und_self_touch_texts()` 的关系：那些是**文本**凭据（旧口径，
          继续保留供旧读数用）；这里是**符号**凭据（新口径）。
          两者并存不互相替代 —— 旧读数要继续可读，新读数要不受尺子影响。
        ★ 空池返回空 dict（调用点据此记 None，不印 0.00 冒充读数）。
        """
        out: dict = {}
        _targets = self.aspect_targets_v12327()
        _pat = re.compile(r"(?:amp|th|probe|A|B|T)#?(\d+)")
        _all_ids = set(_targets.keys())

        def _scan(_text, _tag):
            _s = str(_text or "").strip()
            if not _s:
                return
            # ① 直接出现真实 id 字面量（如 "amp#3" / "A2"）
            for _tid in _all_ids:
                if _tid and re.search(
                        r"(?<![\w#])" + re.escape(_tid) + r"(?![\w#])", _s):
                    out.setdefault(_tid, _tag)
            # ② 出现带前缀的形态（amp#3 / th#2 / probe#1 / A2 / B7）
            for _m in _pat.finditer(_s):
                _full = _m.group(0).replace("#", "#")
                if _full in _all_ids:
                    out.setdefault(_full, _tag)
                _bare = _m.group(1)
                for _prefix in ("amp#", "th#", "probe#", "A", "B", "T"):
                    _cand = _prefix + _bare
                    if _cand in _all_ids:
                        out.setdefault(_cand, _tag)

        for _t in (self.threads or []):
            _scan(_t.get("desc", ""), "thread")
            _scan(_t.get("polarity_why", ""), "thread")
        for _p in (self.probes or []):
            _scan(_p.get("question", ""), "probe")
            for _c in (_p.get("covers") or []):
                _scan(_c, "covers")
            _scan(_p.get("link", ""), "link")
        for _e in (self.engagements or []):
            _scan(_e.get("target", ""), "engagement")
        for _s in (self.suspensions or []):
            _scan(_s.get("target", ""), "suspension")
        for _d in (self.deferrals or []):
            _scan(_d.get("target", ""), "deferral")
        return out

    def _und_self_touch_texts(self) -> List[str]:
        """「研究层自己产出的下游文本」——用来判结构 amp 有没有被再次触及。

        ★ 为什么是这几类、且**只能是**这几类：
          · `threads`（悬空线头）：研究层自己产出的待追线索 ——
            一条结构若被后续圈追成线头，就是「还活着」。
          · `probes`（探针）：研究层自己设计的验证动作。
          · `sc_probe_texts`（各圈自报触及）：模型每圈写
            covered/uncovered_aspects 时实际在描述自己碰到的东西。
        ★ **刻意不取**：
          · `und_aspects`（那是评估阶段的疑问，不是研究层的产物）——
            拿了就和「独立度」用同一参照，两读数会互为函数。
          · `evidence[].cite` 的 A# —— 实测模型只引 C#，A# 引用为 0，
            拿了等于恒 0。
        ★ 空池返回空表（调用点据此记 None，不印 0.00 冒充读数）。
        """
        out: List[str] = []
        for t in (self.threads or []):
            s = str(t.get("desc", "")).strip()
            if s:
                out.append(s)
            w = str(t.get("polarity_why", "")).strip()
            if w:
                out.append(w)
        for p in (self.probes or []):
            s = str(p.get("question", "")).strip()
            if s:
                out.append(s)
        for _seg in (self.covered_unders or []):
            s = str(_seg).strip()
            if s:
                out.append(s)
        return out

    def to_dict(self) -> dict:
        d = {"amps": self.amps, "threads": self.threads,
                "probes": self.probes, "meta": self.meta,
                "suspensions": self.suspensions,
                "sub_questions": self.sub_questions,
                "deferrals": self.deferrals,
                "escalations": self.escalations,
                "decidability_log": self.decidability_log,
                "duel_suspensions": self.duel_suspensions,
                "duel_alignment": self.duel_alignment,
                "engagements": self.engagements,
                "refinements": self.refinements,
                "decidable_channel": self.decidable_channel,
                "undecidable_channel": self.undecidable_channel}
        # [A2/A3 符号对账] 符号对账的登记表：出口才能被下游读。
        # ★ to_dict 是**手工白名单**，新键不同步 = 静默丢产物。
        if self.undecidable_channel:
            _at = self.aspect_targets_v12327()
            if _at:
                d["aspect_targets"] = _at
        # [D1/D2 信念四态] 信念条目与迁移轨迹：出口才能被下游读。
        if self.belief_items:
            d["belief_items"] = self.belief_items
        if self.belief_transitions:
            d["belief_transitions"] = self.belief_transitions
        # [D2 可配] `revoked` 门槛是**实际生效值**（配置可能覆盖默认）
        #   ⇒ 必须出口，否则读的人不知道这批产物是按哪个门槛判的。
        #   ★ 键名必须 == 字段名（`revoke_sources`）：`check_v123_pool_export`
        #     的「前向守卫」按 `__dataclass_fields__` 逐个查出口，改名即判红。
        d["revoke_sources"] = int(self.revoke_sources)
        # [D3 可配] 语义熵聚类阈值同上：出口的是**实际生效值**（配置可能
        #   覆盖默认）—— 读产物的人要知道这批 `semantic_entropy` 是按哪个
        #   门槛算的。★ 键名必须 == 字段名（前向守卫按
        #   `__dataclass_fields__` 逐个查出口，改名即判红）。
        d["sem_entropy_thr"] = float(self.sem_entropy_thr)
        # ★ [D2 修正] 归并留痕出口（两向一致：开关关时恒为空列表）。
        d["merge_semantic"] = bool(getattr(self, "merge_semantic", False))
        d["merge_log"] = list(getattr(self, "merge_log", []) or [])
        # ★ merge_sim 同样出口**实际生效值**（前向守卫按字段名逐个查）。
        d["merge_sim"] = float(getattr(self, "merge_sim", 0.0) or 0.0)
        # [E6 停止信号] 与 belief_items 同样走白名单出口。
        if self.probe_stop_history:
            d["probe_stop_history"] = self.probe_stop_history
        # [D1 四态统计] 信念状态计数（可观测量）：给「稳不稳」一个读数出口。
        #   `belief_status_counts()` 原本零调用点 ⇒ 能力在、产物读不到。
        if self.belief_items:
            d["belief_status_counts"] = self.belief_status_counts()
        # [A1 方面单元] 池级镜像出口（A1~An 编号可在产物里审计）。
        if self.aspect_units:
            d["aspect_units"] = self.aspect_units
        # ★ [层目标] 四层目标读数所需的原料必须**出口**（否则 AutoTune
        #   的 `layer_goal_summary` 在真跑里永远读不到 ⇒ 只能走 fallback）。
        if getattr(self, "aspect_hist", None):
            d["aspect_hist"] = list(self.aspect_hist)
        if getattr(self, "upstream_layers", 0):
            d["upstream_layers"] = int(self.upstream_layers)
        if getattr(self, "upstream_texts", None):
            d["upstream_texts"] = list(self.upstream_texts)
        if getattr(self, "sem_stagnation", None) is not None:
            d["sem_stagnation"] = float(self.sem_stagnation)
        # ★ [四层目标 · 运行痕迹] 逐圈目标读数序列（停因判据就是读它）。
        #   出口的理由：真跑验收要能看见「每圈有没有读到目标」——
        #   只 append 不出出口 = 产物里看不到（本项目已栽过多次）。
        # ★ [第六期] 量化读数出口：**有才出**（空 dict 不出键，
        #   与 goal_trace 同款纪律，避免产物里出现空壳读数）。
        if getattr(self, "quant_readings", None):
            d["quant_readings"] = {
                str(k): dict(v) for k, v in (self.quant_readings or {}).items()
                if isinstance(v, dict) and v
            }
        if getattr(self, "goal_trace", None):
            d["goal_trace"] = list(self.goal_trace)
        if getattr(self, "goal_verdict", ""):
            d["goal_verdict"] = str(self.goal_verdict)
        if self.covered_unders:
            d["covered_unders"] = self.covered_unders
        if self.anchors:
            d["anchors"] = self.anchors
            d["anchor_as_evidence"] = self.anchor_as_evidence
        if self.web_results or self.web_errors or self.web_as_evidence:
            d["web_results"] = self.web_results
            d["web_errors"] = self.web_errors
            d["web_as_evidence"] = self.web_as_evidence
        if self.web_arbitration:
            d["web_arbitration"] = self.web_arbitration
        if self.web_clean_check:
            d["web_clean_check"] = self.web_clean_check
        if self.web_tier_proposals:
            d["web_tier_proposals"] = self.web_tier_proposals
        return d


@dataclass
class Input:
    question: Optional[str] = None
    root_question: Optional[str] = None
    upstream_views: List[View] = field(default_factory=list)
    upstream_pools: List[Pool] = field(default_factory=list)
    upstream_untouched: List[List[dict]] = field(default_factory=list)
    seed_probes: List[dict] = field(default_factory=list)
    # [P2-7] 上一圈 self-check 的硬约束。与 seed_probes 分开：
    # 混在一起时它被渲染成「上一圈没带走的自问」——一条普通探针，
    # 模型当参考看，不当约束听。分开后它是独立的硬约束块。
    carry_constraints: List[dict] = field(default_factory=list)
    context: str = ""
    self_memory: str = ""
    key_terms: List[str] = field(default_factory=list)
    round_role: str = ""
    round_no: int = 0
    is_last_round: bool = False

    pool: Optional[Pool] = None
    decidability_result: dict = field(default_factory=dict)

    @property
    def is_base(self) -> bool:
        return self.question is not None


# ============================================================
# LLM
# ============================================================
class LLM:
    def __init__(self, config: dict):
        api_cfg = config["api"]
        # [fix-111] 本次进程实际被服务过的模型集合（跨线程共享）。
        #   跑批要在日志末尾答出「用了哪些模型」，否则无从谈复现。
        self.SERVED_SEEN = set()
        key = (os.getenv("DGTF_API_KEY") or os.getenv("OPENAI_API_KEY")
               or api_cfg.get("key") or "").strip()
        if not key:
            raise RuntimeError("未找到 API Key。请设置 DGTF_API_KEY。")
        self.client = openai.OpenAI(
            api_key=key,
            base_url=api_cfg.get("base_url", "https://api.deepseek.com/v1"),
            timeout=api_cfg.get("timeout", 240),
        )
        self.default_model = api_cfg.get("default_model", "deepseek-chat")
        self.reasoner_model = api_cfg.get("reasoner_model", "deepseek-reasoner")
        # [fix-111] V4 起 thinking 是**请求参数**，不再是另一个模型 ID。
        #   靠 model 名字猜（旧 _is_reasoner）会在换掉 legacy 别名后静默失效，
        #   所以这里一律由配置显式给出，两个模型 ID 允许同名。
        _th = api_cfg.get("thinking")
        # ★ [形状守卫] `api_cfg["thinking"]` 必须是 mapping。若被写成
        #   bool/str（手改 yaml，或上层把整段 `api.thinking` 覆盖成标量），
        #   下面的 `_th.get` 会抛 `AttributeError: 'bool' object has no attribute
        #   'get'` **直接炸掉整次真跑**（本版矩阵跑批 4 题全灭即此因）。
        #   按「失败留痕」纪律：非法形状 → 降级为 {}（全走服务端默认）**并在
        #   解析处大声告警**，绝不静默当空 —— 静默会让「配置写坏了」看起来
        #   像「本来就没配」。★ 守卫必须**紧贴取值之后、首个 `.get` 之前**：
        #   放晚了「第一处 .get」照样先炸（本处第一版就踩了这坑）。
        if _th is not None and not isinstance(_th, dict):
            print("   ⚠️ [api.thinking] 形状非法（%s，应为 mapping）⇒ 已降级为 {}；"
                  "请检查 dgtf_config.yaml 的 api.thinking 段是否被整段覆盖成了标量。"
                  % type(_th).__name__)
            _th = None
        _th = _th or {}
        self.thinking_default = _th.get("default") or None
        self.thinking_reasoner = _th.get("reasoner") or None
        self.thinking_effort = _th.get("effort") or None
        # [fix-112] 逐环节思考档位：stages 里写了哪个环节，哪个环节就覆盖
        #   default。判据是「多步推理才需要思考」，不是「生成才需要」。
        self.thinking_stages = _th.get("stages") or {}
        self.max_retries = int(api_cfg.get("max_retries", 3))
        self.backoff = float(api_cfg.get("retry_backoff", 1.8))
        self.total_calls = 0
        self.total_tokens = 0
        # [成本两分] 跑本身 vs 自测量（判定类）分开计 —— 依据 SHP：
        #   「operational tokens」与「evaluation tokens」不是一回事，
        #   混在一起会让「自测量的开销」看起来像「任务本身的成本」。
        self.ops_calls = 0
        self.ops_tokens = 0
        self.eval_calls = 0
        self.eval_tokens = 0
        # [fix-98] 上一次调用的 finish_reason / 截断标志必须是**线程局部**的。
        # 并行模式 A/B 下 4 个线程共用同一个 LLM 实例，实例属性会让
        # _call_long 读到别的层刚写入的 truncated，误判续跑。
        self._tls = threading.local()
        self._lock = threading.Lock()

    # ---- 线程局部的 last_finish / last_truncated ----
    @property
    def last_finish(self) -> Optional[str]:
        return getattr(self._tls, "finish", None)

    @last_finish.setter
    def last_finish(self, v) -> None:
        self._tls.finish = v

    @property
    def last_truncated(self) -> bool:
        return bool(getattr(self._tls, "truncated", False))

    @last_truncated.setter
    def last_truncated(self, v) -> None:
        self._tls.truncated = bool(v)

    # ---- [fix-111] 实际服务本次调用的模型名（可能与请求的不同） ----
    @property
    def last_served_by(self) -> Optional[str]:
        return getattr(self._tls, "served", None)

    # [fix-111] ⚠️ 已废弃：按 model **名字**猜是不是推理模型。
    #   它对 deepseek-flash / deepseek-v4-pro 一律判 False（名字里没有
    #   "reasoner"/"-r1"/"reasoning"），而这两个恰恰是官方推荐的现用 ID。
    #   保留只为兼容可能存在的外部脚本；决定行为请一律用显式 thinking。
    @staticmethod
    def _is_reasoner(name: str) -> bool:
        n = (name or "").lower()
        return "reasoner" in n or "-r1" in n or "reasoning" in n

    def call(self, system, user, temperature=0.6, max_tokens=3000,
             json_mode=False, model=None, thinking=None, stage=None):
        # [fix-111] thinking 是请求级参数，由调用方或配置**显式**给出。
        #   ★ 「model == reasoner_model 就算推理调用」这种判据不可靠：
        #     迁移后 default_model 与 reasoner_model 同名（都是 deepseek-flash），
        #     它会把所有调用判成推理调用。别再靠名字或身份反推。
        # [fix-112] 档位优先级：显式 thinking > 环节 stage 配置 > default。
        model = model or self.default_model
        th = thinking
        if th is None and stage:
            th = self.thinking_stages.get(stage)
        if th is None:
            th = self.thinking_default
        is_thinking = str(th or "").lower() == "enabled"
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
        }
        # ★ OpenAI SDK 的顶层 reasoning_effort= 会被吞掉，必须走 extra_body
        if th:
            body: Dict[str, Any] = {"type": str(th)}
            if is_thinking and self.thinking_effort:
                body["effort"] = str(self.thinking_effort)
            kwargs["extra_body"] = {"thinking": body}
        if not is_thinking:
            kwargs["temperature"] = temperature
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
        if json_mode:
            system += "\n\n【重要】只输出一个合法 JSON 对象。"
            if is_thinking:
                system += "\n【再次强调】必须能被 json.loads 直接解析。"
            kwargs["messages"][0]["content"] = system
        if is_thinking:
            # 推理部分的 token 计入 max_tokens，预算不够会被 length 掐断
            kwargs["max_tokens"] = max(max_tokens, 32000)

        # [fix-98] 这几个现在写进线程局部存储，不是实例属性
        self.last_finish = None
        self.last_truncated = False
        self._tls.served = None
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.client.chat.completions.create(**kwargs)
                ch = resp.choices[0]
                # [fix-111] 实际服务者可能与请求的不同（legacy 别名会被路由）。
                #   不留痕的话「这一跑到底用的哪个模型」永远是黑箱，
                #   —— 2026-10-02 前全部 124 跑都处在这个状态。
                served = getattr(resp, "model", None) or model
                self._tls.served = served
                if served != model:
                    logger.warning(
                        "模型别名漂移：请求 %s，实际服务 %s", model, served)
                # 跑完要能在日志里答出「这跑到底用了哪些模型」，
                # 不然「复现」两个字没有落处（见 §7.18②）。
                if served not in self.SERVED_SEEN:
                    with self._lock:
                        self.SERVED_SEEN.add(served)
                usage = getattr(resp, "usage", None)
                if usage:
                    with self._lock:
                        self.total_tokens += (
                            getattr(usage, "total_tokens", 0) or 0)
                with self._lock:
                    self.total_calls += 1
                    # [成本两分] 按 stage 归类（未登记的 stage 一律算 ops，
                    #   宁少算自测量、不多算）。
                    _tk = 0
                    try:
                        _tk = int(getattr(usage, "total_tokens", 0) or 0)
                    except Exception:
                        _tk = 0
                    if cost_bucket(stage) == "eval":
                        self.eval_calls += 1
                        self.eval_tokens += _tk
                    else:
                        self.ops_calls += 1
                        self.ops_tokens += _tk
                    _tok_calls, _tok_total = (
                        self.total_calls, self.total_tokens)
                # 供调用方（工作台等）**实时**读数：每次调用后打一行累计。
                #   走 logging 不走 vp —— vp 受 output.verbose 控制，
                #   而这是「运行状态」不是「调试细节」，关 verbose 也要看得到。
                logger.info("[tok] calls=%d tokens=%d",
                            _tok_calls, _tok_total)
                self.last_finish = getattr(ch, "finish_reason", None)
                self.last_truncated = (self.last_finish == "length")
                if self.last_truncated:
                    logger.warning("输出被长度掐断(finish_reason=length)")
                content = ch.message.content or ""
                if content.strip():
                    return content
                last_err = last_err or RuntimeError("LLM 返回空内容")
                logger.warning("返回空内容(%d/%d)", attempt, self.max_retries)
                if attempt < self.max_retries:
                    time.sleep(self.backoff ** attempt)
                    continue
            except Exception as e:
                last_err = e
                logger.warning("调用失败(%d/%d): %s", attempt, self.max_retries, e)
                if attempt < self.max_retries:
                    time.sleep(self.backoff ** attempt)
        raise RuntimeError(
            f"LLM 连续 {self.max_retries} 次失败: {last_err}")

    @staticmethod
    def parse_json(raw: str) -> Optional[dict]:
        if not raw:
            return None
        raw = raw.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        s, e = raw.find("{"), raw.rfind("}")
        if s != -1 and e > s:
            chunk = raw[s:e+1]
            try:
                return json.loads(chunk)
            except json.JSONDecodeError:
                try:
                    fixed = re.sub(r",\s*([}\]])", r"\1", chunk)
                    return json.loads(fixed)
                except Exception:
                    return None
        return None


# ============================================================
# 全量留痕 · 字段落盘（唯一实现）
# ============================================================
# 挂在 view 上的**内部账**：差分基准的快照。它不是 view 的字段，
# 所以 _view_field_map 与 View.to_dict（asdict）都不带它 —— 产物不受影响。
_VIEW_INTERNAL = ("_dump_canon",)


def _canon(v) -> str:
    """字段值的**规范化可比较**形式：JSON 串（键序无关）。"""
    try:
        return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return repr(v)


def _view_field_map(view) -> dict:
    """view 的「字段名 → 值」：dataclass 字段 + 动态属性，asdict 的容错版。"""
    try:
        d = dict(asdict(view))
    except Exception:
        d = {}
    for _k, _v in vars(view).items():
        if _k.startswith("__") or _k in _VIEW_INTERNAL or _k in d:
            continue
        d[_k] = _v                    # 动态属性（asdict 覆盖不到）
    return d


def dump_view_fields(view, emit, *, prev=None, remember=False) -> None:
    """把 view 的**全部字段**逐条写进 emit（真跑时即日志）。

    [v1.21.68] 建立：不挑字段、机械全量 —— 新增字段自动被覆盖，不会因为
      漏写一行 print 而丢。
    [v1.21.69] 从 DGTF.dump_round 提出来给「收尾增量留痕」复用：同一件事
      两条通道各写一份，是本项目反复栽的坑。

    prev 非 None 时走**增量模式**：只打与 prev 有差异的字段。
      ★ 不维护「哪些字段是累积型」的清单 —— 那种清单一定会漏，
        本项目「无渲染点」事故就是这么来的。差异是**算**出来的。
    remember=True 时把「这一刻打出来的内容」的规范化快照挂到
      view._dump_canon 上，供收尾留痕差分。必须取在**真打出来的时刻**：
      取晚了（收尾前）会把圈后的后处理算进基准，于是那部分又漏一次。
    """
    try:
        _d = _view_field_map(view)
    except Exception as _e:
        emit(f"   ✗ 全量留痕失败：{type(_e).__name__}: {_e}")
        return
    _keys = sorted(_d.keys())
    if prev is not None:
        _same = [k for k in _keys if _canon(_d[k]) == prev.get(k)]
        _keys = [k for k in _keys if _canon(_d[k]) != prev.get(k)]
        emit(f"   （增量模式：{len(_same)}/{len(_d)} 个字段与上一圈留痕"
             f"完全相同、已省略；下面只列**变了的**）")
    _OVERSIZED = {"rendered", "manifest"}
    for _k in _keys:
        _v = _d[_k]
        if _k in _OVERSIZED and isinstance(_v, str):
            emit(f"   ├ {_k}：str {len(_v)} 字"
                 f"（超大覆盖字段，正文见产物 md）")
            continue
        if isinstance(_v, (list, tuple, dict, set)):
            _v = list(_v)
            emit(f"   ├ {_k}：{type(_d[_k]).__name__} {len(_v)} 项")
            if _v:
                _js = json.dumps(_v, ensure_ascii=False, indent=1,
                                 default=str)
                for _ln in _js.splitlines():
                    emit("   │ " + _ln)
        elif isinstance(_v, str) and "\n" in _v:
            emit(f"   ├ {_k}：str {len(_v)} 字")
            for _ln in _v.splitlines():
                emit("   │ " + _ln)
        else:
            emit(f"   ├ {_k}：{'' if _v is None else _v}")
    emit("   └ 全量留痕结束")
    if remember:
        try:
            view._dump_canon = {k: _canon(v) for k, v in _d.items()}
        except Exception:
            pass


# ============================================================
# DGTF · 单层执行器（纯生成器）
# ============================================================
class DGTF:
    def __init__(self, entry: str, llm: LLM, config: dict,
                 phase: Optional["Phase"] = None,
                 sp: Optional[dict] = None):
        assert entry in ("0", "1", "both", "all")
        self.entry = entry
        self.llm = llm
        self.config = config
        self.phase = phase or PHASES[entry]
        self.verbose = config["output"].get("verbose", True)
        # 全量留痕（dump_round / dump_final）的**独立开关**，默认关：
        #   verbose 同时管进度与留痕，关它会连每圈进度一起关；留痕只用于调试，
        #   产物 md 的「全量字段」附录已承担其职责。要看留痕：output.dump_rounds=true。
        self.dump_rounds = config["output"].get("dump_rounds", False)
        self.show_dual = config["output"].get("show_dual_judge", True)
        self.do_self_check = config["output"].get("self_check", True)
        mcfg = config.get("memory", {})
        self.channels = tuple(
            MemoryChannel.check(c)
            for c in mcfg.get("channels", CHANNELS))
        self.use_content = "content" in self.channels
        self.use_context = "context" in self.channels
        self.use_self = "self" in self.channels
        self.self_memory = ""
        # ★ [第六期] 阴阳分歧度的**圈内暂存**（`_expand_pair` 算完 → 由
        #   `run()` 在同一圈内落到 view）。初始化防 AttributeError。
        self._quant_pending_yy = None
        # ★ [四层目标·第二期] 上一圈算出的**下一圈形状指引**（空串 = 不表态）。
        #   初始为空 ⇒ 第 1 圈不带指引（那时也确实还没有读数）。
        self._goal_hint_next = ""
        self.sp = sp if sp is not None else _spiral_for(config, entry)

    def vp(self, *args):
        if self.verbose:
            print(*args)

    def dump_round(self, view, inp) -> None:
        """ 每层每圈的**全量留痕**：把本圈 view 的所有字段写进日志。

        为什么要有它：此前每圈只打**摘要** —— 候选只报条数、ing 只报
        **字数**、悬置/债务/清算只报计数。正文与明细都不落日志，出问题只能
        从产物反推（而产物只留**最后一圈**的 view）。

        ★ 与产物 md 的「全量字段」附录同一条哲学：**不挑字段、机械全量** ——
          逐字段输出、**不截断**，动态挂上去的属性（如 `_expanded_descs`
          去重账）也一并带上。新增字段自动被覆盖，不会因为漏写一行
          print 而丢。

        [v1.21.69] 字段落盘收口到模块级 `dump_view_fields()`（唯一实现），
          本方法与 `dump_final` 共用；打完把这一刻的规范化快照挂到
          `view._dump_canon`，供收尾留痕做**增量**差分。
        """
        if not (self.verbose and self.dump_rounds):
            return
        _rnd = getattr(inp, "round_no", 0) or 0
        _role = (getattr(inp, "round_role", "") or "").strip()
        self.vp("")
        self.vp("╔" + "═" * 58 + "╗")
        self.vp(f"║ 圈全量留痕 · entry={self.entry} · 第 {_rnd} 圈"
                f" · {_role or '（无角色）'}")
        self.vp("╚" + "═" * 58 + "╝")
        self.vp("   ℹ️ 本段是**本圈**留痕；跨圈回填字段（roles_run / "
                "round_log / rounds_cap / carry_* 等）此处可能为空或仅本圈，"
                "最终值见该层收尾留痕。")
        dump_view_fields(view, self.vp, remember=True)

    def dump_final(self, view) -> None:
        """ **收尾留痕**：跑圈 + 回填之后补一段**增量**留痕。

        ★ 为什么需要它：每圈的 dump 发生在 `DGTF.run` 里，而
          `round_log` / `roles_run` / `carry_checks` / `carry_dropped_all`
          是**回填**的，回填发生在最后一圈 dump **之后** ⇒ 这几个字段
          在任何一段留痕里都恒为 0 项 ——「全量留痕」对它们从来没兑现过。
          实测 verif_V68.log 的 4 段留痕：这四个字段每段都是 0 项；
          每段 26k-31k 字符全由 candidates / rendered / untouched 撑着
          （逐圈内容，不是累积）。所以 v1.21.68 遗留 1 说的
          「n 圈约 n(n+1)/2 份重复」**不存在**，真问题正相反：没出口。

        ★ 增量而非全量：只打与上一圈 dump 有差异的字段，并交代省略了几个。
          差分基准 = `dump_round` 挂在 view 上的 `_dump_canon`。
        """
        if not (self.verbose and self.dump_rounds):
            return
        _rounds = int(getattr(view, "rounds_run", 0) or 0) or int(
            getattr(view, "rounds_cap", 0) or 0)
        _roles = " → ".join(str(r) for r in (getattr(view, "roles_run", [])
                                             or []))
        self.vp("")
        self.vp("╔" + "═" * 58 + "╗")
        self.vp(f"║ 收尾留痕 · entry={self.entry} · 共 {_rounds} 圈"
                f" · {_roles or '（无角色记录）'}")
        self.vp("╚" + "═" * 58 + "╝")
        dump_view_fields(view, self.vp,
                         prev=getattr(view, "_dump_canon", None))

    def _decidability_block(self, inp: Input) -> str:
        dr = inp.decidability_result or {}
        status = str(dr.get("decidability", "")).strip()
        reason = str(dr.get("reason", "")).strip()
        if not status and not reason:
            return ""
        lines = [
            "",
            "【全局可判定性评估（前置）】",
            f"  状态：{status or '（未标）'}",
        ]
        if reason:
            lines.append(f"  理由：{reason[:120]}")
        dec_aspects = dr.get("decidable_aspects", [])[:3]
        if dec_aspects:
            lines.append("  可判定方向：")
            for a in dec_aspects:
                lines.append(f"    - {str(a)[:80]}")
        und_aspects = dr.get("undecidable_aspects", [])[:3]
        if und_aspects:
            lines.append("  不可判定方向：")
            for a in und_aspects:
                lines.append(f"    - {str(a)[:80]}")
        lines.append(
            "  这是本层展开/判断的前置信息，供你参考：\n"
            "  不可判定方向上的候选，允许更多悬置、更多 both、更多未生；\n"
            "  可判定方向上的候选，尽量给出明确的 0/1 判断。"
        )
        return "\n".join(lines)

    def _assess_decidability(self, question: str,
                             anchors: Optional[List[dict]] = None) -> dict:
        system = """你是【问题可判定性评估者】。

判断一个问题的可判定性，输出三态之一：
- decidable：主要由可判定子问题构成
- partial：可判定与不可判定子问题并存
- undecidable：主要由不可判定子问题构成

【不可判定的特征（满足任一项）】
1. 预设了无法获得的参照系
2. 无法设计判决实验
3. 是本体论判断而非经验判断
4. 是自指循环
5. 信息不足：你没有渠道获得该问题的具体答案（即使它在世界上客观存在，
   例如「某人今天早餐吃了什么」「某人的 Wi-Fi 密码」——你查不到，就归
   不可判定，而不是因为"世界上有答案"就判可判定）

【可判定的特征（满足任一项）】
1. 可通过操作化定义转化为可测命题
2. 有明确的判决实验
3. 是经验问题或定义问题

【★ 关键原则】
- 若问题同时含可判定和不可判定子问题，必判 partial
- 必须同时列出 decidable_aspects 和 undecidable_aspects（可空）
- ★ 判断的是「你（评估者）现在能否得出答案」，不是「这个问题在世界上
  有没有客观答案」。可判定 = 你凭已有知识/常识/可执行的推理就能给出结论；
  若答案只能靠你访问不到的外部事实（具体某人的隐私、未发生的未来、
  未观测的私事），即使世界里有答案，也判 undecidable。

严格 JSON：
{
  "decidability": "decidable|partial|undecidable",
  "reason": "80字内",
  "features": ["命中的特征，最多3条"],
  "decidable_aspects": ["可判定的方面，最多5条"],
  "undecidable_aspects": ["不可判定的方面，最多5条"]
}
"""
        _anchor_sys = ""
        _anchor_user = ""
        if anchors:
            _a_lines = []
            for _a in anchors:
                _ln = "- [" + str(_a.get("id")) + "] " + str(_a.get("claim"))
                if _a.get("source"):
                    _ln = _ln + "（来源：" + str(_a.get("source")) + "）"
                _a_lines.append(_ln)
            _anchor_sys = (
                "\n\n【外部事实锚点】\n"
                "下面会附上本次运行前由外部检索得到的真实事实条目。它们是**校验参照**：\n"
                "- 只在某条事实能支撑或反驳某个方面时引用它，不要凭空扩写；\n"
                "- 用到的条目把编号填进 anchor_refs；一条都没用到就给空列表；\n"
                "- 锚点没覆盖到的方面照常按你自己的知识判，不要因为没锚点就判"
                "不可判定，也不要因为有锚点就判可判定。\n")
            _anchor_user = ("\n\n【外部事实锚点（" + str(len(anchors)) + " 条）】\n"
                            + "\n".join(_a_lines))
        try:
            raw = self.llm.call(system + _anchor_sys,
                                f"【问题】\n{question}" + _anchor_user,
                                0.2, 1100, json_mode=True,
                                stage="assess_decidability")
        except Exception as e:
            logger.warning("可判定性评估失败: %s", e)
            return {"decidability": "decidable", "reason": "评估失败",
                    "features": [], "decidable_aspects": [],
                    "undecidable_aspects": []}
        data = self.llm.parse_json(raw) or {}
        status = str(data.get("decidability", "decidable")).lower()
        if status not in ("decidable", "partial", "undecidable"):
            status = "decidable"

        def _list(key):
            v = data.get(key, [])
            if not isinstance(v, list):
                return []
            return [str(x)[:120] for x in v[:5]]

        dec_aspects = _list("decidable_aspects")
        und_aspects = _list("undecidable_aspects")

        original_status = status
        status = _normalize_decidability(status, dec_aspects, und_aspects,
                                        where="外部评估")

        _refs: List[str] = []
        if isinstance(data.get("anchor_refs"), list):
            _valid = set(str(_a.get("id")) for _a in (anchors or []))
            _refs = [str(x)[:40] for x in data["anchor_refs"][:8]
                     if str(x) in _valid]

        return {"decidability": status,
                "reason": str(data.get("reason", ""))[:200],
                "features": _list("features"),
                "decidable_aspects": dec_aspects,
                "undecidable_aspects": und_aspects,
                "_original_status": original_status,
                "anchor_refs": _refs,
                "_anchors_given": len(anchors or [])}

    def _self_block(self) -> str:
        if not self.use_self or not self.self_memory:
            return ""
        return (
            "\n【你上一次是谁】（这是记忆，不是要求，也不要模仿它的腔调）\n"
            f"{self.self_memory}\n"
        )

    def _pool_shape(self, pool: "Pool", label: str = "") -> str:
        cfg = self.config.get("memory", {})
        limit = int(cfg.get("shape_items", 6))
        bits = [f"  & {a.get('desc', '')}" for a in pool.amps[-limit:]]
        bits += [f"  ... {t.get('desc', '')}" for t in pool.threads[-limit:]]
        bits += [f"  ? {p.get('question', '')}" for p in pool.probes[-limit:]]
        bits += [f"  ⏸ {s.get('target', '')}"
                 for s in pool.suspensions[-limit:]
                 if s.get("status") in ("active", "stable")]
        bits += [f"  ⏳ {d.get('sub_question', '')}（回访：{d.get('revisit_condition', '')}）"
                 for d in pool.deferrals[-limit:]
                 if d.get("status") == "deferred"]
        bits += [f"  ⚔️ {s.get('target', '')}（{s.get('quadrant', '')}）"
                 for s in pool.duel_suspensions[-limit:]
                 if s.get("status") in ("active", "stable")]
        refs = [r for r in (pool.refinements or [])][-limit:]
        for r in refs:
            bits.append(f"  ↻ 深入子问题[{r.get('sub_id')}]："
                        f"{r.get('how', '')[:40]}")
        if pool.decidable_channel.get("last_coverage"):
            bits.append(f"  📗 可判定覆盖 {pool.decidable_channel['last_coverage']:.2f}")
        if pool.undecidable_channel.get("last_clarity"):
            bits.append(f"  📘 不可判定清晰度 {pool.undecidable_channel['last_clarity']:.2f}")
        _uc = pool.undecidable_channel
        if "indep_history" in _uc:
            _ir = _uc.get("last_indep_ratio")
            if _ir is not None:
                bits.append(f"  📘 不可判定独立度 {_ir:.2f}"
                            f"（独立结构不与评估阶段方面重合的比例）")
        elif _uc.get("last_struct_coverage"):
            bits.append(f"  📘 不可判定结构覆盖 "
                        f"{_uc['last_struct_coverage']:.2f}")
        body = "\n".join(bits)
        return f"{label}\n{body}" if body else f"{label}\n（空）"

    def _call_long(self, system, user, temperature, max_tokens,
                   model=None, max_cont: int = 2,
                   thinking=None, stage=None) -> Tuple[str, bool]:
        text = self.llm.call(system, user, temperature, max_tokens,
                             model=model, thinking=thinking, stage=stage)
        n = 0
        while self.llm.last_truncated and n < max_cont:
            n += 1
            tail = text[-1200:]
            self.vp(f"   ⚠️ 输出被长度掐断，续跑第 {n}/{max_cont} 次")
            cont_system = system + (
                "\n\n【续写】上一次输出因为长度限制被掐断。"
                "现在从它的断点处继续往下写。\n"
                "不要重述已经写过的部分，不要道歉，不要加开场白，\n"
                "不要写'继续'这类标题，直接从断点那句话接下去。"
            )
            cont_user = (
                f"{user}\n\n"
                f"【已经写到这里（最后一段）】\n…\n{tail}\n\n"
                "【从这里继续】把没走完的步骤接着走完。"
            )
            try:
                more = self.llm.call(cont_system, cont_user, temperature,
                                     max_tokens, model=model,
                                     thinking=thinking, stage=stage)
            except Exception as e:
                logger.warning("续跑失败: %s", e)
                # ★ 续跑失败 = 没补完 = 仍截断。上一次 call 开头把
                #   last_truncated 重置成 False，若不改回，下游会误以为
                #   text 是完整的 —— 静默失败。
                self.llm.last_truncated = True
                break
            if not more.strip():
                self.llm.last_truncated = True
                break
            text = text + more
        return text, self.llm.last_truncated

    def run(self, inp: Input) -> View:
        if self.use_self and inp.self_memory:
            self.self_memory = inp.self_memory
        view = View(entry=self.entry)
        pool = inp.pool if inp.pool is not None else Pool()

        # 第 1 步：锚点重述
        if _action_on(self.config, "re_anchor"):
            view.anchor, _anchor_touched, anchor_untouched = \
                self._re_anchor(inp)
        else:
            if self.entry in ("both", "all") and inp.root_question:
                view.anchor = inp.root_question.strip()
            elif inp.is_base:
                view.anchor = (inp.question or "")[:120]
            else:
                view.anchor = (inp.root_question or "")[:120]
            anchor_untouched = []
            _anchor_touched = []
            self.vp("   🪞 锚点重述：已关闭（用透传/原文）")
        # ★ [第六期 · 依据 ①] 锚点对**原问题**的保真度（零成本纯函数）。
        #   BenchDrift(arXiv:2608.11694)：含义保持的重述会让答案漂移，
        #   且**强模型损失更大** ⇒ 这里是最上游的闸门（重述跑偏则下游全白跑）。
        try:
            _q0 = str(inp.root_question or inp.question or "")
            _rf = restate_fidelity(_q0, str(view.anchor or ""))
            if _rf.get("verdict"):
                self._quant_note(view, "restate_fidelity", _rf)
                if _rf["verdict"] == "drifted":
                    self.vp("   ⚑ 锚点保真度偏低 %.2f（关键词覆盖 %.2f）"
                            "——重述可能已跑偏，下游会跟着偏"
                            % (_rf["fidelity"] or 0.0, _rf["coverage"] or 0.0))
        except Exception:
            pass
        tag = "透传" if (self.entry in ("both", "all")
                        and inp.root_question) else "重述"
        self.vp(f"\n🪞 [锚点·{tag}] {view.anchor}")

        # [A1 方面单元] 双写：旧键照旧 + aspect_units 统一登记（带 id）。
        # ★ 触及侧 polarity="阳"（已显形）/ 未触及侧 polarity="阴"（未显形）
        #   —— 与阴阳展开臂的语义对齐（§3.1 A1）。
        for t in _anchor_touched:
            _u_t = view.add_aspect_unit(t, source="anchor", polarity="阳",
                                        ground="anchor")
            view.anchor_touched.append({"desc": t, "source": "anchor",
                                        "id": (_u_t or {}).get("id", "")})
        for u in anchor_untouched:
            _u_u = view.add_aspect_unit(u, source="anchor", polarity="阴",
                                        ground="anchor")
            # [A1 编号统一] `untouched` 必须带 `id` —— 渲染前缀与
            #   covers 靶子共用同一个编号，否则「A1」在两处指向不同物。
            view.untouched.append({"desc": u, "source": "anchor",
                                   "id": (_u_u or {}).get("id", "")})
        if _anchor_touched or anchor_untouched:
            self.vp(f"   🪞 锚点·触及 {len(_anchor_touched)} 条 / "
                    f"未触及 {len(anchor_untouched)} 条")

        # 第 2 步：阴阳展开
        candidates = self._expand(inp, pool, view.anchor)
        # ★ [第六期 · 依据 ②] 把阴阳分歧度落到本层 view（**真实入口**）。
        try:
            _yy = getattr(self, "_quant_pending_yy", None)
            if _yy:
                self._quant_note(view, "yin_yang_divergence", _yy)
                if _yy.get("verdict") == "fake_duel":
                    self.vp("   ⚑ 阴阳分歧度偏低 %.2f（重合 %.2f）"
                            "——两臂像复述，对撞未发生"
                            % (_yy.get("divergence") or 0.0,
                               _yy.get("max_sim") or 0.0))
            self._quant_pending_yy = None
        except Exception:
            pass
        # [P2-9] 自省回流的硬执行：上一圈点名禁掉的条目如果这一圈又写出来了，
        # 当场丢掉，不许它进 ingest / 判断 / 沉淀。
        # 丢之前先留痕 → view.carry_dropped，_check_carry_response 认这份账，
        # 否则会出现「已经拦下，核对却报零违例」的自相矛盾。
        # 关掉 memory.carry_feedback 时 banned 为空，这一步自然不生效。
        try:
            view._expanded_descs = [
                str(getattr(c, "desc", "") or "").strip()
                for c in candidates
            ]
        except Exception:
            pass
        candidates = self._drop_banned(candidates, inp, view)
        self.vp(f"   📋 展开候选 {len(candidates)} 条"
                + (f"（{len(view.carry_dropped)} 条触犯上一圈禁令已拦下）"
                   if view.carry_dropped else ""))
        if not candidates:
            self.vp("   ⚠️ 本次未展开出候选——这不是失败，是此处未生")

        # 第 3 步：对偶判断
        if _action_on(self.config, "dual_judge"):
            candidates = self._dual_judge(candidates, inp, view.anchor, view)
        else:
            self.vp("   🔮 对偶判断：已关闭（全部候选 position=0）")
        view.candidates = [c.to_dict() for c in candidates]
        amp_cands = [c for c in candidates if c.is_amp_candidate]
        self.vp(f"   🔮 & 候选 {len(amp_cands)} 条（属性≠位置）")
        try:
            view._amp_cand_count = len(amp_cands)
        except Exception:
            pass

        for c in candidates:
            if c.position == "0" and c.desc.strip():
                if not any(_similar(c.desc, x.get("desc", ""), 0.85)
                           for x in view.untouched):
                    _u_j = view.add_aspect_unit(c.desc, source="judge",
                                                polarity="阴", ground="anchor")
                    view.untouched.append({"desc": c.desc, "source": "judge",
                                           "id": (_u_j or {}).get("id", "")})
                    view.add_aspect_unit(c.desc, source="judge",
                                         polarity="阴", ground="judge")

        # 第 4 步：ing 对撞
        if _action_on(self.config, "ing"):
            try:
                view.collision = self._ing(candidates, inp, view.anchor, view)
                self.vp(f"   🔥 ing 输出 {len(view.collision)} 字")
                # ★ [第六期 · 依据 ④] ing 输出的**语义密度**（零成本纯函数）。
                #   信息瓶颈：>5 个无信息 token ⇒ 性能降 15%+ —— 低密度即提示。
                try:
                    _sd = semantic_density(view.collision)
                    if _sd is not None:
                        self._quant_note(view, "ing_density", {
                            "value": _sd, "chars": len(view.collision or ""),
                            "verdict": ("thin" if _sd < 0.6 else "ok")})
                        if _sd < 0.6:
                            self.vp(f"   ⚑ ing 语义密度偏低 {_sd:.2f}"
                                    f"（<0.60 ⇒ 填充语多，信息量薄）")
                except Exception:
                    pass
                for _ln in (view.collision or "").splitlines():
                    self.vp("   🔥 │ " + _ln)
                _upstream_texts: List[str] = []
                for _v in (inp.upstream_views or []):
                    _m = getattr(_v, "manifest", "") or ""
                    _c = getattr(_v, "collision", "") or ""
                    if _m:
                        _upstream_texts.append(_m)
                    if _c:
                        _upstream_texts.append(_c)
                # ★ [层目标 / 对撞] 融合率的分母 + CORE 停滞罚的比对语料
                #   必须**从真跑填**（否则读数恒 None ⇒ 对撞层无判别力）。
                #   ★ 放在 `if _upstream_texts:` **之外**：没有上游文本时
                #     也要留 `upstream_layers`（分母），否则「没有上游」
                #     与「没测」又混成一种。
                try:
                    view.upstream_layers = len(inp.upstream_views or [])
                    if _upstream_texts:
                        view.upstream_texts = list(_upstream_texts)
                except Exception:
                    pass
                if _upstream_texts:
                    _rr = _detect_ing_rephrase(
                        view.collision, _upstream_texts)
                    if _rr is not None:
                        # [P2-9] 复述率原来只挂在私有属性上，进不了 md。
                        # 模型在自省里说「没复述」、代码说 50% 复述时，
                        # 读产物的人要有这个数字才能自己判断谁对。
                        view.rephrase_ratio = float(_rr)
                        # ★ [层目标 / CORE] 复述率是「与上游的重合度」，
                        #   正是 CORE 的 semantic stagnation —— 直接出口它，
                        #   对撞层读数就用**引擎已算的这把尺子**，
                        #   而不是让 `_lg_stag_ratio` 另算一把（两把尺子会漂）。
                        try:
                            view.sem_stagnation = float(_rr)
                        except Exception:
                            pass
                        try:
                            # ★ 两个都要留：_apply_view_to_pool 的 culture/idle
                            #   判据读的是这个私有属性，别只留公有字段。
                            view._ing_rephrase_ratio = _rr
                        except Exception:
                            pass
                        if _rr >= 0.5:
                            self.vp(f"   ⚠️ ing 复述率 {_rr:.0%}"
                                    f"（超过 0.5，直接检测）")
                if self.config.get("output", {}).get("show_ing", False):
                    self.vp("")
                    self.vp("┌" + "─" * 58)
                    self.vp("│ 【ing 全文】")
                    self.vp("├" + "─" * 58)
                    for ln in (view.collision or "").splitlines():
                        self.vp("│ " + ln)
                    self.vp("└" + "─" * 58)
            except Exception as e:
                view.add_error("ing", e)
                view.collision = ""
                self.vp(f"   ✗ ing 失败：{e}")
        else:
            view.collision = "（此处未生）"
            self.vp("   🔥 ing 对撞：已关闭")

        # 第 5 步：& 沉淀
        if _action_on(self.config, "he"):
            try:
                amps, threads, meta, extra = self._he(
                    view.collision, amp_cands, pool, inp)
            except Exception as e:
                view.add_error("&", e)
                amps, threads, meta, extra = [], [], [], {}
        else:
            amps, threads, meta, extra = [], [], [], {}
            self.vp("   & 沉淀：已关闭")

        if extra:
            view.decidable_product = extra.get("decidable_product", {}) or {}
            view.undecidable_product = extra.get("undecidable_product", {}) or {}
            # ★ [LDG 修真] 缺省从 1.0 改 None：
            #   「模型没报」不许冒充「离得最远」（与上一版修
            #   touch_rate 同族：默认值不得冒充读数）。
            _d2q_raw = extra.get("distance_to_question")
            try:
                view.distance_to_question = (
                    None if _d2q_raw is None else float(_d2q_raw))
            except (TypeError, ValueError):
                view.distance_to_question = None
            view.covered_aspects = list(extra.get("covered_aspects") or [])
            view.uncovered_aspects = list(extra.get("uncovered_aspects") or [])

        sp_he = self.sp
        amps, drop_a = drop_rehashes(amps, pool.amps, sp_he)
        threads, drop_t = drop_rehashes(threads, pool.threads, sp_he)
        view.rehashed = [dict(d, kind="&") for d in drop_a] + \
                        [dict(d, kind="线头") for d in drop_t]
        if view.rehashed:
            self.vp(f"   🚫 翻回老地方 {len(view.rehashed)} 条"
                    f"（换个说法再说一遍，入池前就挡）")
        view.amps = amps
        view.threads = threads
        view.meta = meta

        _role_now = (inp.round_role or "").strip()
        # 档位维度已删除 ⇒ 探针不再按角色跳过（回到「不省」）。
        _skip_probe = False
        if _action_on(self.config, "phase_probe") and not _skip_probe:
            try:
                view.probes = self._phase_probe(view, inp, pool)
                if view.probes:
                    self.vp(f"   🌱 探针回归 {len(view.probes)} 个自问")
                else:
                    self.vp("   🌱 探针回归：此处无自问可回归（允许空）")
            except Exception as e:
                view.add_error("探针回归", e)
                view.probes = []
                self.vp(f"   ✗ 探针回归失败：{e}")
        else:
            if _skip_probe:
                self.vp(f"   🌱 探针回归：成本档跳过"
                        f"（{_role_now}圈不再开新面）")
            else:
                self.vp("   🌱 探针回归：已关闭")
            view.probes = []
            if _skip_probe:
                view.probe_skipped = True

        # 质量检查
        view.quality_flags = self._quality_check(
            view, pool, round_no=inp.round_no or 0)
        view.quality_verdict = self._quality_verdict(view.quality_flags)
        if view.quality_flags:
            self.vp(f"   ⚑ 质量线索：{', '.join(view.quality_flags)}")
            self.vp(f"   ⚖ 质量评价：{view.quality_verdict}")

        # view 生成
        if _action_on(self.config, "manifest"):
            view.manifest = self._manifest(view, inp)
            if view.manifest:
                self.vp(f"   🌕 view 显形 {len(view.manifest)} 字")
                if self.config.get("output", {}).get("show_manifest", False):
                    self.vp("")
                    self.vp("┌" + "─" * 58)
                    self.vp("│ 【view 全文】")
                    self.vp("├" + "─" * 58)
                    for ln in view.manifest.splitlines():
                        self.vp("│ " + ln)
                    self.vp("└" + "─" * 58)
        else:
            view.manifest = "（manifest 动作已关闭）"
            self.vp("   🌕 view 生成：已关闭")

        # self-check
        if _action_on(self.config, "self_check"):
            view.self_check = self._self_check(view)
            if view.self_check.get("notes"):
                self.vp(f"   🔍 self-check: {view.self_check['notes']}")
            _sc_c_list = view.self_check.get("suspicious_candidates") or []
            if len(_sc_c_list) >= 5:
                if not any("candidates_backfilled" in f
                           for f in view.quality_flags):
                    view.quality_flags.append(
                        f"candidates_backfilled(sc:{len(_sc_c_list)})")
                    view.quality_verdict = self._quality_verdict(
                        view.quality_flags)
                    self.vp(f"   ⚑ [self-check 联动] 可疑候选 "
                            f"{len(_sc_c_list)} >= 5，"
                            f"追加 candidates_backfilled")

        view.rendered = self._render(view, inp)

        self.dump_round(view, inp)

        return view

    # ---------- 锚点重述 ----------
    def _re_anchor(self, inp: Input):
        if self.entry in ("both", "all") and inp.root_question:
            return inp.root_question.strip(), [], []

        chars = int(self.config.get("memory", {}).get("shape_chars", 900))
        pool = inp.pool or Pool()
        if inp.is_base:
            base = inp.question
            ctx = "（第一层）"
        else:
            base = "\n\n".join(
                View.shape_of(v)[:chars] for v in inp.upstream_views)
            shapes = [
                self._pool_shape(p, f"【上游池 {i}】")
                for i, p in enumerate(inp.upstream_pools, 1)]
            ctx = "\n\n".join(shapes) or "（无上游池）"
        if pool.amps or pool.threads or pool.probes:
            ctx += "\n\n" + self._pool_shape(pool, "【本层池】")

        system = (
            "你是【锚点重述者】。\n"
            "把输入重述成当下要处理的那个问题/处境。\n"
            "不改变本质，只让它成为'此刻的问题'。\n"
            f"{self.phase.anchor}\n"
            "【★ 重述必须带出两半】\n"
            "  · touched：这句话里**已经被触及、已经被指向**的方面（0-4 条）\n"
            "    —— 重述之后你重新看见的、原本就在里面的东西\n"
            "  · untouched：这句话里**还没被触及、还没被展开**的方面（0-4 条）\n"
            "  ★ touched 是重述真的发生了的证据。如果 touched 空着，\n"
            "    说明这次只是在换说法，没有真的重述。\n"
            "严格 JSON：\n"
            '{"anchor":"≤80字一句话","touched":["≤30字"],"untouched":["≤30字"]}\n'
            + ANTI_PRETTY
            + self._self_block()
        )
        dec_block = self._decidability_block(inp)
        user = f"【输入】\n{base}\n{dec_block}\n\n【上下文】\n{ctx}"
        try:
            raw = self.llm.call(system, user, 0.3, 500, json_mode=True, stage=_thinking_stage(self.config, 're_anchor'))
            data = self.llm.parse_json(raw) or {}
            anchor = str(data.get("anchor", "")).strip()

            _ANCHOR_PLACEHOLDERS = (
                "此处未生", "（此处未生）", "(此处未生)",
                "无", "（无）", "(无)", "暂无", "未知", "n/a", "N/A",
            )

            def _clean(key, n=4):
                v = data.get(key, [])
                if not isinstance(v, list):
                    return []
                out = []
                for x in v:
                    s = str(x).strip()[:60]
                    if not s:
                        continue
                    if s in _ANCHOR_PLACEHOLDERS:
                        continue
                    if s.replace("（", "(").replace("）", ")") \
                            in _ANCHOR_PLACEHOLDERS:
                        continue
                    out.append(s)
                return out[:n]

            touched = _clean("touched")
            untouched = _clean("untouched")
            if not anchor:
                anchor = raw.strip().split("\n")[0][:120]
            return anchor, touched, untouched
        except Exception:
            return base[:120], [], []

    # ---------- 阴阳展开 ----------
    def _expand(self, inp: Input, pool: Pool, anchor: str) -> List[Candidate]:
        seeds = inp.seed_probes or []
        role, rno = inp.round_role, inp.round_no
        if inp.is_base:
            return self._expand_from_question(
                inp.question, pool, anchor, seeds, role, rno, inp)
        return self._expand_from_views(
            inp.upstream_views, pool, anchor, seeds, inp.context,
            inp.upstream_pools, role, rno, inp)

    def _drop_banned(self, candidates: List["Candidate"], inp: "Input",
                     view: "View") -> List["Candidate"]:
        """把命中上一圈禁令的候选当场丢掉。

        [P2-9] [P2-7] 只记不看：自省点名「候选 7、9 是补写凑数」，
        下一圈照样原样出现，回流核对写着「违例 1 条」，然后什么都没发生。
        现在改成硬执行 —— 命中即丢，丢完还要留痕，
        让「这一轮到底挡掉了什么」成为产物的一部分。
        """
        carry_c = inp.carry_constraints or []
        if not carry_c:
            return candidates
        banned: List[str] = []
        for c in carry_c:
            if c.get("kind") != "candidate":
                continue
            for b in (c.get("banned") or []):
                b = str(b).strip()
                if b and b not in banned:
                    banned.append(b)
        if not banned:
            return candidates
        kept: List["Candidate"] = []
        dropped: List[dict] = []
        hit_idx: List[int] = []
        for i, cand in enumerate(candidates):
            d = str(getattr(cand, "desc", "") or "").strip()
            if d and _banned_hit(d, banned):
                hit_idx.append(i)
        # [P2-9] 拦一半留一半，且至少留一条。
        # 不留的后果在 mock 里直接暴露过：某一圈的候选全部命中禁令 →
        # 全丢 → _self_check 因「无候选无 &」早退 → 这一圈没有自省 →
        # 下一圈没有 carry → 整层塌成一圈后熄火。硬执行把整个反馈环
        # 一起掐掉，比放任它重复更糟。
        # 留一条也是留一口气：review 还能跑，下一圈的约束还能生成。
        budget = len(candidates) // 2
        if budget > 0 and hit_idx:
            # 后补的条目通常堆在后面（自省点名的「候选 9-15」就是），
            # 预算不够时优先拦下标靠后的那些。
            do_drop = set(sorted(hit_idx, reverse=True)[:budget])
        else:
            do_drop = set()
        for i, cand in enumerate(candidates):
            if i in do_drop:
                d = str(getattr(cand, "desc", "") or "").strip()
                dropped.append({"desc": d,
                                "ban": _banned_hit(d, banned)})
                self.vp(f"   🗑 [回流硬执行] 拦下重现候选：{_vp_preview(d)}")
                continue
            kept.append(cand)
        if dropped:
            view.carry_dropped = dropped
        if len(hit_idx) > len(do_drop):
            self.vp(f"   ⚠ [回流硬执行] 本圈 {len(hit_idx)} 条命中禁令，"
                    f"只拦 {len(do_drop)} 条（保底留一半）")
        return kept

    # ---------- 阴阳展开的并行执行壳 [perf-104] ----------
    def _expand_pair(self, order, build_user) -> List[Candidate]:
        '''阴 / 阳两次展开是互不依赖的 LLM 调用，并行发出。

        设计 9.1 把「阴阳展开」列为可并行点：每层每圈省一次往返。
        **解析必须串行、且严格按 order 顺序**——去重的 seen 依赖先后，
        乱序解析会改变产物，也会让「阴在前还是阳在前」的层配置失效。
        '''
        jobs = []
        for label, prompt in order:
            key = "expand_yin" if label == "阴" else "expand_yang"
            if not _action_on(self.config, key):
                self.vp(f"\n💧 [{label}视角] 已关闭")
                continue
            # [P2-2][P2-9] 每次调用都带上「宁可空，不要凑」——
            # 八个展开 prompt 共用这一条，不必各自抄一遍。
            # ★ 置顶而不是追加：追加在末尾时它排在「能写几条写几条」
            #   之后成了补充说明，实测依然会为了凑满上限而灌水。
            #   放在最前面，它是这一轮展开的第一约束。
            jobs.append((label, NO_FILL_RULE + prompt, build_user(label)))
        if not jobs:
            return []


        raws: Dict[str, Optional[str]] = {}
        # ★ [第六期 L1 · 降本] 阴阳合并成**一次**调用（opt-in，默认关）。
        #   依据：Tokonomics 2025（批处理是第一降本杠杆）+ 信息瓶颈
        #   （阴阳 user 完全相同 ⇒ 第二份是**无信息输入**）。
        #   ★ 开关默认 false ⇒ 与历史行为**逐字一致**（零行为差）。
        #   ★ 只合并恰好两臂的情形；单臂（另一开关关掉）走原路径。
        if len(jobs) == 2 and _action_on(self.config, "merge_expand", False):
            _mg = self._expand_pair_merged_once(jobs)
            if _mg is not None:
                return _mg
            # 合并失败 ⇒ 落回原路径（下方并行/串行），**不丢内容**。
            self.vp("   ↩ 合并展开不可用，回落两臂独立调用")
        parallel = (len(jobs) > 1
                    and _action_on(self.config, "parallel_expand"))
        if parallel:
            with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
                futs = {
                    ex.submit(self.llm.call, prompt, user, 0.9, 1500): label
                    for label, prompt, user in jobs
                }
                for f, label in futs.items():
                    try:
                        raws[label] = f.result()
                    except Exception as e:
                        logger.warning("展开失败(%s): %s", label, e)
                        self.vp(f"   ✗ {label}展开失败：{e}")
        else:
            for label, prompt, user in jobs:
                try:
                    raws[label] = self.llm.call(prompt, user, 0.9, 1500)
                except Exception as e:
                    logger.warning("展开失败(%s): %s", label, e)
                    self.vp(f"   ✗ {label}展开失败：{e}")

        seen: List[str] = []
        out: List[Candidate] = []
        for label, _prompt, _user in jobs:
            raw = raws.get(label)
            if raw is None:
                continue
            self.vp(f"\n💧 [{label}视角]")
            self.vp(f"   {_vp_preview(raw)}")
            for line in raw.splitlines():
                c = self._parse_candidate_line(line)
                if not c:
                    continue
                if any(_similar(c.desc, s, _DUP_SIM) for s in seen):
                    continue
                seen.append(c.desc)
                c.source = label
                out.append(c)
        # ★ [第六期 · 依据 ②] 阴阳两臂的**分歧度**（SIEV 对抗性依从率）。
        #   低分歧 ⇒ 假对撞（只是换个说法复述），出读数作下游线索。
        try:
            _by = {}
            for _c in out:
                _by.setdefault(str(getattr(_c, "source", "") or ""), []).append(
                    str(getattr(_c, "desc", "") or ""))
            if len(_by) >= 2:
                _ks = list(_by.keys())
                _yy = yin_yang_divergence(_by[_ks[0]], _by[_ks[1]])
                if _yy:
                    self._quant_pending_yy = _yy
        except Exception:
            pass
        return out

    def _expand_pair_merged_once(self, jobs):
        """ ① 阴阳合并成一次调用；失败返回 None。

        阴阳的 user 内容完全相同（锚点/池/自问对两个视角是一样的），
        只有 system 里的「视角」不同。合并后省掉重复的 user 输入 token。
        输出用一行「----阳----」作分段标记，先阴后阳。

        ★ 兜底：模型没按标记分段时，补跑缺的那半边，而不是静默把它
          丢掉。这样最坏情况退化成原来的两次调用（不亏），不会丢内容。
        """
        (label0, prompt0, user0), (label1, prompt1, user1) = jobs
        # prompt1 只取主体：去掉开头的 NO_FILL_RULE（prompt0 已带一份）
        # 和尾部的 ANTI_PRETTY + self_block（合并段末尾统一带一份）。
        _p1 = prompt1
        if _p1.startswith(NO_FILL_RULE):
            _p1 = _p1[len(NO_FILL_RULE):]
        p1_body = (_p1.split(ANTI_PRETTY)[0] if ANTI_PRETTY in _p1 else _p1)
        marker = f"===== {label1} ====="
        merged_system = (
            f"{prompt0}\n\n"
            f"== 以上是{label0}视角。输出完这段候选后，**继续**在同一个"
            f"回答里完成{label1}视角 ==\n\n"
            f"{p1_body}\n\n"
            f"{ANTI_PRETTY}\n"
            f"{self._self_block()}\n\n"
            f"输出分两段：先输出{label0}视角的候选，"
            f"然后**单独一行**原样输出「{marker}」，"
            f"再输出{label1}视角的候选。"
            f"那一行除了「{marker}」不许有别的内容，"
            f"这是机器用来切段的，改了就切不开。\n"
            f"每行候选仍是 '- [kind] 描述（20-80字）'。"
        )
        raw = None
        try:
            raw = self.llm.call(merged_system, user0, 0.9, 2600)
        except Exception as e:
            logger.warning("合并展开失败: %s", e)
            return None

        self.vp(f"\n💧 [合并展开 {label0}+{label1}]")
        self.vp(f"   {_vp_preview(raw or '')}")
        # 分段：先精确匹配标记；再容错（整行只含阳字与符号）；
        # 都没有则补跑，不静默丢内容。
        _raw = raw or ""
        seg0, seg1 = _raw, None
        if marker in _raw:
            seg0, _, seg1 = _raw.partition(marker)
        else:
            _m = re.search(
                r"^\s*[-=#*>\s]*" + re.escape(label1) + r"\s*[-=#*>\s]*$",
                _raw, re.M)
            if _m:
                seg0, seg1 = _raw[:_m.start()], _raw[_m.end():]
        if seg1 is None:
            self.vp(f"   ⚠️ 合并输出缺「{marker}」分段标记，"
                    f"补跑{label1}视角（不丢内容）")
            try:
                seg1 = self.llm.call(prompt1, user1, 0.9, 1500) or ""
            except Exception as e:
                logger.warning("补跑%s失败: %s", label1, e)
                seg1 = ""

        seen: List[str] = []
        out: List[Candidate] = []
        for label, seg in ((label0, seg0), (label1, seg1)):
            for line in seg.splitlines():
                c = self._parse_candidate_line(line)
                if not c:
                    continue
                if any(_similar(c.desc, s, _DUP_SIM) for s in seen):
                    continue
                seen.append(c.desc)
                c.source = label
                out.append(c)
        return out

    @staticmethod
    def _role_text(role: str, round_no: int = 0) -> str:
        if not role:
            return ""
        # [P2-7] 「转向」「复裁」是 [P1-5] 自省回流注入时改出来的 role，
        # 原先这里没有对应文案 → 返回空串 → 【本轮形状】整块消失。
        # 一带回流反而少了一段约束，这是 carry 看着没生效的一个原因。
        body = {
            "摊开": "这是本层的**第 1 轮 · 摊开**：先别急着深入，把能看见的面铺开。"
                    "广度优先——能摆出来的都摆出来，不必每条都追到底。",
            "深入": "这是本层的**深入轮**：面已经铺过，这一轮往里走。"
                    "带着上面给出的重点往深里去，不要重铺一遍已经铺过的面。",
            "收束": "这是本层的**收束轮**：不再开新面。把已经走到的收拢成形，"
                    "能定下来的定下来，开不了的就如实说此处未生。",
            "转向": "这是本层的**转向轮**：上一圈的自我回看判定这一圈"
                    "踩在复述或凑数上。不要沿着上一圈的路再走一遍——"
                    "换一个切面进去，先回应下面【硬约束】里点名的问题，"
                    "再谈别的。",
            "复裁": "这是本层的**复裁轮**：上一圈该裁的没裁、或裁成了 both。"
                    "这一轮不再开新面，把悬着的张力重新过一遍，"
                    "能定成 0 或 1 的就定，实在定不了要说清缺的是什么，"
                    "不要用 both 搪塞。",
        }.get(role, "")
        if not body:
            return ""
        return (f"\n\n【本轮形状 · 第 {round_no} 轮 · {role}】\n{body}")

    @staticmethod
    def _seed_text(seeds) -> str:
        if not seeds:
            return "（无）"
        return "\n".join(
            f"  - {p.get('question','')}（回来：{p.get('link','')}"
            f"｜增益{p.get('expected_gain','?')}）"
            for p in seeds[:8])

    @staticmethod
    def _carry_block_text(carry, kind: str = "any") -> str:
        """[P2-7] 把上一圈 self-check 的结论渲染成硬约束块。

        kind 用于分流：候选类约束进对偶判断、ing 类进 ing，
        免得每条约束在所有环节都出现一遍（出现太多次等于没有）。
        """
        items = [c for c in (carry or [])
                 if isinstance(c, dict)
                 and str(c.get("text", "")).strip()
                 and (kind == "any" or c.get("kind") in (kind, "any"))]
        if not items:
            return ""
        lines = "\n".join(f"  C{i+1}. {str(c.get('text', '')).strip()}"
                          for i, c in enumerate(items[:4]))
        return (
            "\n【★ 上一圈 self-check 的硬约束 · 必须回应，不是参考】\n"
            + lines +
            "\n  这些是上一圈的自我回看点名的问题。本圈必须先避开/补上它们，\n"
            "  再谈别的。做不到就明说为什么做不到，不要默默照旧。\n"
        )

    def _expand_from_question(self, question, pool, anchor,
                              seeds=(), role="", round_no=0,
                              inp=None) -> List[Candidate]:
        if self.entry == "both":
            pair = (self._both_yin_prompt(), self._both_yang_prompt())
        elif self.entry == "all":
            pair = (self._all_yin_prompt(), self._all_yang_prompt())
        else:
            pair = (self._yin_prompt(), self._yang_prompt())
        order = (
            [("阴", pair[0]), ("阳", pair[1])]
            if self.phase.expand_order == "yin_first"
            else [("阳", pair[1]), ("阴", pair[0])]
        )
        pool_text = self._pool_text(pool)
        seed_text = self._seed_text(seeds)
        dec_block = self._decidability_block(inp) if inp else ""
        # [P2-7] 硬约束块放最前：写在最后会被当成补充说明滑过去。
        carry_block = self._carry_block_text(
            getattr(inp, "carry_constraints", None) or [])

        goal_hint = str(getattr(self, "_goal_hint_next", "") or "")

        def build_user(label):
            return (
                f"{carry_block}\n"
                f"【原始问题】\n{question}\n\n"
                f"【锚点重述】\n{anchor}\n"
                f"{self._role_text(role, round_no)}\n"
                f"{goal_hint}\n"
                f"{dec_block}\n\n"
                f"【上一圈没带走的自问】\n{seed_text}\n\n"
                f"【池】\n{pool_text}"
            )
        return self._expand_pair(order, build_user)

    def _expand_from_views(self, views, pool, anchor,
                           seeds=(), context="",
                           upstream_pools=(), role="",
                           round_no=0, inp=None) -> List[Candidate]:
        views_text = "\n\n".join(
            View.shape_of(v) for v in views
        )
        pool_text = self._pool_text(pool)
        seed_text = self._seed_text(seeds)
        ctx_block = (
            "\n\n【背景】（这是来路，不是要求：它只影响你怎么看，"
            "不要把它当成要展开的东西）\n" + context
        ) if (self.use_context and context) else ""

        up_block = ""
        if self.use_content and upstream_pools:
            bits = []
            for i, p in enumerate(upstream_pools):
                v = views[i] if i < len(views) else None
                ent = getattr(v, "entry", "") if v is not None else ""
                tag = _LAYER_LABEL.get(ent, f"上游{i+1}")
                bits.append(self._pool_shape(p, f"[{tag}层针对本问题的沉淀]"))
            up_block = ("\n\n【上游层的池 · 同一问题下的各自沉淀】"
                        "（这些是上游各自留下的东西，是本层的输入；"
                        "它们是**同一个问题**的不同切面，不是新话题）\n"
                        + "\n\n".join(bits))

        q_block = ""
        if self.entry == "both" and self.use_content:
            q_text = _quadrant_text(getattr(pool, "duel_alignment", None) or {})
            if q_text:
                q_block = ("\n\n【四象限对齐】（修行悬置 × 研究延迟债务："
                           "这是本轮的输入之一，不是要你复述的背景）\n"
                           + q_text)

        pair = ((self._both_yin_prompt(), self._both_yang_prompt())
                if self.entry == "both"
                else (self._all_yin_prompt(), self._all_yang_prompt()))
        order = ([("阴", pair[0]), ("阳", pair[1])]
                 if self.phase.expand_order == "yin_first"
                 else [("阳", pair[1]), ("阴", pair[0])])

        dec_block = self._decidability_block(inp) if inp else ""
        anchor_block = (
            "【原始问题 · 本层锚点（透传，不重写）】\n"
            f"{anchor}\n"
            "（下面每一项——上游 view / 四象限 / 上游池——都是**这同一个问题**"
            "的不同切面。它们只提供角度，不改写问题；"
            "展开始终回到上面的这个问题。）\n"
        )

        # [P2-7] 同 _expand_from_question：硬约束块置顶。
        carry_block = self._carry_block_text(
            getattr(inp, "carry_constraints", None) or [])

        goal_hint = str(getattr(self, "_goal_hint_next", "") or "")

        def build_user(label):
            return (
                f"{carry_block}\n"
                f"{anchor_block}\n"
                f"{self._role_text(role, round_no)}\n"
                f"{goal_hint}\n"
                f"{dec_block}\n\n"
                f"【上游的 view · 同一问题下的各自显形】\n{views_text}\n\n"
                f"【上一圈没带走的自问】\n{seed_text}\n"
                f"{q_block}"
                f"{up_block}"
                f"{ctx_block}\n\n【本层的池】\n{pool_text}"
            )
        return self._expand_pair(order, build_user)

    # ---------- 四套视角 prompt ----------
    def _yin_prompt(self) -> str:
        return (
            "你处于【0 · 阴视角】。\n"
            "0 是尚未显形的那一面。\n"
            "从锚点里看出去，找出还没显形的部分。\n"
            "能写几条写几条（8 是上限，不是要交的作业量）。"
            "展开几条就写几条；一条都展开不出来就只输出一行：'（无）'\n"
            "每行格式：- [kind] 描述（20-80字）\n"
            "kind: concept/event/person/object/startpoint/question/thread/other\n"
            "不要解释，不要标题。\n"
            + ANTI_PRETTY
            + self._self_block()
        )

    def _yang_prompt(self) -> str:
        return (
            "你处于【1 · 阳视角】。\n"
            "1 是已经显形的那一面。\n"
            "从锚点里看出去，找出已经显形的部分。\n"
            "能写几条写几条（8 是上限，不是要交的作业量）。"
            "展开几条就写几条；一条都展开不出来就只输出一行：'（无）'\n"
            "每行格式：- [kind] 描述（20-80字）\n"
            "kind: concept/event/person/object/startpoint/question/thread/other\n"
            "不要解释，不要标题。\n"
            + ANTI_PRETTY
            + self._self_block()
        )

    def _both_yin_prompt(self) -> str:
        return (
            "你处于【对撞 · 阴视角】。\n"
            "两个 view 已经给出。\n"
            "这里的 0 是：两个 view 之间还不对齐、还悬空、还没成形的部分。\n"
            "阴视角看这些：\n"
            "  - 一边说了，另一边没有呼应的\n"
            "  - 两边都提到，但角度不同、对不上的\n"
            "  - 两边都绕开、谁也没碰的\n"
            "候选是'关系'，不是'立场'。\n"
            "不要把任一 view 的内容直接搬过来当候选。\n"
            "能写几条写几条（8 是上限，不是要交的作业量）。"
            "展开几条就写几条；一条都展开不出来就只输出一行：'（无）'\n"
            "每行格式：- [kind] 描述（20-80字）\n"
            "kind: concept/event/person/object/startpoint/question/thread/other\n"
            "不要解释，不要标题。\n"
            + ANTI_PRETTY
            + self._self_block()
        )

    def _both_yang_prompt(self) -> str:
        return (
            "你处于【对撞 · 阳视角】。\n"
            "两个 view 已经给出。\n"
            "这里的 1 是：两个 view 之间已经对齐、已经确定、已经成形的部分。\n"
            "阳视角看这些：\n"
            "  - 两边明确对齐的\n"
            "  - 两边共同确认的\n"
            "  - 两边共同悬置的（一起不碰，也算一种确定）\n"
            "候选是'关系'，不是'立场'。\n"
            "不要把任一 view 的内容直接搬过来当候选。\n"
            "能写几条写几条（8 是上限，不是要交的作业量）。"
            "展开几条就写几条；一条都展开不出来就只输出一行：'（无）'\n"
            "每行格式：- [kind] 描述（20-80字）\n"
            "kind: concept/event/person/object/startpoint/question/thread/other\n"
            "不要解释，不要标题。\n"
            + ANTI_PRETTY
            + self._self_block()
        )

    def _all_yang_prompt(self) -> str:
        return (
            "你处于【元 · 阳视角】。\n"
            "多个 view 已经给出，它们加在一起代表'全部'。\n"
            "这里的 1 是：all 作为整体已经被看见、已经被确认的部分，\n"
            "以及 all 里已经被吸收进去的局部。\n"
            "阳视角看这些：\n"
            "  - 这几个 view 共同确认了什么\n"
            "  - 其中已经稳定成立、不再晃动的部分\n"
            "  - '全部都已经在'这件事本身，落在哪里是确定的\n"
            "候选的对象是 all 这个状态本身，不是任何一个 view 的内容。\n"
            "\n"
            "【★ v1.21.32 硬约束】\n"
            "如果一条候选以 view0 / view1 / both / 两边 / 上游 / "
            "对撞层 / 研究层 / 修行层 为主语或宾语，\n"
            "它不是 all 的候选——这种候选应被丢弃，不要写。\n"
            "all 的候选必须回答：作为整体，all 自身是什么。\n"
            "能写几条写几条（8 是上限，不是要交的作业量）。"
            "展开几条就写几条；一条都展开不出来就只输出一行：'（无）'\n"
            "每行格式：- [kind] 描述（20-80字）\n"
            "kind: concept/event/person/object/startpoint/question/thread/other\n"
            "不要解释，不要标题。\n"
            + ANTI_PRETTY
            + self._self_block()
        )

    def _all_yin_prompt(self) -> str:
        return (
            "你处于【元 · 阴视角】。\n"
            "多个 view 已经给出，它们加在一起代表'全部'。\n"
            "这里的 0 是：all 作为整体还没被看见的部分，\n"
            "以及 all 里还没被吸收进去的局部。\n"
            "阴视角看这些：\n"
            "  - 为什么恰好是这几个 view，而不是别的\n"
            "  - 它们加在一起就够成'全部'吗，缺了什么\n"
            "  - 哪个局部还悬在外面，没被整体收进去\n"
            "候选的对象是 all 这个状态本身，不是任何一个 view 的内容。\n"
            "\n"
            "【★ v1.21.32 硬约束】\n"
            "如果一条候选以 view0 / view1 / both / 两边 / 上游 / "
            "对撞层 / 研究层 / 修行层 为主语或宾语，\n"
            "它不是 all 的候选——这种候选应被丢弃，不要写。\n"
            "all 的候选必须回答：作为整体，all 自身是什么。\n"
            "能写几条写几条（8 是上限，不是要交的作业量）。"
            "展开几条就写几条；一条都展开不出来就只输出一行：'（无）'\n"
            "每行格式：- [kind] 描述（20-80字）\n"
            "kind: concept/event/person/object/startpoint/question/thread/other\n"
            "不要解释，不要标题。\n"
            + ANTI_PRETTY
            + self._self_block()
        )

    # ---------- 池文本 ----------
    def _pool_text(self, pool: Pool) -> str:
        if not self.use_content:
            return "（内容通道未开：本次不读历史）"
        lines = []
        if pool.amps:
            lines.append("& 印记：")
            for a in pool.amps[-8:]:
                pol = str(a.get("polarity", "")).strip()
                tag = f"[{pol}] " if pol else ""
                lines.append(f"  - {tag}{a.get('desc','')}")
        if pool.threads:
            lines.append("悬空线头：")
            for t in pool.threads[-8:]:
                pol = str(t.get("polarity", "")).strip()
                tag = f"[{pol}] " if pol else ""
                lines.append(f"  - {tag}{t.get('desc','')}")
        if pool.probes:
            lines.append("还没带走的自问：")
            for p in pool.probes[-8:]:
                lines.append(
                    f"  - {p.get('question','')}（回来：{p.get('link','')}）")
        alive = [s for s in pool.suspensions
                 if s.get("status") in ("active", "stable")]
        if alive:
            lines.append("主动悬置（判断过、决定不碰）：")
            for s in alive[-8:]:
                lines.append(
                    f"  - {s.get('target','')}"
                    f"（{s.get('reason') or '直觉，无理由'}）"
                    f"[{s.get('status','')}]")
        return "\n".join(lines) or "（空）"

    # ---------- 候选行解析 ----------
    @staticmethod
    def _parse_candidate_line(line: str) -> Optional[Candidate]:
        line = line.strip()
        if line in ("（无）", "(无)", "无"):
            return None
        m = re.match(r"^[-•·]\s*(?:\[(\w+)\]\s*)?(.+)$", line)
        if not m:
            return None
        kind = (m.group(1) or "concept").lower()
        if kind not in KINDS:
            kind = "concept"
        desc = m.group(2).strip()
        desc = re.sub(r"[（(]\s*\d+\s*[-–—~至到]\s*\d+\s*字\s*[)）]\s*$", "", desc)
        desc = re.sub(r"[（(]\s*\d+\s*字\s*[)）]\s*$", "", desc)
        desc = re.sub(r"[。；;]+$", "", desc).strip()
        if not desc or len(desc) < 5 or len(desc) > 200:
            return None
        # [B5] 原来只数英文 "?" —— 中文问号"？"与全角省略号"…"漏网，
        # 整段全是问号的伪候选照样进池。补全三种写法。
        if (desc.count("?") + desc.count("？")) > 2 \
                or desc.count("...") + desc.count("…") > 1:
            return None
        return Candidate(desc=desc, kind=kind)

    # ---------- 对偶判断 ----------
    def _dual_judge_spec(self) -> str:
        return self.phase.dual_spec

    def _judge_context(self, inp: Input, anchor: str) -> str:
        if inp.is_base:
            return f"{anchor}\n\n【原始问题】\n{inp.question}"
        parts = [f"【问题（透传）】\n{anchor}"]
        for v in inp.upstream_views:
            parts.append(
                f"【view-{v.entry} 形状】\n{View.shape_of(v)[:1200]}")
        if self.use_context and inp.context:
            parts.append(
                "【背景】（这是来路，不是要求：它只影响你怎么看，"
                "不要把它当成要回答或要判断的东西）\n"
                f"{inp.context}")
        return "\n\n".join(parts)

    @staticmethod
    def _extract_judgments(data: dict) -> dict:
        jmap: Dict[int, dict] = {}
        raw_js = data.get("judgments", [])
        if isinstance(raw_js, dict):
            for k, v in raw_js.items():
                if not isinstance(v, dict):
                    continue
                try:
                    idx = int(k)
                except (ValueError, TypeError):
                    continue
                jmap[idx] = v
            return jmap
        if not isinstance(raw_js, list):
            return jmap
        for j in raw_js:
            if not isinstance(j, dict):
                continue
            idx = j.get("idx", j.get("index", 0))
            try:
                idx = int(idx)
            except (ValueError, TypeError):
                continue
            jmap[idx] = j
        return jmap

    def _dual_judge(self, candidates, inp, anchor,
                    view: Optional[View] = None) -> List[Candidate]:
        if not candidates:
            return []
        cand_text = "\n".join(
            f"{i+1}. [{c.kind}] {c.desc}" for i, c in enumerate(candidates))
        anchored = True
        if anchored:
            schema = ('{"judgments":[{"idx":1,"position":"0|1|both",'
                      '"why_position":"≤30字",'
                      '"why_0":"≤30字（仅当 position=both）",'
                      '"why_1":"≤30字（仅当 position=both）"}]}')
            how = (
                "本层【属性】已由这条候选是从哪一面被看出来而确定，你不用判、也别猜。\n"
                "你只判【位置】这一维。\n"
            )
        else:
            schema = ('{"judgments":[{"idx":1,"yin":"0|1|both",'
                      '"yang":"0|1|both","attribute":"0|1|both",'
                      '"position":"0|1|both","why_attribute":"≤30字",'
                      '"why_position":"≤30字"}]}')
            how = (
                "四个维度**独立作答**：从阴看、从阳看、属性、位置，\n"
                "不要回看前一个答案去迁就后一个。\n"
                "不一致是常态，不是错误——不一致处正是 & 的出生地。\n"
            )
        system = (
            "你是【对偶判断者】。\n"
            + self._dual_judge_spec() + how +
            "both 只在真的看不出偏向时才用；\n"
            "不要为了省事把两端都填 both，那是逃避判断。\n"
            + NO_FILL_JUDGE_RULE
            + self._carry_block_text(
                getattr(inp, "carry_constraints", None) or [], "candidate")
            + "严格 JSON：\n" + schema
            + self._self_block()
        )
        dec_block = self._decidability_block(inp)
        user = (f"【处境】\n{self._judge_context(inp, anchor)}"
                f"\n{dec_block}\n"
                f"\n【候选列表】\n{cand_text}")

        n = len(candidates)
        jmap: Dict[int, dict] = {}
        hit = 0
        try:
            raw = self.llm.call(system, user, 0.3, 3000, json_mode=True,
                                stage="dual_judge")
            jmap = self._extract_judgments(self.llm.parse_json(raw) or {})
            hit = sum(1 for i in range(1, n + 1) if i in jmap)
        except Exception as e:
            logger.warning("对偶判断失败: %s", e)

        if hit < n * 0.5:
            logger.warning("对偶判断命中 %d/%d，降级重试（候选减半）", hit, n)
            n2 = max(1, n // 2)
            sub_text = "\n".join(
                f"{i+1}. [{c.kind}] {c.desc}"
                for i, c in enumerate(candidates[:n2]))
            sub_user = (
                f"【处境】\n{self._judge_context(inp, anchor)}"
                f"\n{dec_block}\n"
                f"\n【候选列表（前 {n2} 条）】\n{sub_text}"
            )
            try:
                raw2 = self.llm.call(system, sub_user, 0.3, 3000,
                                      json_mode=True, stage="dual_judge")
                jmap2 = self._extract_judgments(self.llm.parse_json(raw2) or {})
                for k, v in jmap2.items():
                    if 1 <= k <= n2:
                        jmap[k] = v
                if n > n2:
                    rest = candidates[n2:]
                    rest_text = "\n".join(
                        f"{i+1}. [{c.kind}] {c.desc}"
                        for i, c in enumerate(rest))
                    rest_user = (
                        f"【处境】\n{self._judge_context(inp, anchor)}"
                        f"\n{dec_block}\n"
                        f"\n【候选列表（后半 {len(rest)} 条）】\n{rest_text}"
                    )
                    try:
                        raw3 = self.llm.call(system, rest_user, 0.3, 3000,
                                              json_mode=True,
                                              stage="dual_judge")
                        jmap3 = self._extract_judgments(
                            self.llm.parse_json(raw3) or {})
                        for k, v in jmap3.items():
                            if 1 <= k <= len(rest):
                                jmap[n2 + k] = v
                    except Exception as e:
                        logger.warning("对偶判断后半重试失败: %s", e)
                hit = sum(1 for i in range(1, n + 1) if i in jmap)
                logger.info("降级重试后命中 %d/%d", hit, n)
            except Exception as e:
                logger.warning("对偶判断重试失败: %s", e)

        # [P2-2] 少判不再是错误：prompt 已经允许「判不了就不输出」。
        # 原来这里无条件记一条 error，等于又把「宁可空」打回成缺陷。
        # 只有在**一条都没判到**（解析或调用层面失败）时才算错误。
        if hit == 0 and view is not None:
            view.add_error(
                "对偶判断",
                f"一条都没判到（{n} 条候选全部无判断结果），"
                f"位置全部按默认 0 处理")
        elif hit < n and view is not None:
            try:
                view._dual_unjudged = n - hit
            except Exception:
                pass
            self.vp(f"   🔮 未判 {n - hit}/{n} 条"
                    f"（[P2-2] 允许少判，按默认位置处理）")
        if hit == 0:
            return candidates

        for i, c in enumerate(candidates, 1):
            j = jmap.get(i)
            if not j:
                continue
            p = str(j.get("position", "0")).lower()
            c.position = p if p in ("0", "1", "both") else "0"
            c.why_position = str(j.get("why_position", ""))[:200]
            c.why_0 = str(j.get("why_0", ""))[:120]
            c.why_1 = str(j.get("why_1", ""))[:120]
            if anchored:
                c.attribute = "1" if c.source == "阳" else "0"
                c.attribute_anchored = True
                c.why_attribute = f"来源：{c.source or '?'}展开"
            else:
                a = str(j.get("attribute", "0")).lower()
                y = str(j.get("yin", a)).lower()
                g = str(j.get("yang", p)).lower()
                c.attribute = a if a in ("0", "1", "both") else "0"
                c.yin = y if y in ("0", "1", "both") else c.attribute
                c.yang = g if g in ("0", "1", "both") else c.position
                c.why_attribute = str(j.get("why_attribute", ""))[:200]
            if self.show_dual:
                self.vp(f"   [{i}] {_vp_preview(c.desc)}")
                if anchored:
                    self.vp(f"       属性={c.attribute}◈（{c.why_attribute}，非判断）")
                else:
                    self.vp(f"       阴={c.yin} 阳={c.yang}"
                            + ("  ⟂两端读不同" if c.yin != c.yang else ""))
                    self.vp(f"       属性={c.attribute}（{c.why_attribute}）")
                self.vp(f"       位置={c.position}（{c.why_position}）"
                        + ("  ⚡&候选" if c.is_amp_candidate else ""))

        if candidates:
            before = sum(1 for c in candidates if c.position == "both")
            cdicts = [c.to_dict() for c in candidates]
            _tighten_ratio = float(
                (self.config.get("spiral") or {}).get(
                    "both_tighten_ratio", 0.3))
            cdicts = _tighten_both(cdicts, max_ratio=_tighten_ratio)
            for c, d in zip(candidates, cdicts):
                c.position = d.get("position", c.position)
            after = sum(1 for c in candidates if c.position == "both")
            if self.show_dual and before != after:
                self.vp(f"   🔧 both 收紧：{before} → {after}")

        return candidates

    # ---------- ing 对撞 ----------
    def _ing(self, candidates, inp, anchor,
             view: Optional[View] = None) -> str:
        if not candidates:
            return "（此处未生）"
        amp_cands = [c for c in candidates if c.is_amp_candidate]
        normal = [c for c in candidates if not c.is_amp_candidate]

        cand_text = "\n".join(
            f"- [{c.attribute}×{c.position}] {c.desc}" for c in normal)
        amp_text = "\n".join(
            f"- {c.desc}（{c.why_attribute}｜{c.why_position}）"
            for c in amp_cands) or "（无）"

        if inp.is_base:
            object_desc = "这个问题里的 0 和 1"
        elif self.entry == "both":
            object_desc = "两个已经完成的形状"
        elif self.entry == "all":
            object_desc = "整体与每一个局部"
        else:
            # entry 0/1 却带着上游 view —— 当前通道不可达，留给将来的接线。
            object_desc = "上游留下的形状与本圈的候选"

        if inp.is_base:
            speech_text = ""
        elif self.entry == "both":
            intro = "以下是要相撞的两端各自说过的话：\n\n"
            speech_text = (intro
                           + "\n\n".join(View.speech_of(v)
                                         for v in inp.upstream_views))
        elif self.entry == "all":
            intro = "以下是这个整体所包含的各个局部说过的话：\n\n"
            speech_text = (intro
                           + "\n\n".join(View.speech_of(v)
                                         for v in inp.upstream_views))
        else:
            intro = "以下是上游留下的形状各自说过的话：\n\n"
            speech_text = (intro
                           + "\n\n".join(View.speech_of(v)
                                         for v in inp.upstream_views))

        _upstream_label = ("两个 view" if self.entry == "both"
                           else "各个局部 view" if self.entry == "all"
                           else "上游 view")
        _fix83_block = (
            f"\n【★ 硬约束 · ing 不许复述上游】\n"
            f"本次 ing 输出里的每一句，都必须包含{_upstream_label}"
            f"没有单独说过的话。\n"
            f"禁止逐句复述上游 view 的 manifest / collision，\n"
            f"也不许把它们换个说法再说一遍（换说法也是复述）。\n"
            f"如果发现自己写的是「上游说过的话的换说法」，立刻停笔，\n"
            f"重写成对撞真正生成的句子。宁可短，也不要复述。\n"
            f"★ 本层候选不是上游：它是给你对撞的原料，你可以拿它生成，\n"
            f"  但不能只是把它扩写成一段话交回来。\n"
            + self._carry_block_text(
                getattr(inp, "carry_constraints", None) or [], "ing")
        )

        system = (
            "你处于【ing · 对撞】。\n"
            f"对撞的对象是：{object_desc}\n"
            + (("两端各自说过的话已在下面给出。\n"
                "先让它们各自把话说完——不要用你的总结替代它们的话，\n"
                "也不要先做比较。说完，再对撞。\n")
               if speech_text else "")
            + "按六步展开：\n"
            "一、让两端各自把话说完\n"
            "二、各推到极端\n"
            "三、找反转点\n"
            "四、让对撞生成新东西（不是折中，是生成）\n"
            "五、标出撞不动的地方（用 '&' 标记）\n"
            "六、回到原始问题/处境\n"
            f"【本层侧重】{self.phase.ing_focus}\n"
            "语气：清醒、克制，不煽情，不客服。\n"
            + (("【★ 结构化尾块】六步写完后，**另起一行**原样输出\n"
                "  ===ING-STRUCT===\n"
                "  紧接**一行 JSON**：\n"
                '  {"shared":["两边都指向的1","..."],\n'
                '   "tensions":[{"name":"张力名","a":"0面说...",'
                '"b":"1面说..."}],\n'
                '   "third":"撞出的第三者（一句话）"}\n'
                "  ★ third 是这次撞出的**不在任何一面里**的新东西。\n"
                "    撞不出就写空字符串——那叫「此处未生」，是合法结果。\n"
                "    不许把 0 面或 1 面的话换个说法填进去。\n")
               if self.entry in ("both", "all") else "")
            + _fix83_block
            + ANTI_PRETTY
            + self._self_block()
        )
        user = (
            f"【原始问题/处境】\n{anchor}\n\n"
            + (f"{speech_text}\n\n" if speech_text else "")
            + f"【普通候选】\n{cand_text}\n\n"
            f"【& 候选（属性≠位置）】\n{amp_text}"
        )
        try:
            text, trunc = self._call_long(
                system, user, 0.7, 4000, model=self.llm.reasoner_model,
                thinking=self.llm.thinking_reasoner)
            if trunc and view is not None:
                view.add_error(
                    "ing", RuntimeError(
                        "输出被长度掐断，续跑后仍未走完六步；"
                        "下游读到的可能是残篇"))
                self.vp("   ✗ ing 输出仍被截断——本层是残篇，不是完整对撞")
            if view is not None and self.entry in ("both", "all"):
                _idx = text.rfind("===ING-STRUCT===")
                if _idx >= 0:
                    _tail = text[_idx + len("===ING-STRUCT==="):].strip()
                    try:
                        _s = self.llm.parse_json(_tail)
                        if isinstance(_s, dict):
                            view.ing_structured = _s
                        else:
                            view.errors.append(
                                "ing 结构化解析失败（不是对象）")
                    except Exception as _e:
                        view.errors.append(f"ing 结构化解析失败：{_e}")
                else:
                    view.errors.append(
                        "ing 结构化尾块缺失（未输出 ===ING-STRUCT===）")
            return text
        except Exception as e:
            msg = f"ing(reasoner) 失败：{type(e).__name__}: {e}"
            logger.warning(msg)
            if view is not None:
                view.add_error("ing/reasoner", e)
            self.vp("   ⚠️ reasoning 调用失败，降级：同模型关掉 thinking 重试")
            try:
                text, trunc = self._call_long(system, user, 0.7, 4000)
                if view is not None:
                    view.errors.append("ing 已降级为非思考模式产出")
                    if trunc:
                        view.add_error(
                            "ing", RuntimeError(
                                "降级后输出仍被长度掐断；本层是残篇"))
                    if self.entry in ("both", "all"):
                        _idx = text.rfind("===ING-STRUCT===")
                        if _idx >= 0:
                            _tail = text[
                                _idx + len("===ING-STRUCT==="):].strip()
                            try:
                                _s = self.llm.parse_json(_tail)
                                if isinstance(_s, dict):
                                    view.ing_structured = _s
                            except Exception:
                                pass
                return text
            except Exception as e2:
                if view is not None:
                    view.add_error("ing/chat-fallback", e2)
                raise RuntimeError(
                    f"{msg}；降级重试亦失败：{e2}") from e2

    # ---------- & 沉淀 ----------
    def _he(self, collision, amp_candidates, pool, inp) -> Tuple[
            List[dict], List[dict], List[str], dict]:
        if not collision:
            logger.warning("& 收到空 collision，跳过沉淀")
            return [], [], [], {}
        if collision == "（此处未生）":
            return [], [], [], {}
        existing = self._pool_text(pool)
        amp_hint = "\n".join(f"- {c.desc}" for c in amp_candidates) or "（无）"

        is_research = (self.entry == "1")
        if is_research:
            dec_subs = [s for s in pool.sub_questions
                        if s.get("decidability") in _DEC_ANSWERABLE]
            und_subs = [s for s in pool.sub_questions
                        if s.get("decidability") == "undecidable"]
            dec_text = "\n".join(
                f"- {s['id']}. {s['question']}"
                for s in dec_subs) or "（无）"
            und_text = "\n".join(
                f"- {s['id']}. {s['question']}"
                for s in und_subs) or "（无）"
            und_aspects_list = []
            if inp.decidability_result:
                und_aspects_list = inp.decidability_result.get(
                    "undecidable_aspects", []) or []
            und_aspects_text = "\n".join(
                f"- {a}" for a in und_aspects_list) or "（无）"

            system = (
                "你处于【& · 双通道融合】（研究层）。\n"
                "\n"
                "【核心任务】\n"
                "从 ing 的对撞余烬里，同时产出：\n"
                "  A. decidable_product：针对可判定子问题的直接回答\n"
                "  B. undecidable_product：针对不可判定子问题的结构揭示\n"
                "\n"
                "【A. decidable_product 要求】\n"
                "  - answer：具体、可检验的回答（不是抽象重构）\n"
                "  - answered_sub_ids：回答的子问题编号列表\n"
                "  - evidence：支持这个回答的证据或推理（≤2 条）\n"
                "  - distance：距离完整回答全部可判定子问题还有多远（0-1）\n"
                "  - actions：回答若落在「该做什么」（decision 取向），\n"
                "    **必须**同时给 \"actions\" 段，而不是只给结论段落。\n"
                "\n"
                "【★ actions 段 · decision 取向必须产出】\n"
                "  - 研究层的回答若落在\"该做什么\"，必须同时给 actions 段。\n"
                "  - 每条 action 六字段**全部必填**，缺一格视为无效条目。\n"
                "  - owner_role 必须是一个**具体的角色 / 部门 / 岗位**，\n"
                "    不许写\"相关部门\"\"有关方面\"。\n"
                "  - deadline_hint 必须是**可指认的时限或触发条件**\n"
                "    （如\"汛期前 30 天\"\"下一次暴雨后 24h\"），\n"
                "    不许写\"尽早\"\"适时\"。\n"
                "  - acceptance 必须能**被第三方核对**\n"
                "    （如\"出具签字人清单\"\"泵站流量记录入档\"）。\n"
                "  - fallback 必须写**失败时的退路**，\n"
                "    不许写\"重新评估\"这类空动作。\n"
                "  - 若确实给不出 actions（纯事实题 / 边界题），\n"
                "    给空数组并在 answer 里说明，不要硬凑。\n"
                "\n"
                "【★ not_do 段 · decision 取向必须产出】\n"
                "  - 至少 1 条，最多 3 条。\n"
                "  - what 必须是一件**明确不做的事**（不是\"暂缓\"、不是\"待定\"）。\n"
                "    例：\"不在成因判定缺席时启动物探\"\"不优先改造非瓶颈段\"。\n"
                "  - why 必须能指向一个**可核对的事实**或一条**可指认的判据**\n"
                "    （不是\"资源有限\"这种套话）。\n"
                "  - 若本次确实没有明确不做的事，写空数组并在 answer 里说明；\n"
                "    不要硬凑。\n"
                "\n"
                "【B. undecidable_product 要求】\n"
                "  - why_undecidable：为什么这个子问题不可判定\n"
                "  - structural_amps：从 ing 输出里**独立**提炼的结构性 & 印记，\n"
                "    用自己的语言，**不得直接复述下方 und_aspects 的原话**。\n"
                "    有 & 就至少写 1 条；确实没有新的不可通约处，\n"
                "    返回空数组，并在 why_undecidable 里说明为何此处未生。\n"
                "    ★ DGTF 允许未生。硬凑比空数组更糟。\n"
                "  - aligned_amps：如果你确实发现某条结构**正好对应**\n"
                "    下方【评估阶段的不可判定方面】中的某一项，写在这里。\n"
                "    这是两套独立产物的对账，不是必须凑齐的清单——\n"
                "    对不上就留空，对得上才写。\n"
                "    ★ 合法的空数组比硬凑更受尊重。\n"
                "  - clarity：对不可判定结构的揭示清晰度（0-1）\n"
                "  - distance：距离完整揭示全部不可判定结构还有多远（0-1）\n"
                "\n"
                "【C. 综合产物】\n"
                "  - desc：综合两个子产物的凝练（≤60字）\n"
                "  - reason / link_to_question\n"
                "  - distance_to_question：综合产物离原始问题多远（0-1）\n"
                "  - covered_aspects / uncovered_aspects：已触及/未触及的方面\n"
                "\n"
                "【D. & 印记】从 ing 中提炼 2-4 条本层新产生的结构性 &\n"
                "   顶层 amp 是全域结构，undecidable_product.structural_amps\n"
                "   是不可判定通道内的结构。两者不互斥：\n"
                "   既属于全域又属于不可判定通道的结构，两边都可填——\n"
                "   系统会按 _similar 去重，不会重复计入。\n"
                "   若只在一处填，系统会自动镜像到另一边。\n"
                "【E. 悬空线头】0-3 条\n"
                "【F. 元反思】0-2 条\n"
                "\n"
                "严格 JSON：\n"
                "{\n"
                '  "desc": "综合产物，≤60字",\n'
                '  "reason": "≤80字",\n'
                '  "link_to_question": "≤50字",\n'
                '  "distance_to_question": 0.0-1.0,\n'
                '  "covered_aspects": ["..."],\n'
                '  "uncovered_aspects": ["..."],\n'
                '  "decidable_product": {\n'
                '    "answer": "...",\n'
                '    "answered_sub_ids": [1],\n'
                '    "evidence": ["..."],\n'
                '    "distance": 0.0-1.0,\n'
                '    "actions": [\n'
                '      {"id": "A1",\n'
                '       "verb": "指派|核查|测量|提交|申请|封堵|清淤|试点|备案|"\n'
                '               "签发|复核|排查|改造|扩容|委托|报审|谈判|调取",\n'
                '       "object": "≤40字，动作对象",\n'
                '       "owner_role": "≤20字，具名角色或部门",\n'
                '       "deadline_hint": "≤20字，具体时限或触发条件",\n'
                '       "acceptance": "≤40字，怎么算完成",\n'
                '       "fallback": "≤40字，失败时的退路"}\n'
                '    ],\n'
                '    "not_do": [\n'
                '      {"what": "≤40字，明确不做的事",\n'
                '       "why": "≤40字，理由"}\n'
                '    ]\n'
                "  },\n"
                '  "undecidable_product": {\n'
                '    "why_undecidable": "...",\n'
                '    "structural_amps": ["..."],\n'
                '    "aligned_amps": ["..."],\n'
                '    "clarity": 0.0-1.0,\n'
                '    "distance": 0.0-1.0\n'
                "  },\n"
                '  "amp": [{"desc":"≤60字","type":"ontological"}],\n'
                '  "threads": ["..."],\n'
                '  "meta": ["..."]\n'
                "}\n"
                + ANTI_PRETTY
                + self._self_block()
            )
            user = (
                f"【ing 输出】\n{collision}\n\n"
                f"【★ 本层必须回答的可判定子问题】\n{dec_text}\n\n"
                f"【★ 本层必须揭示结构的不可判定子问题】\n{und_text}\n\n"
                f"【评估阶段的不可判定方面（供参考，不强制对齐；\n"
                f"  若你的结构正好对应其中某一项，写进 aligned_amps）】\n"
                f"{und_aspects_text}\n\n"
                f"【属性≠位置的 & 候选】\n{amp_hint}\n\n"
                f"【已存在的 & 与线头】\n{existing}"
            )
        elif self.entry == "both":
            system = (
                "你处于【& · 对撞沉淀】。\n"
                "从 ing 输出里沉淀'撞不开'的东西。\n"
                f"【本层侧重】{self.phase.he_focus}\n"
                "【★ 硬约束 · & 必须来自具体张力点】\n"
                "  每条 & 都要带 tension_from 字段 —— 写它来自 ing 里的\n"
                "  哪条具体张力。笼统的'两边不可通约'不算，\n"
                "  要说出**在哪一点上**不可通约。\n"
                "【共同盲区不是 &】—— 归线头。\n"
                "一、& 印记（0-4 条，不要凑）：\n"
                "   每条标注类型：logical/ontological/structural/"
                "axiological/pseudo\n"
                "   每条带 tension_from（≤30字）\n"
                "二、悬空线头（0-3 条）：还没走完的方向，包括共同绕开的盲区\n"
                "三、元反思（0-2 条）\n"
                "如果本次确实没有新的不可通约处，amps 返回空数组。\n"
                "严格 JSON：\n"
                '{"amps":[{"desc":"≤60字","type":"ontological",'
                '"tension_from":"≤30字"}],'
                '"threads":["..."],"meta":["..."]}\n'
                + ANTI_PRETTY
                + self._self_block()
            )
            user = (
                f"【ing 输出】\n{collision}\n\n"
                f"【属性≠位置的 & 候选】\n{amp_hint}\n\n"
                f"【已存在的 & 与线头】\n{existing}"
            )
        else:
            # 修行 / 元层 —— 保留原模板，但盲区措辞按层替换
            if self.entry == "all":
                _blind = "整体和局部共同绕开的盲区"
            else:
                _blind = "0 面和 1 面共同绕开、都没碰到的盲区"
            system = (
                "你处于【& · 阴阳结合】。\n"
                "从 ing 输出里沉淀出'撞不开'的东西。\n"
                f"【本层侧重】{self.phase.he_focus}\n"
                f"{_blind}不是 &，归到线头。\n"
                "一、& 印记（0-4 条，不要凑）：\n"
                "   每条标注类型：logical/ontological/structural/"
                "axiological/pseudo\n"
                "二、悬空线头（0-3 条）：还没走完的方向，包括共同绕开的盲区\n"
                "三、元反思（0-2 条）\n"
                "如果本次确实没有新的不可通约处，amps 返回空数组。\n"
                "严格 JSON：\n"
                '{"amps":[{"desc":"≤60字","type":"ontological"}],'
                '"threads":["..."],"meta":["..."]}\n'
                + ANTI_PRETTY
                + self._self_block()
            )
            user = (
                f"【ing 输出】\n{collision}\n\n"
                f"【属性≠位置的 & 候选】\n{amp_hint}\n\n"
                f"【已存在的 & 与线头】\n{existing}"
            )

        try:
            raw = self.llm.call(system, user, 0.3, 2500, json_mode=True)
        except Exception as e:
            logger.warning("& 失败: %s", e)
            raise

        data = self.llm.parse_json(raw) or {}
        amps_in = data.get("amps", [])
        threads_in = data.get("threads", [])
        meta_in = data.get("meta", [])

        amps = []
        for a in amps_in:
            if not isinstance(a, dict):
                continue
            desc = str(a.get("desc", "")).strip()[:200]
            if not desc or len(desc) < 5:
                continue
            t = str(a.get("type", "ontological")).lower()
            if t not in AMP_TYPES:
                t = "ontological"
            _amp = {"desc": desc, "type": t, "source": self.entry,
                    "polarity": "?"}
            _tf = str(a.get("tension_from", "")).strip()[:80]
            if _tf:
                _amp["tension_from"] = _tf
            amps.append(_amp)

        threads = []
        for t in threads_in:
            desc = str(t).strip()[:200]
            if not desc or len(desc) < 5:
                continue
            threads.append({"desc": desc, "kind": "thread",
                            "polarity": "?"})

        meta = [str(m).strip()[:200] for m in meta_in if str(m).strip()]

        for a in amps:
            self.vp(f"   & [{AMP_TYPES[a['type']]}] {a['desc']}")
        for t in threads:
            self.vp(f"   ... {t['desc']}")
        if not amps and not threads:
            self.vp("   （本次无 & 印记，无线头——此处一片澄明）")

        extra: Dict[str, Any] = {}
        if is_research:
            dec = data.get("decidable_product") or {}
            if not isinstance(dec, dict):
                dec = {}
            dec_norm = {
                "answer": str(dec.get("answer", ""))[:800],
                "answered_sub_ids": list(dec.get("answered_sub_ids") or [])[:20],
                "evidence": [str(e)[:200]
                             for e in (dec.get("evidence") or [])][:5],
                "actions": _norm_schema_actions(dec.get("actions")),
                "not_do": _norm_schema_not_do(dec.get("not_do")),
                "distance": 0.0,
            }
            try:
                dec_norm["distance"] = max(0.0, min(1.0,
                    float(dec.get("distance", 1.0))))
            except (TypeError, ValueError):
                dec_norm["distance"] = 1.0

            und = data.get("undecidable_product") or {}
            if not isinstance(und, dict):
                und = {}
            und_norm = {
                "why_undecidable": str(und.get("why_undecidable", ""))[:300],
                "structural_amps": [str(s)[:200]
                                    for s in (und.get("structural_amps") or [])][:5],
                "aligned_amps": [str(s)[:200]
                                 for s in (und.get("aligned_amps") or [])][:5],
                "clarity": 0.0,
                "distance": 1.0,
            }
            try:
                und_norm["clarity"] = max(0.0, min(1.0,
                    float(und.get("clarity", 0.0))))
            except (TypeError, ValueError):
                und_norm["clarity"] = 0.0
            try:
                und_norm["distance"] = max(0.0, min(1.0,
                    float(und.get("distance", 1.0))))
            except (TypeError, ValueError):
                und_norm["distance"] = 1.0

            _d2q_v = data.get("distance_to_question")
            try:
                d2q = None if _d2q_v is None else float(_d2q_v)
            except (TypeError, ValueError):
                d2q = None
            extra = {
                "decidable_product": dec_norm,
                "undecidable_product": und_norm,
                "distance_to_question": (None if d2q is None
                                            else max(0.0, min(1.0, d2q))),
                "covered_aspects": [str(x)[:120]
                                    for x in (data.get("covered_aspects") or [])][:5],
                "uncovered_aspects": [str(x)[:120]
                                      for x in (data.get("uncovered_aspects") or [])][:5],
            }

            _n_mirror = 0
            for sa in und_norm.get("structural_amps", []):
                desc = str(sa).strip()
                if not desc or len(desc) < 5:
                    continue
                if any(_similar(desc, a.get("desc", ""), 0.85)
                       for a in amps):
                    continue
                amps.append({
                    "desc": desc[:200],
                    "type": "structural",
                    "source": self.entry,
                    "polarity": "?",
                })
                _n_mirror += 1
            if _n_mirror > 0:
                self.vp(f"   ↳ 不可判定通道结构镜像到顶层 amp："
                        f"+{_n_mirror} 条（共 {len(amps)} 条）")
                for a in amps[-_n_mirror:]:
                    self.vp(f"   & [{AMP_TYPES[a['type']]}] {a['desc']}")

        return amps, threads, meta, extra

    # ---------- 问题分解（外部路径） ----------
    def _decompose_question(self, question: str,
                            decidability_result: Optional[dict] = None) -> List[dict]:
        dr = decidability_result or {}
        status = dr.get("decidability", "decidable")
        und_aspects = dr.get("undecidable_aspects", [])
        dec_aspects = dr.get("decidable_aspects", [])

        status = _normalize_decidability(status, dec_aspects, und_aspects,
                                        where="拆解分派")
        if status == "undecidable":
            return self._decompose_koan(question)
        elif status == "partial":
            return self._decompose_hybrid(question, dec_aspects, und_aspects)
        else:
            return self._decompose_normal(question, dec_aspects, und_aspects)

    def _decompose_normal(self, question, dec_aspects, und_aspects) -> List[dict]:
        dec_hint = "\n".join(f"- {a}" for a in dec_aspects) or "（无）"
        und_hint = "\n".join(f"- {a}" for a in und_aspects) or "（无）"
        system = """你是【问题拆解者】。
把一个复杂问题拆解成 3-6 个可独立回答的子问题。
【★ 重要】若上方给出了评估阶段的方面，你的拆解必须覆盖它们。
严格 JSON：
{"sub_questions": [{"id": 1, "question": "...", "weight": 0.5, "decidability": "decidable|partial|undecidable"}]}
""" + ANTI_PRETTY + self._self_block()
        user = (f"【原始问题】\n{question}\n\n"
                f"【评估阶段识别的可判定方面】\n{dec_hint}\n\n"
                f"【评估阶段识别的不可判定方面】\n{und_hint}"
                + (getattr(self, "_web_digest", "") or ""))
        try:
            raw = self.llm.call(system, user, 0.3, 1300, json_mode=True, stage=_thinking_stage(self.config, 'decompose_normal'))
        except Exception as e:
            logger.warning("问题分解失败: %s", e)
            return []
        subs = self._parse_subs(raw, default_decidability="decidable")
        return self._ensure_undecidable_subs(subs, und_aspects)

    def _decompose_hybrid(self, question, dec_aspects, und_aspects) -> List[dict]:
        dec_hint = "\n".join(f"- {a}" for a in dec_aspects) or "（无）"
        und_hint = "\n".join(f"- {a}" for a in und_aspects) or "（无）"
        system = """你是【混合问题拆解者】。
一个问题同时包含可判定和不可判定的成分。
拆解成 3-6 个子问题，**必须同时包含至少 1 个 decidable 和至少 1 个 undecidable**。
严格 JSON：
{"sub_questions": [{"id": 1, "question": "...", "weight": 0.5, "decidability": "decidable|partial|undecidable"}]}
""" + ANTI_PRETTY + self._self_block()
        user = (f"【原始问题】\n{question}\n\n"
                f"【评估阶段识别的可判定方面】\n{dec_hint}\n\n"
                f"【评估阶段识别的不可判定方面】\n{und_hint}"
                + (getattr(self, "_web_digest", "") or ""))
        try:
            raw = self.llm.call(system, user, 0.3, 1300, json_mode=True, stage=_thinking_stage(self.config, 'decompose_hybrid'))
        except Exception as e:
            logger.warning("混合问题分解失败: %s", e)
            return []
        subs = self._parse_subs(raw, default_decidability="decidable")
        return self._ensure_undecidable_subs(subs, und_aspects)

    def _decompose_koan(self, question) -> List[dict]:
        # ★ 这条路径在真跑里几乎进不去（判定归一化后只要还剩一条可判定
        #   方面就走 hybrid）。以前它连一行痕迹都不留，审计只能靠 tag 名
        #   误统计——所以这里必须留痕：进了就是进了，没进就是没进。
        self.vp("   ☯️ 进入 koan 整体不可判定分解（全部方面判不出，"
                "不拆可判定子题）")
        system = """你是【不可判定结构拆解者】。
把一个不可判定问题拆解成 3-6 个维度。
严格 JSON：
{"dimensions": [{"id": 1, "dimension": "...", "why_undecidable": "...", "what_can_probe": "..."}]}
""" + ANTI_PRETTY + self._self_block()
        try:
            raw = self.llm.call(
                system, f"【原始问题】\n{question}"
                + (getattr(self, "_web_digest", "") or ""),
                                0.3, 1100, json_mode=True, stage=_thinking_stage(self.config, 'decompose_koan'))
        except Exception as e:
            logger.warning("koan 分解失败: %s", e)
            return []
        data = self.llm.parse_json(raw) or {}
        dims = data.get("dimensions", [])
        if not isinstance(dims, list):
            return []
        out = []
        for d in dims:
            if not isinstance(d, dict):
                continue
            dim = str(d.get("dimension", "")).strip()
            if not dim:
                continue
            out.append({"id": len(out) + 1, "dimension": dim[:100],
                         "question": dim[:100], "weight": 1.0,
                         "decidability": "undecidable",
                         "depth": 1.0,
                         "why_undecidable": str(d.get("why_undecidable", ""))[:150],
                         "what_can_probe": str(d.get("what_can_probe", ""))[:150]})
            if len(out) >= 6:
                break
        return out

    @staticmethod
    def _ensure_undecidable_subs(subs: List[dict],
                                  und_aspects: List[str]) -> List[dict]:
        has_und = any(s.get("decidability") == "undecidable" for s in subs)
        if has_und:
            return subs
        if not und_aspects:
            return subs
        for aspect in und_aspects[:3]:
            subs.append({
                "id": len(subs) + 1,
                "question": aspect,
                "weight": 0.5,
                "decidability": "undecidable",
                "_from_assessment": True,
            })
        logger.info("拆解未产生 undecidable 子问题，从评估阶段兜底强加 %d 条",
                    min(len(und_aspects), 3))
        return subs

    @staticmethod
    def _parse_subs(raw: str, default_decidability="decidable") -> List[dict]:
        data = DGTF._parse_json_safe(raw) or {}
        subs = data.get("sub_questions", [])
        if not isinstance(subs, list):
            return []
        out = []
        for sq in subs:
            if not isinstance(sq, dict):
                continue
            q = str(sq.get("question", "")).strip()
            if not q or len(q) < 4:
                continue
            try:
                sid = int(sq.get("id", len(out) + 1))
            except (ValueError, TypeError):
                sid = len(out) + 1
            try:
                w = float(sq.get("weight", 0.5))
            except (ValueError, TypeError):
                w = 0.5
            w = max(0.0, min(1.0, w))
            dec = str(sq.get("decidability", default_decidability)).lower()
            if dec not in _DECIDABILITY_STATES:
                dec = default_decidability
            out.append({"id": sid, "question": q[:200], "weight": w,
                         "decidability": dec, "status": "open",
                         "depth": 1.0})
            if len(out) >= 7:
                break
        return _canonical_sub_ids(out)

    @staticmethod
    def _parse_json_safe(raw: str) -> Optional[dict]:
        return LLM.parse_json(raw)

    # ---------- 内部分解（方案 Y：从 0 池产物读） ----------
    def _decompose_from_pool(self, question: str, pool: Pool,
                             view: Optional[View]) -> List[dict]:
        probe_lines = [
            f"  P{i+1}. {str(p.get('question', ''))[:100]}"
            f"（回来：{str(p.get('link', ''))[:60]}）"
            for i, p in enumerate((pool.probes or [])[:10])
        ] or ["  （无探针）"]

        amp_lines = [
            f"  A{i+1}. [{a.get('type', '?')}] "
            f"{str(a.get('desc', ''))[:100]}"
            for i, a in enumerate((pool.amps or [])[:10])
        ] or ["  （无 & 印记）"]

        susp_lines = [
            f"  S{i+1}. {str(s.get('target', ''))[:80]}"
            f"（{str(s.get('reason', ''))[:40]}）"
            for i, s in enumerate([
                x for x in (pool.suspensions or [])
                if x.get("status") in ("active", "stable")
            ][:10])
        ] or ["  （无主动悬置）"]

        thread_lines = [
            f"  T{i+1}. {str(t.get('desc', ''))[:100]}"
            for i, t in enumerate((pool.threads or [])[:10])
        ] or ["  （无线头）"]

        cand_lines = []
        if view and view.candidates:
            for i, c in enumerate(view.candidates[:15], 1):
                pos = c.get("position", "?")
                attr = c.get("attribute", "?")
                desc = str(c.get("desc", ""))[:80]
                amp = " [&候选]" if c.get("is_amp_candidate") else ""
                cand_lines.append(f"  C{i}. [{attr}×{pos}]{amp} {desc}")
        cand_text = "\n".join(cand_lines) or "  （无候选）"

        ing_text = ""
        if view and view.collision and view.collision != "（此处未生）":
            ing_text = str(view.collision)[:1500]

        system = (
            "你是【从展开产物里生发子问题的人】。\n"
            "\n"
            "你不从原始问题重新拆解——那会把修行层白跑一遍。\n"
            "你从修行层留下的形状里读出：研究该追什么。\n"
            "\n"
            "【输入：修行层的产物】\n"
            "- P#：探针。还没带走的自问——最直接的研究对象\n"
            "- A#：& 印记。撞不动的结构——不可判定子问题的种子\n"
            "- S#：主动悬置。决定不碰的——已知硬边界\n"
            "- T#：悬空线头。未走完的方向\n"
            "- C#：候选。position 分布反映哪些判得明确、哪些判不出\n"
            "- ing 输出：撞出第三者处可对撞；\"此处未生\"处是硬边界\n"
            "\n"
            "【任务】\n"
            "生发 3-6 个子问题。每个标注 decidability\n"
            "（decidable = 可通过实验/基准判定；\n"
            " undecidable = 定义/制度/物理反馈等不可判定的结构）。\n"
            "\n"
            "【★ 硬约束】\n"
            "1. 每条子问题必须能追溯到上面的某条产物。\n"
            "   在 source 字段给出追溯编号（如 \"P1\"、\"A2\"、\"S1\"、\n"
            "   \"T3\"、\"C4\"、\"ing\"）。\n"
            "2. 探针是最直接的研究对象——不要忽略它们。\n"
            "   探针本身就是修行层未消化的东西。\n"
            "3. 若某项产物为空，不要硬凑。宁可子问题少，也不要凑数。\n"
            "4. 不要从原始问题重新拆一遍——从产物里长。\n"
            "\n"
            "严格 JSON：\n"
            "{\n"
            '  "sub_questions": [\n'
            "    {\n"
            '      "id": 1,\n'
            '      "question": "...",\n'
            '      "weight": 0.5,\n'
            '      "decidability": "decidable|partial|undecidable",\n'
            '      "source": "P1 / A2 / S1 / T3 / C4 / ing"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            + ANTI_PRETTY
            + self._self_block()
        )
        user = (
            f"【原始问题】\n{question}\n\n"
            f"【修行层 · 探针】\n" + "\n".join(probe_lines) + "\n\n"
            f"【修行层 · & 印记】\n" + "\n".join(amp_lines) + "\n\n"
            f"【修行层 · 主动悬置】\n" + "\n".join(susp_lines) + "\n\n"
            f"【修行层 · 悬空线头】\n" + "\n".join(thread_lines) + "\n\n"
            f"【修行层 · 候选】\n{cand_text}\n\n"
            f"【修行层 · ing 输出】\n{ing_text or '（此处未生）'}"
            + (getattr(self, "_web_digest", "") or "")
        )

        try:
            raw = self.llm.call(system, user, 0.3, 1600, json_mode=True, stage=_thinking_stage(self.config, 'decompose_from_pool'))
        except Exception as e:
            logger.warning("内部分解失败: %s", e)
            return []

        data = self.llm.parse_json(raw) or {}
        subs = data.get("sub_questions", [])
        if not isinstance(subs, list):
            return []

        out: List[dict] = []
        for sq in subs:
            if not isinstance(sq, dict):
                continue
            q = str(sq.get("question", "")).strip()
            if not q or len(q) < 4:
                continue
            try:
                sid = int(sq.get("id", len(out) + 1))
            except (ValueError, TypeError):
                sid = len(out) + 1
            try:
                w = float(sq.get("weight", 0.5))
            except (ValueError, TypeError):
                w = 0.5
            w = max(0.0, min(1.0, w))
            dec = str(sq.get("decidability", "decidable")).lower()
            if dec not in _DECIDABILITY_STATES:
                dec = "decidable"
            src = str(sq.get("source", "")).strip()[:60]
            out.append({
                "id": sid, "question": q[:200], "weight": w,
                "decidability": dec, "status": "open",
                "depth": 1.0,
                "source": src,
            })
            if len(out) >= 7:
                break

        _canonical_sub_ids(out)

        for s in out:
            self.vp(f"      · [{s['decidability']}] {_vp_preview(s['question'])}"
                    f"  ← {s.get('source', '?')}")

        return out

    # ---------- 探针方向块 ----------
    def _target_text(self, view: "View", inp: Input) -> str:
        parts = []
        if inp.key_terms:
            parts.append(
                "【原始问题的核心词（底裤）】探针不能把这些词全丢开——"
                "它们是问题里最不能散掉的部分：\n  - " + "、".join(inp.key_terms))
        own = [u.get("desc", "") for u in view.untouched if u.get("desc")]
        if own:
            w = HARD_TARGET if self.phase.target_hardness == "hard" else SOFT_TARGET
            parts.append(f"【本层尚未触及的方面】{w}\n  - " + "\n  - ".join(own))
        if inp.upstream_untouched:
            for i, lst in enumerate(inp.upstream_untouched):
                if not lst:
                    continue
                ent = (inp.upstream_views[i].entry
                       if i < len(inp.upstream_views) else "")
                tag = _LAYER_LABEL.get(ent, f"上游{i+1}")
                if self.phase.target_hardness == "mixed":
                    w = HARD_TARGET if ent == "1" else SOFT_TARGET
                else:
                    w = HARD_TARGET if self.phase.target_hardness == "hard" else SOFT_TARGET
                descs = [u.get("desc", "") for u in lst if u.get("desc")]
                parts.append(f"【来自{tag}侧的未触及】{w}\n  - " + "\n  - ".join(descs))
        return "\n\n".join(parts) if parts else ""

    # ---------- 研究层探针 ----------
    def _probe_research(self, view: "View", inp: Input, pool: Pool) -> List[dict]:
        residue = [f"& {a.get('desc', '')}" for a in view.amps] + \
                  [f"... {t.get('desc', '')}" for t in view.threads]
        target_text = self._target_text(view, inp)

        subs = [s for s in pool.sub_questions
                if s.get("decidability") in _DEC_ANSWERABLE]
        subs_text = "\n".join(
            f"  - [{s.get('id')}] {s.get('question')}"
            f"（{s.get('decidability')}，权重 {s.get('weight')}"
            f"｜{s.get('status', 'open')}）"
            for s in subs) or "（无）"
        und_subs = [s for s in pool.sub_questions
                    if s.get("decidability") == "undecidable"]
        und_text = "\n".join(
            f"  - [{s.get('id')}] {s.get('question')}"
            for s in und_subs) or "（无）"
        if und_subs:
            und_text += ("\n    → 这些当前判为「不可判定」。若本圈材料里有能推翻这个"
                         "判定的线索，用 reclassifications 提出，附 evidence\n"
                         "      （编号照抄下方【可引用的证据编号】清单，或直接引原句）；"
                         "没有就保持原判。")
        open_def = [d for d in pool.deferrals if d.get("status") == "deferred"]
        def_text = "\n".join(
            f"  - [{d.get('id')}] 子问题 [{d.get('sub_id')}]"
            f"：{d.get('sub_question', '')}\n"
            f"      延迟理由：{d.get('reason', '')}\n"
            f"      回访条件：{d.get('revisit_condition', '')}"
            f"\n      → 本层请判断：回访条件满足了吗？"
            for d in open_def) or "（无）"

        if not residue and not subs_text.strip("（无）") and not open_def:
            return []

        prior = "\n".join(
            f"  - {p.get('question', '')}" for p in pool.probes[-8:]
        ) or "（无）"
        min_gain = float(
            self.config.get("probe", {}).get("min_gain", 0.3))
        # [E6] 停止阈值：与 min_gain 两把尺子（见常量注释）
        stop_floor = float(self.config.get("probe", {}).get(
            "stop_floor", _GAIN_STOP_FLOOR))

        system = (
            "你是【探针 · 自问】阶段（研究层）。\n"
            "你正在为回答【原始问题】而生发探针，并决定这一层「先处理什么、暂缓什么」。\n"
            "探针从上面**没消化完的东西**里生发，但**必须指向原始问题**。\n"
            f"{self.phase.probe_focus}\n"
            "1. 生成 1-3 个探针，每个给 expected_gain（0.0-1.0）和 link（怎么带回去）\n"
            "2. 每条探针必须用 covers 声明它碰了下方【本层未触及项】里的哪几项，\n"
            "   用编号引用（如 [\"T1\", \"T3\"]）。一条都没碰就填 []。\n"
            "   不要为了通过检查而乱填——covers 反映的是你这条探针的真实意图。\n"
            "3. ★ 若你判断**所有未触及项都推不动**，返回 \"probes\": []，\n"
            "   并在 no_probe_reason 里说明**为什么推不动**（指到具体哪几项）。\n"
            "   ★ 空探针配得上理由就是**合格答案**，不扣分；\n"
            "   空探针 + 空洞理由（或不写理由）会被记 lazy_empty。\n"
            "   宁可空，不要凑数——但要为『空』交代清楚。\n"
            "4. engagements：写**本圈真正触及的每一个子问题**（用 sub_id）。\n"
            "   不只是首次回答——你对已回答子问题的再确认、深化、反转，\n"
            "   也都要写进来。系统会按子问题当前状态自动区分：\n"
            "     首次触及 → answered；再次触及 → refinement。\n"
            "   若本圈碰了 3 个子问题，就写 3 条 engagements。\n"
            "   depth（0.0-1.0）可选填：1.0=完整回答；0.7=回答了但还有未消化的；\n"
            "   0.4=只碰了一下。不填默认 1.0。再次触及时 depth 表示本次增量。\n"
            "   ★ 不要因为'已经在 view 正文里说了'就省略 engagements——\n"
            "     正文是给用户读的，engagements 是给系统读的，两条通道。\n"
            "5. deferrals：暂缓的子问题。**必须给 revisit_condition**。\n"
            "6. reconfirmations / resolutions：对【上一层的延迟债务】——\n"
            "7. escalations：本圈发现它其实不可判定时写。**必须给 evidence**。\n"
            "8. reclassifications：**本圈有新证据推翻某个子问题的可判定性判定**\n"
            "   时写。三态之间**任意方向**都允许（decidable / partial /\n"
            "   undecidable 互转）——判定是当前值不是终审，只要能推翻就该改。\n"
            "   ★ 每条**必须**给 evidence：从下方【可引用的证据编号】里**照抄**\n"
            "     编号（A2 / P1 / T3 / S1 / C4 / ing），或直接引原句。\n"
            "     ★ 不要凭印象编编号——清单外的编号一律定位不到，整条驳回。\n"
            "     系统会核对：引用的东西此刻不在池里 → **整条驳回并留痕**。\n"
            "   ★ 没有新证据就不要写——空喊\"我觉得可以\"不算证据。\n"
            "   ★ 与 escalations 的区别：escalations 只覆盖\"迁向不可判定\"，\n"
            "     reclassifications 覆盖全部方向（含改回 decidable）。\n"
            "严格 JSON：\n"
            '{"probes":[{"question":"≤60字","link":"≤40字",'
            '"expected_gain":0.6,"covers":["T1"]}],'
            '"engagements":[{"sub_id":1,"how":"≤40字","depth":0.7}],'
            '"deferrals":[{"sub_id":3,"reason":"≤40字",'
            '"revisit_condition":"≤30字"}],'
            '"reconfirmations":[{"deferral_id":"d_001","reason":"≤30字"}],'
            '"resolutions":[{"deferral_id":"d_002","how":"≤40字"}],'
            '"escalations":[{"sub_id":5,"reason":"≤40字","evidence":["A2"]}],'
            '"reclassifications":[{"sub_id":5,"to":"decidable",'
            '"reason":"≤40字","evidence":["A2","P1"]}]}\n'
            + ANTI_PRETTY
            + self._self_block()
        )
        user = (
            f"【原始问题 / 锚点】\n{view.anchor}\n\n"
            f"【这一圈没消化完的】\n" + ("\n".join(residue) or "（无）") + "\n\n"
            f"【可判定子问题】\n{subs_text}\n\n"
            f"【不可判定子问题】\n{und_text}\n\n"
            f"【上一层的延迟债务】\n{def_text}\n\n"
            f"【已有的探针（不要重复）】\n{prior}"
        )
        cite_tbl = _citation_table(view, pool)
        if cite_tbl:
            cite_lines = "\n".join(
                f"  {cid}：{str(t)[:60]}" for cid, t in cite_tbl)
            user += ("\n\n【可引用的证据编号（escalations / reclassifications "
                     "的 evidence **只可从这里选**）】\n" + cite_lines
                     + "\n  ★ 这里的 T# 与下方【本层未触及项】的 T# 是两套编号：\n"
                       "    本清单给 evidence 用，那份给 covers 用，别混用。")
        untouched_items = [str(u.get("desc", "")).strip()
                           for u in (view.untouched or [])
                           if str(u.get("desc", "")).strip()]
        if untouched_items:
            ut_lines = "\n".join(
                f"  T{i+1}. {d}" for i, d in enumerate(untouched_items))
            user += ("\n\n【本层未触及项（covers 用编号引用）】\n"
                     + ut_lines)
        if target_text:
            user += f"\n\n【可以碰的点（研究层：至少涉及其中一项）】\n{target_text}"
        user += (
            "\n\n【本层选择】\n"
            "至少推进一件（碰一个子问题 / 新结构性 & / 提一条延迟）。\n"
            "延迟必须有回访条件；研究允许延迟，但不允许永远拖着。\n"
            "★ 若你判断所有未触及项都推不动：probes 可以返回 []，\n"
            "  但必须在 no_probe_reason 里写明**为什么**（指到具体哪几项）。\n"
        )
        if deferred_ratio_of(pool) > 0.6 and open_def:
            user += (
                "\n⚠️ 反躺平：当前延迟债务占比已超过 0.6，本层**必须**至少清偿\n"
                "一个延迟债务（写进 resolutions，或 engagements 回答对应子问题）。\n"
            )

        raw = self.llm.call(system, user, 0.5, 1900, json_mode=True, stage=_thinking_stage(self.config, 'probe_research'))
        data = self.llm.parse_json(raw) or {}

        # [E5] 接住**响应的根级** no_probe_reason（空探针的正当理由）。
        _npr = str(data.get("no_probe_reason", "") or "").strip()
        if _npr:
            view.no_probe_reason = _npr

        out: List[dict] = []
        _e6_seen = 0        # [E6] 候选探针数（含被剪掉的）
        _e6_max_gain = 0.0  # [E6] 候选里最大的 G
        for p in (data.get("probes") or []):
            if not isinstance(p, dict):
                continue
            q = str(p.get("question", "")).strip()[:200]
            link = str(p.get("link", "")).strip()[:120]
            try:
                gain = float(p.get("expected_gain", 0.0))
            except (TypeError, ValueError):
                gain = 0.0
            gain = max(0.0, min(1.0, gain))
            _e6_seen += 1
            _e6_max_gain = max(_e6_max_gain, gain)
            if not q or len(q) < 6 or not link or gain < min_gain:
                continue
            covers_raw = p.get("covers") or []
            covers: List[str] = []
            if isinstance(covers_raw, list):
                for c in covers_raw:
                    s = str(c).strip()
                    if s:
                        covers.append(s[:40])
            # [E1 双写落盘] 引擎算的 G 与它的**来源**必须落在**同一份**
            #   dict 上 —— 只写进「喂下一轮」的副本 = 产物里读不到来源。
            _eng = p.get("expected_gain_engine", None)
            out.append({"question": q, "link": link,
                        "expected_gain": round(gain, 2),
                        "expected_gain_engine": (
                            round(float(_eng), 4) if _eng is not None else None),
                        "gain_source": str(p.get("gain_source") or "model"),
                        "covers": covers})

        if not out:
            self._e6_note_stop(pool, view, "research",
                               _e6_seen, _e6_max_gain, min_gain,
                               stop_floor)

        sub_by_id = {s.get("id"): s for s in pool.sub_questions}

        def _sub_text(sid):
            sq = sub_by_id.get(sid)
            return sq.get("question", "") if sq else f"子问题{sid}"

        for e in (data.get("engagements") or []):
            if not isinstance(e, dict):
                continue
            sid = e.get("sub_id")
            if sid is None:
                continue
            try:
                sid = int(sid)
            except (TypeError, ValueError):
                continue
            view.engagements.append({
                "sub_id": sid, "target": _sub_text(sid)[:100],
                "how": str(e.get("how", "")).strip()[:160],
                "depth": e.get("depth", None)})

        for d in (data.get("deferrals") or []):
            if not isinstance(d, dict):
                continue
            try:
                sid = int(d.get("sub_id"))
            except (TypeError, ValueError):
                continue
            if sid not in sub_by_id:
                _r = str(d.get('reason', ''))[:60]
                _rc = str(d.get('revisit_condition', ''))[:60]
                view.errors.append(
                    'unsynced_deferral sub_id=' + str(sid)
                    + ' reason=' + _r + ' revisit=' + _rc)
                continue
            view.deferrals.append({
                "sub_id": sid,
                "reason": str(d.get("reason", "")).strip()[:200],
                "revisit_condition": str(d.get("revisit_condition", "")).strip()[:120]})

        for r in (data.get("reconfirmations") or []):
            if isinstance(r, dict):
                view.reconfirmations.append({
                    "deferral_id": str(r.get("deferral_id", "")).strip(),
                    "reason": str(r.get("reason", "")).strip()[:160]})
        for r in (data.get("resolutions") or []):
            if isinstance(r, dict):
                view.resolutions.append({
                    "deferral_id": str(r.get("deferral_id", "")).strip(),
                    "how": str(r.get("how", "")).strip()[:160]})

        for e in (data.get("escalations") or []):
            if not isinstance(e, dict):
                continue
            try:
                sid = int(e.get("sub_id"))
            except (TypeError, ValueError):
                continue
            if sid in sub_by_id:
                view.escalations.append({
                    "sub_id": sid,
                    "reason": str(e.get("reason", "")).strip()[:200],
                    "evidence": _ev_list(e.get("evidence"))})

        for e in (data.get("reclassifications") or []):
            if not isinstance(e, dict):
                continue
            try:
                sid = int(e.get("sub_id"))
            except (TypeError, ValueError):
                continue
            if sid in sub_by_id:
                view.reclassifications.append({
                    "sub_id": sid,
                    "to": str(e.get("to", "")).strip().lower()[:20],
                    "reason": str(e.get("reason", "")).strip()[:200],
                    "evidence": _ev_list(e.get("evidence"))})

        out.sort(key=lambda x: -x["expected_gain"])
        out = out[:3]
        for p in out:
            self.vp(f"   🌱 {p['question']}")
            self.vp(f"      ↩ 回来：{p['link']}｜增益{p['expected_gain']}")
            if "covers" in p:
                self.vp(f"      ✓ covers={p['covers']}")
        for e in view.engagements:
            self.vp(f"   🤝 推进：子问题[{e['sub_id']}] {_vp_preview(e['target'])}（{e['how']}）")
        for d in view.deferrals:
            self.vp(f"   ⏳ 延迟意图：子问题[{d['sub_id']}]"
                    f"（回访条件：{d['revisit_condition']}）")
        for r in view.reconfirmations:
            self.vp(f"   ✓ 确认债务：{r['deferral_id']}")
        for r in view.resolutions:
            self.vp(f"   ✔ 清偿：{r['deferral_id']}")
        for e in view.escalations:
            _ev = "、".join(e.get("evidence") or []) or "（无）"
            self.vp(f"   ⬆ 提案→不可判定：子问题[{e['sub_id']}]"
                    f"（{e['reason']}｜证据：{_ev}）")
        for e in view.reclassifications:
            _ev = "、".join(e.get("evidence") or []) or "（无）"
            _to = _DEC_STATE_CN.get(e.get("to"), e.get("to") or "?")
            self.vp(f"   ↻ 提案→{_to}：子问题[{e['sub_id']}]"
                    f"（{e['reason']}｜证据：{_ev}）")

        has_struct_amp = any(a.get("type") == "structural"
                             for a in view.amps)
        if (not view.engagements and not view.deferrals
                and not view.escalations and not has_struct_amp and not out):
            view.idle = True
            self.vp("   ⚠️ 本层空转（没推进、没延迟、没新结构&、没探针）")

        return out

    # ---------- 对撞层探针 ----------
    def _probe_duel(self, view: "View", inp: Input, pool: Pool) -> List[dict]:
        residue = [f"& {a.get('desc', '')}" for a in view.amps] + \
                  [f"... {t.get('desc', '')}" for t in view.threads]
        target_text = self._target_text(view, inp)
        tensions_text = _quadrant_text(pool.duel_alignment or {})

        active_duel = [s for s in pool.duel_suspensions
                       if s.get("status") in ("active", "stable")]
        duel_text = "\n".join(
            f"  - [{s.get('id', '')}] 悬置了张力「{s.get('target', '')}」"
            f"（{s.get('quadrant', '') or '未归类'}）因为："
            f"{s.get('reason') or '（直觉，无理由）'}"
            + ("　← 已多轮未复核，请确认或撤回" if s.get("needs_review") else "")
            for s in active_duel) or "（无）"

        if not residue and not tensions_text and not active_duel:
            return []

        prior = "\n".join(
            f"  - {p.get('question', '')}" for p in pool.probes[-8:]
        ) or "（无）"
        min_gain = float(self.config.get("probe", {}).get("min_gain", 0.3))
        # [E6] 停止阈值：与 min_gain 两把尺子（见常量注释）
        stop_floor = float(self.config.get("probe", {}).get(
            "stop_floor", _GAIN_STOP_FLOOR))

        system = (
            "你是【探针 · 自问】阶段（对撞层）。\n"
            "你面对两个 view（修行 / 研究）之间的**具体张力**，"
            "并决定这一层「裁决哪个、悬置哪个」。\n"
            f"{self.phase.probe_focus}\n"
            "1. probes：1-3 个探针，各给 question/link/expected_gain；\n"
            "2. adjudications：对既有张力的**裁决**。polarity 三选。\n"
            "3. duel_suspensions：把「暂时不解决的张力」悬置起来（前瞻决定）。\n"
            "4. 硬约束：**每轮至少裁决一个张力**。\n"
            "5. reconfirmations / revocations：对【上一层的张力悬置】的回应。\n"
            "严格 JSON：\n"
            '{"probes":[{"question":"≤60字","link":"≤40字","expected_gain":0.6}],'
            '"adjudications":[{"tension":"≤40字","polarity":"0|1|both",'
            '"how":"≤40字"}],'
            '"duel_suspensions":[{"tension":"≤40字","quadrant":"③",'
            '"reason":"≤40字","reason_type":"explicit|intuitive"}],'
            '"reconfirmations":[{"suspension_id":"t_001","reason":"≤30字"}],'
            '"revocations":[{"suspension_id":"t_002","reason":"≤40字"}]}\n'
            + ANTI_PRETTY
            + self._self_block()
        )
        user = (
            f"【原始问题 / 锚点】\n{view.anchor}\n\n"
            f"【这一圈没消化完的】\n" + ("\n".join(residue) or "（无）") + "\n\n"
            f"【四象限张力】\n" + (tensions_text or "（无）") + "\n\n"
            f"【上一层悬置的张力】\n{duel_text}\n\n"
            f"【已有的探针（不要重复）】\n{prior}"
        )
        if target_text:
            user += f"\n\n【可以碰的点】\n{target_text}"
        user += (
            "\n\n【本层选择】\n"
            "至少裁决一个张力（adjudications 或 duel_suspensions）。\n"
            "极性与悬置是两件事：裁决是回溯，悬置是前瞻。\n"
        )

        raw = self.llm.call(system, user, 0.5, 1900, json_mode=True, stage=_thinking_stage(self.config, 'probe_duel'))
        data = self.llm.parse_json(raw) or {}

        # [E5] 接住**响应的根级** no_probe_reason（空探针的正当理由）。
        _npr = str(data.get("no_probe_reason", "") or "").strip()
        if _npr:
            view.no_probe_reason = _npr

        out: List[dict] = []
        _e6_seen = 0        # [E6] 候选探针数（含被剪掉的）
        _e6_max_gain = 0.0  # [E6] 候选里最大的 G
        for p in (data.get("probes") or []):
            if not isinstance(p, dict):
                continue
            q = str(p.get("question", "")).strip()[:200]
            link = str(p.get("link", "")).strip()[:120]
            try:
                gain = float(p.get("expected_gain", 0.0))
            except (TypeError, ValueError):
                gain = 0.0
            gain = max(0.0, min(1.0, gain))
            _e6_seen += 1
            _e6_max_gain = max(_e6_max_gain, gain)
            if not q or len(q) < 6 or not link or gain < min_gain:
                continue
            out.append({"question": q, "link": link,
                        "expected_gain": round(gain, 2)})

        for a in (data.get("adjudications") or []):
            if not isinstance(a, dict):
                continue
            tension = str(a.get("tension", "")).strip()[:120]
            pol = str(a.get("polarity", "")).strip()
            if pol not in ("0", "1", "both"):
                pol = "both"
            if not tension:
                continue
            view.adjudications.append({
                # ★ [裁决维度拆分] 依据：多评委框架 + 红线「自省是另一个
                #   视角，不可合并」⇒ 裁决依据**拆维留痕**，不合成一个 how。
                "aspect": adjudication_aspect(
                    str(a.get("tension", "")), str(a.get("how", ""))),
                "tension": tension, "polarity": pol,
                "how": str(a.get("how", "")).strip()[:160]})

        # [P1-4] 极性配额：both 占绝对多数 = 什么都没裁
        self._enforce_both_quota(view)

        for s in (data.get("duel_suspensions") or []):
            if not isinstance(s, dict):
                continue
            tension = str(s.get("tension", "")).strip()[:160]
            if not tension:
                continue
            view.duel_suspensions.append({
                "tension": tension,
                "quadrant": str(s.get("quadrant", "")).strip()[:2],
                "reason": str(s.get("reason", "")).strip()[:200],
                "reason_type": str(s.get("reason_type", "explicit")).lower()})

        for r in (data.get("reconfirmations") or []):
            if isinstance(r, dict):
                view.reconfirmations.append({
                    "suspension_id": str(r.get("suspension_id", "")).strip(),
                    "reason": str(r.get("reason", "")).strip()[:160]})
        for r in (data.get("revocations") or []):
            if isinstance(r, dict):
                view.revocations.append({
                    "suspension_id": str(r.get("suspension_id", "")).strip(),
                    "reason": str(r.get("reason", "")).strip()[:160]})

        if not out:
            self._e6_note_stop(pool, view, "duel", _e6_seen,
                               _e6_max_gain, min_gain, stop_floor)

        out.sort(key=lambda x: -x["expected_gain"])
        out = out[:3]
        for p in out:
            self.vp(f"   🌱 {p['question']}")
            self.vp(f"      ↩ 回来：{p['link']}｜增益{p['expected_gain']}")
        for a in view.adjudications:
            self.vp(f"   ⚖️ 裁决张力：{a['tension']} → 极性 {a['polarity']}")
        for s in view.duel_suspensions:
            self.vp(f"   ⏸ 悬置张力：{s['tension']}（{s.get('quadrant', '?')}）")
        for r in view.reconfirmations:
            self.vp(f"   ✓ 确认张力悬置：{r['suspension_id']}")
        for r in view.revocations:
            self.vp(f"   ✗ 撤回张力悬置：{r['suspension_id']}")

        if (not view.adjudications and not view.duel_suspensions and not out):
            view.idle = True
            self.vp("   ⚠️ 本层无新张力（材料耗尽）")

        return out

    # ---------- 元层探针 ----------
    def _probe_meta(self, view: "View", inp: Input, pool: Pool) -> List[dict]:
        residue = [f"& {a.get('desc', '')}" for a in view.amps] + \
                  [f"... {t.get('desc', '')}" for t in view.threads]
        target_text = self._target_text(view, inp)

        duel_tensions = []
        _duel_all_ids = set()
        for _i, v in enumerate(inp.upstream_views or []):
            if getattr(v, "entry", "") != "both":
                continue
            _up = list(inp.upstream_pools or [])
            _src = _up[_i] if _i < len(_up) else None
            _raw = (getattr(_src, "duel_suspensions", None)
                    if _src is not None else None)
            if not _raw:                      # 池里拿不到再退回 view
                _raw = v.duel_suspensions or []
            _duel_all_ids = {str(s.get("id")) for s in _raw if s.get("id")}
            duel_tensions = [s for s in _raw
                             if s.get("status") in ("active", "stable")]
            break
        tension_text = "\n".join(
            f"  - [{s.get('id', '') or '?'}]"
            f"（{s.get('quadrant', '') or '?'}）{s.get('target', '')}"
            for s in duel_tensions) or "（无）"

        active_susp = [s for s in pool.suspensions
                       if s.get("status") in ("active", "stable")]
        susp_text = "\n".join(
            f"  - [{s.get('id', '')}] 决定不消解「{s.get('target', '')}」，因为："
            f"{s.get('reason') or '（直觉，无理由）'}"
            + ("　← 已多轮未复核" if s.get("needs_review") else "")
            for s in active_susp) or "（无）"

        if not residue and not tension_text and not active_susp:
            return []

        prior = "\n".join(
            f"  - {p.get('question', '')}" for p in pool.probes[-8:]
        ) or "（无）"
        min_gain = float(self.config.get("probe", {}).get("min_gain", 0.3))
        # [E6] 停止阈值：与 min_gain 两把尺子（见常量注释）
        stop_floor = float(self.config.get("probe", {}).get(
            "stop_floor", _GAIN_STOP_FLOOR))

        system = (
            "你是【探针 · 自问】阶段（元层）。\n"
            "你面对三个子层已经各自处理完的东西，"
            "要做的是**元决策**：哪一类张力，我决定不消解。\n"
            f"{self.phase.probe_focus}\n"
            "1. probes：1-3 个探针，各给 question/link/expected_gain。\n"
            "2. engagements：**至少碰一个**。元层的「碰」= 对某类张力做出裁决。\n"
            "   ★ 你处置的是【对撞悬置的张力】里的哪一条，就把清单里\n"
            "     方括号中的编号**原样复制**进 tension_id（t_ 开头）。\n"
            "     ★ s_ 开头的是**元层自己的悬置编号**，那是 suspension_id，\n"
            "       填进 tension_id 一律定位不到。两套编号不能互换。\n"
            "     不许自造编号，不许抄示例，不许写「（无）」——\n"
            "     定位不到的编号等于没交代。这是清算对账用的。\n"
            "   ★ 判「这一类缺判据、不可裁定」**也算一种处置**，照写并带\n"
            "     编号 —— 说清为什么判不了，本身就是交代。\n"
            "3. suspensions：把「决定不消解的张力类别」写在这里。\n"
            "   允许 reason_type=intuitive。同样要带 tension_id。\n"
            "4. reconfirmations / revocations：对【元层之前的悬置决定】的回应。\n"
            "★ target 写完整（≤60 字），别压缩成短标签：清算时编号对不上\n"
            "   的话，只能靠 target 的措辞去比对，压太短就对不上了。\n"
            "严格 JSON：\n"
            '{"probes":[{"question":"≤60字","link":"≤40字","expected_gain":0.6}],'
            '"engagements":[{"tension_id":"<从清单原样复制>","target":"≤60字",'
            '"how":"≤40字"}],'
            '"suspensions":[{"tension_id":"<从清单原样复制>","target":"≤60字",'
            '"reason":"≤40字","reason_type":"explicit|intuitive"}],'
            '"reconfirmations":[{"suspension_id":"<本层悬置编号>",'
            '"reason":"≤30字"}],'
            '"revocations":[{"suspension_id":"<本层悬置编号>",'
            '"reason":"≤40字"}]}\n'
            + ANTI_PRETTY
            + self._self_block()
        )
        user = (
            f"【原始问题 / 锚点】\n{view.anchor}\n\n"
            f"【这一圈没消化完的】\n" + ("\n".join(residue) or "（无）") + "\n\n"
            f"【对撞悬置的张力（要不要消解的候选）】\n{tension_text}\n\n"
            f"【元层之前的悬置决定】\n{susp_text}\n\n"
            f"【已有的探针（不要重复）】\n{prior}"
        )
        if target_text:
            user += f"\n\n【可以碰的点】\n{target_text}"
        user += (
            "\n\n【本层选择】\n"
            "至少对一类张力做出裁决（消解，或决定不消解写进 suspensions）。\n"
            "★ 处置【对撞悬置的张力】里的条目时，把**清单方括号里的编号**\n"
            "  原样复制进 tension_id 字段（清单形如「- [t_XXX]（③）…」）。\n"
            "  ★ 只填 t_ 开头的编号（那是**对撞层**发的张力编号）；\n"
            "    s_ 开头的是**元层自己的悬置编号**，只能填 suspension_id，\n"
            "    填进 tension_id 一律定位不到。\n"
            "  ★ 不许自造编号，不许抄示例，不许写「（无）」。清单外的编号\n"
            "    一律不算，抄错等于没交代。这是清算对账的依据。\n"
        )

        raw = self.llm.call(system, user, 0.5, 1900, json_mode=True, stage=_thinking_stage(self.config, 'probe_meta'))
        data = self.llm.parse_json(raw) or {}

        # [E5] 接住**响应的根级** no_probe_reason（空探针的正当理由）。
        _npr = str(data.get("no_probe_reason", "") or "").strip()
        if _npr:
            view.no_probe_reason = _npr

        out: List[dict] = []
        _e6_seen = 0        # [E6] 候选探针数（含被剪掉的）
        _e6_max_gain = 0.0  # [E6] 候选里最大的 G
        for p in (data.get("probes") or []):
            if not isinstance(p, dict):
                continue
            q = str(p.get("question", "")).strip()[:200]
            link = str(p.get("link", "")).strip()[:120]
            try:
                gain = float(p.get("expected_gain", 0.0))
            except (TypeError, ValueError):
                gain = 0.0
            gain = max(0.0, min(1.0, gain))
            _e6_seen += 1
            _e6_max_gain = max(_e6_max_gain, gain)
            if not q or len(q) < 6 or not link or gain < min_gain:
                continue
            out.append({"question": q, "link": link,
                        "expected_gain": round(gain, 2)})

        _valid_tids = {str(s.get("id")) for s in duel_tensions
                       if s.get("id")}
        for e in (data.get("engagements") or []):
            if not isinstance(e, dict):
                continue
            t = str(e.get("target", "")).strip()[:80]
            if not t:
                continue
            _tid = str(e.get("tension_id", "")).strip()[:16]
            if _tid and _tid not in _valid_tids:
                if _tid in _duel_all_ids:
                    _why = (f"该编号在池里存在但**已了结**"
                            f"（当前可引用的只有 {sorted(_valid_tids)}）")
                else:
                    _why = (f"池里没有这个编号（可能是自造/抄示例/"
                            f"串了 s_ 命名空间；当前可引用的只有 "
                            f"{sorted(_valid_tids)}）")
                view.errors.append(f"元层 tension_id 不合法：{_tid!r} —— {_why}")
                self.vp(f"   ✗ 元层 tension_id 不合法：{_tid!r} —— {_why}")
            view.engagements.append(
                {"target": t, "how": str(e.get("how", "")).strip()[:160],
                 "tension_id": _tid})

        for s in (data.get("suspensions") or []):
            if not isinstance(s, dict):
                continue
            t = str(s.get("target", "")).strip()[:120]
            if not t:
                continue
            rt = str(s.get("reason_type", "explicit")).lower()
            if rt not in SUSPENSION_REASON_TYPES:
                rt = "explicit"
            _tid = str(s.get("tension_id", "")).strip()[:16]
            view.suspensions.append({
                "target": t,
                "reason": str(s.get("reason", "")).strip()[:200],
                "reason_type": rt,
                "tension_id": _tid,
            })

        for r in (data.get("reconfirmations") or []):
            if not isinstance(r, dict):
                continue
            view.reconfirmations.append({
                "suspension_id": str(r.get("suspension_id", "")).strip(),
                "target": str(r.get("target", "")).strip(),
                "reason": str(r.get("reason", "")).strip()[:160]})
        for r in (data.get("revocations") or []):
            if not isinstance(r, dict):
                continue
            view.revocations.append({
                "suspension_id": str(r.get("suspension_id", "")).strip(),
                "target": str(r.get("target", "")).strip(),
                "reason": str(r.get("reason", "")).strip()[:160]})

        out.sort(key=lambda x: -x["expected_gain"])
        out = out[:3]
        if not out:
            self._e6_note_stop(pool, view, "meta", _e6_seen,
                               _e6_max_gain, min_gain, stop_floor)

        for p in out:
            self.vp(f"   🌱 {p['question']}")
            self.vp(f"      ↩ 回来：{p['link']}｜增益{p['expected_gain']}")
            if p.get("covers"):
                self.vp(f"      ✓ covers={p['covers']}")
        for e in view.engagements:
            self.vp(f"   🤝 元决策：{e['target']}（{e['how']}）")
        for s in view.suspensions:
            self.vp(f"   ⏸ 决定不消解：{s['target']}（{s['reason'] or '直觉，无理由'}）")
        for r in view.reconfirmations:
            self.vp(f"   ✓ 确认元层悬置：{r['suspension_id']}")
        for r in view.revocations:
            self.vp(f"   ✗ 撤回元层悬置：{r['suspension_id']}")

        if not view.engagements and not view.suspensions and not out:
            view.idle = True
            self.vp("   ⚠️ 无新元决策（没裁决、没决定不消解、没探针）")

        return out

    # ---------- 探针回归（总入口） ----------
    def _e6_note_stop(self, pool, view, layer, seen, max_gain,
                      min_gain, stop_floor):
        """[E6] 本轮 0 探针时统一留痕（四处探针解析共用这一处）。"""
        _rec = pool.note_probe_stop(layer, seen, max_gain,
                                    min_gain, stop_floor)
        if _rec["stop"]:
            self.vp(f"   ⏹ [E6] 停止信号：{layer} 层所有候选探针"
                    f" max_gain={_rec['max_gain']} < "
                    f"floor={_rec['stop_floor']} ⇒ 本轮只出不进"
                    f"（空探针合法）")
        else:
            self.vp(f"   ⏹ [E6] 本轮无探针（{_rec['reason']}，"
                    f"seen={_rec['seen']}）")
        return _rec

    def _phase_probe(self, view: "View", inp: Input, pool: Pool) -> List[dict]:
        if self.entry == "1":
            return self._probe_research(view, inp, pool)
        if self.entry == "both":
            return self._probe_duel(view, inp, pool)
        if self.entry == "all":
            return self._probe_meta(view, inp, pool)

        residue = [f"& {a.get('desc', '')}" for a in view.amps] + \
                  [f"... {t.get('desc', '')}" for t in view.threads]
        target_text = self._target_text(view, inp)
        active_susp = [s for s in pool.suspensions
                       if s.get("status") in ("active", "stable")]
        susp_text = "\n".join(
            f"  - [{s.get('id', '')}] 悬置了「{s.get('target', '')}」，因为："
            f"{s.get('reason') or '（直觉，无理由）'}"
            + ("　← 已多轮未复核，请确认或撤回" if s.get("needs_review") else "")
            for s in active_susp) or "（无）"

        if not residue and not target_text and not active_susp:
            return []

        prior = "\n".join(
            f"  - {p.get('question', '')}" for p in pool.probes[-8:]
        ) or "（无）"
        min_gain = float(self.config.get("probe", {}).get("min_gain", 0.3))
        # [E6] 停止阈值：与 min_gain 两把尺子（见常量注释）
        stop_floor = float(self.config.get("probe", {}).get(
            "stop_floor", _GAIN_STOP_FLOOR))

        system = (
            "你是【探针 · 自问】阶段。\n"
            "你正在为回答【原始问题】而生发探针，并决定这一层「碰什么、不碰什么」。\n"
            "探针从上面这些**没消化完的东西**里生发，但**必须指向原始问题**。\n"
            f"{self.phase.probe_focus}\n"
            "1. 探针必须推进，不能重复上面已有的内容\n"
            "2. 探针必须能把探索带回原始问题\n"
            "3. 生成 1-3 个探针\n"
            "4. 每个探针必须给出 expected_gain（0.0-1.0）\n"
            "5. 每个探针必须给出 link\n"
            "5b. 每条探针必须用 covers 声明它碰了下方【本层未触及项】"
            "里的哪几项，\n"
            "   用编号引用（如 [\"T1\", \"T3\"]）。一条都没碰就填 []。\n"
            "   不要为了通过检查而乱填——covers 反映的是你这条探针的真实意图。\n"
            "6. 若确实推不动，probes 返回空数组\n"
            "7. engagements：**至少碰一个**。\n"
            "8. suspensions：只收【主动悬置】（见下方分界规则）。\n"
            "9. threads：只收【硬边界】（见下方分界规则）。\n"
            "10. reconfirmations / revocations："
            "对【上一层的悬置决定】的回应。\n"
            + SUSPENSION_VS_THREAD_RULE +
            "严格 JSON：\n"
            '{"probes":[{"question":"≤60字","link":"≤40字",'
            '"expected_gain":0.6,"covers":["T1"]}],'
            '"engagements":[{"target":"≤30字","how":"≤40字"}],'
            '"suspensions":[{"target":"≤30字","reason":"≤40字",'
            '"reason_type":"explicit|intuitive"}],'
            '"threads":["≤40字"],'
            '"reconfirmations":[{"suspension_id":"<本层悬置编号>",'
            '"reason":"≤30字"}],'
            '"revocations":[{"suspension_id":"<本层悬置编号>",'
            '"reason":"≤40字"}]}\n'
            + ANTI_PRETTY
            + self._self_block()
        )
        user = (
            f"【原始问题 / 锚点】\n{view.anchor}\n\n"
            f"【这一圈没消化完的】\n" + ("\n".join(residue) or "（无）") + "\n\n"
            f"【上一层的悬置决定】\n{susp_text}\n\n"
            f"【已有的探针（不要重复）】\n{prior}"
        )
        _fix86_untouched = [
            str(u.get("desc", "")).strip()
            for u in (view.untouched or [])
            if str(u.get("desc", "")).strip()
        ]
        if _fix86_untouched:
            _ut_lines = "\n".join(
                f"  T{i+1}. {d}"
                for i, d in enumerate(_fix86_untouched))
            user += ("\n\n【本层未触及项（covers 用编号引用）】\n"
                     + _ut_lines)
        if target_text:
            user += f"\n\n【可以碰的点（按本层要求）】\n{target_text}"
        user += (
            "\n\n【本层选择】\n"
            "你可以碰其中任意一个，也可以继续悬置，但要给出理由。\n"
            "至少碰一个（写进 engagements）。\n"
        )

        def _parse_probe_resp(_data):
            """ 解析一份探针响应，**不改 view**。
            返回 {probes, engagements, suspensions, reconfirmations,
                  revocations, threads, boundary_threads}。
            主路径与重试路径共用 —— 不复制粘贴解析逻辑。"""
            _probes: List[dict] = []
            _e6_seen = 0        # [E6] 候选探针数（含被剪掉的）
            _e6_max_gain = 0.0  # [E6] 候选里最大的 G
            for p in (_data.get("probes") or []):
                if not isinstance(p, dict):
                    continue
                q = str(p.get("question", "")).strip()[:200]
                link = str(p.get("link", "")).strip()[:120]
                try:
                    gain = float(p.get("expected_gain", 0.0))
                except (TypeError, ValueError):
                    gain = 0.0
                gain = max(0.0, min(1.0, gain))
                _e6_seen += 1
                _e6_max_gain = max(_e6_max_gain, gain)
                if not q or len(q) < 6 or not link or gain < min_gain:
                    continue
                covers_raw = p.get("covers")
                covers: List[str] = []
                if isinstance(covers_raw, list):
                    for c in covers_raw:
                        s = str(c).strip()
                        if s:
                            covers.append(s[:40])
                _show_diag = bool(self.config.get("output", {}).get(
                    "show_probe_diag", False))
                if covers_raw is None:
                    self.vp("      [fix-89 diag] 探针 covers 字段缺失")
                elif not isinstance(covers_raw, list):
                    self.vp(f"      [fix-89 diag] 探针 covers 类型非 list："
                            f"{type(covers_raw).__name__}")
                elif _show_diag:
                    self.vp(f"      [fix-89 diag] covers_raw={covers_raw}"
                            f" → parsed={covers}")
                _probes.append({"question": q, "link": link,
                                "expected_gain": round(gain, 2),
                                "covers": covers})
            _engs = []
            for e in (_data.get("engagements") or []):
                if not isinstance(e, dict):
                    continue
                t = str(e.get("target", "")).strip()[:80]
                if not t:
                    continue
                _engs.append({"target": t,
                              "how": str(e.get("how", "")).strip()[:160]})
            _susps = []
            for s in (_data.get("suspensions") or []):
                if not isinstance(s, dict):
                    continue
                t = str(s.get("target", "")).strip()[:120]
                if not t:
                    continue
                rt = str(s.get("reason_type", "explicit")).lower()
                if rt not in SUSPENSION_REASON_TYPES:
                    rt = "explicit"
                _susps.append({
                    "target": t,
                    "reason": str(s.get("reason", "")).strip()[:200],
                    "reason_type": rt})
            _recs = []
            for r in (_data.get("reconfirmations") or []):
                if not isinstance(r, dict):
                    continue
                _recs.append({
                    "suspension_id":
                        str(r.get("suspension_id", "")).strip(),
                    "target": str(r.get("target", "")).strip(),
                    "reason": str(r.get("reason", "")).strip()[:160]})
            _revs = []
            for r in (_data.get("revocations") or []):
                if not isinstance(r, dict):
                    continue
                _revs.append({
                    "suspension_id":
                        str(r.get("suspension_id", "")).strip(),
                    "target": str(r.get("target", "")).strip(),
                    "reason": str(r.get("reason", "")).strip()[:160]})
            _ths = []
            _bt = 0
            _seen_desc: List[str] = []
            for t in (_data.get("threads") or []):
                d = str(t).strip()[:200] if not isinstance(t, dict) \
                    else str(t.get("desc", "")).strip()[:200]
                if not d or len(d) < 4:
                    continue
                if any(_similar(d, x, 0.8) for x in _seen_desc):
                    continue
                if any(_similar(d, str(x.get("desc", "")), 0.8)
                       for x in view.threads):
                    continue
                if any(_similar(d, str(x.get("desc", "")), 0.8)
                       for x in (pool.threads or [])):
                    continue
                _seen_desc.append(d)
                _ths.append({"desc": d, "kind": "thread",
                             "source": "probe_boundary"})
                _bt += 1
            _probes.sort(key=lambda x: -x["expected_gain"])
            return {"probes": _probes[:3],
                    "e6_seen": _e6_seen,
                    "e6_max_gain": _e6_max_gain,
                    "engagements": _engs,
                    "suspensions": _susps,
                    "reconfirmations": _recs,
                    "revocations": _revs,
                    "threads": _ths,
                    "boundary_threads": _bt}

        def _absorb_probe(_p):
            """把解析结果填进 view。"""
            view.engagements.extend(_p["engagements"])
            view.suspensions.extend(_p["suspensions"])
            view.reconfirmations.extend(_p["reconfirmations"])
            view.revocations.extend(_p["revocations"])
            view.threads.extend(_p["threads"])

        raw = self.llm.call(system, user, 0.5, 1900, json_mode=True, stage=_thinking_stage(self.config, 'phase_probe'))
        data = self.llm.parse_json(raw) or {}
        # [E5] 接住响应的根级 no_probe_reason（空探针的正当理由）。
        _npr = str(data.get("no_probe_reason", "") or "").strip()
        if _npr:
            view.no_probe_reason = _npr
        _p1 = _parse_probe_resp(data)
        _absorb_probe(_p1)
        _boundary_threads = _p1["boundary_threads"]
        out = list(_p1["probes"])
        _e6_p1_seen = _p1.get("e6_seen", 0)
        _e6_p1_gain = _p1.get("e6_max_gain", 0.0)

        _has_progress = (bool(view.engagements) or bool(view.suspensions)
                         or bool(out))
        if not _has_progress and not getattr(inp, "is_last_round", False):
            self.vp("   ♻️ 本层未碰任何一项，重试探针（强制至少碰一个）")
            _force_user = user + (
                "\n\n【★ 强制】上一次你没有写 engagements —— 本层必须"
                "有至少一个 engagement。哪怕只碰一个也行，不许空着。"
                "若真的推不动任何一项，就在 engagement 里写"
                "「尝试碰 X 但推不动，因为 Y」——那也是碰。"
            )
            try:
                raw2 = self.llm.call(system, _force_user, 0.5, 1900,
                                     json_mode=True, stage=_thinking_stage(self.config, 'phase_probe'))
                data2 = self.llm.parse_json(raw2) or {}
                _p2 = _parse_probe_resp(data2)
                _absorb_probe(_p2)
                _boundary_threads += _p2["boundary_threads"]
                if _p2["probes"]:
                    out = _p2["probes"]
                self.vp(f"   ♻️ 重试后：碰了 {len(view.engagements)} 条 / "
                        f"悬置 {len(view.suspensions)} 条 / "
                        f"探针 {len(out)} 个")
            except Exception as _e:
                view.errors.append(f"探针强制重试失败：{_e}")
                self.vp(f"   ✗ 探针强制重试失败：{_e}")

        if not out:
            self._e6_note_stop(pool, view, "phase", _e6_p1_seen,
                               _e6_p1_gain, min_gain, stop_floor)

        for p in out:
            self.vp(f"   🌱 {p['question']}")
            self.vp(f"      ↩ 回来：{p['link']}｜增益{p['expected_gain']}")
            _cov = p.get("covers") or []
            if _cov:
                self.vp(f"      ✓ covers={_cov}")
            else:
                self.vp("      ✗ covers=（空，模型未输出或输出为空）")
        for e in view.engagements:
            self.vp(f"   🤝 碰了：{e['target']}（{e['how']}）")
        for s in view.suspensions:
            self.vp(f"   ⏸ 悬置：{s['target']}"
                    f"（{s['reason'] or '直觉，无理由'}）")
        if _boundary_threads:
            self.vp(f"   🧵 硬边界归线头 {_boundary_threads} 条"
                    f"（推不动的，不占主动悬置）")
        for r in view.reconfirmations:
            self.vp(f"   ✓ 确认悬置：{r['suspension_id'] or r['target']}")
        for r in view.revocations:
            self.vp(f"   ✗ 撤回悬置：{r['suspension_id'] or r['target']}")

        if not view.engagements and not view.suspensions and not out:
            view.idle = True
            self.vp("   ⚠️ 本层空转（没碰、没新悬置、没探针）")

        return out

    # ---------- 多样性判据 ----------
    @staticmethod
    def _polarity_why_diversity(cands: List[dict]) -> float:
        texts = [str(c.get("polarity_why", "")) for c in cands
                 if c.get("polarity_why")]
        if len(texts) < 2:
            return 1.0
        all_kw = set()
        total = 0
        for t in texts:
            kws = _kw(t, 6)
            all_kw |= kws
            total += len(kws)
        if total == 0:
            return 1.0
        return len(all_kw) / total

    @staticmethod
    def _why_position_diversity(cands: List[dict]) -> float:
        texts = [str(c.get("why_position", "")) for c in cands
                 if c.get("why_position")]
        if len(texts) < 2:
            return 1.0
        all_kw = set()
        total = 0
        for t in texts:
            kws = _kw(t, 6)
            all_kw |= kws
            total += len(kws)
        if total == 0:
            return 1.0
        return len(all_kw) / total

    # ---------- position 诊断 ----------
    def _dump_position_diagnostic(self, view: View, anchor: str,
                                  round_no: int) -> Optional[Path]:
        if not view.candidates:
            return None
        try:
            d = Path(self.config["output"].get("save_dir", "outputs"))
            d.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            f = d / f"diagnostic_position_{self.entry}_{ts}.log"
            positions = [c.get("position", "?") for c in view.candidates]
            same_pos = positions[0] if positions else "?"
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(f"# position_all_same 诊断\n")
                fh.write(f"entry={self.entry}\n")
                fh.write(f"round={round_no}\n")
                fh.write(f"anchor={anchor}\n")
                fh.write(f"same_position={same_pos}\n")
                fh.write(f"candidate_count={len(view.candidates)}\n\n")
                for i, c in enumerate(view.candidates, 1):
                    fh.write(
                        f"[{i}] attr={c.get('attribute','?')} "
                        f"pos={c.get('position','?')} "
                        f"src={c.get('source','?')}\n")
                    fh.write(f"    desc: {c.get('desc','')}\n")
                    fh.write(
                        f"    why_position: {c.get('why_position','')}\n\n")
            return f
        except Exception as e:
            logger.warning("position 诊断 dump 失败: %s", e)
            return None

    # ---------- 质量检查 ----------
    def _quality_check(self, view: View, pool: Pool,
                       round_no: int = 0, *,
                       write_diag: bool = True) -> List[str]:
        """质量线索。

        [v1.21.71 F11] `write_diag` 只管一件事：**position_all_same 的
        诊断文件写不写**。
          · 圈内调用（`DGTF.run` 里）**保持默认 True** —— 诊断的对象本来
            就是"这一圈的候选怎么会全挤在同一个 position"；
          · 收尾复核（`_finalize_layer_common` 里，合并后重跑一次）传
            False —— 同一层会再写一份同名不同时间戳的
            `outputs/diagnostic_position_*.log`，是重复留痕。
        ⚠️ 压制时**不静默**：打一条 `logger.info` 说明"本该写、因收尾
        复核没写"。
        """
        flags = []
        _expanded_descs = getattr(view, "_expanded_descs", None)
        if _expanded_descs is not None and view.candidates:
            if not _expanded_descs:
                flags.append("candidates_backfilled(展开为0)")
            else:
                _unmatched = 0
                _total = 0
                for c in view.candidates:
                    d = str(c.get("desc", "")).strip()
                    if not d:
                        continue
                    _total += 1
                    if not any(_similar(d, x, _QC_POOL_SIM)
                               for x in _expanded_descs if x):
                        _unmatched += 1
                if _total > 0:
                    _r = _unmatched / _total
                    if _r >= _QC_BACKFILL_RATIO:
                        flags.append(
                            f"candidates_backfilled({_r:.0%})")
        _ing_rr = getattr(view, "_ing_rephrase_ratio", 0.0)
        _qc_rr = _spiral_num(self.config, "qc_rephrase_ratio", 0.5)
        if _ing_rr >= _qc_rr:
            flags.append(f"ing_rephrased_direct({_ing_rr:.0%})")
        dims = ("position",)
        for dim in dims:
            vals = [c.get(dim, "0") for c in view.candidates]
            if vals and len(set(vals)) == 1:
                if dim == "position":
                    div = self._why_position_diversity(view.candidates)
                    if div >= _QC_DIVERSITY_RATIO:
                        flags.append(f"{dim}_all_same_structural")
                    else:
                        flags.append(f"{dim}_all_same")
                    if write_diag:
                        dumped = self._dump_position_diagnostic(
                            view, view.anchor, round_no)
                        if dumped:
                            logger.info("position 诊断已写：%s", dumped)
                    else:
                        logger.info(
                            "position_all_same（收尾复核）："
                            "write_diag=False，不重复写诊断文件")
                else:
                    flags.append(f"{dim}_all_same")
        avals = [c.get("attribute", "0") for c in view.candidates]
        if avals and len(set(avals)) == 1:
            if len(avals) >= 5:
                flags.append("expand_imbalanced_benign")
            else:
                flags.append("expand_imbalanced")

        amp_cands = [c for c in view.candidates if c.get("is_amp_candidate")]
        if view.candidates and not amp_cands:
            if view.entry in ("both", "all"):
                if not view.amps:
                    flags.append("no_amp_at_all")
            else:
                flags.append("no_amp_candidates")

        for dim in dims:
            vals = [c.get(dim, "0") for c in view.candidates]
            _qc_both = _spiral_num(self.config, "qc_both_ratio", 0.6)
            if vals and vals.count("both") / len(vals) > _qc_both:
                flags.append(f"judge_mostly_both({dim})")

        if view.candidates:
            ratio = len(amp_cands) / len(view.candidates)
            if self.entry in ("0", "1"):
                thr = 0.75
            elif self.entry == "both":
                thr = 0.65
            else:
                thr = 0.75
            if ratio > thr:
                flags.append(f"too_many_amp_candidates({ratio:.0%})")

        if any(p in (view.collision or "") for p in _BOILERPLATE):
            flags.append("ing_has_boilerplate")

        if view.candidates and not view.collision:
            flags.append("ing_empty_with_candidates")

        pool_descs = [a.get("desc", "") for a in pool.amps] + \
                     [t.get("desc", "") for t in pool.threads]
        if view.candidates and pool_descs:
            overlap = sum(
                1 for c in view.candidates
                if any(_similar(c.get("desc", ""), pd, 0.85)
                       for pd in pool_descs)
            )
            if overlap / len(view.candidates) > _QC_OVERLAP_POOL_RATIO:
                flags.append("candidates_overlap_pool")

        if (not getattr(view, "probe_skipped", False)
                and (view.amps or view.threads) and not view.probes):
            errored = any(e.startswith("探针回归 失败")
                          for e in view.errors)
            flags.append("probe_failed" if errored
                         else "probe_return_empty")

        if (self.entry == "1" and view.untouched and view.probes):
            untouched_items = [str(u.get("desc", "")).strip()
                               for u in view.untouched
                               if str(u.get("desc", "")).strip()]
            # [E3] 靶子集合：**id → 文本**。优先用 A1 的 AspectUnit.id
            #   （本层未触及项的稳定编号）；没有 id 时退回「T{i+1}」
            #   这个**位置编号** —— 两种都要认，否则老产物会全判 bad_ref。
            _cov_targets: dict = {}
            for _i, _u in enumerate(view.untouched or []):
                _t = str(_u.get("desc", "")).strip()
                if not _t:
                    continue
                _uid = str(_u.get("id", "") or "").strip()
                _pos = "T%d" % (_i + 1)
                _cov_targets[_pos] = _t
                if _uid:
                    _cov_targets[_uid] = _t
                elif _uid is None or _uid == "":
                    # 位置编号与裸数字两种写法都收（模型老习惯）
                    _cov_targets[str(_i + 1)] = _t
            has_touch = False
            covers_seen = False
            bad_ref = False
            for p in view.probes:
                _pq = str(p.get("question", "")).strip()
                for c in (p.get("covers") or []):
                    c = str(c).strip()
                    if not c:
                        continue
                    covers_seen = True
                    _tgt = _cov_targets.get(c)
                    if _tgt is None:
                        # [E3] 归一化后再试一次（去 T 前缀 / 去 # 号）
                        _c2 = re.sub(r"^#", "", re.sub(r"^T(?=\d)", "", c))
                        _tgt = _cov_targets.get(_c2)
                    if _tgt is None:
                        # [E3] ★ 编号**不在任何 id 集合里** ⇒ 报 bad_ref。
                        #   这是「只查编号范围」永远抓不到的一类：
                        #   编号越界会被当「没覆盖」，但**不区分**是
                        #   「模型瞎指」还是「模型指对了但没写全覆盖」。
                        bad_ref = True
                        continue
                    # [E3] 编号对只是**必要条件**：还要**语义对得上**。
                    if (_similar(_pq, _tgt, _QC_DUP_SIM)
                            or _sim3(_pq, _tgt) >= _COVERS_SIM_MIN
                            or _overlap_coef(_pq, _tgt)
                            >= _COV_OVERLAP_MIN):
                        has_touch = True
                        break
                if has_touch:
                    break
            if not covers_seen:
                has_touch = any(
                    _similar(p.get("question", ""), u.get("desc", ""), 0.6)
                    for p in view.probes for u in view.untouched)
            if bad_ref:
                flags.append("probe_covers_bad_ref")
            if not has_touch:
                flags.append("probe_no_target_covered")

        # ── [E4] link 反查（**只留痕，不拦**：红线「未对齐合法」） ──
        #  ★ 反查靶子 = 池内条目的 id（Amp/Thread/Probe/AspectUnit）
        #    + 上游 manifest 的文本片段。查不到只记 probe_link_dangling，
        #    **不进** quality_verdict 的拦截项。
        try:
            _link_ids = set()
            for _i, _a in enumerate(pool.amps or [], 1):
                _link_ids.add(str(_a.get("id") or ("amp#%d" % _i)))
            for _i, _t2 in enumerate(pool.threads or [], 1):
                _link_ids.add(str(_t2.get("id") or ("th#%d" % _i)))
            for _i, _p2 in enumerate(pool.probes or [], 1):
                _link_ids.add(str(_p2.get("id") or ("probe#%d" % _i)))
            for _u2 in (view.aspect_units or []):
                _uid2 = str(_u2.get("id") or "").strip()
                if _uid2:
                    _link_ids.add(_uid2)
            _dangling = 0
            for _p3 in (view.probes or []):
                _lk = str(_p3.get("link", "")).strip()
                if not _lk:
                    continue
                _hit = False
                for _lid in _link_ids:
                    if _lid and re.search(
                            r"(?<![\w#])" + re.escape(_lid) + r"(?![\w#])",
                            _lk):
                        _hit = True
                        break
                if not _hit:
                    _dangling += 1
            if _dangling:
                flags.append("probe_link_dangling(%d)" % _dangling)
        except Exception:
            pass

        # ── [E5] 空探针的**双向**判据：honest_empty vs lazy_empty ──
        #  ★ 旧行为：`probe_return_empty` 一律罚空 —— 与提示词
        #    「推不动就返回空数组」**方向正好相反**。
        #  ★ 新行为：空 + 有理由 + 理由与 untouched 对得上 ⇒ honest_empty
        #    （**不罚**）；空 + 理由空洞/缺失 ⇒ lazy_empty（**留痕不罚分**）。
        if "probe_return_empty" in flags:
            _reason = ""
            for _p4 in (view.probes or []):
                _reason = str(_p4.get("no_probe_reason", "") or "").strip()
                if _reason:
                    break
            _vr = str(getattr(view, "no_probe_reason", "") or "").strip()
            _reason = _reason or _vr
            _ut_all = [str(u.get("desc", "")).strip()
                       for u in (view.untouched or [])
                       if str(u.get("desc", "")).strip()]
            _honest = False
            if len(_reason) >= _NO_PROBE_REASON_MIN:
                # ★ 「对得上」= 理由里提到了 untouched 清单里至少一项
                #   的语义内容（用 sim3 严尺子 + 词面兜底）。
                #   只是「写了一段长理由」不算 —— 那是换个方式空洞。
                _honest = any(
                    _sim3(_reason, _u) >= _COVERS_SIM_MIN
                    for _u in _ut_all) if _ut_all else False
            if _honest:
                flags = [f for f in flags if f != "probe_return_empty"]
                flags.append("honest_empty")
            else:
                flags = [f for f in flags if f != "probe_return_empty"]
                flags.append("lazy_empty")

        pool_amps = [a for a in pool.amps
                     if str(a.get("polarity", "")).strip() in ("0", "1", "both")]
        pool_pols = [str(a.get("polarity", "")).strip() for a in pool_amps]
        if len(pool_pols) >= 3 and len(set(pool_pols)) == 1:
            div = self._polarity_why_diversity(pool_amps)
            if div >= _QC_DIVERSITY_RATIO:
                flags.append(f"polarity_all_same_structural({pool_pols[0]})")
            else:
                flags.append(f"polarity_all_same({pool_pols[0]})")

        return flags

    def _quality_verdict(self, flags: List[str]) -> str:
        if not flags:
            return "判断正常，无质量线索"
        has = lambda *ks: any(k in f for f in flags for k in ks)
        _bf = [f for f in flags
               if f.startswith("candidates_backfilled")]
        _ir = [f for f in flags
               if f.startswith("ing_rephrased_direct")]
        if _bf or _ir:
            _parts = []
            if _bf:
                _parts.append(f"候选后补（{_bf[0]}）")
            if _ir:
                _parts.append(f"ing 复述（{_ir[0]}）")
            return "；".join(_parts)
        collapse = [f for f in flags if f.endswith("_all_same")]
        structural = [f for f in flags if f.endswith("_all_same_structural")]

        if "expand_imbalanced_benign" in flags:
            return ("阴阳展开单边：另一边输出足够多，"
                    "可能是这一圈问题性质决定（非失败）")
        if has("expand_imbalanced"):
            return ("阴阳展开批次不均：某一边几乎没产出候选"
                    "（单边输出也少，疑似 LLM 偷懒）")
        if has("too_many_amp_candidates") and collapse:
            return "对偶判断塌缩（机械全反）：& 候选比例是假象，不是真实错位"
        if has("too_many_amp_candidates"):
            return ("& 候选占比偏高（0/1 层锚点收敛时为正常现象；"
                    "both/all 层超过 0.5 需留意）")
        if collapse:
            dims = "、".join(f.split("_")[0] for f in collapse)
            return f"对偶判断塌缩（机械全同）：{dims} 维度全同，判断没起作用"
        if structural:
            dims = "、".join(f.replace("_all_same_structural", "")
                            for f in structural)
            return (f"{dims} 全同但 why_position 多样——"
                    f"结构性一致，非判断塌缩")
        if has("no_amp_candidates"):
            return "对偶判断塌缩（机械全同）：属性与位置全同，& 未出生"
        if has("no_amp_at_all"):
            return "候选层与 ing 都没有沉淀出 &，本次确实没有不可通约处"
        if has("ing_empty_with_candidates"):
            return "有候选但 ing 未产出，是失败不是未生"
        if has("ing_has_boilerplate"):
            return "ing 出现套话，质量存疑"
        if has("candidates_overlap_pool"):
            return "候选与池高度重合，可能没长出新的"
        if has("probe_failed"):
            return "探针回归这一步调用失败，本次没有完成回归"
        if has("probe_return_empty"):
            return "有 & / 线头带不走，但探针回归没生发出能指回问题的自问"
        pol_struct = [f for f in flags
                      if f.startswith("polarity_all_same_structural(")]
        pol_collapse = [f for f in flags
                        if f.startswith("polarity_all_same(")]
        if pol_struct:
            return (f"池极性全同（{pol_struct[0]}）但 why 多样——"
                    f"结构性一致，非坍缩")
        if pol_collapse:
            return (f"池极性全同（{pol_collapse[0]}）且 why 重复——"
                    f"可能真坍缩")
        return "、".join(flags)

    # ---------- [P1-4] 极性 both 配额 ----------
    def _ask_missing_polarity(self, boths: List[dict]) -> Dict[str, str]:
        """对每条 both 追问「要裁成 0 或 1，还缺什么」。

        不要求它改裁决 —— 那会破坏「未对齐合法」「悬置不打分」的宪法级约束。
        只要求它说出缺席的那个东西：一个具体对象、一条未写出的判据、
        一个还不存在的操作。这个东西能进 seeds，成为下一圈真正的入口。
        """
        lines = "\n".join(
            f"{i+1}. {str(a.get('tension', ''))[:120]}"
            for i, a in enumerate(boths[:8]))
        system = (
            "你是【裁决补完者】。\n"
            "下面每条张力都被判为极性 both（两边都保留、不合并）。\n"
            "both 本身合法，但一张全是 both 的单子等于什么都没裁。\n"
            "对每条回答：**要把它裁成 0 或 1，还缺什么**。\n"
            "★ 只写缺的那个东西：一个缺席的对象、一条未写出的判据、"
            "一个还不存在的操作。\n"
            "★ 不要改裁决，不要给结论，不要写「需要进一步研究」这类套话。\n"
            "★ 如果确实裁不动，就写明缺的那个不可能出现的东西是什么。\n"
            "严格 JSON：\n"
            '{"items":[{"idx":1,"missing":"≤30字"}]}'
        )
        try:
            raw = self.llm.call(system, f"【both 张力】\n{lines}",
                                0.3, 1200, json_mode=True, stage=_thinking_stage(self.config, 'ask_missing_polarity'))
            data = self.llm.parse_json(raw) or {}
        except Exception as e:
            logger.warning("both 补裁调用失败: %s", e)
            return {}
        out: Dict[str, str] = {}
        for it in (data.get("items") or []):
            if not isinstance(it, dict):
                continue
            try:
                i = int(it.get("idx", 0)) - 1
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(boths):
                out[str(boths[i].get("tension", ""))[:120]] = \
                    str(it.get("missing", "")).strip()[:120]
        return out

    def _enforce_both_quota(self, view: "View") -> None:
        """both 占比超阈值时强制补裁并挂 advice 到 view。

        实测三份产物：极性 1 出现 0/0/1 次，both 占绝对多数。
        both 合法，但 both 占 100% 就是没裁 —— 自省自己写过
        「每条 both 只拒绝合并，不判定了什么」。
        """
        cfg = ((self.config.get("spiral") or {}).get("both_quota") or {})
        if cfg.get("enabled") is False:
            return
        max_ratio = float(cfg.get("max_ratio", 0.7))
        min_n = int(cfg.get("min_items", 2))
        adj = view.adjudications or []
        if len(adj) < min_n:
            return
        boths = [a for a in adj
                 if str(a.get("polarity", "")).strip() == "both"]
        if not boths:
            return
        ratio = len(boths) / len(adj)
        if ratio <= max_ratio:
            return

        self.vp(f"   ⚖️ [both 配额] {len(boths)}/{len(adj)}"
                f"（{ratio:.0%}）> {max_ratio:.0%}，要求补裁")
        missing_map = self._ask_missing_polarity(boths)
        for a in view.adjudications:
            if str(a.get("polarity", "")).strip() != "both":
                continue
            m = missing_map.get(str(a.get("tension", ""))[:120], "")
            if m:
                a["missing"] = m
                self.vp(f"      ↳ 缺：{m}")
        view.both_quota = {
            "ratio": round(ratio, 3),
            "n_both": len(boths),
            "n_total": len(adj),
            "max_ratio": max_ratio,
            "items": [{"tension": str(a.get("tension", "")),
                       "missing": a.get("missing", "")} for a in boths],
        }

    def _unsaid_escape_limit(self) -> int:
        """[P2-4] 一圈里「此处未生」超过多少处就算逃避。

        走 spiral.unsaid_escape_limit（支持 per_entry 按层覆盖）。
        0 表示不设限——「此处未生」永远只当诚实姿态，不做判据。
        """
        try:
            n = int(self.sp.get("unsaid_escape_limit", UNSAID_ESCAPE_LIMIT))
        except (TypeError, ValueError):
            n = UNSAID_ESCAPE_LIMIT
        return max(0, n)

    # ---------- self-check ----------
    def _self_check(self, view: View) -> dict:
        if not view.candidates and not view.amps:
            return {"notes": "本次内容为空白，无需回看"}

        _cands = view.candidates
        cand_lines = "\n".join(
            f"{i+1}. [{c.get('attribute','0')}×{c.get('position','0')}] "
            f"{c.get('desc','')}"
            for i, c in enumerate(_cands))
        amp_lines = "\n".join(
            f"{i+1}. [{a.get('type','?')}] {a.get('desc','')}"
            for i, a in enumerate(view.amps))

        system = (
            "你是【自我回看者】。\n"
            "回看这次运行，如实回答：\n"
            "1. 有没有哪条候选，是后面补的，不是从展开里长出来的？\n"
            "2. 有没有哪条 &，是为了凑数？\n"
            "3. ing 输出里，是否有**超过一半**的句子与**上游 view** 的"
            "manifest/collision 逐字或近义重复？\n"
            "   - 逐字重复：完全相同的句子；\n"
            "   - 近义重复：换了个说法但说的是同一件事。\n"
            "   - 若超过一半 → ing_rephrased=true；\n"
            "   - 若不到一半 → false。\n"
            "   ★ 不要因为'有几句原话'就填 true；要看**比例**。\n"
            "   ★ 本层候选不是上游：ing 本来就是吃候选的，\n"
            "     ing 提到候选不算复述——只有复述**上游 view 的话**才算。\n"
            "4. 如果撞不出新东西，我有没有诚实说'未生'？\n"
            "5. 这次 DGTF 整体流程走得好不好？\n"
            f"6. 本层 view 的标准是：{self.phase.view_focus}\n"
            "7. 本圈有几处说了「此处未生」？自己数一遍，填进 unsaid_count。\n"
            "   ★ 「此处未生」是允许的诚实姿态，但如果一处圈里出现超过 3 处，\n"
            "     说明这一圈的探针没有真的往里推——它成了收尾的套路。\n"
            "     这种情况下 unsaid_is_escape 填 true，\n"
            "     并说明是哪一步该推没推。\n"
            "严格 JSON：\n"
            '{"suspicious_candidates":[1,2],'
            '"suspicious_amps":[1],'
            '"ing_rephrased":false,'
            '"honest_about_empty":true,'
            '"unsaid_count":0,'
            '"unsaid_is_escape":false,'
            '"unsaid_where":"≤60字（超过 3 处时填：哪一步该推没推）",'
            '"flow_verdict":"≤60字",'
            '"view_verdict":"≤60字",'
            '"amp_ratio_verdict":"≤40字",'
            '"notes":"≤80字"}'
            + self._self_block()
        )
        user = (
            f"【锚点】\n{view.anchor}\n\n"
            f"【候选】\n{cand_lines}\n\n"
            f"【& 印记】\n{amp_lines}\n\n"
            f"【ing 输出】\n{view.collision[:1500]}\n\n"
            f"【view】\n{view.manifest or '（未生）'}\n\n"
            f"【代码已发现的质量线索】\n"
            f"{', '.join(view.quality_flags) or '（无）'}\n"
        )
        if any("too_many_amp_candidates" in f for f in view.quality_flags):
            user += (
                "\n\n【★ 深究请求】本轮 amp 候选占比偏高。请专门判断：\n"
                "  这是结构性一致（& 候选从不同角度指向同一结构），\n"
                "  还是判断塌缩（属性与位置机械全反）？\n"
                "  把结论写进 amp_ratio_verdict（≤40字）。\n"
            )
        # [P2-4] 「此处未生」的硬计数：模型自报的 unsaid_count 会和实际
        # 对不上（它数的是它记得的，不是它写下的）。代码按产物数一遍，
        # 取两者的较大值作为判据，避免模型靠少报把逃避藏起来。
        # 阈值走 spiral.unsaid_escape_limit（可按层 per_entry 覆盖）。
        _lim = self._unsaid_escape_limit()
        counted, where = _count_unsaid(view)
        if counted:
            user += (f"\n\n【★ 代码统计】本圈产物里出现「{_UNSAID_MARK}」"
                     f"{counted} 处，分布在：{where or '（未定位）'}。\n"
                     f"  你自己数的 unsaid_count 应与此接近；差太多请说明。\n")
            if _lim > 0:
                user += (f"  超过 {_lim} 处 → 这一圈的探针没真的往里推，"
                         f"unsaid_is_escape 填 true。\n")
        try:
            raw = self.llm.call(system, user, 0.3, 1500, json_mode=True, stage=_thinking_stage(self.config, 'self_check'))
        except Exception as e:
            logger.warning("self-check 失败: %s", e)
            return {"unsaid_count": counted, "unsaid_where": where}

        data = self.llm.parse_json(raw) or {}
        try:
            reported = int(data.get("unsaid_count", 0) or 0)
        except (TypeError, ValueError):
            reported = 0
        unsaid_n = max(counted, reported)
        unsaid_escape = bool(data.get("unsaid_is_escape", False))
        # [P2-8] _lim <= 0 = 不设限：阈值 0 不是「一处都不许有」，
        # 而是关掉这条判据（否则 0 反而成了最严的设置，和配置注释相反）。
        if _lim > 0 and unsaid_n > _lim:
            unsaid_escape = True
        if _lim > 0 and unsaid_n > _lim and not any(
                "unsaid_overused" in f for f in view.quality_flags):
            view.quality_flags.append(f"unsaid_overused({unsaid_n})")
            view.quality_verdict = self._quality_verdict(view.quality_flags)
            self.vp(f"   ⚑ [self-check 联动] 本圈「{_UNSAID_MARK}」"
                    f"{unsaid_n} 处 > {_lim}，"
                    f"这一圈的探针没真的往里推")
        return {
            "suspicious_candidates": [
                int(x) for x in data.get("suspicious_candidates", [])
                if isinstance(x, (int, float, str)) and str(x).isdigit()
            ],
            "suspicious_amps": [
                int(x) for x in data.get("suspicious_amps", [])
                if isinstance(x, (int, float, str)) and str(x).isdigit()
            ],
            "ing_rephrased": bool(data.get("ing_rephrased", False)),
            "honest_about_empty": bool(data.get("honest_about_empty", True)),
            "unsaid_count": unsaid_n,
            "unsaid_is_escape": unsaid_escape,
            "unsaid_where": str(data.get("unsaid_where", ""))[:200] or where,
            "flow_verdict": str(data.get("flow_verdict", ""))[:200],
            "view_verdict": str(data.get("view_verdict", ""))[:200],
            "amp_ratio_verdict": str(data.get("amp_ratio_verdict", ""))[:200],
            "notes": str(data.get("notes", ""))[:200],
        }

    # ---------- view 生成 ----------
    def _manifest(self, view: View, inp: Input) -> str:
        if not (view.candidates or view.collision or view.amps):
            return "（此处未生）"

        parts = []
        if view.collision:
            parts.append("【这一层走过的路】\n" + view.collision[:2500])
        if view.candidates:
            parts.append("【候选】\n" + "\n".join(
                f"  - {c['desc']}" for c in view.candidates))
        if view.amps:
            parts.append("【& 印记】\n" + "\n".join(
                f"  - [{AMP_TYPES.get(a['type'], '?')}] {a['desc']}"
                for a in view.amps))
        if view.threads:
            parts.append("【还悬着的】\n" + "\n".join(
                f"  - {t['desc']}" for t in view.threads))
        if view.engagements:
            parts.append("【这一层碰了】\n" + "\n".join(
                f"  - {e.get('target','')}（{e.get('how','')}）"
                for e in view.engagements))
        if view.suspensions:
            head = ("【这一层决定不消解（元决策 · 承认这类张力是结构性的）】"
                    if self.entry == "all"
                    else "【这一层决定不碰（主动悬置）】")
            parts.append(head + "\n" + "\n".join(
                f"  - {s.get('target','')}（{s.get('reason') or '直觉，无理由'}"
                f"｜{s.get('reason_type','')}）"
                for s in view.suspensions))
        if view.revocations:
            parts.append("【这一层撤回的悬置】\n" + "\n".join(
                f"  - {r.get('suspension_id','') or r.get('target','')}"
                f"（{r.get('reason','')}）" for r in view.revocations))
        if view.probes:
            parts.append("【还没带走的自问】\n" + "\n".join(
                f"  - {p['question']}（回来：{p['link']}"
                f"｜增益{p['expected_gain']}）"
                for p in view.probes))
        if view.meta:
            parts.append("【元反思】\n" + "\n".join(
                f"  - {m}" for m in view.meta))
        if view.deferrals:
            parts.append("【这一层新提的延迟】\n" + "\n".join(
                f"  - 子问题{d.get('sub_id')}：{d.get('reason','')}"
                f"（回访条件：{d.get('revisit_condition','')}）"
                for d in view.deferrals))
        if view.resolutions:
            parts.append("【这一层清偿的债务】\n" + "\n".join(
                f"  - {r.get('deferral_id','')}：{r.get('how','')}"
                for r in view.resolutions))
        if view.escalations:
            parts.append("【这一层升级为不可判定】\n" + "\n".join(
                f"  - 子问题{e.get('sub_id')}：{e.get('reason','')}"
                for e in view.escalations))
        if getattr(view, "reclassifications", None):
            parts.append("【这一层提出的可判定性转移】\n" + "\n".join(
                f"  - 子问题{e.get('sub_id')}→"
                f"{_DEC_STATE_CN.get(e.get('to'), e.get('to'))}："
                f"{e.get('reason','')}"
                f"（证据：{'、'.join(e.get('evidence') or []) or '无'}）"
                for e in view.reclassifications))
        if view.settlement:
            parts.append("【终局清算】\n"
                         f"  clean={view.settlement.get('clean')}，"
                         f"遗留 {view.settlement.get('leftover', 0)} 项")
        if view.adjudications:
            parts.append("【这一层裁决的张力】\n" + "\n".join(
                f"  - {a.get('tension','')} → 极性 {a.get('polarity','?')}"
                f"（{a.get('how','')}）"
                for a in view.adjudications))
        if view.duel_suspensions:
            parts.append("【这一层悬置的张力】\n" + "\n".join(
                f"  - {s.get('tension','')}（{s.get('quadrant','?')}）"
                f"：{s.get('reason') or '直觉，无理由'}"
                for s in view.duel_suspensions))
        if view.meta_closure:
            parts.append("【闭环清算】\n"
                         f"  clean={view.meta_closure.get('clean')}，"
                         f"未交代 {view.meta_closure.get('unsettled', 0)} 类张力")
        if view.decidable_product and view.decidable_product.get("answer"):
            parts.append("【📗 可判定通道产物】\n"
                         f"  - answer：{view.decidable_product.get('answer','')[:400]}\n"
                         f"  - answered_sub_ids：{view.decidable_product.get('answered_sub_ids')}\n"
                         f"  - distance：{view.decidable_product.get('distance')}")
        if view.undecidable_product and view.undecidable_product.get("structural_amps"):
            parts.append("【📘 不可判定通道产物】\n"
                         f"  - why_undecidable：{view.undecidable_product.get('why_undecidable','')[:200]}\n"
                         f"  - clarity：{view.undecidable_product.get('clarity')}\n"
                         "  - structural_amps：\n"
                         + "\n".join(f"    - {s}"
                                     for s in view.undecidable_product.get("structural_amps", [])[:5]))
        # ★ [LDG 修真] 只有**真拿到**读数才印（缺省 None = 模型没报，
        #   不许印 1.00 冒充「离得最远」）。
        if view.distance_to_question is not None:
            parts.append(
                f"【综合距离】distance_to_question="
                f"{float(view.distance_to_question):.2f}")

        if self.entry == "0":
            style = (
                "严格按四段写，每段用 `## 一、…` 这样的标题：\n"
                "一、这一路看到了什么\n"
                "二、哪些还没看清（只写线头与 &，不写「决定不碰」）\n"
                "三、我决定不碰什么，为什么（只写主动悬置；这是决定，不是遗憾）\n"
                "四、与问题相处的姿态\n"
                "不要重述上面已有的原话，不要总结套话。\n"
            )
        elif self.entry == "1":
            style = (
                "严格按五段写，每段用 `## 一、…` 这样的标题：\n"
                "一、可判定部分 · 直接回答\n"
                "   从【📗 可判定通道产物】的 answer 出发，\n"
                "   逐条回应对应子问题。\n"
                "二、不可判定部分 · 结构揭示\n"
                "   从【📘 不可判定通道产物】出发，\n"
                "   逐条揭示不可判定的结构。\n"
                "三、★ 暂缓处理的部分（延迟债务）——每条写：子问题是什么 / \n"
                "   为什么延迟 / 原本的回访条件 / 最终状态。\n"
                "   ★ 语气：这是一笔账，不是一句遗憾。\n"
                "四、螺旋轨迹\n"
                "五、& 张力与悬空线头\n"
                "不要重述上面已有的原话，不要总结套话。\n"
            )
        elif self.entry == "both":
            style = (
                "严格按五段写，每段用 `## 一、…` 这样的标题：\n"
                "一、两个 view 撞出了什么（第三者）\n"
                "二、哪些分歧已经被裁决（写极性 0/1/both 及其理由）\n"
                "三、★ 我悬置了哪些张力，为什么\n"
                "四、螺旋轨迹\n"
                "五、& 张力与悬空线头\n"
                "不要重述上面已有的原话，不要总结套话。\n"
            )
        elif self.entry == "all":
            style = (
                "严格按六段写，每段用 `## 一、…` 这样的标题：\n"
                "一、all 作为整体的形态——以及它与局部不可通约处。\n"
                "二、整体与局部对撞里长出的新东西。\n"
                "三、★ 我决定不消解哪类张力，为什么。\n"
                "四、螺旋轨迹\n"
                "五、& 张力与悬空线头\n"
                "六、一个新的姿态（与「完整」相处的方式）\n"
                "不要重述上面已有的原话，不要总结套话。\n"
            )
        else:
            style = (
                "写 150-500 字的一段。\n"
                "不要罗列条目，不要重述上面已有的话，不要小标题。\n"
            )
        system = (
            "你处于【view · 显形】。\n"
            "这一步不是把上面的产物再总结一遍——总结是被禁止的。\n"
            "是让这一整批产物，作为一次运行的整体，显形为它自己。\n"
            f"{self.phase.view_focus}\n"
            + style
            + ANTI_PRETTY
            + self._self_block()
        )
        user = "\n\n".join(parts)
        try:
            out, trunc = self._call_long(
                system, user, 0.7, 2500, model=self.llm.reasoner_model,
                thinking=self.llm.thinking_reasoner)
            if trunc:
                view.add_error(
                    "view", RuntimeError(
                        "view 生成被长度掐断，这段可能不完整"))
            return (out or "").strip()
        except Exception as e:
            logger.warning("view 生成失败: %s", e)
            view.add_error("view", e)
            return ""

    # ---------- 渲染 ----------
    def _render(self, view: View, inp: Input) -> str:
        cand_lines = []
        for c in view.candidates:
            tag = f"[{c['attribute']}×{c['position']}]"
            marks = []
            if c.get("is_amp_candidate"):
                marks.append("⚡&")
            if c.get("attribute_anchored"):
                marks.append(f"属性◈{c.get('source') or '?'}展开")
            elif c.get("yin") != c.get("yang"):
                marks.append("⟂阴阳")
            mark = ("  " + " ".join(marks)) if marks else ""
            cand_lines.append(f"  {tag} {c['desc']}{mark}")

        amp_lines = [f"  - [{AMP_TYPES.get(a['type'],'?')}] {a['desc']}"
                     for a in view.amps]
        thread_lines = [f"  💭 {t['desc']}" for t in view.threads]
        probe_lines = [
            f"  ? {p['question']}（回来：{p['link']}"
            f"｜增益{p['expected_gain']}）"
            for p in view.probes]

        section_label = {
            "0": "修行", "1": "研究",
            "both": "对撞", "all": "元",
        }[view.entry]

        meta_lines = [f"  ∘ {m}" for m in view.meta]
        err_lines = [f"  ✗ {e}" for e in view.errors]

        lines = [
            f"━━━ {section_label} · entry={view.entry} ━━━",
            "",
            f"【锚点】{view.anchor}",
            "",
            "【候选】",
            *(cand_lines or ["  （无）"]),
            "",
            "【ing 对撞】",
            view.collision or "（未生）",
            "",
            "【& 印记】",
            *(amp_lines or ["  （无）"]),
            "",
            "【悬空线头】",
            *(thread_lines or ["  （无）"]),
            "",
            "【探针回归】",
            *(probe_lines or ["  （此处无自问可回归）"]),
        ]
        if view.untouched:
            lines += ["", "【尚未触及的方面】",
                      *[f"  💭 {u.get('desc','')}（{u.get('source','')}）"
                        for u in view.untouched]]
        if view.engagements:
            lines += ["", "【本层碰了】",
                      *[f"  - {e.get('target','')}：{e.get('how','')}"
                        for e in view.engagements]]
        if view.suspensions:
            head = ("【决定不消解（元决策 · 这类张力是结构性的）】"
                    if view.entry == "all"
                    else "【主动悬置（决定不碰）】")
            lines += ["", head,
                      *[f"  - {s.get('target','')}："
                        f"{s.get('reason') or '直觉，无理由'}"
                        f"[{s.get('reason_type','')}]"
                        for s in view.suspensions]]
        if view.revocations:
            lines += ["", "【撤回的悬置】",
                      *[f"  - {r.get('suspension_id','') or r.get('target','')}："
                        f"{r.get('reason','')}" for r in view.revocations]]
        if view.deferrals:
            lines += ["", "【延迟债务（暂缓，非悬置）】",
                      *[f"  - 子问题{d.get('sub_id')}：{d.get('reason','')}"
                        f"（回访条件：{d.get('revisit_condition','')}）"
                        for d in view.deferrals]]
        if view.resolutions:
            lines += ["", "【本层清偿的债务】",
                      *[f"  - {r.get('deferral_id','')}：{r.get('how','')}"
                        for r in view.resolutions]]
        if view.escalations:
            lines += ["", "【本层迁向不可判定】",
                      *[f"  - 子问题{e.get('sub_id')}：{e.get('reason','')}"
                        for e in view.escalations]]
        if getattr(view, "reclassifications", None):
            lines += ["", "【本层提出的可判定性转移（三态可转·须证据）】",
                      *[f"  - 子问题{e.get('sub_id')}→"
                        f"{_DEC_STATE_CN.get(e.get('to'), e.get('to'))}："
                        f"{e.get('reason','')}"
                        f"（证据：{'、'.join(e.get('evidence') or []) or '无'}）"
                        for e in view.reclassifications]]
        if view.adjudications:
            lines += ["", "【本层裁决的张力（极性）】",
                      *[f"  - {a.get('tension','')} → 极性 {a.get('polarity','?')}"
                        f"（{a.get('how','')}）"
                        for a in view.adjudications]]
        if view.duel_suspensions:
            lines += ["", "【本层悬置的张力（不解决什么分歧）】",
                      *[f"  - {s.get('tension','')}（{s.get('quadrant','?')}）"
                        f"：{s.get('reason') or '直觉，无理由'}"
                        for s in view.duel_suspensions]]
        if view.decidable_product and view.decidable_product.get("answer"):
            dp = view.decidable_product
            lines += ["", "【📗 可判定通道】",
                      f"  answer：{dp.get('answer','')}",
                      f"  answered_sub_ids：{dp.get('answered_sub_ids')}",
                      f"  distance：{dp.get('distance')}"]
            for ev in (dp.get("evidence") or []):
                lines.append(f"  evidence：{ev}")
        if view.undecidable_product and view.undecidable_product.get("structural_amps"):
            up = view.undecidable_product
            lines += ["", "【📘 不可判定通道】",
                      f"  why_undecidable：{up.get('why_undecidable','')}",
                      f"  clarity：{up.get('clarity')}",
                      "  独立结构（独立度分母）："]
            for sa in up.get("structural_amps", []):
                lines.append(f"    structural_amp：{sa}")
            if up.get("aligned_amps"):
                lines.append("  对齐 und_aspects（另计，不参与独立度）：")
                for aa in up["aligned_amps"]:
                    lines.append(f"    aligned_amp：{aa}")
        # ★ [LDG 修真] 同上：缺省不印。
        if view.distance_to_question is not None:
            lines += ["", f"【综合距离】"
                          f"{float(view.distance_to_question):.2f}"]
            if view.covered_aspects:
                lines.append("  covered_aspects："
                             + "、".join(view.covered_aspects))
            if view.uncovered_aspects:
                lines.append("  uncovered_aspects："
                             + "、".join(view.uncovered_aspects))
        if view.meta_closure:
            clo = view.meta_closure
            lines += ["", "【闭环清算】",
                      f"  clean={clo.get('clean')}，"
                      f"对撞张力 {clo.get('total', 0)} 类，"
                      f"未交代 {clo.get('unsettled', 0)} 类"]
            for u in (clo.get("uncovered") or []):
                lines.append(f"  - 未交代：{u}")
        if view.stop_reason:
            lines += ["", f"【螺旋停止】{view.stop_reason}"]
            # ★ [LDG] 职责判定**紧接着**停止理由渲染：读者不可能只看到
            #   「自然安住」而看不到「职责未尽」（诚实性由同屏保证）。
            if view.duty_verdict:
                lines += [f"【职责判定】{view.duty_verdict}"]
            if getattr(view, "goal_verdict", ""):
                lines += [f"【目标判定】{view.goal_verdict}"]
            # ★ [停因级联] 主因单列 —— 与「全部触发」并列，读者一眼看到
            #   「真正停下来的是哪一个」，不必自己从 " + " 串里猜。
            if view.stop_primary:
                lines += [f"【主因（最高优先级）】{view.stop_primary}"]
            # ★ [CSD 早期预警] 读数（不是判定）：口径写在文案里，防被读成预测。
            try:
                _cd = (view.csd or {}).get("new_amps")
                if _cd:
                    lines += [f"【早期预警】{csd_line(_cd)}"]
            except Exception:
                pass
            # ★ [发散三态 + 回滚指针]（LoopGain）：三态 + 历史最佳圈的**指针**。
            try:
                _dv = view.divergence or {}
                if _dv:
                    _bp = ("第 %s 圈" % view.best_round
                           if view.best_round else "—")
                    lines += [f"【发散三态】{_dv.get('state')}"
                              f"（前半方差 {_dv.get('var_first')} → "
                              f"后半 {_dv.get('var_last')}，AC1 {_dv.get('ac1')}）"
                              f"｜历史最佳圈（回滚指针）：{_bp}"
                              f"　★ 只给指针，被回滚的圈不删"]
            except Exception:
                pass
            # ★ [anytime-valid] 均值下界（随时看随时停仍然有效）。
            try:
                _at = view.anytime or {}
                if _at.get("lower") is not None:
                    lines += [f"【anytime 下界】「仍在长」下界 "
                              f"{float(_at['lower']):.3f}"
                              f"（n={_at.get('n')}，δ={_at.get('delta')}）"
                              f"　★ 下界 < 0.5 才够说「不再长」"]
            except Exception:
                pass
        if view.closure_reason:
            lines += ["", f"【清算交代】{view.closure_reason}"]
        lines += ["", "【view】", view.manifest or "  （未生）"]
        if meta_lines:
            lines += ["", "【元反思】", *meta_lines]
        if err_lines:
            lines += ["", "【失败记录】", *err_lines]
        if view.quality_flags:
            lines += ["", f"【质量线索】{', '.join(view.quality_flags)}"]
        if view.quality_verdict:
            lines += ["", f"【质量评价】{view.quality_verdict}"]
        if view.self_check and view.self_check.get("notes"):
            lines += ["", f"【自省】{view.self_check['notes']}"]
        _sc = view.self_check or {}
        _un = int(_sc.get("unsaid_count", 0) or 0)
        if _un:
            _esc = "　⚠ 判为逃避：探针没有真的往里推" \
                if _sc.get("unsaid_is_escape") else "　（诚实姿态，未越界）"
            lines += ["", f"【「{_UNSAID_MARK}」计数】本圈 {_un} 处"
                          f"（阈值 {UNSAID_ESCAPE_LIMIT}）{_esc}"]
            if _sc.get("unsaid_where"):
                lines += [f"  分布：{_sc['unsaid_where']}"]
        if view.carry_check:
            lines += ["", f"【自省回流核对】{view.carry_check.get('notes', '')}"]

        return "\n".join(lines)


class MetaDGTF:
    def __init__(self, config: dict):
        self.config = config
        self.llm = LLM(config)
        self.pools: Dict[str, Pool] = {
            "0": Pool(), "1": Pool(), "both": Pool(), "all": Pool(),
        }
        # [D2 可配] `belief.revoke_sources` 落到每个池上（默认 = 模块常量）。
        #   ★ 配置只在 DEFAULT_CONFIG 里加键而不读 = 换个地方埋同一个坑
        #     （本版修的正是这类）。这里显式下发。
        try:
            _rs = int((config.get("belief") or {}).get(
                "revoke_sources", _BELIEF_REVOKE_SOURCES))
        except (TypeError, ValueError):
            _rs = _BELIEF_REVOKE_SOURCES
        for _p in self.pools.values():
            _p.revoke_sources = _rs
        # [D3 可配] `belief.sem_entropy_thr` 落到每个池上（默认 = 模块常量）。
        #   ★ 与 revoke_sources 同因：配置键不读 = 埋坑。这里显式下发。
        try:
            _se = float((config.get("belief") or {}).get(
                "sem_entropy_thr", _SEM_CLUSTER_THR))
        except (TypeError, ValueError):
            _se = _SEM_CLUSTER_THR
        for _p in self.pools.values():
            _p.sem_entropy_thr = _se
        # [D2 可配] 语义归并开关/阈值同样显式下发（默认关 / 0.85）。
        try:
            _mg = bool((config.get("belief") or {}).get(
                "merge_semantic", False))
        except (TypeError, ValueError):
            _mg = False
        try:
            _ms = float((config.get("belief") or {}).get(
                "merge_sim", _BELIEF_MERGE_SIM))
        except (TypeError, ValueError):
            _ms = _BELIEF_MERGE_SIM
        for _p in self.pools.values():
            _p.merge_semantic = _mg
            _p.merge_sim = _ms
        # [LDG 可配] 层职责守卫的阈值（默认 = 引擎常量 ⇒ 出厂零行为差）。
        try:
            _du = dict(config.get("duty") or {})
        except Exception:
            _du = {}
        try:
            self._duty_floor = float(_du.get("floor", _DUTY_FLOOR))
        except (TypeError, ValueError):
            self._duty_floor = float(_DUTY_FLOOR)
        try:
            self._duty_tau = float(_du.get("tau", _DUTY_TAU))
        except (TypeError, ValueError):
            self._duty_tau = float(_DUTY_TAU)
        try:
            self._duty_patience = int(_du.get("patience", _DUTY_PATIENCE))
        except (TypeError, ValueError):
            self._duty_patience = int(_DUTY_PATIENCE)
        self._duty_carry: List[str] = []
        # [预算 bandit 可配] 默认关 ⇒ 出厂零行为差（探索会故意选较差档，
        #   因此必须显式打开，且每次探索选择都在产物留痕）。
        try:
            _bd = dict((config.get("auto") or {}).get("bandit") or {})
        except Exception:
            _bd = {}
        self._bandit_cfg = _bd
        self._bandit_enabled = bool(_bd.get("enabled", False))
        self._bandit = None
        self._bandit_pick = None
        if self._bandit_enabled:
            try:
                self._bandit = _load_bandit(_bd)
            except Exception:
                self._bandit = None
        # [anytime-valid 可配] δ（0 = 关；>0 才启用该停止判据）。
        try:
            self._anytime_delta = float(
                (config.get("stop") or {}).get("anytime_alpha", 0.0) or 0.0)
        except (TypeError, ValueError):
            self._anytime_delta = 0.0
        # [EML 可配] 经验记忆回路（默认 shadow ⇒ 出厂零行为差）。
        try:
            _pl = dict(config.get("playbook") or {})
        except Exception:
            _pl = {}
        self._eml_cfg = _pl
        self._eml_mode = str(_pl.get("mode", _EML_MODE_DEFAULT))
        self._eml_used: List[dict] = []
        self._eml_applied: List[dict] = []
        self.verbose = config["output"].get("verbose", True)
        self.self_text: List[str] = []
        self._mcfg = config.setdefault("memory", {})
        m = self._mcfg.setdefault("channels", list(CHANNELS))
        self.channels = tuple(MemoryChannel.check(c) for c in m)
        self.decidability_result: Dict[str, Any] = {}
        self._input_sanity: Dict[str, Any] = {}  # [P1-6]
        self._ext_assess_cache: Dict[str, dict] = {}
        # [动态提前停] 总调用预算。0 = 不设限（沿用各层的停止判据）。
        # 由自动规划 `auto_plan()` 给出，或配置 `max_calls` 指定。
        # ★ 用尽时必须**留痕**：静默少跑几圈，产物看着像自然停止，
        #   读的人无从分辨——这就是"错了却看不出来"。
        self._call_budget = int(self.config.get("max_calls", 0) or 0)
        self._budget_stop_note = ""
        self.dec_tracker: Optional[ChannelTracker] = None
        self.und_tracker: Optional[ChannelTracker] = None
        self._rephrased_streak = 0
        self._uncovered_streak = 0
        self._tri_agree: int = 0
        self._tri_total: int = 0
        self._anchors: List[dict] = []
        self._anchor_err: str = ""
        self._anchor_source: Dict[str, str] = {}
        self._anchor_answers_warning: str = ""
        self._anchor_answers_filtered: str = ""
        self._anchor_tier_warning: str = ""
        self._anchor_report: Optional[dict] = None
        self._anchor_calls: int = 0
        self._question: str = ""
        self._key_terms: List[str] = []
        self._results: Dict[str, View] = {}
        self._prev_results: Dict[str, View] = {}
        self._rounds: Dict[str, int] = {}
        self._keep: Dict[str, str] = {}
        self._upstream_provider = None
        self._self_text_by_entry: Dict[str, List[str]] = {
            e: [] for e in _ENTRIES}
        # [fix-100] 池 / self_text 的写入锁。串行模式下等于无开销，
        # 并行模式 A/B 下保证 merge / 生命周期更新 / 汇总不会互相踩。
        self._pool_lock = threading.RLock()
        self._parallel_mode: str = "serial"
        self._b_state: Dict[str, dict] = {}
        self._parallel_label: str = "B"
        self._warmup_done: int = 0
        self._c_released: Dict[str, Any] = {}

    def vp(self, *args):
        if self.verbose:
            print(*args)

    def _append_self_text(self, entry: str, view: "View") -> None:
        with self._pool_lock:
            self._self_text_by_entry[entry] = MemoryChannel.accumulate_self(
                self._self_text_by_entry.get(entry) or [],
                entry, view, self._mcfg)

    def _self_snapshot_for(self, entry: str) -> str:
        '''给某一层构造 self_memory：读此刻所有层已累积的 self_text。

        串行模式下按 _ENTRIES 顺序拼接 == 原来的按时间累积顺序，行为不变。
        '''
        with self._pool_lock:
            blocks: List[str] = []
            for e in _ENTRIES:
                blocks.extend(self._self_text_by_entry.get(e) or [])
            return MemoryChannel.self_text_of(blocks)

    def _merge_self_text(self) -> None:
        """所有层跑完后调用：把分层的 self_text 合并回 self.self_text。

        [P0-1] 原来是全局 blocks[-keep:]。并行模式下跑得最久的层
        （all，带 all_extra_rounds）最后完成，会把前面几层的自我记忆
        全部挤出 —— 实测 B 模式两份产物的 self 段 4 条全是「元层」，
        回来通道的 self 只剩一个声部，下一圈展开随之同质化。

        改成按层轮转：每层各保留最近 per_entry 条，再按 (圈序, 层序)
        交错合并，保证四层都有代表。
        """
        with self._pool_lock:
            per_entry = max(1, int(
                self._mcfg.get("self_layers_per_entry", 2)))
            per = {e: list(self._self_text_by_entry.get(e) or [])[-per_entry:]
                   for e in _ENTRIES}
            blocks: List[str] = []
            for i in range(max((len(v) for v in per.values()), default=0)):
                for e in _ENTRIES:
                    if i < len(per[e]):
                        blocks.append(per[e][i])
            cap = int(self._mcfg.get("self_layers", 4)) * per_entry
            if cap > 0 and len(blocks) > cap:
                blocks = blocks[-cap:]
            self.self_text = blocks

    # ---------- [P2-9] 跑圈的公共决策点（两条跑圈通道共用） ----------
    @staticmethod
    def _natural_role(round_index: int) -> str:
        """没有任何干预时，第 round_index 圈（0-based）的默认角色。

        [P2-9] 这条排班原来被抄写在两处（_run_layer 里 0-based、
        _run_one_round_B 里 1-based），改动时很容易只改一处。
        next_role 的反馈环 bug 就是这么来的：排班公式被 carry 的
        返回值绕过去了。现在两条通道都来问这一个函数。
        """
        if round_index <= 0:
            return "摊开"
        if round_index == 2:
            return "收束"
        return "深入"

    @classmethod
    def _role_for_round(cls, round_index: int, override: str = "") -> str:
        """本圈实际用的角色：默认排班 + 上一圈 carry 可能的改写。"""
        return (override or "").strip() or cls._natural_role(round_index)

    _UNDIGESTED_CARRY_KINDS = ("candidate", "ing", "any")

    @classmethod
    def _carry_banned_set(cls, carry) -> set:
        """这一圈 carry 里「被点名的问题」的文本集合。

        只收未消化类的约束（可疑候选 / ing 复述 / 此处未生超标）。
        kind=dual 是「both 配额要补什么」，是任务不是缺陷，不进这个集合。
        """
        out = set()
        for c in (carry or []):
            if str(c.get("kind", "")) not in cls._UNDIGESTED_CARRY_KINDS:
                continue
            bans = [str(b).strip() for b in (c.get("banned") or [])
                    if str(b).strip()]
            if not bans:
                # ing / unsaid 类没有 banned 列表，用约束原文前 60 字代替
                t = str(c.get("text", "")).strip()
                bans = [t[:60]] if t else []
            out.update(bans)
        return out

    @staticmethod
    def _carry_is_repeat(prev: set, cur: set) -> bool:
        """这一圈点名的问题，跟上一圈点名的是不是同一批。

        只看有没有 carry 是不够的：自省在健康运行时每圈都会产出结论，
        那只会让计数单调上涨（旧 carry_streak 就是这么把罪名安到
        「复述」头上的）。只有**同一批问题被反复点名**才算没消化。
        """
        if not cur or not prev:
            return False
        for p in prev:
            for c in cur:
                if (_similar(p, c, _CARRY_REPEAT_SIM)
                        or _overlap_coef(p, c, _KW_TOP_N) >= _CARRY_REPEAT_OVERLAP):
                    return True
        return False

    def _flag_all_drift(self, view) -> None:
        """all 层的两条漂移标记（跨层描述 + 本层自指）。

        [v1.21.56 P2-2] 这两条原来只在 _run_layer 里算，B/C/D-H 通道
        没有。放在这里两条通道共用，避免再出现一边有一边没有。
        只加标记不改产物：悬置不打分，这里也不替模型删候选。
        [v1.21.56 配置化] 触发线读 spiral.all_drift_threshold /
        all_selfref_threshold。
        """
        _drift_thr = _spiral_num(self.config, "all_drift_threshold", 0.5)
        _selfref_thr = _spiral_num(self.config, "all_selfref_threshold", 0.4)
        _drift = _all_candidate_drift_rate(view.candidates)
        if _drift > _drift_thr:
            view.quality_flags.append(
                f"all_candidate_drift({_drift:.0%})")
            view.quality_verdict = f"all 层候选漂移：{_drift:.0%}"
        _selfref = _all_candidate_selfref_rate(view.candidates)
        if _selfref > _selfref_thr:
            view.quality_flags.append(
                f"all_candidate_selfref({_selfref:.0%})")
            if not view.quality_verdict:
                view.quality_verdict = (
                    f"all 层候选自指：{_selfref:.0%}"
                    f"（换名不算生成）")

    def _final_dedup(self, view) -> tuple:
        """合并后的二次去重：候选 / & / 线头，阈值从 spiral 配置读。

        [v1.21.56 配置化] 以前三段各写一遍阈值，而且 _run_layer 和
        _b_finalize_layer 各写一遍（双写）。现在阈值和逻辑都只在一处。
        返回 (候选前, &前, 线头前, 候选后, &后, 线头后) 供调用方打印变化。
        """
        c_ov = _spiral_num(self.config, "dedup_candidate_overlap", 0.65)
        c_sim = _spiral_num(self.config, "dedup_candidate_similarity", 0.70)
        t_ov = _spiral_num(self.config, "dedup_amp_overlap", 0.60)
        t_sim = _spiral_num(self.config, "dedup_amp_similarity", 0.62)
        cb, ab, tb = (len(view.candidates or []), len(view.amps or []),
                      len(view.threads or []))
        view.candidates = _cross_round_dedup(
            view.candidates or [], overlap_thr=c_ov, sim_thr=c_sim, max_n=60)
        view.amps = _cross_round_dedup(
            view.amps or [], overlap_thr=t_ov, sim_thr=t_sim, max_n=25)
        view.threads = _cross_round_dedup(
            view.threads or [], overlap_thr=t_ov, sim_thr=t_sim, max_n=15)
        return (cb, ab, tb, len(view.candidates), len(view.amps),
                len(view.threads))

    def _lazy_every_n(self, n: int) -> int:
        """低频项（结构饱和度 / 池重估）的间隔。

        ★ 曾经按成本档「拉大一档」（balanced / economy ⇒ n+1）省调用。
          档位维度删除后不再惰性化 —— 那个做法还有个反效果：间隔被
          拉到 `structure_saturation_every_n + 1` 之后，**上限低于它的
          层永远跑不到这条判据**（实测某组层上限 ≤3、间隔 4 ⇒ 一次都
          不触发）。停止判据的检查频率不该由省钱档位决定。
        """
        return n

    def _coverage_segment(self) -> str:
        """生成「原始问题覆盖率」段；无数据时返回空串。

        [v1.21.56 自查 / v1.21.57 更正标签] 覆盖率有**两个口径**，一起显示：
          · 「模型自评折算」= dec_tracker.coverage_history[-1]，即
            coverage_of(pool) 的**累计最大值**。★ 它**不是模型直接报的数**
            （LLM 的输出 schema 里根本没有 coverage 字段）——它是
            `Σ w·depth / Σ w`：depth 是模型在 engagements[].depth 里
            自己给的 0~1 深度，被 answer 的子问题按它折算，
            status=deferred 的子问题另记 0.2 部分分。
          · 「代码实算」= 池里 status=answered 且 decidability ∈
            `_DEC_ANSWERABLE`（可判定 + 部分可判定）的**条数** /
            同名分母**条数**（等权、不看 depth、deferred 完全不计）。
        两个数不一样是**口径差**，不是谁算错。四处差异：
          1) 加权 + depth 折算  vs  等权计数；
          2) deferred 记 0.2    vs  完全不计；
          3) 累计最大值         vs  收尾那一刻的瞬时值；
          4) 按 weight 加权      vs  不看 weight。
        [v1.21.59] 两侧分母现在**同源**（都走 `_DEC_ANSWERABLE`）。
        以前只认 decidable，而喂模型的 shape 早把 partial 算成"必须回答"
        —— 三态可转之后那是静默漏账。
        只显示一个数会误导读者。同一份产物里自评通常 <= 实算
        （0.33/2/2、0.43/3/3、0.95/2/2），但**跨运行比排序会骗人**：
        quality 自评 0.70 而已答 2，economy 自评 0.33 而已答 3。
        ★ 这是「两条跑圈通道各写一份」的第三个受害者，这次一并收口到
          这一个方法里，_run_layer 和 _b_finalize_layer 都调它。

        [v1.21.57] 不可判定通道也对齐成双口径：清晰度（模型自评）+
        独立度（代码实算）。以前这两个量只进了喂模型的 shape，
        产物里看不到——等于这条通道比可判定通道少一个可核对的口径。
        """
        cov_hist = (list(self.dec_tracker.coverage_history)
                    if self.dec_tracker else [])
        if cov_hist:
            last_cov = cov_hist[-1]
            subs = list(getattr(self.pools["1"], "sub_questions", None) or [])
            dec_subs = [s for s in subs
                        if s.get("decidability") in _DEC_ANSWERABLE]
            ans = [s for s in dec_subs if s.get("status") == "answered"]
            _hard = (f"｜代码实算：已答子问题 {len(ans)}/{len(dec_subs)}"
                     if dec_subs else "")
            return (f"\n\n## 七、原始问题覆盖率\n"
                    f"研究层可判定通道最近一次覆盖率：{last_cov:.2f}"
                    f"（模型自评折算·depth 加权，累计 {len(cov_hist)} 次记录）"
                    f"{_hard}\n"
                    + self._und_channel_line())
        _und = self._und_channel_line()
        if _und:
            return ("\n\n## 七、原始问题覆盖率\n"
                    "无 decidable 子问题（可判定通道不适用）。\n" + _und)
        return ""

    def _und_channel_line(self) -> str:
        """不可判定通道的一行；无数据返回空串。

        口径：
          · 清晰度（模型自评）= undecidable_product.clarity，取最近一次。
          · 独立度（代码实算）= structural_amps 里**不与任何 und_aspects
            重合**（_overlap_coef < 0.3）的条数 / structural_amps 总条数。
            ★ 它量的是「独立提炼出来的结构有多独立」，**不是覆盖率** ——
              提示词要求 structural_amps「不得直接复述 und_aspects 的原话」，
              所以越高越合规。旧名「结构覆盖率」与这条要求方向相反（复述得
              越像读数越高），已废弃。空池记 `None`（不可计算），
              不印 0.00 冒充读数。
          · 对齐覆盖率（代码实算）**保留原名**：aligned_amps 的定义就是
            「正好对应 und_aspects 中的某一项」，用覆盖率是自洽的。
        ★ 历史 packed 只有旧键（struct_coverage_history）时按旧口径渲染，
          并显式标注「旧口径」，保证老产物重渲染不丢信息、也不误导。
        """
        ch = getattr(self.pools["1"], "undecidable_channel", None) or {}
        cl_hist = list(ch.get("clarity_history") or [])
        ih_hist = list(ch.get("indep_history") or [])
        sc_hist = list(ch.get("struct_coverage_history") or [])
        ac_hist = list(ch.get("aligned_coverage_history") or [])
        if not cl_hist and not ih_hist and not sc_hist and not ac_hist:
            return ""
        parts = []
        if cl_hist:
            parts.append(f"清晰度 {cl_hist[-1]:.2f}"
                         f"（模型自评，累计 {len(cl_hist)} 次记录）")
        if ih_hist:
            _iv = ih_hist[-1]
            _nfree = int(ch.get("last_indep_free", 0) or 0)
            _npool = int(ch.get("last_indep_pool", 0) or 0)
            if _iv is None:
                parts.append("独立度 —（无独立结构，不可计算）")
            else:
                parts.append(f"独立度 {_iv:.2f}"
                             f"（代码实算：独立结构 {_nfree}/{_npool} 条"
                             f"不与评估阶段方面重合；这是「独立比例」，"
                             f"不是覆盖率）")
        elif sc_hist:
            aspects = list(ch.get("und_aspects") or [])
            hit = int(ch.get("last_struct_hit", 0) or 0)
            _hard = (f"，已对上 {hit}/{len(aspects)} 个不可判定方面"
                     if aspects else "")
            parts.append(f"结构覆盖率 {sc_hist[-1]:.2f}"
                         f"（旧口径{_hard}）")
        if ac_hist:
            aspects = list(ch.get("und_aspects") or [])
            ahit = int(ch.get("last_aligned_hit", 0) or 0)
            _hard2 = (f"，已对上 {ahit}/{len(aspects)} 个不可判定方面"
                      if aspects else "")
            parts.append(f"对齐覆盖率 {ac_hist[-1]:.2f}"
                         f"（代码实算{_hard2}）")
        #  ★ 结构覆盖率（重设计）＝自触及：结构写完之后，研究过程
        #    自己还碰不碰它。分母 = 结构条数（与独立度同），
        #    视角正交（独立度＝有多新；本读数＝有多活）。
        if "sc_history" in ch and ch.get("last_sc_ratio") is not None:
            _scv = ch.get("last_sc_ratio")
            _nsc_t = int(ch.get("last_sc_touched", 0) or 0)
            _nsc_p = int(ch.get("last_sc_pool", 0) or 0)
            parts.append(
                f"结构覆盖率 {_scv:.2f}"
                f"（代码实算：{_nsc_t}/{_nsc_p} 条结构被后续圈"
                f"再次触及；量的是「结构有多活」，不是方面被覆盖几成）")
        elif "sc_history" in ch:
            parts.append("结构覆盖率 —（无结构，不可计算）")
        return "研究层不可判定通道：" + "｜".join(parts) + "\n"

    @classmethod
    def _carry_next_role(cls, round_index: int, has_carry: bool) -> str:
        """上一圈产出 carry 时，下一圈（round_index）该用什么角色。

        ★ 关键：改写的是**下一圈的默认角色**，不是本圈已经用完的那个。
        旧代码写的是 `if role == "深入": next_role = "转向"`，
        role 是本圈的角色 —— 既错位一圈，又在 role 为「摊开」时
        把自己原样喂回去（else: next_role = role），
        于是只要每圈都有 carry，排班就永久冻在「摊开」。
        实测产物里四层全是「摊开 → 摊开 → 摊开」，就是这么来的。
        """
        if not has_carry:
            return ""
        _next = cls._natural_role(round_index)
        return {"深入": "转向", "收束": "复裁"}.get(_next, _next)

    def _carry_tail(self, view: "View", seeds: List[dict],
                    round_index: int) -> tuple:
        """一圈收尾的自省回流：算 carry → 并进 seeds → 定下一圈角色。

        [P2-9] 这段原来在 _run_layer 和 _run_one_round_B 里各写一遍。
        next_role 的反馈环就发生在这个尾巴上，而且只有一处被改、
        一处没改（B 通道带着同一个 bug）。抽出来之后，这一条尾巴
        只剩一个版本，双写没有第二次机会。

        round_index 是 **0-based** 的圈序（_run_one_round_B 传 r-1）。
        返回 (本圈产出的 carry 列表, 拼好 carry 前缀的 seeds, 下一圈角色)。
        """
        view.carry = self._build_carry(view)
        if not view.carry:
            return [], seeds, ""
        carry = list(view.carry)
        self.vp(f"   🔁 [自省回流] 注入 {len(carry)} 条约束进下一圈")
        for _c in carry[:3]:
            self.vp(f"      · [{_c.get('kind', '?')}] "
                    f"{str(_c.get('text', ''))[:70]}")
        # [P2-9] 改写的是**下一圈**的默认角色，不是本圈已用完的那个
        next_role = self._carry_next_role(round_index + 1, True)
        return carry, carry + list(seeds), next_role

    # ---------- [P1-5] 自省回流 ----------
    def _build_carry(self, view: "View") -> List[dict]:
        """把这一圈 _self_check 的结论翻译成下一圈的约束探针。

        原先 self_check 的结果只写进 md 的自省段落。实测三份产物的自省
        都精准抓到了「候选 9-15 属补写凑数」「ing 复述=True」
        「可疑 & 全 6 条」，然后什么都没发生 —— 花一次 LLM 调用做质检，
        质检结论被丢弃。这里让它变成下一圈真正的输入约束。
        """
        cfg = (self.config.get("memory") or {})
        if cfg.get("carry_feedback") is False:
            return []
        out: List[dict] = []
        sc = view.self_check or {}

        # [P2-7] 每条约束带 kind（决定它进哪个环节的 prompt）、
        # text（渲染用）、banned（核对用）。原来只有 question 一个字段，
        # 传下去被当成普通探针，约束性全靠模型自觉。
        def _mk(text, link, gain, kind, banned=None):
            return {"question": text, "link": link,
                    "expected_gain": gain, "kind": kind,
                    "text": text, "banned": banned or []}

        susp = sc.get("suspicious_candidates") or []
        if susp:
            descs = []
            for i in susp[:6]:
                try:
                    n = int(i) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= n < len(view.candidates or []):
                    d = str(view.candidates[n].get("desc", "")).strip()
                    if d:
                        descs.append(d[:60])
            if descs:
                out.append(_mk(
                    "上面这几条候选被判为「后补／换说法复述」，本圈禁止"
                    "以任何形式重述它们——原样、换说法、扩写都算。"
                    "只交真的长出来的新东西：" + "；".join(descs),
                    "self-check 判定的复述条目，绕开去重就能喷更多，"
                    "但那不叫展开",
                    0.6, "candidate", descs))

        if sc.get("ing_rephrased"):
            out.append(_mk(
                "上一圈 ing 输出超过一半是上游 view 的复述。本圈 ing 必须"
                "写出上游 view 里没有的句子；写不出就明说「此处未生」，"
                "不要用换个说法顶替。",
                "复述不产生距离，只会把空转记成推进",
                0.7, "ing"))

        bq = view.both_quota or {}
        items = [i for i in (bq.get("items") or [])
                 if str(i.get("missing", "")).strip()]
        if items:
            miss = "；".join(
                f"「{str(i.get('tension', ''))[:40]}」缺"
                f"{str(i.get('missing', ''))[:40]}"
                for i in items[:4])
            out.append(_mk(
                f"以下张力被判 both 且写明了缺什么：{miss}。"
                f"本圈若能给出其中任一项，就把对应张力裁成 0 或 1"
                f"；给不出就明说它为什么不可能出现。",
                "both 占满一张单子等于没裁，"
                "缺的东西要有人去把它生出来",
                0.8, "dual"))

        # [P2-4] 「此处未生」用过头也是结论，同样要回流。
        if sc.get("unsaid_is_escape"):
            _un = int(sc.get("unsaid_count", 0) or 0)
            _lim = self._unsaid_limit_for(getattr(view, "entry", ""))
            # 阈值 <= 0 = 不设限：_self_check 不会判逃避，这里也就没有
            # 可回流的结论（否则会拿一个被关掉的判据去约束下一圈）。
            if _lim > 0:
                out.append(_mk(
                    f"上一圈出现 {_un} 处「此处未生」，已超过阈值 "
                    f"{_lim}——这一圈不许再拿它收尾。"
                    f"先把上一圈标了未生的地方真的推一遍，"
                    f"推不动要说清卡在哪一步，不是写一句「未生」就交卷。",
                    "「此处未生」是诚实姿态，用成套路就是逃避",
                    0.75, "any"))

        if getattr(view, "entry", "") == "all" and (view.candidates or []):
            _drift = _all_candidate_drift_rate(view.candidates)
            _selfref = _all_candidate_selfref_rate(view.candidates)
            _dthr = _spiral_num(
                self.config, "all_drift_threshold", 0.5)
            _sthr = _spiral_num(
                self.config, "all_selfref_threshold", 0.4)
            _why = []
            if _drift > _dthr:
                _why.append(f"{_drift:.0%} 在描述别层")
            if _selfref > _sthr:
                _why.append(f"{_selfref:.0%} 在议论候选自己")
            if _why:
                out.append(_mk(
                    "上一圈 all 的候选里 " + "、".join(_why) + "。"
                    "这不是 all 的候选——它没有落在任何**具体的东西**上。"
                    "本圈每一条候选都要能指到一个具体的东西："
                    "谁、在什么情况下、发生了什么，或者到底缺了哪一样。"
                    "不许再拿 view0 / view1 / 两边 / 上游 / 层 这类词"
                    "当主语宾语，也不许议论「本层候选」自己怎么样。"
                    "宁可少写几条，也不要再交抽象话。",
                    "描述层与层的关系是记账不是内容，换名不算生成",
                    0.7, "candidate"))
                # 单独留痕：这条不在 carry 预览的前 3 条里（见上面的
                # 截断说明），不主动打一行的话，日志里看不到它生效过。
                self.vp(f"   🧭 [P2-3] all 候选漂移（{'、'.join(_why)}），"
                        f"注入「落到具体」约束进下一圈")
        return out

    def _unsaid_limit_for(self, entry: str) -> int:
        """MetaDGTF 侧的同一阈值（_build_carry 用，按层取）。"""
        try:
            n = int(_spiral_for(self.config, entry).get(
                "unsaid_escape_limit", UNSAID_ESCAPE_LIMIT))
        except (TypeError, ValueError):
            n = UNSAID_ESCAPE_LIMIT
        return max(0, n)

    # ---------- [P2-7] 回流生效核对 ----------
    def _check_carry_response(self, view: "View",
                              carry: List[dict]) -> dict:
        """上一圈注入的约束，这一圈到底有没有被遵守？

        [P1-5] 只管注入不管核对：日志里有一行「注入 N 条约束」，
        然后没有任何证据说明这 N 条起了作用。自省于是永远在
        「发现问题 → 写进 md → 下一圈照旧」的环里。
        这里给出可落地的核对结论：
          · kind=candidate：被点名的条目有没有换个说法又出现在本圈候选里
          · kind=ing：本圈 ing 复述率有没有降下来
          · kind=any：只记录，不做硬判据
        """
        if not carry:
            return {}
        violations: List[str] = []
        checked = 0
        dropped = list(getattr(view, "carry_dropped", None) or [])
        for c in carry:
            kind = c.get("kind")
            if kind == "candidate":
                banned = [str(b).strip() for b in (c.get("banned") or [])
                          if str(b).strip()]
                if not banned:
                    continue
                checked += 1
                # [P2-9] 先认硬执行拦下的账：这几条模型确实又写出来了，
                # 只是被当场丢掉。不认这笔账的话，硬执行会让核对恒为
                # 「0 违例」，等于用统计口径的干净掩盖了行为没改。
                _dropped = [x for x in dropped
                            if _banned_hit(str(x.get("desc", "")),
                                           banned)]
                if _dropped:
                    violations.append(
                        f"禁条目重现·已拦下{len(_dropped)}条："
                        f"{str(_dropped[0].get('desc', ''))[:24]}")
                    continue
                for cand in (view.candidates or []):
                    d = str(cand.get("desc", "")).strip()
                    if not d:
                        continue
                    if _banned_hit(d, banned):
                        violations.append(f"禁条目重现：{d[:30]}")
                        break
            elif kind == "ing":
                checked += 1
                rr = getattr(view, "_ing_rephrase_ratio", None)
                if rr is not None and float(rr) >= 0.5:
                    violations.append(f"ing 复述率仍 {float(rr):.0%}")
                elif (view.self_check or {}).get("ing_rephrased"):
                    violations.append("ing 仍被自省判为复述")
        if not checked:
            return {}
        res = {
            "checked": checked,
            "violations": len(violations),
            "items": violations[:5],
            "notes": (f"注入 {len(carry)} 条、可核对 {checked} 条，"
                      f"违例 {len(violations)} 条"
                      + ("" if not violations
                         else "：" + "；".join(violations[:3]))),
        }
        if violations:
            self.vp(f"   ⚠️ [自省回流核对] {len(violations)}/{checked} "
                    f"条约束没被遵守：" + "；".join(violations[:2]))
        else:
            self.vp(f"   ✅ [自省回流核对] {checked} 条约束已遵守")
        return res

    # ============================================================
    # 状态更新：调度器唯一入口
    # ============================================================
    def _apply_view_to_pool(self, view: View, pool: Pool, entry: str,
                            rephrased_streak: int = 0,
                            meta_idle_streak: int = 0, layer: int = 0):
        # [fix-100] 池是共享状态，写入统一走这把可重入锁
        with self._pool_lock:
            return self._apply_view_to_pool_locked(
                view, pool, entry, rephrased_streak, meta_idle_streak,
                layer)

    def _apply_view_to_pool_locked(self, view: View, pool: Pool, entry: str,
                            rephrased_streak: int = 0,
                            meta_idle_streak: int = 0, layer: int = 0):
        _sim_cfg = (self.config.get("sim") or {})
        pool.merge(view.amps, view.threads, view.meta, view.probes,
                   thr=_sim_cfg.get("dedup", _DEDUP_SIM),
                   susp_thr=_sim_cfg.get("dedup_susp", _DEDUP_SUSP_SIM),
                   aspect_units=list(getattr(view, "aspect_units", None) or []))
        _sc = getattr(view, "self_check", None) or {}
        _sc_c = _sc.get("suspicious_candidates") or []
        _sc_a = _sc.get("suspicious_amps") or []

        if _sc:
            _notes = []
            if _sc.get("ing_rephrased"):
                _notes.append("ing 被判定为复述")
            if len(_sc_c) >= 3:
                _notes.append("可疑候选 " + str(_sc_c))
            if len(_sc_a) >= 2:
                _notes.append("可疑 & " + str(_sc_a))
            if _notes:
                _msg = "[上一圈 self-check 反馈] " + "；".join(_notes)
                pool.meta.append(_msg)
                if getattr(self, "verbose", False):
                    print(f"   📝 self-check 反馈写入池：{_msg[:120]}")

        _sc_rephrase = (bool(_sc.get("ing_rephrased")) if _sc else False)
        _direct_rephrase = (getattr(view, "_ing_rephrase_ratio", 0.0)
                            >= 0.5)
        _rr_ratio = getattr(view, "_ing_rephrase_ratio", None)
        _rr_str = (f"{_rr_ratio:.0%}"
                   if _rr_ratio is not None else "n/a")
        _is_meta_or_duel = (entry in ("all", "both"))
        _rephrase_detected = _direct_rephrase or _sc_rephrase

        if _is_meta_or_duel and _rephrase_detected:
            view.idle = True
            rephrased_streak = 0
            meta_idle_streak += 1
            try:
                view._meta_idle_streak = meta_idle_streak
            except Exception:
                pass
            if getattr(self, "verbose", False):
                _layer_label = "元层" if entry == "all" else "对撞层"
                _why = ("direct" if _direct_rephrase
                        else "self-check")
                print(f"   ⏸ [fix-72 v3] {_layer_label} ing 复述"
                      f"直接判 idle（why={_why}, "
                      f"ing_rr={_rr_str}），不累积 streak"
                      f"（连续 {meta_idle_streak} 圈）")
        elif _is_meta_or_duel:
            meta_idle_streak = 0
            try:
                view._meta_idle_streak = 0
            except Exception:
                pass
        else:
            if _sc_rephrase or _direct_rephrase:
                rephrased_streak += 1
            else:
                rephrased_streak = 0
            if getattr(self, "verbose", False):
                print(f"   🔬 rephrase streak={rephrased_streak}"
                      f" sc={_sc_rephrase}"
                      f" direct={_direct_rephrase}"
                      f" ing_rr={_rr_str}"
                      f" susp_c={len(_sc_c)}")
            if rephrased_streak >= 2:
                view.idle = True
                if getattr(self, "verbose", False):
                    _why_parts = []
                    if _sc_rephrase:
                        _why_parts.append("self-check")
                    if _direct_rephrase:
                        _why_parts.append("direct")
                    _why_str = "+".join(_why_parts) or "?"
                    print(f"   ⏸ self-check 反复复述"
                          f"（连续 {rephrased_streak} 圈，"
                          f"why={_why_str}），"
                          f"标记为空转")
            # ★ 让 0/1 层的「连续复述圈数」也**可读**：`_compute_rephrase_streak`
            #   （唯一消费点）读的就是这个属性。条件 1 已四层通用，没有这一行，
            #   它那半条信号对 0/1 永远是 0。**不改 view.idle 的既有语义。**
            try:
                view._meta_idle_streak = rephrased_streak
            except Exception:
                pass
        if view.decidable_product:
            pool.add_decidable(view.decidable_product)
        if view.undecidable_product:
            und_aspects = []
            if self.decidability_result:
                und_aspects = self.decidability_result.get(
                    "undecidable_aspects", []) or []
            # [D1/D2 元数据注入] 层名 / 圈号 / 迁移驱动**由这里统一注入**
            #   —— `layer` 实参在本仓库常指**圈号**（见 `layer_no = r + 1`），
            #   层名另走 `view.entry`；两者的语义差正是「独立复现」能否成立的关键。
            _und_prod = view.undecidable_product
            try:
                _und_prod["_layer_name"] = str(getattr(view, "entry", "") or "")
                _und_prod["_round_no"] = int(layer or 0)
                # 攻击证据：不可判定通道里被点名的冲突（非空即「被质疑」）
                _atk = getattr(view, "collision", "") or ""
                if not _atk:
                    _atk = str(getattr(view, "duel_conflict", "") or "")
                if _atk:
                    _und_prod["_belief_attack"] = str(_atk)[:80]
                # 已清偿：本层可判定通道答出的条 ⇒ resolved
                _res = ""
                _dc = getattr(view, "decidable_product", None) or {}
                if _dc:
                    _ans = _dc.get("answered") or _dc.get("resolutions") or []
                    if _ans:
                        _res = "decidable_channel"
                if _res:
                    _und_prod["_belief_resolved"] = _res
            except Exception:
                pass
            pool.add_undecidable(
                _und_prod,
                und_aspects=und_aspects, layer=layer,
                covered_aspects=list(
                    getattr(view, "covered_aspects", None) or []))
        # [D1 回填 · 时序修正] `View.belief_items` 之前是**声明了、也出口了、
        #   但从不被赋值**的死字段（`View.to_dict = asdict(self)` ⇒ 键恒 []）。
        #   ★ 回填**必须放在 `add_undecidable` 之后** —— 信念条目是那一步才
        #     upsert 进池的；放前面读到的池还是空的（真跑实测恒 []，
        #     见 v12328_报告.md §2.5）。这是「有接线 ≠ 这跑走得到」的时序版。
        #   ★ 只回填**与本次 view 相关**的条目（按 text 精确命中），
        #     不是把全池倒给每个 view —— view 是「这一圈看到了什么」。
        #   ★ 命中不到就保持 []（不猜、不兜底）。
        try:
            _seen_keys = set()
            for _a in (view.amps or []):
                _t0 = str(_a.get("desc") or _a.get("text") or "").strip()
                if _t0:
                    _seen_keys.add(_t0)
            for _t0 in (view.anchor_touched or []):
                _t0 = str(_t0.get("text") or _t0.get("desc") or "").strip()
                if _t0:
                    _seen_keys.add(_t0)
            if _seen_keys:
                _bind = []
                for _it in (pool.belief_items or []):
                    if str(_it.get("text", "")).strip() in _seen_keys:
                        _bind.append(_it)
                if _bind:
                    view.belief_items = _bind
        except Exception:
            pass
        return rephrased_streak, meta_idle_streak

    # ============================================================
    # 池评估
    # ============================================================
    def _assess_decidability_from_pool_view(
            self, question: str, view: View) -> dict:
        cand_lines = []
        for i, c in enumerate((view.candidates or [])[:20], 1):
            pos = c.get("position", "?")
            attr = c.get("attribute", "?")
            desc = str(c.get("desc", ""))[:80]
            amp = " [&候选]" if c.get("is_amp_candidate") else ""
            cand_lines.append(f"  {i}. [{attr}×{pos}]{amp} {desc}")
        cand_text = "\n".join(cand_lines) or "（无候选）"

        amp_lines = [
            f"  - [{a.get('type', '?')}] {str(a.get('desc', ''))[:80]}"
            for a in (view.amps or [])[:10]
        ] or ["（无 & 印记）"]

        susp_lines = [
            f"  - {str(s.get('target', ''))[:80]}"
            f"（{str(s.get('reason', ''))[:40]}）"
            for s in (view.suspensions or [])
            if s.get("status") in ("active", "stable")
        ][:10] or ["（无主动悬置）"]

        thread_lines = [
            f"  - {str(t.get('desc', ''))[:80]}"
            for t in (view.threads or [])[:10]
        ] or ["（无线头）"]

        ing_text = str(view.collision or "")[:1500]

        _triage_sys = self._anchor_triage_sys()
        _anchor_ctx = self._anchor_view_ctx()

        system = (
            "你是一个可判定性的**观察者**。\n"
            "\n"
            "你不看原始问题本身去判断它是否可判定，\n"
            "而是**读修行层留下来的形状**，从形状里读出可判定性。\n"
            "\n"
            "【你看到的产物】\n"
            "- 候选的 position 分布：判得明确（0 或 1）说明锚点能触及；\n"
            "  position=both 说明这一处两面读不出同一个答案\n"
            "- & 候选（attribute != position）：从一面长出、另一面读出不同结果\n"
            "- 主动悬置：修行层\"看清了、可以碰、决定不碰\"的点\n"
            "- ing 输出：撞出第三者说明有可对撞结构；\"此处未生\"说明这一面还没撞动\n"
            "- 悬空线头：未走完的方向\n"
            "\n"
            "【★ 最重要：区分「未决」和「不可判定」】\n"
            "修行层产出的 & 候选、主动悬置、悬空线头、\"此处未生\"，绝大多数\n"
            "只是**这一圈还没判出**（未决），不代表**原则上判不出**（不可判定）。\n"
            "- 未决：还需要更多工作/查阅/下一圈才定得下来 → 不算不可判定\n"
            "- 不可判定：结构上原则判不出——自指循环、无共同参照系、\n"
            "  本体论判断（无经验判决实验）、两面原则性对不上\n"
            "  → 只有这类才放进 undecidable_aspects\n"
            "\n"
            "[v1.21.61] ★★ 「不可判定」的**范围**：一条要进 undecidable_aspects，\n"
            "必须**同时**过两道闸\n"
            "  闸一（范围）：它落在**这道题的核心诉求**上。某一列的读法、\n"
            "    某一处的计数方式、某个附属环节的细节 → 都不是核心诉求，不算。\n"
            "  闸二（性质）：它**原则上判不出**。凡属下面任一种 → 不算：\n"
            "    · \"此处未生\" / 这一面还没撞动 → 未决，再多跑一圈可能就生\n"
            "    · 需外部动作 / 由外部动作决定 / 需适用动作 → 未决，\n"
            "      差的是有人去做，不是判不出\n"
            "    · 计数/统计需要额外记录 → 未决，补一次测量就有\n"
            "    · 定义未规定 / 措辞未明 / 文本没给次序 → **可规定**，\n"
            "      规定下来答案就确定，属可判定\n"
            "    · 两侧量纲不可比 → **可分别报告**，各自给各自的数即可，\n"
            "      属可判定\n"
            "  过了闸二的，只剩：自指循环、无共同参照系**且无法分别报告**、\n"
            "  没有经验判决实验的本体论判断。\n"
            "\n"
            "【★ 主导性】decidable_aspects 明显占多数、且核心诉求可判时，\n"
            "不要让一两条局部细节把整体拉成 partial：局部的未决或不可比，\n"
            "只要能分别报告，整体仍判 decidable。\n"
            "\n"
            "【从这些产物读出三态之一（口径与外判一致）】\n"
            "- decidable：候选普遍能判出 0/1；即便有未决，也属于查得到的\n"
            "  经验/定义问题，不是原则判不出\n"
            "- partial：核心诉求里**同时**存在真的可判定部分和真的不可判定\n"
            "  部分（不是未决，是过了上面两道闸的结构上判不出）\n"
            "- undecidable：主要成分是自指/无参照系/本体论这类原则判不出的\n"
            "\n"
            "【★ 关键】\n"
            "每一条 decidable_aspects / undecidable_aspects 必须能追溯到\n"
            "池里的具体产物。在 evidence 字段里给出追溯来源。\n"
            "undecidable_aspects **只放\"原则判不出\"的**；未决的不要放进去。\n"
            + _triage_sys +
            "\n"
            "严格 JSON：\n"
            "{\n"
            '  "decidability": "decidable|partial|undecidable",\n'
            '  "reason": "<=100字，说明从池里读到了什么",\n'
            '  "features": ["命中的特征，<=3条"],\n'
            '  "decidable_aspects": ["<=5条，每条<=40字"],\n'
            '  "undecidable_aspects": ["<=5条，每条<=40字"],\n'
            '  "evidence": [\n'
            '    {"aspect": "...", "source": "候选3 / amp1 / suspension2"}\n'
            "  ]\n"
            "}\n"
        )
        user = (
            f"【原始问题】\n{question}\n\n"
            f"【修行层候选（attribute×position）】\n{cand_text}\n\n"
            f"【& 印记】\n" + "\n".join(amp_lines) + "\n\n"
            f"【主动悬置】\n" + "\n".join(susp_lines) + "\n\n"
            f"【悬空线头】\n" + "\n".join(thread_lines) + "\n\n"
            f"【ing 输出】\n{ing_text or '（此处未生）'}"
            + _anchor_ctx
        )

        try:
            raw = self.llm.call(system, user, 0.3, 1200, json_mode=True,
                                stage="assess_decidability_from_pool_view")
        except Exception as e:
            logger.warning("从池读可判定性失败: %s", e)
            return {
                "decidability": "decidable", "reason": "池评估失败",
                "features": [], "decidable_aspects": [],
                "undecidable_aspects": [], "evidence": [],
                "_source": "pool_failed",
            }

        data = self.llm.parse_json(raw) or {}
        status = str(data.get("decidability", "decidable")).lower()
        if status not in ("decidable", "partial", "undecidable"):
            status = "decidable"

        def _list(key):
            v = data.get(key, [])
            if not isinstance(v, list):
                return []
            return [str(x)[:120] for x in v[:5]]

        evidences = data.get("evidence", [])
        if not isinstance(evidences, list):
            evidences = []
        _dec = _list("decidable_aspects")
        _und = _list("undecidable_aspects")
        _untraced = _untraced_undecidable(_und, evidences)
        _und_traced = [a for a in _und if a not in _untraced]
        status = _normalize_decidability(status, _dec, _und_traced,
                                         where="修行池评估")
        return {
            "decidability": status,
            "reason": str(data.get("reason", ""))[:200],
            "features": _list("features"),
            "decidable_aspects": _dec,
            "undecidable_aspects": _und,
            "evidence": evidences[:8],
            "_evidence_full": list(evidences),
            "_source": "pool",
            "_und_untraced": _untraced,
            # 归一化实际采信的那几条（无追溯的已剔除）
            "_und_traced": _und_traced,
        }

    def _merge_decidability(self, pool_res: dict,
                            ext_res: Optional[dict]) -> dict:
        if ext_res is None:
            return pool_res

        pool_status = pool_res.get("decidability", "decidable")
        ext_status = ext_res.get("decidability", "decidable")

        dec_aspects = list(pool_res.get("decidable_aspects", []))
        for a in ext_res.get("decidable_aspects", []):
            a_str = str(a).strip()
            if not a_str:
                continue
            if not any(_similar(a_str, x, _MERGE_SIM) for x in dec_aspects):
                dec_aspects.append(f"[外] {a_str}")

        und_aspects = list(pool_res.get("undecidable_aspects", []))
        for a in ext_res.get("undecidable_aspects", []):
            a_str = str(a).strip()
            if not a_str:
                continue
            if not any(_similar(a_str, x, _MERGE_SIM) for x in und_aspects):
                und_aspects.append(f"[外] {a_str}")

        merged = dict(pool_res)
        merged["decidable_aspects"] = dec_aspects[:8]
        merged["undecidable_aspects"] = und_aspects[:8]
        _ext_refs = [str(x)[:20] for x in
                     (ext_res.get("anchor_refs") or [])[:12]]
        _ext_given = int(ext_res.get("_anchors_given") or 0)
        if _ext_refs or _ext_given:
            merged["anchor_refs"] = _ext_refs
            merged["_anchors_given"] = _ext_given

        _cached = pool_res.get("_und_untraced")
        if isinstance(_cached, list):
            _untraced_pool = set(_cached)
        else:
            _full_ev = list(pool_res.get("_evidence_full")
                            or pool_res.get("evidence") or [])
            _untraced_pool = set(_untraced_undecidable(
                pool_res.get("undecidable_aspects", []),
                _full_ev))
        _und_for_norm = [
            a for a in merged["undecidable_aspects"]
            if str(a).startswith("[外]") or a not in _untraced_pool
        ]
        merged["decidability"] = _normalize_decidability(
            pool_status, merged["decidable_aspects"],
            _und_for_norm, where="合并池+外判")
        merged["_ext_status"] = ext_status
        merged["_ext_reason"] = str(ext_res.get("reason", ""))[:200]
        merged["_ext_features"] = list(ext_res.get("features", []))[:5]
        merged["_divergent"] = (pool_status != ext_status)
        merged["_pool_status"] = pool_status
        # 只报**池判**里没追溯的。[外] 条目不算 —— 见上面 `_und_for_norm`
        # 的说明，把它算进来就是误报（a61F 的 5 条里 3 条是这种）。
        merged["_und_untraced"] = sorted(_untraced_pool)
        merged["_source"] = "pool+external"
        return merged

    def _stamp_decidability_criteria(self) -> None:
        """ 给判定盖上「判据可查」的戳 —— **所有出口**都过一遍。

        判据只有两条能自动查：两路分不分叉、每条不可判定有没有追溯。
        ★ 单边路径（external-only / pool-only / off）**没有分叉可言**，
          `_divergent` 记 False 而不是让它缺失——缺失会让验收无从下手
          （冒烟 [P0-3] 就是这么抓到这个缺口的：D/E 走 external，
          两个判据字段都没有，判定对不对根本没法查）。
        ★ `_und_untraced` 只在**有池**的路径上算：外判本来就没有池可追溯，
          拿"无池内追溯"去否定它的理由是误报，所以 external-only 时置空。
        """
        d = self.decidability_result
        if d.get("_divergent") is None:
            d["_divergent"] = False          # 单边判定：无分叉可言
        if d.get("_pool_status") is None:
            d["_pool_status"] = d.get("decidability")
        if d.get("_und_untraced") is None:
            if "pool" in str(d.get("_source", "")):
                # [外] 前缀 = 外判列的条目。外判没有池可追溯，把它算进
                # "无追溯"是误报（与 _merge_decidability 同一口径）。
                _pool_und = [a for a in (d.get("undecidable_aspects") or [])
                             if not str(a).startswith("[外]")]
                d["_und_untraced"] = _untraced_undecidable(
                    _pool_und, d.get("evidence") or [])
            else:
                d["_und_untraced"] = []

    def _print_decidability(self, source: str = "external") -> None:
        self._stamp_decidability_criteria()
        if source == "off":
            self.vp(f"\n{'─'*60}\n🧭 全局可判定性评估：已关闭"
                    f"（默认 decidable）")
            return

        source_label = {
            "pool+external": "池 + 外部",
            "pool_only": "仅修行池",
            "external": "外部评估",
        }.get(source, source)
        self.vp(f"\n{'─'*60}\n🧭 全局可判定性评估（{source_label}）")

        status_label = {
            "decidable": "✓ 以可判定为主",
            "partial": "◐ 双通道并行",
            "undecidable": "⚠️ 以不可判定为主",
        }

        pool_status = self.decidability_result.get("decidability", "decidable")
        ext_status = self.decidability_result.get("_ext_status")
        divergent = bool(self.decidability_result.get("_divergent"))

        if ext_status is not None:
            self.vp(f"   池判：{status_label.get(pool_status, pool_status)}")
            self.vp(f"   外判：{status_label.get(ext_status, ext_status)}")
            if divergent:
                self.vp(f"   ⚠️ 两路分叉：池={pool_status} / 外={ext_status}"
                        "；以池判为准（DGTF 机制下池是展开的产物）")
                ext_reason = self.decidability_result.get("_ext_reason", "")
                if ext_reason:
                    self.vp(f"      外判理由：{ext_reason}")
        else:
            self.vp(f"   {status_label.get(pool_status, pool_status)}")

        self.vp(f"   池理由：{self.decidability_result.get('reason', '')}")
        for a in self.decidability_result.get("decidable_aspects", []):
            self.vp(f"   📗 可判定：{a}")
        for a in self.decidability_result.get("undecidable_aspects", []):
            self.vp(f"   📘 不可判定：{a}")
        untraced = self.decidability_result.get("_und_untraced") or []
        if untraced:
            self.vp(f"   ⚠️ 不可判定里 {len(untraced)} 条**无池内追溯**"
                    f"（理由不成立，别拿它当判据）：")
            for a in untraced[:5]:
                self.vp(f"       · {a}")

        evidences = self.decidability_result.get("evidence") or []
        if evidences:
            self.vp("   📎 追溯来源：")
            for ev in evidences[:5]:
                if isinstance(ev, dict):
                    aspect = str(ev.get("aspect", ""))[:40]
                    src = str(ev.get("source", ""))[:60]
                    self.vp(f"      · {aspect}  ← {src}")

    def _assess_decidability_dynamic(self, question: str,
                                     zero_view: Optional[View]) -> None:
        """ 可判定性判定的**唯一**确定时机：研究层第 1 圈拆解时。

        读池有产物 → 池评估（读 0 层此刻留下的形状，读到哪就是哪）；
        没产物 → 退回外部评估。判定跟着研究层拆解源走，不再有起跑前的
        全局快照——D/E 双起并行时，修行层跑得快、先交出第 1 圈，研究层
        拆解就能读到池；跑得慢就读不到、退回外部。二者由竞态决定，
        不做人为定死。
        """
        assess_on = _action_on(self.config, "assess_decidability")
        source_cfg = (self.config.get("actions") or {}).get(
            "decidability_source", "pool")
        fallback = {
            "decidability": "decidable", "reason": "",
            "features": [], "decidable_aspects": [],
            "undecidable_aspects": []}

        if not assess_on:
            self.decidability_result = dict(fallback)
            self.decidability_result["reason"] = "动作已关闭"
            self.decidability_result["_source"] = "off"
            self._print_decidability(source="off")
            return

        ext_res: Optional[dict] = None
        if source_cfg in ("pool", "external"):
            try:
                ext_res = self._cached_ext_assess(question)
            except Exception as exc:
                logger.warning("外部可判定性评估失败: %s", exc)

        has_prod = self._has_pool_content_view(zero_view)
        use_pool = has_prod and source_cfg in ("pool", "pool_only")

        if not use_pool:
            self.decidability_result = dict(ext_res) if ext_res \
                else dict(fallback)
            self.decidability_result["_source"] = "external"
            self._print_decidability(source="external(拆解时池空)")
            return

        pool_res = None
        try:
            pool_res = self._assess_decidability_from_pool_view(
                question, zero_view)
        except Exception as exc:
            logger.warning("池视角可判定性评估失败: %s", exc)

        if pool_res is None:
            self.decidability_result = dict(ext_res) if ext_res \
                else dict(fallback)
            self.decidability_result["_source"] = "external"
            self._print_decidability(source="external(pool失败)")
        elif source_cfg == "pool" and ext_res is not None:
            self.decidability_result = self._merge_decidability(
                pool_res, ext_res)
            self._print_decidability(source="pool+external(拆解时读池)")
        else:
            self.decidability_result = pool_res
            self._print_decidability(source="pool_only(拆解时读池)")

    def _print_polarity_snapshot(self, pool: Pool, entry: str,
                                 layer_no: int) -> None:
        if not self.verbose:
            return
        if not (pool.amps or pool.threads):
            return
        n = 5
        amps_tail = pool.amps[-n:]
        threads_tail = pool.threads[-n:]
        bits = []
        for a in amps_tail:
            pol = str(a.get("polarity") or "?").strip() or "?"
            desc = str(a.get("desc", ""))[:36]
            bits.append(f"      & [{pol}] {desc}")
        for t in threads_tail:
            pol = str(t.get("polarity") or "?").strip() or "?"
            desc = str(t.get("desc", ""))[:36]
            bits.append(f"      ... [{pol}] {desc}")
        if bits:
            n_unset = sum(1 for a in pool.amps
                          if str(a.get("polarity") or "?") == "?")
            n_total = len(pool.amps) + len(pool.threads)
            header = (f"   📋 池极性快照（{entry} 第 {layer_no} 圈，"
                      f"共 {n_total} 条，未判 {n_unset} 条）：")
            self.vp(header)
            for b in bits:
                self.vp(b)

    def _before_round(self, entry: str, pool: "Pool",
                      layer_no: int) -> None:
        """ 圈前统一动作：极性快照 + 锚点入池。

        ★ A1 根因：`_anchor_round` 原来只挂在 `_run_layer`（serial 通道）
          里。B/C/D-H 七个模式走的是 `_run_one_round_B` 等入口，它们只调
          `_print_polarity_snapshot`、不调 `_anchor_round` —— 于是**非
          serial 模式下锚点池恒为空**，`pooled` 永远是 0，收尾对照拿不到
          锚点。改前实测：全源码 `self._anchor_round(` 只有 1 处调用点，
          `_before_round` 0 处；`_run_one_round_B` 函数体含
          `_print_polarity_snapshot` 但不含 `_anchor_round`。

        做成一个方法而不是在两处各写一份，是为了防止这个坑再出现
        第十次（本项目「同一条逻辑两条通道各写一份」已发生过 7 次以上）。

        `layer_no` 是 **1-based**（调用方传圈号），`_anchor_round` 收
        **0-based**，这里做 -1 转换。
        """
        self._print_polarity_snapshot(pool, entry, layer_no)
        self._anchor_round(entry, pool, layer_no - 1)

    def _check_structure_saturation(
            self, new_amps: List[str],
            recent_amps: List[str]) -> Optional[bool]:
        if not new_amps:
            return None

        new_text = "\n".join(f"  N{i+1}. {d[:120]}"
                              for i, d in enumerate(new_amps[:8]))
        recent_text = "\n".join(f"  R{i+1}. {d[:120]}"
                                 for i, d in enumerate(recent_amps[:15])) \
            or "  （无）"

        system = (
            "你是【结构饱和度检查者】。\n"
            "\n"
            "本次运行的研究螺旋每圈会产出若干「& 印记」——\n"
            "撞不动、不可通约的结构。问题是：这些 & 会不会\n"
            "在若干圈后只是在换措辞重复同一个结构，而不产生新东西。\n"
            "\n"
            "【你的任务】\n"
            "判断本圈新增的 & 是否引入了**新的结构维度**。\n"
            "\n"
            "【判断标准】\n"
            "- 新维度 = 引入了之前没有的区分轴、新的关系类型、\n"
            "  新的对象类别。例如：从「执行链」跳到「责任链」，\n"
            "  从「记录位」跳到「写序位」，这是新维度。\n"
            "- 换措辞 = 同一结构轴上的重新表达、同义重命名、\n"
            "  细节展开、举例补充。例如：「认领者缺位」和\n"
            "  「写序分配者缺位」如果都在讲同一个空位，是同维度。\n"
            "\n"
            "【严格 JSON】\n"
            "{\n"
            '  "new_dimension": true|false,\n'
            '  "reason": "<=60字，说明判断理由",\n'
            '  "shared_axes": ["与新 & 重叠的已有结构轴，<=3条"]\n'
            "}\n"
        )
        user = (
            f"【本圈新 &（{len(new_amps)} 条）】\n{new_text}\n\n"
            f"【池内已有 &（{len(recent_amps)} 条）】\n{recent_text}"
        )

        try:
            raw = self.llm.call(system, user, 0.2, 500, json_mode=True, stage=_thinking_stage(self.config, 'check_structure_saturation'))
        except Exception as e:
            logger.warning("结构饱和度检查失败: %s", e)
            return None

        data = self.llm.parse_json(raw) or {}
        nd = data.get("new_dimension")
        if isinstance(nd, bool):
            reason = str(data.get("reason", ""))[:200]
            self.vp(f"   🧭 结构饱和度判断："
                    f"{'有新维度' if nd else '无新维度'}（{reason}）")
            return nd
        return None

    def _update_trackers(self, view: View, layer_no: int,
                         cov_before: Optional[float],
                         cov: Optional[float]) -> None:
        if self.dec_tracker is None or self.und_tracker is None:
            return
        if not hasattr(self, "_dec_conv_streak"):
            self._dec_conv_streak = 0
        if not hasattr(self, "_und_conv_streak"):
            self._und_conv_streak = 0
        conv_window = int(self.config.get("spiral", {}).get(
            "convergence_window", 2))
        _subs1 = list(self.pools["1"].sub_questions or [])
        dec_n = sum(1 for s in _subs1
                    if s.get("decidability") in _DEC_ANSWERABLE)
        if not hasattr(self, "_dec_n_last"):
            self._dec_n_last = None
        _denom_changed = (self._dec_n_last is not None
                          and dec_n != self._dec_n_last)
        effective_cov = cov if cov is not None else cov_before
        if effective_cov is not None:
            answered = sum(1 for s in _subs1
                           if s.get("decidability") in _DEC_ANSWERABLE
                           and s.get("status") == "answered")
            if _denom_changed:
                # 只记账不判定：把基线挪到新比值上，streak 清零
                self._dec_conv_streak = 0
                self.dec_tracker.note_rebaseline(effective_cov)
                self.vp(f"   📊 可判定分母变了"
                        f"（可判定子问题 {self._dec_n_last}→{dec_n} 条），"
                        f"覆盖率基线重置为 {effective_cov:.0%}"
                        f"（比值不可比，不计停滞）")
            else:
                self.dec_tracker.update_decidable(effective_cov, answered)
                if effective_cov >= _TRACKER_COVERAGE:
                    self._dec_conv_streak += 1
                else:
                    self._dec_conv_streak = 0
                if (self._dec_conv_streak >= conv_window
                        and not self.dec_tracker.converged):
                    self.dec_tracker.mark_converged(layer_no)
                    self.vp(f"   📗 可判定通道收敛"
                            f"（第 {layer_no} 圈，"
                            f"cov={effective_cov:.0%}，"
                            f"连续 {self._dec_conv_streak} 圈）")
        self._dec_n_last = dec_n
        if view.undecidable_product:
            und_clarity = float(
                view.undecidable_product.get("clarity", 0.0) or 0.0)
            und_amps = list(
                view.undecidable_product.get("structural_amps") or [])
        else:
            und_clarity = 0.0
            und_amps = []
        struct_cov = (self.pools["1"].undecidable_channel
                      .get("last_struct_coverage"))
        self.und_tracker.update_undecidable(
            und_amps, und_clarity, struct_cov)
        if len(und_amps) >= 2 and und_clarity >= _TRACKER_CLARITY:
            self._und_conv_streak += 1
        else:
            self._und_conv_streak = 0
        if (self._und_conv_streak >= conv_window
                and not self.und_tracker.converged):
            self.und_tracker.mark_converged(layer_no)
            self.vp(f"   📘 不可判定通道收敛（第 {layer_no} 圈，"
                    f"连续 {self._und_conv_streak} 圈）")
        if struct_cov is not None:
            ch = self.pools["1"].undecidable_channel
            n_hit = ch.get("last_struct_hit", 0)
            n_aspects = len(ch.get("und_aspects", []))
            n_indep = len(ch.get("structural_amps", []))
            n_aligned = len(ch.get("aligned_amps", []))
            _iratio = ch.get("last_indep_ratio")
            if "indep_history" not in ch:
                # 历史 packed 重渲染：只认旧口径，别硬套新名。
                self.vp(f"   📘 不可判定结构覆盖率 {struct_cov:.0%}"
                        f"（旧口径 {n_hit}/{n_aspects} und_aspects 命中）")
            elif _iratio is None:
                self.vp("   📘 不可判定独立度 —（无独立结构，不可计算）")
            else:
                self.vp(f"   📘 不可判定独立度 {_iratio:.0%}"
                        f"（{int(ch.get('last_indep_free', 0) or 0)}"
                        f"/{n_indep} 条独立结构不与 und_aspects 重合；"
                        f"不是覆盖率）")
            _acov = ch.get("last_aligned_coverage")
            if _acov is not None:
                self.vp(f"   📘 不可判定对齐覆盖率 {_acov:.0%}"
                        f"（{int(ch.get('last_aligned_hit', 0) or 0)}"
                        f"/{n_aspects} und_aspects 命中）")
            _scv = ch.get("last_sc_ratio")
            if "sc_history" in ch:
                if _scv is None:
                    self.vp("   📘 不可判定结构覆盖率 "
                            "—（无结构，不可计算）")
                else:
                    self.vp(f"   📘 不可判定结构覆盖率 {_scv:.0%}"
                            f"（{int(ch.get('last_sc_touched', 0) or 0)}"
                            f"/{int(ch.get('last_sc_pool', 0) or 0)}"
                            f" 条结构被后续圈再次触及）")
            self.vp(f"      ↳ 独立结构 {n_indep} 条（独立度分母），"
                    f"对齐结构 {n_aligned} 条（计入对齐覆盖率）")
        if self.und_tracker.needs_recheck:
            self.vp("   ⚠️ 不可判定通道已收敛但停滞"
                    "（结构连续为空 + clarity 下降）")

    def _re_evaluate_pool(self, entry: str, pool: Pool,
                          layer: int) -> Optional[Tuple[int, List[dict]]]:
        if entry not in _ENTRIES:
            return None
        k = int(self.config.get("spiral", {}).get("re_eval_recent_k", 10))
        items: List[Tuple[str, dict]] = []
        for it in pool.amps[-k:]:
            items.append(("amp", it))
        for it in pool.threads[-k:]:
            items.append(("thread", it))
        if not items:
            return None

        lines = "\n".join(
            f"{n+1}. [{'&' if kind == 'amp' else '线头'}] "
            f"{it.get('desc', '')}（当前极性：{it.get('polarity') or '未标'}）"
            for n, (kind, it) in enumerate(items))
        system = (
            "你是【极性重估者】。\n"
            "对每条 & 或线头，重新判断它在这个问题里偏向哪一侧：\n"
            "  0 = 未显 / 悬空 / 还没成形\n"
            "  1 = 已显 / 已成立 / 已经确定\n"
            "  both = 两端都撑得住，看不出偏向\n"
            "同时给 why（≤20字）：这条为什么判成这个极性。\n"
            "严格 JSON：\n"
            '{"revals":[{"idx":1,"polarity":"0|1|both","why":"≤20字"}]}\n'
            + ANTI_PRETTY
        )
        try:
            raw = self.llm.call(system, lines, 0.3, 900, json_mode=True,
                                stage="re_evaluate_pool")
            data = self.llm.parse_json(raw) or {}
        except Exception as e:
            logger.warning("极性重估失败: %s", e)
            return (-1, [])

        changed = 0
        details: List[dict] = []
        for r in (data.get("revals") or []):
            if not isinstance(r, dict):
                continue
            try:
                idx = int(r.get("idx")) - 1
            except (TypeError, ValueError):
                continue
            if idx < 0 or idx >= len(items):
                continue
            p = str(r.get("polarity", "")).lower()
            if p not in ("0", "1", "both"):
                continue
            _kind, it = items[idx]
            why = str(r.get("why", "")).strip()[:80]
            if why:
                it["polarity_why"] = why
            old_pol = str(it.get("polarity", "?"))
            if old_pol != p:
                it["polarity"] = p
                changed += 1
                details.append({
                    "idx": idx + 1,
                    "old": old_pol,
                    "new": p,
                    "desc": str(it.get("desc", ""))[:60],
                    "why": why,
                })
        return (changed, details)

    def _settle_research(self, layer: int) -> dict:
        pool = self.pools["1"]
        left = [d for d in pool.deferrals if d["status"] == "deferred"]
        if not left:
            return {"clean": True, "leftover": 0}

        items = "\n".join(
            f"  - [{d['id']}] 子问题[{d.get('sub_id')}] {d.get('sub_question', '')}\n"
            f"      延迟理由：{d.get('reason', '')}\n"
            f"      回访条件：{d.get('revisit_condition', '')}"
            for d in left)
        system = (
            "你是【研究 · 终局清算】。\n"
            "研究螺旋已经停止，下面这些「延迟债务」必须逐条给出交代，三选一：\n"
            "  handled   现在清偿它（写怎么清偿）\n"
            "  escalated 它其实不可判定，升级为不可判定（写为什么）\n"
            "  dropped   放弃它，如实写放弃理由\n"
            "不能留「以后再说」。逐条给，不要漏。\n"
            "严格 JSON：\n"
            '{"settlements":[{"deferral_id":"d_001","decision":"handled|escalated|dropped",'
            '"reason":"≤40字"}]}\n'
            + ANTI_PRETTY
        )
        decided = {}
        try:
            raw = self.llm.call(
                system, "【待清算的延迟债务】\n" + items, 0.4, 1500,
                json_mode=True, stage=_thinking_stage(self.config, 'settle_research'))
            data = self.llm.parse_json(raw) or {}
        except Exception as e:
            logger.warning("终局清算 LLM 调用失败，回退确定性兜底: %s", e)
            return settle_deferrals(pool, layer)
        for s in (data.get("settlements") or []):
            if not isinstance(s, dict):
                continue
            did = str(s.get("deferral_id", "")).strip()
            dec = str(s.get("decision", "")).strip().lower()
            if dec not in ("handled", "escalated", "dropped"):
                continue
            decided[did] = (dec, str(s.get("reason", "")).strip()[:200])

        for d in left:
            if d["id"] not in decided:
                continue
            dec, reason = decided[d["id"]]
            if dec == "handled":
                d["status"] = "handled"
            elif dec == "escalated":
                d["status"] = "escalated"
                for sq in pool.sub_questions:
                    if sq.get("id") == d.get("sub_id"):
                        sq["decidability"] = "undecidable"
                        break
            else:
                d["status"] = "dropped"
            d["resolved_at"] = layer
            d["resolution_reason"] = reason or (
                "已清偿" if dec == "handled" else "终局清算")

        leftover = sum(1 for d in pool.deferrals if d["status"] == "deferred")
        return {"clean": leftover == 0, "leftover": leftover}

    def _settle_meta(self) -> dict:
        thr = float(self.config.get("spiral", {})
                    .get("meta_cover_similarity", 0.6))
        duel = [s for s in self.pools["both"].duel_suspensions
                if s.get("status") in ("active", "stable")]
        _all_duel = list(self.pools["both"].duel_suspensions or [])
        _closed = len(_all_duel) - len(duel)
        if not duel:
            return {"clean": True, "unsettled": 0, "total": 0,
                    "uncovered": [], "closed": _closed,
                    "duel_total": len(_all_duel),
                    "by_id": 0, "covered_ids": 0,
                    "by_id_inactive": 0, "by_id_unknown": 0}

        adjudicated = [str(e.get("target", "")).strip()
                       for e in self.pools["all"].engagements]
        suspended = [str(x.get("target", "")).strip()
                     for x in self.pools["all"].suspensions
                     if x.get("status") in ("active", "stable")]

        _covered_ids = set()
        for e in self.pools["all"].engagements:
            _tid = str(e.get("tension_id", "") or "").strip()
            if _tid:
                _covered_ids.add(_tid)
        for x in self.pools["all"].suspensions:
            if x.get("status") not in ("active", "stable"):
                continue
            _tid = str(x.get("tension_id", "") or "").strip()
            if _tid:
                _covered_ids.add(_tid)

        _all_duel_ids = {str(s2.get("id", "") or "").strip()
                         for s2 in _all_duel if s2.get("id")}
        _all_duel_ids.discard("")
        by_id = len(_covered_ids & _all_duel_ids)

        uncovered = []
        for s in duel:
            t = str(s.get("target", "")).strip()
            if not t:
                continue
            sid = str(s.get("id", "") or "").strip()
            if sid and sid in _covered_ids:
                continue
            if any(_similar(t, a, thr) for a in adjudicated if a):
                continue
            if any(_similar(t, x, thr) for x in suspended if x):
                continue
            uncovered.append(t)
        _all_tids = _all_duel_ids
        _active_tids = {str(x.get("id", "") or "").strip()
                        for x in duel if x.get("id")}
        _inactive = {x for x in _covered_ids
                     if x in _all_tids and x not in _active_tids}
        _unknown = {x for x in _covered_ids if x not in _all_tids}
        return {"clean": not uncovered, "unsettled": len(uncovered),
                "total": len(duel), "uncovered": uncovered,
                "closed": _closed, "duel_total": len(_all_duel),
                "by_id": by_id, "covered_ids": len(_covered_ids),
                "by_id_inactive": len(_inactive),
                "by_id_unknown": len(_unknown)}

    def _totalize_all_pool(self):
        dst = self.pools["all"]
        for k in ("0", "1", "both"):
            src = self.pools[k]
            for a in src.amps:
                if not any(_similar(a.get("desc", ""), x.get("desc", ""), 0.9)
                           for x in dst.amps):
                    dst.amps.append(a)
            for t in src.threads:
                if not any(_similar(t.get("desc", ""), x.get("desc", ""), 0.9)
                           for x in dst.threads):
                    dst.threads.append(t)
            for p in src.probes:
                q = str(p.get("question", "")).strip()
                if q and not any(_similar(q, x.get("question", ""), 0.9)
                                 for x in dst.probes):
                    dst.probes.append(p)
            for s in src.suspensions:
                tgt = str(s.get("target", "")).strip()
                if tgt and not any(_similar(tgt, x.get("target", ""), 0.85)
                                   for x in dst.suspensions):
                    dst.suspensions.append(s)
            for d in src.deferrals:
                sq = str(d.get("sub_question", "")).strip()
                if sq and not any(_similar(sq, x.get("sub_question", ""), 0.85)
                                  for x in dst.deferrals):
                    dst.deferrals.append(d)
            for e in src.escalations:
                if not any(x.get("sub_id") == e.get("sub_id")
                           for x in dst.escalations):
                    dst.escalations.append(e)
            for ent in (getattr(src, "decidability_log", None) or []):
                _key = (ent.get("layer"), ent.get("sub_id"), ent.get("to"))
                if not any((x.get("layer"), x.get("sub_id"), x.get("to")) == _key
                           for x in dst.decidability_log):
                    dst.decidability_log.append(ent)
            for s in src.duel_suspensions:
                tgt = str(s.get("target", "")).strip()
                if tgt and not any(_similar(tgt, x.get("target", ""), 0.85)
                                   for x in dst.duel_suspensions):
                    dst.duel_suspensions.append(s)
            for e in src.engagements:
                tgt = str(e.get("target", "")).strip()
                if tgt and not any(_similar(tgt, x.get("target", ""), 0.85)
                                   for x in dst.engagements):
                    dst.engagements.append(e)

    @staticmethod
    def _apply_keep(pool: Pool, mode: str):
        mode = (mode or "all").strip()
        if mode in ("all", ""):
            return
        if mode == "none":
            pool.amps.clear()
            pool.threads.clear()
            pool.probes.clear()
            pool.meta.clear()
            pool.suspensions.clear()
            pool.deferrals.clear()
            pool.duel_suspensions.clear()
            pool.engagements.clear()
            pool.duel_alignment.clear()
            return

        ALL = "ALL"
        mentioned = set()
        want: Dict[str, object] = {}
        for piece in mode.split("+"):
            cls, _, ids = piece.strip().partition(":")
            cls = cls.strip()
            if cls not in ("amps", "threads", "probes", "meta",
                           "suspensions", "deferrals", "duel_suspensions"):
                logger.warning("keep：未知类别 %r，忽略这一段", cls)
                continue
            mentioned.add(cls)
            sel = set()
            for chunk in ids.split("|"):
                chunk = chunk.strip()
                if not chunk:
                    continue
                try:
                    sel.add(int(chunk) - 1)
                except ValueError:
                    logger.warning("keep：索引 %r 不是数字，忽略", chunk)
            if sel:
                cur = want.get(cls)
                if isinstance(cur, set):
                    cur |= sel
                elif cur != ALL:
                    want[cls] = sel
            else:
                want[cls] = ALL

        for cls, store in (("amps", pool.amps), ("threads", pool.threads),
                           ("probes", pool.probes), ("meta", pool.meta),
                           ("suspensions", pool.suspensions),
                           ("deferrals", pool.deferrals),
                           ("duel_suspensions", pool.duel_suspensions)):
            if cls not in mentioned:
                store.clear()
                continue
            w = want.get(cls, ALL)
            if w == ALL:
                continue
            store[:] = [x for i, x in enumerate(store) if i in w]

    def _rounds_plan(self, rounds):
        hard = int(self.config.get("spiral", {}).get("hard_max", 6))
        per = {}
        # ★ [预算 bandit] 仅当 `auto.bandit.enabled=true` 时，向「每层默认圈数」
        #   注入一个**建议上限**（仍会被后续 floor/ceil 钳制）。默认关 ⇒ 无影响。
        _b_rounds = None
        if getattr(self, "_bandit_enabled", False) and \
                getattr(self, "_bandit", None) is not None:
            try:
                _pk = self._bandit.pick()
                self._bandit_pick = _pk
                _b_rounds = int((_pk.get("arm") or {}).get("rounds") or 0) or None
                self.vp("\n🎰 预算 bandit：建议每层上限 %s 圈"
                        "（%s；scores=%s）"
                        % (_b_rounds,
                           "探索" if _pk.get("explore") else "利用",
                           _pk.get("scores")))
            except Exception:
                _b_rounds = None
        if isinstance(rounds, str):
            rounds = _normalize_punct(rounds)
        if isinstance(rounds, dict):
            for k, v in rounds.items():
                if k in _ENTRIES:
                    per[k] = max(1, int(v or 0) or hard)
        elif isinstance(rounds, str) and (":" in rounds or "," in rounds):
            for part in rounds.split(","):
                part = part.strip()
                if not part:
                    continue
                k, _, v = part.partition(":")
                k = k.strip()
                v = v.strip()
                if not v:
                    m = re.match(r"^([a-zA-Z]+)(\d+)$", k)
                    if m:
                        k, v = m.group(1), m.group(2)
                if k in _ENTRIES:
                    try:
                        per[k] = max(1, int(v or 0) or hard)
                    except (TypeError, ValueError):
                        self.vp(f"   ⚠️ 圈数段 {part!r} 的值不是整数，忽略")
                else:
                    self.vp(f"   ⚠️ 圈数段 {part!r} 的入口 {k!r} 未知，忽略")
        else:
            n = int(rounds or 0)
            if n > 0:
                per = {e: n for e in _ENTRIES}

        min_rounds = (self.config.get("spiral") or {}).get("min_rounds") or {}
        _med = None
        if per:
            _vs = sorted(per.values())
            _med = _vs[len(_vs) // 2]
        out = {}
        for e in _ENTRIES:
            if e in per:
                out[e] = per[e]
                continue
            if _med:
                _floor = min(_MIN_LAYER_ROUNDS, hard)
                out[e] = min(max(_med, _floor),
                             _layer_ceil(e, hard, _floor))
                continue
            _cap = int(_spiral_for(self.config, e).get("hard_max", hard))
            _floor = int(min_rounds.get(e, 0) or 0)
            out[e] = max(_cap, _floor)
        if _med is not None:
            _filled = [e for e in _ENTRIES if e not in per]
            if _filled:
                self.vp(f"   ⚠️ 圈数只指定了 {sorted(per)}，"
                        f"{'/'.join(_filled)} 按已给值的中位数 {_med} 补 "
                        f"（不用 hard_max，否则这层会白跑到 {hard} 圈）")
        return out

    def _plan_dispatch(self, route):
        order, skipped, done = [], [], []
        for e in route:
            if e not in _ENTRIES:
                skipped.append({"entry": e,
                                "reason": f"未知入口（只有 {', '.join(_ENTRIES)}）"})
                continue
            miss = [d for d in _ENTRY_DEPS.get(e, ()) if d not in done]
            if miss:
                skipped.append({"entry": e,
                                "reason": f"上游 {','.join(miss)} 在调度顺序里排在它之后"})
                continue
            need = _ENTRY_MIN_UPSTREAM.get(e, 0)
            if need and len(done) < need:
                skipped.append({"entry": e,
                                "reason": f"需要至少 {need} 个上游 view，"
                                          f"当前只有 {len(done)} 个"})
                continue
            order.append(e)
            done.append(e)
        return {"requested": list(route), "order": order, "skipped": skipped}


    def _planned_active(self, route) -> List[str]:
        """本次真正要跑的层 = **请求计划里的 order**。

        ★ 原来四条并行路径各自写 `[e for e in route if e in _ENTRIES]`
        —— 只看 route，于是：计划里因「依赖不满足 / 顺序不合法」被判跳过
        的层，并行模式照样会跑；而 `_dispatch_for_pack` 是以计划为基准的，
        两边对不上，**缺层就报不准**。统一取计划 order，与串行同源
        （串行本来就走 `dispatch["order"]`）。
        """
        plan = getattr(self, "_dispatch_plan", None) or {}
        order = [e for e in (plan.get("order") or []) if e in _ENTRIES]
        if order:
            return order
        return [e for e in (route or []) if e in _ENTRIES]

    def _dispatch_for_pack(self, mode: str, extra: Optional[dict] = None) -> dict:
        """打包用的 dispatch。计划是基准，实际结果另记在 ran/missing/failed。

        ★ `missing` 的定义要小心：失败层会留一个**占位 View**（在场但不可用），
        所以只判「在不在 `_results` 里」**判不出缺层** —— 必须把失败层也算进去。
        否则守卫会被自己留的占位骗过去（我第一版就是这么写错的）。
        """
        plan = getattr(self, "_dispatch_plan", None) or {}
        order = list(plan.get("order") or [])
        failed = dict(getattr(self, "_failed_layers", None) or {})
        out = {
            "requested": list(plan.get("requested") or []),
            "order": order,                    # 计划顺序（不再随完成序变化）
            "ran": [e for e in order
                    if e in self._results and e not in failed],
            "missing": [e for e in order
                        if e not in self._results or e in failed],
            "failed": failed,
            "skipped": list(plan.get("skipped") or []),
            "_parallel_mode": mode,
        }
        if extra:
            out.update(extra)
        return out

    def _note_layer_failure(self, entry: str, exc: BaseException) -> str:
        """记下某层失败。**必须被记下来**——只写日志等于静默。"""
        if not hasattr(self, "_failed_layers"):
            self._failed_layers = {}
        reason = f"{type(exc).__name__}: {exc}"
        self._failed_layers[entry] = reason
        return reason

    def _failed_layer_view(self, entry: str, reason: str) -> "View":
        """失败层的占位 View。

        ★ 为什么造一个假的：留 `None` 就等于该层从 views/pools/self 段
        **整层消失**，而下游与读者都看不出。占位 View 是「**在场但不可用**」
        ——`_view_usable()` 对「有 errors 且无 manifest」返回 False，
        所以它既不会被当成上游骗下游，又能在产物里被看见。
        A 模式早就这么做了，这里把 B/C/D-H 对齐过来。
        """
        return View(entry=entry, errors=[f"该层失败：{reason}"])

    def _layer_guard(self, packed: dict) -> None:
        """跑完后核对：**计划的层**是不是都在。缺了就大声说，不许静默。"""
        disp = packed.get("dispatch") or {}
        missing = list(disp.get("missing") or [])
        skipped = list(disp.get("skipped") or [])
        if skipped:
            self.vp(f"\n{'!'*60}\n⚠️ 调度跳过（未产出，原因如实记下）")
            for sk in skipped:
                self.vp(f"   · {_LAYER_LABEL.get(sk.get('entry'), sk.get('entry'))}"
                        f"：{sk.get('reason', '')}")
        if missing:
            self.vp(f"\n{'!'*60}")
            self.vp("❌ 缺层：请求了但这些层没有产出 —— 这份产物是不完整的")
            for e in missing:
                why = (disp.get("failed") or {}).get(e) or "未记录原因（这是缺陷）"
                self.vp(f"   · {_LAYER_LABEL.get(e, e)}：{why}")
            self.vp(f"{'!'*60}")
            packed["layer_gap"] = {
                "missing": missing,
                "failed": dict(disp.get("failed") or {}),
                "requested": list(disp.get("requested") or []),
            }

    def _context_if_on(self) -> str:
        if "context" not in self.channels:
            return ""
        return MemoryChannel.context_of(self._results, self.pools, self._mcfg)

    @staticmethod
    def _check_uncovered_directions(view: View) -> List[str]:
        untouched = [
            u for u in (view.untouched or [])
            if u.get("source") == "judge"
            and str(u.get("desc", "")).strip()
        ]
        if not untouched:
            return []
        covered: set = set()
        probes = view.probes or []
        for p in probes:
            for c in (p.get("covers") or []):
                c_str = str(c).strip()
                if not c_str:
                    continue
                m = re.match(r"^T?(\d+)$", c_str)
                if m:
                    idx = int(m.group(1)) - 1
                    if 0 <= idx < len(untouched):
                        covered.add(idx)
                else:
                    for i, u in enumerate(untouched):
                        if _similar(c_str, u.get("desc", ""), 0.7):
                            covered.add(i)
            q = str(p.get("question", "")).strip()
            if q:
                for i, u in enumerate(untouched):
                    if _similar(q, u.get("desc", ""), 0.6):
                        covered.add(i)
        missing = []
        for i, u in enumerate(untouched):
            if i not in covered:
                missing.append(str(u.get("desc", ""))[:60])
        return missing

    def _uncovered_gate(self, view: View, stop_reasons: List[str],
                        uncovered_streak: int, prev_missed_n,
                        is_last_round: bool, sp: dict) -> tuple:
        """[fix-88b 收口] 有「没深入的方向」时，该不该推迟这次停止。

        返回值：(stop_reasons, uncovered_streak, prev_missed_n, deferred_note)
        deferred_note 非空 = 这次真的把停止理由推迟掉了，内容是理由原文。

        [v1.21.57] 原来这段在 _run_layer 和 _run_one_round_B 里各写一份，
        而且有两处不诚实，都是被「19 次体力耗尽 vs 1 次真停止」这个比例
        查出来的：
          1) **最后一圈推迟停止毫无意义**：for 循环本来就要结束，推迟买
             不到下一圈，只是把理由丢掉。实测 balanced 那 3 次推迟**全部**
             落在各层最后一圈，drift 的 2 次里也有 1 次。
          2) 被丢掉的理由**不留痕**，于是收尾永远写「体力耗尽（…
             未触发任何停止判据）」——那些圈里这句话是**假的**，
             判据触发了、只是被推迟。（与 P0-1 同一类病：停止理由名实不符。）
        另外：没有上一次测量时（prev_missed_n is None）不再说「减少中」，
        那只是「首次」，无从判断趋势。
        """
        missed = self._check_uncovered_directions(view)
        n = len(missed)
        if not missed:
            return stop_reasons, 0, None, ""

        if int(sp.get("no_push_when_idle", 1)) and any(
                ("层内空转" in str(r)) or ("有新增但无推进" in str(r))
                for r in (stop_reasons or [])):
            if getattr(self, "verbose", False):
                print(f"   ⚠️ [fix-88b] 有 {n} 条未深入方向，但停止判据是"
                      f"空转类（再给一圈也消化不掉），不推迟")
            return stop_reasons, uncovered_streak, n, ""

        uncovered_streak += 1
        max_push = int(sp.get("max_uncovered_pushes", 1))
        first_time = prev_missed_n is None
        decreasing = True if first_time else (n < prev_missed_n)
        within_budget = uncovered_streak <= max_push
        if within_budget and decreasing and not is_last_round:
            if getattr(self, "verbose", False):
                _trend = "首次" if first_time else f"{prev_missed_n}→{n}"
                print(f"   ⚠️ [fix-88b] {n} 条未深入方向"
                      f"（{_trend}，第 {uncovered_streak}/{max_push} 次），"
                      f"推迟停止")
                for _m in missed[:3]:
                    print(f"      · {_m}")
            note = " + ".join(str(r) for r in stop_reasons) if stop_reasons else ""
            return [], uncovered_streak, n, note
        why = []
        if not within_budget:
            # max_uncovered_pushes=0 是「一次都不推迟」的合法配置，
            # 这时说「已达上限 0」读着别扭，如实说成本意。
            if max_push <= 0:
                why.append("配置为不推迟（max_uncovered_pushes=0）")
            else:
                why.append(f"已达上限 {max_push}")
        if not decreasing:
            why.append(f"方向数未减少（{prev_missed_n}→{n}）")
        if is_last_round:
            why.append("已是最后一圈，没有下一圈可推")
        if getattr(self, "verbose", False):
            print(f"   ⚠️ [fix-88b] 未深入方向 {n} 条，放行停止"
                  f"（{chr(59).join(why)}）")
        return stop_reasons, uncovered_streak, n, ""

    @staticmethod
    def _has_pool_content_view(view: Optional[View]) -> bool:
        if not view:
            return False
        if view.probes or view.amps or view.suspensions or view.threads or view.meta:
            return True
        if view.candidates or view.collision:
            return True
        return False

    #: 自动分派**可达**的模式：只放「规则判得出、且历史上真被选中过」的。
    #: ★ 6 个 stage 模式（A/D/E/F/G/H）**不进自动分派** —— 近 80 份产物
    #:   零命中（实测：serial 71 / B 6 / C 1 / 其余 0），而它们每个都要
    #:   多一次 LLM 调用才可能选中。它们仍可**显式** `--parallel X` 到达。
    _AUTO_REACHABLE_MODES = ("serial", "B", "C")

    def _mode_rule(self, question: str):
        """规则优先的模式判断（薄壳）：唯一实现在模块级 `mode_rule`。

        ★ 下沉原因（本版冒烟 v1235 [1d] 抓出的真分叉）：规则层只接在
          本方法上时，`plan_resources` / `auto_plan(llm=...)` 两处分派
          不走规则 ⇒ 同一问题三处模式决策不一致。规则逻辑必须**一份
          实现、三处接线**（本项目「同一条逻辑两条通道各写一份」老坑）。
        """
        return mode_rule(question)

    def _decide_parallel_mode(self, question: str) -> dict:
        q = question or ""
        _m, _r = self._mode_rule(q)
        if _m:
            self.vp(f"\n🧵 并行模式（规则）：{_m}（{_r}）")
            return {"mode": _m, "reason": _r, "confidence": 0.9,
                    "source": "rule"}
        feats = {
            "len": len(q),
            "multi_clause": (q.count("，") + q.count(",")) >= 3,
            "has_and": ("和" in q) or ("与" in q),
            "has_or": ("或" in q) or ("还是" in q),
            "has_how": ("如何" in q) or ("怎样" in q) or ("怎么" in q),
            "has_what": ("是什么" in q) or ("为什么" in q),
        }
        system = (
            "你是【并行模式调度者】。给定一个问题，判断它适合哪种\n"
            "DGTF 执行模式。\n\n"
            "【serial · 严格串行】\n"
            "  0→1→both→all 严格按序。\n"
            "  适合：结构清晰、层间依赖强、需要深度而非吞吐。\n\n"
            "【A · 独立并行】\n"
            "  四层都从原问题出发，互不依赖，最后汇流。\n"
            "  适合：多义、多维、多视角并置，每层能独立产出。\n\n"
            "【B · 轮次并行】\n"
            "  四层每圈 barrier，both/all 读上一圈 0/1。\n"
            "  适合：开放、层次不分明、需要震荡收敛。\n\n"
            "【C · 流水线并行】\n"
            "  每层不等上游跑完，只等上游交出第一圈就出发，\n"
            "  之后各跑各的，每圈读当下最新的上游。\n"
            "  适合：层间有接力关系但不需要互相等待校准；\n"
            "        想尽量压缩总时长，能接受结果带时序依赖。\n\n"
            "【D · 双起并行 + 撞元并行】\n"
            "  修行/研究同时出发各跑完所有圈 → 对撞起跑 →\n"
            "  对撞交出第一圈后元层跟上，对撞/元层并行收尾。\n"
            "  适合：修行与研究互不相干，真正的交汇点在对撞。\n\n"
            "【E · 双起并行 + 撞元串行】\n"
            "  修行/研究同时出发各跑完 → 对撞跑完 → 元层才起。\n"
            "  适合：同上，但元层必须对着**完整**的对撞结果清算。\n\n"
            "【F · 修行先行 + 全流水】\n"
            "  修行跑完 → 研究起，研究出一圈后对撞跟上，\n"
            "  对撞出一圈后元层跟上。\n"
            "  适合：修行是地基，后三层能边跑边接力。\n\n"
            "【G · 修行先行 + 撞毕收元】\n"
            "  修行跑完 → 研究起 → 对撞跟上 → 对撞跑完元层才起。\n"
            "  适合：要元层清算完整对撞结果，不接受中间态。\n\n"
            "【H · 逐层接力 + 撞元并行】\n"
            "  修行跑完 → 研究跑完 → 对撞起 → 对撞出一圈后元层跟上。\n"
            "  适合：研究要吃完整修行、对撞要吃完整研究。\n\n"
            "【启发】\n"
            "- 明确单一问题 → serial\n"
            "- 多分句/并列 → A\n"
            "- 含'或/还是'、过程性 → B\n"
            "- 层界清楚、只想快、能接受时序依赖 → C\n"
            "- 修行与研究互不依赖、对撞才是交汇点 → D\n"
            "- 同上，且元层必须对最终对撞结果 → E\n"
            "- 修行是地基、后三层能接力 → F\n"
            "- 要元层清算完整对撞结果 → G\n"
            "- 研究要吃完整修行、对撞要吃完整研究 → H\n"
            "- 拿不准 → serial\n\n"
            "严格 JSON：\n"
            '{"mode":"serial|A|B|C|D|E|F|G|H",'
            '"reason":"≤80字","confidence":0.0-1.0}'
        )
        user = (
            f"【问题】\n{q}\n\n"
            f"【轻量特征】\n"
            f"  长度：{feats['len']} 字\n"
            f"  多分句：{feats['multi_clause']}\n"
            f"  含并列：{feats['has_and']}\n"
            f"  含选择：{feats['has_or']}\n"
            f"  含过程：{feats['has_how']}\n"
            f"  含定义：{feats['has_what']}\n"
        )
        try:
            raw = self.llm.call(system, user, 0.2, 400, json_mode=True, stage=_thinking_stage(self.config, 'decide_parallel_mode'))
            data = self.llm.parse_json(raw) or {}
            mode = _normalize_plan_mode(data)
            conf = _plan_conf(data)
            reason = str(data.get("reason", ""))[:200]
        except Exception as e:
            logger.warning("并行模式决策失败: %s", e)
            return {"mode": "serial", "reason": "决策失败，退回保守",
                    "confidence": 0.0}
        if mode != "serial" and conf < _PARALLEL_CONF_MIN:
            return {"mode": "serial",
                    "reason": f"低置信({conf:.2f})，退回 serial：{reason}",
                    "confidence": conf}
        return {"mode": mode, "reason": reason, "confidence": conf}

 # [AUDIT-122] **已收口**（原 pending_fix #1）：归一化抽成
    def _auto_plan(self, question: str) -> dict:
        """ 收口：唯一实现在模块级 `auto_plan`，本方法退薄壳。

        本方法不再自己实现任何调度逻辑 —— 签名与返回值形状都不变，
        `run()` 与外部脚本都不用改。

        ★ 与模块级 `auto_plan` 的关系（v1.21.71 F8 起要求写清，收口后
          更要写清）：
            · 传 `llm` → 模块级走**单调用**路径（一次定 mode + rounds），
              也就是原 `_auto_plan` 的正文，行为与 v1.21.77 逐字相同；
              对照见 `_probe_v122_phase6.py` 的 before/after 快照。
            · 不传 `llm` → 模块级走 `plan_orientation` + `plan_resources`
              两段（v1.21.62 起的对外 API 路径，仅外部脚本使用）。
        """
        return auto_plan(question, self.config, llm=self.llm)

    def _build_inp_base(self, s, role="", rno=0, entry="0", carry=None):
        # ★ [LDG 补救] 前面某层判定「职责未尽」时，其缺失的 core 问项
        #   在这里并入 carry 约束 ⇒ 后续层被**定向**提醒「这几项还没答」。
        #   对应 NAACL'25「core 子问题喂回生成器」（实测胜率 74%）；
        #   本仓库不重跑本层（不浪费预算、不掩盖），只让下游带着它走。
        _carry_all = list(carry or [])
        try:
            for _q in (getattr(self, "_duty_carry", None) or []):
                _carry_all.append({"question": str(_q)[:80],
                                   "kind": "duty_missing_core",
                                   "banned": []})
        except Exception:
            pass
        return Input(
            question=self._question,
            seed_probes=s,
            carry_constraints=_carry_all,
            key_terms=self._key_terms,
            round_role=role, round_no=rno,
            self_memory=self._self_snapshot_for(entry),
        )

    def _build_inp_duel(self, s, role="", rno=0, carry=None):
        up = []
        if self._upstream_provider is not None:
            try:
                up = list(self._upstream_provider("both") or [])
            except Exception:
                up = []
        # [fix-101] 失败占位 View 不能当上游
        up = [v for v in up if _view_usable(v)]
        if len(up) < 2:
            return Input(
                question=self._question,
                seed_probes=s, key_terms=self._key_terms,
                carry_constraints=list(carry or []),
                round_role=role, round_no=rno,
                self_memory=self._self_snapshot_for("both"),
            )
        return Input(
            upstream_views=up,
            upstream_pools=[self.pools["0"], self.pools["1"]],
            upstream_untouched=[v.untouched for v in up],
            root_question=self._question,
            seed_probes=s, key_terms=self._key_terms,
            carry_constraints=list(carry or []),
            round_role=role, round_no=rno,
            context=self._context_if_on(),
            self_memory=self._self_snapshot_for("both"),
        )

    def _build_inp_meta(self, s, role="", rno=0, carry=None):
        up = []
        if self._upstream_provider is not None:
            try:
                up = list(self._upstream_provider("all") or [])
            except Exception:
                up = []
        up = [v for v in up if _view_usable(v)]
        _pairs, _bad_entry = [], []
        for _v in up:
            _e = getattr(_v, "entry", "")
            if _e in self.pools:
                _pairs.append(_v)
            else:
                _bad_entry.append(str(_e))
        if _bad_entry:
            _note = (f"上游 view 的 entry 非法"
                     f"（{','.join(sorted(set(_bad_entry)))}）"
                     f"，已剔除 {len(_bad_entry)} 条、不参与元层配对")
            self._build_inp_dropped = _note
            logger.warning("%s", _note)
            self.vp(f"   ⚠️ {_note}")
        up = _pairs
        if not up:
            return Input(
                question=self._question,
                seed_probes=s, key_terms=self._key_terms,
                carry_constraints=list(carry or []),
                round_role=role, round_no=rno,
                self_memory=self._self_snapshot_for("all"),
            )
        return Input(
            upstream_views=up,
            upstream_pools=[self.pools[getattr(v, "entry", "0")]
                            for v in up],
            upstream_untouched=[v.untouched for v in up],
            root_question=self._question,
            seed_probes=s, key_terms=self._key_terms,
            carry_constraints=list(carry or []),
            round_role=role, round_no=rno,
            context=self._context_if_on(),
            self_memory=self._self_snapshot_for("all"),
        )

    def _budget_exhausted(self) -> bool:
        """总调用预算是否用尽（0 = 不设限）。

        ★ 与层内的自然停止判据**不是一回事**：那些判据看的是
        "这一层还在不在产出新东西"，预算看的是"这次跑一共花得起多少"。
        两者可能同时成立，也可能只有预算成立 —— 后者如果不留痕，
        产物看起来就和自然停止一样。
        """
        b = int(getattr(self, "_call_budget", 0) or 0)
        if b <= 0:
            return False
        return int(getattr(self.llm, "total_calls", 0) or 0) >= b

    def _note_budget_stop(self, where: str = "") -> None:
        """记下"因为预算而提前收尾"，并打进日志。"""
        b = int(getattr(self, "_call_budget", 0) or 0)
        used = int(getattr(self.llm, "total_calls", 0) or 0)
        self._budget_stop_note = (
            f"预算用尽（已用 {used}/{b} 次调用"
            + (f"，{where}" if where else "") + "）")
        self.vp(f"\n   ⏹ {self._budget_stop_note}，提前收尾"
                f"（不是自然停止）")

    def _run_layer(self, entry: str, n_rounds: int = 0) -> View:
        question = self._question
        key_terms = self._key_terms
        results = self._results

        uncovered_streak = 0
        _prev_missed_n: Optional[int] = None
        rephrased_streak = 0
        meta_idle_streak = 0

        sp = _spiral_for(self.config, entry)
        soft_max = int(sp.get("soft_max", 2))
        sim_thr = float(sp.get("stop_similarity", 0.8))
        stable_need = int(sp.get("stable_need", 2))
        idle_limit = int(sp.get("idle_limit", 2))
        rounds_n = max(1, int(n_rounds or 0)
                       or int(sp.get("hard_max", 6)))
        _extra_rounds = 0
        if entry == "all":
            _extra_rounds = int(sp.get("all_extra_rounds", 1))
        _total_rounds = rounds_n + _extra_rounds
        # [P2-9] 真正的圈数上限是含 all_extra_rounds 的 _total_rounds。
        # 停止理由和 md 的「上限 N 圈」以前拿的是 rounds_n（请求的圈数），
        # 元层多给一圈之后两个数不一致，产物里看着像超跑了。
        rounds_cap = _total_rounds

        # 研究层前置：问题分解
        if (entry == "1"
                and not self.pools["1"].sub_questions
                and _action_on(self.config, "decompose_question")):
            d0 = DGTF("1", self.llm, self.config)
            d0.verbose = False
            dec_src = self.config.get("actions", {}).get(
                "decompose_source", "pool")

            zero_view = self._results.get("0")
            has_zero_prod = self._has_pool_content_view(zero_view)
            self._assess_decidability_dynamic(self._question, zero_view)
            use_internal = (dec_src == "pool" and has_zero_prod)

            subs, src_label = self._research_decompose_with_web(
                question, d0, zero_view, use_internal)

            try:
                self._tri_agree, self._tri_total = \
                    self._adjudicate_sub_tristate(subs, question)
            except Exception as _e:
                logger.warning("三态判决异常，退回拆解原标签: %s", _e)
            self.pools["1"].sub_questions = subs
            if subs:
                n_dec = sum(1 for s in subs
                            if s["decidability"] == "decidable")
                n_par = sum(1 for s in subs
                            if s["decidability"] == "partial")
                n_und = sum(1 for s in subs
                            if s["decidability"] == "undecidable")
                _par = f" / 部分 {n_par}" if n_par else ""
                self.vp(f"   🧩 研究层从{src_label}分解出 {len(subs)} "
                        f"个子问题（可判定 {n_dec}{_par} / "
                        f"不可判定 {n_und}）")

        # 对撞层前置：四象限对齐
        if entry == "both" and not self.pools["both"].duel_alignment:
            with self._pool_lock:
                self.pools["both"].duel_alignment = \
                    _align_suspensions_and_deferrals(
                        self.pools["0"], self.pools["1"], sp)
            self.pools["both"].duel_alignment["consumed"] = False
            al = self.pools["both"].duel_alignment
            note = "（两侧没有同一件事可对，不是故障）" \
                if al["quality"] == "unaligned" else ""
            self.vp(f"   🧭 四象限对齐：{al['quality']}"
                    f"（匹配率 {al['match_rate']:.0%}，"
                    f"{len(al['quadrants'])} 对张力）{note}")

        seeds: List[dict] = []
        # [P2-7] 上一圈注入、这一圈要核对的硬约束
        carry_pending: List[dict] = []
        view = None
        prev_product = ""
        # [P1-6 补] 跨圈累积 view.errors —— 每圈新建 view、只 return 最后
        # 一圈，中间圈的 errors（含 deferral 被拦留痕）会随 view 丢弃。
        # 这里逐圈收集，收尾时合并回最终 view。
        _all_view_errors: List[str] = []
        idles = 0
        r_idle_limit = int(sp.get("round_idle_limit", 2))
        new_thr = float(sp.get("new_item_similarity", 0.55))
        overlap_thr = float(sp.get("new_item_overlap", 0.55))
        thread_new_thr = float(sp.get("thread_new_similarity", 0.70))
        thread_overlap_thr = float(sp.get("thread_new_overlap", 0.70))
        r_stall_limit = int(sp.get("round_stall_limit", 2))
        idle_new_amp = 0
        idle_new_thread = 0
        idle_stall = 0
        deferred_notes: List[str] = []
        carry_streak = 0
        _last_carry_banned: set = set()
        _last_unsettled = 999
        _all_settle_streak = 0
        all_candidates: List[dict] = []
        all_amps: List[dict] = []
        all_amp_cands = 0
        all_threads: List[dict] = []
        roles_hist: List[str] = []
        round_log: List[dict] = []
        all_rehashed: List[dict] = []
        all_dec_products: List[dict] = []
        all_und_products: List[dict] = []
        views_per_round: List[dict] = []
        all_expanded_descs: List[str] = []

        # [P2-7] next_role：上一圈的 carry 把这一圈的角色改成「转向/复裁」。
        # 原来这两行改的是**本圈已经用完**的 role 变量，下一圈按 r 重算，
        # 「转向」从来没进过任何一圈的 prompt。这是回流的第二个断点。
        # [P2-9] 角色排班与「carry 改写下一圈」都在 _natural_role /
        # _carry_next_role 里，这里只做取值，不再自己算一遍。
        next_role = ""
        for r in range(_total_rounds):
            # [动态提前停] 每一圈开始前先看预算。用尽就收尾，
            # 理由记进 `_budget_stop_note`，最后并进 stop_reasons
            # —— 不留痕的话，产物看着和自然停止一模一样。
            if r > 0 and self._budget_exhausted():
                self._note_budget_stop(f"本层跑到第 {r} 圈")
                break
            layer_no = r + 1
            role = self._role_for_round(r, next_role)
            next_role = ""
            if _total_rounds > 1:
                self.vp(f"\n   ↻ 第 {layer_no}/{_total_rounds} 圈 · {role}"
                        f"{'（带着上一圈 ' + str(len(seeds)) + ' 个重点）'
                           if seeds else ''}")
            pool = self.pools[entry]
            snap_amps = [str(a.get("desc", "")) for a in pool.amps]
            snap_threads = [str(t.get("desc", "")) for t in pool.threads]
            self._before_round(entry, pool, layer_no)

            if entry == "0" or entry == "1":
                inp = self._build_inp_base(seeds, role, layer_no, entry,
                                           carry_pending)
            elif entry == "both":
                inp = self._build_inp_duel(seeds, role, layer_no,
                                           carry_pending)
            else:
                inp = self._build_inp_meta(seeds, role, layer_no,
                                           carry_pending)

            inp.pool = pool
            inp.decidability_result = self.decidability_result
            inp.is_last_round = (layer_no >= _total_rounds)

            dg = DGTF(entry, self.llm, self.config)
            view = dg.run(inp)
            view.rounds_run = layer_no
            # [P1-6 补] 逐圈收集 errors（去重，保留首次出现的）
            for _err in (view.errors or []):
                if _err not in _all_view_errors:
                    _all_view_errors.append(_err)
            try:
                for _d in (getattr(view, "_expanded_descs", None)
                           or []):
                    if _d and not any(_similar(_d, x, _DUP_SIM)
                                      for x in all_expanded_descs):
                        all_expanded_descs.append(_d)
            except Exception:
                pass
            roles_hist.append(role)
            for rp in (view.rehashed or []):
                all_rehashed.append(dict(rp, round=layer_no))

            rephrased_streak, meta_idle_streak = (
                self._apply_view_to_pool(
                    view, pool, entry,
                    rephrased_streak, meta_idle_streak, layer_no))

            if carry_pending:
                view.carry_check = self._check_carry_response(
                    view, carry_pending)
                view.carry_check["round"] = layer_no
                view.carry_checks.append(dict(view.carry_check))
                _dropped_now = list(getattr(view, "carry_dropped", None)
                                    or [])
                if _dropped_now:
                    for _x in _dropped_now:
                        _y = dict(_x)
                        _y.setdefault("round", layer_no)
                        view.carry_dropped_all.append(_y)
                if view.carry_check.get("violations"):
                    pool.meta.append(
                        "[自省回流未生效] "
                        + str(view.carry_check.get("notes", ""))[:160])

            for e in (view.engagements or []):
                t = str(e.get("target", "")).strip()
                if t and not any(
                        _similar(t, x.get("target", ""), 0.85)
                        for x in self.pools[entry].engagements):
                    self.pools[entry].engagements.append(dict(e))

            if entry == "1":
                cov_before = coverage_of(self.pools[entry], sp, entry=entry)
                st = update_deferrals(
                    self.pools[entry], view, layer_no, sp,
                    web_hook=self._web_evidence_hook)
                # [P1-6 补·修] 这里**再收一次**。`dg.run` 之后那个收集点
                #   （见 `view = dg.run(inp)` 下方）只能收到 DGTF 内部
                #   产生的 errors；而 P1-6 的「deferral 被拦」是**同一圈
                #   更晚**在 update_deferrals 里写进 view.errors 的，
                #   只收前面那次 = 收不到它（真跑实测：4 圈只剩最后 1 条）。
                for _err in (view.errors or []):
                    if _err not in _all_view_errors:
                        _all_view_errors.append(_err)
                if any(st[k] for k in ("new", "handled", "escalated",
                                       "answered", "refined",
                                       "reclassified", "rejected")):
                    self.vp(f"   ⏳ 债务：新增{st['new']} 确认{st['confirmed']} "
                            f"清偿{st['handled']} 升级{st['escalated']} "
                            f"回答{st['answered']} 深入{st['refined']}")
                for _t in st.get("_transitions") or []:
                    if _t["status"] == "applied":
                        _ev = "、".join(
                            str(e.get("resolved_to"))
                            for e in (_t.get("evidence") or [])) or "—"
                        _rb = (f"，并重新挂账 {_t['reopened_debt']}"
                               if _t.get("reopened_debt") else "")
                        self.vp(f"   ↻ 可判定性转移成立：子问题[{_t['sub_id']}] "
                                f"{_DEC_STATE_CN.get(_t.get('from'), '?')}→"
                                f"{_DEC_STATE_CN.get(_t.get('to'), '?')}"
                                f"（据 {_ev}；{_t.get('reason', '')}）{_rb}")
                    else:
                        self.vp(f"   ⛔ 可判定性转移驳回：子问题[{_t['sub_id']}]"
                                f"→{_DEC_STATE_CN.get(_t.get('to'), _t.get('to'))}"
                                f"（{_t.get('why', '')}）")
                cov = coverage_of(self.pools[entry], sp, entry=entry)
                if cov is not None:
                    if (cov_before is not None
                            and abs(cov - cov_before) > 0.01):
                        self.vp(f"   📊 可判定覆盖率 {cov:.0%}"
                                f"（升级前 {cov_before:.0%}）")
                    else:
                        self.vp(f"   📊 可判定覆盖率 {cov:.0%}")
                else:
                    self.vp("   📊 可判定覆盖率 N/A")
                self._update_trackers(view, layer_no, cov_before, cov)
                _actual_deferred = [
                    d for d in self.pools["1"].deferrals
                    if d.get("status") == "deferred"]
                if _actual_deferred:
                    for _d in _actual_deferred[-3:]:
                        self.vp(f"      ⏳ 实际挂账：子问题"
                                f"[{_d.get('sub_id')}] "
                                f"（回访条件："
                                f"{_d.get('revisit_condition', '')}）")
            elif entry == "both":
                st = update_duel_suspensions(
                    self.pools[entry], view, layer_no, sp)
                if any(st[k] for k in ("new", "revoked", "resolved",
                                       "stable", "adjudicated")):
                    _sr = st.get("self_resolved", 0)
                    _sr_s = f" ⚠️自解{_sr}" if _sr else ""
                    self.vp(f"   ⚔️ 张力：裁决{st['adjudicated']} "
                            f"新增{st['new']} 确认{st['confirmed']} "
                            f"撤回{st['revoked']} 消解{st['resolved']}{_sr_s} "
                            f"转稳{st['stable']}")
            else:
                st = update_suspensions(
                    self.pools[entry], view, layer_no, sp)
                if any(st[k] for k in ("new", "revoked", "resolved", "stable")):
                    _sr = st.get("self_resolved", 0)
                    _sr_s = f" ⚠️自解{_sr}" if _sr else ""
                    self.vp(f"   ⏸ 悬置：新增{st['new']} 确认{st['confirmed']} "
                            f"撤回{st['revoked']} 解决{st['resolved']}{_sr_s} "
                            f"转稳{st['stable']}")

            # ★ [层目标] 逐圈把池的累计层面序列回填到 view（出口见 to_dict）。
            #   在 `re_evaluate_pool` **之前**：那一步可能改池，回填要贴本圈终态。
            try:
                _p0 = self.pools.get(entry)
                if _p0 is not None and getattr(_p0, "aspect_hist", None):
                    view.aspect_hist = list(_p0.aspect_hist)
            except Exception:
                pass

            if _action_on(self.config, "re_evaluate_pool"):
                re_eval_n = self._lazy_every_n(int(sp.get("re_eval_every_n", 1)))
                if re_eval_n > 0 and layer_no % re_eval_n == 0:
                    result = self._re_evaluate_pool(entry, pool, layer_no)
                    if result is None:
                        self.vp("   🔄 极性重估：不适用")
                    elif result[0] < 0:
                        self.vp("   🔄 极性重估：失败")
                    elif result[0] == 0:
                        self.vp("   🔄 极性重估：无变化")
                    else:
                        changed, details = result
                        self.vp(f"   🔄 极性重估：移动 {changed} 条")
                        for d in details:
                            self.vp(f"      [{d['old']}→{d['new']}] "
                                    f"{d['desc']}"
                                    + (f"（{d['why']}）" if d['why'] else ""))

            for c in (view.candidates or []):
                d = str(c.get("desc", "")).strip()
                if d and not any(_similar(d, str(x.get("desc", "")), 0.85)
                                 for x in all_candidates):
                    all_candidates.append(dict(c))
            for a in (view.amps or []):
                d = str(a.get("desc", "")).strip()
                if d and not any(_similar(d, str(x.get("desc", "")), 0.85)
                                 for x in all_amps):
                    all_amps.append(dict(a))
            try:
                all_amp_cands += int(getattr(view, "_amp_cand_count", 0) or 0)
            except Exception:
                pass
            for t in (view.threads or []):
                d = str(t.get("desc", "")).strip()
                if d and not any(_similar(d, str(x.get("desc", "")), 0.85)
                                 for x in all_threads):
                    all_threads.append(dict(t))
            if entry == "1":
                if view.decidable_product:
                    all_dec_products.append(dict(view.decidable_product))
                if view.undecidable_product:
                    all_und_products.append(dict(view.undecidable_product))

            recent_amps = list(snap_amps)
            recent_threads = list(snap_threads)
            cur_amps = [str(a.get("desc", "")) for a in pool.amps]
            cur_threads = [str(t.get("desc", "")) for t in pool.threads]
            added_amps = [d for d in cur_amps
                          if not any(_similar(d, x, _DUP_SIM)
                                     for x in snap_amps)]
            added_threads = [d for d in cur_threads
                             if not any(_similar(d, x, _DUP_SIM)
                                        for x in snap_threads)]

            def _is_dup(d, x):
                return (_overlap_coef(d, x) >= overlap_thr
                        or _similar(d, x, new_thr))

            def _is_dup_thread(d, x):
                return (_overlap_coef(d, x) >= thread_overlap_thr
                        or _similar(d, x, thread_new_thr))

            new_amps = [d for d in added_amps
                        if not any(_is_dup(d, x) for x in recent_amps)]
            new_threads = [d for d in added_threads
                           if not any(_is_dup_thread(d, x)
                                      for x in recent_threads)]

            acted = any(v for k, v in st.items()
                        if k not in ("confirmed", "kept", "refined"))
            if entry == "0":
                stalled = ((not new_amps and not new_threads)
                           or (bool(new_amps or new_threads)
                               and not acted))
                stall_why = "修行层无新增或无推进" if stalled else ""
            else:
                stalled = bool(new_amps or new_threads) and not acted
                stall_why = "池在长、判断没动" if stalled else ""
            idle_new_amp = 0 if new_amps else idle_new_amp + 1
            idle_new_thread = 0 if new_threads else idle_new_thread + 1
            idle_stall = idle_stall + 1 if stalled else 0
            sat_override = False
            _stall_is_sat = False

            sat_enabled = bool(sp.get("structure_saturation_enabled", True))
            sat_every_n = int(sp.get("structure_saturation_every_n", 2))
            if (sat_enabled and sat_every_n > 0
                    and layer_no % sat_every_n == 0
                    and new_amps):
                sat_verdict = self._check_structure_saturation(
                    new_amps, list(snap_amps))
                idle_new_amp, idle_stall, sat_override = _sat_override(
                    entry, sat_verdict, idle_new_amp, idle_stall,
                    r_idle_limit, r_stall_limit)
                # sat 顶了计数、而本圈其实没 stall ⇒ 条件 3 会印空括号。
                _stall_is_sat = bool(sat_verdict is False and not stalled)
                if sat_verdict is False:
                    self.vp(f"      ↳ 无新维度：idle_new_amp→"
                            f"{idle_new_amp}、idle_stall→{idle_stall}"
                            f"（四层同等生效）")
                elif sat_verdict is True:
                    self.vp(f"      ↳ 有新维度，idle_new_amp 重置为 0")

            if rounds_n > 1:
                _stall_disp = (stall_why if stalled
                               else ("结构饱和度判定" if _stall_is_sat
                                     else ""))
                self.vp(f"   🆕 本圈新增 & {len(new_amps)} 条 / "
                        f"线头 {len(new_threads)} 条"
                        f"（近似不算，比对池内全部；"
                        f"连续无新增 &{idle_new_amp}/线头{idle_new_thread} "
                        f"｜连续无推进 {idle_stall}"
                        f"{'（' + _stall_disp + '）' if _stall_disp else ''}）")
            round_log.append({
                "round": layer_no, "role": role,
                "new_amps": len(new_amps), "new_threads": len(new_threads),
                "idle_amp": idle_new_amp, "idle_thread": idle_new_thread,
                "idle_stall": idle_stall, "why": stall_why,
            })

            views_per_round.append({
                "round": layer_no,
                "role": role,
                "manifest": view.manifest or "",
            })
            if self.verbose:
                entry_label = _LAYER_LABEL.get(entry, entry)
                bar = "━" * 60
                print(f"\n{bar}")
                print(f"━━━ {entry_label} · 第 {layer_no}/{rounds_n} 圈 · "
                      f"{role} · view ━━━")
                print(bar)
                print(view.manifest or "（此处未生）")
                print(bar)

            seeds = select_probe_focus(
                pool, view.probes, view.threads,
                key_terms, view.anchor, self.config)

            # [P1-5] 自省回流：把这一圈 self-check 的结论变成下一圈的约束。
            # [P2-7] 约束不再只是混进 seeds（那会让它变成一条普通探针），
            # 另外走 carry_pending → Input.carry_constraints，
            # 在下一圈 prompt 里渲染成独立的硬约束块。
            # [P2-9] 尾巴的三件事（算 carry / 拼 seeds / 定下一圈角色）
            # 统一走 _carry_tail，两条跑圈通道共用同一份实现。
            carry_pending, seeds, next_role = self._carry_tail(
                view, seeds, r)
            _cur_banned = self._carry_banned_set(view.carry)
            if _cur_banned and self._carry_is_repeat(
                    _last_carry_banned, _cur_banned):
                carry_streak += 1
            elif _cur_banned:
                carry_streak = 1
            else:
                carry_streak = 0
            _last_carry_banned = _cur_banned
            if view.probes and rounds_n > 1:
                self.vp(f"   🎯 探针筛出 {len(seeds)} 条重点"
                        f"（生发 {len(view.probes)} 条 → 进下一轮 {len(seeds)} 条）")

            # ★ [LDG] 停止/收敛处先算职责读数（交付面 vs 问项），
            #   再把「连续推不动几圈」喂给停止判据。
            self._layer_duty_now(entry, view)
            _duty_streak = self._duty_marginal_streak(view)
            # ★ [四层目标 → 每圈运行] 算本层目标读数并逐圈留痕，再转停止信号。
            self._layer_goal_now(entry, view)
            self._refresh_goal_hint(entry, view)
            _goal_hit, _goal_why = self._goal_stop_signal(entry, view)
            # ★ [anytime-valid] 是否启用由配置决定（默认关 ⇒ 恒 False）。
            _any_ok = False
            try:
                _aa = float(getattr(self, "_anytime_delta", 0.0) or 0.0)
                if _aa > 0:
                    _any_ok = bool(anytime_majority_decided(
                        [1 if (int(r.get("new_amps", 0) or 0) > 0) else 0
                         for r in (view.round_log or [])], delta=_aa,
                        thr=0.5)[0])
            except Exception:
                _any_ok = False
            stop_reasons: List[str] = []
            _mi_from_view = getattr(view, "_meta_idle_streak", 0)
            _rephrase_streak = _compute_rephrase_streak(view, {
                "meta_idle_streak": meta_idle_streak})
            # [fix-78 diag] 这条只在 verbose 下打，且带的参数比判据本身多，
            # 所以留在调用点（它只是诊断，不是判据）。
            if getattr(self, "verbose", False):
                print(f"   🔬 [fix-78 diag] entry={entry} "
                      f"复述={_rephrase_streak} "
                      f"（参数 {meta_idle_streak} / view {_mi_from_view}）"
                      f"｜自省点名未消={carry_streak} soft_max={soft_max}")
            stop_reasons, idles = self._stop_reasons(
                entry=entry, layer_no=layer_no, rounds_n=rounds_n,
                total_rounds=_total_rounds, sp=sp, soft_max=soft_max,
                sim_thr=sim_thr, stable_need=stable_need,
                idle_limit=idle_limit, r_idle_limit=r_idle_limit,
                r_stall_limit=r_stall_limit,
                rephrase_streak=_rephrase_streak,
                carry_streak=carry_streak,
                idle_new_amp=idle_new_amp,
                idle_new_thread=idle_new_thread,
                idle_stall=idle_stall, stall_why=stall_why,
                sat_override=sat_override,
                stall_is_sat=_stall_is_sat,
                prev_product=prev_product,
                view=view, idles=idles, diag=False,
                duty_streak=_duty_streak,
                goal_hit=_goal_hit, goal_why=_goal_why,
                anytime_ok=_any_ok)
            if stop_reasons and rounds_n > 1:
                (stop_reasons, uncovered_streak, _prev_missed_n,
                 _def_note) = self._uncovered_gate(
                    view, stop_reasons, uncovered_streak, _prev_missed_n,
                    is_last_round=(layer_no >= _total_rounds), sp=sp)
                if _def_note:
                    deferred_notes.append(_def_note)

            stop = ""
            if stop_reasons:
                stop = " + ".join(stop_reasons) + "，螺旋停止"
            # [动态提前停] 预算理由并进来，产物里才看得出是"被截断"
            # 还是"自然停止"。min_rounds 不该压住预算（钱花完了就是花完了）。
            if getattr(self, "_budget_stop_note", ""):
                stop = (stop + "；" if stop else "") \
                    + self._budget_stop_note + "，提前收尾"

            if entry == "both" and r == 0:
                self.pools["both"].duel_alignment["consumed"] = True
            prev_product = view.manifest or ""

            min_r = int((sp.get("min_rounds") or {}).get(entry, 0))
            if stop and layer_no < min_r:
                self.vp(f"   ⏸ 停止理由「{stop}」被 min_rounds={min_r} "
                        f"拦截，继续第 {layer_no + 1} 圈")
                stop = ""
            if (stop and entry == "all"
                    and layer_no < _total_rounds):
                try:
                    _clo_pre = self._settle_meta()
                except Exception:
                    _clo_pre = None
                if (_clo_pre is not None
                        and not _clo_pre.get("clean", True)
                        and _clo_pre.get("unsettled", 0) > 0):
                    _cur_uns = int(_clo_pre.get("unsettled", 0))
                    if _cur_uns < _last_unsettled:
                        _all_settle_streak = 0
                    else:
                        _all_settle_streak += 1
                    _last_unsettled = _cur_uns
                    if _all_settle_streak < 1:
                        self.vp(f"   ⏸ 元层闭环未清算"
                                f"（{_cur_uns}/"
                                f"{_clo_pre['total']} 类张力，"
                                f"streak={_all_settle_streak}），"
                                f"推迟停止")
                        stop = ""
                    else:
                        self.vp(f"   ⏹ 元层清算未下降"
                                f"（连续 {_all_settle_streak} 圈），"
                                f"不再推迟停止")
            if stop:
                view.stop_reason = stop
                self.vp(f"   ⏹ 螺旋停止（第 {layer_no} 圈）：{stop}")
                break
        # 走满预算的交代不再写在这里——已挪进 _finalize_layer_common，
        # 让 B/C/D-H 通道也有同一句（它们以前完全不说）。

        if view is not None:
            self._finalize_layer_common(entry, view, {
                "roles_hist": roles_hist,
                "all_view_errors": _all_view_errors,
                "total_rounds": rounds_cap,
                "round_log": round_log,
                "deferred_notes": deferred_notes,
                "all_rehashed": all_rehashed,
                "all_candidates": all_candidates,
                "all_expanded_descs": all_expanded_descs,
                "all_amps": all_amps,
                "all_amp_cands": all_amp_cands,
                "all_threads": all_threads,
                "all_dec_products": all_dec_products,
                "all_und_products": all_und_products,
                "r": view.rounds_run or rounds_n,
                "rounds_n": rounds_n,
                "sp": sp,
            })

        # [fix-99] self 记忆：按层写各自的桶，不再 4 个线程抢同一个 list。
        # ★ 这一句必须在 `rounds_n > 1` 块**外**——原实现就在块外，
        #   单圈的层（如 route 不含 all 时）也要写 self；挪进块内会让
        #   这些层的 self 段为空（冒烟的 A(no-all) 会抓到）。
        if "self" in self.channels and view is not None:
            self._append_self_text(entry, view)

        return view

    def _make_serial_provider(self):
        def provider(entry: str):
            deps = _ENTRY_CONTENT_DEPS.get(entry, ())
            return [self._results[k] for k in deps
                    if k in self._results]
        return provider

    # ============================================================
    # 可判定性：0 层先行 [P0-2]
    # ============================================================
    def _run_zero_then_assess(self, question, rounds,
                              active: List[str]) -> List[str]:
        """把 0 层从并行集合里提出来先跑，供研究层拆解时读池。

        [v1.21.60⑩] 评估职责已移到 `_assess_decidability_dynamic`
        （研究层第 1 圈拆解时动态读池/外部），这里只负责「跑满 0 层」。

        返回剔除了 "0" 的 active（0 的结果已进 self._results）。
        """
        self.vp(f"\n{'─'*60}\n🪞 修行层先行"
                f"（研究层拆解时读的是它留下的形状）\n{'─'*60}")
        try:
            self._results["0"] = self._run_layer(
                "0", self._rounds.get("0", rounds.get("0", 0)))
        except Exception as exc:
            logger.error("0 层先行失败: %s", exc, exc_info=True)
            self._results.pop("0", None)
        return [e for e in active if e != "0"]

    # ============================================================
    # B/C 模式：0 层预热圈 [feat-107]
    # ============================================================
    def _warmup_and_assess(self, active: List[str],
                           warm_full: bool = False,
                           warm_rounds: Optional[int] = None) -> int:
        """0 层先跑 N 圈，供研究层拆解时读到修行层先行产物。

        [v1.21.60⑩] 评估职责已移到 `_assess_decidability_dynamic`
        （研究层第 1 圈拆解时动态读池/外部），这里只负责「跑 0 层」。

        warm_full=True 时（F/G/H），圈数 = 0 层 total_rounds（跑满）；
        warm_rounds 显式指定圈数（覆盖配置，含 0）。D/E 双起并行传 0，
        不制造 0 层领先。

        返回实际跑的圈数。
        """
        self._warmup_done = 0
        has_zero = "0" in active and "0" in self._b_state

        if warm_full and "0" in self._b_state:
            want = max(0, int(self._b_state["0"]["total_rounds"]))
        elif warm_rounds is not None:
            want = max(0, int(warm_rounds))
        else:
            want = max(0, int((self.config.get("actions") or {}).get(
                "parallel_warmup_rounds", 1) or 0))

        if not has_zero or want == 0:
            return 0

        st0 = self._b_state["0"]
        warm = min(want, max(0, int(st0["total_rounds"])))
        if warm <= 0:
            return 0

        tag = self._parallel_label
        if warm_full:
            head = (f"🪞 修行层跑满 {warm} 圈"
                    f"（下游在它收工后出发，研究层拆解时读它留下的形状）")
        else:
            head = (f"🪞 修行层预热 {warm} 圈"
                    f"（之后它从第 {warm+1} 圈接着跑）")
        self.vp(f"\n{'─'*60}\n{head}\n{'─'*60}")
        phase = "跑满" if warm_full else "预热"
        ok_rounds = 0
        for r in range(1, warm + 1):
            if st0["stopped"]:
                break
            try:
                v = self._run_one_round_B("0", r)
            except Exception as exc:
                logger.error("%s 模式 0 层%s第 %d 圈失败: %s",
                             tag, phase, r, exc, exc_info=True)
                break
            if v is None:
                break
            self._results["0"] = v
            ok_rounds = r

        self._warmup_done = ok_rounds

        if ok_rounds < want:
            self.vp(f"   ℹ️ {phase}只跑出 {ok_rounds}/{want} 圈"
                    f"（修行层提前停止）")
        return ok_rounds

    # ============================================================
    # A 模式
    # ============================================================
    def _run_parallel_A(self, question, route, keep, rounds, channels):
        route = route or ["0", "1", "both", "all"]
        keep = keep or {k: "all" for k in route}
        if channels is not None:
            self.channels = tuple(MemoryChannel.check(c) for c in channels)
        self._mcfg["channels"] = list(self.channels)

        self._question = question
        self._key_terms = sorted(_kw(question, top_n=6))
        self._rounds = rounds
        self._keep = keep
        self._results = {}
        self._upstream_provider = lambda e: []

        sp1 = _spiral_for(self.config, "1")
        self.dec_tracker = ChannelTracker(
            "decidable",
            int(sp1.get("stall_streak_limit", 2)),
            float(sp1.get("min_distance_improvement", 0.03)))
        self.und_tracker = ChannelTracker(
            "undecidable",
            int(sp1.get("stall_streak_limit", 2)),
            float(sp1.get("min_distance_improvement", 0.03)))

        # [P0-2] 0 层先行 + 池视角判定，返回的 active 已剔除 "0"
        _active0 = self._planned_active(route)
        _rounds0 = rounds or self._rounds
        active = self._run_zero_then_assess(
            question, _rounds0, _active0)

        self.pools["both"].duel_alignment = {
            "quality": "unaligned",
            "match_rate": 0.0,
            "quadrants": [],
            "consumed": True,
            "_note": "A 模式独立运行，两侧并行，无上游可对齐",
        }

        self.vp(f"\n{'═'*60}\n🧵 A 模式："
                f"{'/'.join(_LAYER_LABEL[e] for e in active)} 并行"
                f"\n{'─'*60}")
        for e in active:
            self.vp(f"   → {_LAYER_LABEL[e]}（上限 {rounds.get(e, 0)} 圈）")

        with ThreadPoolExecutor(max_workers=max(2, len(active))) as ex:
            futures = {
                e: ex.submit(self._run_layer, e, rounds.get(e, 0))
                for e in active
            }
            for e, f in futures.items():
                try:
                    self._results[e] = f.result()
                except Exception as exc:
                    logger.error("A 模式 %s 失败: %s", e, exc, exc_info=True)
                    reason = self._note_layer_failure(e, exc)
                    self._results[e] = self._failed_layer_view(e, reason)

        # [fix-101] 汇流圈不再要求 route 里必须有 all：
        # 只要拿到 >=2 份**可用**的上游 view 就跑，否则 A 模式下
        # `--route 0,1,both` 会退化成四份互不相干的独立报告。
        available = [k for k in ("0", "1", "both")
                     if _view_usable(self._results.get(k))]
        conf_view = None
        if len(available) >= 2:
            self.vp(f"\n{'─'*60}\n🔀 汇流圈"
                    f"（上游 {available}）\n{'─'*60}")
            try:
                up = [self._results[k] for k in available]
                conf_inp = Input(
                    upstream_views=up,
                    upstream_pools=[self.pools[k] for k in available],
                    upstream_untouched=[v.untouched for v in up],
                    root_question=question,
                    seed_probes=[],
                    key_terms=self._key_terms,
                    round_role="收束", round_no=1,
                    context=self._context_if_on(),
                    self_memory=self._self_snapshot_for("all"),
                )
                conf_inp.pool = self.pools["all"]
                conf_inp.decidability_result = self.decidability_result
                dg = DGTF("all", self.llm, self.config)
                conf_view = dg.run(conf_inp)
                self._apply_view_to_pool(
                    conf_view, self.pools["all"], "all")
                if _view_usable(self._results.get("all")):
                    self._merge_confluence(self._results["all"], conf_view)
                else:
                    # route 里没要 all 层：汇流结果只入池，不凭空多出一个 view
                    self.vp("   ℹ️ route 未含 all，汇流仅入池")
                self.vp(f"   ✓ 汇流圈完成"
                        f"（view {len(conf_view.manifest or '')} 字）")
            except Exception as exc:
                logger.warning("汇流圈失败: %s", exc, exc_info=True)
                conf_view = None
        else:
            self.vp(f"\n   ℹ️ 可用上游不足 2 份（{available}），跳过汇流圈")

        with self._pool_lock:
            self._totalize_all_pool()
        self._merge_self_text()

        packed = self._pack_result(
            question, route, keep, rounds, self._results)
        if conf_view is not None and not _view_usable(
                self._results.get("all")):
            packed["confluence"] = conf_view.to_dict()
        packed["dispatch"] = self._dispatch_for_pack("A")
        return packed

    # ============================================================
    # B 模式
    # ============================================================
    def _run_parallel_B(self, question, route, keep, rounds, channels):
        route = route or ["0", "1", "both", "all"]
        keep = keep or {k: "all" for k in route}
        if channels is not None:
            self.channels = tuple(MemoryChannel.check(c) for c in channels)
        self._mcfg["channels"] = list(self.channels)

        self._question = question
        self._key_terms = sorted(_kw(question, top_n=6))
        self._rounds = rounds
        self._keep = keep
        self._results = {}
        self._prev_results = {}
        self._parallel_label = "B"
        self._warmup_done = 0

        sp1 = _spiral_for(self.config, "1")
        self.dec_tracker = ChannelTracker(
            "decidable",
            int(sp1.get("stall_streak_limit", 2)),
            float(sp1.get("min_distance_improvement", 0.03)))
        self.und_tracker = ChannelTracker(
            "undecidable",
            int(sp1.get("stall_streak_limit", 2)),
            float(sp1.get("min_distance_improvement", 0.03)))

        active = self._planned_active(route)
        self._b_state = {e: self._init_b_state(e) for e in active}
        self._upstream_provider = self._make_jacobi_provider()
        warm = self._warmup_and_assess(active)
        # 0 层预热产物立刻成为其余层第 1 圈的 Jacobi 上游，
        # 不再出现"第 1 圈全员没有上游"的空转。
        self._prev_results = dict(self._results)

        hi0 = (self._b_state["0"]["total_rounds"]
               if "0" in self._b_state else warm)
        others = [e for e in active if e != "0"]
        max_wave = max([hi0]
                       + [self._b_state[e]["total_rounds"] + warm
                          for e in others]
                       + [warm])

        self.vp(f"\n{'═'*60}\n🧵 B 模式：轮次并行"
                f"（{'0 层预热 ' + str(warm) + ' 圈后错位接力，'
                   if warm else ''}"
                f"共 {max_wave} 波）\n{'═'*60}")
        for e in active:
            st = self._b_state[e]
            lead = f"　已跑 {warm} 圈预热，从第 {warm+1} 圈接力" \
                if (e == "0" and warm) else ""
            self.vp(f"   → {_LAYER_LABEL[e]}"
                    f"（上限 {st['total_rounds']} 圈）{lead}")

        for k in range(warm + 1, max_wave + 1):
            # [动态提前停] B 是自动规划**最常选**的模式，而它的波循环原来
            # 根本没有预算守卫 —— 预算只在 serial / A / C / D-H 生效，等于
            # 最常用的这条路上「动态提前停」是死的（实测 bd61a：预算压到 60，
            # 实际跑到 170 次调用，日志里 0 条「预算用尽」）。
            # 第一波不拦：至少让每层交出第一圈，否则产物全是空占位。
            if k > warm + 1 and self._budget_exhausted():
                self._note_budget_stop(f"B 模式第 {k} 波")
 # ★ 这里**同时停掉所有层**是**刻意的 barrier
                for e in active:
                    st = self._b_state.get(e) or {}
                    if st.get("stopped"):
                        continue
                    st["stopped"] = True
                    _prev = st.get("stop_reason") or ""
                    st["stop_reason"] = (
                        (_prev + "；") if _prev else ""
                    ) + self._budget_stop_note + "，提前收尾"
                    if st.get("view") is not None:
                        st["view"].stop_reason = st["stop_reason"]
                break
            batch: List[Tuple[str, int]] = []
            if "0" in self._b_state and warm < k <= hi0:
                batch.append(("0", k))
            for e in others:
                rr = k - warm
                if 1 <= rr <= self._b_state[e]["total_rounds"]:
                    batch.append((e, rr))
            batch = [b for b in batch
                     if not self._b_state[b[0]]["stopped"]]
            if not batch:
                continue

            self.vp(f"\n{'─'*60}\n🔄 B 第 {k}/{max_wave} 波"
                    f"（{len(batch)} 层："
                    f"{'/'.join(_LAYER_LABEL[e] for e, _ in batch)}）"
                    f"\n{'─'*60}")

            with ThreadPoolExecutor(max_workers=max(2, len(batch))) as ex:
                futures = {
                    e: ex.submit(self._run_one_round_B, e, rr)
                    for e, rr in batch
                }
                for e, f in futures.items():
                    try:
                        view = f.result()
                        if view is not None:
                            self._results[e] = view
                    except Exception as exc:
                        logger.error("B 模式 %s 第 %d 波失败: %s",
                                     e, k, exc, exc_info=True)
                        reason = self._note_layer_failure(e, exc)
                        self._b_state[e]["stopped"] = True
                        self._b_state[e]["stop_reason"] = f"异常：{reason}"
                        if self._b_state[e].get("view") is None:
                            self._results[e] = self._failed_layer_view(
                                e, reason)

            self._prev_results = dict(self._results)

        for e in active:
            self._b_finalize_layer(e)

        # [fix-100] _totalize_all_pool 必须串行，且在所有层跑完后执行
        with self._pool_lock:
            self._totalize_all_pool()
        self._merge_self_text()

        packed = self._pack_result(
            question, route, keep, rounds, self._results)
        packed["dispatch"] = self._dispatch_for_pack(
            "B", {"_warmup_rounds": self._warmup_done})
        return packed

    # ============================================================
    # C 模式：流水线并行（Pipeline）[feat-106]
    # ============================================================
    #   时间 →
    #     0:    [r1][r2][r3][r4]
    #     1:        [r1][r2][r3][r4]
    #     both:         [r1][r2][r3]
    #     all:              [r1][r2]
    #
    #   每层不等上游跑完，只等上游交出第一圈就出发，之后各跑各的。
    #   每圈读的是**当下最新**的上游 view，不是 Jacobi 的上一轮定格。
    #   这是三档并行里最快的一档，代价是结果带时序依赖 ——
    #   both 的第 2 圈读到 0 的第几圈，取决于那一圈谁先跑完。
    # ============================================================
    def _run_parallel_C(self, question, route, keep, rounds, channels):
        route = route or ["0", "1", "both", "all"]
        keep = keep or {k: "all" for k in route}
        if channels is not None:
            self.channels = tuple(MemoryChannel.check(c) for c in channels)
        self._mcfg["channels"] = list(self.channels)

        self._question = question
        self._key_terms = sorted(_kw(question, top_n=6))
        self._rounds = rounds
        self._keep = keep
        self._results = {}
        self._prev_results = {}
        self._parallel_label = "C"
        self._warmup_done = 0

        sp1 = _spiral_for(self.config, "1")
        self.dec_tracker = ChannelTracker(
            "decidable",
            int(sp1.get("stall_streak_limit", 2)),
            float(sp1.get("min_distance_improvement", 0.03)))
        self.und_tracker = ChannelTracker(
            "undecidable",
            int(sp1.get("stall_streak_limit", 2)),
            float(sp1.get("min_distance_improvement", 0.03)))

        active = self._planned_active(route)
        self._b_state = {e: self._init_b_state(e) for e in active}
        # C 读活的结果表，B 读上一轮的定格 —— 这是两个模式唯一的本质差别
        self._upstream_provider = self._make_pipeline_provider()
        self._c_released = {e: threading.Event() for e in active}

        warm = self._warmup_and_assess(active)
        if warm > 0:
            self._c_release("0")

        if not active:
            self.vp("\n   ⚠️ route 为空，C 模式无事可做")
            packed = self._pack_result(question, route, keep, rounds, {})
            packed["dispatch"] = self._dispatch_for_pack(
                "C", {"_warmup_rounds": self._warmup_done})
            return packed

        self.vp(f"\n{'═'*60}\n🧵 C 模式：流水线并行\n{'═'*60}")
        self.vp("   0:    [r1][r2][r3]…")
        self.vp("   1:        [r1][r2][r3]…")
        self.vp("   both:         [r1][r2][r3]…")
        self.vp("   all:              [r1][r2]…")
        if warm:
            self.vp(f"   （修行层已预热 {warm} 圈，先手出发）")
        for e in active:
            st = self._b_state[e]
            deps = self._c_gate_deps(e)
            gate = ("等 " + "/".join(_LAYER_LABEL.get(d, d) for d in deps)
                    if deps else "立即出发")
            self.vp(f"   → {_LAYER_LABEL[e]}"
                    f"（上限 {st['total_rounds']} 圈，{gate}）")

        with ThreadPoolExecutor(max_workers=max(2, len(active))) as ex:
            futures = {
                e: ex.submit(self._run_layer_C, e) for e in active
            }
            for e, f in futures.items():
                try:
                    f.result()
                except Exception as exc:
                    logger.error("C 模式 %s 线程异常: %s",
                                 e, exc, exc_info=True)

        for e in active:
            self._b_finalize_layer(e)

        # 同 B：汇总必须串行，且在所有层跑完后执行
        with self._pool_lock:
            self._totalize_all_pool()
        self._merge_self_text()

        packed = self._pack_result(
            question, route, keep, rounds, self._results)
        packed["dispatch"] = self._dispatch_for_pack(
            "C", {"_warmup_rounds": self._warmup_done})
        return packed

    def _make_pipeline_provider(self):
        """C 模式的上游供给：读**当下最新**的上游 view。

        B 读的是 self._prev_results（上一波结束时的定格），
        C 读的是 self._results（活表）——上游刚跑完第 5 圈，
        下游的第 2 圈就直接吃第 5 圈。这就是流水线要的错位，
        也正是它结果带时序依赖的原因。
        """
        def provider(entry: str):
            deps = _ENTRY_CONTENT_DEPS.get(entry, ())
            out = []
            for k in deps:
                v = self._results.get(k)
                if v is not None:
                    out.append(v)
            return out
        return provider

    def _c_gate_deps(self, entry: str) -> tuple:
        """C 模式某层的放行前提：哪些上游必须先交出第一圈。

        *_ENTRY_DEPS 里 1 是空的（它不"需要"0），但用户要求
        研究/对撞/元层都在修行层跑完预热圈之后再开动 —— 否则
        研究层第 1 圈读不到修行池，只能退回外部分解。
        """
        if entry == "all":
            base = ("0", "1", "both")
        else:
            base = tuple(_ENTRY_DEPS.get(entry, ()))
        if entry != "0":
            base = tuple(dict.fromkeys(("0",) + base))
        return tuple(d for d in base
                     if d != entry and d in self._c_released)

    def _c_wait_gate(self, entry: str) -> None:
        timeout = float((self.config.get("actions") or {}).get(
            "pipeline_gate_timeout", 900) or 900)
        for dep in self._c_gate_deps(entry):
            ev = self._c_released.get(dep)
            if ev is None or ev.is_set():
                continue
            self.vp(f"   🚦 {_LAYER_LABEL.get(entry, entry)} 等 "
                    f"{_LAYER_LABEL.get(dep, dep)} 交出第一圈…")
            if not ev.wait(timeout=timeout):
                logger.warning("C 模式 %s 等 %s 超时 %.0fs，自行出发",
                               entry, dep, timeout)
                self.vp(f"   ⚠️ 等 {_LAYER_LABEL.get(dep, dep)} "
                        f"超时 {timeout:.0f}s，自行出发"
                        f"（这一圈可能没有上游可读）")

    def _c_release(self, entry: str) -> None:
        ev = self._c_released.get(entry)
        if ev is not None and not ev.is_set():
            ev.set()

    def _run_layer_C(self, entry: str) -> Optional[View]:
        """C 模式单层：等闸门 → 连续跑完自己的圈 → 放行下游。

        跑圈本身复用 _run_one_round_B（同一套停止判据 / 生命周期 /
        跨圈合并）。它内部只依赖 self._upstream_provider，
        C 把 provider 换成实时读活的 _results，语义就变成了流水线。
        """
        state = self._b_state[entry]
        total = int(state["total_rounds"])
        start_r = (self._warmup_done + 1) if entry == "0" else 1
        last: Optional[View] = None
        try:
            self._c_wait_gate(entry)
            for r in range(start_r, total + 1):
                if state["stopped"]:
                    break
                # [动态提前停] 与 _run_layer 同一口径：预算用尽就收尾
                if r > start_r and self._budget_exhausted():
                    self._note_budget_stop(f"C 模式 {entry} 跑到第 {r} 圈")
                    state["stopped"] = True
                    break
                try:
                    view = self._run_one_round_B(entry, r)
                except Exception as exc:
                    logger.error("C 模式 %s 第 %d 圈失败: %s",
                                 entry, r, exc, exc_info=True)
                    reason = self._note_layer_failure(entry, exc)
                    state["stopped"] = True
                    state["stop_reason"] = f"异常：{reason}"
                    if self._results.get(entry) is None:
                        self._results[entry] = self._failed_layer_view(
                            entry, reason)
                    break
                if view is None:
                    break
                self._results[entry] = view
                last = view
                # 交出第一圈，下游可以出发了
                self._c_release(entry)
                if state["stopped"]:
                    break
        finally:
            # 无论跑成什么样都要放行下游，否则整条流水线吊死
            self._c_release(entry)
        return last

    # ============================================================
    # D~H 模式：阶段式 DAG 并行 [feat-109]
    # ============================================================
    # 五种模式一台调度器。每层一个线程，出发前过两道闸门：
    #   waits 里的上游 —— 等它**跑完所有圈**（_st_done）
    #   gates 里的上游 —— 等它**交出第一圈**（_st_gate）
    # 跑圈还是 _run_one_round_B，上游供给还是"读当下最新"
    # （C 那套 pipeline provider）——D/E 下下游出发时上游要么已收工、
    # 要么已出圈，读到的就是那一刻的最新 view。
    #
    # 与 B/C 的分工：B 是"每波 barrier 对齐"，
    # C 是"首圈放行后各跑各的"，
    # D~H 是"指定的层必须先收工" —— 把 C 过于激进的错位
    # 收回到用户能点名的位置。
    # ============================================================
    def _run_parallel_stage(self, mode, question, route, keep,
                            rounds, channels):
        route = route or ["0", "1", "both", "all"]
        keep = keep or {k: "all" for k in route}
        if channels is not None:
            self.channels = tuple(
                MemoryChannel.check(c) for c in channels)
        self._mcfg["channels"] = list(self.channels)

        self._question = question
        self._key_terms = sorted(_kw(question, top_n=6))
        self._rounds = rounds
        self._keep = keep
        self._results = {}
        self._prev_results = {}
        self._parallel_label = mode
        self._warmup_done = 0

        sp1 = _spiral_for(self.config, "1")
        self.dec_tracker = ChannelTracker(
            "decidable",
            int(sp1.get("stall_streak_limit", 2)),
            float(sp1.get("min_distance_improvement", 0.03)))
        self.und_tracker = ChannelTracker(
            "undecidable",
            int(sp1.get("stall_streak_limit", 2)),
            float(sp1.get("min_distance_improvement", 0.03)))

        active = self._planned_active(route)
        if not active:
            self.vp(f"\n   ⚠️ route 为空，{mode} 模式无事可做")
            packed = self._pack_result(question, route, keep, rounds, {})
            packed["dispatch"] = self._dispatch_for_pack(
                mode, {"_warmup_rounds": self._warmup_done})
            return packed

        self._b_state = {e: self._init_b_state(e) for e in active}
        self._upstream_provider = self._make_pipeline_provider()
        # 每层两个事件：已交出第一圈 / 已全部收工
        self._st_gate = {e: threading.Event() for e in _ENTRIES}
        self._st_done = {e: threading.Event() for e in _ENTRIES}
        # 不在本次 route 里的层直接算完成，否则下游会永远等下去
        for e in _ENTRIES:
            if e not in active:
                self._st_gate[e].set()
                self._st_done[e].set()

        graph = _MODE_GRAPH[mode]
        _waits_0, _ = graph.get("0", ((), ()))
        _waits_1, _ = graph.get("1", ((), ()))
        zero_full_first = ("0" in active and "0" in (_waits_1 or ()))
        dual_start = ("0" in active and "1" in active
                      and not (_waits_0 or ()) and not (_waits_1 or ()))
        if dual_start:
            warm = self._warmup_and_assess(active, warm_rounds=0)
        else:
            warm = self._warmup_and_assess(active, warm_full=zero_full_first)
        if warm > 0:
            self._st_gate["0"].set()

        self.vp(f"\n{'═'*60}\n🧵 {mode} 模式："
                f"{_MODE_LABEL.get(mode, mode)}\n{'═'*60}")
        for line in _MODE_TIMING.get(mode, []):
            self.vp(f"   {line}")
        if warm:
            _zero_verb = "跑满" if zero_full_first else "预热"
            self.vp(f"   （修行层已{_zero_verb} {warm} 圈）")
        for e in active:
            st = self._b_state[e]
            waits, gates = graph.get(e, ((), ()))
            cond = []
            if waits:
                cond.append("等 " + "/".join(
                    _LAYER_LABEL.get(d, d) for d in waits) + " 跑完所有圈")
            if gates:
                cond.append("等 " + "/".join(
                    _LAYER_LABEL.get(d, d) for d in gates) + " 交出第一圈")
            lead = (f"，已跑满 {warm} 圈"
                    if (e == "0" and warm and zero_full_first)
                    else f"，已跑 {warm} 圈预热"
                    if (e == "0" and warm) else "")
            self.vp(f"   → {_LAYER_LABEL[e]}"
                    f"（上限 {st['total_rounds']} 圈{lead}，"
                    f"{'；'.join(cond) if cond else '立即出发'}）")

        with ThreadPoolExecutor(max_workers=max(2, len(active))) as ex:
            futures = {
                e: ex.submit(self._run_layer_stage, e,
                             graph.get(e, ((), ())))
                for e in active
            }
            for e, f in futures.items():
                try:
                    f.result()
                except Exception as exc:
                    logger.error("%s 模式 %s 线程异常: %s",
                                 mode, e, exc, exc_info=True)

        for e in active:
            self._b_finalize_layer(e)

        with self._pool_lock:
            self._totalize_all_pool()
        self._merge_self_text()

        packed = self._pack_result(
            question, route, keep, rounds, self._results)
        packed["dispatch"] = self._dispatch_for_pack(
            mode, {"_warmup_rounds": self._warmup_done})
        return packed

    def _st_wait(self, entry: str, dep: str, ev, what: str) -> None:
        """等上游过闸。超时也放行 —— 这一圈没上游可以，整张图吊死不行。"""
        if ev is None or ev.is_set():
            return
        timeout = float((self.config.get("actions") or {}).get(
            "pipeline_gate_timeout", 900) or 900)
        self.vp(f"   🚦 {_LAYER_LABEL.get(entry, entry)} 等 "
                f"{_LAYER_LABEL.get(dep, dep)} {what}…")
        if not ev.wait(timeout=timeout):
            logger.warning("%s 模式 %s 等 %s %s 超时 %.0fs，自行出发",
                           self._parallel_label, entry, dep, what, timeout)
            self.vp(f"   ⚠️ 等 {_LAYER_LABEL.get(dep, dep)} {what} "
                    f"超时 {timeout:.0f}s，自行出发"
                    f"（这一圈可能没有上游可读）")

    def _run_layer_stage(self, entry: str, spec: tuple) -> Optional[View]:
        """D~H 单层：过闸 → 连续跑完自己的圈 → 放行下游。"""
        waits, gates = spec
        state = self._b_state[entry]
        total = int(state["total_rounds"])
        start_r = (self._warmup_done + 1) if entry == "0" else 1
        last: Optional[View] = None
        try:
            for d in waits:
                self._st_wait(entry, d, self._st_done.get(d), "跑完所有圈")
            for d in gates:
                self._st_wait(entry, d, self._st_gate.get(d), "交出第一圈")
            for r in range(start_r, total + 1):
                if state["stopped"]:
                    break
                # [动态提前停] 与 _run_layer 同一口径
                if r > start_r and self._budget_exhausted():
                    self._note_budget_stop(
                        f"{self._parallel_label} 模式 {entry} 跑到第 {r} 圈")
                    state["stopped"] = True
                    break
                try:
                    view = self._run_one_round_B(entry, r)
                except Exception as exc:
                    logger.error("%s 模式 %s 第 %d 圈失败: %s",
                                 self._parallel_label, entry, r,
                                 exc, exc_info=True)
                    reason = self._note_layer_failure(entry, exc)
                    state["stopped"] = True
                    state["stop_reason"] = f"异常：{reason}"
                    if self._results.get(entry) is None:
                        self._results[entry] = self._failed_layer_view(
                            entry, reason)
                    break
                if view is None:
                    break
                self._results[entry] = view
                last = view
                # 交出第一圈，等着它的下游可以出发了
                self._st_gate[entry].set()
                if state["stopped"]:
                    break
        finally:
            # 跑成什么样都要放行，否则整张图吊死
            self._st_gate[entry].set()
            self._st_done[entry].set()
        return last

    def _make_jacobi_provider(self):
        def provider(entry: str):
            deps = _ENTRY_CONTENT_DEPS.get(entry, ())
            out = []
            for k in deps:
                v = self._prev_results.get(k)
                if v is not None:
                    out.append(v)
            return out
        return provider

    def _init_b_state(self, entry: str) -> dict:
        sp = _spiral_for(self.config, entry)
        rounds_n = (int(self._rounds.get(entry, 0))
                    or int(sp.get("hard_max", 6)))
        extra = int(sp.get("all_extra_rounds", 1)) if entry == "all" else 0
        return {
            "sp": sp,
            "rounds_n": rounds_n,
            "total_rounds": rounds_n + extra,
            "soft_max": int(sp.get("soft_max", 2)),
            "sim_thr": float(sp.get("stop_similarity", 0.8)),
            "stable_need": int(sp.get("stable_need", 2)),
            "idle_limit": int(sp.get("idle_limit", 2)),
            "r_idle_limit": int(sp.get("round_idle_limit", 2)),
            "new_thr": float(sp.get("new_item_similarity", 0.55)),
            "overlap_thr": float(sp.get("new_item_overlap", 0.55)),
            "thread_new_thr": float(sp.get("thread_new_similarity", 0.70)),
            "thread_overlap_thr": float(sp.get("thread_new_overlap", 0.70)),
            "r_stall_limit": int(sp.get("round_stall_limit", 2)),
            "r": 0,
            "seeds": [],
            # [P2-7] 与 _run_layer 的 carry_pending / next_role 对齐
            "carry": [],
            "next_role": "",
            "prev_product": "",
            "idles": 0,
            "uncovered_streak": 0,
            "prev_missed_n": None,
            "carry_streak": 0,  # [P1-5] 自省连续判定「复述/未裁」的圈数
            "rephrased_streak": 0,
            "meta_idle_streak": 0,
            "idle_new_amp": 0,
            "idle_new_thread": 0,
            "idle_stall": 0,
            "_last_unsettled": 999,
            "_all_settle_streak": 0,
            "all_candidates": [],
            "all_amps": [],
            "all_amp_cands": 0,
            "all_threads": [],
            "roles_hist": [],
            "round_log": [],
            "all_rehashed": [],
            "all_dec_products": [],
            "all_und_products": [],
            "all_expanded_descs": [],
            "stopped": False,
            "stop_reason": "",
            "view": None,
            "all_view_errors": [],
        }

    def _run_one_round_B(self, entry: str, r: int) -> Optional[View]:
        state = self._b_state[entry]
        sp = state["sp"]
        pool = self.pools[entry]
        state["r"] = r

        snap_amps = [str(a.get("desc", "")) for a in pool.amps]
        snap_threads = [str(t.get("desc", "")) for t in pool.threads]

        # [P2-9] 与 _run_layer 用同一个排班函数（B 通道的 r 是 1-based）
        role = self._role_for_round(r - 1, state.get("next_role"))
        state["next_role"] = ""
        self._before_round(entry, pool, r)

        self._b_pre_layer(entry, r)

        if entry in ("0", "1"):
            inp = self._build_inp_base(state["seeds"], role, r, entry,
                                       state.get("carry"))
        elif entry == "both":
            inp = self._build_inp_duel(state["seeds"], role, r,
                                       state.get("carry"))
        else:
            inp = self._build_inp_meta(state["seeds"], role, r,
                                       state.get("carry"))
        inp.pool = pool
        inp.decidability_result = self.decidability_result
        inp.is_last_round = (r >= state["total_rounds"])

        dg = DGTF(entry, self.llm, self.config)
        view = dg.run(inp)
        view.rounds_run = r
        # [P1-6 补] 逐圈收集 errors（B/C/D-H 通道）
        for _err in (view.errors or []):
            if _err not in state["all_view_errors"]:
                state["all_view_errors"].append(_err)

        if state.get("carry"):
            view.carry_check = self._check_carry_response(
                view, state["carry"])
            view.carry_check["round"] = r
            view.carry_checks.append(dict(view.carry_check))
            _dropped_now = list(getattr(view, "carry_dropped", None) or [])
            if _dropped_now:
                for _x in _dropped_now:
                    _y = dict(_x)
                    _y.setdefault("round", r)
                    view.carry_dropped_all.append(_y)
            if view.carry_check.get("violations"):
                pool.meta.append(
                    "[自省回流未生效] "
                    + str(view.carry_check.get("notes", ""))[:160])

        try:
            for _d in (getattr(view, "_expanded_descs", None) or []):
                if _d and not any(_similar(_d, x, _DUP_SIM)
                                  for x in state["all_expanded_descs"]):
                    state["all_expanded_descs"].append(_d)
        except Exception:
            pass
        state["roles_hist"].append(role)
        for rp in (view.rehashed or []):
            state["all_rehashed"].append(dict(rp, round=r))

        state["rephrased_streak"], state["meta_idle_streak"] = (
            self._apply_view_to_pool(
                view, pool, entry,
                state["rephrased_streak"], state["meta_idle_streak"], r))

        for e in (view.engagements or []):
            t = str(e.get("target", "")).strip()
            if t and not any(_similar(t, x.get("target", ""), 0.85)
                             for x in self.pools[entry].engagements):
                self.pools[entry].engagements.append(dict(e))

        st = self._b_lifecycle(entry, view, r, sp)
        # [P1-6 补·修] 同上：P1-6 的留痕在 `_b_lifecycle` → `update_deferrals`
        #   里写进 view.errors，`dg.run` 之后的收集点收不到，这里补一次。
        #   （B/C/D-H 四条通道都经这里，所以只需这一处。）
        for _err in (view.errors or []):
            if _err not in state["all_view_errors"]:
                state["all_view_errors"].append(_err)

        if _action_on(self.config, "re_evaluate_pool"):
            re_eval_n = self._lazy_every_n(int(sp.get("re_eval_every_n", 1)))
            if re_eval_n > 0 and r % re_eval_n == 0:
                self._re_evaluate_pool(entry, pool, r)

        self._b_merge(entry, view, state)

        if self.verbose:
            entry_label = _LAYER_LABEL.get(entry, entry)
            bar = "━" * 60
            print(f"\n{bar}")
            print(f"━━━ {entry_label} · {self._parallel_label} 第 {r}/"
                  f"{state['total_rounds']} 圈 · {role} · view ━━━")
            print(bar)
            print(view.manifest or "（此处未生）")
            print(bar)

        state["seeds"] = select_probe_focus(
            pool, view.probes, view.threads,
            self._key_terms, view.anchor, self.config)

        _carry, state["seeds"], state["next_role"] = self._carry_tail(
            view, state["seeds"], r - 1)
        state["carry"] = _carry or []
        _prev_banned = state.get("last_carry_banned") or set()
        _cur_banned = self._carry_banned_set(_carry)
        if _cur_banned and self._carry_is_repeat(_prev_banned, _cur_banned):
            state["carry_streak"] = int(state.get("carry_streak", 0)) + 1
        elif _cur_banned:
            state["carry_streak"] = 1
        else:
            state["carry_streak"] = 0
        state["last_carry_banned"] = _cur_banned

        self._b_check_stop(entry, view, r, state, st,
                           snap_amps, snap_threads)

        # [fix-99] B 模式此前完全没写 self_text，回来通道的 self 在
        # B 模式下是空的。与 _run_layer 保持一致：按层写各自的桶。
        if "self" in self.channels and view is not None:
            self._append_self_text(entry, view)

        state["view"] = view
        return view

    def _b_pre_layer(self, entry: str, r: int):
        if r != 1:
            return
        if (entry == "1"
                and not self.pools["1"].sub_questions
                and _action_on(self.config, "decompose_question")):
            d0 = DGTF("1", self.llm, self.config)
            d0.verbose = False
            dec_src = self.config.get("actions", {}).get(
                "decompose_source", "pool")
            zero_view = self._results.get("0")
            has_zero_prod = self._has_pool_content_view(zero_view)
            self._assess_decidability_dynamic(self._question, zero_view)
            use_internal = (dec_src == "pool" and has_zero_prod)
            subs, src_label = self._research_decompose_with_web(
                self._question, d0, zero_view, use_internal)
            try:
                self._tri_agree, self._tri_total = \
                    self._adjudicate_sub_tristate(subs, self._question)
            except Exception as _e:
                logger.warning("三态判决异常，退回拆解原标签: %s", _e)
            self.pools["1"].sub_questions = subs
            if subs:
                n_dec = sum(1 for s in subs
                            if s["decidability"] == "decidable")
                n_par = sum(1 for s in subs
                            if s["decidability"] == "partial")
                n_und = sum(1 for s in subs
                            if s["decidability"] == "undecidable")
                _par = f" / 部分 {n_par}" if n_par else ""
                self.vp(f"   🧩 研究层从{src_label}分解出 "
                        f"{len(subs)} 个子问题"
                        f"（可判定 {n_dec}{_par} / 不可判定 {n_und}）")

        # [fix-108] 原来只要 r==1 就写死"上游尚未产生，无对齐"。
        # 预热落地后 both 的第 1 圈可能真的有 0/1 两侧，
        # 再写死等于把刚拥有对齐能力的所有权摒掉了。
        # 改为按上游是否真就绪判断，与 _run_layer 一致。
        if entry == "both" and not self.pools["both"].duel_alignment:
            ups: List[View] = []
            if self._upstream_provider is not None:
                try:
                    ups = list(self._upstream_provider("both") or [])
                except Exception:
                    ups = []
            ups = [v for v in ups if _view_usable(v)]
            if len(ups) >= 2:
                sp = self._b_state.get(entry, {}).get(
                    "sp") or _spiral_for(self.config, entry)
                with self._pool_lock:
                    self.pools["both"].duel_alignment = \
                        _align_suspensions_and_deferrals(
                            self.pools["0"], self.pools["1"], sp)
                self.pools["both"].duel_alignment["consumed"] = False
                al = self.pools["both"].duel_alignment
                note = "（两侧没有同一件事可对，不是故障）" \
                    if al["quality"] == "unaligned" else ""
                self.vp(f"   🧭 四象限对齐：{al['quality']}"
                        f"（匹配率 {al['match_rate']:.0%}，"
                        f"{len(al['quadrants'])} 对张力）{note}")
            else:
                self.pools["both"].duel_alignment = {
                    "quality": "unaligned",
                    "match_rate": 0.0,
                    "quadrants": [],
                    "consumed": False,
                    "_note": f"{self._parallel_label} 模式第 1 圈，"
                             f"上游尚未产生，无对齐",
                }
                self.vp("   🧭 四象限对齐：跳过"
                        f"（{self._parallel_label} 第 1 圈，上游未就绪）")

    def _b_lifecycle(self, entry, view, r, sp) -> dict:
        if entry == "1":
            cov_before = coverage_of(self.pools[entry], sp, entry=entry)
            st = update_deferrals(self.pools[entry], view, r, sp,
                                  web_hook=self._web_evidence_hook)
            if any(st[k] for k in ("new", "handled", "escalated",
                                   "answered", "refined",
                                   "reclassified", "rejected")):
                self.vp(f"   ⏳ 债务：新增{st['new']} "
                        f"确认{st['confirmed']} "
                        f"清偿{st['handled']} 升级{st['escalated']} "
                        f"回答{st['answered']} 深入{st['refined']}")
            for _t in st.get("_transitions") or []:
                if _t["status"] == "applied":
                    _ev = "、".join(
                        str(e.get("resolved_to"))
                        for e in (_t.get("evidence") or [])) or "—"
                    _rb = (f"，并重新挂账 {_t['reopened_debt']}"
                           if _t.get("reopened_debt") else "")
                    self.vp(f"   ↻ 可判定性转移成立：子问题[{_t['sub_id']}] "
                            f"{_DEC_STATE_CN.get(_t.get('from'), '?')}→"
                            f"{_DEC_STATE_CN.get(_t.get('to'), '?')}"
                            f"（据 {_ev}；{_t.get('reason', '')}）{_rb}")
                else:
                    self.vp(f"   ⛔ 可判定性转移驳回：子问题[{_t['sub_id']}]"
                            f"→{_DEC_STATE_CN.get(_t.get('to'), _t.get('to'))}"
                            f"（{_t.get('why', '')}）")
            cov = coverage_of(self.pools[entry], sp, entry=entry)
            if cov is not None:
                if (cov_before is not None
                        and abs(cov - cov_before) > 0.01):
                    self.vp(f"   📊 可判定覆盖率 {cov:.0%}"
                            f"（升级前 {cov_before:.0%}）")
                else:
                    self.vp(f"   📊 可判定覆盖率 {cov:.0%}")
            else:
                self.vp("   📊 可判定覆盖率 N/A")
            self._update_trackers(view, r, cov_before, cov)
        elif entry == "both":
            st = update_duel_suspensions(self.pools[entry], view, r, sp)
            if any(st[k] for k in ("new", "revoked", "resolved",
                                   "stable", "adjudicated")):
                _sr = st.get("self_resolved", 0)
                _sr_s = f" ⚠️自解{_sr}" if _sr else ""
                self.vp(f"   ⚔️ 张力：裁决{st['adjudicated']} "
                        f"新增{st['new']} 确认{st['confirmed']} "
                        f"撤回{st['revoked']} 消解{st['resolved']}{_sr_s} "
                        f"转稳{st['stable']}")
        else:
            st = update_suspensions(self.pools[entry], view, r, sp)
            if any(st[k] for k in ("new", "revoked",
                                   "resolved", "stable")):
                _sr = st.get("self_resolved", 0)
                _sr_s = f" ⚠️自解{_sr}" if _sr else ""
                self.vp(f"   ⏸ 悬置：新增{st['new']} "
                        f"确认{st['confirmed']} "
                        f"撤回{st['revoked']} 解决{st['resolved']}{_sr_s} "
                        f"转稳{st['stable']}")
        return st

    def _b_merge(self, entry, view, state):
        for c in (view.candidates or []):
            d = str(c.get("desc", "")).strip()
            if d and not any(_similar(d, str(x.get("desc", "")), 0.85)
                             for x in state["all_candidates"]):
                state["all_candidates"].append(dict(c))
        for a in (view.amps or []):
            d = str(a.get("desc", "")).strip()
            if d and not any(_similar(d, str(x.get("desc", "")), 0.85)
                             for x in state["all_amps"]):
                state["all_amps"].append(dict(a))
        try:
            state["all_amp_cands"] += int(
                getattr(view, "_amp_cand_count", 0) or 0)
        except Exception:
            pass
        for t in (view.threads or []):
            d = str(t.get("desc", "")).strip()
            if d and not any(_similar(d, str(x.get("desc", "")), 0.85)
                             for x in state["all_threads"]):
                state["all_threads"].append(dict(t))
        if entry == "1":
            if view.decidable_product:
                state["all_dec_products"].append(
                    dict(view.decidable_product))
            if view.undecidable_product:
                state["all_und_products"].append(
                    dict(view.undecidable_product))

    def _layer_csd_now(self, entry: str, view) -> dict:
        """[CSD 早期预警] 逐圈序列的方差 / lag-1 自相关（**只作读数**）。

        ★ 依据（复杂系统 / 生态学）：系统接近临界转变时恢复速率下降 ⇒
          方差与 AC(1) 上升。
        ★ **口径写死**：这是「韧性的**概率性评估**，不是迫近崩溃的预测」
          —— 六种 regime shift 机制里多数没有 CSD 前兆。
        ★ **不参与任何停止判定**（不改变行为，只出读数）。
        """
        if view is None:
            return {}
        _rl = list(getattr(view, "round_log", None) or [])
        _s_new = [int(r.get("new_amps", 0) or 0) for r in _rl
                  if isinstance(r, dict)]
        _s_idle = [int(r.get("idle_stall", 0) or 0) for r in _rl
                   if isinstance(r, dict)]
        d = {}
        try:
            d["new_amps"] = csd_indicators(_s_new)
            d["idle_stall"] = csd_indicators(_s_idle)
        except Exception:
            d = {}
        view.csd = d
        # ★ [发散三态 + 回滚指针] 用同一序列判三态，并记下历史最佳圈的**指针**。
        #   依据 LoopGain：发散时该回滚到历史最佳 —— 但本项目**只给指针**，
        #   被回滚掉的圈照旧全部保留（红线「失败留痕」）。
        try:
            view.divergence = divergence_state(_s_new) or {}
            view.best_round = best_round_index(_s_new, higher_is_better=True)
        except Exception:
            view.divergence = {}
        # ★ [anytime-valid] 「结构仍在长」的 0/1 序列 → 均值下界。
        #   口径：下界 < 0.5 ⇒ 「仍在长」不再被证据支持 ⇒ 可停（opt-in）。
        try:
            _seq = [1 if x > 0 else 0 for x in _s_new]
            view.anytime = stitched_hoeffding_lower(
                _seq, delta=float(getattr(self, "_anytime_delta", 0.05) or 0.05)) or {}
        except Exception:
            view.anytime = {}
        return d

    def _layer_goal_now(self, entry: str, view) -> dict:
        """[四层目标] 在**停止/收敛处**算该层目标读数并记账（逐圈进
        `view.goal_trace`）。

        ★ 与 `_layer_duty_now` 同构：读数是**信号**不是分数；
          缺读数回 None（不假装 0）。**不改停止行为** —— 那由
          `layer_goal_stop_signal` 在 `_stop_reasons` 里决定。
        """
        if view is None:
            return {}
        try:
            from types import SimpleNamespace
            _vd = view.to_dict() if hasattr(view, "to_dict") else {}
            _d = layer_goal_readings({str(entry): _vd}).get(str(entry)) or {}
        except Exception:
            _d = {}
        _rec = {"round": int(getattr(view, "rounds_run", 0) or 0)}
        for _k in ("excavate", "settle", "fuse", "crystallize", "fuse_raw",
                   "sem_stagnation", "n_aspects", "n_new", "n_hits",
                   "pseudo_convergence", "converging", "conv_state"):
            if _k in _d:
                _rec[_k] = _d.get(_k)
        view.goal_trace.append(_rec)
        try:
            view.goal_now = dict(_d)
        except Exception:
            pass
        return _d

    def _goal_stop_signal(self, entry: str, view):
        """[四层目标 → 停因] 读 `view.goal_trace`，返回 `(hit, why)`。"""
        _tr = list(getattr(view, "goal_trace", None) or [])
        _now = _tr[-1] if _tr else {}
        return layer_goal_stop_signal(str(entry), _now, _tr)

    def _quant_note(self, view, key: str, val) -> None:
        """[第六期] 把一条量化读数写进 `view.quant_readings`（**唯一写入口**）。

        ★ 纪律：**值不可用（None / 空 dict / 空串）就不写键** ——
          与 `goal_trace` 出口同款（产物里不出现空壳读数）。
        ★ 只记读数，**不改任何判定**（红线：读数不是分数）。
        """
        if view is None or not key:
            return
        if val is None or val == "" or val == {}:
            return
        try:
            _d = getattr(view, "quant_readings", None)
            if _d is None:
                view.quant_readings = {}
                _d = view.quant_readings
            _d[str(key)] = dict(val) if isinstance(val, dict) else {"value": val}
        except Exception:
            pass

    def _goal_action_hint(self, entry: str, view) -> str:
        """[四层目标 → 圈内动作] 读 `view.goal_trace`，返回本圈的**形状指引**。

        ★ 与 `_goal_stop_signal` 读**同一个** `goal_trace`（同一把尺子），
          但作用在**圈内**（写进 prompt）而不是层末（写进停因）。
        """
        _tr = list(getattr(view, "goal_trace", None) or [])
        _now = _tr[-1] if _tr else {}
        try:
            return layer_goal_action_hint(str(entry), _now, _tr)
        except Exception:
            return ""

    def _refresh_goal_hint(self, entry: str, view) -> str:
        """把本圈目标读数转成**下一圈要用的形状指引**，写到 `self._goal_hint_next`。

        ★ 为什么叫「下一圈」：`_layer_goal_now` 是在**每圈结束时**调的，
          所以此刻算出来的指引自然作用于**下一圈的 prompt**。
          ⇒ 第二期**零新增接线点**（复用第一期的两处 `_layer_goal_now`）。
        ★ 本层最后一圈算出来的指引会被丢弃（没有下一圈了）——这不丢信息，
          因为它对应的`停/不停`由第一期的 `_goal_stop_signal` 负责。
        """
        try:
            _h = self._goal_action_hint(entry, view)
        except Exception:
            _h = ""
        try:
            self._goal_hint_next = str(_h or "")
        except Exception:
            pass
        return str(_h or "")

    def _layer_duty_now(self, entry: str, view) -> dict:
        """[LDG] 在**停止/收敛处**算该层职责读数并记账（读数不是分数）。

        · 交付面 = `collision` + `decidable_product` 正文 + `meta_closure` 正文
          —— 只算**这层拿出来给问题的东西**，不算内部候选/属性堆。
        · 逐圈结果进 `view.duty_trace`（边际增益判据读它）。
        """
        if view is None:
            return {}
        _dp = view.decidable_product or {}
        _mc = view.meta_closure or {}
        _parts = [str(view.collision or "")]
        for _k in ("answer", "conclusion", "summary", "direct"):
            if _dp.get(_k):
                _parts.append(str(_dp.get(_k)))
        for _k in ("text", "reason", "summary", "closure"):
            if _mc.get(_k):
                _parts.append(str(_mc.get(_k)))
        deliver = "\n".join(p for p in _parts if p)
        d = duty_of_layer(entry, self._question, deliver,
                          objective_words=_DUTY_OBJ_WORDS.get(entry, ()),
                          corpus=getattr(self, "_sim_corpus", None),
                          floor=getattr(self, "_duty_floor", _DUTY_FLOOR))
        d["round"] = int(getattr(view, "rounds_run", 0) or 0)
        try:
            view.duty_trace.append({"round": d["round"], "S": d["S"],
                                    "C": d["C"], "R": d["R"]})
        except Exception:
            pass
        view.duty = d
        return d

    def _duty_marginal_streak(self, view) -> int:
        """[LDG] 连续多少圈边际职责增益 < τ（读 `view.duty_trace`）。

        ★ 依据：EMNLP'25 自纠收敛 —— 每轮只削掉剩余误差的固定比例 ⇒
          边际增益递减即「推不动了」。工程判据 = 连续 patience 次 Δ<τ。
        ★ 计数**挂在 view 上**（不是调用方的 state）：串行通道
          (`_run_layer`) 根本没有 `state` 这个变量 —— 挂 state 就是
          「两条通道只改了一条」的老坑（冒烟当场 NameError）。
        """
        _box = view.__dict__.setdefault("_duty_stall_box", {"n": 0})
        _tr = list(getattr(view, "duty_trace", None) or [])
        if len(_tr) < 2:
            _box["n"] = 0
            return 0
        _last = float(_tr[-1].get("S", 0.0))
        _prev = float(_tr[-2].get("S", 0.0))
        _tau = float(getattr(self, "_duty_tau", _DUTY_TAU))
        _box["n"] = int(_box.get("n", 0) or 0) + 1             if abs(_last - _prev) < _tau else 0
        return int(_box["n"])

    def _stop_reasons(self, *, entry, layer_no, rounds_n, total_rounds, sp,
                      soft_max, sim_thr, stable_need, idle_limit,
                      r_idle_limit, r_stall_limit, rephrase_streak,
                      carry_streak, idle_new_amp, idle_new_thread,
                      idle_stall, stall_why, sat_override, prev_product,
                      view, idles, diag: bool = False,
                      defer_vp: bool = False,
                      stall_is_sat: bool = False,
                      duty_streak: int = 0,
                      goal_hit: bool = False,
                      goal_why: str = "",
                      anytime_ok: bool = False):
        """★ 停止理由的**唯一实现**（串行 `_run_layer` 与并行 `_b_check_stop` 共用）。

        [v1.21.60] 以前这两处各写一份：`_run_layer` 里 92 行（局部变量载体）、
        `_b_check_stop` 里 84 行（`state` dict 载体）。措辞一模一样、条件一模一样，
        只有变量名不同（`layer_no`↔`r`、`_total_rounds`↔`total_rounds`、
        `carry_streak`↔`state["carry_streak"]`…）。收口前它只靠一个
        **只看理由字面量**的冒烟（`check_stop_reason_parity`）兜着 ——
        改了一边的**条件**，两边就悄悄分叉。

        返回 `(reasons, idles)`：`idles` 是空转累计（调用方要写回自己的载体）。
        这里是**纯判据**：不改任何池、不设 stopped（那是调用方的事）。

        ★ 修行层（entry="0"）的**适用停止条件清单**（改条件前先看这张表）：

          1. 复述 / 自省点名未消化 —— **适用**（`layer_no < soft_max`
             时仍推迟）。文案取 `_LAYER_LABEL`，不借「ing」——
             那是**对撞层**的输入名，修行层没有这个输入。
          2. 「无新 &」半条 —— **不适用**（`entry != "0"` 把 0 层排除：
             修行层的 & 无新增本来就不是它的停止理由）；
             「无线头新增」半条 —— **适用**（方向走完了，与层无关）。
          3. 有新增但无推进 / sat 推计数 —— **适用**（0 层最常走的
             自然停止点）。`stall_is_sat=True` 时印「结构饱和度判定」；
             因为 sat 是在 `stalled` 为假时顶的计数，`stall_why`
             这时是空串，照搬老模板会印出 `…无推进（）`。
          4. / 5. 双通道收敛 / 停滞 —— **不适用**（`entry == "1"`
             研究层专属）。
          6. 自然安住 + 空转 —— **适用**（0 层空转文案 = 「连续空转」）。
        """
        reasons: List[str] = []

        # ---- 1) 复述 / 自省点名未消化（四层通用）----
        #   ★ 以前这条只对 all/both 开放。四层都产 & 与自省反馈，判据问的是
        #     「本层这几圈是不是在换措辞重复」，与层无关 —— 门槛去掉。
        #     `layer_no < soft_max` 的推迟仍然保留（早圈不许停）。
        if diag:
            print(f"   🔬 [fix-78 diag] entry={entry} "
                  f"复述={rephrase_streak}｜自省点名未消={carry_streak}"
                  f" soft_max={soft_max}")
        _src: List[str] = []
        # ★ 「ing」是**对撞层**的输入名；修行/研究/元层没有这个输入，
        #   把别的层的词印进它们的停因是借词（以讹传讹）。按层取标签。
        _lyr = _LAYER_LABEL.get(entry, entry)
        if rephrase_streak >= 2:
            _src.append(f"{_lyr}层连续 {rephrase_streak} 圈复述"
                        f"（层内空转）")
        if carry_streak >= 2:
            _src.append(f"自省连续 {carry_streak} 圈点名同一批问题未消化"
                        f"（层内空转）")
        if _src:
            if layer_no < soft_max:
                if diag:
                    print(f"   ⏸ [fix-82] fix-72 v4 待触发"
                          f"（{' + '.join(_src)}），"
                          f"但 layer_no={layer_no} < soft_max={soft_max}，"
                          f"先不停止")
                elif defer_vp:
                    self.vp(f"   ⏸ [fix-82] fix-72 v4 待触发"
                            f"（{' + '.join(_src)}）")
            else:
                reasons.extend(_src)

        # ---- 2) 无新 & / 无线头 ----
        if total_rounds > 1 and r_idle_limit > 0:
            if entry != "0" and idle_new_amp >= r_idle_limit:
                reasons.append("结构饱和度判定连续无新维度" if sat_override
                               else f"连续 {idle_new_amp} 轮无新 &（沉淀完了）")
            if idle_new_thread >= r_idle_limit:
                reasons.append(
                    f"连续 {idle_new_thread} 轮无线头新增（方向走完了）")

        # ---- 3) 有新增但无推进（含 sat 顶计数这一支）----
        if (rounds_n > 1 and r_stall_limit > 0
                and idle_stall >= r_stall_limit):
            if stall_is_sat:
                # sat 判「无新维度」时把 idle_stall 顶到门槛上 —— 那
                # 不是「有新增但无推进」，照搬老模板会把空串印成
                # `…无推进（）`。这一支有自己的说法。
                reasons.append(
                    f"连续 {idle_stall} 轮无新结构维度"
                    f"（结构饱和度判定，不是新增停滞）")
            else:
                reasons.append(
                    f"连续 {idle_stall} 轮有新增但无推进（{stall_why}）")

        # ---- 4) 双通道均收敛 ----
        if (entry == "1"
                and self.dec_tracker is not None
                and self.und_tracker is not None
                and self.dec_tracker.converged
                and self.und_tracker.converged
                and idle_new_amp >= r_idle_limit):
            reasons.append("研究层双通道均收敛")

        # ---- 5) 双通道均停滞 ----
        if (entry == "1"
                and self.dec_tracker is not None
                and self.und_tracker is not None
                and not (self.dec_tracker.converged
                         and self.und_tracker.converged)
                and self.dec_tracker.is_stalled()
                and self.und_tracker.is_stalled()
                and idle_new_amp >= r_idle_limit):
            reasons.append("双通道均停滞（qdist 无改善）")

        # ---- 6) 自然安住（产物相似 / 悬置决定稳定）+ 空转 ----
        if rounds_n > 1 and layer_no >= soft_max:
            product = view.manifest or ""
            _rest = ""
            if (prev_product and product
                    and _similar(prev_product, product, sim_thr)):
                _rest = "产物相似度高，自然安住"
            else:
                if entry == "both":
                    stable = [s for s in self.pools[entry].duel_suspensions
                              if s.get("status") == "stable"]
                else:
                    stable = [s for s in self.pools[entry].suspensions
                              if s.get("status") == "stable"]
                if len(stable) >= stable_need:
                    _rest = "悬置决定稳定，自然安住"
            if _rest:
                reasons.append(_rest)
            # ★ [LDG 新停止判据] 职责增益收敛：连续 patience 圈
            #   ΔS < τ ⇒ 推不动了，允许停（哪怕没有别的判据成立）。
            #   ★ 与「自然安住」的区别：安住说的是**悬置决定稳**，
            #     这条说的是**对问题的贡献不再增长** —— 两件事分开报。
            # ★ [anytime-valid 停止判据 · opt-in] 「结构仍在长」的下界已跌破
            #   0.5 ⇒ 在**随时看随时停仍然有效**的意义上可以说「不再长」。
            #   ★ 默认 `stop.anytime_alpha=0` ⇒ 该参数恒 False ⇒ 零行为差。
            if anytime_ok:
                reasons.append(
                    "结构增长已 anytime-valid 地判停（「仍在长」下界 < 0.5，"
                    "对任意停时有效）")
            _dpat = int(getattr(self, "_duty_patience", _DUTY_PATIENCE))
            if int(duty_streak or 0) >= _dpat:
                reasons.append(
                    f"职责增益收敛（连续 {int(duty_streak)} 圈 "
                    f"ΔS<{_DUTY_TAU}，对问题的贡献不再增长）")
            # ★ [四层目标 → 停因] 本层**目标读数**已达标/受阻 ⇒ 允许停。
            #   与上面两条的区别：duty 问「对问题的贡献」、anytime 问
            #   「结构是否还在长」；这条问的是**这层自己的目标**（修行=挖尽 /
            #   研究=收敛 / 对撞=融合 / 元=结晶）—— 三件事分开报。
            #   ★ 没读数 ⇒ goal_hit 恒 False ⇒ 零行为差（旧产物不受影响）。
            if goal_hit and goal_why:
                reasons.append(str(goal_why))
            if not reasons and view.idle:
                idles += 1
                if idles >= idle_limit:
                    if entry == "both":
                        reasons.append("无新张力（材料耗尽）")
                    elif entry == "all":
                        reasons.append("无新元决策（元决策耗尽）")
                    else:
                        reasons.append("连续空转")
            elif not view.idle:
                idles = 0

        # ★ [停因级联 · 吸收 SHP]
        #   把全部停因按**优先级**排序（判定/收敛 > 熵收敛 > 无信息增益 > 硬上限），
        #   并写出去「主因」。纪律：**报告的主因必须就是真正停下来的那个** ——
        #   一个级联、无漂移；主因不许是「没触发的原因」。
        if reasons:
            try:
                _cas = stop_cascade(reasons)
                if _cas.get("primary"):
                    reasons = list(_cas["ordered"])
                    view.stop_primary = str(_cas["primary"])
            except Exception:
                pass

        return reasons, idles

    def _b_check_stop(self, entry, view, r, state, st,
                      snap_amps, snap_threads):
        pool = self.pools[entry]
        sp = state["sp"]
        r_idle_limit = state["r_idle_limit"]
        r_stall_limit = state["r_stall_limit"]
        soft_max = state["soft_max"]
        sim_thr = state["sim_thr"]
        stable_need = state["stable_need"]
        idle_limit = state["idle_limit"]
        new_thr = state["new_thr"]
        overlap_thr = state["overlap_thr"]
        thread_new_thr = state["thread_new_thr"]
        thread_overlap_thr = state["thread_overlap_thr"]

        recent_amps = list(snap_amps)
        recent_threads = list(snap_threads)
        cur_amps = [str(a.get("desc", "")) for a in pool.amps]
        cur_threads = [str(t.get("desc", "")) for t in pool.threads]
        added_amps = [d for d in cur_amps
                      if not any(_similar(d, x, _DUP_SIM)
                                 for x in snap_amps)]
        added_threads = [d for d in cur_threads
                         if not any(_similar(d, x, _DUP_SIM)
                                    for x in snap_threads)]

        def _is_dup(d, x):
            return (_overlap_coef(d, x) >= overlap_thr
                    or _similar(d, x, new_thr))

        def _is_dup_thread(d, x):
            return (_overlap_coef(d, x) >= thread_overlap_thr
                    or _similar(d, x, thread_new_thr))

        new_amps = [d for d in added_amps
                    if not any(_is_dup(d, x) for x in recent_amps)]
        new_threads = [d for d in added_threads
                       if not any(_is_dup_thread(d, x)
                                  for x in recent_threads)]

        acted = any(v for k, v in st.items()
                    if k not in ("confirmed", "kept", "refined"))
        if entry == "0":
            stalled = ((not new_amps and not new_threads)
                       or (bool(new_amps or new_threads) and not acted))
            stall_why = "修行层无新增或无推进" if stalled else ""
        else:
            stalled = bool(new_amps or new_threads) and not acted
            stall_why = "池在长、判断没动" if stalled else ""

        state["idle_new_amp"] = (0 if new_amps
                                 else state["idle_new_amp"] + 1)
        state["idle_new_thread"] = (0 if new_threads
                                    else state["idle_new_thread"] + 1)
        state["idle_stall"] = (state["idle_stall"] + 1
                               if stalled else 0)
        idle_new_amp = state["idle_new_amp"]
        idle_new_thread = state["idle_new_thread"]
        idle_stall = state["idle_stall"]
        sat_override = False
        _stall_is_sat = False

        sat_enabled = bool(sp.get("structure_saturation_enabled", True))
        sat_every_n = int(sp.get("structure_saturation_every_n", 2))
        if (sat_enabled and sat_every_n > 0
                and r % sat_every_n == 0
                and new_amps):
            sat_verdict = self._check_structure_saturation(
                new_amps, list(snap_amps))
            idle_new_amp, idle_stall, sat_override = _sat_override(
                entry, sat_verdict, idle_new_amp, idle_stall,
                r_idle_limit, r_stall_limit)
            state["idle_new_amp"] = idle_new_amp
            # 同串行侧：sat 顶到门槛而本圈没 stall ⇒ 条件 3 的空括号。
            _stall_is_sat = bool(sat_verdict is False and not stalled)
            if sat_verdict is False:
                self.vp(f"      ↳ 无新维度：idle_new_amp→"
                        f"{idle_new_amp}、idle_stall→{idle_stall}"
                        f"（四层同等生效）")
            elif sat_verdict is True:
                self.vp(f"      ↳ 有新维度，idle_new_amp 重置为 0")

        if state["total_rounds"] > 1:
            _stall_disp = (stall_why if stalled
                           else ("结构饱和度判定" if _stall_is_sat
                                 else ""))
            self.vp(f"   🆕 {self._parallel_label}{r} 新增 & "
                    f"{len(new_amps)} 条 / "
                    f"线头 {len(new_threads)} 条"
                    f"（连续无新增 &{idle_new_amp}/"
                    f"线头{idle_new_thread}"
                    f"｜连续无推进 {idle_stall}"
                    f"{'（' + _stall_disp + '）' if _stall_disp else ''}）")

        state["round_log"].append({
            "round": r, "role": state["roles_hist"][-1],
            "new_amps": len(new_amps),
            "new_threads": len(new_threads),
            "idle_amp": idle_new_amp,
            "idle_thread": idle_new_thread,
            "idle_stall": idle_stall, "why": stall_why,
        })

        _mi_from_view = getattr(view, "_meta_idle_streak", 0)
        _rephrase_streak = _compute_rephrase_streak(view, state)
        _carry_streak = int(state.get("carry_streak", 0) or 0)
        # ★ [LDG] 同上：先算职责读数，再把边际增益停滞圈数喂进判据。
        self._layer_duty_now(entry, view)
        _duty_streak = self._duty_marginal_streak(view)
        # ★ [四层目标 → 每圈运行] 并行通道同样算（两通道一处实现）。
        self._layer_goal_now(entry, view)
        self._refresh_goal_hint(entry, view)
        _goal_hit, _goal_why = self._goal_stop_signal(entry, view)
        _any_ok = False
        try:
            _aa = float(getattr(self, "_anytime_delta", 0.0) or 0.0)
            if _aa > 0:
                _any_ok = bool(anytime_majority_decided(
                    [1 if (int(r.get("new_amps", 0) or 0) > 0) else 0
                     for r in (view.round_log or [])], delta=_aa, thr=0.5)[0])
        except Exception:
            _any_ok = False
        stop_reasons, state["idles"] = self._stop_reasons(
            entry=entry, layer_no=r, rounds_n=state["rounds_n"],
            total_rounds=state["total_rounds"], sp=sp,
            soft_max=soft_max, sim_thr=sim_thr, stable_need=stable_need,
            idle_limit=idle_limit, r_idle_limit=r_idle_limit,
            r_stall_limit=r_stall_limit,
            rephrase_streak=_rephrase_streak, carry_streak=_carry_streak,
            idle_new_amp=idle_new_amp, idle_new_thread=idle_new_thread,
            idle_stall=idle_stall, stall_why=stall_why,
            sat_override=sat_override,
            stall_is_sat=_stall_is_sat,
            prev_product=state["prev_product"], view=view,
            idles=state["idles"], defer_vp=True,
            duty_streak=_duty_streak,
            goal_hit=_goal_hit, goal_why=_goal_why,
            anytime_ok=_any_ok)
        state["prev_product"] = view.manifest or ""

        if stop_reasons and state["rounds_n"] > 1:
            _total = int(state.get("total_rounds") or state["rounds_n"])
            (stop_reasons, state["uncovered_streak"],
             state["prev_missed_n"], _def_note) = self._uncovered_gate(
                view, stop_reasons, state["uncovered_streak"],
                state["prev_missed_n"],
                is_last_round=(r >= _total), sp=sp)
            if _def_note:
                state.setdefault("deferred_notes", []).append(_def_note)

        stop = ""
        if stop_reasons:
            stop = " + ".join(stop_reasons) + "，螺旋停止"

        min_r = int((sp.get("min_rounds") or {}).get(entry, 0))
        if stop and r < min_r:
            self.vp(f"   ⏸ 停止理由被 min_rounds={min_r} 拦截")
            stop = ""

        if stop and entry == "all" and r < state["total_rounds"]:
            try:
                _clo_pre = self._settle_meta()
            except Exception:
                _clo_pre = None
            if (_clo_pre is not None
                    and not _clo_pre.get("clean", True)
                    and _clo_pre.get("unsettled", 0) > 0):
                _cur_uns = int(_clo_pre.get("unsettled", 0))
                if _cur_uns < state["_last_unsettled"]:
                    state["_all_settle_streak"] = 0
                else:
                    state["_all_settle_streak"] += 1
                state["_last_unsettled"] = _cur_uns
                if state["_all_settle_streak"] < 1:
                    self.vp(f"   ⏸ 元层闭环未清算，推迟停止")
                    stop = ""

        if stop:
            state["stopped"] = True
            state["stop_reason"] = stop
            view.stop_reason = stop
            self.vp(f"   ⏹ {self._parallel_label} 第 {r} 圈停止：{stop}")

    def _finalize_layer_common(self, entry: str, view,
                               state: dict) -> None:
        """两条跑圈通道（_run_layer / _b_finalize_layer）共用的收尾。

        [P3-1]「同一条逻辑两条跑圈通道各写一份」在本项目已暴露 5 次：
          跨圈去重 / _flag_all_drift / 覆盖率段 / 成本档的 _final_dedup /
          以及本次的整段收尾。每次改都要改两处，漏一处就分叉。
        这里把整段收尾收口到唯一实现；两条通道只负责把各自的累积
        打包成 state 传进来。

        state 需提供的键（两条通道的局部变量名基本一致，实测确认）：
          all_candidates / all_amps / all_threads / all_rehashed /
          all_expanded_descs / all_dec_products / all_und_products /
          round_log / roles_hist / total_rounds / r / rounds_n / sp

        ★ 顺序说明：池回填放在「元层闭环」之前。这两段互不依赖——
          _settle_meta 与 _coverage_segment 读的都是**池**
          （self.pools[...] / self.dec_tracker），不是 view 上的副本；
          _apply_keep / _settle_research 同理。原先两条通道的顺序相反
          （_run_layer 回填在后、_b_finalize_layer 回填在前），
          统一成一种以免继续分叉。
        ★ self 记忆**不在本函数里写**：serial 通道在调用方块外
          单独写、B/C/D-H 通道在 _run_one_round_B 里逐圈写。两处
          时机都要求「单圈的层也要写」——塞进本函数会让单圈层的
          self 段被写两次。
          ★ [v1.21.71 F1] 上面这句本来写的是「塞进本函数会让单圈层
            的 self 段为空」，理由是「调用方只在 rounds_n > 1 时才
            进入」。F1 去掉那道门之后理由已不成立（调用方对**所有**
            层都进入），但结论不变 —— 改的是理由，不是时机。
        """
        if view is None:
            return
        r_actual = int(state.get("r") or 0)

        # ★ [LDG] 最终职责读数先算出来（**只算不写**：署名必须等其他
        #   写 stop_reason 的人跑完再动 —— 冒烟 [走满] 抓出的时序 bug）。
        try:
            _duty_fin = self._layer_duty_now(entry, view)
        except Exception:
            _duty_fin = {}

        if not view.stop_reason:
            _cap = int(state.get("total_rounds", 0) or 0)
            _notes = list(dict.fromkeys(
                n for n in (state.get("deferred_notes") or []) if n))
            if _notes:
                view.stop_reason = (
                    f"体力耗尽（{_cap} 圈走满；"
                    f"{len(_notes)} 次停止判据被「未深入方向」推迟"
                    f"（{' ｜ '.join(_notes)}），"
                    f"是被截断不是自然停止）")
            else:
                view.stop_reason = (
                    f"体力耗尽（{_cap} 圈走满，"
                    f"未触发任何停止判据，是被截断不是自然停止）")
            # ★ [停因级联补口] 「体力耗尽」是**走满**型停因 —— 它不经过
            #   `_stop_reasons`（那条路径在走满时返回空）⇒ 之前**最需要主因的
            #   截断层反而没有主因**（真缺口，真跑产物实测发现）。
            #   这里补一次级联，保证「有停因必有主因」。
            try:
                if not getattr(view, "stop_primary", ""):
                    _cp = stop_cascade([view.stop_reason])
                    view.stop_primary = str(_cp.get("primary") or "")
            except Exception:
                pass
            self.vp(f"   ⏹ {view.stop_reason}")

        # ★ 修行层本来就能停 —— 要的不是「不许停」，是「停得合理」。
        #   所以不论它是被停止判据自然停住、还是走满上限被体力耗尽
        #   截断，都在停因后补一段「本轮显形 + 未生质量」，让
        #   「停得合理」这件事**可核**。
        #   （旧文案容易被读成「0 层不该停」，那与设计相悖。）
        if entry == "0" and (view.stop_reason or "").strip() \
                and "未生质量" not in (view.stop_reason or ""):
            n_amp = len(view.amps or [])
            n_thr = len(view.threads or [])
            n_sus = len(view.suspensions or [])
            n_prb = len(view.probes or [])
            quality = _classify_unsaid(view)
            view.stop_reason = (
                f"{view.stop_reason}\n"
                f"  本轮显形：& {n_amp} / 线头 {n_thr} / "
                f"悬置 {n_sus} / 探针 {n_prb}\n"
                f"  未生质量：{quality}"
            )
            self.vp(f"   ⏹ {view.stop_reason}")

        # ★ [LDG 署名纪律] **不许把职责未尽说成自然停止**。
        #   分寸：只改**署名**（追加一句），不删任何内容 —— 红线「悬置
        #   不打分」的延续：职责度是读数不是分数；但「说自己自然安住了」
        #   若与读数矛盾，那就是**不诚实**，必须改。
        #   ★ 时序：必须在「体力耗尽 / 未生质量」等**所有**写 stop_reason
        #     的块之后（否则会把它们顶掉）。
        # ★ [截断两向记账] 只报「省了什么」或只报「丢了什么」都会误导 ——
        #   两面必须一起出（AgentExit 的 Redundant Steps vs Progress Degradation）。
        try:
            _is_cut = any(k in str(view.stop_reason or "")
                          for k in ("体力耗尽", "预算用尽", "截断"))
            view.cut_two_way = cut_two_way(
                _is_cut, int(getattr(view, "rounds_cap", 0) or 0),
                int(getattr(view, "rounds_run", 0) or 0), _duty_fin or {})
        except Exception:
            view.cut_two_way = {}

        # ★ [四层目标 · 并列报] 本层**目标读数**单独一行（不改 duty 判定）。
        #   依据：四层定位不同（修行=挖尽 / 研究=收敛 / 对撞=融合 / 元=结晶），
        #   duty 只问「对原始问题的贡献」，问不出「这层自己的目标达没达成」。
        #   ★ 没有读数 ⇒ 不写（`goal_now` 为空时零行为差）。
        try:
            _gn = dict(getattr(view, "goal_now", None) or {})
            if _gn:
                _gk = _LG_KEYS.get(str(entry)) or ""
                _gv = _gn.get(_gk)
                if _gv is not None:
                    view.goal_verdict = "本层目标（%s）：%s=%.3f" % (
                        {"0": "修行·挖尽", "1": "研究·收敛",
                         "both": "对撞·融合", "all": "元·结晶"}.get(str(entry),
                                                                   str(entry)),
                        _gk, float(_gv))
        except Exception:
            pass

        if _duty_fin and _duty_fin.get("short"):
            _miss = _duty_fin.get("missing_core") or []
            _line = duty_short_line(_duty_fin)
            # ★ 写**独立判定行**，不动 `stop_reason`（红线「停止与清算分开」）。
            view.duty_verdict = f"职责未尽：{_line}"
            if "duty_short" not in (view.quality_flags or []):
                view.quality_flags.append("duty_short")
            # 补救定向注入：缺失的 core 问项交给**后续层**的 carry 通道
            # （对应 NAACL'25「core 子问题喂回生成器」；本仓库不重跑本层，
            #  只让下游带着「这几项没答」继续推 —— 不猜、不重跑、留痕）。
            try:
                _dc = getattr(self, "_duty_carry", None)
                if _dc is None:
                    _dc = []
                    self._duty_carry = _dc
                _n_r = int((self.config.get("duty") or {})
                           .get("remedy_rounds", _DUTY_REMEDY_ROUNDS) or 0)
                if _n_r > 0:
                    for _m in _miss:
                        if _m and _m not in _dc:
                            _dc.append(_m)
            except Exception:
                pass
            self.vp(f"   ⚖ 职责未尽（{_line}）")


        #     · action_incomplete —— **模型没按 schema 产出 actions**
        if entry == "1" and str(getattr(self, "_orientation", "auto")) \
                .strip().lower() == "decision":
            _acts_d = _extract_actions(view)
            _schema_acts_d = [a for a in _acts_d
                              if a.get("_source") == "schema"]
            if len(_schema_acts_d) < 3:
                view.errors.append(
                    f"decision 取向 actions 段不足：schema 产出 "
                    f"{len(_schema_acts_d)} 条（< 3）。请在 _he 的 "
                    f"decidable_product 里补 schema actions。")
                view.quality_flags.append("action_incomplete")
            for _a_d in _schema_acts_d:
                if _a_d.get("_missing"):
                    view.errors.append(
                        f"action {_a_d.get('id')} 缺字段：{_a_d['_missing']}")
                    view.quality_flags.append("action_fields_missing")
                    break
            _dp_d = getattr(view, "decidable_product", None) or {}
            _ans_d = str(_dp_d.get("answer") or "")
            if any(k in _ans_d for k in ("缺主体", "无主体", "无承接者",
                                        "缺承接者")) and not _schema_acts_d:
                view.errors.append(
                    "结论落在'缺 X'但 schema 未给 actions，需补 A1~A3")
            _nd_d = _extract_not_do(view)
            _nd_schema = [x for x in _nd_d
                          if isinstance(x, dict)
                          and x.get("_source") == "schema"]
            if not _nd_schema:
                view.errors.append(
                    "decision 取向 not_do 段缺失：schema 未产出。"
                    "请在 _he 的 decidable_product 里补 not_do[]。")
                view.quality_flags.append("not_do_missing")

        try:
            if entry == "both":
                self._web_duel_arbitration(view, r_actual + 1)
            elif entry == "all":
                self._web_meta_clean_check(
                    view, list(getattr(view, "uncovered_aspects", None)
                               or []), r_actual + 1)
        except Exception as _ew3:  # noqa: BLE001
            logger_web.warning("[W-W3] %s", _ew3)

        # ---- 1. 把跨圈累积回填到 view ----
        # [P1-6 补] 把中间圈的 errors 合并进来（最终 view 只有最后一圈的）
        _cross_errors = list(state.get("all_view_errors") or [])
        if _cross_errors:
            _existing = set(view.errors or [])
            for _err in _cross_errors:
                if _err not in _existing:
                    view.errors.append(_err)
                    _existing.add(_err)
        view.roles_run = list(state.get("roles_hist") or [])
        view.rounds_cap = int(state.get("total_rounds", 0) or 0)
        view.round_log = list(state.get("round_log") or [])
        # ★ [CSD 早期预警] 逐圈序列读数（只算，不改行为）。
        try:
            self._layer_csd_now(entry, view)
        except Exception:
            pass
        view.rehashed = list(state.get("all_rehashed") or [])
        if state.get("all_candidates"):
            view.candidates = state["all_candidates"]
        try:
            view._expanded_descs = list(state.get("all_expanded_descs") or [])
        except Exception:
            pass
        if state.get("all_amps"):
            view.amps = state["all_amps"]
        if state.get("all_threads"):
            view.threads = state["all_threads"]

        self.vp(f"   🧺 跨圈合并：候选 {len(state.get('all_candidates') or [])} "
                f"条 / & {len(state.get('all_amps') or [])} 条 / "
                f"线头 {len(state.get('all_threads') or [])} 条"
                f"（覆盖 {r_actual} 圈）")

        # ---- 2. 合并后的二次去重（阈值读 spiral 配置）----
        _cb, _ab, _tb, _ca, _aa, _ta = self._final_dedup(view)
        if (_cb != _ca or _ab != _aa or _tb != _ta):
            self.vp(f"   🧹 合并后二次去重：候选 {_cb}->{_ca} / "
                    f"& {_ab}->{_aa} / 线头 {_tb}->{_ta}")

        _dg = DGTF(entry, self.llm, self.config)
        _dg.verbose = False
        view.quality_flags = _keep_selfcheck_flags(
            view, _dg._quality_check(
                view, self.pools[entry], r_actual, write_diag=False))
        # ★ [LDG] 职责未尽是**读数**，不许被收尾清洗整表覆盖吞掉
        #   （本项目「静默丢失」老坑：改了、判据却是绿的）。
        if (view.duty or {}).get("short") \
                and "duty_short" not in view.quality_flags:
            view.quality_flags.append("duty_short")
        view.quality_verdict = _dg._quality_verdict(view.quality_flags)
        if entry == "all":
            self._flag_all_drift(view)
        if view.quality_flags:
            self.vp("   ⚑ 合并后质量线索："
                    + ", ".join(view.quality_flags))
        try:
            _amp_cands = int(state.get("all_amp_cands") or 0)
            _amps_out = len(view.amps or [])
            if _amp_cands > 0:
                _ratio = _amps_out / _amp_cands
                view.meta.append(
                    f"[P3] & 候选（各圈累计）{_amp_cands} 条 / 本层 amps "
                    f"{_amps_out} 条（比值 {_ratio:.2f}；amps 可能含 "
                    f"adjudications/上游合并的贡献，比值只作方向参考）"
                    + (" ⚠️ 候选有但 amps 一条都没落地"
                       "（语义不一致没变成结构信号）"
                       if _amps_out == 0 else ""))
        except Exception:
            pass

        # ---- 4. 研究层：把跨圈的可判定 / 不可判定通道合并 ----
        if entry == "1":
            _dec_p = state.get("all_dec_products") or []
            _und_p = state.get("all_und_products") or []
            if _dec_p:
                view.decidable_product = _dec_p[-1]
            if _und_p:
                merged_amps: List[str] = []
                for up in _und_p:
                    for s in (up.get("structural_amps") or []):
                        if not any(_similar(s, x, _DUP_SIM)
                                   for x in merged_amps):
                            merged_amps.append(s)
                merged_aligned: List[str] = []
                for up in _und_p:
                    for s in (up.get("aligned_amps") or []):
                        if not any(_similar(s, x, _DUP_SIM)
                                   for x in merged_aligned):
                            merged_aligned.append(s)
                last_und = _und_p[-1]
                view.undecidable_product = {
                    "why_undecidable": last_und.get("why_undecidable", ""),
                    "structural_amps": merged_amps[:10],
                    "aligned_amps": merged_aligned[:10],
                    "clarity": last_und.get("clarity", 0.0),
                    "distance": last_und.get("distance", 1.0),
                }

        # ---- 5. 池回填到 view ----
        view.suspensions = [dict(s)
                            for s in self.pools[entry].suspensions]
        if entry == "1":
            view.deferrals = [dict(d)
                              for d in self.pools["1"].deferrals]
            _co = coverage_parts(self.pools["1"], state.get("sp") or {})
            view.settlement = {
                "clean": not any(
                    d["status"] == "deferred"
                    for d in self.pools["1"].deferrals),
                "leftover": sum(
                    1 for d in self.pools["1"].deferrals
                    if d["status"] == "dropped"),
                "coverage": coverage_of(
                    self.pools["1"], state.get("sp") or {}),
                # ★ 分子分母跟着一起存：百分比不可（100% 可能是 1/1）。
                "answered": _co[0],
                "total": _co[1],
                "decidable_channel":
                    self.pools["1"].decidable_channel,
                "undecidable_channel":
                    self.pools["1"].undecidable_channel,
            }
        if entry == "both":
            view.duel_suspensions = [
                dict(s) for s in self.pools["both"].duel_suspensions]
        view.refinements = [
            dict(r) for r in self.pools[entry].refinements]

        def _append_coverage(_v, _where):
            _seg = self._coverage_segment()
            if not _seg:
                return
            _v.manifest = (_v.manifest or "") + _seg
            _ch = (list(self.dec_tracker.coverage_history)
                   if self.dec_tracker else [])
            _uh = (list(self.und_tracker.und_clarity_history)
                   if self.und_tracker else [])
            if _ch:
                self.vp(f"   📈 {_where}追加覆盖率段：{_ch[-1]:.2f}")
            elif _uh:
                self.vp(f"   📈 {_where}追加覆盖率段"
                        f"（fallback 到 und clarity）：{_uh[-1]:.2f}")

        if entry == "all":
            clo = self._settle_meta()
            view.meta_closure = clo
            if clo["clean"]:
                self.vp(f"   🌀 闭环清算：clean=True"
                        f"（对撞 {clo['total']} 类张力全部有交代）")
            else:
                _unc = clo.get("uncovered") or []
                _unc_s = "；".join(str(u)[:40] for u in _unc[:5])
                view.closure_reason = (
                    f"meta_unsettled（{clo['unsettled']}/{clo['total']} "
                    f"类张力未交代：{_unc_s}）")
                self.vp(f"   ⚠️ 闭环清算：{clo['unsettled']}/{clo['total']} "
                        f"类张力未交代（不是停止理由）")
                for _u in _unc[:5]:
                    self.vp(f"      · 未交代：{_u}")
            _append_coverage(view, "元层")
        elif entry == "1":
            _append_coverage(view, "研究层")

        # ---- 7. keep 过滤 + 研究层终局清算 ----
        self._apply_keep(self.pools[entry], self._keep.get(entry, "all"))

        if (entry == "1"
                and self.pools["1"].deferrals
                and _action_on(self.config, "settle_research")):
            deferred_count = sum(
                1 for d in self.pools["1"].deferrals
                if d["status"] == "deferred")
            if deferred_count > 0:
                self.vp(f"   📋 研究螺旋停止时仍有 {deferred_count} 笔"
                        f"延迟债务，进入终局清算")
            stl = self._settle_research(
                max(1, int(state.get("rounds_n") or 1)))
            if stl["clean"]:
                self.vp("   ✓ 终局清算完成：全部债务已交代"
                        "（handled / escalated / dropped）")
            else:
                view.closure_reason = (
                    f"soft_max_unsettled（{stl['leftover']} 项债务未清算）")
                self.vp(f"   ⚠️ 终局清算：{stl['leftover']} 项未清算"
                        f"（不是停止理由，单列）")

        try:
            _dg.verbose = self.verbose
            _dg.dump_final(view)
        except Exception as _e:
            self.vp(f"   ✗ 收尾留痕失败：{type(_e).__name__}: {_e}")


    def _b_finalize_layer(self, entry: str):
        """B/C/D-H 通道的层收尾。

        [P3-1] 本体的收尾逻辑已收口到 _finalize_layer_common——
        这里只剩「取 state + 守卫」。self 记忆由 _run_one_round_B 逐圈写，
        不在这里写。

        [v1.21.60] ★ 原实现 `if not state or state["view"] is None: return`
        —— 第一圈就抛异常的层 `state["view"]` 恒为 None，于是**整层静默消失**
        （views/pools/self 段都没有它，下游也当它不存在）。现在改为：
        留一个占位 View（在场但不可用），并把失败记进 `_failed_layers`。
        """
        state = self._b_state.get(entry)
        if state is None:
            return
        if state["view"] is None:
            reason = state.get("stop_reason") or "第一圈就失败，无任何产出"
            self._results[entry] = self._failed_layer_view(entry, reason)
            if not hasattr(self, "_failed_layers"):
                self._failed_layers = {}
            self._failed_layers.setdefault(entry, reason)
            return
        view = state["view"]
        self._finalize_layer_common(entry, view, state)

    def _merge_confluence(self, target: View, extra: View):
        if not (target and extra):
            return
        if extra.manifest:
            target.manifest = (target.manifest or "") + \
                "\n\n---\n\n## 汇流圈\n\n" + extra.manifest
        for a in (extra.amps or []):
            d = str(a.get("desc", "")).strip()
            if d and not any(_similar(d, x.get("desc", ""), 0.85)
                             for x in (target.amps or [])):
                target.amps.append(dict(a))
        for t in (extra.threads or []):
            d = str(t.get("desc", "")).strip()
            if d and not any(_similar(d, x.get("desc", ""), 0.85)
                             for x in (target.threads or [])):
                target.threads.append(dict(t))
        for s in (extra.suspensions or []):
            d = str(s.get("target", "")).strip()
            if d and not any(_similar(d, x.get("target", ""), 0.85)
                             for x in (target.suspensions or [])):
                target.suspensions.append(dict(s))
        target.meta_closure = extra.meta_closure or target.meta_closure
        target.errors = (target.errors or []) + (extra.errors or [])

    def _research_round_no(self) -> int:
        """ **前置**检索的圈号 = 0（与圈内 1..N 分开）。

        ★ 原先这里返回「拆解序号」（`_web_prep_seq`）并拿它当配额口径的
          round —— 不只是命名问题：拆解每跑只发生一次 ⇒ 所有环节的 round
          恒为 1 ⇒ `quota.per_stage_round`（任务书是「每环节**每圈**」）
          退化成「每环节每跑」，**三层配额实际只剩两层**。
        ★ 拆解确实发生在圈循环**之前**，没有圈号；用 0 明确表示「前置」。
          圈内一律用 `layer_no`：`_web_evidence_hook` 的 `layer`、
          `_finalize_layer_common` 的 `r_actual + 1`。
        """
        return 0

    def _web_search(self, stage: str, queries, round_no: int,
                    used_as: str = "evidence", pre_seq: int = 0) -> List[dict]:
        """[W2] 联网检索的**唯一实现**。返回这次真的收进来的 W# 列表。

        【做四件事】授权/配额（Gate）→ 检索（Client）→ 编号入池（W#）→
        失败留痕（独立 logger + pool.meta + pool.web_errors）。
        【enabled=False】调用点不必写 `if enabled`：本方法直接返回 []，
        且**一次 Gate 都不判**（零调用是可验证的）。
        【round_no 口径 · v1.23.1 遗留3】**圈内**传真圈号（1..N）；
          **前置**（圈循环之前的拆解/存在性检索）传 0，
          并把序号走 `pre_seq`。产物上另留 `round_kind`（pre/in）把两者
          分开 —— 配额三层的 `per_stage_round` 这才真的是「每圈」。
        """
        gate = getattr(self, "_web_gate", None)
        client = getattr(self, "_web_client", None)
        if gate is None or client is None:
            return []
        pool = self.pools.get("1")
        if pool is not None:
            # 引用授权门每次同步（配置在跑内不变，但显式摆在这里可读）。
            pool.web_as_evidence = _web_evidence_gate(self.config)
            pool._web_cfg = _web_cfg_of(self.config)
        out: List[dict] = []
        for q in [str(x) for x in (queries or []) if str(x).strip()]:
            ok, why = gate.allow(stage, int(round_no))
            if not ok:
                if pool is not None:
                    pool.meta.append("[W-SKIP] " + stage + "：" + str(why))
                break
            gate.note_call(stage, int(round_no))
            try:
                res, kind = client.search(q[:200])
            except Exception as exc:  # noqa: BLE001
                res, kind = [], "api_error"
                logger_web.warning("[W-EXC] %s", exc)
            if kind == "empty":
                # ★ 空结果 = 「外部确实没有」，是**终态**：不算失败、不降级。
                gate.note_success()
                if pool is not None:
                    pool.meta.append("[W-EMPTY] " + stage + " q=" + q[:60])
                continue
            if kind:
                gate.note_failure(kind)
                logger_web.warning("[W-%s] stage=%s q=%s", kind.upper(),
                                   stage, q[:80])
                if pool is not None:
                    pool.meta.append("[W-" + kind.upper() + "] " + stage
                                     + " q=" + q[:60])
                    pool.web_errors.append({
                        "stage": stage, "query": q[:120],
                        "kind": kind, "round": int(round_no)})
                continue
            gate.note_success()
            for it in res[:3]:
                wid = _next_web_id(pool) if pool is not None else "W?"
                item = {"id": wid, "stage": stage, "query": q[:120],
                        "claim": str((it or {}).get("claim", ""))[:400],
                        "url": str((it or {}).get("url", ""))[:300],
                        "source": str((it or {}).get("source", ""))[:200],
                        "tier": int((it or {}).get("tier", 3) or 3),
                        "used_as": used_as, "round": int(round_no),
                        "round_kind": ("pre" if int(round_no) <= 0 else "in"),
                        "pre_seq": int(pre_seq or 0)}
                _cf = _web_tier_confirmed(self.config, item.get("url", ""))
                if _cf is not None:
                    item["tier_effective"] = int(_cf)
                if pool is not None:
                    pool.web_results.append(item)
                out.append(item)
        if out and pool is not None:
            pool.meta.append(
                "[W-OK] " + stage + " 收 " + str(len(out)) + " 条（"
                + "、".join(str(x.get("id")) for x in out[:4])
                + ("…" if len(out) > 4 else "") + "）")
            _cfi = [x for x in out if "tier_effective" in x]
            if _cfi:
                pool.meta.append(
                    "[W-TIER✓] 人工确认表生效 " + str(len(_cfi)) + " 条："
                    + "、".join(
                        str(_web_domain_of(x.get("url"))) + "→"
                        + str(x.get("tier_effective"))
                        for x in _cfi[:4]))
        try:
            _ws_local = (self.config or {}).get("web_search") or {}
            if out and bool(_ws_local.get("tier_proposal")):
                _ck = getattr(client, "cache", None)
                _known = _ck.domains_load() if _ck is not None else set()
                _pr = _web_tier_proposal(out, self.config, _known)
                if _pr:
                    if pool is not None:
                        pool.web_tier_proposals.extend(_pr)
                        pool.meta.append(
                            "[W-TIER?] 建议 tier " + str(len(_pr)) + " 条"
                            "（其中新域名 "
                            + str(sum(1 for x in _pr if x.get("first_seen")))
                            + " 条）："
                            + "、".join(str(x.get("domain")) + "→"
                                        + str(x.get("proposed_tier"))
                                        for x in _pr[:4])
                            + "（**待审**，未生效；不改任何判定）")
                    if _ck is not None:
                        _ck.domains_save([x.get("domain") for x in _pr])
        except Exception as _etp:  # noqa: BLE001
            logger_web.warning("[W-TIER-EXC] %s", _etp)
        return out

    def _research_web_prep(self, question: str, _unused: int = 0) -> str:
        """[W2] 研究层拆解前的联网准备（**唯一实现**，两条通道共用）。

        做两类检索：`research_decompose`（已知/未知边界）+
        `research_precedent`（[外] 标签的存在性）。
        返回可注入 prompt 的**参照**串；`enabled=False` 时返回空串
        （⇒ prompt 逐字与 v1.22.2 相同，加性成立）。
        """
        if not bool((self.config.get("web_search") or {}).get("enabled")):
            return ""
        self._web_prep_seq = int(getattr(self, "_web_prep_seq", 0) or 0) + 1
        _rn = self._research_round_no()
        _pre = self._web_prep_seq
        pool = self.pools.get("1")
        _r1 = self._web_search("research_decompose",
                               _research_decompose_queries(question, pool), _rn,
                               pre_seq=_pre)
        _und = []
        _dr = getattr(self, "decidability_result", None)
        if isinstance(_dr, dict):
            _und = list(_dr.get("undecidable_aspects") or [])
        _r2 = self._web_search("research_precedent",
                               _research_precedent_queries(_und), _rn,
                               used_as="record", pre_seq=_pre)
        return _web_digest_block(_r1 + _r2)

    def _research_decompose_with_web(self, question: str, d0, zero_view,
                                     use_internal: bool):
        """[W2] 研究层拆解的**唯一实现**（串行 / 并行两条通道共用）。

        ★ 为什么必须收成一处：这段逻辑原先在 `_run_layer`(serial) 与
          `_b_pre_layer`(parallel) 里**各写一份**（本项目同类问题已 7 次）。
          加联网参照必然让两份分叉 —— 收口后两条通道的差异只剩「传哪个
          question / 哪个 view」。
        """
        _digest = self._research_web_prep(question)
        try:
            d0._web_digest = _digest
        except Exception:  # noqa: BLE001
            pass
        if use_internal:
            _zp = self.pools.get("0") or Pool()
            return d0._decompose_from_pool(question, _zp, zero_view), \
                "修行池内部"
        return d0._decompose_question(question, self.decidability_result), \
            "外部评估"

    def _web_duel_arbitration(self, view, round_no: int = 0) -> List[dict]:
        """[W3] 对撞层 · 第三方仲裁材料。**结果不进对撞内容**。

        进 `pool.web_arbitration`，并在池级留痕（view.meta）说明「有材料、
        但它只作参照」—— 让「跑了但没用上」与「没跑」能分开读。
        """
        pool = self.pools.get("both")
        _tx: List[str] = []
        for a in (getattr(view, "adjudications", None) or [])[:2]:
            _t = str((a or {}).get("tension", "")).strip()
            if _t:
                _tx.append(_t)
        _qs = _duel_arbitration_queries(_tx)
        if not _qs:
            return []
        _res = self._web_search("duel_arbitration", _qs,
                                max(1, int(round_no or 1)),
                                used_as="arbitration")
        if _res and pool is not None:
            for _x in _res:
                pool.web_arbitration.append(dict(_x))
            view.meta.append(
                "[W-ARB] 外部仲裁材料 " + str(len(_res)) + " 条"
                "（**只作参照**：不进 ing、不进对撞第三者）")
        return _res

    def _web_meta_clean_check(self, view, uncovered,
                            round_no: int = 0) -> List[dict]:
        """[W3] 元层 · 缺失区间核对（**只对 uncovered**）。

        ★ 不碰 deferred 的清算 —— 那属于「停止与清算分开」这条红线。
        """
        pool = self.pools.get("all")
        _qs = _meta_clean_queries(uncovered)
        if not _qs:
            return []
        _res = self._web_search("meta_clean_check", _qs,
                                max(1, int(round_no or 1)),
                                used_as="clean_check")
        if pool is not None:
            for _x in _res:
                pool.web_clean_check.append(dict(_x))
        if _res and view is not None:
            view.meta.append(
                "[W-CHK] 缺失区间外部核对 " + str(len(_res)) + " 条命中"
                "（仅作核对，不改判定）")
        return _res

    def _web_evidence_hook(self, prop: dict, layer: int) -> List[dict]:
        """[W2] `research_evidence`：给「迁向 partial」的提案先配一次外部检索。

        [v1.23.1 遗留3] `layer` 是 `update_deferrals` 传进来的**真圈号**
          （它两处调用点给的都是 `layer_no`）。原先这里忽略它、改用
          拆解序号 —— 配额口径又不对了。
        """
        _qs = _research_evidence_queries(prop)
        if not _qs:
            return []
        _rn = int(layer or 0) or 1        # 只在圈内被调；保险起见 ≥ 1
        return self._web_search("research_evidence", _qs, _rn,
                                used_as="evidence")

    def _write_tri_stability(self, subs, mode: str, from_votes: bool) -> None:
        """ 给**每一条** sub 写 `stability` + `_vote_mode`。

        · from_votes=False（单票）：口径 = 单票 vs 拆解原标签；
        · from_votes=True（多票）：票间口径已由判决循环写好，不动，
          只补「未被判到」的那些条。
        · 未被判到的条 → "abstained"（判决官弃权），**不**混进 high/low。

        ★ 必须在**每个出口前**调用。单票实现有 5 处早退 `return 0, 0`，
          只写在尾部会让「判决失败」这一情形在产物里彻底读不到
          —— 那正是 v1.22.1 P4 那个 bug 的同类形态。
        """
        for s in subs:
            if not isinstance(s, dict):
                continue
            s["_vote_mode"] = mode
            if not s.get("_tri_judged"):
                s["stability"] = "abstained"
            elif not from_votes:
                s["stability"] = _single_vote_stability(s)

    def _adjudicate_sub_tristate_multi(self, subs: List[dict],
                                       question: str) -> Tuple[int, int]:
        """三态**多票**判决（3 票，各自独立一次调用）。

        返回 `(与拆解原标签一致的条数, 有效条数)` —— 与单票实现**同签名**，
        所以两个调用点和产物的 `tri_state` 字段都不用改。多票自己的置信
        分布另存 `self._tri_consensus = (high, medium, low)`，
        逐条明细存 `self._tri_multi_items`（进 packed 的校准队列）。

        ★ 三票全失败 → 返回 (0, 0)，保留拆解原标签（与单票失败同语义）。
          这里**绝不能**回头调 `_adjudicate_sub_tristate` —— 那个方法在
          多票开启时会派发回本方法，会无限递归。
        ★ 无多数票（三票全不同）→ 落 partial，记 low，进校准队列。
          落 partial 而不是 undecidable：`_DEC_ANSWERABLE` 含 partial，
          落 undecidable 会把分母砍掉一截（这正是 v1.21.62 修过的那个形态）。
        """
        if not subs:
            return 0, 0
        lines = [f"  {i}. {str(s.get('question', ''))[:200]}"
                 for i, s in enumerate(subs, 1)]
        user = (f"【原始问题】\n{question}\n\n"
                f"【待判的子问题】\n" + "\n".join(lines))
        votes: Dict[int, List[Tuple[int, str]]] = {}
        ok_votes = 0
        _sys_list = list(_TRI_VOTE_PROMPTS)
        try:
            _ext_ok, _ = (self._web_gate.allow("research_evidence",
                                              self._research_round_no())
                          if getattr(self, "_web_gate", None) else (False, ""))
        except Exception:  # noqa: BLE001
            _ext_ok = False
        if _ext_ok:
            _ev = self._web_search(
                "research_evidence",
                _research_evidence_queries({"to": "partial",
                                            "_sq_text": question[:120]}),
                self._research_round_no(),
                used_as="tri_vote")
            if _ev:
                _sys_list[2] = _TRI_VOTE_PROMPTS[2] + _web_digest_block(_ev)
                _sys_list[2] += ("\n【裁判口径】你的这一票**只看**上面这些"
                                 "外部材料与锚点；池内产物一律不计入。\n")
        _empty_votes = 0
        _id_shift = 0
        _id_bad = 0
        _retry = 0
        try:
            _retry = int((self.config.get("actions") or {})
                         .get("tri_vote_retry_empty", 1) or 0)
        except (TypeError, ValueError):
            _retry = 1
        for _vi, sysp in enumerate(_sys_list):
            data = None
            for _try in range(1 + max(0, _retry)):
                try:
                    raw = self.llm.call(
                        sysp, user, 0.0, 1200, json_mode=True,
                        stage="adjudicate_sub_tristate_multi")
                    data = self.llm.parse_json(raw)
                except Exception as e:
                    logger.warning("三态多票：一票失败（跳过）: %s", e)
                    data = None
                    break
                if isinstance(data, dict) and (data.get("judgments") or []):
                    break
                if _try < max(0, _retry):
                    logger.warning(
                        "三态多票：第 %d 票返回 0 条判决（合法 dict 但空），"
                        "重试 %d/%d", _vi + 1, _try + 2, 1 + max(0, _retry))
            if not isinstance(data, dict):
                continue
            if not (data.get("judgments") or []):
                _empty_votes += 1
                logger.warning(
                    "三态多票：第 %d 票返回 0 条判决（空票，等于弃权）",
                    _vi + 1)
            ok_votes += 1
            _judged: Dict[int, str] = {}
            for it in (data.get("judgments") or []):
                if not isinstance(it, dict):
                    continue
                try:
                    sid = int(it.get("id", 0))
                except (ValueError, TypeError):
                    continue
                st = str(it.get("decidability", "")).lower().strip()
                if st not in _DECIDABILITY_STATES:
                    continue
                _judged[sid] = st
            _jb, _jk = _normalize_judgment_ids(_judged, len(subs))
            if _jk == "0起+1":
                _id_shift += 1
            elif _jb is None and _jk == "越界":
                _id_bad += 1
                logger.warning("三态多票：第 %d 票 id 档位=越界 → 弃票",
                               _vi + 1)
                continue
            # ★ 「空」档**不在这里计数** —— 空票已经由 `_empty_votes` 计过
            #   （上面 `if not (data.get("judgments") or [])` 那条分支）。
            #   第一版把 `_jb is None` 一律记成「越界弃票」⇒ 同一张空票被
            #   数两次，池级留痕印出「1/3 票可用（空票 1；越界弃票 1）」，
            #   可用票数因此**少数一张**。判据 `L4.2` 当场判红。
            for _sid2, _st2 in (_jb or {}).items():
                votes.setdefault(_sid2, []).append((_vi, _st2))
        if _empty_votes or _id_shift or _id_bad:
            _p1 = self.pools.get("1")
            if _p1 is not None:
                # ★ 全 0 时不写（加性）：这条留痕只在**真的发生异常**时出现。
                #   可用票数要把**弃票**也扣掉 —— 否则会印出「3/3 票可用」
                #   却只剩两张在算（非读数被当成测量值）。
                _extra = ""
                if _id_shift:
                    _extra += "；id 0 起→+1 归一 " + str(_id_shift) + " 张"
                if _id_bad:
                    _extra += "；id 越界弃票 " + str(_id_bad) + " 张"
                _p1.meta.append(
                    "[三态多票] "
                    + str(len(_sys_list) - _empty_votes - _id_bad)
                    + "/" + str(len(_sys_list)) + " 票可用（空票 "
                    + str(_empty_votes) + " 张，等于弃权；一致性指标只在"
                    "**可用票**之间计算" + _extra + "）")
        if ok_votes == 0 or not votes:
            logger.warning("三态多票：无有效票（全失败或全部弃票）"
                           " → 保留拆解原标签")
            self._write_tri_stability(subs, "multi", True)
            return 0, 0
        high = med = low = 0
        agree = 0
        n = 0
        items: List[dict] = []
        for i, s in enumerate(subs, 1):
            vs = votes.get(i) or []
            if not vs:
                continue
            n += 1
            _vl = [lb for _bi, lb in vs]
            cnt: Dict[str, int] = {}
            for v in _vl:
                cnt[v] = cnt.get(v, 0) + 1
            top = max(cnt.values())
            winners = [k for k, c in cnt.items() if c == top]
            old = str(s.get("decidability", "")).lower()
            s["first_label"] = old
            s["_tri_votes"] = list(_vl)
            if len(winners) == 1 and top >= 2:
                final = winners[0]
                if top == len(_vl):
                    high += 1
                    level = "high"
                else:
                    med += 1
                    level = "medium"
                s["decidability"] = final
                if final == old:
                    agree += 1
            else:
                low += 1
                level = "low"
                s["decidability"] = "partial"
                s["label_disagreed"] = [old] + list(_vl)
            s["_tri_judged"] = True
            s["_tri_final"] = s["decidability"]
            s["_tri_level"] = level
            s["votes"] = [{"voter": _bi, "label": lb}
                          for _bi, lb in vs]
            s["agreement"] = round(top / len(_vl), 2)
            s["stability"] = level
            if level == "low":
                # 无多数票 → 落 partial 并标 unstable（不落 undecidable：
                #   _DEC_ANSWERABLE 含 partial，落 und 会把分母砍一截）。
                s["unstable"] = True
            items.append({"sub_id": s.get("id", i),
                          "question": str(s.get("question", ""))[:160],
                          "votes": s["votes"],
                          "final": s["decidability"],
                          "first_label": old, "level": level})
        for s in subs:
            s["_decided_answerable"] = s.get("decidability") in _DEC_ANSWERABLE
        # ★ 一致性口径修正：原始一致率**不计机会一致**，
        #   在标签偏斜时严重误导（实证：原始 79% ↔ κ 0.34~0.44）。
        #   三态天然定序 ⇒ 用 **ordinal α / 加权 κ**，并单报少数类一致。
        try:
            _units = []
            _a_lab, _b_lab = [], []
            for _it in items:
                _vs = _it.get("votes") or []
                _ls = [v.get("label") for v in _vs]
                if len(_ls) >= 2:
                    _units.append(_ls)
                    _a_lab.append(_ls[0])
                    _b_lab.append(_ls[1])
            _al = krippendorff_alpha_ordinal(_units)
            _kp = weighted_kappa_pair(_a_lab, _b_lab)
            _rc = rare_class_agreement(_units, "undecidable")
            self._tri_alpha = {
                "alpha": (None if _al is None else _al.get("alpha")),
                "kappa": (None if _kp is None else _kp.get("kappa")),
                "rare": _rc,
                "n_units": len(_units),
                "verdict": alpha_verdict(
                    None if _al is None else _al.get("alpha")),
            }
        except Exception:
            self._tri_alpha = {}
        self._tri_consensus = (high, med, low)
        self._tri_multi_items = items
        self._calibration_queue = [it for it in items
                                   if it.get("level") == "low"]
        _tot = max(1, n)
        self.vp(f"   🗳 三态多票（3 票）：一致 {high} / 多数 {med} / "
                f"分裂 {low}（共识 {(high + med) / _tot:.0%}；"
                f"与拆解原标签一致 {agree}/{n}）")
        self._write_tri_stability(subs, "multi", True)
        return agree, n

    def _adjudicate_sub_tristate(self, subs: List[dict],
                                 question: str) -> Tuple[int, int]:
        """把「挑角度」和「判难度」分家：给已拆好的子问题单独判一次三态。

        【为什么要这一步】实测同题 × 同模式 × 同圈数四份样本
        （欧盟题 × G × 4 圈 × 4 层），研究层的三态分布是
        0/1/5、3/2/1、0/1/5、1/2/3 —— ANSWERABLE 在 1~5 之间跳。
        而这个标签往下**同时**是覆盖率的分母、路由与提前停的依据、
        以及终局答案「可判定部分 / 不可判定部分」的分区线。

        根因在 `_decompose_from_pool`：**一次调用**（温度 0.3）同时产出
        子问题文本和每条的 `decidability`。「选哪 6 个角度」和「这些角度
        多难」在同一个抽样里纠缠，于是分数每次都在跳。

        全量 70 份按 0 层探针数分组验过：输入形状（6/12/15/18 探针）
        对三态分布没有解释力，四组中位都是 3、都横跨 1~5 ——
        所以这不是「输入不同导致输出不同」，是判决环节本身没被单独做。

        【这一步做什么】拿已经拆好的子问题文本，换一次干净的调用、
        温度 0、并要求**先写判定依据再给标签**，逐条重判。判决结果写到
        `sub["decidability"]`，并把拆解自带的旧标签留在 `first_label`。

        【分歧怎么办】两者不一致时**落 `partial`，不落 `undecidable`**。
        因为 `_DEC_ANSWERABLE = (decidable, partial)`：落 undecidable 会把
        分母从 3 砍到 1 —— 那正是现在这个 bug 的形态；而 partial 的语义
        本来就是"可能答得出也可能答不出"，是对不确定的诚实表达。

        返回 `(一致条数, 有效条数)`；任一步失败时**保留原标签**不动，
        返回 `(0, 0)` —— 这条路径的失败不能让整趟跑挂掉。
        """
        # [AUDIT-122] 标 pending_fix：单票实现整段保留（同签名、可退路）。
        if _action_on(self.config, "tri_multi_vote"):
            return self._adjudicate_sub_tristate_multi(subs, question)
        if not subs:
            return 0, 0
        lines = [f"  {i}. {str(s.get('question', ''))[:200]}"
                 for i, s in enumerate(subs, 1)]
        system = (
            "你是【可判定性判决官】。\n"
            "\n"
            "给你若干条子问题，逐条判它：能不能被**判定**。\n"
            "\n"
            "【判据】\n"
            "- decidable：存在可指认的 0/1 候选答案——某个动作、条款、\n"
            "  数值、时间戳能被指认出「是或不是」。答得出也没关系，\n"
            "  关键是**存在一个能被占据的位置**。\n"
            "- undecidable：角色槽本身就是空的——定义尚未生成、\n"
            "  角色未被指派、缺共同参照系。不是“还没找到答案”，\n"
            "  是“那个用于承载答案的位置还没长出来”。\n"
            "- partial：一部分能被指认，另一部分落在空槽里。\n"
            "\n"
            "【★ 顺序】每条先写一句 reason（为什么落在这一格），\n"
            "再给 decidability。理由没写出来就判，等于猜。\n"
            "\n"
            "严格 JSON：\n"
            '{"judgments":[{"id":1,"reason":"...",'
            '"decidability":"decidable|partial|undecidable"}]}\n'
            + ANTI_PRETTY
        )
        # ★ 这里不能调 `self._self_block()` —— 那是 DGTF 类的方法，本方法
        #   挂在 MetaDGTF 上，调它会 AttributeError（实测把研究层第 1 圈
        #   整层打崩，D 模式记成 missing=['1']）。判决书不需要自身画像。
        user = (f"【原始问题】\n{question}\n\n"
                f"【待判的子问题】\n" + "\n".join(lines))
        try:
            raw = self.llm.call(system, user, 0.0, 1200, json_mode=True,
                                stage="adjudicate_sub_tristate")
        except Exception as e:
            logger.warning("三态独立判决失败（保留拆解原标签）: %s", e)
            self._write_tri_stability(subs, "single", False)
            return 0, 0
        # ★ parse_json 可能返回 None / list / str，只有 dict 才有 .get。
        #   直接往下走会抛 AttributeError，而且它落在 try **之外** ——
        #   调用点（两个 runner）的兜底会把整个异常吞掉，表现为"判决哑了"，
        #   日志上跟"模型返回了空 judgments"分不出来。这里把三种失败显式
        #   分开记：_parse 异常 / 非对象 / 空 judgments。
        try:
            _parsed = self.llm.parse_json(raw)
        except Exception as e:
            logger.warning("三态独立判决 JSON 解析异常（保留原标签）: %s", e)
            self._write_tri_stability(subs, "single", False)
            return 0, 0
        if not isinstance(_parsed, dict):
            logger.warning("三态独立判决返回非对象（%s，保留原标签）",
                           type(_parsed).__name__)
            self._write_tri_stability(subs, "single", False)
            return 0, 0
        data = _parsed
        judged: Dict[int, str] = {}
        for it in (data.get("judgments") or []):
            if not isinstance(it, dict):
                continue
            try:
                sid = int(it.get("id", 0))
            except (ValueError, TypeError):
                continue
            st = str(it.get("decidability", "")).lower().strip()
            if st not in _DECIDABILITY_STATES:
                continue
            judged[sid] = st
        judged, _jk1 = _normalize_judgment_ids(judged, len(subs))
        if judged is None and _jk1 == "越界":
            logger.warning("三态独立判决：id 档位=%s → 弃（保留拆解原标签）",
                           _jk1)
        if not judged:
            logger.warning("三态独立判决返回空（保留拆解原标签）")
            self._write_tri_stability(subs, "single", False)
            return 0, 0

        agree = 0
        n = 0
        for i, s in enumerate(subs, 1):
            new = judged.get(i)
            if new is None:
                continue
            n += 1
            old = str(s.get("decidability", "")).lower()
            s["_tri_judged"] = True
            s["first_label"] = old
            if new == old:
                agree += 1
                s["decidability"] = new
            else:
                # 分歧 → partial。理由见 docstring：绝不能落 undecidable。
                s["decidability"] = "partial"
                s["label_disagreed"] = [old, new]
        # ★ 冻结名单（`_decided_answerable`）在**全部** sub 上落，包括上面
        #   `continue` 掉的那些。为什么要单独再走一圈：
        #   `judged` 里没有第 i 条（模型少给几条非常常见）时，那条走不到
        #   打标记的分支，于是在 `coverage_parts` 里会被当成"没冻结"、
        #   按**此刻**的 `decidability` 算 —— 又被同一批内部机制改写回去，
        #   冻结就漏风了。没被判到 = 判决官弃权 = 保留拆解原标签，那就照
        #   它此刻（=原）的样子冻，语义一致。
        for s in subs:
            s["_decided_answerable"] = s.get("decidability") in _DEC_ANSWERABLE
        self.vp(f"   🎯 三态独立判决：{agree}/{n} 一致"
                f"（{n - agree} 条分歧落 partial）")
        self._write_tri_stability(subs, "single", False)
        return agree, n

    def _refresh_settlement(self, results):
        """把研究层终局清算改成**真·终局**。

        `view.settlement` 原先是在研究层收尾那一刻算的（那时对撞层、
        元层还没跑），于是产物头条那个覆盖率是**半程快照**：
        后两层回答上来的子问题永远进不了这个数。同一版本三跑量过一次，
        快照与终局会差在这两个数上，读数的人却看不出这是半程的。

        现在在打包（`_pack_result`）之前用**最终池**再算一次，并把快照值
        留在 `snapshot_coverage` 上 —— 两个数都印出来，读者一眼能看出
        后两层到底补回来多少。
        """
        v = results.get("1")
        if v is None or getattr(v, "settlement", None) is None:
            return
        try:
            _x, _y, _cov = coverage_parts(self.pools["1"], self.config)
        except Exception:
            return
        stl = v.settlement
        stl["snapshot_coverage"] = stl.get("coverage")
        stl["coverage"] = _cov
        stl["answered"] = _x
        stl["total"] = _y
        stl["clean"] = not any(
            d.get("status") == "deferred" for d in self.pools["1"].deferrals)
        stl["leftover"] = sum(
            1 for d in self.pools["1"].deferrals
            if d.get("status") == "dropped")
        # ★ 三态漂移留痕：判决冻结进分母的名单里，有多少条在跑的过程中
        #   被内部机制（`_starve_escalation` / `_settle_research`）改出了
        #   `_DEC_ANSWERABLE`。分母已经被冻结（见 `coverage_parts`），所以
        #   这些条不会被偷偷划出账外，但它们答不上来 —— 覆盖率因此下降，
        #   这才是诚实的读数。数字本身也得让人看见，否则读者只会看到
        #   「覆盖率掉了」而不知道掉在哪。
        try:
            _frozen = [s for s in self.pools["1"].sub_questions
                       if s.get("_decided_answerable")]
            if _frozen:
                stl["drifted_out"] = sum(
                    1 for s in _frozen
                    if s.get("decidability") not in _DEC_ANSWERABLE)
        except Exception:
            pass

    def _layer_contribution(self, results):
        """ 每层的「贡献」粗信号：实际圈数 + 停止理由 + 是否空转。

        这是「通过数据按需调度」的地基。四层定位不同（修行=摊开两面、
        研究=拆子问题、对撞=撞第三者、元=清算），不同领域、不同题的题需要
        的层组合不同。要按需调度，先得有「哪层在这题上真有贡献、哪层空转」
        的数据——分领域跑题时自动积累，后续据此提炼调度规则喂给 auto_plan。

        这里只采三个**最稳**的信号（都是 View 现成字段，不猜子结构）：
          · rounds_run：实际跑了几圈（圈数走满=被截断，暗示没收敛）
          · stop_reason：怎么停的（空转 / 体力耗尽 / 安住）
          · idle：是否判为层内空转
        产出量（& 数、裁决数、清算数）后续再加，先让「空转 vs 有产出」
        这个最有判别力的信号落地。
        """
        out = {}
        for k, v in results.items():
            if v is None:
                out[k] = {"rounds": 0, "stop": "缺失", "idle": True}
                continue
            stop = (v.stop_reason or "").strip()
            idle = bool(v.idle) or ("层内空转" in stop)
            out[k] = {"rounds": v.rounds_run, "stop": stop[:24], "idle": idle}
        return out

    def _pack_result(self, question, route, keep, rounds, results):
        # ★ 所有并行路径都汇到这里，终局清算放在这一处刷新，不会有哪条
        #   路径漏掉（原来 4 个 runner 各写各的，才会出现口径不一）。
        self._refresh_settlement(results)
        _pack = {
            "question": question,
            "route": route,
            "keep": keep,
            "rounds": rounds,
            "dispatch": {},
            "channels": list(self.channels),
            "self_text": self.self_text,
            "decidability": self.decidability_result,
            "views": {k: v.to_dict() for k, v in results.items()},
            "pools": {k: p.to_dict() for k, p in self.pools.items()},
            "llm_calls": self.llm.total_calls,
            "llm_tokens": self.llm.total_tokens,
            "tri_state": [self._tri_agree, self._tri_total],
            "layer_contribution": self._layer_contribution(results),
            "orientation": str(getattr(self, "_orientation", "auto")),
            "_auto_plan_used": dict(getattr(self, "_auto_plan_used", None) or {}),
            "_auto_dispatch": dict(
                getattr(self, "_auto_plan_spec", None) or {}),
            "_anchor_tier_warning": str(
                getattr(self, "_anchor_tier_warning", "") or ""),
            "_config": {"actions": dict(self.config.get("actions") or {})},
            "_runtime": _runtime_snapshot(self.config),
        }
        try:
            _v1p = results.get("1")
            if _v1p is not None:
                _pack["views"].setdefault("1", {})["_actions"] = \
                    _extract_actions(_v1p)
                _pack["views"]["1"]["_not_do"] = _extract_not_do(_v1p)
        except Exception as _e3:
            logger.warning("行动清单落 packed 失败: %s", _e3)
        _pack["tri_alpha"] = dict(getattr(self, "_tri_alpha", None) or {})
        _pack["llm_ops_calls"] = int(getattr(self.llm, "ops_calls", 0) or 0)
        _pack["llm_ops_tokens"] = int(getattr(self.llm, "ops_tokens", 0) or 0)
        _pack["llm_eval_calls"] = int(getattr(self.llm, "eval_calls", 0) or 0)
        _pack["llm_eval_tokens"] = int(getattr(self.llm, "eval_tokens", 0) or 0)
        _pack["tri_consensus"] = list(getattr(self, "_tri_consensus",
                                              None) or [])
        try:
            _p1 = self.pools.get("1")
            if _p1 is not None:
                _fz = DecidabilityFreeze()
                _fz.freeze(_p1, layer=1)
                _pack["freeze"] = _fz.to_dict()
                _pack["calibration_queue"] = [
                    it for it in (getattr(self, "_tri_multi_items", None) or [])
                    if it.get("level") == "low"]
            else:
                _pack["freeze"] = {"signature": "", "reason": "研究层未跑"}
                _pack["calibration_queue"] = []
        except Exception as _e:
            logger.warning("冻结/校准队列写入失败: %s", _e)
            _pack["freeze"] = {"signature": "", "error": str(_e)}
            _pack["calibration_queue"] = []

        _ar = self._anchor_report_for_pack(results)
        # ★ [锚点 ⑤⑥] 离线解析验证（refchecker 思路）+ 内部批判提示
        #   （史学 Quellenkritik：外部批判已有 tier，内部批判此前缺失）。
        #   ★ 挂到 `pool.anchors`（每条锚点带 url）—— 报告里的 claim items
        #     只有 anchor_ids，没有 url。
        try:
            for _p in self.pools.values():
                for _a in (getattr(_p, "anchors", None) or []):
                    if not isinstance(_a, dict):
                        continue
                    _u = str(_a.get("url") or "")
                    _a["offline_check"] = anchor_offline_check(_u)
                    _a["interest_hint"] = anchor_interest_hint(_u)
        except Exception:
            pass
        if _ar is not None:
            _pack["external_anchor"] = _ar
        # ★ [预算 bandit] 更新奖励（职责度中位 − λ·成本）并落盘状态。
        #   口径：reward 用**职责度中位**（读数不是分数）；cost 用 tokens/1000。
        try:
            if getattr(self, "_bandit_enabled", False) and \
                    getattr(self, "_bandit", None) is not None:
                _dv = []
                for _e in ("0", "1", "both", "all"):
                    _s = (_rv(_rv(results.get(_e), "duty", {}) or {}, "S"))
                    if _s is not None:
                        _dv.append(float(_s))
                _dv.sort()
                _rew = _dv[len(_dv) // 2] if _dv else 0.0
                _cst = float(int(_pack.get("llm_tokens") or 0)) / 1000.0
                _idx = int((getattr(self, "_bandit_pick", None) or {})
                           .get("index", 0) or 0)
                self._bandit.update(_idx, _rew, _cst)
                _save_bandit(self._bandit, self._bandit_cfg)
                _pack["bandit"] = {
                    "enabled": True, "arm": _idx,
                    "reward": round(float(_rew or 0.0), 4),
                    "cost": round(_cst, 3),
                    "explore": bool((getattr(self, "_bandit_pick", None) or {})
                                    .get("explore")),
                    "mean": [round(x, 4) for x in self._bandit.mean],
                    "n": list(self._bandit.n)}
        except Exception:
            pass
        # ★ [compact 内部面预算] 率失真口径：给定位率下的最优表示，而非越短越好
        #   （ACE 反面数据：把 1.8 万 token 压到 122 ⇒ 66.7→57.1）。
        #   ⇒ 只出**读数与政策**，**不自动压缩**（避免 ACE 式掉分）。
        try:
            import json as _j2
            # ★ [鸭子类型] 别对 View 用 .get（真跑静默失效的根因）。
            #   体积代理改用 repr 长度：repr 对循环引用安全（打印 `{...}`）。
            _inner = len(repr(results))
            _ans = 0
            for _e in ("0", "1", "both", "all"):
                _ans += len(str(_rv(results.get(_e), "collision", "") or ""))
            _pack["compact"] = compact_plan(_inner, _inner + max(1, _ans))
        except Exception as _ecp:
            _pack["compact"] = {"error": type(_ecp).__name__}
        # ★ [信念 staleness 读数] 不改四态，只出「多久没被再确认」。
        try:
            _p1s = self.pools.get("1")
            _cur = 0
            for _e in ("0", "1", "both", "all"):
                _cur = max(_cur, int(_rv(results.get(_e), "rounds_run", 0) or 0))
            _st = [belief_staleness(_it, _cur)
                   for _it in (getattr(_p1s, "belief_items", None) or [])]
            _pack["belief_staleness"] = {
                "n": len(_st),
                "stale_n": sum(1 for x in _st if x.get("stale_hint")),
                "max_age": max([x.get("age") or 0 for x in _st] or [0]),
                "items": _st[:12]}
        except Exception as _esb:
            _pack["belief_staleness"] = {"error": type(_esb).__name__}
        # ★ [多样性预算 · Ashby 必要多样性定律] 本跑实际动用的「层 × 通道」组合数。
        #   固定层×通道的多样性**有上限** —— 踩到上限时「跑得不好」不是工程缺陷，
        #   而是控制论上不可能。它是**读数**（提示谨慎读结论），不是分数。
        try:
            _mode_now = str((_pack.get("dispatch") or {})
                            .get("_parallel_mode") or "serial")
            _pack["diversity"] = diversity_budget(
                results, getattr(self, "channels", None), _mode_now)
        except Exception:
            _pack["diversity"] = {}
        return _pack

    # ============================================================
    # 分发方法：run
    # ============================================================
    # ================================================== EML 经验记忆回路
    def _eml_prepare(self, question: str) -> dict:
        """**跑前**：recall（读）→ 决定生效面 → 留痕。返回 `{used_ids, applied}`。

        ★ 生效面只有两处（都属「调度/守卫阈值」，不碰答案）：
          · `rounds_plan`：截断过的层 +1 圈（`schedule/rounds_delta`）；
          · `self._duty_floor`：guard 类条目建议的阈值。
        ★ `mode == "shadow"` ⇒ 读出来**只留痕不生效**（F1 隔离；与 off 的差别
          只是「记录下我本来会怎么做」）。
        """
        _c = getattr(self, "_eml_cfg", None) or {}
        _mode = str(_c.get("mode", _EML_MODE_DEFAULT))
        self._eml_used = []
        self._eml_applied = []
        self._eml_mode = _mode
        if _mode == "off":
            return {"mode": _mode, "used_ids": [], "applied": []}
        _dir = Path(str(_c.get("dir") or eml_dir()))
        _pb = eml_read_jsonl(_dir / _EML_PLAYBOOK)
        _now = time.time()
        _h = float(_c.get("halflife_days", _EML_HALFLIFE_DAYS) or 14.0)
        _k = int(_c.get("top_k", _EML_TOP_K) or 3)
        _rec = []
        for _kind in _EML_KINDS:
            for _it in eml_recall(_pb, _kind, _now, halflife=_h, top_k=_k):
                _it["kind"] = _kind
                _rec.append(_it)
        _rec.sort(key=lambda x: -x["score"])
        self._eml_used = [{"id": x["id"], "kind": x["kind"],
                           "score": x["score"], "action": x["action"],
                           "applied": False} for x in _rec]
        return {"mode": _mode, "used_ids": [x["id"] for x in _rec],
                "applied": self._eml_applied}

    def _eml_apply(self, rounds_plan: dict) -> list:
        """把 recall 到的 active 条目落到**生效面**（仅 `mode=="on"`）。"""
        _applied = []
        if str(getattr(self, "_eml_mode", "off")) != "on":
            return _applied
        for _it in (getattr(self, "_eml_used", None) or []):
            _a = _it.get("action") or {}
            _key = str(_a.get("key") or "")
            if _key == "rounds_delta" and isinstance(rounds_plan, dict):
                _lyr = str(_a.get("layer") or "")
                _d = int(_a.get("delta", 1) or 1)
                if _lyr in rounds_plan:
                    _old = int(rounds_plan.get(_lyr) or 1)
                    rounds_plan[_lyr] = max(1, _old + _d)
                    _it["applied"] = True
                    _applied.append({"id": _it["id"], "key": _key,
                                     "layer": _lyr, "rounds": "%d→%d"
                                     % (_old, rounds_plan[_lyr])})
            elif _key == "duty_floor":
                _fl = _a.get("floor")
                try:
                    self._duty_floor = float(_fl)
                except (TypeError, ValueError):
                    continue
                _it["applied"] = True
                _applied.append({"id": _it["id"], "key": _key,
                                 "floor": self._duty_floor})
        self._eml_applied = _applied
        return _applied

    def _eml_note_use(self, _pb, result) -> dict:
        """**访问加强 + 执行留痕**（吸收 agentmemory / MemoryMCP），带一条闸。

        ★ 闸（防**自我强化**）：只有「本条**真生效**」且「本跑读数**达标**」
          才加强（`weight` / `t_last`）；否则只在 `used_outcomes` 记一笔负面。
          —— 用过 ≠ 有用；这正是「只升不降的指标是自欺」在记忆层的落点。
        ★ 对照：MemoryMCP「memory strength strengthens with access」，
          本实现加了「达标才加强」的限定；agentmemory 的 execution tracking
          对应 `used_outcomes`。
        """
        _used = [x for x in (getattr(self, "_eml_used", None) or [])
                 if x.get("applied")]
        if not _used:
            return {"strengthened": 0, "negative": 0}
        _ep = episode_from_result(result, t=time.time())
        _dmed = None
        _dv = []
        for _e in ("0", "1", "both", "all"):
            _s = ((result.get("views") or {}).get(_e) or {}).get("duty") or {}
            if _s.get("S") is not None:
                _dv.append(float(_s["S"]))
        if _dv:
            _dv.sort()
            _dmed = _dv[len(_dv) // 2]
        _ok = _dmed is not None and _dmed >= float(
            getattr(self, "_duty_floor", _DUTY_FLOOR))
        _n_pos = _n_neg = 0
        _ids = {x.get("id") for x in _used}
        for _e in (_pb or []):
            if _e.get("id") not in _ids:
                continue
            _e.setdefault("used_outcomes", []).append(
                {"run": _ep.get("run_id"), "duty_med": _dmed, "ok": bool(_ok)})
            _tu = list(_e.get("t_used") or [])
            if _ep.get("run_id") and _ep.get("run_id") not in _tu:
                _tu.append(_ep.get("run_id"))
            _e["t_used"] = _tu
            if _ok:
                _e["weight"] = min(1.0, float(_e.get("weight", 1.0) or 1.0)
                                   + 0.05)
                _e["t_last"] = float(time.time())
                _n_pos += 1
            else:
                _e["weight"] = max(0.1, float(_e.get("weight", 1.0) or 1.0)
                                   - 0.05)
                _n_neg += 1
        return {"strengthened": _n_pos, "negative": _n_neg,
                "duty_med": _dmed}


    def _eml_finish(self, result: dict) -> dict:
        """**跑后**：micro 反思 → 质量闸 → 合并（只增）→ meso 升级 → 遗忘 → 摘要。

        ★ 返回写进产物 `result["playbook"]` 的块（口径：读数 + 留痕，不是打分）。
        """
        _c = getattr(self, "_eml_cfg", None) or {}
        _mode = str(_c.get("mode", _EML_MODE_DEFAULT))
        _blk = {"mode": _mode, "used": list(getattr(self, "_eml_used", None) or []),
                "applied": list(getattr(self, "_eml_applied", None) or []),
                "candidates": [], "gated_out": [], "merged": [],
                "promoted": [], "retired": [], "parents": []}
        if _mode == "off":
            return _blk
        _lk = None
        try:
            _dir = Path(str(_c.get("dir") or eml_dir()))
            _dir.mkdir(parents=True, exist_ok=True)
            _now = time.time()
            _ep = episode_from_result(result, t=_now)
            _ep["used_ids"] = _blk["used"]
            # ★ [EML 闸 · 生产库清洁] **无 run_id 的跑次一律不写库**（连
            #   episode 也不写）：它当不了证据（evidence 会是空串），
            #   却会污染库、并可能混进后续统计。这类跑次 = 测试/半途/
            #   工具调用；真实跑次必有 id（app 层会写 `.run.json`）。
            #   显式要收匿名跑次时把 `playbook.learn_from_anon` 打开。
            _anon = not str(_ep.get("run_id") or "").strip()
            _learn_anon = bool(_c.get("learn_from_anon", False))
            if _anon and not _learn_anon:
                _blk["anon_skipped"] = True
                return _blk
            # ★ [并发正确性] 记忆库的读-改-写（episode 追加 + playbook 升级/遗忘/
            #   macro 整表重写）**必须互斥**：3 并发真跑时两个进程同时改会互相
            #   覆盖（丢条目/写坏行）。只保护**写库这一小段**，跑本身不受影响。
            _lk = eml_lock(dirpath=_dir)
            _lk.__enter__()
            eml_append_jsonl(_dir / _EML_EPISODES, _ep)
            _pb = eml_read_jsonl(_dir / _EML_PLAYBOOK)
            _n0 = len(_pb)
            _pn = int(_c.get("promote_n", _EML_PROMOTE_N) or 3)
            _cands = eml_candidates_from_result(result, ep=_ep)
            for _cd in _cands:
                _ok, _why = gate_check(_cd, _pb, promote_n=_pn)
                if not _ok:
                    _blk["gated_out"].append({"cand": _cd.get("action"),
                                              "why": _why})
                    # ★ [nogoods] 被闸拒的原因**留档**（append-only）——
                    #   矛盾/红线/无证据这三类如果只留在本次产物里，
                    #   下次没人知道它们发生过。
                    if _why in ("redline", "evidence", "verifiable",
                                "contradiction"):
                        eml_append_jsonl(
                            _dir / _EML_NOGOODS,
                            nogood_record("gate_reject", _why,
                                          _cd.get("action"), _ep.get("run_id"),
                                          _now))
                    continue
                _ent = eml_merge_candidate(_pb, _cd, _now)
                _blk["candidates"].append(_cd.get("action"))
                _blk["merged"].append(_ent.get("id"))
            _blk["promoted"] = eml_promote(_pb, promote_n=_pn)
            # ★ 访问加强（吸收 agentmemory / MemoryMCP；带「达标才加强」的闸）
            _blk["strengthen"] = self._eml_note_use(_pb, result)
            try:
                _st = _blk.get("strengthen") or {}
                if int(_st.get("negative", 0) or 0) > 0:
                    _nr = nogood_record(
                        "used_but_below_floor", "below_floor",
                        {"n": int(_st.get("negative", 0) or 0),
                         "duty_med": _st.get("duty_med")},
                        _ep.get("run_id"), _now)
                    eml_append_jsonl(_dir / _EML_NOGOODS, _nr)
            except Exception:
                pass
            _blk["retired"] = [e.get("id") for e in
                               eml_sweep_forget(_pb, _now, promote_n=_pn)]
            _blk["parents"] = eml_aggregate_macro(_pb, _now)
            # ★ 落盘两条路（F5「只增不删」的物理保证）：
            #   · 有新行 ⇒ 整表写（行数**只增**，写前断言不减少）；
            #   · 无新行 ⇒ 走 `eml_rewrite_jsonl`（它自断言行数/id 集合不变）。
            if len(_pb) > _n0:
                with (_dir / _EML_PLAYBOOK).open(
                        "w", encoding="utf-8", newline="\n") as _f:
                    for _r in _pb:
                        _f.write(json.dumps(_r, ensure_ascii=False) + "\n")
            elif len(_pb) == _n0:
                eml_rewrite_jsonl(_dir / _EML_PLAYBOOK, _pb)
            else:
                raise RuntimeError("EML 行数减少（%d→%d），违反只增不删"
                                   % (_n0, len(_pb)))
            eml_write_memory_md(_pb, dirpath=_dir)
            _blk["n_playbook"] = len(_pb)
            self.vp(f"\n🧠 EML：用 {len(_blk['used'])} 条（生效 "
                    f"{len(_blk['applied'])}）· 过闸新增 "
                    f"{len(_blk['merged'])} · 隔离 "
                    f"{len(_blk['gated_out'])} · 升级 {len(_blk['promoted'])} "
                    f"· 遗忘 {len(_blk['retired'])} · 库 {len(_pb)} 条")
        except Exception as _e:
            _blk["error"] = "%s: %s" % (type(_e).__name__, _e)
            self.vp(f"\n🧠 EML：异常（已留痕，不阻断）{_blk['error']}")
        finally:
            # ★ 锁必须在 finally 释放：中途异常若漏放，记忆库会被**卡住**
            #   （虽有 stale 回收兜底，但不该指望它）。
            if _lk is not None:
                try:
                    _lk.__exit__(None, None, None)
                except Exception:
                    pass
        return _blk

    def run(self, question: str,
            route: Optional[List[str]] = None,
            keep: Optional[Dict[str, str]] = None,
            rounds=0,
            channels: Optional[List[str]] = None,
            parallel_mode: str = "auto",
            orientation: str = "auto",
            auto_plan: Optional[dict] = None,
            run_id: str = "") -> dict:
        # ★ [EML 记账] `run_id` 只有**调用方显式给**才盖（app / 真跑脚本会传）。
        #   不给 ⇒ 产物无 id ⇒ EML 写库闸跳过（**测试/半途调用不许污染生产库**）。
        #   为什么必须显式：`run()` 自身不生成 id（id 原本在 `save_result` 才发），
        #   导致 CLI 真跑**永远拿不到 id ⇒ EML 从不学习真跑**（真跑逮到：
        #   `anon_skipped: true`）。这是「自学习闭环」的关键一环，缺了它跨跑学习
        #   只对 app 路径生效、对命令行真跑完全失效。
        self._run_id = str(run_id or "")
        route = route or ["0", "1", "both", "all"]
        self._ext_assess_cache = {}
        self._anchor_report = None
        self._anchor_source = {}
        self._load_anchors()
        self._web_gate, self._web_client = build_web_search(self.config)
        self._web_prep_seq = 0
        # ★ 统一调度器给的 plan（逐项来源留痕）；没给则沿用旧路径。
        self._auto_plan_spec = auto_plan if isinstance(auto_plan, dict) else None
        _ai = ((self._auto_plan_spec or {}).get("_items") or {})
        if orientation == "auto" and _ai.get("orientation", {}).get(
                "source") == "auto":
            orientation = str((self._auto_plan_spec or {}).get("orientation")
                              or "auto")
        _dec_probe = True
        if _ai.get("decidability", {}).get("source") == "auto":
            _dec_probe = bool((self._auto_plan_spec or {}).get("decidability"))
        self._orientation = str(orientation or "auto")
        route = self._route_by_decidability(question, route, orientation,
                                            allow_probe=_dec_probe)
        keep = keep or {k: "all" for k in route}
        if channels is not None:
            self.channels = tuple(MemoryChannel.check(c) for c in channels)
        self._mcfg["channels"] = list(self.channels)

        self._dispatch_plan = self._plan_dispatch(route)
        self._failed_layers: Dict[str, str] = {}
        self.decidability_result = {}

        # [自动调度] 模式**和**圈数都没指定 → 一次调用全定下来。
        # 只指定了其中一个 → 尊重用户，退回单目标决策（只定模式）。
        self._auto_plan_used = None
        if self._auto_plan_spec is not None and _ai.get("mode", {}).get(
                "source") == "auto" and parallel_mode == "auto":
            mode = str((self._auto_plan_spec or {}).get("mode") or "serial")
            if mode == "llm":
                decision = self._decide_parallel_mode(question)
                mode = decision["mode"]
                self.vp(f"\n🧵 并行模式自动决策：{mode}"
                        f"（{decision['reason']}，"
                        f"置信 {decision['confidence']:.2f}）")
            else:
                self.vp(f"\n🧭 自动调度：模式 {mode}"
                        f"（{_ai['mode'].get('reason', '')}）")
            self._auto_plan_used = dict(self._auto_plan_spec)
            if not rounds:
                rounds = (self._auto_plan_spec or {}).get("rounds") or 0
        elif parallel_mode == "auto" and not rounds:
            plan = self._auto_plan(question)
            self._auto_plan_used = plan
            mode = plan["mode"]
            rounds = plan.get("rounds") or 0
            self.vp(f"\n🧭 自动调度：模式 {mode}"
                    f"（{plan.get('reason', '')}，"
                    f"置信 {plan.get('confidence', 0):.2f}）")
            if plan.get("rounds"):
                _r = "／".join(
                    f"{_LAYER_LABEL.get(k, k)}{v}圈"
                    for k, v in plan["rounds"].items())
                self.vp(f"   圈数：{_r}（层内到点会自然停，非跑满）")
        elif parallel_mode == "auto":
            decision = self._decide_parallel_mode(question)
            mode = decision["mode"]
            self.vp(f"\n🧵 并行模式自动决策：{mode}"
                    f"（{decision['reason']}，"
                    f"置信 {decision['confidence']:.2f}）")
        else:
            mode = parallel_mode if parallel_mode in (
                "serial", "A", "B", "C", "D", "E", "F", "G",
                "H") else "serial"
            self.vp(f"\n🧵 并行模式：{mode}（用户指定）")

        rounds_plan = self._rounds_plan(rounds)
        # ★ [EML] 跑前：读记忆（recall）→（仅 mode=on）落到生效面 → 留痕。
        try:
            self._eml_prepare(question)
            self._eml_apply(rounds_plan)
        except Exception as _ee:
            self.vp(f"\n🧠 EML 读记忆异常（不阻断）：{_ee}")
        self._parallel_mode = mode

        # [P1-6] 输入健全性自检：P=PN 这一步就该被说出来
        self._input_sanity = self._check_input_sanity(question)
        if self._input_sanity.get("issues"):
            self.vp(f"\n{'!'*60}")
            self.vp("❓ 输入自检：问题里的符号可能有歧义或笔误")
            for _it in self._input_sanity["issues"]:
                self.vp(f"   · {_it['term']} — {_it['why']}")
            self.vp(f"{'!'*60}")
            if self._input_sanity.get("note"):
                self.vp(f"   {self._input_sanity['note']}")

        if mode == "A":
            packed = self._run_parallel_A(question, route, keep,
                                          rounds_plan, channels)
        elif mode == "B":
            packed = self._run_parallel_B(question, route, keep,
                                          rounds_plan, channels)
        elif mode == "C":
            packed = self._run_parallel_C(question, route, keep,
                                          rounds_plan, channels)
        elif mode in _MODE_GRAPH:
            packed = self._run_parallel_stage(mode, question, route,
                                              keep, rounds_plan, channels)
        else:
            packed = self._run_serial(question, route, keep,
                                      rounds_plan, channels)
        if isinstance(packed, dict):
            packed["cost_profile"] = getattr(
                self, "_cost_profile", "balanced")
            packed["orientation"] = orientation
        if isinstance(packed, dict) and self._input_sanity:
            packed["input_sanity"] = self._input_sanity
        if isinstance(packed, dict) and not packed.get("decidability"):
            self._assess_decidability_dynamic(
                question, self._results.get("0"))
            packed["decidability"] = self.decidability_result
        if isinstance(packed, dict):
            self._layer_guard(packed)
        # ★ [EML] 跑后：写 episode + 抽候选 + 过闸 + 只增合并 + 升级 + 遗忘。
        if isinstance(packed, dict):
            # ★ [EML 记账] 把显式 run_id 盖进产物（**必须在 `_eml_finish` 之前**：
            #   episode 的 run_id 就是从这里读的；晚盖 = 这一跑又被当匿名丢掉）。
            _rid = str(getattr(self, "_run_id", "") or "").strip()
            if _rid and not str(packed.get("id") or "").strip():
                packed["id"] = _rid
            try:
                packed["playbook"] = self._eml_finish(packed)
            except Exception as _ef:
                packed["playbook"] = {"error": "%s: %s"
                                      % (type(_ef).__name__, _ef)}
        return packed


    # ---------------------------------------------------------- 检索适配层
    def _anchor_round(self, entry: str, pool: "Pool", rno: int) -> None:
        """ 本圈检索 → 锚点入池。

        ★ 当前 `retriever="snapshot"` **零额外调用**：锚点已在 run 开头
          一次性读进来（`_load_anchors`），这里只按 `per_round` 配额**分圈
          投放**，模拟"逐步检索"的节奏，顺便让不同圈看到不同锚点。

        ★ 锚点有两个来源，按 `retriever` 分流：
          · `snapshot`（默认）：锚点在 run 开头一次性读进来（`_load_anchors`），
            这里只按 `per_round` 配额**分圈投放**；
          · 其它取值（当前实现 `tavily`）：本圈先按池内问题**真检索**
            （`_retrieve_anchors` → `AnchorRetriever`，结果并进 `self._anchors`），
            再走同一套配额投放。失败**一律留痕**，不静默降级。

        ★ **早退条件里不再要求「已有锚点」**：原来 `not self._anchors` 挡在最前，
          而 `_retrieve_anchors` 就在它**后面** —— 于是真检索只有在**先挂了快照
          文件**时才可能被调用；没挂文件时连「后端未实现」的留痕都发生不了
          （承诺了「非 snapshot 抛错留痕」，实际上够不到）。现在这一项移到
          模式分流**之后**：snapshot 模式仍要求已读入锚点；真检索模式自己填。

        ★ 与 `web_search` 的分工（**别混**）：`web_search` 收的进
          `pool.web_results`，是喂给各层的**证据**（`used_as`）；本函数入的是
          `pool.anchors`，是收尾「结论 vs 外部事实」对照的**标尺**。
          两者互不喂 —— 拿本次喂进层里的东西回头量层的结论，是自证不是校验。

        元层（all）不检索 —— 它的活是清算，不是核对。
        """
        cfg = self.config.get("external_anchor") or {}
        if not cfg.get("enabled") or entry == "all":
            return
        per = int(cfg.get("per_round", 2) or 0)
        if per <= 0:
            return
        _mode = str(cfg.get("retriever") or "snapshot").strip().lower()
        if _mode != "snapshot":
            try:
                queries = self._build_anchor_queries(entry, pool)
                self._retrieve_anchors(queries)
            except Exception as exc:
                # 宪法级：失败必须留痕，不静默跳过
                self._anchor_err = f"锚点检索失败（第 {rno + 1} 圈）：{exc}"
                logger.warning("外部锚点检索失败：%s", exc)
                pool.meta.append(f"[外部锚点] 检索失败：{exc}")
                return
        # ★ 到这里 `self._anchors` 的来源已经定：snapshot 读进来的，或上面
        #   真检索刚并进来的。两边都空 = 本圈没事可做。
        if not self._anchors:
            return
        already = {str(a.get("id")) for a in (pool.anchors or [])}
        rest = [a for a in self._anchors
                if str(a.get("id")) not in already]
        picked = rest[:per]
        for a in picked:
            pool.anchors.append(dict(a))
        pool._anchor_cfg = dict(cfg)
        _ae_tier = _anchor_tier(cfg)
        pool.anchor_as_evidence = _ae_tier in ("evidence", "gate")
        if picked:
            pool.meta.append(
                f"[外部锚点] 第 {rno + 1} 圈入池 {len(picked)} 条"
                f"（累计 {len(pool.anchors)}，"
                f"{'作证据' if pool.anchor_as_evidence else '仅记录'}）")
        self.vp(f"   ⚓ 锚点入池 +{len(picked)}"
                f"（累计 {len(pool.anchors)}）")

    def _build_anchor_queries(self, entry: str, pool: "Pool") -> List[str]:
        """ 本圈"该查什么"。

        按评审建议，query 从池里现成的东西取，不额外造：
          · 研究层(1)：sub_questions 里 status=open 的前 2 条
          · 对撞层(both)：未清偿债务的 revisit_condition（"缺什么"就是 query）
          · 修行层(0)：probes / 悬空线头
        snapshot 模式下这些 query **不发起调用**，只留痕（将来接真检索时
        接口已经在这里了）。
        """
        out: List[str] = []
        if entry == "1":
            for sq in (pool.sub_questions or []):
                if str(sq.get("status", "")).lower() in ("open", ""):
                    q = str(sq.get("question", "")).strip()
                    if q:
                        out.append(q)
                if len(out) >= 2:
                    break
        elif entry == "both":
            for d in (pool.deferrals or []):
                if d.get("status") == "deferred":
                    q = str(d.get("revisit_condition", "")).strip()
                    if q:
                        out.append(q)
                if len(out) >= 2:
                    break
        else:
            for p in (pool.probes or [])[:2]:
                q = str(p.get("question", "")).strip()
                if q:
                    out.append(q)
        return out

    def _retrieve_anchors(self, queries: List[str]) -> List[dict]:
        """ 检索适配层。

        ★ 当前**只有一个真实现**：`snapshot`。其它取值抛错留痕，
          不静默降级 —— 留给将来接真搜索 API 的接口位，但现在不假装。
        """
        cfg = self.config.get("external_anchor") or {}
        mode = str(cfg.get("retriever") or "snapshot").strip().lower()
        if mode == "snapshot":
            return list(self._anchors or [])
        import os as _os
        _env = str(cfg.get("api_key_env") or "TAVILY_API_KEY")
        _r = AnchorRetriever(mode, _os.environ.get(_env, ""),
                             int(cfg.get("cache_ttl_hours", 24) or 24))
        got = _r.search(queries or [], int(cfg.get("max_items", 12) or 12))
        if got:
            # 检索到的锚点并入本 run 的锚点池；tier 缺省 3（二手转述）。
            for _a in got:
                _a.setdefault("tier", 3)
            self._anchors = list(self._anchors or []) + got
        return got

    def _anchor_pooled_total(self) -> int:
        """本次各层池子里累计入池的锚点条数（不去重，如实报）。"""
        n = 0
        for p in (self.pools or {}).values():
            n += len(getattr(p, "anchors", None) or [])
        return n

    def _anchor_triage_sys(self) -> str:
        """ **空壳**，永远返回空串。

        原先这里返回分诊判据段，被拼进 `_assess_decidability_from_pool_view`
        的 **system**；而"分诊判据"要生效，模型必须同时看到 user 段里的
        锚点清单，于是 user 段写了句"按上面的分诊判据处理"—— 跨段引用，
        模型两段看到的顺序并不保证。

        现在判据整段挪到 `_anchor_view_ctx`（user 段），与锚点清单同处一
        段，不再有跨段引用。这个方法**保留**只为兼容外部脚本对它的调用，
        不删。
        """
        return ""

    def _anchor_view_ctx(self) -> str:
        """ 摊进池判 prompt 的锚点块（空串 = 一个字都不加）。

        ★ [B2] **可见性说清**：池判
          （`_assess_decidability_from_pool_view`）在一次运行里**只跑一次**
          （评估阶段），读的是**当时**的池 —— 也就是**第 1 圈结束后的
          状态**。所以哪怕 `per_round=2`、后面几圈还在继续入池，池判看到
          的永远是最早那 2 条（受 `max_items` 上限约束）。
          这不是 bug，是"评估先于展开"的结构决定的；写在这里免得下次
          有人以为"分圈投放 = 池判能看到全部"。

        ★ [B5] 分诊判据**挪到本段**（原来在 system 段，靠 user 段的
          "按上面的判据处理"跨段引用）。判据与锚点清单同段，模型一次读完。
        """
        cfg = self.config.get("external_anchor") or {}
        if not cfg.get("enabled"):
            return ""
        pool = (self.pools or {}).get("0")
        anchors = getattr(pool, "anchors", None) or []
        if not anchors:
            return ""
        lines = "\n".join(
            f"  X{i}: {str(a.get('claim', ''))[:100]}"
            f"（源：{str(a.get('source', ''))[:40]}）"
            for i, a in enumerate(anchors[:10], 1))
        body = ("\n\n【外部锚点（本圈已入池 "
                + str(len(anchors)) + " 条）】\n" + lines)
        if cfg.get("triage"):
            body += (
                "\n\n【分诊判据（triage=on）】\n"
                "若一条 undecidable 的理由是「信息不足 / 需外部动作」，\n"
                "而上面【外部锚点】里**有**能回答它的材料 → 该条不算\n"
                "不可判定，降为 decidable 或 partial。\n"
                "若理由是「自指循环 / 无共同参照系 / 本体论判断」 → 检索\n"
                "无关，**保持 undecidable**，不许降级。\n"
                "★ 只在这两种情况里动；其余一律不动。\n")
        else:
            body += ("\n（这些锚点**仅作对照**，你不必迁就它们；"
                     "判据仍以池内形状为准）")
        return body

    def _load_anchors(self) -> List[dict]:
        """ 读外部锚点快照（一次 run 只在开头调一次）。

        ★ 为什么是「读文件」而不是「引擎自己联网」：引擎没有联网能力
          （v9.1 的 web_search / external_facts 在 v1.21 重写后是 0 处
          引用，v1.21.61 已核过）。与其假装联网，不如把外部事实**显式
          落盘**再读 —— 每条锚点带来源、URL 与检索时刻，可复现、可核对、
          可事后逐条复查。
        ★ 失败一律留痕：读不到 / 结构不对 / 空列表都写 `self._anchor_err`，
          日志与产物都会印出来。★ 不静默降级成「没接入」—— 那正是本
          项目反复踩的坑（看着像没接，其实是接了但失败了）。
        """
        cfg = self.config.get("external_anchor") or {}
        self._anchors = []
        self._anchor_err = ""
        # ★ 「开着但没挂文件」= 独立状态（默认打开后这是**最常见**的一次运行）。
        self._anchor_unconfigured = False
        self._anchor_answers_warning = ""
        self._anchor_tier_warning = ""
        self._anchor_answers_filtered = ""
        if not cfg.get("enabled"):
            return self._anchors
        path = str(cfg.get("path") or "").strip()
        max_items = int(cfg.get("max_items", 12) or 12)
        if not path:
            # ★ 通道开着但没挂文件 —— **不是错误**：记 error 会让每一次默认
            #   运行都写「⚠️ 接入失败」，把「没挂文件」读成「接失败了」。
            #   ★ 但只有 **snapshot** 模式才叫「未挂文件」：真检索模式
            #     （retriever 非 snapshot）本来就不读文件，它是**已配置**的。
            _mode0 = str(cfg.get("retriever") or "snapshot").strip().lower()
            if _mode0 == "snapshot":
                self._anchor_unconfigured = True
                logger.info("外部锚点：已开启但未配置 path（未挂锚点文件）")
            else:
                logger.info("外部锚点：retriever=%s —— 不读快照文件，按圈真检索",
                            _mode0)
            return self._anchors
        try:
            p = Path(path)
            if not p.is_absolute():
                p = Path.cwd() / p
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            self._anchor_err = ("锚点文件读取失败：" + type(exc).__name__
                                + ": " + str(exc)[:200])
            logger.warning("外部锚点加载失败：%s", self._anchor_err)
            return self._anchors
        if not isinstance(data, dict):
            self._anchor_err = "锚点文件顶层不是对象"
            logger.warning("外部锚点加载失败：%s", self._anchor_err)
            return self._anchors
        raw = data.get("anchors")
        if not isinstance(raw, list) or not raw:
            self._anchor_err = "锚点文件里 anchors 不是非空列表"
            logger.warning("外部锚点加载失败：%s", self._anchor_err)
            return self._anchors
        self._anchor_source = {
            "file": p.name,
            "retrieved_at": str(data.get("retrieved_at") or "")[:40],
            "retriever": str(data.get("retriever") or "")[:80],
        }
        out: List[dict] = []
        _n_explicit_tier = 0
        _n_declared_ans = 0
        _n_dropped_ans = 0
        _min_len = int(cfg.get("answers_min_len", 6) or 0)
        _max_n = int(cfg.get("answers_max_n", 5) or 5)
        for i, a in enumerate(raw[:max_items], 1):
            if not isinstance(a, dict):
                continue
            claim = str(a.get("claim") or "").strip()
            if not claim:
                continue
            try:
                _t = int(a.get("tier", 3) or 3)
            except (TypeError, ValueError):
                _t = 3
            if str(a.get("tier") if a.get("tier") is not None else "").strip():
                _n_explicit_tier += 1
            _raw_ans = a.get("answers") or []
            if isinstance(_raw_ans, list) and _raw_ans:
                _n_declared_ans += 1
            _ans_kept: List[str] = []
            _ans_dropped: List[str] = []
            for _x in (_raw_ans if isinstance(_raw_ans, list) else []):
                _sx = str(_x).strip()
                if not _sx:
                    continue
                if _min_len > 0 and len(_sx) < _min_len:
                    _ans_dropped.append(_sx[:30])
                    _n_dropped_ans += 1
                    continue
                _ans_kept.append(_sx[:60])
                if len(_ans_kept) >= _max_n:
                    break
            out.append({"id": str(a.get("id") or ("a" + str(i))),
                        "tier": max(1, min(4, _t)),
                        "claim": claim[:400],
                        "answers": _ans_kept,
                        "_answers_dropped": _ans_dropped,
                        "source": str(a.get("source") or "")[:200],
                        "url": str(a.get("url") or "")[:300],
                        "as_of": str(a.get("as_of") or "")[:40],
                        "kind": str(a.get("kind") or "")[:40]})
        self._anchors = out
        _n_no_ans = len(out) - _n_declared_ans
        if out and _n_no_ans == len(out):
            self._anchor_answers_warning = (
                "全部 " + str(len(out)) + " 条锚点未声明 answers，triage 只能走"
                " claim 路径（历史实测：claim 路径对「缺什么」型侧面命中率"
                " ≈ 0）")
            logger.warning("锚点 answers 全部缺失：%s",
                           self._anchor_answers_warning)
        else:
            self._anchor_answers_warning = ""
        if _n_dropped_ans:
            self._anchor_answers_filtered = (
                str(_n_dropped_ans) + " 条 answer 因短于 "
                + str(_min_len) + " 字被丢弃"
                "（overlap_coef 分母取 min，短 answer 会产生假命中）")
            logger.warning("锚点 answers 过滤：%s",
                           self._anchor_answers_filtered)
        else:
            self._anchor_answers_filtered = ""
        if out and _n_explicit_tier == 0:
            self._anchor_tier_warning = (
                "全部 " + str(len(out)) + " 条锚点未显式声明 tier（缺省 3 > "
                "tier_floor " + str(_tier_floor(cfg)) + "），引用表将收不到任何"
                "锚点")
            logger.warning("锚点 tier 全部缺省：%s", self._anchor_tier_warning)
        else:
            self._anchor_tier_warning = ""
        if not out:
            self._anchor_err = ("锚点文件里 " + str(len(raw))
                                + " 条全部缺 claim")
            logger.warning("外部锚点加载失败：%s", self._anchor_err)
        else:
            self.vp("\n⚓ 外部锚点：载入 " + str(len(out)) + " 条（"
                    + p.name + "）")
        return out

    def _anchor_claims(self, results) -> List[str]:
        """ 收集本次要拿去对照的**结论条目**（只读，不改任何池）。

        ★ M1 根因（v1.21.73/74/75 三轮、6 道题实测）：原来只取两处 ——
          各层 view 的 `decidable_product.answer` 与研究池里 answered 的
          子问题。这两处产出的全是**认识论层**的句子（"序关系能否单独
          裁决""能否用现有记录做区间估计"），而锚点在**领域事实层**
          （回本周期、稼动率红线、GDPR 条款）。两者永远不同层 ——
          所以 6/6 题、32 条 claims 全部判「无对应」，`anchor_used` 全 0。
          **那不是锚点没用，是抽取器取错了地方。**

          引擎真正的领域论断在 `views[*].candidates` 里（探索实测：同一份
          已跑完的 packed、同一份锚点、同一把尺，只换取值处 ——
          沾边 0/5 → 7/12，用到锚点 0 → 9/12）。

        ★ 口径变更声明：这是 **M1 口径变更**，会改变对照结果，按项目预
          注册纪律单独记录（`_anchor_prereg.json`）。candidates 排在
          最前 —— 它们是领域层，优先占满 `[:12]` 的配额。

        ★ [v1.21.77 M1'] 而 candidates **内部**还要按层排序：**层 0 优先**。
          v1.21.76 把层 1 排最前，12 条配额全被研究层的操作性论断占满，
          后来实测「印证 0 / 用到锚点 0」。换成层 0 优先后，同样一份打包
          数据、同一把尺，变成「印证 4 / 用到锚点 3」。
          根因不是「引擎不产领域论断」，是**取值优先级排反了**。

        取三处（candidates 优先）：
          1. `views[*].candidates[].desc` —— 领域论断（本次新增）
          2. `views[*].decidable_product.answer` —— 成品答案
          3. 研究池 sub_questions 里 status=answered 的
        都空就返回空列表，产物里写「本次没有可对照的结论条目」。
        """
        out: List[str] = []
        for k in ("0", "1", "both", "all"):
            v = (results or {}).get(k)
            if v is None:
                continue
            for c in (getattr(v, "candidates", None) or []):
                if not isinstance(c, dict):
                    continue
                d = str(c.get("desc") or "").strip()
                if d:
                    out.append(d[:300])
        for k in ("1", "both", "all", "0"):
            v = (results or {}).get(k)
            if v is None:
                continue
            dp = getattr(v, "decidable_product", None) or {}
            ans = str(dp.get("answer") or "").strip()
            if ans:
                out.append(ans[:300])
        rp = (self.pools or {}).get("1")
        subs = getattr(rp, "sub_questions", None) or []
        for sq in subs:
            if isinstance(sq, dict) and sq.get("status") == "answered":
                q = str(sq.get("question") or "").strip()
                if q:
                    out.append(q[:300])
        seen = set()
        uniq = []
        for c in out:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        return uniq[:12]

    def _anchor_crosscheck(self, results) -> dict:
        """ 收尾只读对照：本次结论条目 vs 外部锚点。

        ★ 只读：不写回任何 view / pool / settlement，不改判定。它回答的是
          「本次跑出来的结论，与外部事实对得上吗」—— 这是 v1.21.63 那句
          承认回答不了的问题。
        ★ 一次 LLM 调用，只在「开启 + 有锚点 + 有可对照条目」时发生。
        """
        base = {
            "enabled": True,
            "anchors": len(self._anchors or []),
            "source_file": (self._anchor_source or {}).get("file", ""),
            "retrieved_at": (self._anchor_source or {}).get("retrieved_at", ""),
            "retriever": (self._anchor_source or {}).get("retriever", ""),
            "answers_all_missing": bool(getattr(
                self, "_anchor_answers_warning", "")),
            "answers_filtered": str(getattr(
                self, "_anchor_answers_filtered", "") or ""),
            "pooled": self._anchor_pooled_total(),
            "unconfigured": bool(getattr(
                self, "_anchor_unconfigured", False)),
            # ★ 有效检索模式（配置里那个）—— 渲染要用它区分「文件」与「真检索」。
            "retriever_mode": str(
                ((self.config.get("external_anchor") or {})
                 .get("retriever") or "snapshot")).strip().lower(),
            "as_evidence": _anchor_tier(
                self.config.get("external_anchor") or {}),
            "anchor_calls": int(getattr(self, "_anchor_calls", 0) or 0),
            "claims": 0,
            "items": [],
            "summary": {"claims": 0, "supported": 0, "conflicted": 0,
                        "unmatched": 0, "anchor_used": 0},
            "error": self._anchor_err or "",
        }
        if not self._anchors:
            # ★ unconfigured 有它自己的渲染文案 ⇒ 不塞「没有可用锚点」兜底，
            #   否则「未挂文件」会被读成一种失败。
            if not base["error"] and not base["unconfigured"]:
                base["error"] = "没有可用锚点（未开启或加载失败）"
            return base
        claims = self._anchor_claims(results)
        base["claims"] = len(claims)
        if not claims:
            base["error"] = ("本次没有可对照的结论条目（成品答案与已答"
                             "子问题都为空）")
            self.vp("\n⚓ 外部锚点：本次无结论条目可对照（不假装对照过）")
            return base
        if not (self.config.get("external_anchor") or {}).get("crosscheck", True):
            base["error"] = "crosscheck 已关闭，只载入锚点不做对照"
            return base
        _b = int(getattr(self, "_call_budget", 0) or 0)
        if _b > 0 and int(getattr(self.llm, "total_calls", 0) or 0) >= _b:
            base["error"] = ("收尾对照跳过：预算已用尽（"
                             + str(getattr(self.llm, "total_calls", 0))
                             + "/" + str(_b) + "）")
            self.vp("\n⚓ 外部锚点：" + base["error"])
            return base
        a_lines = []
        for a in self._anchors:
            ln = "- [" + str(a.get("id")) + "] " + str(a.get("claim"))
            if a.get("source"):
                ln = ln + "（来源：" + str(a.get("source")) + "）"
            a_lines.append(ln)
        c_lines = []
        for i, c in enumerate(claims, 1):
            c_lines.append("- [c" + str(i) + "] " + c)
        system = """你是【外部事实对照者】。

你会拿到两组材料：一组是本次运行产出的结论条目，一组是运行前由外部检索得到的真实事实（外部锚点）。你的任务是把两组对起来，逐条给判定。

判定只有三种，不许给第四种：
- 印证：锚点里有条目支持它（把编号填进 anchor_ids）
- 冲突：锚点里有条目与它相反、或使它不成立（把编号填进 anchor_ids）
- 无对应：锚点里没有能支持也没有能反驳它的条目（anchor_ids 给空列表）

【判据】
- 只在锚点条目**直接**支持或反驳时才判印证 / 冲突；沾不上边就判无对应。不要因为"大致相关"就判印证 —— 那会把对照变成奉承。
- note 写一两句理由，说明用的是哪条锚点的什么内容。判无对应也要写（写"锚点未涉及 X"之类）。
- 一条结论最多引 3 条锚点，编号必须来自下面给出的锚点列表，不许自造。

严格 JSON：
{
  "items": [
    {"claim_id": "c1", "verdict": "印证|冲突|无对应", "anchor_ids": ["a1"], "note": "40字内"}
  ]
}
"""
        user = ("【本次结论条目（" + str(len(claims)) + " 条）】\n"
                + "\n".join(c_lines)
                + "\n\n【外部锚点（" + str(len(self._anchors)) + " 条）】\n"
                + "\n".join(a_lines)
                + "\n\n逐条给判定，严格 JSON。")
        self._anchor_calls = int(getattr(self, "_anchor_calls", 0) or 0) + 1
        base["anchor_calls"] = self._anchor_calls
        try:
            raw = self.llm.call(system, user, 0.2, 1800, json_mode=True,
                                stage="anchor_crosscheck")
        except Exception as exc:
            base["error"] = ("对照调用失败：" + type(exc).__name__ + ": "
                             + str(exc)[:200])
            logger.warning("外部锚点对照失败：%s", base["error"])
            return base
        data = self.llm.parse_json(raw)
        if not isinstance(data, dict):
            base["error"] = "对照返回的不是对象"
            return base
        raw_items = data.get("items")
        if not isinstance(raw_items, list):
            base["error"] = "对照返回缺 items 列表"
            return base
        cmap = {}
        for i, c in enumerate(claims, 1):
            cmap["c" + str(i)] = c
        used = set()
        sup = 0
        con = 0
        unm = 0
        items: List[dict] = []
        valid = set(str(a.get("id")) for a in self._anchors)
        for it in raw_items[:24]:
            if not isinstance(it, dict):
                continue
            cid = str(it.get("claim_id") or "").strip()
            if cid not in cmap:
                continue
            verdict = str(it.get("verdict") or "").strip()
            if verdict not in ("印证", "冲突", "无对应"):
                verdict = "无对应"
            ids = [str(x)[:20] for x in (it.get("anchor_ids") or [])[:3]
                   if isinstance(x, str)]
            ids = [x for x in ids if x in valid]
            used.update(ids)
            if verdict == "印证":
                sup += 1
            elif verdict == "冲突":
                con += 1
            else:
                unm += 1
            items.append({"claim_id": cid, "claim": cmap[cid][:200],
                          "verdict": verdict, "anchor_ids": ids,
                          "note": str(it.get("note") or "")[:160]})
        covered = set(i["claim_id"] for i in items)
        for cid, c in cmap.items():
            if cid not in covered:
                unm += 1
                items.append({"claim_id": cid, "claim": c[:200],
                              "verdict": "无对应", "anchor_ids": [],
                              "note": "对照未覆盖该条目（判据缺失，不是无冲突）"})
        _tier_c = _anchor_tier(self.config.get("external_anchor") or {})
        _floor_c = _tier_floor(self.config.get("external_anchor") or {})
        _pv1 = results.get("1") if isinstance(results, dict) else None
        _blocked: List[str] = []
        for _it in items:
            if _it.get("verdict") != "冲突":
                continue
            _ids = "、".join(_it.get("anchor_ids") or []) or "?"
            if _pv1 is not None:
                try:
                    _pv1.errors.append("锚点冲突：" + str(_it.get("claim_id"))
                                       + " ↔ " + _ids)
                except Exception:
                    pass
            try:
                self.pools["1"].meta.append(
                    "[锚点冲突] " + str(_it.get("claim_id")) + " ↔ " + _ids)
            except Exception:
                pass
            if _tier_c == "gate":
                _blocked.append(str(_it.get("claim_id")))
        _und_aspects = ((self.decidability_result or {}).get(
            "undecidable_aspects") or [])
        _tg: List[dict] = _triage_suggestions(
            _und_aspects, self._anchors, {"tier_floor": _floor_c})
        base["tier_floor"] = _floor_c
        base["triage_downgrades"] = len(_tg)
        base["triage_items"] = _tg
        base["blocked_conclusions"] = _blocked
        base["items"] = items
        base["summary"] = {"claims": len(claims), "supported": sup,
                           "conflicted": con, "unmatched": unm,
                           "anchor_used": len(used)}
        self.vp("\n⚓ 外部锚点对照：结论 " + str(len(claims)) + " 条 —— 印证 "
                + str(sup) + " / 冲突 " + str(con) + " / 无对应 " + str(unm)
                + "（用到锚点 " + str(len(used)) + "/" + str(len(self._anchors))
                + "）")
        return base

    def _anchor_report_for_pack(self, results):
        """ 打包时决定要不要挂 `external_anchor` 键。

        ★ 只在配置开启时返回 dict（哪怕失败也返回 —— 失败是必须留痕的
          状态）；关闭时返回 None，packed 与 v1.21.72 逐字同构。
        """
        if not (self.config.get("external_anchor") or {}).get("enabled"):
            return None
        if self._anchor_report is not None:
            return self._anchor_report
        self._anchor_report = self._anchor_crosscheck(results)
        return self._anchor_report

    def _cached_ext_assess(self, question: str) -> dict:
        """ 同题的外部可判定性评估，一次运行内只跑一次。

        ★ 为什么需要：`_route_by_decidability`（开跑前定 route）与
          `_assess_decidability_dynamic`（研究层拆解时读池）各自要一次
          **同题同配置**的外部评估，改前一次 run 打两次 API。
        ★ 边界：
          · 只在本实例的**一次 run** 内有效 —— `run()` 开头重置缓存；
          · 失败**不缓存**：`_assess_decidability` 抛异常时原样上抛，
            由两个调用点各自的 except 处理（行为与改前一致）；
          · 外判结果是 (问题, 配置) 的函数，与池内容无关，所以复用
            不会拿到"过期的池形状"（池那条走的是
            `_assess_decidability_from_pool_view`，不在本缓存里）。
        """
        cache = getattr(self, "_ext_assess_cache", None)
        if cache is None:
            cache = {}
            self._ext_assess_cache = cache
        key = (question or "").strip()
        if key in cache:
            return cache[key]
        d = DGTF("1", self.llm, self.config)
        d.verbose = False
        res = d._assess_decidability(question,
                                     anchors=getattr(self, "_anchors", None))
        cache[key] = res
        return res

    def _route_by_decidability(self, question: str,
                               route: List[str],
                               orientation: str = "auto",
                               allow_probe: bool = True) -> List[str]:
        """ 前置判定：判据从"能不能判"改成"想要什么"。

        「能不能判」是效率判据；「想要什么」才是显化判据。
          · boundary（要边界清单）→ 无论能不能判，跑全四层；
            因为"边界"这件事只有对撞/元层会认真做。
          · decision（要可落地方案）→ 允许按可判定性砍层（旧逻辑）。
          · auto（默认）→ 取向未明时按 decision 处理，但如实留痕。

        ⚠️ 已知波动：外部判定 temperature=0.2，实测有误判。降 route 是
          优化不是正确性要求，接受波动，不为它加脆弱的字符串匹配。
        """
        if not route or len(route) <= 2:
            return route
        _o = (orientation or "auto").strip().lower()
        if _o not in ("auto", "boundary", "decision"):
            _o = "auto"

        if _o == "boundary":
            self.vp("\n📐 取向=boundary（要边界清单）"
                    "→ 保留全四层（边界只有对撞/元层会认真做）")
            return route

        if not allow_probe:
            self.vp("\n📐 可判定性判定被 auto 关闭（事实型短题：层集合已按"
                    "题型定，不花那次外部评估）→ 保留当前 route")
            return route

        if _o == "auto":
            self.vp("\n   ⚠️ 取向未指定：路由按 decision 处理"
                    "（可显式传 orientation=boundary 保留全四层）；"
                    "落地层模板另按题面有无决策语境分流")
            _o = "decision"

        # _o == "decision"
        try:
            ext = self._cached_ext_assess(question)
        except Exception as e:
            logger.warning("决策取向下的可判定性评估失败，保留全 route：%s",
                           e)
            return route
        if str(ext.get("decidability", "")).lower() == "undecidable":
            dropped = [k for k in route if k not in ("0", "1")]
            self.vp(f"\n📉 取向=decision 且外判 undecidable，"
                    f"route {route} → [0,1]（降 {dropped}；"
                    f"§7.16 砍层省一半且质量打平）")
            return ["0", "1"]
        return route


    def _check_input_sanity(self, question: str) -> dict:
        """[P1-6] 检查问题字符串里有没有未定义／疑似笔误的符号。

        22:50 那次跑的是 `P=PN`：PN 不是任何标准复杂度类，引擎不知道，
        于是把「PN 读法未定」当成核心议题，认认真真跑了 4 层 × 168 次调用。
        宪法允许它诚实地说「此处未生」，但不该在第一步就把一个可能是笔误的
        符号当成合法对象收下。

        只报告，不改写：替用户改写他的问题等于替他决定想问什么。
        """
        if not _action_on(self.config, "input_sanity"):
            return {}
        system = (
            "你是【输入检查者】。\n"
            "只看这一个字符串，判断里面有没有**悬空符号**：\n"
            "- 未定义的缩写、疑似笔误的写法；\n"
            "- 在标准语境里不存在、但被当成已知对象使用的记号；\n"
            "- 同一个词前后指的不是同一个东西。\n"
            "\n"
            "★ 只报真的悬空的。不要质疑正常术语，不要建议改写，\n"
            "  不要把「这个问题很难」当成符号问题。\n"
            "★ [v1.21.76 S1] 特别检查「**形似标准记号的非标准记号**」：\n"
            "  看起来像某个公认缩写 / 标准编号 / 复杂度类，但拼出来并不\n"
            "  存在的那种。例：把 NP 写成 PN、把 ISO 27001 写成\n"
            "  ISO-27001x。这类**最容易被当成已知对象收下**，也最难被\n"
            "  察觉 —— 一旦收下，后面所有推理都建在一个不存在的东西上。\n"
            "  负对照实测（v1.21.75）：本检查项曾把 `P=PN` 判成\n"
            "  「P与PN均为标准术语」而放行 —— 而它正是为 P=PN 那次\n"
            "  事故才建的。所以这条必须显式写出来，不能靠通用判断。\n"
            "★ 没有问题就返回空数组，这是最常见的情况。\n"
            "严格 JSON：\n"
            '{"issues":[{"term":"≤20字","why":"≤40字"}],'
            '"note":"≤40字"}'
        )
        try:
            d = DGTF("1", self.llm, self.config)
            d.verbose = False
            raw = d.llm.call(system, f"【问题】\n{question}",
                             0.0, 800, json_mode=True, stage=_thinking_stage(getattr(d, 'config', None), 'check_input_sanity'))
            data = d.llm.parse_json(raw) or {}
        except Exception as e:
            logger.warning("输入自检失败: %s", e)
            return {}
        issues = []
        for it in (data.get("issues") or [])[:5]:
            if not isinstance(it, dict):
                continue
            term = str(it.get("term", "")).strip()[:40]
            why = str(it.get("why", "")).strip()[:80]
            if term:
                issues.append({"term": term, "why": why})
        # ★ [规则类自检] 不可见字符 / 指令注入 / 预设式 —— **不计入 LLM 调用**，
        #   在既有检查之外补一层确定性判据（llm-guard 的规则类思路）。
        try:
            _rf = input_red_flags(question)
        except Exception:
            _rf = []
        return {
            "issues": issues,
            "note": str(data.get("note", ""))[:80],
            "checked": True,
            "rule_flags": _rf,
        }

    def _run_serial(self, question: str,
                    route: Optional[List[str]] = None,
                    keep: Optional[Dict[str, str]] = None,
                    rounds=0,
                    channels: Optional[List[str]] = None,
                    _provider=None) -> dict:
        route = route or ["0", "1", "both", "all"]
        keep = keep or {k: "all" for k in route}
        rounds = self._rounds_plan(rounds) if not isinstance(rounds, dict) \
            else rounds
        if channels is not None:
            self.channels = tuple(MemoryChannel.check(c) for c in channels)
        self._mcfg["channels"] = list(self.channels)

        self._question = question
        self._key_terms = sorted(_kw(question, top_n=6))
        self._rounds = rounds
        self._keep = keep
        self._results = {}
        self._upstream_provider = (
            _provider if _provider is not None
            else self._make_serial_provider())

        results = self._results
        key_terms = self._key_terms

        sp1 = _spiral_for(self.config, "1")
        stall_limit = int(sp1.get("stall_streak_limit", 2))
        min_improve = float(sp1.get("min_distance_improvement", 0.03))
        self.dec_tracker = ChannelTracker("decidable", stall_limit, min_improve)
        self.und_tracker = ChannelTracker("undecidable", stall_limit, min_improve)

        dispatch = getattr(self, "_dispatch_plan", None) \
            or self._plan_dispatch(route)
        has_zero = "0" in dispatch["order"]

        # 串行固有语义：0 层先行，研究层拆解时才能读到修行池。
        if has_zero and dispatch["order"][0] != "0":
            order_wo0 = [e for e in dispatch["order"] if e != "0"]
            dispatch["order"] = ["0"] + order_wo0

        self.vp(f"\n{'─'*60}\n🎛 调度："
                f"{' → '.join(_LAYER_LABEL[e] for e in dispatch['order']) or '（空）'}"
                f"　圈数上限 "
                + ", ".join(f"{_LAYER_LABEL[e]}{rounds[e]}"
                            for e in dispatch["order"]))
        _pe = (self.config.get("spiral") or {}).get("per_entry") or {}
        if _pe:
            _pe_parts = []
            for _k, _v in _pe.items():
                if isinstance(_v, dict) and _v:
                    _kv = ", ".join(f"{kk}={vv}" for kk, vv in _v.items())
                    _pe_parts.append(f"{_LAYER_LABEL.get(_k, _k)}[{_kv}]")
            if _pe_parts:
                self.vp("   ⚙️ per_entry 覆盖：" + "；".join(_pe_parts))
        for sk in dispatch["skipped"]:
            self.vp(f"   ⚠️ 跳过 {sk['entry']}：{sk['reason']}")

        for entry in dispatch["order"]:
            try:
                self.vp(f"\n{'═'*60}\n【{entry}】{_LAYER_LABEL[entry]} DGTF"
                        f"（螺旋上限 {rounds[entry]} 圈）\n{'═'*60}")
                self._results[entry] = self._run_layer(
                    entry, self._rounds.get(entry, 0))
            except Exception as exc:
                logger.error("串行 %s 失败: %s", entry, exc, exc_info=True)
                reason = self._note_layer_failure(entry, exc)
                self._results[entry] = self._failed_layer_view(entry, reason)
                continue

        if "all" in self._results:
            with self._pool_lock:
                self._totalize_all_pool()
        self._merge_self_text()

        packed = self._pack_result(question, route, keep, rounds,
                                   self._results)
        packed["dispatch"] = self._dispatch_for_pack("serial")
        return packed


# ============================================================
# 落地层：把跑完的内部状态渲染成「能拿去用」的五块
# ============================================================
#
# ★ 硬约束（不可违反，改这里等于造假）：
#   1. 不可判定与悬置**原样保留**，绝不强行收口。
#      · 悬置不打分、不转待办 —— 「决定不碰」本身就是一种结论。
#      · 未对齐合法：undecidable_product.aligned_amps 不是缺陷，
#        只是没对上评估阶段圈出的 und_aspects。
#      · 未决 ≠ 不可判定：未决进「未决缺口」，不可判定进「边界」。
#        把未决写成待办，就是把"还没查"伪装成"要去做"。
#   2. 停止（stop_reason）与清算（closure_reason）是两回事：
#      停止 = 螺旋不再推进；清算 = 遗留有没有交代。合并成一句
#      "跑完了"会让人以为两件事都完成了。
#
# 五块：决议书 / 待办 / 风险 / 边界 / 未决缺口
# ============================================================

# 待办里**绝不出现**的类别 —— 它们不是"要做的事"
_LANDING_NOT_TODO = ("suspension", "undecidable", "unsaid")

_DEC_STATE_CN_LANDING = {
    "decidable": "可判定",
    "partial": "部分可判定",
    "undecidable": "不可判定",
}


def _landing_pick(res: dict, key: str, prefer=("all", "1", "both", "0")):
    """按优先级从各层 view 里取第一个非空字段。"""
    views = res.get("views") or {}
    for e in prefer:
        got = (views.get(e) or {}).get(key)
        if got:
            return got, e
    for e, v in views.items():
        got = (v or {}).get(key)
        if got:
            return got, e
    return None, None



def render_manifestation(res: dict) -> str:
    """把本次运行的**每一个动作**显式写出它背后"想要什么"。

    不是免责声明。是让这份产物自己承认："我选了 X 来看这个问题" ——
    包括它砍了哪层、用了什么成本档、哪些东西没有被显化。
    """
    out = []
    out.append("## 显化说明\n\n")

    dec = res.get("decidability") or {}
    disp = res.get("dispatch") or {}
    views = res.get("views") or {}

    _o = res.get("orientation") or "auto"
    _o_disp = {
        "auto": "auto（未指定：按题面有无决策语境分流）",
        "boundary": "boundary（要边界清单）",
        "decision": "decision（要可落地方案）",
    }.get(_o, _o)
    _pm = disp.get("_parallel_mode") or "（未记录）"
    out.append(
        f"**这份产物以什么方式显化**：取向={_o_disp}，并行={_pm}。\n\n")
    out.append("**本次运行的显化动作清单**：\n\n")

    out.append(f"- 🎯 **取向选择**：{_o_disp} —— ")
    if _o == "boundary":
        out.append("保留了全四层，代价是多花约一倍。\n")
    elif _o == "decision":
        out.append("允许按可判定性砍层，代价是放弃了后两层的视角。\n")
    else:
        out.append("未指定：落地层按题面有无决策语境分流（无决策语境走 boundary 模板）。\n")

    _order = disp.get("order") or []
    _requested = disp.get("requested") or []
    _skipped = disp.get("skipped") or []
    out.append(f"- 🛣 **路由选择**："
               f"route={' → '.join(_order) or '（空）'}"
               f"（请求 {' → '.join(_requested) or '（空）'}）")
    if _skipped:
        _sk_list = "、".join(s.get("entry", "?") for s in _skipped)
        out.append(f"，跳过了 {_sk_list}")
    _dropped = [k for k in _requested if k not in _order]
    if _dropped:
        out.append(f"，降了 {'、'.join(_dropped)}（取向={_o}）")
    out.append("。\n")

    out.append(f"- 🧵 **mode 选择**：{_pm} —— 按题结构依赖选的。\n")

    rounds = res.get("rounds") or {}
    if rounds:
        _r = "／".join(f"{_LAYER_LABEL.get(k, k)}{v}圈"
                       for k, v in rounds.items())
        out.append(f"- 📏 **圈数选择**：{_r} —— 层内到点会自然停，"
                   f"非跑满。\n")
    else:
        out.append("- 📏 **圈数选择**：（未记录）\n")


    _n_susp = 0
    _n_duel_susp = 0
    for k in ("0", "1", "both", "all"):
        v = views.get(k) or {}
        for s in (v.get("suspensions") or []):
            if (s.get("status") or "active") in ("active", "stable"):
                _n_susp += 1
        for s in (v.get("duel_suspensions") or []):
            if (s.get("status") or "active") in ("active", "stable"):
                _n_duel_susp += 1
    out.append(f"- ⏸ **悬置决定**：本次 {_n_susp} 条修行悬置"
               f"、{_n_duel_susp} 条对撞张力悬置 —— "
               f"悬置不打分，它们是**决定**不是遗憾。\n")

    _und = dec.get("undecidable_aspects") or []
    _untr = dec.get("_und_untraced") or []
    out.append(f"- 📘 **不可判定条目**：{len(_und)} 条"
               f"（其中 {len(_untr)} 条无池内追溯）。\n")

    _tri = res.get("tri_state") or [0, 0]
    try:
        _ag, _tt = int(_tri[0]), int(_tri[1])
    except (TypeError, ValueError, IndexError):
        _ag, _tt = 0, 0
    if _tt > 0:
        _pct = _ag / _tt
        # ★ 原始一致率**必须与机会校正指标并列报** ——
        #   单报原始值在偏斜标签上会严重高估（实证：原始 79% ↔ κ 0.34~0.44）。
        #   口径：三态定序 ⇒ 用 ordinal α / 加权 κ；阈值用 Krippendorff 的
        #   α≥0.800 可靠 / 0.667~0.800 暂定 / <0.667 不可靠。
        out.append(f"- 📊 **三态判决一致率（原始）**：{_ag}/{_tt}"
                   f"（{_pct:.0%}）—— ★ 原始值不计机会一致，须与下行的"
                   f"机会校正指标一起读。\n")
        _ta = res.get("tri_alpha") or {}
        if _ta:
            _a_v = _ta.get("alpha")
            _k_v = _ta.get("kappa")
            _a_s = "—（样本不足）" if _a_v is None else "%.3f" % float(_a_v)
            _k_s = "—（样本不足）" if _k_v is None else "%.3f" % float(_k_v)
            out.append(f"- 📊 **机会校正一致（ordinal）**："
                       f"Krippendorff α = {_a_s} · 加权 κ = {_k_s}"
                       f"（n_unit={_ta.get('n_units', 0)}）"
                       f"｜判词：{_ta.get('verdict', '未测')}\n")
            _rc = _ta.get("rare") or {}
            if _rc:
                out.append(f"- 📊 **少数类一致（{_rc.get('rare')}）**："
                           f"{_rc.get('unanimous')}/{_rc.get('units')}"
                           f"（{float(_rc.get('rate', 0)):.0%}）"
                           f"—— 偏斜标签下多数类共识廉价，少数类一致才有信息。\n")

    out.append("\n**这份产物没有显化的**：\n\n")
    _miss = list(disp.get("missing") or [])
    _gf = res.get("layer_gap") or {}
    _miss = _miss or list(_gf.get("missing") or [])
    _gaps = []
    if _miss:
        _gaps.append(f"缺层 {'、'.join(_miss)} —— 请求了但没产出")
    if dec.get("_divergent"):
        _gaps.append(f"两路判定分叉"
                     f"（池={dec.get('_pool_status', '?')} / "
                     f"外={dec.get('_ext_status', '?')}）—— 产物里以池判为准，"
                     f"但外判不同意的理由没有被展开")
    if _untr:
        _gaps.append(f"{len(_untr)} 条不可判定无池内追溯 —— "
                     f"理由不成立，但留在了产物里")
    if not _gaps:
        _gaps.append("（四层齐备、两路一致、追溯齐）")
    # ★ 两条通道分别记账（文本锚点 / 联网检索）—— 单一实现见
    #   `_anchor_lane_lines`。旧实现只写「外部锚点：无」，联网真跑了
    #   读者也看不到。
    for _al in _anchor_lane_lines(res):
        _gaps.append(_al)
    for g in _gaps:
        out.append(f"- {g}\n")
    out.append("\n")

    return "".join(out)


def _pool_meta_summary(res: dict) -> str:
    """ 池级留痕一句汇总（无留痕时返回空串）。

    ★ 为什么抽出来：这段原来只写在 `_render_landing_boundary` 里。
      阶段 3 加了分流壳之后，`orientation="auto"` 会走 decision 模板，
      于是这一行在新模板上**凭空丢了** —— 旧判据（v64 A）当场判红。
      修法不是把判据改宽，而是让两个模板调**同一份**实现：
      「同一条逻辑两条通道各写一份」是本项目的头号复发问题，不加第 8 例。
    """
    _pools_meta = (res.get("pools") or {})
    _meta_total = sum(len(pp.get("meta") or []) for pp in _pools_meta.values())
    if not _meta_total:
        return ""
    _meta_kinds = {"P1-6 拦截": 0, "自省回流未生效": 0, "自省反馈": 0,
                   "其它": 0}
    for _pp in _pools_meta.values():
        for _m in (_pp.get("meta") or []):
            _s = str(_m)
            if _s.startswith("[P1-6]"):
                _meta_kinds["P1-6 拦截"] += 1
            elif _s.startswith("[自省回流未生效]"):
                _meta_kinds["自省回流未生效"] += 1
            elif "self-check" in _s or "上一圈" in _s:
                _meta_kinds["自省反馈"] += 1
            else:
                _meta_kinds["其它"] += 1
    _parts = " / ".join(f"{k} {v}" for k, v in _meta_kinds.items() if v)
    return f"**池级留痕**：{_meta_total} 条（{_parts}）\n\n"


def _susp_key(target) -> str:
    """取一枚悬置条目的归并键：target 的首个分句（按「；」切）。

    ★ 真跑实测：同一类张力被登记成「X」与「X；元层决定不消解。」—— 全长
      不等 ⇒ 按全长去重完全无效；取首分句后两者相等。首分句短于 6 字时
      退回全长，避免短串误合并。
    """
    _t = str(target or "").strip()
    _head = _t.split("；")[0].split(";")[0].strip()
    return _head if len(_head) >= 6 else _t


def _dedup_suspensions_for_render(items) -> tuple:
    """渲染层归一：同 target 的悬置只渲染一条，返回 (保留列表, 合并条数)。

    ★ 池内已有重复检测，但「决定不消解」这一类没接同一个去重器。这里只做
      渲染层归一，并把合掉的条数打印出来 —— 去冗余、但留痕，不假装池里
      没有重复。
    """
    _seen = set()
    _kept = []
    _dup = 0
    for _it in (items or []):
        _k = _susp_key(_it.get("target") if isinstance(_it, dict) else _it)
        if _k and _k in _seen:
            _dup += 1
            continue
        if _k:
            _seen.add(_k)
        _kept.append(_it)
    return _kept, _dup


_STOP_CUT_MARKS = ("体力耗尽", "被截断")


def _rounds_run_line(views) -> str:
    """各层**实际跑了几圈**（`rounds_run`）+ 种子上限（`rounds_cap`）一行。

    ★ 为什么要有这一行：调度器的「历史实际停圈」读数此前**取不到** ——
      `_auto_history` 把字段名读成了 `rounds`，真实字段是 `rounds_run`
      （静默：`dict.get` 不报错，只是恒 None）。而且产物里根本没有任何渲染点
      把它写出来。于是「实际停圈」这条信号**既没被读、也没被记**。
      本行把它落进产物 ⇒ 后续语料才积累得起来（数据收集闭环）。
    """
    if not isinstance(views, dict) or not views:
        return ""
    _parts = []
    for _e in _ENTRIES:
        _v = views.get(_e)
        if not isinstance(_v, dict):
            continue
        _r = _v.get("rounds_run")
        if not isinstance(_r, int) or _r <= 0:
            continue
        _c = _v.get("rounds_cap")
        _parts.append("%s %d 圈%s"
                      % (_LAYER_LABEL.get(_e, _e), _r,
                         ("（上限 %d）" % _c
                          if isinstance(_c, int) and _c else "")))
    if not _parts:
        return ""
    return "**实际停圈**：" + " / ".join(_parts) + "\n\n"


def _stop_kind_summary(views) -> str:
    """把各层 stop_reason 归纳成一行「自然停 n 层 / 被截断 m 层」。

    ★ 为什么单列到头部：真跑实测四层全部「体力耗尽（被截断不是自然停止）」
      时，读者从头部完全看不出来 —— 「一次停止判据都没触发」与「四层都
      自然收敛」在头部长得一样。没有任何一层留下停因时返回空串（不渲染）。
    """
    if not isinstance(views, dict) or not views:
        return ""
    _nat = _cut = _none = 0
    for _v in views.values():
        if isinstance(_v, dict):
            _sr = str(_v.get("stop_reason") or "")
        else:
            _sr = str(getattr(_v, "stop_reason", "") or "")
        if not _sr:
            _none += 1
        elif any(_m in _sr for _m in _STOP_CUT_MARKS):
            _cut += 1
        else:
            _nat += 1
    if _nat + _cut <= 0:
        return ""
    _tail = f"，无停因记录 {_none} 层" if _none else ""
    _flag = " ⚠️ 无一层自然收敛" if (_cut and not _nat) else ""
    return (f"**停止**：自然 {_nat} 层 / 被截断（体力耗尽）{_cut} 层"
            f"{_tail}{_flag}\n\n")
def _web_lane_stats(res: dict) -> dict:
    """联网检索侧的可读读数（纯函数、零 LLM）—— 「外部锚点」两条通道之一。

    ★ 与 `external_anchor` 的分工：`external_anchor` 读的是运行前挂进来的
      **锚点文件**；本函数读的是 `web_search` 落进池里的**联网检索**结果
      （`web_results` / `web_errors`）。两者互相独立 —— 一个开、另一个
      可以是关的。真跑实测出现过「联网收了 6 条（W1–W6）、锚点文件一条
      没有」，而旧产物只写「**外部锚点**：无」，读者据此会以为本次没有
      任何外部校验。
    ★ `enabled` 三态：True 开 / False 关 / None 未记录（产物没写 `_runtime`）。
    """
    _rt = res.get("_runtime")
    _enabled = (_rt or {}).get("web_enabled") if isinstance(_rt, dict) else None
    _ok: List[dict] = []
    _errs: List[tuple] = []
    for _p in (res.get("pools") or {}).values():
        if not isinstance(_p, dict):
            continue
        for _it in (_p.get("web_results") or []):
            if isinstance(_it, dict):
                _ok.append(_it)
        for _e in (_p.get("web_errors") or []):
            if isinstance(_e, dict):
                _errs.append((str(_e.get("kind") or "?"),
                              str(_e.get("stage") or "?")))
    _tiers: Dict[str, int] = {}
    for _it in _ok:
        _t = _it.get("tier_effective", _it.get("tier"))
        _k = "?" if _t is None else str(_t)
        _tiers[_k] = _tiers.get(_k, 0) + 1
    return {
        "enabled": _enabled,
        "ok": len(_ok),
        "ids": [str(_it.get("id")) for _it in _ok if _it.get("id")],
        "stages": sorted({str(_it.get("stage")) for _it in _ok
                          if _it.get("stage")}),
        "tiers": _tiers,
        "errs": _errs,
    }


def _anchor_lane_lines(res: dict) -> List[str]:
    """把「外部锚点」拆成**两条通道**分别写明：文本锚点（文件）/ 联网检索。

    ★ 为什么必须分开写：真跑产物里联网明明收了 6 条（`pool.meta` 里的
      `[W-OK] …收 3 条`），产物却只写「**外部锚点**：无」—— 读者会据此
      认为本次没有任何外部校验。两套机制各自「没有」时也要各自写清。
    ★ **单一实现**：产物头部 / 显化说明 / 两套落地层模板共 4 处调用本函数。
      「同一条逻辑两条通道各写一份」是本项目复发率最高的问题，不再加例。
    ★ 通道行只写「这一路接没接上」；锚点的**明细**（对照 / 分级 /
      triage 降级 / 冲突 / 入池）仍由产物头部那几行承担 —— 两条通道是
      **多一条出口**，不是换掉那些读数。
    """
    out: List[str] = []
    _ea = res.get("external_anchor")
    if isinstance(_ea, dict) and _ea.get("unconfigured"):
        # ★ 四态之「开（未挂文件）」：既不是「关」，也不是「接失败」。
        out.append("**外部锚点 · 文本**（锚点文件 `external_anchor`）："
                   "**开（未挂锚点文件）** —— 两条接入路二选一："
                   "① `external_anchor.path` 指向锚点快照 JSON；"
                   "② `external_anchor.retriever: tavily` 按圈真检索"
                   "（读 `TAVILY_API_KEY`）。本次结论只取决于池内材料")
    elif isinstance(_ea, dict):
        _l = ("**外部锚点 · 文本**（锚点文件 `external_anchor`）：**开** —— 已接入 "
              + str(_ea.get("anchors", 0)) + " 条")
        if _ea.get("source_file"):
            _l += ("（" + str(_ea.get("source_file"))
                   + "，检索于 " + str(_ea.get("retrieved_at", "?")) + "）")
        elif str(_ea.get("retriever_mode") or "snapshot") != "snapshot":
            _l += "（真检索后端 `" + str(_ea.get("retriever_mode")) + "`）"
        if _ea.get("error"):
            _l += "；⚠️ 接入失败（明细见下方「锚点异常」）"
        out.append(_l)
    else:
        # ★ 与联网通道对称：缺席 = 「关」（不再是「无」）。
        out.append("**外部锚点 · 文本**（锚点文件 `external_anchor`）："
                   "**关** —— 本次未接入锚点文件（关闭时产物不写该通道状态）；"
                   "要接入：`external_anchor.enabled: true` + `path`。"
                   "结论可信度只取决于池内材料的一致性（设计边界，不是缺陷）")
    _w = _web_lane_stats(res)
    if _w["enabled"] is None:
        _l2 = ("**外部锚点 · 联网**（`web_search`）：未记录 —— "
               "本次产物没有写入联网生效状态（要接入：`--web on`）")
    elif not _w["enabled"]:
        _l2 = ("**外部锚点 · 联网**（`web_search`）：**关** —— "
               "本次未接入联网检索；事实类结论没有外部证据支撑"
               "（要接入：`--web on`）")
    else:
        _l2 = ("**外部锚点 · 联网**（`web_search`）：**开** —— 收 "
               + str(_w["ok"]) + " 条")
        if _w["ok"]:
            _ids = "、".join(_w["ids"][:6]) + ("…" if len(_w["ids"]) > 6 else "")
            _l2 += ("（" + (_ids + "；" if _ids else "")
                    + str(len(_w["stages"])) + " 个环节"
                    + ("；tier " + "/".join(
                        _k + "×" + str(_v) for _k, _v in _w["tiers"].items())
                       if _w["tiers"] else "")
                    + "）")
        _l2 += ("；失败 " + str(len(_w["errs"])) + " 条"
                + ("（" + "、".join("[W-" + _k.upper() + "] " + _s
                                   for _k, _s in _w["errs"][:3]) + "）"
                   if _w["errs"] else ""))
    out.append(_l2)
    return out



def _render_landing_decision(res: dict) -> str:
    """ decision 模式的落地层：六段行动闭环。

    ★ 与 boundary 版的关系：老实现整体改名 `_render_landing_boundary`，
      一行没删。分流在 `render_landing` 里做，两个模板都能被单独调用，
      所以旧断言/旧探针只要直接点老名字就还能跑。
    """
    out = []
    views = res.get("views") or {}
    v1 = views.get("1") or {}
    dp = (v1.get("decidable_product") or {}) if isinstance(v1, dict) else {}
    out.append("## 落地层（decision 模式）\n\n")
    out.append(_pool_meta_summary(res))

    out.append("### 一、决议书\n")
    ans = dp.get("answer") or "（未产出可执行结论）"
    out.append(f"- **主结论**：{ans}\n")

    actions = _extract_actions(v1)

    out.append("\n### 二、行动清单\n")
    if not actions:
        out.append("（未抽出 action，rubric 扣分）\n")
    for a in actions:
        out.append(f"- **{a.get('id', 'A?')}**：{a.get('verb', '')} "
                   f"{a.get('object', '')}\n")
        out.append(f"  - 负责人：{a.get('owner_role', '（未指定）')}\n")
        out.append(f"  - 时限：{a.get('deadline_hint', '（未指定）')}\n")
        out.append(f"  - 验收：{a.get('acceptance', '（未指定）')}\n")
        out.append(f"  - 回退：{a.get('fallback', '（未指定）')}\n")
    # ★ [言语行为标注] 承诺 / 断言 / 请求 —— 全是「请求」= 公文体
    #   （言语行为论：一份清单若没有任何「承诺」，就没人真的认领）。
    try:
        _il = illocution_dist(actions)
        if _il.get("n"):
            _dd_ = _il["dist"]
            out.append("\n> **言语行为分布**（承诺/断言/请求/其他）："
                       f"{_dd_.get('承诺', 0)}/{_dd_.get('断言', 0)}/"
                       f"{_dd_.get('请求', 0)}/{_dd_.get('其他', 0)}"
                       f"（n={_il['n']}）")
            if _il.get("verdict"):
                out.append("> ⚠️ " + _il["verdict"])
            out.append("\n")
    except Exception:
        pass

    _dd = [a.get("object", "") for a in actions
           if a.get("deadline_hint") == "（未指定）"]
    out.append("\n### 三、所需数据清单\n")
    if _dd:
        out.append("（以下行动缺时限，通常是因为缺一次现场量测）\n")
        for s in _dd[:3]:
            out.append(f"- {s[:80]}\n")
    else:
        # 空节守卫：有标题、没内容，读者会读成「渲染失败」。
        out.append("（本节无内容：没有「缺时限」的行动，"
                   "因此没有待补的现场量测项）\n")

    out.append("\n### 四、失败模式与回退\n")
    _nf = [a for a in actions if a.get("fallback") == "（未指定）"]
    if _nf:
        out.append(f"- ⚠️ {len(_nf)} 条行动**没有回退**："
                   + "、".join(a.get("id", "?") for a in _nf) + "\n")
    else:
        out.append("- 所有行动都带回退路径。\n")
    # ★ [FMEA 可检测性] 不可检测的失败最危险 —— 它不会出现在任何读数里。
    #   本节原有「有没有回退」，缺「这个失败**能不能被发现**」。
    #   ★ 口径：**无条件输出**（没有可标注项也要写 —— 「没输出」会被读成
    #     「没有失败」，而真相多半是「没被记下来」）；异常也不再静默吞掉。
    _marks = []
    try:
        if isinstance(v1, dict):
            for _vv in v1.values():
                _marks += [str(x) for x in ((_vv or {}).get("quality_flags") or [])]
                _marks += [str(x) for x in
                           ((_vv or {}).get("errors") or [])][:6]
    except Exception as _ef:
        _marks = ["（FMEA 取标记失败：%s）" % type(_ef).__name__]
    _fmea_names = [("失败模式" + str(_idx + 1))
                   for _idx in range(min(3, len(_nf)))]
    out.append("\n> **FMEA 可检测性**（严重度×频度×**可检测性**）：\n")
    if _fmea_names:
        for _nm in _fmea_names:
            out.append(f"> - {_nm}：{fmea_detectability(_nm, _marks)}\n")
    else:
        out.append("> - 本次没有「缺回退」的行动 ⇒ 没有可标注的失败模式；"
                   "★ 这不等于没有失败，只等于**没被记下来**\n")
    out.append("> - 已知标记（用于判可检测性）：%s\n"
               % ("、".join(_marks[:6]) if _marks else "（无）"))

    out.append("\n### 五、不做什么\n")
    not_do = _extract_not_do(v1)
    if not_do:
        for s in not_do:
            if isinstance(s, dict):
                _w = str(s.get("what", "") or "")
                _y = str(s.get("why", "") or "")
                out.append(f"- {_w}"
                           + (f"（{_y}）" if _y else "") + "\n")
            else:
                out.append(f"- {s}\n")
    else:
        out.append("（未指定「不做什么」—— 这是 decision 产物的缺口）\n")

    # ★ [LDG] 未答的核心问项 —— **点名**，而不是让读者以为都答了。
    #   来源：各层职责读数里 `missing_core` 的并集（去重保序）。
    try:
        _miss_all = []
        for _e in ("0", "1", "both", "all"):
            _dd = ((result.get("views") or {}).get(_e) or {}).get("duty") or {}
            for _m in (_dd.get("missing_core") or []):
                if _m and _m not in _miss_all:
                    _miss_all.append(_m)
        if _miss_all:
            out.append("\n### ★ 未答的核心问项（守卫实算·点名）\n")
            out.append("> 这些是问项的 **core 档**（主问，不含附加目标）"
                       "在四层交付面里**没有被正面回答**的部分。\n")
            out.append("> 列在这里不是「失败了」，是不许假装答过 —— "
                       "按红线「悬置不打分」。\n")
            for _m in _miss_all[:8]:
                out.append(f"- ⚠ {_m}")
    except Exception:
        pass
    out.append("\n### 六、如果只能做一件事\n")
    if actions:
        a1 = actions[0]
        out.append(f"- {a1.get('verb', '')} {a1.get('object', '')}\n")
    else:
        out.append("（本节无内容：没有抽出任何行动）\n")

    out.append("\n### 七、外部锚点（两条通道分开记账）\n")
    out.append("（`external_anchor` 是运行前挂进来的**锚点文件**；"
               "`web_search` 是**联网检索**。两者互相独立 —— "
               "一条没有时也各自写明，避免把「没接入」读成「没这一项」。）\n")
    for _al in _anchor_lane_lines(res):
        out.append(f"- {_al}\n")
    return "".join(out)


# decision 模板的适用前提是「题面里有决策语境」。
#   词表只增不减 —— 加词只会让更多题走 decision 模板（即回到旧版行为），
#   不会静默把本来走 decision 的题踢出去。
_DECISION_CUES = (
    "该不该", "要不要", "是否", "怎么办", "怎么选", "怎么建", "怎么改",
    "如何", "方案", "建议", "选哪个", "取舍", "优先", "值不值", "利弊",
    "可行", "落地", "规划", "部署", "决策", "权衡", "风险", "预算",
    "排期", "步骤", "流程", "设计",
)


def _has_decision_context(question: str) -> bool:
    """题面是否带决策语境（决定 decision 模板适不适用）。

    ★ 判据落在**行为**上：命中任一决策语汇 → True（走 decision 模板）。
      只判「有 / 没有」，不判程度。
    ★ 负对照：单点事实询问（「…是什么时候」「…是哪一年」「…有多少」）
      不该命中 —— 它们套 decision 模板会替提问者编出一整套不存在的
      执行流程（行动清单 / 负责人 / 时限 / 验收）。
    ★ 题面取不到（空 / 缺 question 键）时返回 False：宁可走边界模板，
      也不在不知道题面时套决策模板。
    """
    _q = str(question or "")
    if not _q.strip():
        return False
    return any(_c in _q for _c in _DECISION_CUES)


def _with_form_declaration(res: dict, body: str, template: str,
                           why: str) -> str:
    """把「形态声明」插到落地层标题之后，返回新正文。

    ★ 为什么不能插在标题之前：md 里标题前放正文，那个标题就不再是章节标题了。
    ★ 为什么要有：decision 模板会渲染出「行动清单 / 负责人 / 时限 / 验收」
      这类**模板结构**；真跑实测它们被填成了不存在的岗位与会议
      （「党史研究室编研岗」「定稿会前2个工作日」）。声明一行，
      读的人才知道哪些段落是模板约定、哪些是问题本身要求的。
    """
    _decl = (f"\n> **形态声明**：本次落地层用 **{template}** 模板 —— {why}。\n"
             "> 模板里的分节（如 decision 的「行动清单 / 负责人 / 时限 / "
             "验收」）是**渲染约定**，不等于提问者的要求。\n")
    _nl = body.find("\n")
    if _nl < 0:
        return _decl + body
    return body[:_nl] + "\n" + _decl + body[_nl:]




_APPENDIX_JSON_RE = re.compile(r"```json\n(.*?)\n```\n?", re.S)


def _appendix_to_file(text: str, side_path) -> str:
    """把附录里的内联全量 JSON 搬到旁挂文件；正文只留文件名与读法。

    ★ 红线不变：「**不得因为没写渲染点就丢信息**」。变的是**位置**，不是有没有 ——
      `_render_full_appendix` 一字未改，它依旧是「机械全量」的权威实现；
      本函数只做**搬运**，搬运失败就原样退回内联（并留痕），绝不悄悄丢。
    ★ 为什么值得搬：真跑实测内联 JSON 占全文 81.7%（9987 行里 4760 行是它）。
    """
    _m = _APPENDIX_JSON_RE.search(text)
    if not _m:
        return text
    _dump = _m.group(1)
    try:
        _p = Path(side_path)
        _p.write_text(_dump, encoding="utf-8")
    except Exception as e:                      # 搬运失败 → 退回内联 + 留痕
        return text.replace(
            _m.group(0),
            "⚠️ **全量 JSON 外置失败**（已回退为内联）："
            f"{type(e).__name__}: {e}\n", 1)
    _tip = ("```text\n" + str(Path(side_path).name) + "\n```\n\n"
            f"（{len(_dump)} 字符 / {_dump.count(chr(10)) + 1} 行；"
            "用 `json.load` 打开即可，UTF-8，与产物 md 同目录。）\n")
    return text.replace(_m.group(0), _tip, 1)


def _append_self_check_writeback(res: dict, body: str) -> str:
    """把自省的**高置信诊断**回写成落地层里的一条可执行动作。

    ★ 为什么要有：自省结论原先只落在逐层明细（`views.*.self_check`），
      读落地层的人看不到 —— 诊断与动作之间是断的。这里把两类高置信信号
      提到落地层：
        · `unsaid_is_escape=True` —— 自省判「用『未生』收尾 = 逃避」；
        · `quality_flags` 里的 `xxx_overused(n)` / `action_incomplete` /
          `not_do_missing`。
    ★ 没有高置信信号时**原样返回**（不渲染、不制造动作）。
    """
    _items = []
    _views = res.get("views") or {}
    for _k in ("0", "1", "both", "all"):
        _v = _views.get(_k) or {}
        if not isinstance(_v, dict):
            continue
        _sc = _v.get("self_check") or {}
        if isinstance(_sc, dict) and _sc.get("unsaid_is_escape"):
            _w = str(_sc.get("unsaid_where") or "")[:120]
            _items.append(
                f"- [{_k}] ⚠ **判为逃避**：{_w}\n"
                "  ⇒ 动作：回到该层「撞不动的地方」继续推，别用「未生」收尾。")
        for _fl in (_v.get("quality_flags") or []):
            _s = str(_fl)
            if ("_overused" in _s or _s.startswith("action_incomplete")
                    or _s.startswith("not_do_missing")):
                _items.append(
                    f"- [{_k}] ⚠ **质量线索 `{_s}`**\n"
                    "  ⇒ 动作：先核这条线索对应的机制是否真跑到，"
                    "再决定采不采信结论。")
    if not _items:
        return body
    _blk = (f"\n> **自省回写**（诊断 → 动作）：本次 {len(_items)} 条高置信诊断"
            "被提升为动作 ——\n" + "\n".join(_items) + "\n")
    _i = body.find("> 模板里的分节")
    if _i >= 0:
        _j = body.find("\n\n", _i)
        if _j >= 0:
            return body[:_j] + "\n" + _blk + body[_j:]
    _nl = body.find("\n")
    if _nl < 0:
        return body + _blk
    return body[:_nl] + "\n" + _blk + body[_nl:]


def _web_auto_for_facts(question: str) -> bool:
    """`--web auto` 下，事实型询问是否自动接入外部校验。

    ★ 判据同 `_has_decision_context`：无决策语境 = 事实型 ⇒ 自动接入。
    ★ 为什么默认接入：真跑实证 —— 事实型询问的史实结论完全靠池内材料一致性
      撑着，产物里却只写一句「这是设计边界，不是缺陷」。把「没校验」变成
      一次**默认会做的动作**，比一句免责声明有用。
    ★ 要关掉：`--web off`。
    """
    return not _has_decision_context(question)


def render_landing(res: dict) -> str:
    """ 落地层分流壳：boundary / 关掉开关 / **无决策语境** → 老五块模板；
    decision → 行动闭环模板。壳里不写任何渲染逻辑。

    ★ `auto` 还要看题面：无决策语境的单点事实询问
      （「…是什么时候」「…是哪一年」）套 decision 模板，会替提问者
      编出一整套不存在的执行流程（行动清单 / 负责人 / 时限 / 验收）。
      这类题面走 boundary 模板。
      **显式传 `--orientation decision` 仍走 decision**（不覆盖用户的
      显式选择）；`boundary` 与「关掉开关」两种短路都保持原样。
    """
    cfg = res.get("_config") or {}
    orientation = str(res.get("orientation") or "auto").strip().lower()
    # ★ 落地层模板可**单独接管**（与取向解耦）——
    #   取向决定「是否按可判定性砍层」，本项只决定产物形态。
    #   上一版之前 `auto` 在 route 侧按 decision、在模板侧按题面分流，
    #   同一趟里可能自相矛盾（产物要靠「取向错配」告警来自证清白）。
    _li = ((res.get("_auto_dispatch") or {}).get("_items") or {}).get(
        "landing") or {}
    _land = str(_li.get("value") or "") if _li.get("source") in (
        "auto", "explicit", "config") else ""
    if _land in ("boundary", "decision"):
        orientation = _land
    if orientation == "boundary" or not _action_on(cfg, "landing_decision"):
        _why = ("取向显式指定 boundary" if orientation == "boundary"
                else "落地决策模板已关闭")
        _body = _with_form_declaration(
            res, _render_landing_boundary(res), "boundary", _why)
    elif orientation == "auto" and not _has_decision_context(
            str(res.get("question") or "")):
        _body = _with_form_declaration(
            res, _render_landing_boundary(res), "boundary",
            "auto：题面无决策语境（单点事实询问）")
    else:
        _body = _with_form_declaration(
            res, _render_landing_decision(res), "decision",
            ("取向 %s" % orientation)
            + ("：题面含决策语境" if orientation == "auto" else ""))
    return _append_self_check_writeback(res, _body)


def _render_landing_boundary(res: dict) -> str:
    """把 result 渲染成落地文档（决议书 / 待办 / 风险 / 边界 / 未决缺口）。

    纯函数，不改 result。缺什么就写缺什么，不脑补。
    """
    out = []
    views = res.get("views") or {}
    dec = res.get("decidability") or {}

    # ────────────────────────────────────────────────
    # 0 · 一句话：这份产物能不能直接用
    # ────────────────────────────────────────────────
    _d = dec.get("decidability") or "?"
    _d_cn = _DEC_STATE_CN_LANDING.get(_d, _d)
    _div = dec.get("_divergent")
    _untr = dec.get("_und_untraced")
    disp = res.get("dispatch") or {}
    _miss = list(disp.get("missing") or (res.get("layer_gap") or {}).get("missing") or [])

    out.append("## 落地层\n")
    out.append(_pool_meta_summary(res))
    verdict = []
    if _miss:
        verdict.append(f"❌ **缺层** `{'、'.join(_miss)}` —— 这份产物不完整，"
                       f"下面的决议书只覆盖跑出来的那几层")
    if _div:
        verdict.append(f"⚠️ 判定分叉（池={dec.get('_pool_status', '?')} / "
                       f"外={dec.get('_ext_status', '?')}），以池判为准")
    if _untr:
        verdict.append(f"⚠️ 有 {len(_untr)} 条不可判定**没有池内追溯**，"
                       f"判定依据不足")
    out.append("**可用性**：" + ("；".join(verdict) if verdict
                                 else "✅ 四层齐备、两路判定一致、理由均有追溯")
               + "\n")

    # ────────────────────────────────────────────────
    # 1 · 决议书（只有可判定部分能进）
    # ────────────────────────────────────────────────
    out.append("\n### 一、决议书\n")
    dp, dp_from = _landing_pick(res, "decidable_product")
    if dp and dp.get("answer"):
        out.append(f"**结论**：{dp['answer']}\n")
        _ids = dp.get("answered_sub_ids") or []
        if _ids:
            out.append(f"\n**答出的子问题**：{'、'.join(str(i) for i in _ids)}\n")
        _dist = dp.get("distance")
        if _dist is not None:
            out.append(f"\n**距原问题**：{_dist}"
                       f"（0 = 正面答中，越大越偏）\n")
        _ev = dp.get("evidence") or []
        if _ev:
            out.append("\n**依据**：\n")
            for e in _ev:
                out.append(f"- {e}\n")
        out.append(f"\n<sub>取自 {_LAYER_LABEL.get(dp_from, dp_from)} 层"
                   f"可判定通道</sub>\n")
    else:
        out.append("（本次没有产出可判定结论"
                   + ("——" + _d_cn if _d != "?" else "") + "）\n")

    # ────────────────────────────────────────────────
    # 2 · 待办清单（★ 只有"欠着的账"能进，悬置/不可判定/未决都不进）
    # ────────────────────────────────────────────────
    out.append("\n### 二、待办清单\n")
    todos = []
    for e in ("0", "1", "both", "all"):
        v = views.get(e) or {}
        for d in (v.get("deferrals") or []):
            # resolved_at 有值 = 已了结，不再进待办
            if d.get("resolved_at") is not None:
                continue
            todos.append((e, d))
    if todos:
        for e, d in todos:
            line = f"- [ ] 子问题{d.get('sub_id', '?')} {d.get('sub_question', '')}"
            if d.get("decidability"):
                line += f"（{_DEC_STATE_CN_LANDING.get(d['decidability'], d['decidability'])}）"
            out.append(line + "\n")
            out.append(f"  - 为什么欠着：{d.get('reason', '（未写）')}\n")
            if d.get("revisit_condition"):
                out.append(f"  - 什么时候能回来：{d.get('revisit_condition')}\n")
            out.append(f"  - 挂账于 {_LAYER_LABEL.get(e, e)} 层"
                       + (f"（← 重新挂账，接 {d['reopened_from']}）"
                          if d.get("reopened_from") else "") + "\n")
    else:
        out.append("（无未了结债务）\n")

    # ────────────────────────────────────────────────
    # 3 · 风险登记表（判定不稳定 / 迁向不可判定 / 分叉 / 无追溯）
    # ────────────────────────────────────────────────
    out.append("\n### 三、风险登记表\n")
    risks = []
    if _miss:
        for e in _miss:
            _fail = dict(disp.get("failed") or (res.get("layer_gap") or {}).get("failed") or {})
            risks.append(f"缺层 `{e}`：{_fail.get(e, '未记录原因（这是缺陷）')}")
    if _div:
        risks.append(f"两路判定分叉：池={dec.get('_pool_status', '?')} / "
                     f"外={dec.get('_ext_status', '?')} —— 以池判为准，"
                     f"但外判不同意的理由值得单独看")
    for u in (_untr or []):
        risks.append(f"不可判定条目无池内追溯：{u}")
    for e in ("0", "1", "both", "all"):
        v = views.get(e) or {}
        for esc in (v.get("escalations") or []):
            _ev = "、".join(esc.get("evidence") or []) or "无证据"
            risks.append(f"[{_LAYER_LABEL.get(e, e)}] 子问题{esc.get('sub_id')} "
                         f"迁向不可判定（{_ev}）：{esc.get('reason', '')}")
        for rc in (v.get("reclassifications") or []):
            _ev = "、".join(rc.get("evidence") or []) or "无证据"
            risks.append(f"[{_LAYER_LABEL.get(e, e)}] 子问题{rc.get('sub_id')} "
                         f"改判为 {_DEC_STATE_CN_LANDING.get(rc.get('to'), rc.get('to') or '?')}"
                         f"（{_ev}）：{rc.get('reason', '')}")
    if risks:
        for r in risks:
            out.append(f"- ⚠ {r}\n")
    else:
        out.append("（无登记风险）\n")

    # ────────────────────────────────────────────────
    # 4 · 边界清单（★ 原样保留，不转待办、不打分）
    # ────────────────────────────────────────────────
    out.append("\n### 四、边界 —— 判不出 / 决定不碰\n")
    out.append("<sub>这两类都**不是**待办。判不出是性质，决定不碰是选择。</sub>\n\n")

    out.append("**判不出（不可判定）**\n")
    _any_und = False
    for a in (dec.get("undecidable_aspects") or []):
        out.append(f"- 📘 {a}\n")
        _any_und = True
    up, up_from = _landing_pick(res, "undecidable_product")
    if up and up.get("why_undecidable"):
        out.append(f"- 📘 {up['why_undecidable']}"
                   f"（{_LAYER_LABEL.get(up_from, up_from)} 层不可判定通道）\n")
        _any_und = True
        if up.get("clarity") is not None:
            out.append(f"  - 清晰度：{up['clarity']}\n")
        for sa in (up.get("structural_amps") or []):
            out.append(f"  - 独立结构：{sa}\n")
        # 未对齐合法：如实标出，不写成缺陷
        for aa in (up.get("aligned_amps") or []):
            out.append(f"  - 对齐 und_aspects（另计）：{aa}\n")
    if not _any_und:
        out.append("（本次没有圈出不可判定）\n")

    out.append("\n**决定不碰（悬置）**\n")
    _any_susp = False
    for e in ("all", "both", "1", "0"):
        v = views.get(e) or {}
        for s in (v.get("suspensions") or []):
            if (s.get("status") or "active") not in ("active", "stable"):
                continue  # 已撤回的不算"决定不碰"
            out.append(f"- ⏸ {s.get('target', '')}："
                       f"{s.get('reason') or '直觉，无理由'}"
                       f"（{s.get('reason_type', '')}）"
                       f"〔{_LAYER_LABEL.get(e, e)}〕\n")
            _any_susp = True
        for s in (v.get("duel_suspensions") or []):
            if (s.get("status") or "active") not in ("active", "stable"):
                continue
            out.append(f"- ⏸ 张力「{s.get('target', '')}」悬置"
                       f"（{s.get('quadrant') or '未归类'}）："
                       f"{s.get('reason') or '直觉，无理由'}"
                       f"〔{_LAYER_LABEL.get(e, e)}〕\n")
            _any_susp = True
    if not _any_susp:
        out.append("（本次没有悬置）\n")

    # ────────────────────────────────────────────────
    # 5 · 未决缺口（★ 未决 ≠ 不可判定 ≠ 待办 —— 只是这一轮没走到）
    # ────────────────────────────────────────────────
    out.append("\n### 五、未决缺口\n")
    out.append("<sub>「还没走到」而已。写在这里不代表要做，"
               "更不代表判不出。</sub>\n\n")
    gaps = []
    for e in ("0", "1", "both", "all"):
        v = views.get(e) or {}
        for t in (v.get("threads") or []):
            d = t.get("desc", "") if isinstance(t, dict) else str(t)
            if d:
                gaps.append((_LAYER_LABEL.get(e, e), "悬空线头", d))
        for u in (v.get("untouched") or []):
            d = u.get("desc", "") if isinstance(u, dict) else str(u)
            if d:
                gaps.append((_LAYER_LABEL.get(e, e), "尚未触及", d))
    for e in ("all", "both", "1", "0"):
        v = views.get(e) or {}
        for a in (v.get("uncovered_aspects") or []):
            gaps.append((_LAYER_LABEL.get(e, e), "未覆盖方面", str(a)))
    if gaps:
        # 去重（同一句可能多层重复出现）
        seen, uniq = set(), []
        for layer, kind, d in gaps:
            k = (kind, d.strip()[:80])
            if k in seen:
                continue
            seen.add(k)
            uniq.append((layer, kind, d))
        for layer, kind, d in uniq[:24]:
            out.append(f"- 〔{layer}〕{kind}：{d}\n")
        if len(uniq) > 24:
            out.append(f"\n<sub>共 {len(uniq)} 条，此处列出前 24 条</sub>\n")
    else:
        out.append("（无未决缺口）\n")

    # ────────────────────────────────────────────────
    # 6 · 停止 vs 清算（★ 两件事，不合并）
    # ────────────────────────────────────────────────
    out.append("\n### 六、停止 / 清算（两件事）\n")
    _stop, _clo = None, None
    for e in ("all", "both", "1", "0"):
        v = views.get(e) or {}
        if not _stop and v.get("stop_reason"):
            _stop = (_LAYER_LABEL.get(e, e), v["stop_reason"])
        if not _clo and v.get("closure_reason"):
            _clo = (_LAYER_LABEL.get(e, e), v["closure_reason"])
    out.append(f"- **停止**（螺旋不再推进）："
               f"{_stop[1] if _stop else '（未记录）'}"
               + (f" 〔{_stop[0]}〕" if _stop else "") + "\n")
    out.append(f"- **清算**（遗留有没有交代）："
               f"{_clo[1] if _clo else '（未记录）'}"
               + (f" 〔{_clo[0]}〕" if _clo else "") + "\n")
    for e in ("all", "both"):
        v = views.get(e) or {}
        stl = v.get("settlement") or {}
        if stl:
            _cov = stl.get("coverage")
            _cov_s = f"{_cov:.0%}" if isinstance(_cov, (int, float)) else "N/A"
            out.append(f"- 终局清算〔{_LAYER_LABEL.get(e, e)}〕："
                       f"clean={stl.get('clean')}，遗留 {stl.get('leftover', 0)} 项，"
                       f"可判定覆盖率 {_cov_s}\n")
        clo = v.get("meta_closure") or {}
        if clo:
            out.append(f"- 闭环清算〔{_LAYER_LABEL.get(e, e)}〕："
                       f"clean={clo.get('clean')}，"
                       f"未交代 {clo.get('unsettled', 0)} 类\n")

    out.append("\n### 七、外部锚点（两条通道分开记账）\n")
    out.append("（`external_anchor` 是运行前挂进来的**锚点文件**；"
               "`web_search` 是**联网检索**。两者互相独立 —— "
               "一条没有时也各自写明，避免把「没接入」读成「没这一项」。）\n")
    for _al in _anchor_lane_lines(res):
        out.append(f"- {_al}\n")

    return "".join(out)





_ACTION_VERB_WHITELIST = (
    "指派", "指定", "核查", "测量", "提交", "申请", "封堵",
    "清淤", "试点", "备案", "签发", "复核", "排查", "改造",
    "扩容", "委托", "报审", "谈判", "调取",
)

_ACTION_ROLES = ("区防汛办", "排水公司", "信息科", "医务科",
                 "法务", "财务", "项目组", "上级部门")

_ACTION_DEADLINES = ("汛期前", "本月内", "30 天内", "本季度", "下一财年",
                     "本月底", "下周", "一季内")

# 「不做什么」的标记词。少了这一项，decision 产物就只剩"要做什么"，
# 而决策的风险恰恰在于没说清"不做什么"。
_NOT_DO_MARKS = ("不做", "不要", "不采取", "不走", "不先", "禁止",
                 "暂不", "不得", "不宜", "避免")


def _act_text(view) -> str:
    """取结论文本。View 或 dict（packed 里的 views.N）都要吃。"""
    if isinstance(view, dict):
        dp = view.get("decidable_product") or {}
        return str(dp.get("answer") or "")
    dp = getattr(view, "decidable_product", None) or {}
    return str(dp.get("answer") or "")


def _und_text(view) -> str:
    if isinstance(view, dict):
        dp = view.get("undecidable_product") or {}
        return str(dp.get("answer") or "")
    dp = getattr(view, "undecidable_product", None) or {}
    return str(dp.get("answer") or "")


def _guess_role(s: str) -> str:
    for role in _ACTION_ROLES:
        if role in s:
            return role
    return "（未指定）"


def _guess_deadline(s: str) -> str:
    for hint in _ACTION_DEADLINES:
        if hint in s:
            return hint
    return "（未指定）"


def _guess_acceptance(s: str) -> str:
    if "验收" in s:
        return s.split("验收", 1)[1][:60]
    return "（未指定）"


def _guess_fallback(s: str) -> str:
    if "回退" in s or "否则" in s:
        return s.split("否则", 1)[-1][:60]
    return "（未指定）"


def _extract_actions_lexical(view) -> list:
    """ 词法兜底：从结论文本里抽行动条目，每条补齐 6 个字段。

    入参两形态：View 对象 / packed 里的 dict。
    已抽过的（dict 里带 `_actions`）直接返回，避免落地层再抽一次抽成两份。

    ★ 负对照（写进冒烟）：空结论必须返回 **0 条** ——
      否则「有没有行动」这件事永远为真，`action_incomplete` 就永远不亮。
    """
    import re as _re
    if isinstance(view, dict) and isinstance(view.get("_actions"), list):
        return list(view["_actions"])
    text = _act_text(view)
    if not text:
        return []
    out: list = []
    # 按句号/分号切，逐句看有没有白名单里的动词。
    for m in _re.finditer(r"[。；;]([^。；;]{4,120})", "。" + text):
        s = m.group(1).strip()
        _v = next((v for v in _ACTION_VERB_WHITELIST if v in s), "")
        if not _v:
            continue
        out.append({
            "id": f"A{len(out) + 1}",
            "verb": _v,
            "object": s,
            "owner_role": _guess_role(s),
            "deadline_hint": _guess_deadline(s),
            "acceptance": _guess_acceptance(s),
            "fallback": _guess_fallback(s),
        })
        if len(out) >= 5:
            break
    return out


def _norm_schema_not_do(raw) -> list:
    """ 把模型给的 `decidable_product.not_do` 归一成 what/why。

    与 `_norm_schema_actions` 同款：非 list → 空；非 dict 条目丢弃；
    **`what` 为空 → 丢弃**（空 what 不算一条，否则 rubric 第三项会假通过）。
    """
    out: list = []
    if not isinstance(raw, list):
        return out
    for i, a in enumerate(raw[:6], 1):
        if not isinstance(a, dict):
            continue
        w = str(a.get("what", "") or "").strip()
        if not w:
            continue
        out.append({
            "id": str(a.get("id") or f"N{i}")[:12],
            "what": w[:80],
            "why": str(a.get("why", "") or "").strip()[:80],
        })
    return out


def _norm_schema_actions(raw) -> list:
    """ 把模型给的 `decidable_product.actions` 归一成六字段 dict。

    放在这里（而不是内联在 `_he` 里）是为了让 `_he` 的 dec_norm 只写一行。
    归一策略：非 list → 空；非 dict 条目丢弃；每条按字段截断；最多 6 条。
    """
    out: list = []
    if not isinstance(raw, list):
        return out
    for i, a in enumerate(raw[:6], 1):
        if not isinstance(a, dict):
            continue
        out.append({
            "id": str(a.get("id") or f"A{i}")[:12],
            "verb": str(a.get("verb", ""))[:20],
            "object": str(a.get("object", ""))[:80],
            "owner_role": str(a.get("owner_role", ""))[:40],
            "deadline_hint": str(a.get("deadline_hint", ""))[:40],
            "acceptance": str(a.get("acceptance", ""))[:80],
            "fallback": str(a.get("fallback", ""))[:80],
        })
    return out


def _single_vote_stability(sq: dict) -> str:
    """ 单票路径的 stability 口径，与多票路径**同层级可比**。

    · 该条未被判决（判决官弃权）→ "abstained"（**不参与**一致率统计）
    · 与拆解原标签一致          → "high"
    · 不一致                    → "low"
    · 有判决但无原标签          → "medium"

    ★ 与多票路径的 `stability` **不是同一把尺子**（多票那份量的是
      「三票之间」）。两者都叫 stability 但必须按 `_vote_mode` 分口径读，
      头部标题会印出当前口径 —— 拿两臂的数直接比会得到错结论。
    """
    if not sq.get("_tri_judged"):
        return "abstained"
    if sq.get("label_disagreed"):
        return "low"
    first = str(sq.get("first_label", "") or "").strip().lower()
    curr = str(sq.get("decidability", "") or "").strip().lower()
    if not first:
        return "medium"
    return "high" if first == curr else "low"


def _extract_actions(view) -> list:
    """优先读 schema 产出的 actions；schema 缺失时才回退词法抽取。

    [v1.22.1 P1] 语义变更：从「从结论段落里猜动作」变成「读研究层已产出的
    结构化 actions」。词法路径保留（`_extract_actions_lexical`），仅作兜底
    （老产物 / 未升级 schema 的跑批）。

    入参两形态：View 对象 / packed 里的 dict。
    已抽过的（dict 里带 `_actions`）直接返回，避免落地层再抽一次抽成两份。

    ★ 负对照（写进冒烟）：空结论必须返回 **0 条** ——
      否则「有没有行动」这件事永远为真，`action_incomplete` 就永远不亮。
    """
    if isinstance(view, dict) and isinstance(view.get("_actions"), list):
        return list(view["_actions"])
    if isinstance(view, dict):
        dp = view.get("decidable_product") or {}
    else:
        dp = getattr(view, "decidable_product", None) or {}
    dp = dp if isinstance(dp, dict) else {}
    _schema_actions = dp.get("actions")
    if isinstance(_schema_actions, list) and _schema_actions:
        out: list = []
        for a in _schema_actions:
            if not isinstance(a, dict):
                continue
            _act = {
                "id": str(a.get("id") or f"A{len(out) + 1}"),
                "verb": str(a.get("verb", "")).strip(),
                "object": str(a.get("object", "")).strip(),
                "owner_role": str(a.get("owner_role", "")).strip(),
                "deadline_hint": str(a.get("deadline_hint", "")).strip(),
                "acceptance": str(a.get("acceptance", "")).strip(),
                "fallback": str(a.get("fallback", "")).strip(),
            }
            # 六字段全空视为无效；留一条空字段也收，但标 incomplete
            if not any(_act[k] for k in ("verb", "object")):
                continue
            _act["_source"] = "schema"
            _act["_missing"] = [k for k in
                                ("verb", "object", "owner_role",
                                 "deadline_hint", "acceptance", "fallback")
                                if not _act[k]]
            out.append(_act)
        if out:
            return out
    # 兜底：词法（老路径一字不动，只补 `_source` 标签）
    out2: list = []
    for _a in _extract_actions_lexical(view):
        if isinstance(_a, dict):
            _a = dict(_a)
            _a["_source"] = "lexical"
        out2.append(_a)
    return out2


def _extract_not_do(view) -> list:
    """ 优先读 schema 产出的 not_do；缺失时才回退词法抽取。

    入参两形态：View 对象 / packed 里的 dict。已抽过的（dict 里带
    `_not_do`）直接返回，避免落地层再抽一次抽成两份。
    · schema 结果带 `_source="schema"`（每条 {what, why}）；
    · 词法兜底带 `_source="lexical"`（老产物 / 未升级 schema 的跑批）。

    ★ 负对照（写进冒烟）：空 view 必须返回 **0 条** ——
      否则「有没有不做的事」永远为真，`not_do_missing` 就永远不亮。
    """
    if isinstance(view, dict) and isinstance(view.get("_not_do"), list):
        return list(view["_not_do"])
    if isinstance(view, dict):
        dp = view.get("decidable_product") or {}
    else:
        dp = getattr(view, "decidable_product", None) or {}
    dp = dp if isinstance(dp, dict) else {}
    _schema = dp.get("not_do")
    if isinstance(_schema, list) and _schema:
        out: list = []
        for a in _schema:
            if not isinstance(a, dict):
                continue
            _w = str(a.get("what", "") or "").strip()
            if not _w:
                continue
            out.append({"what": _w[:80],
                        "why": str(a.get("why", "") or "").strip()[:80],
                        "_source": "schema"})
        if out:
            return out
    # 兜底：词法（老路径语义不变，只改成 dict + `_source` 标签）
    return [{"what": str(_s)[:120], "why": "", "_source": "lexical"}
            for _s in _extract_not_do_lexical(view)]


def _extract_not_do_lexical(view) -> list:
    """ 原 `_extract_not_do` 的词法版（正文一字未动）。

    只在 schema 路径抽不到时兜底 —— 老产物 / 未升级 schema 的跑批。
    """
    text = (_act_text(view) or "") + "\n" + (_und_text(view) or "")
    if not text.strip():
        return []
    out: list = []
    for seg in text.replace("；", "。").replace(";", "。").split("。"):
        s = seg.strip()
        if len(s) < 4:
            continue
        if any(k in s for k in _NOT_DO_MARKS):
            out.append(s[:120])
        if len(out) >= 5:
            break
    return out


def _classify_unsaid(block) -> str:
    """ 「此处未生」的分类：`real`（真未生）/ `lazy`（偷懒）。

    红线上写着「悬置不打分、未生合法」，但**合法 ≠ 一律可信**：一条探针
    在没看过「本层未触及项」清单的情况下说「此处未生」，与它认真核过清单
    之后说未生，是两件事。判据取最便宜的那一个 —— 它有没有用 `covers`
    声明碰过清单里的东西：

      · 有非空 covers → `real`（认真看过才说未生）；
      · 无 covers / 空 covers / 非 mapping → `lazy`（没声称碰过任何东西）。

    ★ 负对照（写进冒烟）：`{"covers": []}` 必须判 `lazy`，不是 `real` ——
      否则「空数组」会被 fuzz 成通过，这个判据就永远亮了。
    """
    # ★ 两种入参形态都要吃（任务书 Step 1.5 的探针传的是 View 对象）：
    #   · View 形态：看 view.collision 与 view.probes[*].covers；
    #   · dict 形态：直接看 block["covers"]（早期调用点用它）。
    #   判据只有一条：说「此处未生」之前，有没有声明碰过「未触及项」清单。
    if not isinstance(block, dict):
        ing = str(getattr(block, "collision", "") or "")
        prb = list(getattr(block, "probes", None) or [])
        if not ing or ing.strip() == "（此处未生）":
            return "lazy"
        return "real" if any(
            (p.get("covers") or []) for p in prb if isinstance(p, dict)
        ) else "lazy"
    if "collision" in block or "probes" in block:
        ing = str(block.get("collision") or "")
        if not ing or ing.strip() == "（此处未生）":
            return "lazy"
        return "real" if any(
            (p.get("covers") or [])
            for p in (block.get("probes") or []) if isinstance(p, dict)
        ) else "lazy"
    cov = block.get("covers")
    if isinstance(cov, str):
        return "real" if cov.strip() else "lazy"
    if isinstance(cov, (list, tuple, set)):
        return "real" if len(cov) > 0 else "lazy"
    return "lazy"


_LAYER_CN = {"0": "修行层", "1": "研究层", "both": "对撞层", "all": "元层"}

_OBJECTIVE_CN = {
    "manifest": "把处境显形 —— 不求答案，因此不计覆盖率",
    "truth": "求可判定的真 —— 覆盖率只对这一层算",
    "collision": "求不可通约处 —— 对撞不改判定，只暴露张力",
    "closure": "求整体闭环 —— 不评价修行层，只交代留没留账",
}


def _layer_objective_lines(result=None) -> List[str]:
    """ 四层目标函数分层，一行一层，进产物头部。

    为什么要写进产物：以前「覆盖率」只有一个数，读者看不出**它属于哪一层**。
    修行层本来就不求答案 —— 拿它的覆盖率去衡量它，等于用错的尺。四行写清
    「这一层在求什么」，覆盖率的适用面就自明了。
    """
    if result is not None:
        _views = result.get("views") or {}
        _pools = result.get("pools") or {}

        def _g(k):
            return _views.get(k) or {}

        _p0, _p1 = _g("0"), _g("1")
        _pb, _pa = _g("both"), _g("all")
        out_c: List[str] = []
        out_c.append(
            f"  - 修行层（显形过程 · objective=manifest）："
            f"& {len(_p0.get('amps') or [])} / "
            f"线头 {len(_p0.get('threads') or [])} / "
            f"悬置 {len(_p0.get('suspensions') or [])} / "
            f"探针 {len(_p0.get('probes') or [])}")
        _st = _p1.get("settlement") or {}
        _cov = _st.get("coverage")
        _cov_s = f"{_cov:.0%}" if isinstance(_cov, (int, float)) else "N/A"
        _dist = (_p1.get("decidable_product") or {}).get("distance", "?")
        out_c.append(
            f"  - 研究层（逼近真理 · objective=truth）："
            f"覆盖率 {_cov_s} · distance {_dist}")
        _pbi = _pb.get("ing_structured") or {}
        out_c.append(
            f"  - 对撞层（第三者 · objective=collision）："
            f"third {'\u2713' if _pbi.get('third') else '\u2717'} · "
            f"张力 {len(_pbi.get('tensions') or [])}")
        _clo = _pa.get("meta_closure") or {}
        out_c.append(
            f"  - 元层（闭环清算 · objective=closure）："
            f"clean {_clo.get('clean')} · "
            f"未交代 {_clo.get('unsettled', 0)} 类")
        return out_c

    out: List[str] = []
    for e in ("0", "1", "both", "all"):
        o = getattr(PHASES.get(e), "objective", "?")
        out.append(f"- **{_LAYER_CN[e]}**：objective=`{o}` —— "
                   f"{_OBJECTIVE_CN.get(o, '')}")
    return out


# ============================================================
# 保存结果
# ============================================================
# ============================================================
# 自动规划（构造 MetaDGTF **之前**跑）
# ============================================================
#
# ★ 为什么要放在构造前：规划里的 route / rounds 决定层与圈数，
#   而 `MetaDGTF.__init__` 会按它们建池与状态。构造之后再想改，
#   改不动。所以完整规划必须在**拿到 MetaDGTF 之前**完成。
#
# 四个维度：route（走哪几层）/ mode（怎么并行）/ rounds（每层几圈）
#           / max_calls（总调用预算）
#
# 用法：
#   plan = auto_plan(question, cfg)
#   cfg["max_calls"]    = plan["max_calls"]
#   meta = MetaDGTF(cfg)
#   res  = meta.run(question, route=plan["route"],
#                   rounds=plan["rounds"], parallel_mode=plan["mode"])
# ============================================================

# 每层圈数的**可达性下限/上限**。
#   下限 4：停止判据要累计 ≥2 圈，元层再叠一条语义下限，给 3 圈以下
#           等于判据不可达（实测对撞 70% / 元 79% 被截断）。
#   上限 6：★ 先封到 5 试过，实测是**净亏** ——
#             · 没省下钱：给 5 圈 194 calls，给 6 圈反而 189 calls
#               （「给多不等于跑多」，层内会自己停，多给的圈不花）。
#             · 却把截断买回来了：4 圈 8/14、5 圈 11/23、6 圈 2/8 被截断。
#           所以上限放回 6。
#   ⚠️ 只在**用户什么都没指定**时生效（auto_plan / _auto_plan），
#      显式传 rounds 的不动。
_MIN_LAYER_ROUNDS = 4
_MAX_LAYER_ROUNDS = 6

# ★ 按层的上限：研究层封 5，其余 6。
#   实证（86 个真跑 + y 批次）：研究层 4 圈自然停 80%（n=44，最大样本）、
#   5 圈 69%、6 圈 86%，但**给 6 时实际中位仍是 4 圈** —— 多给的不花，
#   也不会更好。y 批次里给 4 的 4/4 全部安住，给 5/6 的是走满或晚一圈停。
#   而写在 prompt 里的实测表**模型没听**（y61e 仍给研究层 5 圈），
#   所以要落到代码上。
#   ★ 为什么不钉死 4：4 是数据最支持的档，但"研究"的外延很宽（事实题
#     拆清楚就够，开放题可能真要摊开），留到 5 给模型一点弹性，同时
#     挡掉最浪费的 6。
#   ★ 只对 auto/未指定生效，显式传 rounds 的不动。
_MAX_ROUNDS_BY_LAYER = {"1": 5}

# ★ 按层的下限：元层抬到 5（实际跑 6 圈）。
#   ▲ 这里**推翻了上一轮我自己写的结论**，得把过程写下来，不然下次
#     又会被同样的混杂数据骗回去：
#     · 上一轮从 86 个历史样本统计出「元层实际 4 圈自然停 68%、5 圈 32%」，
#       于是建议"元层不要给多"。那个结论是**题型混杂**的产物 —— 历史上
#       只有简单题才被给到 4 圈，难题天然分到了 6/7 圈，于是"4 圈"看起来
#       又省又好。按题型分层后 P 类 4 圈只剩 3/5。
#     · 严格单变量对照（同题「拆成几部分之后剩下的整体」、同 B 模式、
#       同 0:5/1:4/both:6，只变元层请求圈数）是**单调**的：
#           请求 3 → 实际 4：走满，未触发任何判据（157 calls）
#           请求 4 → 实际 5：走满，未触发任何判据（159 calls）
#           请求 5 → 实际 6：空转停（178 calls）
#           请求 6 → 实际 7：安住（181 calls）
#       给少了不是省钱，是**买截断** —— 元层前 4 圈还在不断开出新的
#       缺失（这就是它的活），判据根本没机会成立。
#     · 但"实际 5 圈"确实是个坑，跨模式跨题型一致（serial 0/4、B 1/9、
#       A 0/2、C 0/2；走满 26/40、真收敛 20%、clean 0/41）。它尴尬在
#       比 4 多一圈不够、比 6 少一圈所以判据没机会重新成立。
#   → 所以不是"给少"，而是"给够"：下限抬到请求 5（实际 6），把最差的
#     实际 5 圈整档跳过去。P 类实际 6 圈 6/9 = 67%，是最大样本里最好的。
_MIN_ROUNDS_BY_LAYER = {"all": 5}


def _layer_ceil(k: str, hard: int, floor: int) -> int:
    """某层的圈数上限。未单独配置的层用 _MAX_LAYER_ROUNDS。"""
    return max(floor, min(_MAX_ROUNDS_BY_LAYER.get(k, _MAX_LAYER_ROUNDS),
                          hard))


def _layer_floor(k: str, hard: int, floor: int) -> int:
    """某层的圈数下限。未单独配置的层用 floor（_MIN_LAYER_ROUNDS 钳过）。"""
    return max(floor, min(_MIN_ROUNDS_BY_LAYER.get(k, floor), hard))


def _plan_conf(data) -> float:
    """归一化 `confidence`：不可解析的输入一律记 0.0（= 最低置信 ⇒ 退 serial）。

    ★ 单调用分支原来是**裸** `float(...)`、不在 try 里 ⇒ 模型返回一个
      非数字字面量会抛 ValueError 逃出 auto_plan。这里统一兜住，兜的方向
      是保守的（0.0 < 阈值 ⇒ 退 serial）。
    """
    try:
        return float((data or {}).get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_orientation(v, fallback: str = "") -> str:
    """取向归一化的**唯一实现**（v1.23.13 合并前有三份，且 fallback 语义不同）。

    ★ 合并前的三处：`plan_orientation`（非法 → decision，保守）、
      `plan_resources`（非法 → decision）、单调用路径（非法 → ""，表示未知）。
      三份代码各自 normalize 同一个字段，是「同一条逻辑三条实现」。
      fallback 是**调用方语义**（外部 API 要保守值、热路径要「未知」），
      所以做成显式参数，而不是让实现分叉。
    """
    s = str(v or "").strip().lower()
    if s in ("boundary", "decision"):
        return s
    return fallback if fallback in ("boundary", "decision") else ""


def _assemble_plan(mode, rounds, cfg, route=None, orientation="", max_calls=0,
                   reason="", confidence=0.0, extra=None) -> dict:
    """**唯一装配器**：所有调度出口都过这里 ⇒ `auto_plan()` 只有一种 schema。

    ★ 技术债（v1.21.71 F8 起挂账）：单调用路径返回 `{mode, rounds, reason,
      orientation, confidence}`，两段式路径返回 `{route, mode, rounds,
      max_calls, orientation, reason, confidence, _auto}` ——
      同一个函数名按参数返回**两种形状**，`plan.get("route")` 在单调用路径下
      是 None。装到一处之后形状差异消失，`check_v71_auto_plan_agreement`
      从「漂移检测器」升格为「同一实现的构造性证明」。
    """
    out = {
        "route": [str(x) for x in (route or list(_ROUTE_PRESETS["full"]))],
        "mode": str(mode or "serial"),
        "rounds": dict(rounds or {}),
        "max_calls": int(max_calls or 0),
        "orientation": _normalize_orientation(orientation, ""),
        # ★ 这个键单调用路径本来没有 ⇒ 两条路径 schema 差一个键。
        #   放进基数里（默认空串），谁有理由谁在 `extra` 里覆盖它。
        "_orientation_reason": "",
        "reason": str(reason or "")[:200],
        "confidence": float(confidence or 0.0),
        "_auto": True,
    }
    if extra:
        out.update(extra)
    return out

def _normalize_plan_mode(data) -> str:
    """归一化 `mode`：只有 A~H 与 serial 两种结局，其余一律 serial。"""
    _up = str((data or {}).get("mode", "serial")).strip().upper()
    return _up if _up in ("A", "B", "C", "D", "E", "F", "G", "H") \
        else "serial"


def _normalize_plan_rounds(data, hard: int, route=None) -> dict:
    """归一化 `rounds`：解析 → 漏层按中位数补 → 钳到每层 [floor, ceil]。

    `route` 给了就按 route 裁剪 —— 那是**调用方**的语义（两段式路径要裁，
    单调用路径没有 route 概念），不是规则本身，所以做成可选参数而不是
    写死在规则里。
    """
    rnd = {}
    raw_r = (data or {}).get("rounds") or {}
    _floor = min(_MIN_LAYER_ROUNDS, hard)
    if isinstance(raw_r, dict):
        for k in ("0", "1", "both", "all"):
            try:
                iv = int(raw_r.get(k))
            except (TypeError, ValueError):
                continue
            if 1 <= iv <= hard:
                rnd[k] = max(iv, _floor)
    # ★ 漏层必须补齐，不能交给配置兜底 —— 真跑实证：a61H 的调度只给了
    #   修行4/研究4，对撞和元漏了 → 那两层走 hard_max（12/13）→ 元层跑满
    #   13 圈、体力耗尽被截断，整轮 20.7min；给全四层的 a61F 只要 9.7min。
    #   hard_max 是「最坏情况预算」，拿它当默认值等于默认最贵。
    if rnd and len(rnd) < 4:
        _vals = sorted(rnd.values())
        _fill = _vals[len(_vals) // 2]
        for k in ("0", "1", "both", "all"):
            rnd.setdefault(k, _fill)
        logger.info("自动调度漏层，按中位数 %d 补齐：%s", _fill, rnd)
    # 补齐值同样要过钳制区（中位数可能落在区间外）
    for k in list(rnd):
        rnd[k] = min(max(rnd[k], _layer_floor(k, hard, _floor)),
                     _layer_ceil(k, hard, _floor))
    if route is not None:
        rnd = {k: v for k, v in rnd.items() if k in route}
    return rnd

_ROUTE_PRESETS = {
    "full": ["0", "1", "both", "all"],
    "no_meta": ["0", "1", "both"],
    "duel_only": ["0", "1", "both"],
    "light": ["0", "1"],
}


# ============================================================
# 统一自适应调度器
# ============================================================
# 【要解决的问题】本版之前，「自动」散在 8 处：main() 里三条纯规则、
#   run() 里两次 LLM 调用、_route_by_decidability 一处，停止 / 降级 / 配额
#   写死在配置里。读者无法回答「这一次到底是**谁**定了 route / 圈数 / 联网」；
#   也没有任何一项能单独交给 auto —— 想「只让 auto 管圈数、其余固定」做不到。
#
# 【本版做法】把十一项收进**一个调度器**，逐项独立：
#       route / cost_profile / mode / rounds / orientation /
#       web / thinking / effort / stop / web_downgrade /
#       decidability / landing
#   每项按同一优先级取 4 个来源之一，并**逐项留痕**：
#       explicit（命令行显式给了） > config（配置被改过） > auto > default
#   ★ 铁律：explicit 或 config 给了，auto **就不碰那一项**（逐项独立，
#     不是「一个总开关管全部」）。
#   ★ 全关开关：`auto.enabled=false` ⇒ 全项退回 config/default，
#     行为与上一版逐字相同（判据守着这条）。
#
# 【auto 的输入】三样，全部本地可得、**零 LLM**：
#     ① 题型特征（`_auto_features`，纯规则，复用 `_has_decision_context`）
#     ② 成本质量意图（cost_profile / effort 的显式值、rounds 的效率约束）
#     ③ 历史读数（`_auto_history`，扫最近 N 份 `*.packed.json`）
#   auto 的**输出**是该项的值 + 理由，全部写进产物头部，可复盘。
#
# 【设计纪律】
#   · 每项都是可单独测的纯函数 `_auto_pick_<项>(feat, hist, cfg)`；
#   · 不引入任何新的判定语义 —— 停止 / 降级 / 配额本就是**配置驱动**的，
#     auto 接手的方式是「按题型与历史算出更合适的配置值」，判据本身一行未改；
#   · 历史读不到（0 份样本）时一律走「无历史」分支，不猜、不崩。
_AUTO_ITEM_ORDER = ("route", "mode", "rounds", "orientation",
                    "web", "thinking", "effort", "stop", "web_downgrade",
                    "decidability", "landing")

_AUTO_ITEM_LABEL = {
    "route": "层集合",
    "mode": "并行模式",
    "rounds": "圈数",
    "orientation": "取向路由",
    "web": "联网检索",
    "thinking": "思考",
    "effort": "思考强度",
    "stop": "停止阈值",
    "web_downgrade": "联网降级",
    "decidability": "可判定性判定",
    "landing": "落地层模板",
}

_AUTO_SRC_LABEL = {
    "explicit": "显式",
    "config": "配置",
    "auto": "auto",
    "default": "默认",
}

_AUTO_META_MARKS = ("本身", "自身", "递归", "元", "整体", "到底")

#: 各层圈数的**实测默认**（384 条真实语料里「种子上限」的中位数）。
#: 用途：历史里既没有实际停圈、也没有种子上限时的最后回退。
_AUTO_ROUNDS_BASE = {"0": 4, "1": 4, "both": 5, "all": 6}

#: 「实际停圈」要多少份样本才值得信。低于它退回「种子上限」——
#: 实测：真实语料里落 packed 的只有 1 份；若只按「有没有」判断，
#: 单条噪声（`{'1': 1}`）会盖掉 200 份的种子上限分布。
_AUTO_ACT_MIN = 3

#: 三态一致率的**异常线**。真实语料 254 份实测 p10 = 0.167
#: （p50 = 0.333 —— 旧门槛 0.5 在中位数之上，会拦掉 54%，等于废掉降档）。
_AUTO_TRI_FLOOR = 0.167

#: 三态一致率要多少份样本才够用来判「异常」。低于它不表态。
_AUTO_TRI_MIN_N = 30

#: 截断率要多少**层**样本才够。实测语料只有 5 层 —— 不足以下结论。
_AUTO_STOP_MIN_N = 24

#: 该项「配置给了」的判定路径（任一被改过即算）。值 = 路径元组的列表。
_AUTO_CONFIG_PATHS = {
    "web": [("runtime", "web")],
    "thinking": [("runtime", "thinking")],
    "effort": [("runtime", "effort")],
    "mode": [("actions", "parallel_mode")],
    "stop": [("spiral", "round_stall_limit"),
             ("spiral", "round_idle_limit")],
    "web_downgrade": [("web_search", "auto_disable_after_failures"),
                      ("web_search", "quota", "per_run_total")],
}


def _auto_enabled(cfg) -> bool:
    """总开关。缺省 True（出厂即接管）；显式 false 回到 v1.23.12 行为。"""
    return bool(((cfg or {}).get("auto") or {}).get("enabled", True))


def _auto_save_dir(cfg) -> str:
    return str(((cfg or {}).get("output") or {}).get("save_dir", "outputs"))


def _cfg_get_path(cfg, path, default=None):
    cur = cfg
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _cfg_has_path(cfg, path) -> bool:
    """配置里**改过**该路径（与出厂 DEFAULT_CONFIG 不同）才算「配置给了」。"""
    _cur, _def = _cfg_get_path(cfg, path), _cfg_get_path(DEFAULT_CONFIG, path)
    return _cur is not None and _cur != _def


def _cfg_overridden(cfg, name) -> bool:
    return any(_cfg_has_path(cfg, p) for p in _AUTO_CONFIG_PATHS.get(name, []))


def _set_cfg_path(cfg, path, value) -> None:
    cur = cfg
    for k in path[:-1]:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    cur[path[-1]] = value


def _auto_normalize_explicit(ex) -> dict:
    """把命令行原值归一成调度器的取值域（`auto` / 空串 = 没给 ⇒ None）。

    ★ 不做归一化会把 `--web auto` 当成「显式给了 on」—— `"auto"` 是**真值**
      字符串，直接用会静默把「没指定」记成「显式指定」。
    """
    out = {}
    for k, v in dict(ex or {}).items():
        if v is None:
            continue
        if k in ("web", "thinking"):
            s = str(v).strip().lower()
            if s == "auto":
                continue
            out[k] = {"on": True, "off": False}.get(s)
            if out[k] is None:
                out.pop(k)
            continue

        if k in ("mode", "orientation", "landing",
                 "decidability"):
            s = str(v).strip()
            if not s or s.lower() == "auto":
                continue
            out[k] = s
            continue
        if k == "effort":
            s = str(v).strip().lower()
            if not s or s == "auto":
                continue
            out[k] = s
            continue
        if k == "route":
            if isinstance(v, (list, tuple)):
                _r = [str(x).strip() for x in v if str(x).strip()]
            else:
                _r = [x.strip() for x in str(v).split(",") if x.strip()]
            if not _r:
                continue
            out[k] = _r
            continue
        if k == "rounds":
            s = str(v).strip()
            if not s or s == "0":
                continue
            out[k] = s
            continue
        out[k] = v
    return out


# ------------------------------------------------------------
# ① 题型特征（纯规则，零 LLM）
# ------------------------------------------------------------
def _auto_features(question: str) -> dict:
    """题型 + 规模 + 意图线索。全部来自题面字符，可复现、可断言。"""
    q = str(question or "").strip()
    return {
        "len": len(q),
        "blank": not q,
        "fact": (not q) or (not _has_decision_context(q)),
        "meta": any(k in q for k in _AUTO_META_MARKS),
        "multi": (q.count("，") + q.count(",")) >= 3,
        "choice": ("或" in q) or ("还是" in q),
        "how": any(k in q for k in ("如何", "怎样", "怎么")),
        "what": any(k in q for k in ("是什么", "为什么")),
        "short": 0 < len(q) <= 40,
    }


# ------------------------------------------------------------
# ② 历史读数（扫最近 N 份 packed，零 LLM）
# ------------------------------------------------------------
def _hist_wquant(pairs, p, as_int: bool = True):
    """**加权**分位数（线性插值）。`pairs = [(值, 权重)]`；空 → None。

    ★ 为什么要加权：语料跨了十几天，旧样本的「成本/停圈」是**旧配置**下的读数
      （那时默认给满 12 圈），直接与今天的读数拉平均会系统性偏向旧行为。
      时间衰减（半衰期可配）让新样本说话更响。
    ★ `as_int=False` 用于比率类读数（如三态一致率），否则会被截成 0/1。
    """
    _ps = [(float(v), float(w)) for v, w in (pairs or [])
           if v is not None and w and w > 0]
    if not _ps:
        return None
    _ps.sort(key=lambda x: x[0])
    _tot = sum(w for _, w in _ps)
    if _tot <= 0:
        return None
    _target = p * _tot
    _acc = 0.0
    for _i, (_v, _w) in enumerate(_ps):
        _nxt = _acc + _w
        if _nxt >= _target:
            if _i == 0 or _w <= 0:
                _r = _v
            else:
                _prev = _ps[_i - 1][0]
                _r = _prev + (_v - _prev) * ((_target - _acc) / _w)
            return int(round(_r)) if as_int else round(_r, 4)
        _acc = _nxt
    _last = _ps[-1][0]
    return int(round(_last)) if as_int else round(_last, 4)


def _hist_quant(xs, p):
    """无权重的分位数（`_hist_wquant` 的退化情形）。保留给「权重全等」对照。"""
    return _hist_wquant([(x, 1.0) for x in (xs or [])], p)


def _hist_blank() -> dict:
    return {"n": 0, "sources": {}, "calls": [], "tokens": [], "tri": [],
            "stop_nat": 0, "stop_cut": 0, "actual": {}, "cap": {},
            "modes": {}, "profiles": {}, "orientations": {},
            "web_hit": 0, "web_fail": 0, "web_empty": 0, "web_runs": 0,
            "mismatch": 0}


def _hist_add(acc, rec, w: float = 1.0) -> None:
    """把一条记录并进累加器（带权重）。字段缺省一律容忍。"""
    if not isinstance(rec, dict):
        return
    _w = float(w) if (w and w > 0) else 1.0
    acc["n"] += 1
    _s = str(rec.get("src") or "?")
    acc["sources"][_s] = acc["sources"].get(_s, 0) + 1
    for _k in ("calls", "tokens"):
        _v = rec.get(_k)
        if isinstance(_v, int) and _v > 0:
            acc[_k].append((_v, _w))
    _t = rec.get("tri")
    if isinstance(_t, (int, float)):
        acc["tri"].append((float(_t), _w))
    for _a, _b in (("stop_nat", "nat"), ("stop_cut", "cut")):
        _v = rec.get(_b)
        if isinstance(_v, int) and _v >= 0:
            acc[_a] += _v
    for _key, _dst in (("actual_rounds", "actual"), ("cap_rounds", "cap")):
        for _e, _v in (rec.get(_key) or {}).items():
            if isinstance(_v, int) and _v > 0:
                acc[_dst].setdefault(_e, []).append((_v, _w))
    for _key, _dst in (("mode", "modes"), ("profile", "profiles"),
                       ("orientation", "orientations")):
        _v = str(rec.get(_key) or "")
        if _v:
            acc[_dst][_v] = acc[_dst].get(_v, 0) + 1
    for _k in ("web_hit", "web_fail", "web_empty", "mismatch"):
        _v = rec.get(_k)
        if isinstance(_v, int) and _v > 0:
            acc[_k] += _v
    if isinstance(rec.get("web_hit"), int) and rec.get("web_hit") > 0:
        acc["web_runs"] += 1


def _hist_finish(acc) -> dict:
    out = {
        "n": acc["n"], "sources": dict(acc["sources"]),
        "calls_med": _hist_wquant(acc["calls"], .5) or 0,
        "calls_p75": _hist_wquant(acc["calls"], .75) or 0,
        "tokens_med": _hist_wquant(acc["tokens"], .5) or 0,
        "tokens_p75": _hist_wquant(acc["tokens"], .75) or 0,
        "tri_n": len(acc["tri"]),
        "tri_rate": _hist_wquant(acc["tri"], .5, as_int=False),
        "tri_p10": _hist_wquant(acc["tri"], .10, as_int=False),
        "stop_n": acc["stop_nat"] + acc["stop_cut"],
        "cut_rate": ((acc["stop_cut"] / (acc["stop_nat"] + acc["stop_cut"]))
                     if (acc["stop_nat"] + acc["stop_cut"]) else None),
        "layer_rounds": {}, "cap_rounds": {},
        "layer_rounds_n": {}, "cap_rounds_n": {},
        "modes": dict(acc["modes"]), "profiles": dict(acc["profiles"]),
        "orientations": dict(acc["orientations"]),
        "web_hit": acc["web_hit"], "web_fail": acc["web_fail"],
        "web_empty": acc["web_empty"], "web_runs": acc["web_runs"],
        "mismatch": acc["mismatch"],
    }
    for _e in _ENTRIES:
        _xs = acc["actual"].get(_e) or []
        if _xs:
            # ★ 样本数**总是**记（哪怕中位数因不足门槛而没被采纳）——
            #   否则读产物的人分不清「没有样本」与「有样本但没采纳」。
            out["layer_rounds_n"][_e] = len(_xs)
        _v = _hist_wquant(_xs, .5)
        if _v and len(_xs) >= _AUTO_ACT_MIN:
            out["layer_rounds"][_e] = _v
        _xs2 = acc["cap"].get(_e) or []
        if _xs2:
            out["cap_rounds_n"][_e] = len(_xs2)
        _v2 = _hist_wquant(_xs2, .5)
        if _v2:
            out["cap_rounds"][_e] = _v2
    return out


def _hist_from_packed(d: dict) -> dict:
    """从 packed 快照抽一条记录（**全量字段**，最准）。"""
    if not isinstance(d, dict):
        return {}
    q = str(d.get("question") or "")
    rec = {"src": "packed", "q": q,
           "calls": int(d.get("llm_calls") or 0),
           "tokens": int(d.get("llm_tokens") or 0),
           "mode": str(((d.get("dispatch") or {}).get("_parallel_mode")) or ""),
           "profile": str(d.get("cost_profile") or ""),
           "orientation": str(d.get("orientation") or ""),
           "actual_rounds": {}, "cap_rounds": {}}
    _t = d.get("tri_state") or [0, 0]
    try:
        if int(_t[1]):
            rec["tri"] = int(_t[0]) / int(_t[1])
    except (TypeError, ValueError, IndexError):
        pass
    for _e, _v in (d.get("views") or {}).items():
        if not isinstance(_v, dict):
            continue
        _sr = str(_v.get("stop_reason") or "")
        if _sr:
            if any(_m in _sr for _m in _STOP_CUT_MARKS):
                rec["cut"] = rec.get("cut", 0) + 1
            else:
                rec["nat"] = rec.get("nat", 0) + 1
        # ★ 字段名是 `rounds_run`（实际跑了几圈），不是 `rounds`
        #   —— 上一版这里读错，实际停圈**永远取不到**（静默）。
        _rn = _v.get("rounds_run")
        if isinstance(_rn, int) and _rn > 0:
            rec["actual_rounds"][str(_e)] = _rn
        _rc = _v.get("rounds_cap")
        if isinstance(_rc, int) and _rc > 0:
            rec["cap_rounds"][str(_e)] = _rc
    for _p in (d.get("pools") or {}).values():
        if not isinstance(_p, dict):
            continue
        rec["web_hit"] = rec.get("web_hit", 0) + len(_p.get("web_results") or [])
        rec["web_fail"] = rec.get("web_fail", 0) + len(_p.get("web_errors") or [])
        rec["web_empty"] = rec.get("web_empty", 0) + sum(
            1 for _x in (_p.get("meta") or []) if "[W-EMPTY]" in str(_x))
    _ap = d.get("_auto_plan_used") or {}
    _sug = str(_ap.get("orientation") or "")
    _act = str(d.get("orientation") or "")
    if _sug and _act and _sug != _act:
        rec["mismatch"] = 1
    return rec


_HIST_RE_CALLS = re.compile(
    r"\*\*资源\*\*[:：]\s*(\d+) 次 LLM \| (\d+) tokens")
_HIST_RE_MODE = re.compile(r"\*\*并行模式\*\*[:：]\s*([A-H]) ·")
_HIST_RE_MODE_SER = re.compile(r"\*\*并行模式\*\*[:：]\s*(严格串行)")
_HIST_RE_PROF = re.compile(r"\*\*成本档位\*\*[:：]\s*(\w+)")
_HIST_RE_ROUTE = re.compile(r"\*\*调度\*\*[:：]\s*(.+)")
_HIST_RE_LAYER = re.compile(r"([\u4e00-\u9fff]+)\((\d+)圈\)")
_HIST_RE_STOP = re.compile(
    r"\*\*停止\*\*[:：]\s*自然 (\d+) 层 / 被截断（体力耗尽）(\d+) 层")
_HIST_RE_ORI = re.compile(r"\*\*取向\*\*[:：]\s*(auto|boundary|decision)")
_HIST_RE_Q = re.compile(r"^# 元 DGTF · (.+)$", re.M)
_HIST_RE_TRI = re.compile(r"\*\*三态判决一致率\*\*[:：]\s*(\d+)\s*/\s*(\d+)")
_HIST_RE_WEB = re.compile(
    r"\*\*外部锚点 · 联网\*\*（`web_search`）[:：](.*)")
_HIST_RE_WEB_OK = re.compile(r"收\s*(\d+)\s*条")
_HIST_RE_WEB_FAIL = re.compile(r"失败\s*(\d+)\s*条")
_HIST_LAYER2E = {"修行": "0", "研究": "1", "对撞": "both", "元": "all"}


def _hist_from_md(head: str) -> dict:
    """从产物 md 的**头部片段**抽一条记录。

    ★ 只读前 8KB：头部信息全在里面，产物正文可能几百 KB。
    ★ 这里的圈数是**配置给的种子上限**（`**调度**：修行(4圈)`），
      不是实际停圈 —— 归到 `cap_rounds`，不与 `actual_rounds` 混。
    ★ 抽不到的字段就**不写键**（不要写 0）—— 否则「零样本」与「样本值为 0」
      会被混为一谈（`web_fail = 0` 与「没有联网这一行」是两件事）。
    """
    if not head:
        return {}
    m = _HIST_RE_CALLS.search(head)
    if not m:
        return {}
    rec = {"src": "md", "calls": int(m.group(1)), "tokens": int(m.group(2)),
           "actual_rounds": {}, "cap_rounds": {}}
    _mq = _HIST_RE_Q.search(head)
    rec["q"] = _mq.group(1).strip() if _mq else ""
    _mm = _HIST_RE_MODE.search(head) or _HIST_RE_MODE_SER.search(head)
    rec["mode"] = _mm.group(1) if _mm else ""
    _mp = _HIST_RE_PROF.search(head)
    rec["profile"] = _mp.group(1) if _mp else ""
    _mo = _HIST_RE_ORI.search(head)
    rec["orientation"] = _mo.group(1) if _mo else ""
    _mr = _HIST_RE_ROUTE.search(head)
    if _mr:
        for _a, _b in _HIST_RE_LAYER.findall(_mr.group(1)):
            rec["cap_rounds"][_HIST_LAYER2E.get(_a, _a)] = int(_b)
    _ms = _HIST_RE_STOP.search(head)
    if _ms:
        rec["nat"], rec["cut"] = int(_ms.group(1)), int(_ms.group(2))
    # ★ 三态一致率：产物里 254/368 都写了，而上一版抽取器漏了它 ——
    #   于是「同类题一致率」这条读数只有 n=1，规则形同没校准。
    _mt = _HIST_RE_TRI.search(head)
    if _mt and int(_mt.group(2)) > 0:
        rec["tri"] = int(_mt.group(1)) / int(_mt.group(2))
    # ★ 联网行（本版起产物才有）：把「收了 N 条 / 失败 N 条」也吃进来。
    _mw = _HIST_RE_WEB.search(head)
    if _mw:
        _body = _mw.group(1)
        _ok = _HIST_RE_WEB_OK.search(_body)
        _fa = _HIST_RE_WEB_FAIL.search(_body)
        if _ok:
            rec["web_hit"] = int(_ok.group(1))
        if _fa:
            rec["web_fail"] = int(_fa.group(1))
    return rec


def _hist_from_batch(d) -> List[dict]:
    """从跑批 JSON（`*_runs.json`）抽记录：富字段、样本少。"""
    out: List[dict] = []
    if not isinstance(d, dict):
        return out
    for _x in (d.get("runs") or []):
        if not isinstance(_x, dict) or not _x.get("ok"):
            continue
        out.append({"src": "batch",
                    "q": str(_x.get("question") or ""),
                    "calls": int(_x.get("llm_calls") or _x.get("calls") or 0),
                    "mode": "", "profile": "", "orientation": "",
                    "actual_rounds": {}, "cap_rounds": {},
                    "web_hit": int(_x.get("web_n") or 0),
                    "web_fail": int(_x.get("web_errors_n") or 0),
                    "web_empty": int(_x.get("web_empty_n") or 0)})
    return out


def _hist_decay(cfg) -> float:
    """时间衰减的半衰期（天）。`auto.history_halflife_days`，缺省 14；0 = 不衰减。"""
    try:
        v = float((((cfg or {}).get("auto") or {}).get(
            "history_halflife_days", 14)) or 0)
    except (TypeError, ValueError):
        v = 14.0
    return max(0.0, v)


def _hist_weight(mtime, half_life: float, now: float = None) -> float:
    """`0.5 ** (age_days / half_life)`；半衰期 ≤0 或 mtime 缺失 → 1.0（不衰减）。"""
    if not half_life or not mtime:
        return 1.0
    _now = now if now is not None else time.time()
    _age = max(0.0, (_now - float(mtime)) / 86400.0)
    return float(0.5 ** (_age / half_life))


def _auto_history(save_dir, limit: int = 200, cfg=None,
                  want_md: bool = True, want_batch: bool = True) -> dict:
    """把历史真跑语料抽成可复用的读数 —— 三类来源 + 分层 + 时间衰减。

    ① `**/*.packed.json`  —— 全量字段（最准），含 `views.*.rounds_run`；
    ② `**/*.md`           —— 头部行（覆盖最广）；只读前 8KB；
    ③ `*_runs.json`（仓库根）—— 跑批记录，富字段（llm_calls / web_*），样本少。

    ★ **`limit` 是「每题型上限」**（不是总数）：按题型分两桶各自最多取 `limit`
      条 —— 否则窗口一缩，某一型（尤其是事实型）会被整体挤掉，
      「按题型比同类」就退化成「比全语料」。
    ★ **时间衰减**：权重 `0.5 ** (age_days / 半衰期)`。旧样本是旧配置下的读数，
      不加权会让新读数被系统性拉向旧行为。半衰期 0 = 关掉衰减。
    ★ 半损坏样本只跳过自己；零样本不崩；抽不到的字段**不写键**。
    """
    _cfg = cfg if isinstance(cfg, dict) else {}
    _lim = max(1, int(limit or 200))
    _hl = _hist_decay(_cfg)
    _now = time.time()
    _acc_all, _acc_f, _acc_nf = _hist_blank(), _hist_blank(), _hist_blank()
    _cnt = {"f": 0, "nf": 0}

    def _put(rec, mtime):
        if not rec:
            return False
        _q = str(rec.get("q") or "")
        _w = _hist_weight(mtime, _hl, _now)
        _hist_add(_acc_all, rec, _w)
        if _q and _has_decision_context(_q):
            if _cnt["nf"] < _lim:
                _hist_add(_acc_nf, rec, _w)
                _cnt["nf"] += 1
        elif _q:
            if _cnt["f"] < _lim:
                _hist_add(_acc_f, rec, _w)
                _cnt["f"] += 1
        # 两桶都满 ⇒ 可以提前停（不再往下扫旧文件）
        return _cnt["f"] >= _lim and _cnt["nf"] >= _lim

    try:
        _root = Path(str(save_dir or "outputs"))
    except Exception:  # noqa: BLE001
        return _hist_finish(_acc_all)

    def _files(pat, cap):
        try:
            if not _root.is_dir():
                return []
            _fs = sorted(_root.rglob(pat),
                         key=lambda p: p.stat().st_mtime, reverse=True)
            return _fs[:cap]
        except Exception as exc:  # noqa: BLE001
            logger.warning("调度历史：列 %s 失败（%s）", pat, exc)
            return []

    # ★ 扫描上限 4×limit：两桶各要 limit 条，留 2 倍余量给「某一型被挤掉」的情况。
    _cap = max(_lim * 4, _lim)
    for _f in _files("*.packed.json", _cap):
        try:
            _done = _put(_hist_from_packed(json.loads(
                _f.read_text(encoding="utf-8"))), _f.stat().st_mtime)
            if _done:
                break
        except Exception:  # noqa: BLE001
            continue
    if want_md:
        for _f in _files("*.md", _cap):
            try:
                with open(_f, "r", encoding="utf-8",
                          errors="replace") as _fh:
                    _rec = _hist_from_md(_fh.read(8192))
                if _put(_rec, _f.stat().st_mtime):
                    break
            except Exception:  # noqa: BLE001
                continue
    if want_batch:
        try:
            _broot = _root.resolve().parent
            for _f in sorted(_broot.glob("*_runs.json")):
                if _f.name.startswith("_bak_"):
                    continue
                try:
                    _mt = _f.stat().st_mtime
                    for _r in _hist_from_batch(
                            json.loads(_f.read_text(encoding="utf-8"))):
                        _put(_r, _mt)
                except Exception:  # noqa: BLE001
                    continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("调度历史：跑批 JSON 失败（%s）", exc)

    out = _hist_finish(_acc_all)
    out["_limit_per_type"] = _lim
    out["_half_life_days"] = _hl
    out["by_type"] = {"fact": _hist_finish(_acc_f),
                      "nonfact": _hist_finish(_acc_nf)}
    return out


def _hist_for(feat, hist) -> dict:
    """取**与本题同题型**的那份历史（无同型样本则退全语料）。"""
    _bt = (hist or {}).get("by_type") or {}
    _k = "fact" if feat.get("fact") else "nonfact"
    _sub = _bt.get(_k) or {}
    return _sub if int(_sub.get("n") or 0) > 0 else (hist or {})


# ------------------------------------------------------------
# ③ 十一项策略（各自适应条件）
#   返回 (值, 理由)。返回 None = **auto 不表态**（按配置/默认）。
# ------------------------------------------------------------




    return base, why


def _auto_pick_web(feat, hist, cfg):
    """联网：事实题与「要外部标准」的题默认接；历史收 0 条则不再接。"""
    _n = int(hist.get("n") or 0)
    if _n >= 3 and int(hist.get("web_hit") or 0) == 0 \
            and int(hist.get("web_empty") or 0) >= 3:
        return False, ("历史 %d 份里联网入池 0 条、空结果 ≥3 次，该类题不再"
                       "自动接入（要接：--web on）" % _n)
    if feat["fact"]:
        return True, "事实型询问：史实结论需要外部证据支撑"
    if feat["meta"] or feat["how"]:
        return True, "含元层/过程：需要外部标准与先例"
    return None, "既非事实型也无外部标准需求"


def _auto_pick_thinking(feat, hist, cfg):
    if feat["fact"] and feat["short"]:
        return False, "事实型短题：一次判定够用，省 token"
    if feat["meta"] or feat["choice"]:
        return True, "含元层/选择：需要跨步推理"
    return None, "无明确信号"


def _auto_pick_effort(feat, hist, cfg):
    if feat["meta"] or feat["choice"] or feat["how"]:
        return "high", "含元层/选择/过程：拉高思考强度"
    if feat["fact"] and feat["short"]:
        return "low", "事实型短题：低强度"
    return None, "无明确信号"


def _auto_pick_route(feat, hist, cfg):
    """层集合：默认全四层；只在有正当理由时才砍（`auto.allow_route_trim` 可关）。"""
    if not bool(((cfg or {}).get("auto") or {}).get("allow_route_trim", True)):
        return list(_ENTRIES), "auto.allow_route_trim=false：不砍层"
    # ★ 截断率要**够层样本**才信：实测语料里只有 5 层（产物里的「停止」行是后来才加的），
    #   5 层的比率不足以决定「要不要砍层」。门槛以下不表态。
    _cr = hist.get("cut_rate")
    _sn = int(hist.get("stop_n") or 0)
    if _cr is not None and _sn >= _AUTO_STOP_MIN_N and _cr >= 0.5:
        return list(_ENTRIES), ("历史被截断率 %.2f 偏高（n=%d 层），保留全四层"
                                % (_cr, _sn))
    if feat["meta"] or feat["choice"] or feat["how"] or feat["multi"]:
        return list(_ENTRIES), "题面需要对撞/元层"
    if feat["fact"] and feat["short"]:
        return ["0", "1", "both"], "事实型短题：元层不参与判定，砍掉省一段"
    return list(_ENTRIES), "无砍层依据，保留全四层"


def _auto_pick_orientation(feat, hist, cfg):
    """取向路由：决定是否按可判定性砍层（与落地层模板**已解耦**）。"""
    if feat["fact"]:
        return "boundary", "事实型询问：要边界与事实，不要行动方案"
    if feat["meta"] or feat["how"] or feat["choice"]:
        return "decision", "含元层/过程/选择：要可落地方案"
    _mm = int(hist.get("mismatch") or 0)
    if _mm >= 2:
        return "decision", "历史取向错配 %d 次，保守取 decision" % _mm
    return "boundary", "无决策语境：保守走边界清单"


def _auto_pick_mode(feat, hist, cfg):
    """并行模式：规则能定时不调 LLM（省一次调用）；返回 `llm` = 交 LLM 兜底。"""
    if feat["blank"]:
        return "serial", "空题面"
    if feat["fact"] and feat["short"]:
        return "serial", "事实型短题：层间依赖强，无并行收益"
    if feat["meta"] and feat["multi"]:
        return "A", "多分句且含元层：四层可独立产出后汇流"
    if feat["choice"]:
        return "B", "含选择：需要震荡收敛"
    if feat["how"] and feat["multi"]:
        return "C", "多分句且讲过程：层界清楚，可流水线压缩时长"
    return "llm", "规则拿不准，交 LLM 决策"


def _auto_pick_rounds(feat, hist, cfg):
    """圈数：**实际停圈 → 种子上限 → 按层实测默认** 三级回退。

    ★ 校准依据（真实语料 384 条）：各层**种子圈数上限**实测 p50 =
      修行 4 / 研究 4 / 对撞 5 / 元 6。所以「无历史时统一给 soft_max+2=5」
      对前两层偏高、对元层偏低；改成按层给实测中位（`_AUTO_ROUNDS_BASE`）。
    ★ 实际停圈（`views.*.rounds_run`）优先 —— 它才是真信号；但当前语料里
      只有落 packed 的那几次有，所以必须有回退链，而不是「取不到就当 0」。
    """
    hard = int(((cfg or {}).get("spiral") or {}).get("hard_max", 12) or 12)
    _floor = min(_MIN_LAYER_ROUNDS, hard)
    _act = (hist.get("layer_rounds") or {})
    _act_n = (hist.get("layer_rounds_n") or {})
    _cap = (hist.get("cap_rounds") or {})
    _cap_n = (hist.get("cap_rounds_n") or {})
    out, _src_layers = {}, []
    for e in _ENTRIES:
        _a = int(_act.get(e) or 0)
        _c = int(_cap.get(e) or 0)
        # ★ 实际停圈优先，但要够样本（`_AUTO_ACT_MIN`）—— 见该常量注释。
        if _a > 0 and int(_act_n.get(e) or 0) >= _AUTO_ACT_MIN:
            _v, _k = _a + 1, "实际停圈(n=%d)" % int(_act_n.get(e) or 0)
        elif _c > 0:
            _v, _k = _c, "种子上限(n=%d)" % int(_cap_n.get(e) or 0)
        elif feat["fact"] and feat["short"]:
            _v, _k = _floor, "题型基线"
        else:
            _v, _k = int(_AUTO_ROUNDS_BASE.get(e, max(3, _floor))), "实测默认"
        _v2 = min(max(_v, _layer_floor(e, hard, _floor)),
                  _layer_ceil(e, hard, _floor))
        # ★ 报**钳制后**的值：报钳制前的原始值会与产物「取值」列不一致。
        _src_layers.append("%s=%d(%s%s)"
                           % (_LAYER_LABEL.get(e, e), _v2,
                              _k, "，原始 %d 被钳" % _v if _v2 != _v else ""))
        out[e] = _v2
    _src = "按层：%s（实际停圈需 ≥%d 份样本才采用）" % (
        "、".join(_src_layers), _AUTO_ACT_MIN)
    return out, _src


def _auto_pick_stop(feat, hist, cfg):
    """停止阈值：只调**阈值**，不动判据本身。"""
    if feat["fact"] and feat["short"]:
        return ({"round_stall_limit": 1, "round_idle_limit": 1},
                "事实型短题：收紧停滞阈值，早停")
    if feat["meta"]:
        return ({"round_stall_limit": 3, "round_idle_limit": 3},
                "含元层：放宽停滞阈值，允许更久收敛")
    return {}, "无明确信号，按配置"


def _auto_pick_web_downgrade(feat, hist, cfg):
    """联网降级：失败历史决定「连败几次置 disabled」，成本档决定配额。"""
    _f = int(hist.get("web_fail") or 0)
    _lim = 2 if _f >= 3 else (4 if _f == 0 else 3)
    _why = "历史联网失败 %d 条 ⇒ 连败阈值 %d" % (_f, _lim)
    _q = {"per_run_total": 30, "per_stage_total": 8, "per_stage_round": 2}
    return {"auto_disable_after_failures": _lim, "quota": _q}, _why


def _auto_pick_decidability(feat, hist, cfg):
    """要不要花那次**外部可判定性评估**（route 侧那次 LLM 调用）。"""
    if feat["fact"] and feat["short"]:
        return False, "事实型短题：层集合已按题型定，不必再花一次外部评估"
    return True, "需要按可判定性决定砍层"


def _auto_pick_landing(feat, hist, cfg):
    """落地层模板 —— 与取向**已解耦**（取向管砍层，本项管产物形态）。"""
    if feat["fact"]:
        return "boundary", "事实型询问：要边界清单，不要行动闭环"
    if feat["meta"] or feat["how"] or feat["choice"]:
        return "decision", "含元层/过程/选择：要可落地方案"
    return "boundary", "无决策语境：边界清单"


_AUTO_PICKERS = {
    "web": _auto_pick_web,
    "thinking": _auto_pick_thinking,
    "effort": _auto_pick_effort,
    "route": _auto_pick_route,
    "orientation": _auto_pick_orientation,
    "mode": _auto_pick_mode,
    "rounds": _auto_pick_rounds,
    "stop": _auto_pick_stop,
    "web_downgrade": _auto_pick_web_downgrade,
    "decidability": _auto_pick_decidability,
    "landing": _auto_pick_landing,
}


def auto_dispatch(question: str, config=None, explicit=None,
                  save_dir=None, history=None) -> dict:
    """十一项一次算完。返回 dict：每项一个值 + `_items` 逐项来源留痕。

    ★ 逐项优先级：explicit > config（**改过**才认）> auto > default。
    ★ `auto.enabled=false` ⇒ 十一项一律不进 auto 分支（回 v1.23.12 行为）。
    ★ 纯函数：不改入参 config；写回配置由调用方调 `_apply_auto_dispatch`。
    """
    cfg = config if config is not None else load_config("")
    ex = _auto_normalize_explicit(explicit)
    feat = _auto_features(question)
    _acfg = (cfg or {}).get("auto") or {}
    if history is not None:
        hist = history
    else:
        hist = _auto_history(
            save_dir or _auto_save_dir(cfg),
            int(_acfg.get("history_limit", 200) or 200), cfg=cfg,
            want_md=bool(_acfg.get("history_md", True)),
            want_batch=bool(_acfg.get("history_batch", True)))
    _on = _auto_enabled(cfg)

    plan = {"_features": feat, "_history": hist, "_items": {}, "_auto_on": _on}
    for name in _AUTO_ITEM_ORDER:
        val, why = _AUTO_PICKERS[name](feat, hist, cfg)
        if ex.get(name) is not None:
            src, v = "explicit", ex[name]
        elif _cfg_overridden(cfg, name):
            src = "config"
            v = _cfg_get_path(cfg, _AUTO_CONFIG_PATHS[name][0], None)
        elif (not _on) or val is None:
            src, v = "default", None
            for _p in _AUTO_CONFIG_PATHS.get(name, []):
                _cv = _cfg_get_path(cfg, _p, None)
                # ★ 配置里的字面 `"auto"` 等于「没表态」（运行期三项的默认值
                #   就是它）；把它当成「配置给了」会把「没指定」记成「指定」。
                if _cv is not None and _cv != "auto":
                    v, src = _cv, "config"
                    break
            if v is None:
                v = val
                why = "auto 不表态（" + str(why) + "），不覆盖配置"
        else:
            src, v = "auto", val
        plan[name] = v
        plan["_items"][name] = {"value": v, "source": src,
                                "reason": why, "auto_value": val}
    return plan


def _apply_auto_dispatch(cfg: dict, plan: dict) -> List[str]:
    """把 plan 写进配置键（来源 ∈ {auto, 显式} 的项）。返回留痕行。

    ★★ 必须写 **explicit** 项，不能只写 auto 项 —— 这是本版首版的一个真 bug：
      explicit 的值原先只存在于 plan 里、没人搬进 cfg，于是
      `--web off` / `--thinking on` / `--effort max`
      **全部失效**（`_apply_runtime` 读到的还是配置里的 `auto`）。
      「来源」是给**留痕**用的（产物表里显示谁定的），不是给「写不写」用的。
    ★ 不写 config / default 项：它们的值本来就已在 cfg 里，再写是空转。
    ★ 停止 / 降级 / 配额本就是配置驱动 ⇒ auto 接手的落点就是这些键，
      不改任何判据语义（判据一行未动）。
    """
    notes: List[str] = []
    items = (plan or {}).get("_items") or {}

    def _is_mine(name):
        return (items.get(name) or {}).get("source") in ("auto", "explicit")

    if _is_mine("web"):
        # ★ 写**运行期总控**而不是 `web_search.enabled` 本身 —— 后者的写入者
        #   是 `_apply_runtime`（唯一写入者）。两处都写等于同一条逻辑两条
        #   实现（本项目头号复发问题）。
        _set_cfg_path(cfg, ("runtime", "web"),
                      "on" if plan["web"] else "off")
        notes.append("联网 %s（%s）" % ("开" if plan["web"] else "关",
                                       items["web"]["reason"]))
    for _n in ("thinking", "effort"):
        if _is_mine(_n) and plan[_n] is not None:
            _v = plan[_n]
            _s = "on" if _v is True else ("off" if _v is False else str(_v))
            _set_cfg_path(cfg, ("runtime", _n), _s)
            notes.append("%s %s（%s）" % (_AUTO_ITEM_LABEL[_n], _s,
                                          items[_n]["reason"]))
    if _is_mine("web_downgrade") and isinstance(plan["web_downgrade"], dict):
        _wd = plan["web_downgrade"]
        _set_cfg_path(cfg, ("web_search", "auto_disable_after_failures"),
                      int(_wd.get("auto_disable_after_failures", 3)))
        for _k, _v in (_wd.get("quota") or {}).items():
            _set_cfg_path(cfg, ("web_search", "quota", _k), int(_v))
        notes.append("联网降级（%s）" % items["web_downgrade"]["reason"])
    if _is_mine("stop") and isinstance(plan["stop"], dict) and plan["stop"]:
        for _k, _v in plan["stop"].items():
            _set_cfg_path(cfg, ("spiral", _k), int(_v))
        notes.append("停止阈值（%s）" % items["stop"]["reason"])
    return notes


def _auto_dispatch_lines(res: dict) -> List[str]:
    """产物头部的「自动调度 · 逐项来源」表（无 plan 时返回空）。"""
    plan = res.get("_auto_dispatch")
    if not isinstance(plan, dict) or not (plan.get("_items") or {}):
        return []
    items = plan["_items"]
    _on = plan.get("_auto_on", True)
    _feat = plan.get("_features") or {}
    _hist = plan.get("_history") or {}
    _hl = _hist.get("_half_life_days")
    _plt = _hist.get("_limit_per_type")
    _n_auto = sum(1 for v in items.values()
                  if (v or {}).get("source") == "auto")
    out = ["**自动调度**（%d 项逐项来源；%s，auto 接管 %d 项）\n\n"
           % (len(_AUTO_ITEM_ORDER),
              "总开关开" if _on else "总开关**关**", _n_auto)]
    out.append("| 项 | 取值 | 来源 | 理由 |\n|---|---|---|---|\n")
    for _k in _AUTO_ITEM_ORDER:
        _it = items.get(_k) or {}
        _v = _it.get("value")
        if isinstance(_v, dict):
            _v = "／".join("%s=%s" % (a, b) for a, b in _v.items()) or "（无）"
        elif isinstance(_v, list):
            _v = "、".join(str(x) for x in _v)
        elif isinstance(_v, bool):
            _v = "开" if _v else "关"
        elif _v is None:
            _v = "（不覆盖）"
        out.append("| %s | %s | %s | %s |\n"
                   % (_AUTO_ITEM_LABEL.get(_k, _k), _v,
                      _AUTO_SRC_LABEL.get(_it.get("source"),
                                          _it.get("source")),
                      str(_it.get("reason") or "")[:120]))
    if _hl is not None:
        out.append("- 取样口径：每题型上限 %s 条 · 时间半衰期 %s 天"
                   "（0=不衰减）\n" % (_plt or "—", _hl))
    out.append("- 题型特征：%s\n"
               % "、".join("%s=%s" % (k, v) for k, v in _feat.items()))
    _srcs = _hist.get("sources") or {}
    _bt = _hist.get("by_type") or {}
    out.append("- 历史读数：**%d 份**（%s）· token 中位 %s / p75 %s · "
               "calls 中位 %s / p75 %s · 三态一致率 %s（n=%s）· "
               "被截断率 %s（n=%s 层）· 联网 收%s/失败%s（%s 跑有入池）· "
               "取向错配 %s\n"
               % (int(_hist.get("n") or 0),
                  "、".join("%s %s" % (a, b) for a, b in sorted(_srcs.items()))
                  or "无",
                  _hist.get("tokens_med") or "—", _hist.get("tokens_p75") or "—",
                  _hist.get("calls_med") or "—", _hist.get("calls_p75") or "—",
                  ("%.2f" % _hist["tri_rate"]) if _hist.get("tri_rate")
                  is not None else "—", _hist.get("tri_n") or 0,
                  ("%.2f" % _hist["cut_rate"]) if _hist.get("cut_rate")
                  is not None else "—", _hist.get("stop_n") or 0,
                  _hist.get("web_hit", 0), _hist.get("web_fail", 0),
                  _hist.get("web_runs", 0),
                  _hist.get("mismatch", 0)))
    if _bt:
        out.append("- 分题型：事实型 %s 份（token 中位 %s）/ 决策型 %s 份"
                   "（token 中位 %s）\n"
                   % ((_bt.get("fact") or {}).get("n", 0),
                      (_bt.get("fact") or {}).get("tokens_med") or "—",
                      (_bt.get("nonfact") or {}).get("n", 0),
                      (_bt.get("nonfact") or {}).get("tokens_med") or "—"))
    out.append("- 各项可取 `显式 ＞ 配置 ＞ auto ＞ 默认`；"
               "想固定某项：命令行显式传（来源显示「显式」）。\n\n")
    return out

def plan_orientation(question: str,
                     config: Optional[dict] = None) -> dict:
    """ 第一段：判「用户想要什么形态的产出」。

    返回 {"orientation": "boundary|decision", "reason": ...,
          "confidence": 0.0-1.0}
    失败降级为 decision（保守省钱），但不静默——reason 里写清降级原因。
    """
    cfg = config if config is not None else load_config("")
    system = (
        "你是【取向判读者】。\n"
        "给定一个问题，判断问的人想要的是哪种产出：\n"
        "\n"
        "  · boundary（要边界清单）：\n"
        "      问的是「哪些不确定」「边界在哪」「该不该碰」「有哪些坑」\n"
        "      例如：一个新领域该怎么看 / 这件事的风险在哪 / 有哪些说不清的\n"
        "  · decision（要可落地方案）：\n"
        "      问的是「怎么做」「选哪个」「给个数」「给我一个方案」\n"
        "      例如：选 A 还是 B / 这个指标怎么设计 / 明天该做哪一步\n"
        "\n"
        "★ 拿不准时选 decision（省钱，且不满意的方案可以再追问）。\n"
        "严格 JSON：\n"
        '{"orientation":"boundary|decision",'
        '"reason":"≤60字","confidence":0.0-1.0}'
    )
    user = f"【问题】\n{question}\n"
    try:
        llm = LLM(cfg)
        raw = llm.call(system, user, 0.2, 300, json_mode=True,
                       stage="plan_orientation")
        data = llm.parse_json(raw) or {}
    except Exception as e:
        logger.warning("取向判定失败，降级 decision: %s", e)
        return {"orientation": "decision",
                "reason": f"取向判定失败，降级 decision：{type(e).__name__}",
                "confidence": 0.0}
    _o = _normalize_orientation(data.get("orientation"), "decision")
    try:
        _c = float(data.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        _c = 0.0
    return {"orientation": _o,
            "reason": str(data.get("reason", ""))[:200],
            "confidence": _c}


#: [B1 规则优先] 模块级唯一实现（自类方法下沉）。★ 规则只判到
#:   serial/B/C（与 `MetaDGTF._AUTO_REACHABLE_MODES` 对应）——
#:   6 个 stage 模式不参与自动分派，显式传参才可达。
_MODE_RULE_OR = ("或", "还是", "或者", "抑或")
_MODE_RULE_AND = ("和", "与", "以及", "同时", "并")
_MODE_RULE_PIPE = ("流水", "接力", "时序", "尽快", "尽量快")


def mode_rule(question: str):
    """规则优先的模式判断。返回 (mode, reason) 或 (None, why_not)。

    ★ 为什么要有规则层：出厂把模式**全权**交给一次 LLM 调用，而
      实测该调用几乎总返回 `serial`（含 `_PARALLEL_CONF_MIN` 门槛
      的兜底）——花一次调用换一句『退回保守』。
      规则层能覆盖的情形就地定案，**不再花调用**；拿不准才回落 LLM。
    ★ 三处接线：`_decide_parallel_mode` / `plan_resources` /
      `auto_plan(llm=...)` —— 同一问题必须同案（冒烟 v1235 [1d]）。
    """
    q = question or ""
    _n = len(q)
    _or = any(t in q for t in _MODE_RULE_OR)
    _and = any(t in q for t in _MODE_RULE_AND)
    _pipe = any(t in q for t in _MODE_RULE_PIPE)
    _how = ("如何" in q) or ("怎样" in q) or ("怎么" in q)
    _clauses = (q.count("，") + q.count(",")) >= 2
    # 1) 含「或/还是」⇒ 开放震荡 ⇒ B（与 `_auto_pick_mode` 的
    #    `choice` 判据同源）。
    if _or and _n >= 8:
        return "B", "规则：含选择/开放词（或/还是），走轮次并行"
    # 2) 讲过程 + 显式要压缩时长 ⇒ C（层界可接力）。
    if _pipe and (_clauses or _how):
        return "C", "规则：显式要求压缩时长且讲过程，走流水线并行"
    # 3) 单一短问句 ⇒ serial（与 `_auto_pick_mode` 的
    #    `fact and short` 一致：层间依赖强，无并行收益）。
    if _n <= 16 and not _or and not _and and not _clauses:
        return "serial", "规则：单一短问句，无并列无选择，走严格串行"
    # 4) 多分句且含并列 ⇒ B（层次不分明、需震荡）。
    if _clauses and _and:
        return "B", "规则：多分句且含并列，层次不分明，走轮次并行"
    return None, "规则拿不准"


def plan_resources(question: str, orientation: str,
                   config: Optional[dict] = None) -> dict:
    """ 第二段：根据取向 + 问题规模定资源。

    返回 {"route", "mode", "rounds", "max_calls"}。
    cost_profile 不进这里（由 config 定，见 v1.21.61 定论）。
    """
    cfg = config if config is not None else load_config("")
    spiral = cfg.get("spiral", {}) or {}
    hard = int(spiral.get("hard_max", 12) or 12)
    soft = int(spiral.get("soft_max", 2) or 2)
    q = question or ""
    _o = _normalize_orientation(orientation, "decision")

    if _o == "boundary":
        _route_rule = (
            "取向=boundary → route **必须**是 full（0,1,both,all），"
            "因为边界清单只有对撞/元层会认真做。"
        )
        _route_default = "full"
    else:
        _route_rule = (
            "取向=decision → route 可以是 full/no_meta/light，"
            "按问题自足程度选。"
        )
        _route_default = "full"

    # ★ [B1 规则优先] 命中即定案，**不花这次 LLM 调用**；拿不准才
    #   走下面的真调用。rounds 走 {}（各层由停止判据自定，不猜）。
    #   ★ 位置有讲究：必须在 `_route_default` 赋值**之后**（否则
    #     UnboundLocalError —— 本版冒烟 [P2-8] 抓出的真 bug）。
    _rm, _rr = mode_rule(q)
    if _rm:
        return {"route": list(_ROUTE_PRESETS[_route_default]),
                "mode": _rm, "rounds": {},
                "max_calls": 0,
                "reason": _rr, "confidence": 0.9}

    system = (
        "你是【资源配置者】。给定问题和取向，给出执行资源。\n"
        f"【取向】{_o}\n"
        f"【★ route 规则】{_route_rule}\n"
        "\n"
        "【route 档位】\n"
        "  full    = 0,1,both,all\n"
        "  no_meta = 0,1,both\n"
        "  light   = 0,1\n"
        "\n"
        "【mode】serial / A / B / C / D / E / F / G / H\n"
        "\n"
        f"【rounds】每层 {_MIN_LAYER_ROUNDS}-{_MAX_LAYER_ROUNDS} 圈，"
        "四层都要给；给多不等于跑多。\n"
        "\n"
        "【max_calls】总调用预算，0 = 不设限。\n"
        "\n"
        "严格 JSON：\n"
        '{"route":"full|no_meta|light",'
        '"mode":"serial|A|B|C|D|E|F|G|H",'
        '"rounds":{"0":n,"1":n,"both":n,"all":n},'
        '"max_calls":n,'
        '"reason":"≤80字","confidence":0.0-1.0}'
    )
    user = (f"【问题】\n{q}\n\n"
            f"【参考】长度：{len(q)} 字｜圈数区间：{soft}～{hard}")
    try:
        llm = LLM(cfg)
        raw = llm.call(system, user, 0.2, 600, json_mode=True,
                       stage="plan_resources")
        data = llm.parse_json(raw) or {}
    except Exception as e:
        logger.warning("资源配置失败: %s", e)
        return {"route": list(_ROUTE_PRESETS[_route_default]),
                "mode": "serial", "rounds": {},
                "max_calls": 0,
                "reason": f"资源配置失败：{type(e).__name__}"}

    route_key = str(data.get("route", _route_default)).strip().lower()
    # boundary 强制 full
    if _o == "boundary":
        route_key = "full"
    route = list(_ROUTE_PRESETS.get(route_key,
                                     _ROUTE_PRESETS[_route_default]))
    if isinstance(data.get("route"), list) and _o != "boundary":
        _r = [str(x).strip() for x in data["route"]
              if str(x).strip() in ("0", "1", "both", "all")]
        if _r and "0" in _r:
            route = _r
    if "0" not in route:
        route = ["0"] + route

    mode = _normalize_plan_mode(data)
    rnd = _normalize_plan_rounds(data, hard, route=route)


    try:
        max_calls = int(data.get("max_calls", 0) or 0)
    except (TypeError, ValueError):
        max_calls = 0
    if max_calls < 0:
        max_calls = 0
    if 0 < max_calls < 20:
        max_calls = 0

    conf = _plan_conf(data)
    if mode != "serial" and conf < _PARALLEL_CONF_MIN:
        mode = "serial"

    return {"route": route, "mode": mode, "rounds": rnd,
            "max_calls": max_calls,
            "reason": str(data.get("reason", ""))[:200],
            "confidence": conf}


def auto_plan(question: str, config: Optional[dict] = None,
              config_path: Optional[str] = None,
              llm=None) -> dict:
    """ 拆成两段：先定取向，再定资源。

    返回结构与 v1.21.61 兼容，但增加 `orientation` 字段。
    cost_profile 仍由 config 定（v1.21.61 已定论）。
    """
    cfg = config if config is not None else load_config(
        str(config_path or ""))
    if llm is not None:
        """一次调用定下**模式 + 每层圈数**两件事。

        原来 `_decide_parallel_mode` 只管模式，圈数还得人自己填
        （命令行 `--rounds` 默认 0 → 全层 hard_max，靠 stop 判据兜着）。
        诉求是"把问题丢进来就行"，所以合成一次决策。

        ★ 成本档（quality/balanced/economy）**不在这里定**：它在
        `__init__` 里就已经按 profile 裁剪完 shape_chars 等参数了，
        run 阶段改不动。塞进返回值只会给人"我调了"的错觉。

        ★ 边界：只在**用户什么都没指定**时才接管。指定了模式或圈数
        任一，就尊重用户，退回单目标决策 —— 自作主张覆盖显式参数
        是另一类 bug。

        ★★ [v1.21.71 F8] 与**模块级 `auto_plan()`** 的关系（两份实现，已
          知的双实现，本版**只加检测器、不合并**）：
            · 模块级 `auto_plan` = `plan_orientation` + `plan_resources`，
              **两次**调用、带 orientation 段、没有任何内部调用点，
              是给外部使用的 API；
            · 本方法 = **一次**调用同时定 mode + rounds，`run()` 的自动
              调度走的是它（`parallel_mode == "auto" and not rounds`）。
            · 两者**没有任何互相调用**，但各自都写了一份**同规则**的
              归一化：模式白名单（A~H 之外 → serial）+ 逐层圈数钳到
              `[_layer_floor, _layer_ceil]` + 漏层按已给合法值的**中位数**
              补 + 低置信（< `_PARALLEL_CONF_MIN`）退 serial。
              规则虽同、代码是两份 —— 长期并行必然漂移（本项目
              「同一条逻辑两条通道各写一份」的第 N 次）。
            · 本版的对策是**漂移检测器**：冒烟
              `check_v71_auto_plan_agreement` 用同一份 mock 输入分别喂两个
              实现，断言 mode 与（按 route 裁剪后的）rounds 逐字相同；
              负对照用子类把方法级那份的圈数改坏，断言**必须**判不一致。
            · 真正合并成唯一实现（模块级那份加 `llm` 参数、本方法退成
              薄壳）要贯通 `plan_orientation` / `plan_resources` 的
              签名，属架构批，本轮不做。
        """
        q = question or ""
        spiral = config.get("spiral", {}) or {}
        hard = int(spiral.get("hard_max", 12) or 12)
        soft = int(spiral.get("soft_max", 2) or 2)
        # ★ [B1 规则优先] 与 `_decide_parallel_mode` / `plan_resources`
        #   同一规则、同一接线 —— 命中即定案，**不花这次模式调用**。
        #   ★ 但取向仍要带出（P5 判据钉住的行为）：规则不判
        #     取向，取向本来就不属于这次调用（原 prompt 只问 mode/rounds/
        #     orientation 是否该由本调用定？）—— 这里调 `plan_orientation`
        #     补一次，保证 `_assemble_plan(orientation=...)` 有值。
        _rm, _rr = mode_rule(q)
        if _rm:
            _ori = ""
            try:
                _ori = str((plan_orientation(q, cfg) or {})
                           .get("orientation", "") or "")
            except Exception:
                _ori = ""
            return _assemble_plan(
                _rm, {}, cfg, orientation=_ori, confidence=0.9,
                reason=_rr + "（规则命中，未花调度调用）")
        feats = {
            "len": len(q),
            "multi_clause": (q.count("，") + q.count(",")) >= 3,
            "has_or": ("或" in q) or ("还是" in q),
            "has_how": ("如何" in q) or ("怎样" in q) or ("怎么" in q),
            "is_meta": any(k in q for k in ("本身", "自身", "递归", "元",
                                            "整体", "到底")),
        }
        system = (
            "你是【DGTF 调度者】。给定一个问题，一次给出执行方案：\n"
            "走哪种并行模式、每层跑几圈。\n\n"
            "【模式】\n"
            "  serial：结构清晰、层间依赖强\n"
            "  A：多义多维、每层能独立产出（四层并行后汇流）\n"
            "  B：开放、层次不分明、需要震荡收敛\n"
            "  C：层间接力但不必等上游跑完，想压时长\n"
            "  D/E：修行与研究互不依赖，交汇点在对撞\n"
            "  F：修行是地基，后三层能边跑边接力\n"
            "  G：要元层清算**完整**对撞结果\n"
            "  H：研究要吃完整修行、对撞要吃完整研究\n\n"
            "【每层圈数】"
            f"{_MIN_LAYER_ROUNDS}-{_MAX_LAYER_ROUNDS}。给多不等于跑多 —— "
            "层内到点会自然停\n"
            "（无新增 & / 无新线头 / 停滞）。所以：\n"
            f"  ★ 不要少于 {_MIN_LAYER_ROUNDS} 圈：停止判据要累计 2 圈才成立，\n"
            "    给 2-3 圈等于判据永远够不到，层只能被截断收场\n"
            f"  ★ 也不要多于 {_MAX_LAYER_ROUNDS} 圈：多出的圈停在空转上，\n"
            "    买不到新东西（但给少了更糟 —— 层只能被截断收场）\n"
            f"  · 一般题 → 5\n"
            f"  · 开放、需要摊开 → {_MAX_LAYER_ROUNDS}\n"
            "  · 别一律给满 —— 那是把停止判据当摆设\n"
            "  · 四层都要给；漏给的会按你已给的中间值补，别指望它\n"
            "    落到别处去（那条路是最贵的）\n\n"
            "【取向】\n"
            "  decision：要可落地的方案 / 取舍 / 怎么办\n"
            "  boundary：要边界清单 / 判别标准 / 什么算数什么不算数\n\n"
            "严格 JSON：\n"
            '{"mode":"serial|A|B|C|D|E|F|G|H",'
            '"orientation":"decision|boundary",'
            '"rounds":{"0":n,"1":n,"both":n,"all":n},'
            '"reason":"≤80字","confidence":0.0-1.0}'
        )
        user = (
            f"【问题】\n{q}\n\n"
            f"【轻量特征】\n"
            f"  长度：{feats['len']} 字｜多分句：{feats['multi_clause']}\n"
            f"  含选择：{feats['has_or']}｜含过程：{feats['has_how']}\n"
            f"  自指/元层味：{feats['is_meta']}\n"
            f"  建议区间：{soft}（省）～ {hard}（上限）\n"
        )
        try:
            raw = llm.call(system, user, 0.2, 500, json_mode=True,
                                stage="auto_plan")
            data = llm.parse_json(raw) or {}
        except Exception as e:
            logger.warning("自动调度失败: %s", e)
            return _assemble_plan(
                "serial", {}, cfg, confidence=0.0,
                reason="调度失败，退回保守（圈数走配置）")

        mode = _normalize_plan_mode(data)
        conf = _plan_conf(data)
        reason = str(data.get("reason", ""))[:200]
        _ori = _normalize_orientation(data.get("orientation"), "")

        rnd = _normalize_plan_rounds(data, hard)
        # 低置信不硬上并行模式（与单目标决策同口径）
        if mode != "serial" and conf < _PARALLEL_CONF_MIN:
            return _assemble_plan(
                "serial", rnd, cfg, orientation=_ori, confidence=conf,
                reason=f"低置信({conf:.2f})，退回 serial：{reason}")
        return _assemble_plan(mode, rnd, cfg, orientation=_ori,
                              reason=reason, confidence=conf)
    o = plan_orientation(question, cfg)
    r = plan_resources(question, o["orientation"], cfg)
    _per = float((cfg or {}).get("spiral", {}).get(
        "budget_per_round_floor", 10) or 0)
    _cap_per = float((cfg or {}).get("spiral", {}).get(
        "budget_per_round_cap", 12) or 0)
    _rnd = r.get("rounds") or {}
    _budget_note = ""
    if r.get("max_calls", 0) == 0 and _cap_per > 0 and _rnd:
        _mc = int(sum(_rnd.values()) * _cap_per)
        r["max_calls"] = _mc
        _budget_note = (f"规划给「不限」，按 {_cap_per:.0f}/圈兜到 "
                        f"{_mc}")
    if r.get("max_calls", 0) > 0 and _per > 0 and _rnd:
        _need = int(sum(_rnd.values()) * _per)
        if r["max_calls"] < _need:
            _budget_note = (f"预算 {r['max_calls']} 不够跑完 "
                            f"{sum(_rnd.values())} 圈（按 {_per:.0f}/圈"
                            f"抬到 {_need}）")
            r["max_calls"] = _need
    _reason = r.get("reason", "")
    if _budget_note:
        _reason = f"{_budget_note}；{_reason}"[:200]


    return _assemble_plan(
        r.get("mode", "serial"), r.get("rounds", {}), cfg,
        route=r.get("route", list(_ROUTE_PRESETS["full"])),
        orientation=o["orientation"], max_calls=r.get("max_calls", 0),
        reason=_reason, confidence=r.get("confidence", 0.0),
        extra={"_orientation_reason": o.get("reason", "")})


def _render_full_appendix(result: dict, md_text: str) -> str:
    """ 产物 md 的「全量字段」附录（packed 原文）。

    ★ 为什么必须有它：正文各节都是 packed 的**可读视图**，天然带省略 ——
      实测小跑一次（route 0,1 各 1 圈）packed 有 429 条叶子路径，其中
      405 条的**字段名在正文里根本不出现**。红线「失败必须留痕」的同源
      要求是「**不得因为没写渲染点就丢信息**」，所以这里做**机械全量**
      输出：正文省略的、以及以 `_` 开头的内部量，都以本段为准。

    ★ 为什么用 JSON 原文而不是"再挑几个字段渲染"：挑字段就等于又维护
      一张"该渲染什么"的清单，新增字段会再次静默漏掉 —— 本项目的
      「无渲染点」事故就是这么来的。机械全量没有这个失效模式。
    """
    leaves = []

    def _walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                _walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                _walk(v, f"{path}[{i}]")
        else:
            leaves.append(path)

    try:
        _walk(result, "")
    except Exception:
        leaves = []
    try:
        dump = json.dumps(result, ensure_ascii=False, indent=1, default=str)
    except Exception as e:                      # 序列化失败也要留痕
        return ("\n## 附录 · 全量字段（packed 原文）\n\n"
                f"❌ 序列化失败，**本段缺失**："
                f"{type(e).__name__}: {e}\n\n"
                "⇒ 这一份产物**不完整**，不要据此下结论。\n")
    _miss = 0
    for _p in leaves:
        _k = _p.rsplit(".", 1)[-1].split("[")[0]
        if _k and _k not in md_text:
            _miss += 1
    return (
        "\n## 附录 · 全量字段（packed 原文）\n\n"
        "<sub>本段是**机械全量**输出：正文各节是 packed 的可读视图，凡正文"
        "省略的、或压根没有渲染点的字段（含以 `_` 开头的内部量），"
        "**以本段为准**。</sub>\n\n"
        f"- 叶子路径 {len(leaves)} 条；正文里**找不到字段名**的 {_miss} 条"
        "（按「字段名是否在正文出现」粗算，不是精确覆盖判定）\n"
        f"- JSON {len(dump)} 字符 / {dump.count(chr(10)) + 1} 行\n\n"
        "```json\n" + dump + "\n```\n"
    )


def save_result(result: dict, save_dir: str = "outputs") -> Path:
    _ap_mode = str(((result.get("_config") or {}).get("actions") or {})
                   .get("appendix_mode") or "file").strip().lower()
    if _ap_mode not in ("inline", "file"):
        _ap_mode = "file"
    d = Path(save_dir)
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # [B4] 原来允许「，。？」和空格进文件名 —— 中文标点在部分文件系统
    # /工具链下会出问题，尾部的空格和点在 Windows 上会被静默吃掉。
    # 只留字母数字、中日韩文字、连字符和下划线，空格转下划线。
    safe_q = "".join(
        ("_" if c.isspace() else c)
        for c in result["question"][:20]
        if c.isalnum() or c in "-_" or "一" <= c <= "鿿"
    ).strip("._") or "question"
    md = d / f"{ts}_{safe_q}.md"

    with open(md, "w", encoding="utf-8") as f:
        f.write(f"# 元 DGTF · {result['question']}\n\n")
        f.write(f"**时间**: {datetime.now().isoformat()}\n\n")
        f.write("**分层目标**：\n")
        for _ol in _layer_objective_lines(result):
            f.write(f"{_ol}\n")
        f.write("\n")
        # ★ [LDG] 每层「到底替原始问题干了什么」—— 在**停止/收敛处**算的
        #   读数（C 覆盖 / R 相关 / S 调和平均）。★ 它是读数不是分数：
        #   低于门槛只做两件事 —— 改署名（不许说自然安住）+ 点名缺的 core。
        _duty_lines = []
        for _e in ("0", "1", "both", "all"):
            _vv = (result.get("views") or {}).get(_e) or {}
            _dd = _vv.get("duty") or {}
            if not _dd:
                continue
            _mark = "⚠ " if _dd.get("short") else ""
            _duty_lines.append(
                f"  - {_LAYER_LABEL.get(_e, _e)}层：{_mark}{duty_short_line(_dd)}")
            _tr = _vv.get("duty_trace") or []
            if len(_tr) >= 2:
                _duty_lines.append(
                    "      ↳ 逐圈 S：" + " → ".join(
                        f"{float(t.get('S', 0)):.2f}" for t in _tr))
        if _duty_lines:
            f.write("**层职责（LDG · 停止处实算）**：\n")
            for _dl in _duty_lines:
                f.write(f"{_dl}\n")
            f.write("\n")
        # ★ [EML] 本次记忆：用了哪几条经验、哪几条真生效、跑后写进去什么。
        #   ★ 它是**留痕**（读数），不是打分：不排序、不给「学习效果」分数。
        _pbk = result.get("playbook") or {}
        if _pbk and not _pbk.get("error"):
            f.write("**本次记忆（EML 经验回路）**：\n")
            f.write(f"  - 模式：`{_pbk.get('mode')}`（off 不读不写 / "
                    f"shadow 只记不生效 / on 生效）\n")
            _u = _pbk.get("used") or []
            _uids = "、".join(str(x.get("id")) for x in _u[:6])
            f.write(f"  - 读到（active）{len(_u)} 条"
                    f"{'：' + _uids if _uids else ''}\n")
            _ap = _pbk.get("applied") or []
            f.write(f"  - **真生效 {len(_ap)} 条**"
                    f"{'：' + str(_ap[:4]) if _ap else '（shadow 模式下恒为 0 —— 这是设计，不是失效）'}"
                    f"\n")
            f.write(f"  - 跑后过闸新增 {len(_pbk.get('merged') or [])} 条 / "
                    f"被闸拒 {len(_pbk.get('gated_out') or [])} 条 / "
                    f"升级 {len(_pbk.get('promoted') or [])} / "
                    f"遗忘 {len(_pbk.get('retired') or [])} / "
                    f"库内 {_pbk.get('n_playbook', 0)} 条\n")
            _go = _pbk.get("gated_out") or []
            if _go:
                _cnt = {}
                for _g in _go:
                    _k = _g.get("why", "?")
                    _cnt[_k] = _cnt.get(_k, 0) + 1
                f.write("      ↳ 被闸拒的原因分类："
                        + "、".join("%s×%d" % (k, v)
                                    for k, v in sorted(_cnt.items()))
                        + "\n")
            f.write("\n")
        disp = result.get("dispatch") or {}
        rounds = result.get("rounds") or {}
        if disp:
            _views0 = result.get("views") or {}
            seq = " → ".join(
                f"{_LAYER_LABEL.get(e, e)}"
                f"({(_views0.get(e) or {}).get('rounds_cap')
                    or rounds.get(e, '?')}圈)"
                for e in disp.get("order", []))
            f.write(f"**调度**：{seq or '（空）'}\n\n")
            _stop_line = _stop_kind_summary(_views0)
            if _stop_line:
                f.write(_stop_line)
            _rr_line = _rounds_run_line(_views0)
            if _rr_line:
                f.write(_rr_line)
            _pm = disp.get("_parallel_mode", "serial")
            _pm_disp = {
                "serial": "严格串行",
                "A": "A · 四层独立并行 + 汇流",
                "B": "B · 轮次并行",
                "C": "C · 流水线并行",
                "D": "D · 双起并行 + 撞元并行",
                "E": "E · 双起并行 + 撞元串行",
                "F": "F · 修行先行 + 全流水",
                "G": "G · 修行先行 + 撞毕收元",
                "H": "H · 逐层接力 + 撞元并行",
            }.get(_pm, _pm)
            f.write(f"**并行模式**：{_pm_disp}\n\n")
            for _al in _auto_dispatch_lines(result):
                f.write(_al)
            _or = result.get("orientation")
            if _or:
                _or_disp = {
                    "auto": "auto（未指定：按题面有无决策语境分流）",
                    "boundary": "boundary（要边界清单 → 保留全四层）",
                    "decision": "decision（要可落地方案 → 允许砍层）",
                }.get(_or, _or)
                f.write(f"**取向**：{_or_disp}\n\n")
            _ap = result.get("_auto_plan_used") or {}
            if _ap.get("orientation"):
                f.write(f"**取向判定（plan_orientation）**："
                        f"{_ap['orientation']}"
                        f"（{str(_ap.get('_orientation_reason') or '')[:60]}）"
                        f"\n\n")
                _actual = str(_ap.get("orientation") or "").strip()
                _declared = str(result.get("orientation") or "auto").strip()
                if _declared == "auto" and _actual != "decision":
                    f.write(f"⚠️ **取向错配**：plan_orientation 判为 "
                            f"`{_actual}`，但 orientation 未指定（按 decision "
                            f"渲染）。如想用 boundary 模板，请显式传 "
                            f"`--orientation boundary`。\n\n")
            if result.get("_anchor_tier_warning"):
                f.write(f"⚠️ **锚点 tier 警告**："
                        f"{result['_anchor_tier_warning']}\n\n")
            if result.get("_anchor_answers_filtered"):
                f.write(f"⚠️ **锚点 answers 警告**："
                        f"{result['_anchor_answers_filtered']}\n\n")

            # ★ 外部锚点两条通道（文本 / 联网）分别写明 —— 单一实现。
            for _al in _anchor_lane_lines(result):
                f.write(_al + "\n\n")
            _tri = result.get("tri_state") or [0, 0]
            try:
                _ag, _tt = int(_tri[0]), int(_tri[1])
            except (TypeError, ValueError, IndexError):
                _ag, _tt = 0, 0
            if _tt > 0:
                _pct = _ag / _tt
                f.write(
                    f"**三态判决一致率**：{_ag}/{_tt}（{_pct:.0%}）"
                    f"　其中 {_tt - _ag} 条分歧已按 partial 计入\n\n")
                f.write(
                    "  - 全项目实测落在 17~67%，均未达到当初预设的 80% 线；\n"
                    "    §7.13 已定性：这不是工程质量问题，是这个标签本身的\n"
                    "    可定义性边界。读数时把它当成「这一份的分母有多稳」的\n"
                    "    参考，不要当成不合格的判词。\n")
                if _pct >= 0.8:
                    _level = "✅ 高（标签在此次运行里稳定）"
                elif _pct >= 0.5:
                    _level = "⚠️ 中（标签有噪声，读数时留意分母）"
                elif _pct > 0.0:
                    _level = ("❌ 低（与三分类随机基线 33% 同量级，"
                              "分母不可作为判据）")
                else:
                    _level = "（无有效判决记录）"
                f.write(f"  - 可信度分级：{_level}\n\n")
            f.write(f"**机制审计**：pending_fix {_AUDIT122_PENDING_FIX} 项，"
                    f"双实现 {_AUDIT122_DUAL_IMPL} 项"
                    f"（详见 docs/机制审计-v122.md）\n\n")
            _fz = result.get("freeze") or {}
            _cons = result.get("tri_consensus") or []
            _sig = str(_fz.get("signature") or "")
            _cqn = len(result.get("calibration_queue") or [])
            _sq1 = ((result.get("pools") or {}).get("1") or {}).get(
                "sub_questions") or []
            _hi = sum(1 for s in _sq1 if s.get("stability") == "high")
            _me = sum(1 for s in _sq1 if s.get("stability") == "medium")
            _lo = sum(1 for s in _sq1 if s.get("stability") == "low")
            _ab = sum(1 for s in _sq1
                      if s.get("stability") == "abstained")
            _voted = _hi + _me + _lo
            if _sq1:
                _cm: Dict[str, int] = {}
                for s in _sq1:
                    _m = str(s.get("_vote_mode") or "?")
                    _cm[_m] = _cm.get(_m, 0) + 1
                _mode = max(_cm, key=lambda k: _cm[k])
                _label = {"single": "单票", "multi": "多票"}.get(
                    _mode, "口径未知")
                _cal = {"single": "单票 vs 拆解原标签",
                        "multi": "三票之间"}.get(_mode, "未知")
                if _voted:
                    _rate = (_hi + _me) / _voted
                    _flag = ("" if _rate >= 0.5
                             else "　⚠️ unstable（＜50%）")
                    _line = (f"**三态判决（{_label}）**：high {_hi} / "
                             f"medium {_me} / low {_lo}"
                             f"（已判 {_voted} 条）　"
                             f"一致率 {_rate:.0%}{_flag}")
                else:
                    _line = (f"**三态判决（{_label}）**：无可判读数"
                             f"（判决官未返回任何一条）")
                if _ab:
                    _line += f"　弃权 {_ab} 条"
                f.write(_line + f"　口径={_cal}"
                        f"（共 {len(_sq1)} 条）\n")
            if _cons or _sig:
                if len(_cons) == 3:
                    _cs = (f"一致 {_cons[0]} / 多数 {_cons[1]} / "
                           f"分裂 {_cons[2]}")
                else:
                    _cs = "（无多票记录）"
                f.write(f"**三态多票**（3 票）：{_cs}　"
                        f"**冻结**：sha256={_sig[:16]}…"
                        f"（{len(_sig)} 位）　校准队列 {_cqn} 条\n\n")

            if disp.get("requested") != disp.get("order"):
                f.write(f"**请求顺序**：{' → '.join(disp['requested'])}\n\n")
            for sk in (disp.get("skipped") or []):
                f.write(f"- ⚠️ 跳过 `{sk['entry']}`：{sk['reason']}\n")
            if disp.get("skipped"):
                f.write("\n")
            _miss = list(disp.get("missing") or [])
            _gf = result.get("layer_gap") or {}
            if _miss or _gf.get("missing"):
                _miss = _miss or list(_gf.get("missing") or [])
                f.write(f"**❌ 缺层**：请求了 `{'、'.join(disp.get('requested') or [])}`，"
                        f"但这几层没有产出 —— **这份产物不完整**\n\n")
                _fail = dict(disp.get("failed") or _gf.get("failed") or {})
                for _e in _miss:
                    f.write(f"- ❌ `{_e}`：{_fail.get(_e, '未记录原因（这是缺陷）')}\n")
                f.write("\n")
        else:
            f.write(f"**路由**: {' → '.join(result['route'])}\n\n")
        dec = result.get("decidability") or {}
        if dec:
            # ★ 锚点文件的**明细**（对照 / 分级 / triage 降级 / 冲突 / 入池）
            #   原样保留：两条通道是**多一条出口**，不是换掉这些读数。
            #   `[4.7]` 判据读「锚点分级 / triage 降级」两个字面串，
            #   `_p2_triage_from_md` 读 `**triage 降级**：N 条` 这个格式。
            _ea = result.get("external_anchor")
            if isinstance(_ea, dict) and _ea.get("error"):
                f.write(f"**锚点异常**：{_ea['error']}\n\n")
            elif isinstance(_ea, dict) and _ea.get("unconfigured"):
                # ★ 原先这里会写「结论 0 条 / 印证 0 …」**五行零** —— 读者会
                #   以为「对照做过、结果全是 0」。改成一行说明「未做对照」。
                f.write("**锚点对照**：未做 —— 通道开着但**没有挂锚点文件**"
                        "（两条接入路二选一：`external_anchor.path` 指快照 JSON；"
                        "或 `external_anchor.retriever: tavily` 按圈真检索）\n\n")
            elif isinstance(_ea, dict):
                _sm = _ea.get("summary") or {}
                f.write(f"**锚点对照**：结论 {_sm.get('claims', 0)} 条 —— "
                        f"印证 {_sm.get('supported', 0)} / "
                        f"冲突 {_sm.get('conflicted', 0)} / "
                        f"无对应 {_sm.get('unmatched', 0)}"
                        f"（用到锚点 {_sm.get('anchor_used', 0)}/"
                        f"{_ea.get('anchors', 0)}）\n\n")
                f.write(f"**锚点分级**：{_ea.get('as_evidence', 'off')}"
                        f"（tier_floor {_ea.get('tier_floor', '?')}）\n\n")
                f.write(f"**triage 降级**："
                        f"{_ea.get('triage_downgrades', 0)} 条\n\n")
                f.write(f"**冲突**：{_sm.get('conflicted', 0)} 条"
                        f"（gate 阻断 {len(_ea.get('blocked_conclusions') or [])} 条）\n\n")
                f.write(f"**锚点入池**：{_ea.get('pooled', 0)} 条"
                        f"（{'已获证据资格' if _ea.get('as_evidence')
                            else '仅记录，不作证据'}）\n\n")
            # ★ 两条通道已在头部写明；此处只在「联网关」时补一句留痕，
            #   并把「怎么接」指清楚（事实题才提示 —— 决策题不提示）。
            # ★ 锚点通道默认**开着** —— 再写「两条通道都关」
            #   就是错话。改成按**两条通道各自的实际状态**发言。
            _w_on = bool(_web_lane_stats(result)["enabled"])
            _a_st = result.get("external_anchor")
            _a_eff = bool(isinstance(_a_st, dict) and _a_st.get("anchors"))
            if not _w_on and not _a_eff:
                if not _has_decision_context(
                        str(result.get("question") or "")):
                    f.write(
                        "★ **本题是事实型询问，但本次未接入外部校验**"
                        "（锚点通道："
                        + ("开着但未挂文件" if isinstance(_a_st, dict) else "关")
                        + "；联网检索：关）"
                        " —— 这是一次**显式选择**，不是默认特权：\n"
                        "  - 锚点：把 `external_anchor.path` 指向锚点快照 JSON；\n"
                        "  - 联网：`--web on`（或配置 `web_search.*` 五档）；\n"
                        "  - 未接入时，史实类结论**没有外部证据支撑**，请自行核对。\n\n")
            f.write(f"**可判定性**: {dec.get('decidability', '?')}\n\n")
            f.write(f"**理由**: {dec.get('reason', '')}\n\n")
            for a in dec.get("decidable_aspects", []):
                f.write(f"- 📗 可判定：{a}\n")
            for a in dec.get("undecidable_aspects", []):
                f.write(f"- 📘 不可判定：{a}\n")
            f.write("\n")
        chans = result.get("channels") or []
        f.write(f"**回来通道**: "
                f"{'、'.join(chans) if chans else '全关（历史不参与本次）'}\n\n")
        _ea2 = result.get("external_anchor")
        if _ea2 and not _ea2.get("error"):
            f.write("### 外部锚点 · 逐条对照\n\n")
            f.write(f"来源 `{_ea2.get('source_file', '?')}`"
                    f"（{_ea2.get('retriever', '?')}"
                    f"，检索于 {_ea2.get('retrieved_at', '?')}）\n\n")
            for _it in (_ea2.get("items") or []):
                _mark = {"印证": "✅", "冲突": "❌",
                         "无对应": "➖"}.get(_it.get("verdict"), "➖")
                f.write(f"- {_mark} {_it.get('verdict')}｜"
                        f"{_it.get('claim', '')[:160]}")
                if _it.get("anchor_ids"):
                    f.write(f"　← 锚点 {'、'.join(_it['anchor_ids'])}")
                if _it.get("note"):
                    f.write(f"　（{_it['note'][:120]}）")
                f.write("\n")
            f.write("\n")
        f.write(f"**保留**: {result['keep']}\n\n")
        f.write(f"**资源**: {result['llm_calls']} 次 LLM | "
                f"{result['llm_tokens']} tokens\n")
        # ★ [成本两分] 跑本身 vs 自测量（判定类）：混在一起会让「自测量的开销」
        #   看起来像「任务本身的成本」。未登记的 stage 一律计入前者（宁少算）。
        _oc = int(result.get("llm_ops_calls") or 0)
        _ec = int(result.get("llm_eval_calls") or 0)
        # ★ [多样性预算] 读数：层 × 通道 组合数（Ashby 必要多样性定律）。
        _dv = result.get("diversity") or {}
        if _dv.get("combos"):
            f.write(f"**多样性预算**: 层 {_dv.get('layers')} × 通道 "
                    f"{_dv.get('channels')} = {_dv.get('combos')} 组合"
                    f"（模式 {_dv.get('mode')}）｜{_dv.get('note', '')}\n")
        # ★ [层读数进产物] 此前【主因】/【发散三态】/【anytime 下界】/【早期预警】
        #   只写在 `dump_view_fields()`（**控制台转储**）里 ⇒ **产物 md 看不到**，
        #   读者视角等于不存在（真跑抓出的真缺口）。这里按层补进产物。
        try:
            _lay_rows = []
            for _e in ("0", "1", "both", "all"):
                _vv = (result.get("views") or {}).get(_e) or {}
                if not _vv:
                    continue
                _bits = []
                if _vv.get("stop_primary"):
                    _bits.append("主因=%s" % str(_vv["stop_primary"])[:46])
                _dvv = _vv.get("divergence") or {}
                if _dvv:
                    _bits.append("三态=%s" % _dvv.get("state"))
                    if _vv.get("best_round"):
                        _bits.append("历史最佳=第%s圈" % _vv["best_round"])
                _atv = _vv.get("anytime") or {}
                if _atv.get("lower") is not None:
                    _bits.append("anytime下界=%.3f" % float(_atv["lower"]))
                _cvv = (_vv.get("csd") or {}).get("new_amps") or {}
                if _cvv:
                    _bits.append("早预警=%s"
                                 % ("有前兆" if _cvv.get("hint") else "无前兆"))
                if _bits:
                    _lay_rows.append("  - %s层：%s"
                                     % (_LAYER_LABEL.get(_e, _e),
                                        " ｜ ".join(_bits)))
            if _lay_rows:
                f.write("**层读数（每层）**：\n")
                for _lr in _lay_rows:
                    f.write(_lr + "\n")
                f.write("      ★ 「三态」= 收敛/平稳/停滞/发散；「历史最佳」是**回滚指针**"
                        "（被回滚的圈不删）；anytime 下界对**任意停时**有效。\n")
                f.write("\n")
        except Exception as _el:
            f.write("**层读数（每层）**：取层读数失败（%s）\n\n"
                    % type(_el).__name__)

        # ★ [compact 内部面预算] 率失真读数（不自动压缩，避免 ACE 式掉分）。
        _cp = result.get("compact") or {}
        if _cp.get("inner_share") is not None:
            f.write(f"**内部面预算**: 内部面占 {float(_cp['inner_share']):.0%}"
                    f"（预算 {float(_cp.get('budget', 0)):.0%}）｜{_cp.get('verdict')}\n")
        # ★ [信念 staleness] 读数（不改四态）。
        _bs = result.get("belief_staleness") or {}
        if _bs.get("n"):
            f.write(f"**信念陈旧度**: {_bs.get('stale_n', 0)}/{_bs.get('n')} 条"
                    f"可能已过期（最大 {_bs.get('max_age', 0)} 圈未再确认）"
                    f"｜★ 只出读数，不改状态\n")
        # ★ [预算 bandit] 仅启用时出现；探索选择必须留痕。
        _bd = result.get("bandit") or {}
        if _bd.get("enabled"):
            f.write(f"**预算 bandit**: 选中档 #{_bd.get('arm')}"
                    f"（{'探索' if _bd.get('explore') else '利用'}）"
                    f"｜奖励 {_bd.get('reward')}（职责度中位）· 成本 {_bd.get('cost')}k tok"
                    f"｜各档 n={_bd.get('n')}\n")
        if _oc or _ec:
            f.write(f"**成本两分**: 跑本身 {_oc} 次 / "
                    f"{int(result.get('llm_ops_tokens') or 0)} tokens ｜ "
                    f"自测量（判定类）{_ec} 次 / "
                    f"{int(result.get('llm_eval_tokens') or 0)} tokens\n\n")
        else:
            f.write("\n")
        f.write(
            "**状态标记**：💭 未决（还没走到）｜⏸ 悬置（决定不碰）"
            "｜📘 不可判定（原则上判不出）｜⚡& 撞不动的结构\n\n"
        )
        san = result.get("input_sanity")
        if san is None:
            f.write("**输入自检**：未启用（本产物未做输入健全性检查）\n\n")
        elif san.get("issues"):
            f.write("**⚠️ 输入自检**\n\n")
            for _it in san["issues"]:
                f.write(f"- `{_it['term']}` — {_it['why']}\n")
            if san.get("note"):
                f.write(f"\n{san['note']}\n")
            f.write("\n")
        else:
            f.write("**输入自检**：已检查，未发现问题"
                    f"（{str(san.get('note') or '无悬空符号')[:60]}）\n\n")
        f.write("---\n\n")
        try:
            f.write(render_manifestation(result))
            f.write("\n---\n\n")
        except Exception as _me:
            f.write(f"## 显化说明\n\n❌ 渲染失败：{_me}\n\n---\n\n")
        # ★ 落地层放在显化说明之后：读产物的人要的是结论和待办，
        #   不是四层的原始字段。逐层明细降级为附录后置。
        try:
            f.write(render_landing(result))
            f.write("\n---\n\n")
        except Exception as _le:
            # 落地层渲染失败不能拖累产物落盘 —— 但必须留痕，
            # 否则"没有落地层"和"落地层崩了"长得一样。
            f.write("## 落地层\n\n❌ 渲染失败，下面只有逐层明细："
                    f"{_le}\n\n---\n\n")

        f.write("## 附：逐层明细\n\n<sub>内部状态全量留痕。"
                "结论请看上面的落地层。</sub>\n\n")

        for key in ("0", "1", "both", "all"):
            v = result["views"].get(key)
            if not v:
                continue
            f.write(f"### {_LAYER_LABEL.get(key, key)}层 `{key}`\n\n")
            f.write(f"**锚点**：{v['anchor']}\n\n")
            f.write("**候选**：\n")
            for c in v["candidates"]:
                if c.get("attribute_anchored"):
                    tag = (f"[属性{c['attribute']}◈{c.get('source') or '?'}展开"
                           f"×位置{c['position']}]")
                else:
                    tag = (f"[属性{c['attribute']}×位置{c['position']}"
                           f"｜阴{c.get('yin','?')}×阳{c.get('yang','?')}]")
                marks = []
                if c.get("is_amp_candidate"):
                    marks.append("⚡&")
                if not c.get("attribute_anchored") and \
                        c.get("yin") != c.get("yang"):
                    marks.append("⟂")
                mark = (" " + "".join(marks)) if marks else ""
                f.write(f"- {tag} {c['desc']}{mark}\n")
            f.write(f"\n**ing 对撞**：\n\n{v['collision']}\n\n")
            f.write("**& 印记**：\n")
            for a in v["amps"]:
                f.write(f"- [{AMP_TYPES.get(a.get('type',''),'?')}] "
                        f"{a.get('desc','')}\n")
            f.write("\n**悬空线头**：\n")
            for t in v["threads"]:
                f.write(f"- 💭 {t.get('desc','')}\n")
            if v.get("rehashed"):
                f.write(f"\n**未入池 · 翻回老地方**（{len(v['rehashed'])} 条）：\n")
                for rp in v["rehashed"]:
                    rd = f"（第 {rp['round']} 圈）" if rp.get("round") else ""
                    f.write(f"- [{rp.get('kind','?')}]{rd} {rp.get('desc','')}\n"
                            f"  ⊘ 与池中已有重复：{rp.get('same_as','')}\n")
            if v.get("probes"):
                f.write("\n**探针回归**：\n")
                for p in v["probes"]:
                    f.write(f"- {p.get('question','')}  \n"
                            f"  ↩ 回来：{p.get('link','')}"
                            f"｜增益 {p.get('expected_gain','?')}\n")
            else:
                f.write("\n**探针回归**：此处无自问可回归\n")
            if v.get("meta"):
                f.write("\n**元反思**：\n")
                for m in v["meta"]:
                    f.write(f"- {m}\n")
            if v.get("untouched"):
                f.write("\n**尚未触及的方面**：\n")
                for u in v["untouched"]:
                    f.write(f"- 💭 {u.get('desc','')}"
                            f"（{u.get('source','')}）\n")
            if v.get("engagements"):
                f.write("\n**本层碰了**：\n")
                for e in v["engagements"]:
                    f.write(f"- {e.get('target','')}：{e.get('how','')}\n")
            if v.get("refinements"):
                f.write("\n**深入子问题**（对已回答子问题的再次推进）：\n")
                for rp in v["refinements"]:
                    f.write(f"- 子问题[{rp.get('sub_id')}] "
                            f"{rp.get('sub_question','')}："
                            f"{rp.get('how','')}"
                            f"（第 {rp.get('layer','?')} 圈）\n")
            if v.get("suspensions"):
                f.write("\n**决定不消解**：\n" if key == "all"
                        else "\n**主动悬置**：\n")
                _susp_kept, _susp_dup = _dedup_suspensions_for_render(
                    v["suspensions"])
                for s in _susp_kept:
                    f.write(f"- {s.get('target','')}："
                            f"{s.get('reason') or '直觉，无理由'}"
                            f"（{s.get('reason_type','')}）\n")
                if _susp_dup:
                    f.write(f"  （另有 {_susp_dup} 条同 target 重复"
                            f"已合并；原始 {len(v['suspensions'])} 条）\n")
            if v.get("revocations"):
                f.write("\n**撤回的悬置**：\n")
                for r in v["revocations"]:
                    f.write(f"- {r.get('suspension_id','') or r.get('target','')}："
                            f"{r.get('reason','')}\n")
            if v.get("deferrals"):
                f.write("\n**延迟债务**（终态）：\n")
                for d in v["deferrals"]:
                    f.write(f"- [{d.get('status','?')}] 子问题{d.get('sub_id')} "
                            f"{d.get('sub_question','')}：{d.get('reason','')}\n"
                            f"  回访条件：{d.get('revisit_condition','')}")
                    if d.get("resolved_at") is not None:
                        f.write(f"｜止于第 {d['resolved_at']} 层"
                                f"（{d.get('resolution_reason','')}）")
                    if d.get("reopened_from"):
                        f.write(f"｜← 重新挂账（接 {d['reopened_from']}）")
                    f.write("\n")
            if v.get("escalations"):
                f.write("\n**迁向不可判定（本层提出的）**：\n")
                for e in v["escalations"]:
                    _ev = "、".join(e.get("evidence") or []) or "无"
                    f.write(f"- 子问题{e.get('sub_id')}"
                            f"（证据：{_ev}）：{e.get('reason','')}\n")
            if v.get("reclassifications"):
                f.write("\n**可判定性转移（本层提出的 · 三态可转·须证据）**：\n")
                for e in v["reclassifications"]:
                    _ev = "、".join(e.get("evidence") or []) or "无"
                    f.write(f"- 子问题{e.get('sub_id')}→"
                            f"{_DEC_STATE_CN.get(e.get('to'), e.get('to') or '?')}"
                            f"（证据：{_ev}）：{e.get('reason','')}\n")
            if v.get("settlement"):
                stl = v["settlement"]
                _cov = stl.get("coverage")
                _cov_s = f"{_cov:.0%}" if isinstance(_cov, (int, float)) else "N/A"
                # ★ 百分比必须带分子分母：「100%」是 1/1 还是 20/20，牵着
                #   这个数能不能用。同题三跑实测 1/1、5/5、1/1 都叫 100%。
                #   分母 ≤2 时分辨率 ≥50pt，等于没有中间值，明写出来。
                _x, _y = stl.get("answered"), stl.get("total")
                _xy = f"{_x}/{_y}" if _y is not None else "?/?"
                _warn = ""
                if isinstance(_y, int) and 0 < _y <= 2:
                    _warn = ("  ⚠️ 分母仅 "
                             f"{_y} 条，分辨率 ≥{int(100 / _y)}pt，"
                             "这个百分比只能当有无看，不能当程度看")
                f.write(f"\n**终局清算**：clean={stl.get('clean')}，"
                        f"遗留 {stl.get('leftover', 0)} 项，"
                        f"可判定覆盖率 {_xy}（{_cov_s}）{_warn}\n")
                # ★ 快照 vs 终局：两个数不一样就说明后半程确实补回了
                #   东西 —— 以前只印快照，等于把后半程的功劳抹了。
                _snap = stl.get("snapshot_coverage")
                if (isinstance(_snap, (int, float))
                        and isinstance(_cov, (int, float))
                        and abs(_snap - _cov) > 0.005):
                    f.write(f"  - ⚠️ 研究层收尾时是 {_snap:.0%}，"
                            f"后两层补到 {_cov:.0%}"
                            f"（旧产物只印前面那个数）\n")
                # 被内部机制改出「欠答案」集合的条数。人数没少（分母冻住了），
                # 但这些人现在落在分子外面——覆盖率因此掉了多少，得说清楚。
                _dr = stl.get("drifted_out")
                if isinstance(_dr, int) and _dr > 0:
                    f.write(f"  - ⚠️ 进门时判为「欠答案」有 {_dr} 条，被跑圈中"
                            f"的内部机制改判成了 undecidable"
                            f"（饿够圈数 / 终局清算时账户被转出）。"
                            f"分母已冻结，它们仍算在账里，因此这一"
                            f"条的覆盖率**不会**因为改判而变好看\n")
            if v.get("adjudications"):
                f.write("\n**本层裁决的张力**：\n")
                for a in v["adjudications"]:
                    f.write(f"- {a.get('tension','')} → 极性 {a.get('polarity','?')}"
                            f"（{a.get('how','')}）\n")
            if v.get("duel_suspensions"):
                f.write("\n**本层悬置的张力**：\n")
                for s in v["duel_suspensions"]:
                    f.write(f"- [{s.get('status','?')}] "
                            f"{s.get('target','')}"
                            f"（{s.get('quadrant','') or '未归类'}）"
                            f"：{s.get('reason') or '直觉，无理由'}"
                            f"（{s.get('reason_type','')}）\n")
            if v.get("meta_closure"):
                clo = v["meta_closure"]
                f.write(f"\n**闭环清算**：clean={clo.get('clean')}，"
                        f"对撞张力 {clo.get('total', 0)} 类，"
                        f"未交代 {clo.get('unsettled', 0)} 类"
                        f"（编号对账：命中 {clo.get('by_id', 0)} 条 / "
                        f"引用 {clo.get('covered_ids', 0)} 个编号；"
                        f"其中已了结 {clo.get('by_id_inactive', 0)} 个、"
                        f"定位不到 {clo.get('by_id_unknown', 0)} 个）\n")
                _closed = clo.get("closed")
                if _closed is not None:
                    f.write(f"（对撞悬置共 {clo.get('duel_total', 0)} 类："
                            f"{_closed} 类已了结不参与清算，"
                            f"{clo.get('total', 0)} 类 active/stable 待交代）\n")
                for u in (clo.get("uncovered") or []):
                    f.write(f"- 未交代：{u}\n")
            if v.get("decidable_product") and v["decidable_product"].get("answer"):
                dp = v["decidable_product"]
                f.write("\n**📗 可判定通道**：\n")
                f.write(f"- answer：{dp.get('answer','')}\n")
                f.write(f"- answered_sub_ids：{dp.get('answered_sub_ids')}\n")
                f.write(f"- distance：{dp.get('distance')}\n")
                for ev in (dp.get("evidence") or []):
                    f.write(f"- evidence：{ev}\n")
            if v.get("undecidable_product") and v["undecidable_product"].get("structural_amps"):
                up = v["undecidable_product"]
                f.write("\n**📘 不可判定通道**：\n")
                f.write(f"- why_undecidable：{up.get('why_undecidable','')}\n")
                f.write(f"- clarity：{up.get('clarity')}\n")
                f.write("- 独立结构（独立度分母）：\n")
                for sa in (up.get("structural_amps") or []):
                    f.write(f"  - structural_amp：{sa}\n")
                if up.get("aligned_amps"):
                    f.write("- 对齐 und_aspects（另计，不参与独立度）：\n")
                    for aa in up["aligned_amps"]:
                        f.write(f"  - aligned_amp：{aa}\n")
            # ★ [LDG 修真] 缺省 None 不再参与比较（旧口径 `None < 1.0` 直接
            #   TypeError —— 冒烟 check_layer_guard 抓出的真崩）。缺省不印。
            _d2q_s = v.get("distance_to_question")
            if _d2q_s is not None:
                f.write(f"\n**综合距离**：{float(_d2q_s):.2f}\n")
                if v.get("covered_aspects"):
                    f.write(f"- covered_aspects："
                            f"{'、'.join(v['covered_aspects'])}\n")
                if v.get("uncovered_aspects"):
                    f.write(f"- uncovered_aspects："
                            f"{'、'.join(v['uncovered_aspects'])}\n")
            if v.get("rounds_run"):
                roles = " → ".join(v.get("roles_run") or [])
                # [P2-9] rounds_cap 是这一层真正跑的上限（含 all_extra_rounds）
                _cap = v.get("rounds_cap") or rounds.get(v.get("entry"), "?")
                f.write(f"\n**实际走了 {v['rounds_run']} 圈**"
                        f"（上限 {_cap} 圈）"
                        + (f"：{roles}" if roles else "") + "\n")
            if v.get("round_log"):
                f.write("\n| 圈 | 角色 | 新 & | 新线头 | 连续无新增(&/线头) | 连续无推进 |\n")
                f.write("|---|---|---|---|---|---|\n")
                for g in v["round_log"]:
                    f.write(f"| {g.get('round')} | {g.get('role','')} "
                            f"| {g.get('new_amps')} | {g.get('new_threads')} "
                            f"| {g.get('idle_amp')}/{g.get('idle_thread')} "
                            f"| {g.get('idle_stall')}"
                            f"{'（' + g['why'] + '）' if g.get('why') else ''} |\n")
            if v.get("stop_reason"):
                f.write(f"\n**螺旋停止**：{v['stop_reason']}\n")
            if v.get("closure_reason"):
                f.write(f"\n**清算交代**（不是停止理由）"
                        f"：{v['closure_reason']}\n")
            if v.get("errors"):
                f.write("\n**失败记录**：\n")
                for e in v["errors"]:
                    f.write(f"- {e}\n")
            if v.get("manifest"):
                f.write(f"\n**view**：\n{v['manifest']}\n")
            if v.get("quality_flags"):
                f.write(f"\n**质量线索**：{', '.join(v['quality_flags'])}\n")
            if v.get("quality_verdict"):
                f.write(f"**质量评价**：{v['quality_verdict']}\n")
            if v.get("self_check"):
                sc = v["self_check"]
                # [输出 redesign] 旧写法无条件打印「可疑候选：[]」「可疑 &：[]」
                # 「诚实承认空：True」—— 空列表和模型自评占了一大半篇幅，
                # 读起来像调试日志。改成：只在**有东西**时才写；
                # 模型的自评（*_verdict）不进产物，它们是模型对自己打分，
                # 不是可核对的事实（要事实看下面的代码实算数字）。
                _sus_c = sc.get("suspicious_candidates") or []
                _sus_a = sc.get("suspicious_amps") or []
                if _sus_c or _sus_a:
                    f.write("\n**自省 · 点名**：\n")
                    for _x in _sus_c:
                        f.write(f"- ⚠ 可疑候选：{_x}\n")
                    for _x in _sus_a:
                        f.write(f"- ⚠ 可疑 &：{_x}\n")
                # [P2-4] 「此处未生」计数：进 md，否则自省结论只在 view.rendered 里
                if sc.get("unsaid_count") is not None:
                    f.write(f"- 「此处未生」计数：{sc['unsaid_count']}"
                            f"（阈值 spiral.unsaid_escape_limit）\n")
                if sc.get("unsaid_is_escape"):
                    f.write(f"- ⚠ 判为逃避：{sc.get('unsaid_where', '')}\n")
                elif sc.get("unsaid_where"):
                    f.write(f"- 「此处未生」分布：{sc['unsaid_where']}\n")
                if v.get("rephrase_ratio") is not None:
                    f.write(f"- ing 复述率（代码实算）："
                            f"{v['rephrase_ratio']:.0%}\n")
                elif sc.get("ing_rephrased") is False:
                    f.write("- ing 复述率（代码实算）：未计算"
                            f"（本层没有可比对的上游 view 文本）\n")
            _dropped_all = v.get("carry_dropped_all") or []
            if _dropped_all:
                f.write("\n**回流硬执行 · 逐圈拦下的重现候选**"
                        f"（累计 {len(_dropped_all)} 条）：\n")
                for x in _dropped_all[:12]:
                    f.write(f"- 第 {x.get('round', '?')} 圈："
                            f"{x.get('desc', '')}\n"
                            f"  ⊘ 命中禁令：{x.get('ban', '')}\n")
            elif v.get("carry_dropped"):
                f.write("\n**回流硬执行 · 最后一圈拦下的重现候选**"
                        f"（{len(v['carry_dropped'])} 条）：\n")
                for x in v["carry_dropped"][:8]:
                    f.write(f"- {x.get('desc', '')}\n"
                            f"  ⊘ 命中禁令：{x.get('ban', '')}\n")
            # [P2-7] 自省回流核对：注入了约束就要有核对记录，否则等于没回流
            cc = v.get("carry_check") or {}
            _checks = v.get("carry_checks") or []
            if _checks:
                f.write("\n**自省回流核对**（逐圈）：\n")
                for c in _checks:
                    f.write(f"- 第 {c.get('round', '?')} 圈："
                            f"核对 {c.get('checked', 0)} 条，"
                            f"违例 {c.get('violations', 0)} 条\n")
                    for it in (c.get("items") or [])[:4]:
                        f.write(f"  · {it}\n")
                _tot_v = sum(int(c.get("violations", 0) or 0)
                             for c in _checks)
                f.write(f"- 合计：{len(_checks)} 次核对，"
                        f"违例 {_tot_v} 条\n")
            if cc:
                if not _checks:
                    f.write("\n**自省回流核对**：\n")
                    f.write(f"- 核对 {cc.get('checked', 0)} 条回流约束，"
                            f"违例 {cc.get('violations', 0)} 条\n")
                for it in (cc.get("items") or [])[:8]:
                    f.write(f"- {it}\n")
                if cc.get("notes"):
                    f.write(f"- {cc['notes']}\n")
            f.write("\n---\n\n")

        # ── 这一次我是谁（**索引**，不复述正文）────────────────
        #   `self_text` 的每条就是 `[<层>] <view.manifest[:900]>`，
        #   而完整 manifest 已在上面 `## 附：逐层明细` 里逐字渲染过。
        #   在这里再印一遍 = **纯重复**（实测占产物 15~35% 行）。
        #   ⇒ 只留一句索引：哪几层、各自多少字自我记忆，正文指向上文。
        _st_blocks = [str(b).strip()
                      for b in (result.get("self_text") or [])
                      if str(b).strip()]
        if _st_blocks:
            f.write("## 这一次我是谁（索引）\n\n")
            f.write("<sub>本跑各层已进入自我记忆的正文，见上文"
                    "「附：逐层明细」对应层——此处不重复。</sub>\n\n")
            for _b in _st_blocks:
                _tag = _b.split("\n", 1)[0].strip()
                f.write(f"- {_tag}（自我记忆 {len(_b)} 字）\n")
            f.write("\n---\n\n")

        f.write("## 池\n\n")
        for k, p in result["pools"].items():
            tag = "（总池）" if k == "all" else ""
            f.write(f"### {k} 池{tag}\n\n")
            f.write(f"- & 印记 {len(p['amps'])} 条\n")
            f.write(f"- 悬空线头 {len(p['threads'])} 条\n")
            f.write(f"- 探针 {len(p.get('probes', []))} 条\n")
            f.write(f"- 主动悬置 {len(p.get('suspensions', []))} 条\n")
            _meta_all = list(p.get("meta") or [])
            if _meta_all:
                _meta_kinds = {
                    "自省回流": 0, "P1-6 拦截": 0, "自省未生效": 0, "其它": 0,
                }
                for _m in _meta_all:
                    _s = str(_m)
                    if _s.startswith("[P1-6]"):
                        _meta_kinds["P1-6 拦截"] += 1
                    elif _s.startswith("[自省回流未生效]"):
                        _meta_kinds["自省未生效"] += 1
                    elif "self-check" in _s or "上一圈" in _s:
                        _meta_kinds["自省回流"] += 1
                    else:
                        _meta_kinds["其它"] += 1
                _parts = " / ".join(
                    f"{k} {v}" for k, v in _meta_kinds.items() if v)
                f.write(f"- 📝 池级留痕（pool.meta）{len(_meta_all)} 条："
                        f"{_parts}\n")
            _susp_all = list(p.get('suspensions') or [])
            _self_res = [x for x in _susp_all
                         if x.get('status') == 'resolved'
                         and x.get('resolved_at') == x.get('layer')]
            if _susp_all:
                _sr_n = len(_self_res)
                _sr_ratio = _sr_n / max(len(_susp_all), 1)
                _flag = (" ⚠️偏高（可能把'暂时没写出来'包装成'决定不碰'）"
                         if _sr_ratio > 0.3 else "")
                f.write(f"  · 其中一圈内自解 {_sr_n}/{len(_susp_all)}"
                        f"（{_sr_ratio:.0%}）{_flag}\n")
            if p.get("sub_questions"):
                _sqs = list(p["sub_questions"])
                _n_dec = sum(1 for s in _sqs
                             if s.get("decidability") == "decidable")
                _n_und = sum(1 for s in _sqs
                             if s.get("decidability") == "undecidable")
                _n_oth = len(_sqs) - _n_dec - _n_und
                _tail = f"（另有 {_n_oth} 条 partial 等）" if _n_oth else ""
                f.write(f"- 子问题 {len(_sqs)} 条"
                        f"：可判定 {_n_dec} / 不可判定 {_n_und}{_tail}\n")
                _sr_vals = [int(s2.get("_starve_rounds", 0) or 0)
                            for s2 in _sqs]
                _sr_dist = {}
                for _v in _sr_vals:
                    _sr_dist[_v] = _sr_dist.get(_v, 0) + 1
                _sr_dist_s = "、".join(
                    f"{k}圈×{v}" for k, v in sorted(_sr_dist.items()))
                _debt_sids = {d.get("sub_id")
                              for d in (p.get("deferrals") or [])
                              if d.get("status") == "deferred"}
                _n_with_debt = sum(1 for s2 in _sqs
                                   if s2.get("id") in _debt_sids)
                _srm_vals = [int(s2.get("_starve_max_seen", 0) or 0)
                             for s2 in _sqs]
                _srm_dist = {}
                for _v in _srm_vals:
                    _srm_dist[_v] = _srm_dist.get(_v, 0) + 1
                _srm_dist_s = "、".join(
                    f"{k}圈×{v}" for k, v in sorted(_srm_dist.items()))
                _n_trk = sum(1 for s2 in _sqs
                             if "_starve_max_seen" in s2)
                _trk_note = (f"计数已写 {_n_trk}/{len(_sqs)} 条"
                             if _n_trk else "★ 计数未写（机制未运行）")
                f.write(f"- 🍽 无进展计数：最高 {max(_sr_vals)} 圈"
                        f"（{_sr_dist_s}）｜运行期峰值 {max(_srm_vals)} 圈"
                        f"（{_srm_dist_s}）｜名下有挂账的子问题 "
                        f"{_n_with_debt} 条｜{_trk_note}\n")
            if p.get("deferrals"):
                f.write(f"- 延迟债务 {len(p['deferrals'])} 条\n")
            if p.get("escalations"):
                f.write(f"- 迁向不可判定留痕 {len(p['escalations'])} 条\n")
            _dlog = list(p.get("decidability_log") or [])
            _dok = [x for x in _dlog if x.get("status") == "applied"]
            _dno = [x for x in _dlog if x.get("status") != "applied"]
            if _dok:
                f.write("- 📐 可判定性变更轨迹：" + " ｜ ".join(
                    f"L{x.get('layer', '?')} 子问题[{x.get('sub_id')}] "
                    f"{_DEC_STATE_CN.get(x.get('from'), '?')}→"
                    f"{_DEC_STATE_CN.get(x.get('to'), '?')}"
                    f"（据 "
                    + ("、".join(str(e.get("resolved_to"))
                                 for e in (x.get("evidence") or []))
                       or "—")
                    + f"；{x.get('reason', '')}）"
                    + (f"，并重新挂账 {x['reopened_debt']}"
                       if x.get("reopened_debt") else "")
                    for x in _dok) + "\n")
            if _dno:
                f.write(f"- 📐 被驳回的可判定性变更 {len(_dno)} 条："
                        + " ｜ ".join(
                            f"子问题[{x.get('sub_id')}]→"
                            f"{_DEC_STATE_CN.get(x.get('to'), x.get('to') or '?')}"
                            f"（{x.get('why', '')}）"
                            for x in _dno[:4]) + "\n")
            if p.get("duel_suspensions"):
                f.write(f"- 张力悬置 {len(p['duel_suspensions'])} 条\n")
            dc = p.get("decidable_channel") or {}
            uc = p.get("undecidable_channel") or {}
            if dc.get("answers"):
                f.write(f"- 📗 可判定通道：累计 {len(dc['answers'])} 条 answer\n")
            if uc.get("structural_amps"):
                f.write(f"- 📘 不可判定通道：累计 "
                        f"{len(uc['structural_amps'])} 条结构性 &\n")
            def _render_trace(_trace, _first, _label):
                if not _trace:
                    return
                _segs = []
                _prev = 0
                for _t in _trace:
                    _h = int(_t.get("hit", 0) or 0)
                    _delta = _h - _prev
                    _segs.append(
                        f"L{_t.get('layer', '?')} {_h}/"
                        f"{int(_t.get('total', 0) or 0)}"
                        + (f"（+{_delta}）" if _delta > 0 else ""))
                    _prev = _h
                f.write(f"- 📘 不可判定{_label}覆盖轨迹："
                        + " → ".join(_segs) + "\n")
                if _first:
                    _fl = "、".join(
                        f"{str(_a)[:40]}（L{_l}）"
                        for _a, _l in list(_first.items())[:6])
                    if len(_first) > 6:
                        _fl += f" 等 {len(_first)} 项"
                    f.write(f"- 📘 首次对上的方面（{_label}）：{_fl}\n")

            _render_trace(uc.get("struct_trace") or [],
                          uc.get("aspect_first_hit") or {}, "独立结构")
            _render_trace(uc.get("aligned_trace") or [],
                          uc.get("aligned_first_hit") or {}, "对齐结构")
            if p.get("duel_alignment"):
                _al = p["duel_alignment"]
                _q = _al.get('quality', '?')
                _qnote = "（合法结果：两侧没有同一件事可对）" \
                    if _q == "unaligned" else ""
                f.write(f"- 四象限对齐 {_q}"
                        f"（匹配率 {_al.get('match_rate',0):.0%}）"
                        f"{_qnote}\n")
                if _q == "unaligned":
                    f.write(f"  · 可对齐项：修行 {_al.get('practice_n', 0)} 条"
                            f" × 研究 {_al.get('research_n', 0)} 条；"
                            f"最接近的一对相似度 "
                            f"{_al.get('best_score', 0):.2f}"
                            f"（阈值 0.60 包含度 / 0.70 关键词）\n")
            f.write("\n")

        pools = result.get("pools", {})
        p_susp = pools.get("0", {}).get("suspensions", [])
        r_def = pools.get("1", {}).get("deferrals", [])
        d_susp = pools.get("both", {}).get("duel_suspensions", [])

        f.write("## 悬置总览\n\n")
        def _merge_lifecycle(items, key):
            order = {}
            seq = []
            for it in items:
                k = str(it.get(key, "")).strip()
                if not k:
                    continue
                st = str(it.get("status", "")).strip()
                if k not in order:
                    order[k] = []
                    seq.append(k)
                if st and (not order[k] or order[k][-1] != st):
                    order[k].append(st)
            out = []
            for k in seq:
                sts = order[k]
                if len(sts) > 1:
                    out.append((k, sts[-1], "→".join(sts)))
                else:
                    out.append((k, sts[0] if sts else "", ""))
            return out

        f.write("### 修行决定不碰的\n")
        for t, st, mig in _merge_lifecycle(p_susp, "target"):
            f.write(f"- {t}（{st}"
                    + (f"，状态迁移 {mig}" if mig else "") + "）\n")
        if not p_susp:
            f.write("（无）\n")
        f.write("\n### 研究延迟处理的\n")
        for t, st, mig in _merge_lifecycle(r_def, "sub_question"):
            f.write(f"- {t}（{st}"
                    + (f"，状态迁移 {mig}" if mig else "") + "）\n")
        if not r_def:
            f.write("（无）\n")
        f.write("\n### 对撞悬置的张力\n")
        for t, st, mig in _merge_lifecycle(d_susp, "target"):
            f.write(f"- {t}（{st}"
                    + (f"，状态迁移 {mig}" if mig else "") + "）\n")
        if not d_susp:
            f.write("（无）\n")

        f.write("\n### ★ 三个视角都不碰的\n")
        intersect = []
        used_r = set()
        for s in p_susp:
            st = str(s.get("target", "")).strip()
            if not st:
                continue
            for j, d in enumerate(r_def):
                if j in used_r:
                    continue
                if _similar(st, str(d.get("sub_question", "")), 0.7):
                    for s2 in d_susp:
                        if _similar(st, str(s2.get("target", "")), 0.7):
                            intersect.append(st)
                            used_r.add(j)
                            break
                    break
        for t in intersect:
            f.write(f"- {t}\n")
        if not intersect:
            f.write("（无——三棵树没有共同够不到的面）\n")
        f.write("\n---\n\n")

    # [fix-101] route 不含 all 时，A 模式的汇流圈结果也要落盘。
    # ★ 这一段原来**掉在 `with open(...)` 外面**（缩进少了 4 格），却还在
    #   用 f.write —— 一旦 result 里真有 confluence（route 不含 all 且跑
    #   了汇流圈），落盘就在半途抛 `ValueError: I/O operation on closed
    #   file`，整份日志被吞掉（真跑 s61a 连撞两次才发现）。缩进收回来。
        conf = result.get("confluence")
        if conf:
            f.write("## 汇流圈\n\n")
            f.write("_本次 route 未含 all 层，以下是汇流圈单独跑出的元层结果。_\n\n")
            f.write(f"**锚点**：{conf.get('anchor', '')}\n\n")
            if conf.get("collision"):
                f.write(f"**ing 对撞**：\n\n{conf['collision']}\n\n")
            amps = conf.get("amps") or []
            if amps:
                f.write("**& 印记**：\n")
                for a in amps:
                    f.write(f"- [{AMP_TYPES.get(a.get('type', ''), '?')}] "
                            f"{a.get('desc', '')}\n")
                f.write("\n")
            if conf.get("manifest"):
                f.write(f"**view 显形**：\n\n{conf['manifest']}\n\n")
            f.write("---\n\n")

    try:
        _md_so_far = md.read_text(encoding="utf-8")
        with open(md, "a", encoding="utf-8") as _fa:
            _ap_text = _render_full_appendix(result, _md_so_far)
            if _ap_mode == "file":
                _ap_text = _appendix_to_file(
                    _ap_text, md.with_name(md.stem + ".packed.json"))
            _fa.write(_ap_text)
    except Exception as _ae:
        with open(md, "a", encoding="utf-8") as _fa:
            _fa.write("\n## 附录 · 全量字段（packed 原文）\n\n"
                     f"❌ 渲染失败：{type(_ae).__name__}: {_ae}\n")
    print(f"📁 已保存: {md}")
    return md


# ============================================================
# 默认配置
# ============================================================
DEFAULT_CONFIG = {

    # ============================================================
    # 统一自适应调度器
    #   enabled=false ⇒ 十一项一律退回「配置 / 默认」，行为回到上一版。
    #   allow_route_trim=false ⇒ auto 永不砍层（层集合恒为全四层）。
    #   history_limit = 扫多少份 `outputs/*.packed.json` 做历史读数。
    # ============================================================
    "auto": {
        "enabled": True,
        "allow_route_trim": True,
        # ★ 语料实测：`outputs/` 里有 368 份产物 md + 16 条跑批记录，
        #   默认只扫 20 份等于把历史样本丢了 95%。200 够覆盖现有语料。
        "history_limit": 200,
        "history_md": True,
        "history_batch": True,
        # 历史加权的时间半衰期（天）。0 = 不衰减（等权）。
        # 旧样本是旧配置下的读数，不加权会把新读数系统性地拉向旧行为。
"history_halflife_days": 14,
        # [预算 bandit 可配] 默认 **关**（enabled=false）⇒ 出厂零行为差。
        #   enabled=true 时用 UCB1-with-cost 在「每层圈数上限」三档
        #   （3/4/6）间选择：奖励 = 职责度中位 − cost_w ×（tokens/1000）。
        #   ★ 探索会**故意选已知较差的档**，因此每次探索选择都在产物留痕
        #     （否则用户看到「这次为什么跑得差」会查无原因）。
        "bandit": {
            "enabled": False,
            "cost_w": 0.3,
            "c": 1.0,
        },
    },
    "runtime": {
        "web": "auto",
        "thinking": "auto",
        "effort": "auto",
    },
    "api": {
        "key": "",
        "base_url": os.getenv("DGTF_BASE_URL", "https://api.deepseek.com/v1"),
        # [fix-111] 2026-10-02 起默认用**显式 ID**，不再用 legacy 别名
        #   deepseek-chat / deepseek-reasoner（官方公告 2026-07-24 停服；
        #   实测当天仍通，但 served_by 由服务端决定，不可控且此前无留痕）。
        #   thinking 是请求级参数：普通调用显式 disabled（flash 默认是开思考的）。
        "default_model": os.getenv("DGTF_MODEL", "deepseek-flash"),
        "reasoner_model": os.getenv("DGTF_REASONER_MODEL", "deepseek-flash"),
        "thinking": {
            "default": "disabled",
            "reasoner": "enabled",
            "effort": "low",
            # [fix-112] 逐环节档位：需要的开，不需要的关（与 yaml 一致）。
            "stages": {
                "auto_plan": "enabled",
                "plan_orientation": "enabled",
                "plan_resources": "enabled",
                "adjudicate_sub_tristate": "enabled",
                "adjudicate_sub_tristate_multi": "disabled",
                "anchor_crosscheck": "disabled",
                "dual_judge": "enabled",
                "assess_decidability": "enabled",
                "assess_decidability_from_pool_view": "enabled",
                "re_evaluate_pool": "enabled",
                "decide_parallel_mode": "disabled",
                "check_input_sanity": "disabled",
                "check_structure_saturation": "disabled",
                "re_anchor": "disabled",
                "ask_missing_polarity": "disabled",
                "decompose_normal": "disabled",
                "decompose_hybrid": "disabled",
                "decompose_koan": "disabled",
                "decompose_from_pool": "disabled",
                "probe_research": "disabled",
                "probe_duel": "disabled",
                "probe_meta": "disabled",
                "phase_probe": "disabled",
                "self_check": "disabled",
                "settle_research": "disabled",
            },
        },
        "timeout": 240,
        "max_retries": 3,
        "retry_backoff": 1.8,
    },

    "output": {
        "save_dir": "outputs",
        "verbose": True,
        "dump_rounds": False,
        "show_dual_judge": True,
        "show_ing": False,
        "show_manifest": False,
        "self_check": True,
        "show_probe_diag": False,
    },

    "actions": {
        "assess_decidability": True,
        "decompose_question": True,
        "decidability_source": "pool",
        "decompose_source": "pool",
        "parallel_mode": "auto",
        "parallel_warmup_rounds": 1,
        "pipeline_gate_timeout": 900,
        "parallel_expand": True,
        "input_sanity": True,
        "tri_multi_vote": True,
        "tri_vote_retry_empty": 1,
        "landing_decision": True,

        "re_anchor": True,
        "expand_yin": True,
        "expand_yang": True,
        "dual_judge": True,
        "ing": True,
        "he": True,
        "phase_probe": True,
        "manifest": True,
        "self_check": True,


        "re_evaluate_pool": True,
        "settle_research": True,
    },

    "sim": {
        # 池内去重阈值（上一版及以前是 Pool.merge 里的硬编码字面量）。
        # 默认值与原字面量逐位相同 ⇒ 不改这里就与旧版行为一致。
        "dedup": 0.9,
        "dedup_susp": 0.85,
        # [E2] 探针批选聚类阈值（把「同一个探针」聚起来）。
        #   ★ 曾在 yaml 里登记却没进 DEFAULT_CONFIG（yaml 记了引擎不认识
        #     的键 —— 用户改了没效果）⇒ 这里补上。拾取点：
        #     `select_probe_focus(..., thr=cfg.sim.cluster)`。
        #   ★ **不要**被 D3 复用：D3 的语义熵阈值走
        #     `belief.sem_entropy_thr`（两者尺度不同，见该键注释）。
        "cluster": 0.70,
    },

    "probe": {
        "min_gain": 0.3,
        "select_n": 3,
        # [E6] 自适应停止阈值（与 min_gain 两把尺子）。
        "stop_floor": 0.02,
        # [E2] 子模批选开关。★ 同 `sim.cluster`：曾只写进 yaml、未进
        #   DEFAULT_CONFIG ⇒ 这里补上（拾取点 `select_probe_focus`）。
        "submodular": True,
        # [E2] 子模批选边际下限。★ 必须 > 0，否则 `below_floor` 分支
        #   结构性不可达（值与 `_GAIN_MARGINAL_FLOOR` 同源）。
        "marginal_floor": 0.02,
    },

    "belief": {
        # [D2] `revoked` 需要的**不同攻击来源数**（与 `stable` 对称）。
        "revoke_sources": 2,
        # [D3] 语义熵聚类阈值。★ **独立于 `sim.cluster`**：`_sim3` 在
        #   中文上走字符二元组 Jaccard，「同一主张换个说法」实测只有
        #   0.41~0.79、不同主张 0.00 ⇒ 用 `sim.cluster`(0.70) 会簇恒单
        #   元素 ⇒ 熵恒 None（真跑 + 直测共同证实）。默认 = `_SEM_CLUSTER_THR`。
        #   拾取点：`refresh_belief_entropy(..., thr=cfg.belief.sem_entropy_thr)`。
        "sem_entropy_thr": 0.30,
        # [D2 修正] 语义归并开关（默认**关** ⇒ 出厂零行为差）。
        #   开 ⇒ 「几乎同一句话」的换说法重提记为已存在条目的一次复现
        #   （进 occurrences），留痕 merge_log。见 Pool.merge_semantic。
        "merge_semantic": False,
        # [D2 修正] 语义归并阈值。★ 0.85 是**刻意的高门槛**（红线
        #   「入池前挡重复」：不同主张实测 0.00~0.79，够不到它）。
        #   宁可漏并，不可错并。
        "merge_sim": 0.85,
    },

    "duty": {
        # [LDG] 层职责守卫：在**停止/收敛处**算「这层替原始问题干了什么」。
        #   三个读数：C 覆盖（问项按 core/background/followup 加权）·
        #   R 相关（|Direct|/(|Direct|+|Useless|)，惩罚无用断言）·
        #   S = 2CR/(C+R)（调和平均；一项塌了整体塌）。
        #   ★ 它是**读数不是分数**：不进 `_quality_verdict`，只做两件事
        #     —— ① 署名纪律（低于 floor 不许写「自然安住」）；
        #     ② 新停止判据「职责增益收敛」（连续 patience 圈 ΔS<tau）。
        "floor": 0.35,
        "tau": 0.02,
        "patience": 2,
        "remedy_rounds": 1,
    },

    "stop": {
        # [anytime-valid 可配] δ（默认 **0.0 = 关**）。>0 时启用一条新停止判据
        #   「结构增长已 anytime-valid 地判停」：「结构仍在长」的 0/1 序列，
        #   其**随时看随时停仍有效**的均值下界跌破 0.5 ⇒ 可停。
        #   ★ 为什么需要：本项目每圈边跑边判 = optional stopping，用固定样本
        #     公式在「边跑边看」下有效性不成立（假阳率暴涨）。
        #     依据：stitched Hoeffding 置信序列（Howard et al. 2021）。
        "anytime_alpha": 0.0,
    },

    # ★ [一键全开] 出厂**引擎侧默认 false**（保守）：所有判据/冒烟走它 ⇒
    #   基线零影响。出厂 `dgtf_config.yaml` 写 `true` ⇒ **本机真跑默认全开**。
    #   生效清单见 `_ALL_ON_ITEMS`（EML on / anytime 停止 / bandit / 语义归并 /
    #   相对阈值 / 联网 / 锚点 gate / 思考 high + effort high）。
    "all_on": False,

    "playbook": {
        # [EML] 经验记忆回路：跨跑**储存记忆**并让下次跑用它。
        #   mode：off（不读不写）/ shadow（**出厂默认**：只记不生效 ⇒
        #         零行为差）/ on（生效：只作用于调度与守卫阈值，不碰答案）。
        #   dir：记忆库目录（默认仓库根 `dgtf_memory/`）。
        #   top_k / promote_n：每次读几条 / 同向证据几次才 shadow→active。
        #   halflife_days：检索排序与遗忘共用的半衰期（与 auto 同源）。
        #   ★ 学坏防线：新条目一律 shadow；只省成本（quality_delta≤0 且
        #     cost_delta<0）**不许**升级；遗忘只改状态位、不删行。
        "mode": "shadow",
        "dir": "",
        "top_k": 3,
        "promote_n": 3,
        "halflife_days": 14.0,
        # ★ 无 run_id 的跑次是否也入库/参与学习（默认 False = 不收）：
        #   测试、半途、工具调用没有 id，读数不代表真实任务；让它们参与
        #   会**把真实条目的证据计数抬高**（一次冒烟上百次 run() 曾把
        #   n_ev 从 2 灌到 4 ⇒ 直接触发 promote = 测试替生产刷票）。
        "learn_from_anon": False,
    },

    "autotune": {
        # [AutoTune] 跨跑设计空间调优：从 `episodes.jsonl` 推**建议默认**
        #   （模式 / 层集 / 各层圈数上限），**只建议、不自动改行为**。
        #   min_n：同一（模式,层集）至少几次跑才进榜（样本太小不进 ⇒ 防偶发）。
        #     ★ 真跑数据定：1 → **2**。首轮 sweep 里 n=1 的组会让**单点读数**
        #       主导膝盖取舍；≥2 才谈得上「一批」。（`_autotune_v12333_结论.md`）
        #   quality_tau：层集取舍的容差 —— 质量不低于最优 −τ 的候选里取成本最低
        #     （帕累托膝盖 = 「该去的层去掉」的量化判据）。
        #   out：建议落盘路径（默认仓库根 `dgtf_autotune.json`）。
        "min_n": 2,
        "quality_tau": 0.05,
        "out": "",
    },

    "memory": {
        "channels": ["content", "context", "self"],
        # 每层保留多少条自我记忆（[P0-1] 原来是全局保留 4 条，
        # 并行模式下会被跑得最久的 all 层全部挤出）
        "self_layers": 4,
        "self_layers_per_entry": 2,
        # [P1-5] self-check 结论回流成下一圈的约束探针
        "carry_feedback": True,
        "shape_items": 6,
        "shape_chars": 900,
    },

    "spiral": {
        "soft_max": 2,
        "hard_max": 12,
        "stop_similarity": 0.8,
        "stable_need": 2,
        "stable_layers": 3,
        "batch_similarity": 0.6,
        "meta_cover_similarity": 0.6,
        "idle_limit": 2,
        "round_idle_limit": 2,
        "new_item_similarity": 0.55,
        "new_item_overlap": 0.55,
        "thread_new_similarity": 0.70,
        "thread_new_overlap": 0.70,
        "structure_saturation_enabled": True,
        "structure_saturation_every_n": 2,
        "round_stall_limit": 2,
        "rehash_similarity": 0.6,
        "stall_streak_limit": 2,
        "min_distance_improvement": 0.03,
        # [P2-4] 一圈里「此处未生」超过几处就算逃避（0 = 不设限）。
        # 支持 per_entry 按层覆盖：e.g. per_entry."0".unsaid_escape_limit: 5。
        # 兜底常量 UNSAID_ESCAPE_LIMIT = 3。
        "unsaid_escape_limit": 3,
        "convergence_window": 2,
        "all_extra_rounds": 1,
        "escalate_starve_rounds": 2,
        "no_push_when_idle": 1,
        "budget_per_round_floor": 10,
        "budget_per_round_cap": 12,
        # [P1-4] 极性裁决里 both 占比超过 max_ratio 时要求补裁（**追问**）
        "both_quota": {
            "enabled": True,
            "max_ratio": 0.7,
            "min_items": 2,
        },
        "both_tighten_ratio": 0.3,
        "alignment_similarity": 0.7,
        "alignment_containment": 0.6,
        "dedup_candidate_overlap": 0.65,
        "dedup_candidate_similarity": 0.70,
        "dedup_amp_overlap": 0.60,
        "dedup_amp_similarity": 0.62,
        "qc_rephrase_ratio": 0.5,
        "qc_both_ratio": 0.6,
        "all_drift_threshold": 0.5,
        "all_selfref_threshold": 0.4,
        "re_eval_every_n": 1,
        "re_eval_recent_k": 10,
        "min_rounds": {
            "0": 0,
            "1": 0,
            "both": 0,
            "all": 0,
        },
    },

    "external_anchor": {
        # 【默认 true】通道默认打开：配了 `path` 就自动接入；
        #   没配 path 是「开（未挂锚点文件）」这个**独立干净态** ——
        #   既不记 error，也不当成「接失败」。
        "enabled": True,
        # 【用途】锚点快照 JSON 的路径（相对当前工作目录，或绝对路径）。
        #   格式：{"question":..., "retrieved_at":..., "retriever":...,
        #          "anchors":[{"id","claim","source","url","as_of","kind"}]}
        "path": "",
        # 【用途】最多用几条锚点（防 prompt 膨胀）。
        "max_items": 12,
        # 【用途】收尾要不要做「结论 vs 锚点」只读对照（一次额外调用）。
        "crosscheck": True,
        "tier_floor": 2,
        "answers_min_len": 6,
        "answers_max_n": 5,
        "api_key_env": "TAVILY_API_KEY",
        "cache_ttl_hours": 24,
        "per_round": 2,
        "as_evidence": "off",
        # ★ 分诊降级（undecidable 因「信息不足」降为 decidable）。默认关
        "triage": False,
        # 检索后端。当前只有 snapshot 真实现，其它取值抛错不静默降级
        "retriever": "snapshot",
    },
    "web_search": {
        # 【用途】全局总闸。【默认】false —— 不显式打开就是**零调用**。
        "enabled": False,
        # 【用途】检索后端（key 走环境变量，不落盘）。
        "backend": "tavily",
        "api_key_env": "TAVILY_API_KEY",
        # 【用途】单次请求超时（秒）/ 重试次数 / 退避基数（秒）。
        "timeout_seconds": 30,
        "max_retries": 2,
        "backoff_seconds": 1.8,
        # 【用途】检索结果缓存小时数（sha256 落 cache/websearch/）。
        "cache_ttl_hours": 24,
        # 【配额三层】每环节每圈 / 每环节全程 / 每跑总。三层都过才允许调用。
        "quota": {
            "per_stage_round": 2,
            "per_stage_total": 8,
            "per_run_total": 30,
        },
        # 【环节授权】逐个环节的开关。修行层与停止判据**默认关**
        #   （修行层动了会污染「输入是形状不是数据」这条宪法级特性）。
        "stages": {
            "practice_term_calibration": False,
            "research_decompose": True,
            "research_evidence": True,
            "research_precedent": True,
            "duel_arbitration": True,
            "meta_clean_check": True,
            "stop_criteria": False,
        },
        # 【引用授权】off / record / crosscheck / evidence / gate。
        "as_evidence": "crosscheck",
        "tier_floor": 3,
        "tier_confirmed": {},
        # 【失败降级】连续失败达到此值 → 本跑联网关闭（留痕 [W-DISABLED]）。
        "auto_disable_after_failures": 3,
        "tier_proposal": False,
        # 【域名启发式】提案依据表：`[子串, tier]`，tier 越小越硬。
        #   未知域名保守取 3（> 默认 tier_floor 2 ⇒ 进不了引用表）。
        "domain_tier_rules": [
            [".gov.cn", 1], [".gov", 1], [".edu", 2],
            ["iso.org", 1], ["standard", 1], ["wikipedia.org", 3],
            ["blog", 4], ["forum", 4],
        ],
    },
}


def _deep_merge(base, override):
    r = dict(base)
    for k, v in override.items():
        if k in r and isinstance(r[k], dict) and isinstance(v, dict):
            r[k] = _deep_merge(r[k], v)
        else:
            r[k] = v
    return r


def _load_config_raw(path: str) -> dict:
    # ★ 这一行是 `load_config` 原来函数体的第一行 —— 改名时**不能**连着它一起吃掉：
    #   实测（本轮）就把它弄丢了 ⇒ `_deep_merge(cfg, ...)` 直接 UnboundLocalError。
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if not path or not (HAS_YAML and Path(path).exists()):
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        print(f"\n⚠️  配置文件解析失败：{path}")
        if hasattr(e, "problem_mark") and e.problem_mark:
            mark = e.problem_mark
            print(f"   位置：第 {mark.line + 1} 行，第 {mark.column + 1} 列")
        if hasattr(e, "problem") and e.problem:
            print(f"   问题：{e.problem}")
        print("\n   常见原因：")
        print("     1. 缩进不齐（子键缩进必须一致，通常用 2 或 4 空格）")
        print("     2. 顶层是列表/scalar（顶层必须是 mapping：key: value）")
        print("     3. 键后漏冒号（`output` 应为 `output:`）")
        print("     4. 同一个顶层 key 定义了两次")
        print("     5. Tab 和空格混用（YAML 只允许空格）")
        print(f"\n   已退回默认配置（{path} 被忽略）。")
        print(f"   想禁用该文件：删除或重命名为 {path}.bak\n")
        return cfg
    except Exception as e:
        print(f"\n⚠️  读取 {path} 失败：{type(e).__name__}: {e}")
        print("   已退回默认配置。\n")
        return cfg

    if not isinstance(user_cfg, dict):
        print(f"\n⚠️  {path} 顶层不是 mapping（应形如 `output:`）")
        print(f"   实际类型：{type(user_cfg).__name__}")
        print("   已退回默认配置。\n")
        return cfg

    cfg = _deep_merge(cfg, user_cfg)
    return cfg


#: [一键全开] 生效清单：`(配置路径, 全开值, 为什么)`。
#: ★ 只列**可切换的能力开关**；不含 route/rounds 这类运行参数（那是跑次的事）。
_ALL_ON_ITEMS = (
    ("auto.enabled", True, "自适应调度总开关"),
    ("playbook.mode", "on", "EML 经验记忆生效（跨跑学习闭环）"),
    ("stop.anytime_alpha", 0.05, "anytime-valid 停止判据生效（δ=0.05）"),
    ("auto.bandit.enabled", True, "预算 bandit 生效（探索必留痕）"),
    ("belief.merge_semantic", True, "语义归并生效（换说法记为复现）"),
    ("belief.sem_entropy_thr", "rel", "语义熵改用本批相对分位"),
    ("web_search.enabled", True, "联网检索"),
    ("external_anchor.as_evidence", "gate", "锚点作 gate 证据"),
    ("api.thinking.default", "enabled", "思考档默认开"),
    ("api.thinking.effort", "high", "思考强度 high"),
)


def _apply_all_on(cfg: dict):
    """[一键全开] `all_on: true` ⇒ 把 `_ALL_ON_ITEMS` 全部置开，并返回留痕。

    ★ 与 `_apply_runtime` 同层（`load_config` 最外层）—— 那是四个 return 出口的
      唯一汇合处；插在函数体中间会「某些路径不生效」，且没有判据看得见。
    ★ `all_on` 为假 ⇒ **恒等变换**（返回原 cfg、零 notes）⇒ 判据基线零影响。
    ★ 显式优先级：`all_on` 语义就是「全开」，因此它**覆盖**这些键的出厂值；
      要针对某一项做对照实验就**关掉 all_on**（而不是指望单项覆盖赢）。
    """
    if not (cfg or {}).get("all_on"):
        return cfg, []
    notes = []
    for path, val, why in _ALL_ON_ITEMS:
        d = cfg
        ks = str(path).split(".")
        for k in ks[:-1]:
            if not isinstance(d.get(k), dict):
                d[k] = {}
            d = d[k]
        old = d.get(ks[-1], "<缺>")
        if old != val:
            d[ks[-1]] = val
            notes.append("[all_on] %s：%r → %r（%s）" % (path, old, val, why))
    return cfg, notes


def load_config(path: str) -> dict:
    """ 在 `_load_config_raw` 之上套一层**运行期总控**。

    ★ 套在**最外层**而不是插进函数体中间：`_load_config_raw` 有
      **四个** return 出口（空路径 / yaml 解析失败 / 顶层非 mapping /
      正常）。插在中间就得改四处，漏一处就会「某些路径不生效」，
      而且**没有任何判据看得见**（那正是最难查的一类）。
    ★ 出厂 `runtime` 三项全 auto ⇒ 这一步对绝大多数调用是**恒等
      变换**（`check_v1234_runtime` 用「逐字相同」钉住）。
    """
    cfg, notes = _apply_runtime(_load_config_raw(path))
    cfg, _ao_notes = _apply_all_on(cfg)
    notes = list(notes) + list(_ao_notes)
    for n in notes:
        print("   · " + n)
    return cfg


# ============================================================
# 交互循环
# ============================================================
def _ask_question():
    try:
        q = input("\n你问> ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return q or None


def _validate_route(s):
    if not s:
        return "0,1,both,all"
    s = _normalize_punct(s)
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if not parts:
        return None
    valid = {"0", "1", "both", "all"}
    if any(p not in valid for p in parts):
        return None
    return ",".join(parts)


def _validate_rounds(s):
    if not s:
        return "0"
    s = _normalize_punct(s)
    if s.isdigit():
        n = int(s)
        if n <= 0:
            return None
        return s
    valid = {"0", "1", "both", "all"}
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        k, _, v = part.partition(":")
        k = k.strip()
        v = v.strip()
        if not v:
            m = re.match(r"^([a-zA-Z]+)(\d+)$", k)
            if m:
                k, v = m.group(1), m.group(2)
        if k not in valid:
            return None
        if not v.isdigit() or int(v) <= 0:
            return None
    return s


def _validate_channels(s):
    if not s:
        return ""
    s = _normalize_punct(s)
    if s.strip().lower() == "none":
        return "none"
    valid = {"content", "context", "self"}
    parts = [p.strip().lower() for p in s.split(",") if p.strip()]
    if not parts:
        return ""
    if any(p not in valid for p in parts):
        return None
    return ",".join(parts)


def _ask_route():
    while True:
        try:
            r = input("\n路由 [0,1,both,all]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        v = _validate_route(r)
        if v is not None:
            return v
        print("   ✗ 路由格式不对。可用：0 / 1 / both / all，用逗号分隔")
        print("     例：0,1,both,all  或  0,1,all  或  1")
        print("     （直接回车用默认 0,1,both,all）")


def _ask_rounds():
    while True:
        try:
            r = input("圈数 [0=用 hard_max]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        v = _validate_rounds(r)
        if v is not None:
            return v
        print("   ✗ 圈数格式不对。可用：")
        print("     数字（所有层同圈数）：3")
        print("     层:圈数 列表：0:2,1:2,both:3,all:3")
        print("     缺冒号也可：0:2,1:2,both3,all3")
        print("     直接回车 = 用 hard_max")


def _ask_channels():
    while True:
        try:
            r = input("通道 [回车=全开 / none=全关]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        v = _validate_channels(r)
        if v is not None:
            return v
        print("   ✗ 通道名不对。可用：content / context / self")
        print("     用逗号分隔，如 content,self")
        print("     直接回车=全开；none=全关")


def _ask_parallel():
    """ 询问并行模式（v1.21.53 加 C，v1.21.54 加 D~H）。"""
    while True:
        try:
            r = input("并行模式 [serial/A…H/auto]> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if r in ("", "auto"):
            return "auto"
        if r in ("serial", "s", "串行"):
            return "serial"
        if r in ("a", "b", "c", "d", "e", "f", "g", "h"):
            return r.upper()
        print("   ✗ 可选：serial / A~H / auto（回车=auto）")
        print("     serial = 严格串行（最稳）")
        print("     A      = 四层独立并行 + 汇流（快）")
        print("     B      = 轮次并行（每圈 barrier，读上一圈）")
        print("     C      = 流水线并行（最快，带时序依赖）")
        print("     D      = 修行/研究并行跑完 → 对撞 → 元层跟上")
        print("     E      = 修行/研究并行跑完 → 对撞跑完 → 元层")
        print("     F      = 修行跑完 → 研究 → 对撞 → 元层（全流水）")
        print("     G      = 修行跑完 → 研究 → 对撞跑完 → 元层")
        print("     H      = 修行跑完 → 研究跑完 → 对撞 → 元层跟上")
        print("     auto   = 由调度器按问题性质决定")


def _ask_display_options(cfg):
    print("\n展示开关（直接回车=保持默认；y/n 覆盖）")
    try:
        ans = input("  终端显示 ing 全文？[y/N]> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if ans in ("y", "yes"):
        cfg["output"]["show_ing"] = True
    elif ans in ("n", "no"):
        cfg["output"]["show_ing"] = False
    try:
        ans = input("  终端显示 view 全文？[y/N]> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if ans in ("y", "yes"):
        cfg["output"]["show_manifest"] = True
    elif ans in ("n", "no"):
        cfg["output"]["show_manifest"] = False
    return cfg


def _ask_runtime(cfg):
    """ 三项运行期总控：联网 / 思考 / 强度。返回 dict（**不改 cfg**）。"""
    print("\n运行期总控（3 项；直接回车 = auto = 按配置文件）")
    print("   当前生效：" + _runtime_summary_line(cfg))
    out = {}
    for key, label, tip in (
            ("web", " 联网总开关",
             "on=强制联网（仍受 web_search.stages / 配额约束）/ off=强制不联网"),
            ("thinking", " 思考总开关",
             "on=全环节开思考（成本↑，max_tokens≥32000）/ off=全关"),
            ("effort", " 思考强度  ",
             "low / high / max（**只在思考开启时生效**）")):
        _opts = (_RUNTIME_EFFORTS if key == "effort" else _RUNTIME_SWITCHES)
        while True:
            try:
                r = input("   %s [%s，回车=auto]> " % (label, "/".join(_opts)))
            except (EOFError, KeyboardInterrupt):
                print()
                return None
            _v = (_normalize_runtime_effort(r) if key == "effort"
                  else _normalize_runtime_switch(r))
            if _v is not None:
                out[key] = _v
                break
            print("      ✗ 可选：%s" % " / ".join(_opts))
            print("        %s" % tip)
    return out

def _ask_config(cfg=None):
    """：返回值加 parallel_str（4 元组）。
    v1.23.4：再加 runtime（**5 元组**）—— 联网 / 思考 / 强度总控。"""
    print("\n" + "─" * 60)
    print("配置（直接回车用默认值；Ctrl+C 退出）")
    print("─" * 60)
    route_str = _ask_route()
    if route_str is None:
        return None
    rounds_str = _ask_rounds()
    if rounds_str is None:
        return None
    channels_str = _ask_channels()
    if channels_str is None:
        return None
    parallel_str = _ask_parallel()
    if parallel_str is None:
        return None
    if cfg is not None:
        cfg = _ask_display_options(cfg)
        if cfg is None:
            return None
    runtime = _ask_runtime(cfg if cfg is not None else DEFAULT_CONFIG)
    if runtime is None:
        return None
    return route_str, rounds_str, channels_str, parallel_str, runtime


def _parse_channels(channels_str):
    if not channels_str:
        return None
    raw = [x.strip() for x in channels_str.split(",") if x.strip()]
    if raw == ["none"]:
        return []
    return [MemoryChannel.check(x) for x in raw]


def _ask_continue():
    while True:
        try:
            c = input("\n继续下一个问题？[y/n，默认 n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if c in ("", "n", "no", "q", "quit", "exit"):
            return False
        if c in ("y", "yes"):
            return True
        print("   ✗ 请输入 y 或 n（回车=退出）")


def _interactive_run(cfg):
    print(f"\n{'═'*60}")
    print(f"元 DGTF v{__version__} · 交互模式")
    print(f"{'═'*60}")
    print("每轮：问问题 → 问配置 → 运行 → 询问是否继续")
    print("任意 input 处 Ctrl+C 退出")
    print(f"{'═'*60}")

    while True:
        question = _ask_question()
        if question is None:
            print("已退出。")
            return

        cfg_result = _ask_config(cfg)
        if cfg_result is None:
            print("已取消。")
            return
        (route_str, rounds_str, channels_str, parallel_str,
         runtime) = cfg_result
        run_cfg, _rt_notes = _apply_runtime(cfg, runtime)

        route = [x.strip() for x in route_str.split(",") if x.strip()]
        channels = _parse_channels(channels_str)

        if channels == []:
            ch_disp = "全关（历史不参与本次）"
        elif channels is None:
            ch_disp = "全开（content、context、self）"
        else:
            ch_disp = "、".join(channels)

        _mode_disp = {
            "serial": "严格串行",
            "A": "A · 四层独立并行 + 汇流",
            "B": "B · 轮次并行",
                "C": "C · 流水线并行",
                "D": "D · 双起并行 + 撞元并行",
                "E": "E · 双起并行 + 撞元串行",
                "F": "F · 修行先行 + 全流水",
                "G": "G · 修行先行 + 撞毕收元",
                "H": "H · 逐层接力 + 撞元并行",
            "auto": "auto · 自动决策",
        }.get(parallel_str, parallel_str)

        print(f"\n{'═'*60}")
        print(f"元 DGTF v{__version__} · {question}")
        print(f"{'═'*60}")
        print(f"调度：{' → '.join(route)}")
        print(f"螺旋上限（每层圈数）：{rounds_str}")
        print(f"并行模式：{_mode_disp}")
        print(f"回来通道：{ch_disp}")
        print(f"运行期总控：{_runtime_summary_line(run_cfg)}")
        for _n in _rt_notes:
            print(f"  · {_n}")
        print(f"{'═'*60}")

        meta = MetaDGTF(run_cfg)
        try:
            # ★ [EML 记账] 交互模式每题也是**真实一跑** ⇒ 同样显式盖 run_id。
            result = meta.run(question, route=route, keep={},
                              rounds=rounds_str, channels=channels,
                              parallel_mode=parallel_str,
                              run_id=datetime.now().strftime("%Y%m%d_%H%M%S"))
        except Exception as e:
            print(f"\n⚠️ 运行失败：{type(e).__name__}: {e}")
            if not _ask_continue():
                print("已退出。")
                return
            continue

        print(f"\n{'═'*60}")
        print(f"完成 | {result['llm_calls']} 次 LLM | "
              f"{result['llm_tokens']} tokens")
        n_err = sum(len(v.get("errors", []))
                    for v in result["views"].values())
        if n_err:
            print(f"⚠️  {n_err} 条失败记录（已写入输出）")
        print(f"{'═'*60}")
        try:
            save_result(result, run_cfg["output"]["save_dir"])
        except Exception as e:
            print(f"⚠️ 保存失败：{e}")

        if not _ask_continue():
            print("已退出。")
            return


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description=f"元 DGTF v{__version__}")
    parser.add_argument("question", nargs="*", help="问题")
    parser.add_argument("-c", "--config", default="dgtf_config.yaml")
    # default 改 None：**区分「没给」与「显式给了」**，
    #   否则 route 永远无法交给 auto（旧默认值把「没给」伪装成「给了全四层」）。
    parser.add_argument("--route", default=None)
    parser.add_argument("--keep", default="")
    parser.add_argument("--channels", default="")
    parser.add_argument("--rounds", default=None)
    # [fix-105] 默认 None：命令行没给时回落到配置文件的
    # actions.parallel_mode。原来硬编码 default="auto"，配置项形同虚设。
    parser.add_argument("--parallel", default=None,
                        choices=["serial", "A", "B", "C", "D", "E",
                                 "F", "G", "H", "auto"],
                        help="并行模式：serial / A~H / auto"
                             "（不给则用配置 actions.parallel_mode）")
    parser.add_argument("--appendix", default=None,
                        choices=["file", "inline"],
                        help="全量字段附录：file（默认，JSON 外置旁挂文件）"
                             " / inline（旧行为，JSON 内联正文）")
    parser.add_argument("--landing", default="auto",
                        choices=["auto", "boundary", "decision"],
                        help="落地层模板：与取向**解耦**（取向管砍层，"
                             "本项管产物形态）；auto = 按题面分流")
    parser.add_argument("--decidability", default="auto",
                        choices=["auto", "on", "off"],
                        help="可判定性判定：auto = 事实型短题跳过那次外部评估")
    parser.add_argument("--orientation", default="auto",
                        choices=["auto", "boundary", "decision"],
                        help="取向：boundary（要边界清单 → 保留全四层）/ "
                             "decision（要可落地方案 → 允许砍层）/ "
                             "auto（未指定：按题面有无决策语境分流）")
    parser.add_argument("--no-self-check", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--show-ing", action="store_true",
                        help="终端完整显示 ing 输出全文")
    parser.add_argument("--show-view", action="store_true",
                        help="终端完整显示 view 显形全文")
    parser.add_argument("--actions-off", default="",
                        help="关闭的动作，逗号分隔。")
    parser.add_argument("--actions-on", default="",
                        help="开启的动作，逗号分隔。")
    parser.add_argument("--web", default="auto",
                        choices=list(_RUNTIME_SWITCHES),
                        help="联网总开关：auto（按配置）/ on / off")
    parser.add_argument("--thinking", default="auto",
                        choices=list(_RUNTIME_SWITCHES),
                        help="思考总开关：auto（按配置）/ on / off")
    parser.add_argument("--effort", default="auto",
                        choices=list(_RUNTIME_EFFORTS),
                        help="思考强度：auto / low / high / max"
                             "（只在思考开启时生效）")
    args = parser.parse_args()

    for _attr in ("route", "rounds", "channels", "keep"):
        _v = getattr(args, _attr, None)
        if isinstance(_v, str):
            setattr(args, _attr, _normalize_punct(_v))

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for n in ("httpx", "httpxcore", "openai", "urllib3"):
        logging.getLogger(n).setLevel(logging.WARNING)

    cfg = load_config(args.config)
    # default 改 None ⇒ 没给就别写（写 None 会把附录模式打坏）
    if args.appendix:
        cfg.setdefault("actions", {})["appendix_mode"] = args.appendix
    if args.quiet:
        cfg["output"]["verbose"] = False
    # ★ **十一项一次性调度**（显式 ＞ 配置 ＞ auto ＞ 默认）。
    #   命令行「没给」保持 None，调度器才分得清「没给」与「给了」。
    _question = " ".join(args.question)
    _dispatch = auto_dispatch(_question, cfg, explicit={
        "route": args.route,
        "mode": args.parallel, "rounds": args.rounds,
        "mode": args.parallel, "rounds": args.rounds,
        "orientation": args.orientation, "web": args.web,
        "thinking": args.thinking, "effort": args.effort,
        "landing": args.landing, "decidability": args.decidability,
    })
    for _n in _apply_auto_dispatch(cfg, _dispatch):
        print(f"   ✓ 自动调度：{_n}")
    if args.no_self_check:
        cfg["output"]["self_check"] = False
    if args.show_ing:
        cfg["output"]["show_ing"] = True
    if args.show_view:
        cfg["output"]["show_manifest"] = True
    for _name in (args.actions_off or "").split(","):
        _name = _name.strip()
        if _name:
            cfg.setdefault("actions", {})[_name] = False
            print(f"   ✓ 已关闭动作：{_name}")
    for _name in (args.actions_on or "").split(","):
        _name = _name.strip()
        if _name:
            cfg.setdefault("actions", {})[_name] = True
            print(f"   ✓ 已开启动作：{_name}")

    # 运行期三项总控由调度器写进 `cfg["runtime"]`，`_apply_runtime` 是
    # `web_search.enabled` / `api.thinking.*` 的**唯一写入者**（不两处各写）。
    cfg, _rt_notes = _apply_runtime(cfg)
    for _n in _rt_notes:
        print(f"   · {_n}")

    channels = None
    if args.channels:
        raw = [x.strip() for x in args.channels.split(",") if x.strip()]
        if raw == ["none"]:
            channels = []
        else:
            channels = [MemoryChannel.check(x) for x in raw]

    _ri = (_dispatch.get("_items") or {}).get("route") or {}
    if args.route:
        route = [x.strip() for x in _normalize_punct(args.route).split(",")
                 if x.strip()]
    elif _ri.get("source") == "auto":
        route = list(_dispatch.get("route") or [])
        print(f"   · 层集合由 auto 接管：{'、'.join(route)}"
              f"（{_ri.get('reason', '')}）")
    else:
        route = list(_ENTRIES)
    keep = {}
    if args.keep:
        for piece in args.keep.split(","):
            if ":" in piece:
                k, v = piece.split(":", 1)
                keep[k.strip()] = v.strip()

    if not args.question:
        _interactive_run(cfg)
        return

    meta = MetaDGTF(cfg)

    if args.question:
        question = " ".join(args.question)
    else:
        try:
            question = input("你问> ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not question:
            return

    _sus = re.search(
        r"\b(rou[a-zA-Z]{0,5}|route|keep|channels|config|quiet|debug)\b"
        r"\s+[\d:,]",
        question, re.IGNORECASE)
    if _sus:
        print(f"\n⚠️  问题文本里疑似混入命令行参数：{_sus.group(0)!r}")
        print(f"   完整问题 = {question!r}")
        print("   提示：若想传 --rounds，请写完整形式：")
        print('     --rounds "0:2,1:3,both:2,all:2"')
        print("   若这确实是问题的一部分，忽略本提示继续。\n")

    _mi = (_dispatch.get("_items") or {}).get("mode") or {}
    _pm = args.parallel or (str(_dispatch.get("mode") or "")
                            if _mi.get("source") == "auto" else None) \
        or cfg.get("actions", {}).get("parallel_mode", "auto") or "auto"
    _mode_disp = {
        "serial": "严格串行",
        "A": "A · 四层独立并行 + 汇流",
        "B": "B · 轮次并行",
                "C": "C · 流水线并行",
                "D": "D · 双起并行 + 撞元并行",
                "E": "E · 双起并行 + 撞元串行",
                "F": "F · 修行先行 + 全流水",
                "G": "G · 修行先行 + 撞毕收元",
                "H": "H · 逐层接力 + 撞元并行",
        "auto": "auto · 自动决策",
    }.get(_pm, _pm)

    print(f"\n{'═'*60}")
    print(f"元 DGTF v{__version__} · {question}")
    print(f"{'═'*60}")
    print(f"调度：{' → '.join(route)}")
    if keep:
        print(f"保留：{keep}")
    _rp = args.rounds or _dispatch.get("rounds") or "（按各层配置）"
    print(f"螺旋上限（每层圈数）：{_rp}")
    print(f"并行模式：{_mode_disp}"
          f"{'' if args.parallel else '（来自配置）'}")
    ch = channels if channels is not None else cfg["memory"].get(
        "channels", ["content", "context", "self"])
    print(f"回来通道：{'、'.join(ch) if ch else '全关（历史不参与本次）'}")
    print(f"运行期总控：{_runtime_summary_line(cfg)}")
    print(f"{'═'*60}")

    # ★ [EML 记账] CLI 真跑**显式盖 run_id** ⇒ EML 才会把这一跑当真实证据写库。
    #   不加这行，`run()` 拿不到 id ⇒ 撞「无 id 一律不写库」闸 ⇒ **跨跑学习
    #   对真实路径整体失效**（真跑逮到过：`anon_skipped: true`）。测试直接调
    #   `run()` 不给 id ⇒ 仍走匿名跳过 ⇒ 测试隔离不破。
    _run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    result = meta.run(question, route=route, keep=keep,
                      rounds=args.rounds or _dispatch.get("rounds") or 0,
                      channels=channels, parallel_mode=_pm,
                      orientation=args.orientation, auto_plan=_dispatch,
                      run_id=_run_id)

    print(f"\n{'═'*60}")
    print(f"完成 | {result['llm_calls']} 次 LLM | "
          f"{result['llm_tokens']} tokens")
    n_err = sum(len(v.get("errors", []))
                for v in result["views"].values())
    if n_err:
        print(f"⚠️  {n_err} 条失败记录（已写入输出）")
    print(f"{'═'*60}")

    try:
        save_result(result, cfg["output"]["save_dir"])
    except Exception as e:
        print(f"\n⚠️  保存失败：{type(e).__name__}: {e}")
        print("   本次结果**没有落盘**，上面的终端输出是唯一记录。")
        sys.exit(1)


if __name__ == "__main__":
    main()

