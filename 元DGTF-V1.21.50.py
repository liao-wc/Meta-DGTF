#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

元 DGTF · v1.21.52

v1.21.52 相对 v1.21.51 的改动（修 P0/P1 —— 来自四份真实产物的实测证据）：

  [P0-1] _merge_self_text 按层轮转：
           原来是全局 blocks[-keep:]。并行模式下跑得最久的层（all，
           带 all_extra_rounds）最后完成，把其余层的自我记忆全部挤出。
           实测 B 模式两份产物的 self 段 4 条全是「元层」，
           回来通道的 self 只剩一个声部 —— 下一圈展开随之同质化，
           这正是 B-PNP 自省自认「候选 9-15 属补写凑数」的根因。
           改为每层保留 self_layers_per_entry 条，再按 (圈序, 层序) 交错。
           实测：修后 self 段恢复为四层各一条以上。

  [P0-2] 可判定性判定移到 0 层之后（A/B 模式）：
           A/B 原先在开跑前用 _assess_decidability(question) 做纯外部评估，
           判据只有问题字符串本身。实测同一 P=NP：A/B 判 decidable，
           串行判 undecidable —— 串行是对的，它跑完 0 层后用
           _assess_decidability_from_pool_view 读修行层留下的形状。
           A/B 模式下 1 层被迫走可判定通道，覆盖率失去意义
           （P=PN 那份报 1.00）。
           改为：0 层先行串行跑完 → 再判定 → 其余层并行。
           B 模式顺带把 0 层放进第 1 圈的 Jacobi 上游（原来第 1 圈全员无上游）。

  [P1-4] 极性 both 配额 + 强制补裁：
           实测三份产物极性 1 出现 0/0/1 次，both 占绝对多数，
           B-PNP 自省原话「每条 both 只拒绝合并，不判定了什么」。
           both 占比超 spiral.both_quota.max_ratio（默认 0.7）时，
           追加一次调用追问「要裁成 0 或 1 还缺什么」，结果写进
           adjudications[].missing 与 view.both_quota。
           不改裁决本身 —— 那会破坏「未对齐合法」的宪法级约束。

  [P1-5] 自省结论回流（memory.carry_feedback）：
           _self_check 的结果原先只进 md 的自省段落。三份产物的自省
           都精准抓到了「凑数」「ing 复述=True」「可疑 & 全 6 条」，
           然后什么都没发生 —— 花一次调用做质检，结论被丢弃。
           改为把结论翻译成下一圈的约束探针：
             · 可疑候选 → 禁止重述清单
             · ing_rephrased → 要求产出上游没有的句子
             · both_quota.missing → 要求把缺的东西生出来
           并复用已有的「连续复述」停止判据（carry_streak），
           不让空转无限续下去。

  [P1-6] 输入健全性自检（actions.input_sanity）：
           22:50 那次跑的是 P=PN —— PN 不是任何标准复杂度类。
           引擎不知道，把「PN 读法未定」当核心议题跑了 168 次调用。
           宪法允许诚实地说「此处未生」，但不该在第一步就把一个可能
           是笔误的符号当成合法对象收下。
           只报告不改写 —— 替用户改写问题等于替他决定想问什么。

v1.21.51 相对 v1.21.50 的改动（稳定性 + 并行展开）：

  [fix-97] 终端编码兜底：
           导入期即把 stdout/stderr 重配置为 UTF-8（errors=replace）。
           否则在 GBK 终端或 `python x.py > log.txt` 重定向下，
           第一条 emoji 日志就会抛 UnicodeEncodeError 直接崩。

  [fix-98] LLM 截断标志线程隔离：
           last_finish / last_truncated 改为 threading.local 存储，
           _call_long 不再跨线程读到别的层的截断状态
           （v1.21.50 只给计数器加了锁，这两个漏了）。

  [fix-99] self_text 按层隔离（补完设计 9.7 的并发安全清单）：
           并行模式下每层各写 _self_text_by_entry[entry]，
           全部跑完后 _merge_self_text() 合并并截断到 self_layers。
           v1.21.50 里 4 个线程共享一个 list 做 read-modify-write，会丢条目。
           顺带补上 B 模式此前完全没写 self_text 的缺失。

  [fix-100] 池写入加锁：
           新增 MetaDGTF._pool_lock（RLock），覆盖 _apply_view_to_pool /
           self_text 写入 / _totalize_all_pool。

  [fix-101] A 模式汇流不再依赖 route 含 all：
           只要拿到 >=2 份**可用**的上游 view 就跑汇流圈；
           失败占位 View 不再被当成有效上游。
           route 不含 all 时汇流结果入池 + 写进 packed["confluence"] 并落盘。

  [fix-102] B 模式 _b_pre_layer 死代码清理：
           has_zero_prod 恒假导致"修行池内部分解"分支永不执行，
           改为按上游是否就绪真实判断（与 _run_layer 一致）。

  [fix-103] 配置兜底一致化：
           all_extra_rounds 代码兜底 2 → 1（与 DEFAULT_CONFIG 一致）；
           _rounds_plan 尊重 spiral.min_rounds 与 per_entry 覆盖。

  [fix-105] --parallel 不再硬编码 default="auto"：
           命令行不给时回落配置 actions.parallel_mode（原来配置项形同虚设）。

  [perf-104] 阴阳展开并行（设计 9.1 点名的可并行点）：
           阴/阳两次独立 LLM 调用用 ThreadPoolExecutor 并行发出，
           解析仍严格按 order 顺序串行（去重 seen 依赖先后）。
           每层每圈省一次往返。可用 actions.parallel_expand 关闭。

保留 v1.21.50 全部改动（并行模式 A/B/serial/auto）：

  [feat-94] 并行模式三选一 + auto：
            a. 新增 parallel_mode 配置项（serial / A / B / auto）
            b. serial：0→1→both→all 严格串行（原逻辑）
            c. A：四层独立并行 + 汇流圈（用已有 View 补回 both/all 语义）
            d. B：轮次并行（Jacobi，每圈 barrier）
            e. auto：由 MetaDGTF._decide_parallel_mode 按问题性质决定
            f. CLI --parallel 与交互模式询问接入

  [refactor-E] MetaDGTF.run 拆分：
            a. 原 run 主体改名 _run_serial
            b. 新 run 做模式分发
            c. 内嵌 run_layer 闭包提升为 _run_layer 方法
            d. 内嵌 _inp_base/_inp_duel/_inp_meta 提升为 _build_inp_* 方法
            e. 新增 _pack_result / _merge_confluence 辅助

  [fix-95] LLM 计数器加锁：
           total_calls / total_tokens 在并发下用 threading.Lock 保护。

  [fix-96] DGTF._expand_from_question 加 entry 分支：
           A 模式下 both/all 从 question 出发，需要专属 prompt。

保留 v1.21.49 全部改动：
  [fix-90..fix-93] 见 v1.21.49 changelog。

宪法级原则全部保留：
  - 悬置不打分
  - 未对齐合法
  - 停止与清算分开
  - 输入是形状不是数据
  - 失败必须留痕
  - 入池前挡重复
  - 按层覆盖参数
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
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


__version__ = "1.21.52"

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

_STOPWORDS = set(
    "的了是在和与或及之于以及为此则就也都还但而所以因为如果那么这那这些那些"
    "一种一个进行已经可以通过我们你们他们它们什么怎么如何为何哪些这个那个哪个"
)

_ENTRIES = ("0", "1", "both", "all")

_ENTRY_DEPS = {"0": (), "1": (), "both": ("0", "1"), "all": ()}
_ENTRY_MIN_UPSTREAM = {"0": 0, "1": 0, "both": 0, "all": 2}


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

SOFT_TARGET = "这些方面尚未触及，**可参考**，允许完全忽略——继续你的悬置。"
HARD_TARGET = "这些方面尚未触及，**至少涉及其中一项**。"


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


def _all_candidate_drift_rate(candidates):
    if not candidates:
        return 0.0
    markers = (
        "view0", "view1", "view both",
        "两个 view", "两边", "两侧", "上游",
        "对撞层", "研究层", "修行层",
        "多个 view", "三个 view", "四个 view",
    )
    n = 0
    for c in candidates:
        d = str(c.get("desc", ""))
        if any(m in d for m in markers):
            n += 1
    return n / len(candidates)


def _detect_ing_rephrase(ing_text: str,
                         upstream_texts: List[str]) -> Optional[float]:
    """检测 ing 输出是否复述了上游的话。"""
    if not ing_text or not upstream_texts:
        return None
    if ing_text.strip() in ("", "（此处未生）"):
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
            if len(s) >= 12:
                upstream_sents.append(s)
    if not upstream_sents:
        return None
    hits = 0
    for s in ing_sents:
        if any(_similar(s, u, 0.75) for u in upstream_sents):
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


# ============================================================
# v1.19 主动悬置：生命周期
# ============================================================
SUSPENSION_STATUS = ("active", "stable", "resolved", "revoked")
SUSPENSION_REASON_TYPES = ("explicit", "intuitive")


def _same_batch(a: List[str], b: List[str], thr: float) -> bool:
    if not a or not b:
        return False
    m = sum(1 for t in a if any(_similar(t, u, 0.85) for u in b))
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
    "plain_speak": "plain_speak",
    "summarize_views": "layer_summary",
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
             "resolved": 0, "stable": 0}
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
        if x["id"] in ok_ids or any(_similar(x["target"], t, 0.85)
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
            if x["id"] == sid or (tgt and _similar(x["target"], tgt, 0.85)):
                x["status"] = "revoked"
                x["revoked_at"] = layer
                x["revoke_reason"] = str(r.get("reason", ""))[:200]
                stats["revoked"] += 1

    eng = [str(e.get("target", "")) for e in (view.engagements or [])]
    for x in pool.suspensions:
        if x["status"] not in ("active", "stable"):
            continue
        if any(_similar(x["target"], e, 0.8) for e in eng if e):
            x["status"] = "resolved"
            x["resolved_at"] = layer
            stats["resolved"] += 1

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


def _valid_revisit(cond: str) -> bool:
    c = (cond or "").strip()
    if len(c) < 4:
        return False
    return not any(b in c for b in _BAD_REVISIT)


def coverage_of(pool, cfg: dict) -> Optional[float]:
    """可判定覆盖率。"""
    subs = [s for s in pool.sub_questions
            if s.get("decidability") == "decidable"]
    if not subs:
        return None
    tot = sum(float(s.get("weight", 1.0)) for s in subs)
    if tot <= 0:
        return None
    cov = 0.0
    deferred_ids = {d.get("sub_id") for d in pool.deferrals
                    if d.get("status") == "deferred"}
    for s in subs:
        w = float(s.get("weight", 1.0))
        if s.get("status") == "answered":
            try:
                depth = float(s.get("depth", 1.0))
            except (TypeError, ValueError):
                depth = 1.0
            depth = max(0.0, min(1.0, depth))
            cov += w * depth
        elif s.get("id") in deferred_ids:
            cov += w * 0.2
    return cov / tot


def deferred_ratio_of(pool) -> float:
    subs = [s for s in pool.sub_questions
            if s.get("decidability") == "decidable"]
    if not subs:
        return 0.0
    deferred_ids = {d.get("sub_id") for d in pool.deferrals
                    if d.get("status") == "deferred"}
    n = sum(1 for s in subs if s.get("id") in deferred_ids)
    return n / len(subs)


def update_deferrals(pool, view, layer: int, cfg: dict) -> dict:
    """研究层延迟债务更新 + refinement 记录。"""
    stats = {"new": 0, "confirmed": 0, "handled": 0,
             "escalated": 0, "answered": 0, "invalid": 0,
             "refined": 0}
    sub_by_id = {s.get("id"): s for s in pool.sub_questions}

    for e in (view.escalations or []):
        sid = e.get("sub_id")
        sq = sub_by_id.get(sid)
        if sq is None or sq.get("decidability") == "undecidable":
            continue
        frm = sq.get("decidability", "decidable")
        sq["decidability"] = "undecidable"
        pool.escalations.append({
            "sub_id": sid, "question": sq.get("question", ""),
            "from": frm, "to": "undecidable", "layer": layer,
            "reason": str(e.get("reason", ""))[:200],
            "note": "立刻挪、单向不可逆（蓝图 §二）",
        })
        stats["escalated"] += 1
        for d in pool.deferrals:
            if d.get("sub_id") == sid and d.get("status") == "deferred":
                d["status"] = "escalated"
                d["resolved_at"] = layer
                d["resolution_reason"] = "因分类变更（escalation）"

    for d in (view.deferrals or []):
        sid = d.get("sub_id")
        sq = sub_by_id.get(sid)
        if sq is None:
            continue
        cond = str(d.get("revisit_condition", "")).strip()
        if not _valid_revisit(cond):
            stats["invalid"] += 1
            continue
        reason = str(d.get("reason", "")).strip()
        if len(reason) < 4:
            stats["invalid"] += 1
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
    for pt, pd in p_aspects:
        if not pt:
            continue
        for i, (rt, rd) in enumerate(r_aspects):
            if i in used_r or not rt:
                continue
            if _similar(pt, rt, 0.7):
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
                })
                break

    p_n = len([1 for pt, _ in p_aspects if pt])
    r_n = len([1 for rt, _ in r_aspects if rt])
    denom = max(p_n, r_n, 1)
    match_rate = len(quadrants) / denom

    if match_rate < 0.1:
        quality = "unaligned"
    elif match_rate < 0.3:
        quality = "low"
    else:
        quality = "ok"

    quadrants.sort(key=lambda x: _QUADRANT_ORDER.index(x["quadrant"]))

    return {"quality": quality, "match_rate": round(match_rate, 3),
            "quadrants": quadrants}


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
             "resolved": 0, "stable": 0, "adjudicated": 0}
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
            if x["id"] == sid or (tgt and _similar(x["target"], tgt, 0.85)):
                x["status"] = "revoked"
                x["revoked_at"] = layer
                x["revoke_reason"] = str(r.get("reason", ""))[:200]
                stats["revoked"] += 1

    adj = [str(a.get("tension", "")) for a in (view.adjudications or [])]
    for x in pool.duel_suspensions:
        if x["status"] not in ("active", "stable"):
            continue
        if any(_similar(x["target"], a, 0.8) for a in adj if a):
            x["status"] = "resolved"
            x["resolved_at"] = layer
            stats["resolved"] += 1

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
        w0 = e.get("why_0", "") or ""
        w1 = e.get("why_1", "") or ""
        if not w0 or not w1:
            return 0.0
        return min(len(w0), len(w1)) / max(len(w0), len(w1), 1)

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
    distance_to_question: float = 1.0
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
    settlement: dict = field(default_factory=dict)
    adjudications: List[dict] = field(default_factory=list)
    both_quota: dict = field(default_factory=dict)  # [P1-4]
    carry: List[dict] = field(default_factory=list)  # [P1-5]
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

    quality_flags: List[str] = field(default_factory=list)
    quality_verdict: str = ""
    self_check: dict = field(default_factory=dict)

    errors: List[str] = field(default_factory=list)

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
                lines.append(f"  - {u.get('desc', '')}")
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
        return asdict(self)


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
            if any(_similar(it["text"], t, 0.75) for t in picked_texts):
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
    return [p["raw"] for p in picked[:n]]


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
    duel_suspensions: List[dict] = field(default_factory=list)
    duel_alignment: dict = field(default_factory=dict)
    engagements: List[dict] = field(default_factory=list)
    refinements: List[dict] = field(default_factory=list)
    decidable_channel: dict = field(default_factory=dict)
    undecidable_channel: dict = field(default_factory=dict)

    def merge(self, amps, threads, meta, probes=None, suspensions=None):
        for a in amps:
            if not any(_similar(a.get("desc", ""), x.get("desc", ""), 0.9)
                       for x in self.amps):
                self.amps.append(a)
        for t in threads:
            if not any(_similar(t.get("desc", ""), x.get("desc", ""), 0.9)
                       for x in self.threads):
                self.threads.append(t)
        for p in (probes or []):
            q = str(p.get("question", "")).strip()
            if q and not any(_similar(q, x.get("question", ""), 0.9)
                             for x in self.probes):
                self.probes.append(p)
        for m in meta:
            if m and m not in self.meta:
                self.meta.append(m)
        for s in (suspensions or []):
            t = str(s.get("target", "")).strip()
            if not t:
                continue
            if any(_similar(t, x.get("target", ""), 0.85)
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

    def add_undecidable(self, product: dict,
                        und_aspects: Optional[List[str]] = None):
        if not self.undecidable_channel:
            self.undecidable_channel = {
                "structural_amps": [], "clarity_history": [],
                "last_clarity": 0.0,
                "und_aspects": [], "struct_coverage_history": [],
                "last_struct_coverage": 0.0,
                "aligned_amps": [], "last_struct_hit": 0,
            }
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
        for sa in (product.get("structural_amps") or []):
            s = str(sa).strip()
            if s and not any(_similar(s, x, 0.85)
                             for x in self.undecidable_channel["structural_amps"]):
                self.undecidable_channel["structural_amps"].append(s[:200])
        for sa in (product.get("aligned_amps") or []):
            s = str(sa).strip()
            if s and not any(_similar(s, x, 0.85)
                             for x in self.undecidable_channel["aligned_amps"]):
                self.undecidable_channel["aligned_amps"].append(s[:200])
        aspects = self.undecidable_channel.get("und_aspects", [])
        if aspects:
            covered = sum(
                1 for asp in aspects
                if any(_overlap_coef(asp, sa) >= 0.3
                       for sa in self.undecidable_channel["structural_amps"])
            )
            struct_cov = covered / len(aspects)
            self.undecidable_channel["last_struct_hit"] = covered
        else:
            struct_cov = 0.0
            self.undecidable_channel["last_struct_hit"] = 0
        self.undecidable_channel["struct_coverage_history"].append(struct_cov)
        self.undecidable_channel["last_struct_coverage"] = struct_cov

    def to_dict(self) -> dict:
        return {"amps": self.amps, "threads": self.threads,
                "probes": self.probes, "meta": self.meta,
                "suspensions": self.suspensions,
                "sub_questions": self.sub_questions,
                "deferrals": self.deferrals,
                "escalations": self.escalations,
                "duel_suspensions": self.duel_suspensions,
                "duel_alignment": self.duel_alignment,
                "engagements": self.engagements,
                "refinements": self.refinements,
                "decidable_channel": self.decidable_channel,
                "undecidable_channel": self.undecidable_channel}


@dataclass
class Input:
    question: Optional[str] = None
    root_question: Optional[str] = None
    upstream_views: List[View] = field(default_factory=list)
    upstream_pools: List[Pool] = field(default_factory=list)
    upstream_untouched: List[List[dict]] = field(default_factory=list)
    seed_probes: List[dict] = field(default_factory=list)
    context: str = ""
    self_memory: str = ""
    key_terms: List[str] = field(default_factory=list)
    round_role: str = ""
    round_no: int = 0

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
        self.max_retries = int(api_cfg.get("max_retries", 3))
        self.backoff = float(api_cfg.get("retry_backoff", 1.8))
        self.total_calls = 0
        self.total_tokens = 0
        # [fix-98] 上一次调用的 finish_reason / 截断标志必须是**线程局部**的。
        # 并行模式 A/B 下 4 个线程共用同一个 LLM 实例，实例属性会让
        # _call_long 读到别的层刚写入的 truncated，误判续跑。
        self._tls = threading.local()
        self._lock = threading.Lock()  # v1.21.50 并发计数锁

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

    @staticmethod
    def _is_reasoner(name: str) -> bool:
        n = (name or "").lower()
        return "reasoner" in n or "-r1" in n or "reasoning" in n

    def call(self, system, user, temperature=0.6, max_tokens=3000,
             json_mode=False, model=None):
        model = model or self.default_model
        is_r = self._is_reasoner(model)
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
        }
        if not is_r:
            kwargs["temperature"] = temperature
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
        if json_mode:
            system += "\n\n【重要】只输出一个合法 JSON 对象。"
            if is_r:
                system += "\n【再次强调】必须能被 json.loads 直接解析。"
            kwargs["messages"][0]["content"] = system
        if is_r:
            kwargs["max_tokens"] = max(max_tokens, 32000)

        # [fix-98] 这两个现在写进线程局部存储，不是实例属性
        # [fix-98] 这两个现在写进线程局部存储，不是实例属性
        self.last_finish = None
        self.last_truncated = False
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.client.chat.completions.create(**kwargs)
                ch = resp.choices[0]
                usage = getattr(resp, "usage", None)
                if usage:
                    with self._lock:
                        self.total_tokens += (
                            getattr(usage, "total_tokens", 0) or 0)
                with self._lock:
                    self.total_calls += 1
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
        self.sp = sp if sp is not None else _spiral_for(config, entry)

    def vp(self, *args):
        if self.verbose:
            print(*args)

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

    def _assess_decidability(self, question: str) -> dict:
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

【可判定的特征（满足任一项）】
1. 可通过操作化定义转化为可测命题
2. 有明确的判决实验
3. 是经验问题或定义问题

【★ 关键原则】
- 若问题同时含可判定和不可判定子问题，必判 partial
- 必须同时列出 decidable_aspects 和 undecidable_aspects（可空）

严格 JSON：
{
  "decidability": "decidable|partial|undecidable",
  "reason": "80字内",
  "features": ["命中的特征，最多3条"],
  "decidable_aspects": ["可判定的方面，最多5条"],
  "undecidable_aspects": ["不可判定的方面，最多5条"]
}
"""
        try:
            raw = self.llm.call(system, f"【问题】\n{question}",
                                0.2, 1100, json_mode=True)
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
        if status == "decidable" and und_aspects:
            status = "partial"
        if status == "undecidable" and dec_aspects:
            status = "partial"
        if status == "partial" and not und_aspects and not dec_aspects:
            status = "decidable"
        if dec_aspects and und_aspects:
            status = "partial"
        if status != original_status:
            logger.info("可判定性 sanity check：%s → %s",
                        original_status, status)

        return {"decidability": status,
                "reason": str(data.get("reason", ""))[:200],
                "features": _list("features"),
                "decidable_aspects": dec_aspects,
                "undecidable_aspects": und_aspects,
                "_original_status": original_status}

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
        if pool.undecidable_channel.get("last_struct_coverage"):
            bits.append(f"  📘 不可判定结构覆盖 "
                        f"{pool.undecidable_channel['last_struct_coverage']:.2f}")
        body = "\n".join(bits)
        return f"{label}\n{body}" if body else f"{label}\n（空）"

    def _call_long(self, system, user, temperature, max_tokens,
                   model=None, max_cont: int = 2) -> Tuple[str, bool]:
        text = self.llm.call(system, user, temperature, max_tokens,
                             model=model)
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
                                     max_tokens, model=model)
            except Exception as e:
                logger.warning("续跑失败: %s", e)
                break
            if not more.strip():
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
            view.anchor, anchor_untouched = self._re_anchor(inp)
        else:
            if self.entry in ("both", "all") and inp.root_question:
                view.anchor = inp.root_question.strip()
            elif inp.is_base:
                view.anchor = (inp.question or "")[:120]
            else:
                view.anchor = (inp.root_question or "")[:120]
            anchor_untouched = []
            self.vp("   🪞 锚点重述：已关闭（用透传/原文）")
        tag = "透传" if (self.entry in ("both", "all")
                        and inp.root_question) else "重述"
        self.vp(f"\n🪞 [锚点·{tag}] {view.anchor}")

        for u in anchor_untouched:
            view.untouched.append({"desc": u, "source": "anchor"})

        # 第 2 步：阴阳展开
        candidates = self._expand(inp, pool, view.anchor)
        try:
            view._expanded_descs = [
                str(getattr(c, "desc", "") or "").strip()
                for c in candidates
            ]
        except Exception:
            pass
        self.vp(f"   📋 展开候选 {len(candidates)} 条")
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

        for c in candidates:
            if c.position == "0" and c.desc.strip():
                if not any(_similar(c.desc, x.get("desc", ""), 0.85)
                           for x in view.untouched):
                    view.untouched.append({"desc": c.desc, "source": "judge"})

        # 第 4 步：ing 对撞
        if _action_on(self.config, "ing"):
            try:
                view.collision = self._ing(candidates, inp, view.anchor, view)
                self.vp(f"   🔥 ing 输出 {len(view.collision)} 字")
                _upstream_texts: List[str] = []
                for _v in (inp.upstream_views or []):
                    _m = getattr(_v, "manifest", "") or ""
                    _c = getattr(_v, "collision", "") or ""
                    if _m:
                        _upstream_texts.append(_m)
                    if _c:
                        _upstream_texts.append(_c)
                for _c in (candidates or []):
                    _d = str(getattr(_c, "desc", "") or "").strip()
                    if _d:
                        _upstream_texts.append(_d)
                if _upstream_texts:
                    _rr = _detect_ing_rephrase(
                        view.collision, _upstream_texts)
                    if _rr is not None:
                        try:
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
            try:
                view.distance_to_question = float(
                    extra.get("distance_to_question", 1.0))
            except (TypeError, ValueError):
                view.distance_to_question = 1.0
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

        # 第 6 步：探针回归
        if _action_on(self.config, "phase_probe"):
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
            view.probes = []
            self.vp("   🌱 探针回归：已关闭")

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

        return view

    # ---------- 锚点重述 ----------
    def _re_anchor(self, inp: Input):
        if self.entry in ("both", "all") and inp.root_question:
            return inp.root_question.strip(), []

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
            "同时，列出这个问题里**还没被触及、还没被展开**的方面（0-4 条）。\n"
            "严格 JSON：\n"
            '{"anchor":"≤80字一句话","untouched":["≤30字的方面"]}\n'
            + ANTI_PRETTY
            + self._self_block()
        )
        dec_block = self._decidability_block(inp)
        user = f"【输入】\n{base}\n{dec_block}\n\n【上下文】\n{ctx}"
        try:
            raw = self.llm.call(system, user, 0.3, 400, json_mode=True)
            data = self.llm.parse_json(raw) or {}
            anchor = str(data.get("anchor", "")).strip()
            untouched = [str(x).strip()[:60]
                         for x in data.get("untouched", [])
                         if str(x).strip()]
            if not anchor:
                anchor = raw.strip().split("\n")[0][:120]
            return anchor, untouched
        except Exception:
            return base[:120], []

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
            jobs.append((label, prompt, build_user(label)))
        if not jobs:
            return []

        raws: Dict[str, Optional[str]] = {}
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
            self.vp(f"   {raw[:200]}")
            for line in raw.splitlines():
                c = self._parse_candidate_line(line)
                if not c:
                    continue
                if any(_similar(c.desc, s, 0.85) for s in seen):
                    continue
                seen.append(c.desc)
                c.source = label
                out.append(c)
        return out

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
            jobs.append((label, prompt, build_user(label)))
        if not jobs:
            return []

        raws: Dict[str, Optional[str]] = {}
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
            self.vp(f"   {raw[:200]}")
            for line in raw.splitlines():
                c = self._parse_candidate_line(line)
                if not c:
                    continue
                if any(_similar(c.desc, s, 0.85) for s in seen):
                    continue
                seen.append(c.desc)
                c.source = label
                out.append(c)
        return out

    @staticmethod
    def _role_text(role: str, round_no: int = 0) -> str:
        if not role:
            return ""
        body = {
            "摊开": "这是本层的**第 1 轮 · 摊开**：先别急着深入，把能看见的面铺开。"
                    "广度优先——能摆出来的都摆出来，不必每条都追到底。",
            "深入": "这是本层的**深入轮**：面已经铺过，这一轮往里走。"
                    "带着上面给出的重点往深里去，不要重铺一遍已经铺过的面。",
            "收束": "这是本层的**收束轮**：不再开新面。把已经走到的收拢成形，"
                    "能定下来的定下来，开不了的就如实说此处未生。",
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

    def _expand_from_question(self, question, pool, anchor,
                              seeds=(), role="", round_no=0,
                              inp=None) -> List[Candidate]:
        # v1.21.50：entry 分支，选专属 prompt
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

        def build_user(label):
            return (
                f"【原始问题】\n{question}\n\n"
                f"【锚点重述】\n{anchor}\n"
                f"{self._role_text(role, round_no)}\n"
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

        def build_user(label):
            return (
                f"{anchor_block}\n"
                f"{self._role_text(role, round_no)}\n"
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
            "输出 0-8 条。如果没有值得显形的候选，就只输出一行：'（无）'\n"
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
            "输出 0-8 条。如果没有值得显形的候选，就只输出一行：'（无）'\n"
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
            "输出 0-8 条。如果没有值得显形的候选，就只输出一行：'（无）'\n"
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
            "输出 0-8 条。如果没有值得显形的候选，就只输出一行：'（无）'\n"
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
            "输出 0-8 条。如果没有值得显形的候选，就只输出一行：'（无）'\n"
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
            "输出 0-8 条。如果没有值得显形的候选，就只输出一行：'（无）'\n"
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
        if desc.count("?") > 2 or desc.count("...") > 1:
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
            "严格 JSON：\n" + schema
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
            raw = self.llm.call(system, user, 0.3, 3000, json_mode=True)
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
                                      json_mode=True)
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
                                              json_mode=True)
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

        if hit < n and view is not None:
            view.add_error(
                "对偶判断",
                f"只命中 {hit}/{n} 条，其余 {n - hit} 条保留默认值 0/0，"
                f"不是真实判断结果")
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
                self.vp(f"   [{i}] {c.desc[:50]}")
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
            cdicts = _tighten_both(cdicts, max_ratio=0.3)
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
        else:
            object_desc = "整体与每一个局部"

        if inp.is_base:
            speech_text = ""
        elif self.entry == "both":
            intro = "以下是要相撞的两端各自说过的话：\n\n"
            speech_text = (intro
                           + "\n\n".join(View.speech_of(v)
                                         for v in inp.upstream_views))
        else:
            intro = "以下是这个整体所包含的各个局部说过的话：\n\n"
            speech_text = (intro
                           + "\n\n".join(View.speech_of(v)
                                         for v in inp.upstream_views))

        _fix83_block = ""
        if self.entry == "both":
            _fix83_block = (
                "\n【★ v1.21.46 硬约束 · 对撞层专用】\n"
                "本次对撞的输出里，每一句话都必须包含两个 view "
                "都没有单独说过的话。\n"
                "禁止逐句复述上游 view 的 manifest / collision。\n"
                "若发现自己在重复上游的话，立刻停笔，改写成对撞新生成的句子。\n"
                "宁可短，也不要复述。\n"
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
                system, user, 0.7, 4000, model=self.llm.reasoner_model)
            if trunc and view is not None:
                view.add_error(
                    "ing", RuntimeError(
                        "输出被长度掐断，续跑后仍未走完六步；"
                        "下游读到的可能是残篇"))
                self.vp("   ✗ ing 输出仍被截断——本层是残篇，不是完整对撞")
            return text
        except Exception as e:
            msg = f"ing(reasoner) 失败：{type(e).__name__}: {e}"
            logger.warning(msg)
            if view is not None:
                view.add_error("ing/reasoner", e)
            self.vp("   ⚠️ reasoner 失败，降级到 chat 模型重试")
            try:
                text, trunc = self._call_long(system, user, 0.7, 4000)
                if view is not None:
                    view.errors.append("ing 已降级为 chat 模型产出")
                    if trunc:
                        view.add_error(
                            "ing", RuntimeError(
                                "降级后输出仍被长度掐断；本层是残篇"))
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
                        if s.get("decidability") in ("decidable", "partial")]
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
                '    "distance": 0.0-1.0\n'
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
        else:
            system = (
                "你处于【& · 阴阳结合】。\n"
                "从 ing 输出里沉淀出'撞不开'的东西。\n"
                f"【本层侧重】{self.phase.he_focus}\n"
                "两个 view 共同绕开、都没碰到的盲区不是 &，归到线头。\n"
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
            amps.append({"desc": desc, "type": t, "source": self.entry,
                         "polarity": "?"})

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

            try:
                d2q = float(data.get("distance_to_question", 1.0))
            except (TypeError, ValueError):
                d2q = 1.0
            extra = {
                "decidable_product": dec_norm,
                "undecidable_product": und_norm,
                "distance_to_question": max(0.0, min(1.0, d2q)),
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
{"sub_questions": [{"id": 1, "question": "...", "weight": 0.5, "decidability": "decidable|undecidable"}]}
""" + ANTI_PRETTY + self._self_block()
        user = (f"【原始问题】\n{question}\n\n"
                f"【评估阶段识别的可判定方面】\n{dec_hint}\n\n"
                f"【评估阶段识别的不可判定方面】\n{und_hint}")
        try:
            raw = self.llm.call(system, user, 0.3, 1300, json_mode=True)
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
{"sub_questions": [{"id": 1, "question": "...", "weight": 0.5, "decidability": "decidable|undecidable"}]}
""" + ANTI_PRETTY + self._self_block()
        user = (f"【原始问题】\n{question}\n\n"
                f"【评估阶段识别的可判定方面】\n{dec_hint}\n\n"
                f"【评估阶段识别的不可判定方面】\n{und_hint}")
        try:
            raw = self.llm.call(system, user, 0.3, 1300, json_mode=True)
        except Exception as e:
            logger.warning("混合问题分解失败: %s", e)
            return []
        subs = self._parse_subs(raw, default_decidability="decidable")
        return self._ensure_undecidable_subs(subs, und_aspects)

    def _decompose_koan(self, question) -> List[dict]:
        system = """你是【不可判定结构拆解者】。
把一个不可判定问题拆解成 3-6 个维度。
严格 JSON：
{"dimensions": [{"id": 1, "dimension": "...", "why_undecidable": "...", "what_can_probe": "..."}]}
""" + ANTI_PRETTY + self._self_block()
        try:
            raw = self.llm.call(system, f"【原始问题】\n{question}",
                                0.3, 1100, json_mode=True)
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
            if dec not in ("decidable", "undecidable"):
                dec = default_decidability
            out.append({"id": sid, "question": q[:200], "weight": w,
                         "decidability": dec, "status": "open",
                         "depth": 1.0})
            if len(out) >= 7:
                break
        return out

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
            '      "decidability": "decidable|undecidable",\n'
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
        )

        try:
            raw = self.llm.call(system, user, 0.3, 1600, json_mode=True)
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
            if dec not in ("decidable", "undecidable"):
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

        for s in out:
            self.vp(f"      · [{s['decidability']}] {s['question'][:50]}"
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
                if s.get("decidability") in ("decidable", "partial")]
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

        system = (
            "你是【探针 · 自问】阶段（研究层）。\n"
            "你正在为回答【原始问题】而生发探针，并决定这一层「先处理什么、暂缓什么」。\n"
            "探针从上面**没消化完的东西**里生发，但**必须指向原始问题**。\n"
            f"{self.phase.probe_focus}\n"
            "1. 生成 1-3 个探针，每个给 expected_gain（0.0-1.0）和 link（怎么带回去）\n"
            "2. 每条探针必须用 covers 声明它碰了下方【本层未触及项】里的哪几项，\n"
            "   用编号引用（如 [\"T1\", \"T3\"]）。一条都没碰就填 []。\n"
            "   不要为了通过检查而乱填——covers 反映的是你这条探针的真实意图。\n"
            "3. 推不动就让 probes 返回空数组——宁可空，不要凑数\n"
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
            "7. escalations：只写\"本圈发现它其实不可判定\"的子问题。\n"
            "   ★ 已经是 undecidable 的子问题**不要再写**——系统会跳过并打日志。\n"
            "严格 JSON：\n"
            '{"probes":[{"question":"≤60字","link":"≤40字",'
            '"expected_gain":0.6,"covers":["T1"]}],'
            '"engagements":[{"sub_id":1,"how":"≤40字","depth":0.7}],'
            '"deferrals":[{"sub_id":3,"reason":"≤40字",'
            '"revisit_condition":"≤30字"}],'
            '"reconfirmations":[{"deferral_id":"d_001","reason":"≤30字"}],'
            '"resolutions":[{"deferral_id":"d_002","how":"≤40字"}],'
            '"escalations":[{"sub_id":5,"reason":"≤40字"}]}\n'
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
        )
        if deferred_ratio_of(pool) > 0.6 and open_def:
            user += (
                "\n⚠️ 反躺平：当前延迟债务占比已超过 0.6，本层**必须**至少清偿\n"
                "一个延迟债务（写进 resolutions，或 engagements 回答对应子问题）。\n"
            )

        raw = self.llm.call(system, user, 0.5, 1900, json_mode=True)
        data = self.llm.parse_json(raw) or {}

        out: List[dict] = []
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
            if not q or len(q) < 6 or not link or gain < min_gain:
                continue
            covers_raw = p.get("covers") or []
            covers: List[str] = []
            if isinstance(covers_raw, list):
                for c in covers_raw:
                    s = str(c).strip()
                    if s:
                        covers.append(s[:40])
            out.append({"question": q, "link": link,
                        "expected_gain": round(gain, 2),
                        "covers": covers})

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
                    "reason": str(e.get("reason", "")).strip()[:200]})

        out.sort(key=lambda x: -x["expected_gain"])
        out = out[:3]
        for p in out:
            self.vp(f"   🌱 {p['question']}")
            self.vp(f"      ↩ 回来：{p['link']}｜增益{p['expected_gain']}")
            if "covers" in p:
                self.vp(f"      ✓ covers={p['covers']}")
        for e in view.engagements:
            self.vp(f"   🤝 推进：子问题[{e['sub_id']}] {e['target'][:40]}（{e['how']}）")
        for d in view.deferrals:
            self.vp(f"   ⏳ 延迟意图：子问题[{d['sub_id']}]"
                    f"（回访条件：{d['revisit_condition']}）")
        for r in view.reconfirmations:
            self.vp(f"   ✓ 确认债务：{r['deferral_id']}")
        for r in view.resolutions:
            self.vp(f"   ✔ 清偿：{r['deferral_id']}")
        for e in view.escalations:
            sq = sub_by_id.get(e['sub_id'])
            if sq is not None and sq.get("decidability") == "undecidable":
                self.vp(f"   · 子问题[{e['sub_id']}] 已是不可判定，"
                        f"跳过重复升级")
                continue
            self.vp(f"   ⬆ 升级为不可判定：子问题[{e['sub_id']}]（{e['reason']}）")

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

        raw = self.llm.call(system, user, 0.5, 1900, json_mode=True)
        data = self.llm.parse_json(raw) or {}

        out: List[dict] = []
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
        for v in (inp.upstream_views or []):
            if getattr(v, "entry", "") == "both":
                duel_tensions = [s for s in (v.duel_suspensions or [])
                                 if s.get("status") in ("active", "stable")]
                break
        tension_text = "\n".join(
            f"  - [{s.get('quadrant', '') or '?'}] {s.get('target', '')}"
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

        system = (
            "你是【探针 · 自问】阶段（元层）。\n"
            "你面对三个子层已经各自处理完的东西，"
            "要做的是**元决策**：哪一类张力，我决定不消解。\n"
            f"{self.phase.probe_focus}\n"
            "1. probes：1-3 个探针，各给 question/link/expected_gain。\n"
            "2. engagements：**至少碰一个**。元层的「碰」= 对某类张力做出裁决。\n"
            "3. suspensions：把「决定不消解的张力类别」写在这里。\n"
            "   允许 reason_type=intuitive。\n"
            "4. reconfirmations / revocations：对【元层之前的悬置决定】的回应。\n"
            "严格 JSON：\n"
            '{"probes":[{"question":"≤60字","link":"≤40字","expected_gain":0.6}],'
            '"engagements":[{"target":"≤30字","how":"≤40字"}],'
            '"suspensions":[{"target":"≤30字","reason":"≤40字",'
            '"reason_type":"explicit|intuitive"}],'
            '"reconfirmations":[{"suspension_id":"s_001","reason":"≤30字"}],'
            '"revocations":[{"suspension_id":"s_002","reason":"≤40字"}]}\n'
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
        )

        raw = self.llm.call(system, user, 0.5, 1900, json_mode=True)
        data = self.llm.parse_json(raw) or {}

        out: List[dict] = []
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
            if not q or len(q) < 6 or not link or gain < min_gain:
                continue
            out.append({"question": q, "link": link,
                        "expected_gain": round(gain, 2)})

        for e in (data.get("engagements") or []):
            if not isinstance(e, dict):
                continue
            t = str(e.get("target", "")).strip()[:80]
            if not t:
                continue
            view.engagements.append(
                {"target": t, "how": str(e.get("how", "")).strip()[:160]})

        for s in (data.get("suspensions") or []):
            if not isinstance(s, dict):
                continue
            t = str(s.get("target", "")).strip()[:120]
            if not t:
                continue
            rt = str(s.get("reason_type", "explicit")).lower()
            if rt not in SUSPENSION_REASON_TYPES:
                rt = "explicit"
            view.suspensions.append({
                "target": t,
                "reason": str(s.get("reason", "")).strip()[:200],
                "reason_type": rt,
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
            "8. suspensions：把「看清了、可以碰、但决定不碰」的点写在这里。\n"
            "9. reconfirmations / revocations：对【上一层的悬置决定】的回应。\n"
            "严格 JSON：\n"
            '{"probes":[{"question":"≤60字","link":"≤40字",'
            '"expected_gain":0.6,"covers":["T1"]}],'
            '"engagements":[{"target":"≤30字","how":"≤40字"}],'
            '"suspensions":[{"target":"≤30字","reason":"≤40字",'
            '"reason_type":"explicit|intuitive"}],'
            '"reconfirmations":[{"suspension_id":"s_001","reason":"≤30字"}],'
            '"revocations":[{"suspension_id":"s_002","reason":"≤40字"}]}\n'
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

        raw = self.llm.call(system, user, 0.5, 1900, json_mode=True)
        data = self.llm.parse_json(raw) or {}

        out: List[dict] = []
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
            if not q or len(q) < 6 or not link:
                continue
            if gain < min_gain:
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
                self.vp("      [fix-89 diag] 探针 covers 字段缺失"
                        "（模型未输出）")
            elif not isinstance(covers_raw, list):
                self.vp(f"      [fix-89 diag] 探针 covers 类型非 list："
                        f"{type(covers_raw).__name__}="
                        f"{covers_raw!r}")
            elif _show_diag:
                self.vp(f"      [fix-89 diag] 探针 covers_raw="
                        f"{covers_raw} → parsed={covers}")
            out.append({"question": q, "link": link,
                        "expected_gain": round(gain, 2),
                        "covers": covers})

        for e in (data.get("engagements") or []):
            if not isinstance(e, dict):
                continue
            t = str(e.get("target", "")).strip()[:80]
            if not t:
                continue
            view.engagements.append(
                {"target": t, "how": str(e.get("how", "")).strip()[:160]})

        for s in (data.get("suspensions") or []):
            if not isinstance(s, dict):
                continue
            t = str(s.get("target", "")).strip()[:120]
            if not t:
                continue
            rt = str(s.get("reason_type", "explicit")).lower()
            if rt not in SUSPENSION_REASON_TYPES:
                rt = "explicit"
            view.suspensions.append({
                "target": t,
                "reason": str(s.get("reason", "")).strip()[:200],
                "reason_type": rt,
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
        for p in out:
            self.vp(f"   🌱 {p['question']}")
            self.vp(f"      ↩ 回来：{p['link']}｜增益{p['expected_gain']}")
            _cov = p.get("covers") or []
            if _cov:
                self.vp(f"      ✓ covers={_cov}")
            else:
                self.vp(f"      ✗ covers=（空，模型未输出或输出为空）")
        for e in view.engagements:
            self.vp(f"   🤝 碰了：{e['target']}（{e['how']}）")
        for s in view.suspensions:
            self.vp(f"   ⏸ 悬置：{s['target']}（{s['reason'] or '直觉，无理由'}）")
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
                       round_no: int = 0) -> List[str]:
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
                    if not any(_similar(d, x, 0.60)
                               for x in _expanded_descs if x):
                        _unmatched += 1
                if _total > 0:
                    _r = _unmatched / _total
                    if _r >= 0.5:
                        flags.append(
                            f"candidates_backfilled({_r:.0%})")
        _ing_rr = getattr(view, "_ing_rephrase_ratio", 0.0)
        if _ing_rr >= 0.5:
            flags.append(f"ing_rephrased_direct({_ing_rr:.0%})")
        dims = ("position",)
        for dim in dims:
            vals = [c.get(dim, "0") for c in view.candidates]
            if vals and len(set(vals)) == 1:
                if dim == "position":
                    div = self._why_position_diversity(view.candidates)
                    if div >= 0.4:
                        flags.append(f"{dim}_all_same_structural")
                    else:
                        flags.append(f"{dim}_all_same")
                    dumped = self._dump_position_diagnostic(
                        view, view.anchor, round_no)
                    if dumped:
                        logger.info("position 诊断已写：%s", dumped)
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
            if vals and vals.count("both") / len(vals) > 0.6:
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
            if overlap / len(view.candidates) > 0.7:
                flags.append("candidates_overlap_pool")

        if (view.amps or view.threads) and not view.probes:
            errored = any(e.startswith("探针回归 失败")
                          for e in view.errors)
            flags.append("probe_failed" if errored
                         else "probe_return_empty")

        if (self.entry == "1" and view.untouched and view.probes):
            untouched_items = [str(u.get("desc", "")).strip()
                               for u in view.untouched
                               if str(u.get("desc", "")).strip()]
            has_touch = False
            covers_seen = False
            for p in view.probes:
                for c in (p.get("covers") or []):
                    c = str(c).strip()
                    if not c:
                        continue
                    covers_seen = True
                    m = re.match(r"^T?(\d+)$", c)
                    if m:
                        idx = int(m.group(1)) - 1
                        if 0 <= idx < len(untouched_items):
                            has_touch = True
                            break
                    else:
                        if any(_similar(c, d, 0.7)
                               for d in untouched_items):
                            has_touch = True
                            break
                if has_touch:
                    break
            if not covers_seen:
                has_touch = any(
                    _similar(p.get("question", ""), u.get("desc", ""), 0.6)
                    for p in view.probes for u in view.untouched)
            if not has_touch:
                flags.append("probe_no_target_covered")

        pool_amps = [a for a in pool.amps
                     if str(a.get("polarity", "")).strip() in ("0", "1", "both")]
        pool_pols = [str(a.get("polarity", "")).strip() for a in pool_amps]
        if len(pool_pols) >= 3 and len(set(pool_pols)) == 1:
            div = self._polarity_why_diversity(pool_amps)
            if div >= 0.4:
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
                                0.3, 1200, json_mode=True)
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

    # ---------- self-check ----------
    def _self_check(self, view: View) -> dict:
        if not view.candidates and not view.amps:
            return {"notes": "本次内容为空白，无需回看"}

        cand_lines = "\n".join(
            f"{i+1}. [{c.get('attribute','0')}×{c.get('position','0')}] "
            f"{c.get('desc','')}"
            for i, c in enumerate(view.candidates))
        amp_lines = "\n".join(
            f"{i+1}. [{a.get('type','?')}] {a.get('desc','')}"
            for i, a in enumerate(view.amps))

        system = (
            "你是【自我回看者】。\n"
            "回看这次运行，如实回答：\n"
            "1. 有没有哪条候选，是后面补的，不是从展开里长出来的？\n"
            "2. 有没有哪条 &，是为了凑数？\n"
            "3. ing 输出里，是否有**超过一半**的句子与上游文本"
            "（上游 view 的 manifest/collision，或本层候选 desc）"
            "逐字或近义重复？\n"
            "   - 逐字重复：完全相同的句子；\n"
            "   - 近义重复：换了个说法但说的是同一件事。\n"
            "   - 若超过一半 → ing_rephrased=true；\n"
            "   - 若不到一半 → false。\n"
            "   ★ 不要因为'有几句原话'就填 true；要看**比例**。\n"
            "4. 如果撞不出新东西，我有没有诚实说'未生'？\n"
            "5. 这次 DGTF 整体流程走得好不好？\n"
            f"6. 本层 view 的标准是：{self.phase.view_focus}\n"
            "严格 JSON：\n"
            '{"suspicious_candidates":[1,2],'
            '"suspicious_amps":[1],'
            '"ing_rephrased":false,'
            '"honest_about_empty":true,'
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
        try:
            raw = self.llm.call(system, user, 0.3, 1500, json_mode=True)
        except Exception as e:
            logger.warning("self-check 失败: %s", e)
            return {}

        data = self.llm.parse_json(raw) or {}
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
        if view.distance_to_question < 1.0:
            parts.append(f"【综合距离】distance_to_question={view.distance_to_question:.2f}")

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
                system, user, 0.7, 2500, model=self.llm.reasoner_model)
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
        thread_lines = [f"  ... {t['desc']}" for t in view.threads]
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
                      *[f"  - {u.get('desc','')}（{u.get('source','')}）"
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
            lines += ["", "【本层升级为不可判定（单向）】",
                      *[f"  - 子问题{e.get('sub_id')}：{e.get('reason','')}"
                        for e in view.escalations]]
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
                      "  独立结构（计入覆盖率）："]
            for sa in up.get("structural_amps", []):
                lines.append(f"    structural_amp：{sa}")
            if up.get("aligned_amps"):
                lines.append("  对齐 und_aspects（另计，不参与覆盖率）：")
                for aa in up["aligned_amps"]:
                    lines.append(f"    aligned_amp：{aa}")
        if view.distance_to_question < 1.0:
            lines += ["", f"【综合距离】{view.distance_to_question:.2f}"]
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

        return "\n".join(lines)


# ============================================================
# MetaDGTF · 调度器（v1.21.50 支持并行模式）
# ============================================================
class MetaDGTF:
    def __init__(self, config: dict):
        self.config = config
        self.llm = LLM(config)
        self.pools: Dict[str, Pool] = {
            "0": Pool(), "1": Pool(), "both": Pool(), "all": Pool(),
        }
        self.verbose = config["output"].get("verbose", True)
        self.self_text: List[str] = []
        self._mcfg = config.setdefault("memory", {})
        m = self._mcfg.setdefault("channels", list(CHANNELS))
        self.channels = tuple(MemoryChannel.check(c) for c in m)
        self.decidability_result: Dict[str, Any] = {}
        self._input_sanity: Dict[str, Any] = {}  # [P1-6]
        self.dec_tracker: Optional[ChannelTracker] = None
        self.und_tracker: Optional[ChannelTracker] = None
        self._rephrased_streak = 0
        self._uncovered_streak = 0
        # v1.21.50 并行改造
        self._question: str = ""
        self._key_terms: List[str] = []
        self._results: Dict[str, View] = {}
        self._prev_results: Dict[str, View] = {}
        self._rounds: Dict[str, int] = {}
        self._keep: Dict[str, str] = {}
        self._upstream_provider = None
        self._self_text_by_entry: Dict[str, List[str]] = {
            e: [] for e in _ENTRIES}
        self._pack_lock = threading.Lock()
        # [fix-100] 池 / self_text 的写入锁。串行模式下等于无开销，
        # 并行模式 A/B 下保证 merge / 生命周期更新 / 汇总不会互相踩。
        self._pool_lock = threading.RLock()
        self._parallel_mode: str = "serial"
        self._b_state: Dict[str, dict] = {}

    def vp(self, *args):
        if self.verbose:
            print(*args)

    # ============================================================
    # self_text 按层隔离 [fix-99]
    # ============================================================
    # 设计 9.7 并发安全清单要求：并行模式下每层各写自己的桶，
    # 全部跑完再合并。v1.21.50 是 4 个线程往同一个 list 做
    # read-modify-write（prev[-keep:] 还会互相截断），条目会丢。
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
                out.append({
                    "question": "上面这几条被判为「后补／换说法复述」，"
                                "本圈禁止以任何形式重述它们，只发生"
                                "真的长出来的新东西：" + "；".join(descs),
                    "link": "self-check 判定的复述条目，绕开去重就能喷更多，"
                            "但那不叫展开",
                    "expected_gain": 0.6})

        if sc.get("ing_rephrased"):
            out.append({
                "question": "上一圈 ing 输出超过一半是上游文本的复述，"
                            "本圈必须写出上游 view 与候选里没有的句子；"
                            "写不出就明说「此处未生」，不要用换个说法顶替。",
                "link": "复述不产生距离，只会把空转记成推进",
                "expected_gain": 0.7})

        bq = view.both_quota or {}
        items = [i for i in (bq.get("items") or [])
                 if str(i.get("missing", "")).strip()]
        if items:
            miss = "；".join(
                f"「{str(i.get('tension', ''))[:40]}」缺"
                f"{str(i.get('missing', ''))[:40]}"
                for i in items[:4])
            out.append({
                "question": f"以下张力被判 both 且写明了缺什么：{miss}。"
                            f"本圈若能给出其中任一项，就把对应张力裁成 0 或 1"
                            f"；给不出就明说它为什么不可能出现。",
                "link": "both 占满一张单子等于没裁，"
                        "缺的东西要有人去把它生出来",
                "expected_gain": 0.8})
        return out

    # ============================================================
    # 状态更新：调度器唯一入口
    # ============================================================
    def _apply_view_to_pool(self, view: View, pool: Pool, entry: str,
                            rephrased_streak: int = 0,
                            meta_idle_streak: int = 0):
        # [fix-100] 池是共享状态，写入统一走这把可重入锁
        with self._pool_lock:
            return self._apply_view_to_pool_locked(
                view, pool, entry, rephrased_streak, meta_idle_streak)

    def _apply_view_to_pool_locked(self, view: View, pool: Pool, entry: str,
                            rephrased_streak: int = 0,
                            meta_idle_streak: int = 0):
        pool.merge(view.amps, view.threads, view.meta, view.probes)
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
        if view.decidable_product:
            pool.add_decidable(view.decidable_product)
        if view.undecidable_product:
            und_aspects = []
            if self.decidability_result:
                und_aspects = self.decidability_result.get(
                    "undecidable_aspects", []) or []
            pool.add_undecidable(view.undecidable_product,
                                 und_aspects=und_aspects)
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

        system = (
            "你是一个可判定性的**观察者**。\n"
            "\n"
            "你不看原始问题本身去判断它是否可判定，\n"
            "而是**读修行层留下来的形状**，从形状里读出可判定性。\n"
            "\n"
            "【你看到的产物】\n"
            "- 候选的 position 分布：判得明确（0 或 1）说明锚点能触及；\n"
            "  position=both 或大量同值说明这一处判不出\n"
            "- & 候选（attribute != position）：从一面长出、另一面读出不同结果，\n"
            "  这是\"两面给不出同一答案\"的结构\n"
            "- 主动悬置：修行层\"看清了、可以碰、决定不碰\"的点，是已知硬边界\n"
            "- ing 输出：撞出第三者说明有可对撞结构；写了\"此处未生\"\n"
            "  说明这一面撞不动\n"
            "- 悬空线头：未走完的方向\n"
            "\n"
            "【从这些产物读出三态之一】\n"
            "- decidable：候选普遍能判出 0/1，& 候选少，悬置少，\n"
            "  ing 撞出了第三者\n"
            "- partial：有明显可判的方向，同时有明显判不出的位置\n"
            "- undecidable：大部分候选判不出（position 大量 both），\n"
            "  或悬置密集，或 ing 普遍未生\n"
            "\n"
            "【★ 关键】\n"
            "每一条 decidable_aspects / undecidable_aspects 必须能追溯到\n"
            "池里的具体产物。在 evidence 字段里给出追溯来源。\n"
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
        )

        try:
            raw = self.llm.call(system, user, 0.3, 1200, json_mode=True)
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
        return {
            "decidability": status,
            "reason": str(data.get("reason", ""))[:200],
            "features": _list("features"),
            "decidable_aspects": _list("decidable_aspects"),
            "undecidable_aspects": _list("undecidable_aspects"),
            "evidence": evidences[:8],
            "_source": "pool",
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
            if not any(_similar(a_str, x, 0.7) for x in dec_aspects):
                dec_aspects.append(f"[外] {a_str}")

        und_aspects = list(pool_res.get("undecidable_aspects", []))
        for a in ext_res.get("undecidable_aspects", []):
            a_str = str(a).strip()
            if not a_str:
                continue
            if not any(_similar(a_str, x, 0.7) for x in und_aspects):
                und_aspects.append(f"[外] {a_str}")

        merged = dict(pool_res)
        merged["decidable_aspects"] = dec_aspects[:8]
        merged["undecidable_aspects"] = und_aspects[:8]
        merged["_ext_status"] = ext_status
        merged["_ext_reason"] = str(ext_res.get("reason", ""))[:200]
        merged["_ext_features"] = list(ext_res.get("features", []))[:5]
        merged["_divergent"] = (pool_status != ext_status)
        merged["_source"] = "pool+external"
        return merged

    def _print_decidability(self, source: str = "external") -> None:
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
                self.vp("   ⚠️ 两路分叉：以池判为准"
                        "（DGTF 机制下池是展开的产物）")
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

        evidences = self.decidability_result.get("evidence") or []
        if evidences:
            self.vp("   📎 追溯来源：")
            for ev in evidences[:5]:
                if isinstance(ev, dict):
                    aspect = str(ev.get("aspect", ""))[:40]
                    src = str(ev.get("source", ""))[:60]
                    self.vp(f"      · {aspect}  ← {src}")

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
            f"【近几圈已有 &（{len(recent_amps)} 条）】\n{recent_text}"
        )

        try:
            raw = self.llm.call(system, user, 0.2, 500, json_mode=True)
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
        if cov_before is not None:
            answered = sum(
                1 for s in self.pools["1"].sub_questions
                if s.get("decidability") == "decidable"
                and s.get("status") == "answered")
            effective_cov = max(
                cov_before,
                cov if cov is not None else 0.0)
            self.dec_tracker.update_decidable(effective_cov, answered)
            if effective_cov >= 0.7:
                self._dec_conv_streak += 1
            else:
                self._dec_conv_streak = 0
            if (self._dec_conv_streak >= conv_window
                    and not self.dec_tracker.converged):
                self.dec_tracker.mark_converged(layer_no)
                self.vp(f"   📗 可判定通道收敛"
                        f"（第 {layer_no} 圈，cov={effective_cov:.0%}，"
                        f"连续 {self._dec_conv_streak} 圈）")
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
        if len(und_amps) >= 2 and und_clarity >= 0.6:
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
            self.vp(f"   📘 不可判定结构覆盖率 "
                    f"{struct_cov:.0%}"
                    f"（{n_hit}/{n_aspects} und_aspects 命中）")
            self.vp(f"      ↳ 独立结构 {n_indep} 条（计入覆盖率），"
                    f"对齐结构 {n_aligned} 条（另计）")
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
            raw = self.llm.call(system, lines, 0.3, 900, json_mode=True)
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
                json_mode=True)
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
        if not duel:
            return {"clean": True, "unsettled": 0, "total": 0,
                    "uncovered": []}

        adjudicated = [str(e.get("target", "")).strip()
                       for e in self.pools["all"].engagements]
        suspended = [str(x.get("target", "")).strip()
                     for x in self.pools["all"].suspensions
                     if x.get("status") in ("active", "stable")]

        uncovered = []
        for s in duel:
            t = str(s.get("target", "")).strip()
            if not t:
                continue
            if any(_similar(t, a, thr) for a in adjudicated if a):
                continue
            if any(_similar(t, x, thr) for x in suspended if x):
                continue
            uncovered.append(t)
        return {"clean": not uncovered, "unsettled": len(uncovered),
                "total": len(duel), "uncovered": uncovered}

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
            n = max(1, int(rounds or 0) or hard)
            per = {e: n for e in _ENTRIES}

        # [fix-103] 未被显式指定的层，兜底时尊重 spiral.min_rounds
        # （配置里写的是"这一层至少该跑几圈"，原来被完全忽略，
        #  一律拿 hard_max 兜底）。per_entry 覆盖同样要生效。
        min_rounds = (self.config.get("spiral") or {}).get("min_rounds") or {}
        out = {}
        for e in _ENTRIES:
            if e in per:
                out[e] = per[e]
                continue
            mr = int(min_rounds.get(e, 0) or 0)
            if mr > 0:
                out[e] = mr
            else:
                out[e] = int(_spiral_for(self.config, e).get(
                    "hard_max", hard))
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

    @staticmethod
    def _has_pool_content_view(view: Optional[View]) -> bool:
        if not view:
            return False
        if view.probes or view.amps or view.suspensions or view.threads or view.meta:
            return True
        if view.candidates or view.collision:
            return True
        return False

    # ============================================================
    # v1.21.50 并行模式：决策器 + 三个 Input 工厂
    # ============================================================
    def _decide_parallel_mode(self, question: str) -> dict:
        q = question or ""
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
            "【启发】\n"
            "- 明确单一问题 → serial\n"
            "- 多分句/并列 → A\n"
            "- 含'或/还是'、过程性 → B\n"
            "- 拿不准 → serial\n\n"
            "严格 JSON：\n"
            '{"mode":"serial|A|B","reason":"≤80字",'
            '"confidence":0.0-1.0}'
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
            raw = self.llm.call(system, user, 0.2, 400, json_mode=True)
            data = self.llm.parse_json(raw) or {}
            mode = str(data.get("mode", "serial")).strip()
            if mode.upper() == "A":
                mode = "A"
            elif mode.upper() == "B":
                mode = "B"
            else:
                mode = "serial"
            conf = float(data.get("confidence", 0.0) or 0.0)
            reason = str(data.get("reason", ""))[:200]
        except Exception as e:
            logger.warning("并行模式决策失败: %s", e)
            return {"mode": "serial", "reason": "决策失败，退回保守",
                    "confidence": 0.0}
        if mode != "serial" and conf < 0.5:
            return {"mode": "serial",
                    "reason": f"低置信({conf:.2f})，退回 serial：{reason}",
                    "confidence": conf}
        return {"mode": mode, "reason": reason, "confidence": conf}

    def _build_inp_base(self, s, role="", rno=0, entry="0"):
        return Input(
            question=self._question,
            seed_probes=s,
            key_terms=self._key_terms,
            round_role=role, round_no=rno,
            self_memory=self._self_snapshot_for(entry),
        )

    def _build_inp_duel(self, s, role="", rno=0):
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
                round_role=role, round_no=rno,
                self_memory=self._self_snapshot_for("both"),
            )
        return Input(
            upstream_views=up,
            upstream_pools=[self.pools["0"], self.pools["1"]],
            upstream_untouched=[v.untouched for v in up],
            root_question=self._question,
            seed_probes=s, key_terms=self._key_terms,
            round_role=role, round_no=rno,
            context=self._context_if_on(),
            self_memory=self._self_snapshot_for("both"),
        )

    def _build_inp_meta(self, s, role="", rno=0):
        up = []
        if self._upstream_provider is not None:
            try:
                up = list(self._upstream_provider("all") or [])
            except Exception:
                up = []
        up = [v for v in up if _view_usable(v)]
        if len(up) < 2:
            return Input(
                question=self._question,
                seed_probes=s, key_terms=self._key_terms,
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
            round_role=role, round_no=rno,
            context=self._context_if_on(),
            self_memory=self._self_snapshot_for("all"),
        )

    # ============================================================
    # v1.21.50 _run_layer：单层螺旋执行器
    # ============================================================
    def _run_layer(self, entry: str, n_rounds: int = 0) -> View:
        question = self._question
        key_terms = self._key_terms
        results = self._results

        uncovered_streak = 0
        _prev_missed_n: Optional[int] = None
        rephrased_streak = 0
        meta_idle_streak = 0

        sp = _spiral_for(self.config, entry)
        soft_max = int(sp.get("soft_max", 3))
        sim_thr = float(sp.get("stop_similarity", 0.8))
        stable_need = int(sp.get("stable_need", 2))
        idle_limit = int(sp.get("idle_limit", 2))
        rounds_n = max(1, int(n_rounds or 0)
                       or int(sp.get("hard_max", 6)))
        _extra_rounds = 0
        if entry == "all":
            _extra_rounds = int(sp.get("all_extra_rounds", 1))
        _total_rounds = rounds_n + _extra_rounds

        # 研究层前置：问题分解
        if (entry == "1"
                and not self.pools["1"].sub_questions
                and _action_on(self.config, "decompose_question")):
            d0 = DGTF("1", self.llm, self.config)
            d0.verbose = False
            dec_src = self.config.get("actions", {}).get(
                "decompose_source", "pool")

            zero_view = None
            if self._upstream_provider is not None:
                try:
                    ups = self._upstream_provider("1") or []
                except Exception:
                    ups = []
                for v in ups:
                    if getattr(v, "entry", "") == "0":
                        zero_view = v
                        break
            has_zero_prod = self._has_pool_content_view(zero_view)
            use_internal = (dec_src == "pool" and has_zero_prod)

            if use_internal:
                zero_pool = self.pools.get("0") or Pool()
                subs = d0._decompose_from_pool(
                    question, zero_pool, zero_view)
                src_label = "修行池内部"
            else:
                subs = d0._decompose_question(
                    question, self.decidability_result)
                src_label = "外部评估"

            self.pools["1"].sub_questions = subs
            if subs:
                n_dec = sum(1 for s in subs
                            if s["decidability"] == "decidable")
                n_und = sum(1 for s in subs
                            if s["decidability"] == "undecidable")
                self.vp(f"   🧩 研究层从{src_label}分解出 {len(subs)} "
                        f"个子问题（可判定 {n_dec} / 不可判定 {n_und}）")

        # 对撞层前置：四象限对齐
        if entry == "both" and not self.pools["both"].duel_alignment:
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
        view = None
        prev_product = ""
        idles = 0
        r_idle_limit = int(sp.get("round_idle_limit", 2))
        new_thr = float(sp.get("new_item_similarity", 0.55))
        overlap_thr = float(sp.get("new_item_overlap", 0.55))
        thread_new_thr = float(sp.get("thread_new_similarity", 0.70))
        thread_overlap_thr = float(sp.get("thread_new_overlap", 0.70))
        r_window = max(1, int(sp.get("round_window", 2)))
        r_stall_limit = int(sp.get("round_stall_limit", 2))
        idle_new_amp = 0
        idle_new_thread = 0
        idle_stall = 0
        carry_streak = 0  # [P1-5] 连续多少圈被自省判定为「复述/未裁」
        _last_unsettled = 999
        _all_settle_streak = 0
        win_amps: List[List[str]] = []
        win_threads: List[List[str]] = []
        all_candidates: List[dict] = []
        all_amps: List[dict] = []
        all_threads: List[dict] = []
        roles_hist: List[str] = []
        round_log: List[dict] = []
        all_rehashed: List[dict] = []
        all_dec_products: List[dict] = []
        all_und_products: List[dict] = []
        views_per_round: List[dict] = []
        all_expanded_descs: List[str] = []

        for r in range(_total_rounds):
            layer_no = r + 1
            role = ("摊开" if r == 0 else "收束" if r == 2 else "深入")
            if _total_rounds > 1:
                self.vp(f"\n   ↻ 第 {layer_no}/{_total_rounds} 圈 · {role}"
                        f"{'（带着上一圈 ' + str(len(seeds)) + ' 个重点）'
                           if seeds else ''}")
            pool = self.pools[entry]
            snap_amps = [str(a.get("desc", "")) for a in pool.amps]
            snap_threads = [str(t.get("desc", "")) for t in pool.threads]
            self._print_polarity_snapshot(pool, entry, layer_no)

            if entry == "0" or entry == "1":
                inp = self._build_inp_base(seeds, role, layer_no, entry)
            elif entry == "both":
                inp = self._build_inp_duel(seeds, role, layer_no)
            else:
                inp = self._build_inp_meta(seeds, role, layer_no)

            inp.pool = pool
            inp.decidability_result = self.decidability_result

            dg = DGTF(entry, self.llm, self.config)
            view = dg.run(inp)
            view.rounds_run = layer_no
            try:
                for _d in (getattr(view, "_expanded_descs", None)
                           or []):
                    if _d and not any(_similar(_d, x, 0.85)
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
                    rephrased_streak, meta_idle_streak))

            for e in (view.engagements or []):
                t = str(e.get("target", "")).strip()
                if t and not any(
                        _similar(t, x.get("target", ""), 0.85)
                        for x in self.pools[entry].engagements):
                    self.pools[entry].engagements.append(dict(e))

            if entry == "1":
                cov_before = coverage_of(self.pools[entry], sp)
                st = update_deferrals(
                    self.pools[entry], view, layer_no, sp)
                if any(st[k] for k in ("new", "handled", "escalated",
                                       "answered", "refined")):
                    self.vp(f"   ⏳ 债务：新增{st['new']} 确认{st['confirmed']} "
                            f"清偿{st['handled']} 升级{st['escalated']} "
                            f"回答{st['answered']} 深入{st['refined']}")
                cov = coverage_of(self.pools[entry], sp)
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
                    self.vp(f"   ⚔️ 张力：裁决{st['adjudicated']} "
                            f"新增{st['new']} 确认{st['confirmed']} "
                            f"撤回{st['revoked']} 消解{st['resolved']} "
                            f"转稳{st['stable']}")
            else:
                st = update_suspensions(
                    self.pools[entry], view, layer_no, sp)
                if any(st[k] for k in ("new", "revoked", "resolved", "stable")):
                    self.vp(f"   ⏸ 悬置：新增{st['new']} 确认{st['confirmed']} "
                            f"撤回{st['revoked']} 解决{st['resolved']} "
                            f"转稳{st['stable']}")

            if _action_on(self.config, "re_evaluate_pool"):
                re_eval_n = int(sp.get("re_eval_every_n", 1))
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

            recent_amps = [x for lst in win_amps[-r_window:] for x in lst]
            recent_threads = [x for lst in win_threads[-r_window:]
                              for x in lst]
            cur_amps = [str(a.get("desc", "")) for a in pool.amps]
            cur_threads = [str(t.get("desc", "")) for t in pool.threads]
            added_amps = [d for d in cur_amps
                          if not any(_similar(d, x, 0.85)
                                     for x in snap_amps)]
            added_threads = [d for d in cur_threads
                             if not any(_similar(d, x, 0.85)
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
            win_amps.append(new_amps)
            win_threads.append(new_threads)

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

            sat_enabled = bool(sp.get("structure_saturation_enabled", True))
            sat_every_n = int(sp.get("structure_saturation_every_n", 2))
            if (sat_enabled and sat_every_n > 0
                    and layer_no % sat_every_n == 0
                    and new_amps
                    and entry in ("1", "all")):
                recent_for_sat = [x for lst in win_amps[-r_window:]
                                  for x in lst]
                sat_verdict = self._check_structure_saturation(
                    new_amps, recent_for_sat)
                if sat_verdict is False:
                    if entry == "1":
                        idle_new_amp = max(idle_new_amp, r_idle_limit)
                        sat_override = True
                        self.vp(f"      ↳ 无新维度，idle_new_amp 推到 "
                                f"{idle_new_amp}（视为无新 &）")
                    else:
                        self.vp(f"      ↳ 元层无新维度（软判据，"
                                f"不直接推 idle_new_amp）")
                elif sat_verdict is True:
                    idle_new_amp = 0
                    self.vp(f"      ↳ 有新维度，idle_new_amp 重置为 0")

            if rounds_n > 1:
                self.vp(f"   🆕 本圈新增 & {len(new_amps)} 条 / "
                        f"线头 {len(new_threads)} 条"
                        f"（近似不算，比对近 {r_window} 圈；"
                        f"连续无新增 &{idle_new_amp}/线头{idle_new_thread} "
                        f"｜连续无推进 {idle_stall}"
                        f"{'（' + stall_why + '）' if stalled else ''}）")
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

            # [P1-5] 自省回流：把这一圈 self-check 的结论变成下一圈的约束
            view.carry = self._build_carry(view)
            if view.carry:
                seeds = list(view.carry) + list(seeds)
                self.vp(f"   🔁 [自省回流] 注入 {len(view.carry)} 条约束"
                        f"进下一圈")
                if role == "深入":
                    role = "转向"
                elif role == "收束":
                    role = "复裁"

            if view.carry:
                carry_streak += 1
            else:
                carry_streak = 0
            if view.probes and rounds_n > 1:
                self.vp(f"   🎯 探针筛出 {len(seeds)} 条重点"
                        f"（生发 {len(view.probes)} 条 → 进下一轮 {len(seeds)} 条）")

            stop_reasons: List[str] = []
            _mi_from_view = getattr(view, "_meta_idle_streak", 0)
            # [P1-5] 自省连续判定「复述/未裁」等价于层内空转，
            # 复用已有的「ing 连续复述」停止判据，不再让链条无限续下去。
            _mi_effective = max(meta_idle_streak, _mi_from_view, carry_streak)
            if entry in ("all", "both"):
                if getattr(self, "verbose", False):
                    print(f"   🔬 [fix-78 diag] entry={entry} "
                          f"meta_idle_streak(参数)={meta_idle_streak} "
                          f"meta_idle_streak(view)={_mi_from_view} "
                          f"effective={_mi_effective} "
                          f"soft_max={soft_max}")
                if _mi_effective >= 2:
                    if layer_no < soft_max:
                        if getattr(self, "verbose", False):
                            print(f"   ⏸ [fix-82] fix-72 v4 待触发"
                                  f"（连续复述 {_mi_effective} 圈），"
                                  f"但 layer_no={layer_no} < "
                                  f"soft_max={soft_max}，先不停止")
                    else:
                        stop_reasons.append(
                            f"ing 连续 {_mi_effective} 圈复述"
                            f"（层内空转）")
            if _total_rounds > 1 and r_idle_limit > 0:
                if entry != "0" and idle_new_amp >= r_idle_limit:
                    if sat_override:
                        stop_reasons.append(
                            f"结构饱和度判定连续无新维度")
                    else:
                        stop_reasons.append(
                            f"连续 {idle_new_amp} 轮无新 &（沉淀完了）")
                if idle_new_thread >= r_idle_limit:
                    stop_reasons.append(
                        f"连续 {idle_new_thread} 轮无线头新增（方向走完了）")
            if (rounds_n > 1 and r_stall_limit > 0
                    and idle_stall >= r_stall_limit):
                stop_reasons.append(
                    f"连续 {idle_stall} 轮有新增但无推进（{stall_why}）")
            if (entry == "1"
                    and self.dec_tracker is not None
                    and self.und_tracker is not None
                    and self.dec_tracker.converged
                    and self.und_tracker.converged
                    and idle_new_amp >= r_idle_limit):
                stop_reasons.append("研究层双通道均收敛")
            if (entry == "1"
                    and self.dec_tracker is not None
                    and self.und_tracker is not None
                    and not (self.dec_tracker.converged
                             and self.und_tracker.converged)
                    and self.dec_tracker.is_stalled()
                    and self.und_tracker.is_stalled()
                    and idle_new_amp >= r_idle_limit):
                stop_reasons.append("双通道均停滞（qdist 无改善）")

            if rounds_n > 1 and layer_no >= soft_max:
                product = view.manifest or ""
                _natural_rest_reason = ""
                if (prev_product and product
                        and _similar(prev_product, product, sim_thr)):
                    _natural_rest_reason = "产物相似度高，自然安住"
                else:
                    if entry == "both":
                        stable = [s for s in self.pools[entry].duel_suspensions
                                  if s.get("status") == "stable"]
                    else:
                        stable = [s for s in self.pools[entry].suspensions
                                  if s.get("status") == "stable"]
                    if len(stable) >= stable_need:
                        _natural_rest_reason = "悬置决定稳定，自然安住"
                if _natural_rest_reason:
                    stop_reasons.append(_natural_rest_reason)
                if not stop_reasons and view.idle:
                    idles += 1
                    if idles >= idle_limit:
                        if entry == "both":
                            stop_reasons.append("无新张力（材料耗尽）")
                        elif entry == "all":
                            stop_reasons.append("无新元决策（元决策耗尽）")
                        else:
                            stop_reasons.append("连续空转")
                elif not view.idle:
                    idles = 0

            if stop_reasons and rounds_n > 1:
                _missed_all = self._check_uncovered_directions(view)
                _cur_missed_n = len(_missed_all)
                if _missed_all:
                    uncovered_streak += 1
                    _max_push = int(sp.get(
                        "max_uncovered_pushes", 1))
                    if _prev_missed_n is None:
                        _decreasing = True
                    else:
                        _decreasing = (_cur_missed_n < _prev_missed_n)
                    if uncovered_streak <= _max_push and _decreasing:
                        if getattr(self, "verbose", False):
                            _last_disp = (
                                _prev_missed_n
                                if _prev_missed_n is not None
                                else "首次")
                            print(f"   ⚠️ [fix-88b] "
                                  f"{_cur_missed_n} 条未深入方向"
                                  f"（上次 {_last_disp}，"
                                  f"减少中，"
                                  f"第 {uncovered_streak}/"
                                  f"{_max_push} 次），"
                                  f"推迟停止")
                            for _m in _missed_all[:3]:
                                print(f"      · {_m}")
                        stop_reasons = []
                    else:
                        if getattr(self, "verbose", False):
                            _why = []
                            if uncovered_streak > _max_push:
                                _why.append(
                                    f"已达上限 {_max_push}")
                            if not _decreasing:
                                _prev_disp = (
                                    _prev_missed_n
                                    if _prev_missed_n is not None
                                    else "首次")
                                _why.append(
                                    f"方向数未减少"
                                    f"（{_prev_disp}"
                                    f"→{_cur_missed_n}）")
                            print(f"   ⚠️ [fix-88b] "
                                  f"未深入方向 "
                                  f"{_cur_missed_n} 条，"
                                  f"放行停止"
                                  f"（{chr(59).join(_why)}）")
                    _prev_missed_n = _cur_missed_n
                else:
                    uncovered_streak = 0
                    _prev_missed_n = None

            stop = ""
            if stop_reasons:
                stop = " + ".join(stop_reasons) + "，螺旋停止"

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
        else:
            if view is not None and rounds_n > 1:
                view.stop_reason = (
                    f"体力耗尽（hard_max={rounds_n} 圈走满，"
                    f"未触发任何停止判据，是被截断不是自然停止）")
                self.vp(f"   ⏹ {view.stop_reason}")

        if view is not None and rounds_n > 1:
            view.roles_run = list(roles_hist)
            view.round_log = list(round_log)
            view.rehashed = list(all_rehashed)
            if all_candidates:
                view.candidates = all_candidates
            try:
                view._expanded_descs = list(all_expanded_descs)
            except Exception:
                pass
            if all_amps:
                view.amps = all_amps
            if all_threads:
                view.threads = all_threads
            actual_rounds = view.rounds_run or rounds_n
            self.vp(f"   🧺 跨圈合并：候选 {len(all_candidates)} 条 / "
                    f"& {len(all_amps)} 条 / 线头 {len(all_threads)} 条"
                    f"（去重后，覆盖 {actual_rounds} 圈）")

            _cb = len(view.candidates or [])
            _ab = len(view.amps or [])
            _tb = len(view.threads or [])
            view.candidates = _cross_round_dedup(
                view.candidates or [],
                overlap_thr=0.65, sim_thr=0.70, max_n=60)
            view.amps = _cross_round_dedup(
                view.amps or [],
                overlap_thr=0.65, sim_thr=0.70, max_n=25)
            view.threads = _cross_round_dedup(
                view.threads or [],
                overlap_thr=0.65, sim_thr=0.70, max_n=15)
            if (_cb != len(view.candidates)
                    or _ab != len(view.amps)
                    or _tb != len(view.threads)):
                self.vp(
                    f"   🧹 合并后二次去重："
                    f"候选 {_cb}->{len(view.candidates)} / "
                    f"& {_ab}->{len(view.amps)} / "
                    f"线头 {_tb}->{len(view.threads)}")

            _dg = DGTF(entry, self.llm, self.config)
            _dg.verbose = False
            view.quality_flags = _dg._quality_check(
                view, self.pools[entry], actual_rounds)
            view.quality_verdict = _dg._quality_verdict(
                view.quality_flags)

            if entry == "all":
                _drift = _all_candidate_drift_rate(view.candidates)
                if _drift > 0.5:
                    view.quality_flags.append(
                        f"all_candidate_drift({_drift:.0%})")
                    view.quality_verdict = (
                        f"all 层候选漂移：{_drift:.0%}")

            if view.quality_flags:
                self.vp("   ⚑ 合并后质量线索："
                        + ", ".join(view.quality_flags))
            if entry == "1":
                if all_dec_products:
                    view.decidable_product = all_dec_products[-1]
                if all_und_products:
                    merged_amps: List[str] = []
                    for up in all_und_products:
                        for s in (up.get("structural_amps") or []):
                            if not any(_similar(s, x, 0.85)
                                       for x in merged_amps):
                                merged_amps.append(s)
                    merged_aligned: List[str] = []
                    for up in all_und_products:
                        for s in (up.get("aligned_amps") or []):
                            if not any(_similar(s, x, 0.85)
                                       for x in merged_aligned):
                                merged_aligned.append(s)
                    last_und = all_und_products[-1]
                    view.undecidable_product = {
                        "why_undecidable": last_und.get("why_undecidable", ""),
                        "structural_amps": merged_amps[:10],
                        "aligned_amps": merged_aligned[:10],
                        "clarity": last_und.get("clarity", 0.0),
                        "distance": last_und.get("distance", 1.0),
                    }

        if entry == "all" and view is not None:
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
            cov_hist = (list(self.dec_tracker.coverage_history)
                        if self.dec_tracker else [])
            und_hist = (list(self.und_tracker.und_clarity_history)
                        if self.und_tracker else [])
            if cov_hist:
                last_cov = cov_hist[-1]
                seg = (f"\n\n## 七、原始问题覆盖率\n"
                       f"研究层可判定通道最近一次覆盖率：{last_cov:.2f}"
                       f"（累计 {len(cov_hist)} 次记录）\n")
                view.manifest = (view.manifest or "") + seg
                self.vp(f"   📈 元层追加覆盖率段：{last_cov:.2f}")
            elif und_hist:
                last_cl = und_hist[-1]
                seg = (f"\n\n## 七、原始问题覆盖率\n"
                       f"无 decidable 子问题（可判定通道不适用）。\n"
                       f"不可判定通道最近一次清晰度：{last_cl:.2f}"
                       f"（累计 {len(und_hist)} 次记录）\n")
                view.manifest = (view.manifest or "") + seg
                self.vp(f"   📈 元层追加覆盖率段"
                        f"（fallback 到 und clarity）：{last_cl:.2f}")

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
            stl = self._settle_research(max(1, rounds_n))
            if stl["clean"]:
                self.vp("   ✓ 终局清算完成：全部债务已交代"
                        "（handled / escalated / dropped）")
            elif view is not None:
                view.closure_reason = (
                    f"soft_max_unsettled（{stl['leftover']} 项债务未清算）")
                self.vp(f"   ⚠️ 终局清算：{stl['leftover']} 项未清算"
                        f"（不是停止理由，单列）")

        if view is not None:
            view.suspensions = [dict(s)
                                for s in self.pools[entry].suspensions]
            if entry == "1":
                view.deferrals = [dict(d)
                                  for d in self.pools["1"].deferrals]
                view.settlement = {
                    "clean": not any(
                        d["status"] == "deferred"
                        for d in self.pools["1"].deferrals),
                    "leftover": sum(
                        1 for d in self.pools["1"].deferrals
                        if d["status"] == "dropped"),
                    "coverage": coverage_of(self.pools["1"], sp),
                    "decidable_channel": self.pools["1"].decidable_channel,
                    "undecidable_channel": self.pools["1"].undecidable_channel,
                }
            if entry == "both":
                view.duel_suspensions = [dict(s)
                                         for s in self.pools["both"].duel_suspensions]
            view.refinements = [dict(r)
                                for r in self.pools[entry].refinements]
        # [fix-99] 按层写各自的桶，不再 4 个线程抢同一个 list
        if "self" in self.channels and view is not None:
            self._append_self_text(entry, view)

        return view

    def _make_serial_provider(self):
        def provider(entry: str):
            deps = _ENTRY_DEPS.get(entry, ())
            return [self._results[k] for k in deps
                    if k in self._results]
        return provider

    # ============================================================
    # 可判定性：0 层先行 [P0-2]
    # ============================================================
    def _run_zero_then_assess(self, question, rounds,
                              active: List[str]) -> List[str]:
        """把 0 层从并行集合里提出来先跑，再判可判定性。

        A/B 原先在开跑前用 _assess_decidability(question) 做纯外部评估，
        判据只有问题字符串本身 —— 实测同一 P=NP，A/B 判 decidable，
        串行判 undecidable。串行是对的：它跑完 0 层后
        用 _assess_decidability_from_pool_view 读修行层留下的形状。
        并行那个是错的，1 层因此被迫走可判定通道，覆盖率失去意义。

        返回剔除了 "0" 的 active（0 的结果已进 self._results）。
        """
        assess_on = _action_on(self.config, "assess_decidability")
        source_cfg = (self.config.get("actions") or {}).get(
            "decidability_source", "pool")
        use_pool = (assess_on and "0" in active
                    and source_cfg in ("pool", "pool_only"))

        fallback = {
            "decidability": "decidable", "reason": "",
            "features": [], "decidable_aspects": [],
            "undecidable_aspects": []}

        ext_res: Optional[dict] = None
        if assess_on and source_cfg in ("pool", "external"):
            d_assess = DGTF("1", self.llm, self.config)
            d_assess.verbose = False
            try:
                ext_res = d_assess._assess_decidability(question)
            except Exception as exc:
                logger.warning("外部可判定性评估失败: %s", exc)

        if not use_pool:
            self.decidability_result = ext_res or dict(fallback)
            self._print_decidability(
                source="external" if assess_on else "off")
            return active

        self.vp(f"\n{'─'*60}\n🪞 修行层先行"
                f"（可判定性判定读的是它留下的形状）\n{'─'*60}")
        try:
            self._results["0"] = self._run_layer(
                "0", self._rounds.get("0", rounds.get("0", 0)))
        except Exception as exc:
            logger.error("0 层先行失败: %s", exc, exc_info=True)
            self._results.pop("0", None)
            self.decidability_result = ext_res or dict(fallback)
            self._print_decidability(source="external(0层失败)")
            return active

        pool_res = None
        try:
            pool_res = self._assess_decidability_from_pool_view(
                question, self._results["0"])
        except Exception as exc:
            logger.warning("池视角可判定性评估失败: %s", exc)

        if pool_res is None:
            self.decidability_result = ext_res or dict(fallback)
            self._print_decidability(source="external(pool失败)")
        elif source_cfg == "pool" and ext_res is not None:
            self.decidability_result = self._merge_decidability(
                pool_res, ext_res)
            self._print_decidability(source="pool+external(0层先行)")
        else:
            self.decidability_result = pool_res
            self._print_decidability(source="pool_only(0层先行)")

        return [e for e in active if e != "0"]

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
        _active0 = [e for e in route if e in _ENTRIES]
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
                    self._results[e] = View(
                        entry=e,
                        errors=[f"A 模式失败：{type(exc).__name__}: {exc}"])

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
        packed["dispatch"] = {
            "requested": list(route),
            "order": list(self._results.keys()),
            "skipped": [],
            "_parallel_mode": "A",
        }
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
        _active0 = [e for e in route if e in _ENTRIES]
        active = self._run_zero_then_assess(question, rounds, _active0)
        # 0 层已跑完，把它当成第 1 圈的上游（原来第 1 圈全员无上游）
        if "0" in self._results:
            self._prev_results = dict(self._results)
            self.vp("   ↳ 修行层入 _prev_results，"
                    "作为其余层第 1 圈的 Jacobi 上游")

        self._b_state: Dict[str, dict] = {
            e: self._init_b_state(e) for e in active
        }
        max_round = max(
            (self._b_state[e]["total_rounds"] for e in active),
            default=0)

        self.vp(f"\n{'═'*60}\n🧵 B 模式：轮次并行"
                f"（最多 {max_round} 圈）\n{'═'*60}")
        for e in active:
            st = self._b_state[e]
            self.vp(f"   → {_LAYER_LABEL[e]}"
                    f"（上限 {st['total_rounds']} 圈）")

        for r in range(1, max_round + 1):
            active_r = [
                e for e in active
                if (not self._b_state[e]["stopped"]
                    and r <= self._b_state[e]["total_rounds"])
            ]
            if not active_r:
                break

            self.vp(f"\n{'─'*60}\n🔄 B 第 {r}/{max_round} 圈"
                    f"（{len(active_r)} 层："
                    f"{'/'.join(_LAYER_LABEL[e] for e in active_r)}）"
                    f"\n{'─'*60}")

            self._upstream_provider = self._make_jacobi_provider()

            with ThreadPoolExecutor(max_workers=max(2, len(active_r))) as ex:
                futures = {
                    e: ex.submit(self._run_one_round_B, e, r)
                    for e in active_r
                }
                for e, f in futures.items():
                    try:
                        view = f.result()
                        if view is not None:
                            self._results[e] = view
                    except Exception as exc:
                        logger.error("B 模式 %s 第 %d 圈失败: %s",
                                     e, r, exc, exc_info=True)
                        self._b_state[e]["stopped"] = True
                        self._b_state[e]["stop_reason"] = \
                            f"异常：{type(exc).__name__}: {exc}"

            self._prev_results = dict(self._results)

        for e in active:
            self._b_finalize_layer(e)

        # [fix-100] _totalize_all_pool 必须串行，且在所有层跑完后执行
        with self._pool_lock:
            self._totalize_all_pool()
        self._merge_self_text()

        packed = self._pack_result(
            question, route, keep, rounds, self._results)
        packed["dispatch"] = {
            "requested": list(route),
            "order": list(self._results.keys()),
            "skipped": [],
            "_parallel_mode": "B",
        }
        return packed

    def _make_jacobi_provider(self):
        def provider(entry: str):
            if entry == "all":
                deps = ("0", "1", "both")
            else:
                deps = _ENTRY_DEPS.get(entry, ())
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
            "soft_max": int(sp.get("soft_max", 3)),
            "sim_thr": float(sp.get("stop_similarity", 0.8)),
            "stable_need": int(sp.get("stable_need", 2)),
            "idle_limit": int(sp.get("idle_limit", 2)),
            "r_idle_limit": int(sp.get("round_idle_limit", 2)),
            "new_thr": float(sp.get("new_item_similarity", 0.55)),
            "overlap_thr": float(sp.get("new_item_overlap", 0.55)),
            "thread_new_thr": float(sp.get("thread_new_similarity", 0.70)),
            "thread_overlap_thr": float(sp.get("thread_new_overlap", 0.70)),
            "r_window": max(1, int(sp.get("round_window", 2))),
            "r_stall_limit": int(sp.get("round_stall_limit", 2)),
            "r": 0,
            "seeds": [],
            "prev_product": "",
            "idles": 0,
            "uncovered_streak": 0,
            "prev_missed_n": None,
            "rephrased_streak": 0,
            "meta_idle_streak": 0,
            "idle_new_amp": 0,
            "idle_new_thread": 0,
            "idle_stall": 0,
            "_last_unsettled": 999,
            "_all_settle_streak": 0,
            "win_amps": [],
            "win_threads": [],
            "all_candidates": [],
            "all_amps": [],
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
        }

    def _run_one_round_B(self, entry: str, r: int) -> Optional[View]:
        state = self._b_state[entry]
        sp = state["sp"]
        pool = self.pools[entry]
        state["r"] = r

        snap_amps = [str(a.get("desc", "")) for a in pool.amps]
        snap_threads = [str(t.get("desc", "")) for t in pool.threads]

        role = ("摊开" if r == 1
                else "收束" if r == 3
                else "深入")
        self._print_polarity_snapshot(pool, entry, r)

        self._b_pre_layer(entry, r)

        if entry in ("0", "1"):
            inp = self._build_inp_base(state["seeds"], role, r, entry)
        elif entry == "both":
            inp = self._build_inp_duel(state["seeds"], role, r)
        else:
            inp = self._build_inp_meta(state["seeds"], role, r)
        inp.pool = pool
        inp.decidability_result = self.decidability_result

        dg = DGTF(entry, self.llm, self.config)
        view = dg.run(inp)
        view.rounds_run = r

        try:
            for _d in (getattr(view, "_expanded_descs", None) or []):
                if _d and not any(_similar(_d, x, 0.85)
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
                state["rephrased_streak"], state["meta_idle_streak"]))

        for e in (view.engagements or []):
            t = str(e.get("target", "")).strip()
            if t and not any(_similar(t, x.get("target", ""), 0.85)
                             for x in self.pools[entry].engagements):
                self.pools[entry].engagements.append(dict(e))

        st = self._b_lifecycle(entry, view, r, sp)

        if _action_on(self.config, "re_evaluate_pool"):
            re_eval_n = int(sp.get("re_eval_every_n", 1))
            if re_eval_n > 0 and r % re_eval_n == 0:
                self._re_evaluate_pool(entry, pool, r)

        self._b_merge(entry, view, state)

        if self.verbose:
            entry_label = _LAYER_LABEL.get(entry, entry)
            bar = "━" * 60
            print(f"\n{bar}")
            print(f"━━━ {entry_label} · B 第 {r}/"
                  f"{state['total_rounds']} 圈 · {role} · view ━━━")
            print(bar)
            print(view.manifest or "（此处未生）")
            print(bar)

        state["seeds"] = select_probe_focus(
            pool, view.probes, view.threads,
            self._key_terms, view.anchor, self.config)

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
            # [fix-102] 原来是硬编码 has_zero_prod = False，
            # 导致 use_internal 恒假、"修行池内部"分支永不执行。
            # 改为与 _run_layer 一致：真的去看上游 provider 有没有 0 层产物。
            # B 模式第 1 圈 _prev_results 为空 → 自然走外部评估，行为不变；
            # 但上游一旦就绪，内部路径就能自动生效。
            zero_view = None
            if self._upstream_provider is not None:
                try:
                    ups = list(self._upstream_provider("1") or [])
                except Exception:
                    ups = []
                for v in ups:
                    if getattr(v, "entry", "") == "0":
                        zero_view = v
                        break
            has_zero_prod = self._has_pool_content_view(zero_view)
            use_internal = (dec_src == "pool" and has_zero_prod)
            if use_internal:
                zero_pool = self.pools.get("0") or Pool()
                subs = d0._decompose_from_pool(
                    self._question, zero_pool, zero_view)
                src_label = "修行池内部"
            else:
                subs = d0._decompose_question(
                    self._question, self.decidability_result)
                src_label = "外部评估"
            self.pools["1"].sub_questions = subs
            if subs:
                n_dec = sum(1 for s in subs
                            if s["decidability"] == "decidable")
                n_und = sum(1 for s in subs
                            if s["decidability"] == "undecidable")
                self.vp(f"   🧩 研究层从{src_label}分解出 "
                        f"{len(subs)} 个子问题"
                        f"（可判定 {n_dec} / 不可判定 {n_und}）")

        if entry == "both" and not self.pools["both"].duel_alignment:
            self.pools["both"].duel_alignment = {
                "quality": "unaligned",
                "match_rate": 0.0,
                "quadrants": [],
                "consumed": False,
                "_note": "B 模式第 1 圈，上游尚未产生，无对齐",
            }
            self.vp("   🧭 四象限对齐：跳过（B 第 1 圈，上游未就绪）")

    def _b_lifecycle(self, entry, view, r, sp) -> dict:
        if entry == "1":
            cov_before = coverage_of(self.pools[entry], sp)
            st = update_deferrals(self.pools[entry], view, r, sp)
            if any(st[k] for k in ("new", "handled", "escalated",
                                   "answered", "refined")):
                self.vp(f"   ⏳ 债务：新增{st['new']} "
                        f"确认{st['confirmed']} "
                        f"清偿{st['handled']} 升级{st['escalated']} "
                        f"回答{st['answered']} 深入{st['refined']}")
            cov = coverage_of(self.pools[entry], sp)
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
                self.vp(f"   ⚔️ 张力：裁决{st['adjudicated']} "
                        f"新增{st['new']} 确认{st['confirmed']} "
                        f"撤回{st['revoked']} 消解{st['resolved']} "
                        f"转稳{st['stable']}")
        else:
            st = update_suspensions(self.pools[entry], view, r, sp)
            if any(st[k] for k in ("new", "revoked",
                                   "resolved", "stable")):
                self.vp(f"   ⏸ 悬置：新增{st['new']} "
                        f"确认{st['confirmed']} "
                        f"撤回{st['revoked']} 解决{st['resolved']} "
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

    def _b_check_stop(self, entry, view, r, state, st,
                      snap_amps, snap_threads):
        pool = self.pools[entry]
        sp = state["sp"]
        r_window = state["r_window"]
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

        recent_amps = [x for lst in state["win_amps"][-r_window:]
                       for x in lst]
        recent_threads = [x for lst in state["win_threads"][-r_window:]
                          for x in lst]
        cur_amps = [str(a.get("desc", "")) for a in pool.amps]
        cur_threads = [str(t.get("desc", "")) for t in pool.threads]
        added_amps = [d for d in cur_amps
                      if not any(_similar(d, x, 0.85)
                                 for x in snap_amps)]
        added_threads = [d for d in cur_threads
                         if not any(_similar(d, x, 0.85)
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
        state["win_amps"].append(new_amps)
        state["win_threads"].append(new_threads)

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

        sat_enabled = bool(sp.get("structure_saturation_enabled", True))
        sat_every_n = int(sp.get("structure_saturation_every_n", 2))
        if (sat_enabled and sat_every_n > 0
                and r % sat_every_n == 0
                and new_amps and entry in ("1", "all")):
            recent_for_sat = [x for lst in state["win_amps"][-r_window:]
                              for x in lst]
            sat_verdict = self._check_structure_saturation(
                new_amps, recent_for_sat)
            if sat_verdict is False:
                if entry == "1":
                    idle_new_amp = max(idle_new_amp, r_idle_limit)
                    state["idle_new_amp"] = idle_new_amp
                    sat_override = True
                    self.vp(f"      ↳ 无新维度，"
                            f"idle_new_amp 推到 {idle_new_amp}")
                else:
                    self.vp(f"      ↳ 元层无新维度（软判据）")
            elif sat_verdict is True:
                idle_new_amp = 0
                state["idle_new_amp"] = 0
                self.vp(f"      ↳ 有新维度，idle_new_amp 重置为 0")

        if state["total_rounds"] > 1:
            self.vp(f"   🆕 B{r} 新增 & {len(new_amps)} 条 / "
                    f"线头 {len(new_threads)} 条"
                    f"（连续无新增 &{idle_new_amp}/"
                    f"线头{idle_new_thread}"
                    f"｜连续无推进 {idle_stall}"
                    f"{'（' + stall_why + '）' if stalled else ''}）")

        state["round_log"].append({
            "round": r, "role": state["roles_hist"][-1],
            "new_amps": len(new_amps),
            "new_threads": len(new_threads),
            "idle_amp": idle_new_amp,
            "idle_thread": idle_new_thread,
            "idle_stall": idle_stall, "why": stall_why,
        })

        stop_reasons: List[str] = []

        _mi_from_view = getattr(view, "_meta_idle_streak", 0)
        _mi_effective = max(state["meta_idle_streak"], _mi_from_view)
        if entry in ("all", "both") and _mi_effective >= 2:
            if r < soft_max:
                self.vp(f"   ⏸ [fix-82] fix-72 v4 待触发"
                        f"（连续复述 {_mi_effective} 圈）")
            else:
                stop_reasons.append(
                    f"ing 连续 {_mi_effective} 圈复述（层内空转）")

        if state["total_rounds"] > 1 and r_idle_limit > 0:
            if entry != "0" and idle_new_amp >= r_idle_limit:
                stop_reasons.append(
                    "结构饱和度判定连续无新维度" if sat_override
                    else f"连续 {idle_new_amp} 轮无新 &（沉淀完了）")
            if idle_new_thread >= r_idle_limit:
                stop_reasons.append(
                    f"连续 {idle_new_thread} 轮无线头新增（方向走完了）")
        if (state["rounds_n"] > 1 and r_stall_limit > 0
                and idle_stall >= r_stall_limit):
            stop_reasons.append(
                f"连续 {idle_stall} 轮有新增但无推进（{stall_why}）")
        if (entry == "1"
                and self.dec_tracker is not None
                and self.und_tracker is not None
                and self.dec_tracker.converged
                and self.und_tracker.converged
                and idle_new_amp >= r_idle_limit):
            stop_reasons.append("研究层双通道均收敛")
        if (entry == "1"
                and self.dec_tracker is not None
                and self.und_tracker is not None
                and not (self.dec_tracker.converged
                         and self.und_tracker.converged)
                and self.dec_tracker.is_stalled()
                and self.und_tracker.is_stalled()
                and idle_new_amp >= r_idle_limit):
            stop_reasons.append("双通道均停滞（qdist 无改善）")

        if state["total_rounds"] > 1 and r >= soft_max:
            product = view.manifest or ""
            prev_product = state["prev_product"]
            _natural_rest_reason = ""
            if (prev_product and product
                    and _similar(prev_product, product, sim_thr)):
                _natural_rest_reason = "产物相似度高，自然安住"
            else:
                if entry == "both":
                    stable = [
                        s for s in self.pools[entry].duel_suspensions
                        if s.get("status") == "stable"]
                else:
                    stable = [
                        s for s in self.pools[entry].suspensions
                        if s.get("status") == "stable"]
                if len(stable) >= stable_need:
                    _natural_rest_reason = "悬置决定稳定，自然安住"
            if _natural_rest_reason:
                stop_reasons.append(_natural_rest_reason)
            if not stop_reasons and view.idle:
                state["idles"] += 1
                if state["idles"] >= idle_limit:
                    if entry == "both":
                        stop_reasons.append("无新张力（材料耗尽）")
                    elif entry == "all":
                        stop_reasons.append("无新元决策（元决策耗尽）")
                    else:
                        stop_reasons.append("连续空转")
            elif not view.idle:
                state["idles"] = 0

        state["prev_product"] = view.manifest or ""

        if stop_reasons and state["rounds_n"] > 1:
            _missed_all = self._check_uncovered_directions(view)
            _cur_missed_n = len(_missed_all)
            if _missed_all:
                state["uncovered_streak"] += 1
                _max_push = int(sp.get("max_uncovered_pushes", 1))
                if state["prev_missed_n"] is None:
                    _decreasing = True
                else:
                    _decreasing = (
                        _cur_missed_n < state["prev_missed_n"])
                if (state["uncovered_streak"] <= _max_push
                        and _decreasing):
                    self.vp(f"   ⚠️ [fix-88b] {_cur_missed_n} 条"
                            f"未深入方向（减少中，"
                            f"第 {state['uncovered_streak']}/"
                            f"{_max_push} 次），推迟停止")
                    stop_reasons = []
                else:
                    self.vp(f"   ⚠️ [fix-88b] 未深入方向 "
                            f"{_cur_missed_n} 条，放行停止")
                state["prev_missed_n"] = _cur_missed_n
            else:
                state["uncovered_streak"] = 0
                state["prev_missed_n"] = None

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
            self.vp(f"   ⏹ B 第 {r} 圈停止：{stop}")

    def _b_finalize_layer(self, entry: str):
        state = self._b_state.get(entry)
        if not state or state["view"] is None:
            return
        view = state["view"]
        if state["total_rounds"] <= 1:
            return

        view.roles_run = list(state["roles_hist"])
        view.round_log = list(state["round_log"])
        view.rehashed = list(state["all_rehashed"])
        if state["all_candidates"]:
            view.candidates = state["all_candidates"]
        try:
            view._expanded_descs = list(state["all_expanded_descs"])
        except Exception:
            pass
        if state["all_amps"]:
            view.amps = state["all_amps"]
        if state["all_threads"]:
            view.threads = state["all_threads"]

        actual_rounds = state["r"]
        self.vp(f"   🧺 B {entry} 跨圈合并："
                f"候选 {len(state['all_candidates'])} / "
                f"& {len(state['all_amps'])} / "
                f"线头 {len(state['all_threads'])}"
                f"（覆盖 {actual_rounds} 圈）")

        _cb = len(view.candidates or [])
        _ab = len(view.amps or [])
        _tb = len(view.threads or [])
        view.candidates = _cross_round_dedup(
            view.candidates or [],
            overlap_thr=0.65, sim_thr=0.70, max_n=60)
        view.amps = _cross_round_dedup(
            view.amps or [],
            overlap_thr=0.65, sim_thr=0.70, max_n=25)
        view.threads = _cross_round_dedup(
            view.threads or [],
            overlap_thr=0.65, sim_thr=0.70, max_n=15)
        if (_cb != len(view.candidates)
                or _ab != len(view.amps)
                or _tb != len(view.threads)):
            self.vp(f"   🧹 B {entry} 二次去重："
                    f"候选 {_cb}->{len(view.candidates)} / "
                    f"& {_ab}->{len(view.amps)} / "
                    f"线头 {_tb}->{len(view.threads)}")

        _dg = DGTF(entry, self.llm, self.config)
        _dg.verbose = False
        view.quality_flags = _dg._quality_check(
            view, self.pools[entry], actual_rounds)
        view.quality_verdict = _dg._quality_verdict(view.quality_flags)

        if entry == "all":
            _drift = _all_candidate_drift_rate(view.candidates)
            if _drift > 0.5:
                view.quality_flags.append(
                    f"all_candidate_drift({_drift:.0%})")
                view.quality_verdict = f"all 层候选漂移：{_drift:.0%}"

        if entry == "1":
            if state["all_dec_products"]:
                view.decidable_product = state["all_dec_products"][-1]
            if state["all_und_products"]:
                merged_amps: List[str] = []
                for up in state["all_und_products"]:
                    for s in (up.get("structural_amps") or []):
                        if not any(_similar(s, x, 0.85)
                                   for x in merged_amps):
                            merged_amps.append(s)
                merged_aligned: List[str] = []
                for up in state["all_und_products"]:
                    for s in (up.get("aligned_amps") or []):
                        if not any(_similar(s, x, 0.85)
                                   for x in merged_aligned):
                            merged_aligned.append(s)
                last_und = state["all_und_products"][-1]
                view.undecidable_product = {
                    "why_undecidable": last_und.get(
                        "why_undecidable", ""),
                    "structural_amps": merged_amps[:10],
                    "aligned_amps": merged_aligned[:10],
                    "clarity": last_und.get("clarity", 0.0),
                    "distance": last_und.get("distance", 1.0),
                }

        view.suspensions = [dict(s)
                            for s in self.pools[entry].suspensions]
        if entry == "1":
            view.deferrals = [dict(d)
                              for d in self.pools["1"].deferrals]
            view.settlement = {
                "clean": not any(
                    d["status"] == "deferred"
                    for d in self.pools["1"].deferrals),
                "leftover": sum(
                    1 for d in self.pools["1"].deferrals
                    if d["status"] == "dropped"),
                "coverage": coverage_of(self.pools["1"], state["sp"]),
                "decidable_channel":
                    self.pools["1"].decidable_channel,
                "undecidable_channel":
                    self.pools["1"].undecidable_channel,
            }
        if entry == "both":
            view.duel_suspensions = [
                dict(s) for s in
                self.pools["both"].duel_suspensions]
        view.refinements = [
            dict(r) for r in self.pools[entry].refinements]

        if entry == "all":
            clo = self._settle_meta()
            view.meta_closure = clo
            if clo["clean"]:
                self.vp(f"   🌀 闭环清算：clean=True")
            else:
                _unc = clo.get("uncovered") or []
                _unc_s = "；".join(str(u)[:40] for u in _unc[:5])
                view.closure_reason = (
                    f"meta_unsettled（{clo['unsettled']}/"
                    f"{clo['total']} 类张力未交代：{_unc_s}）")
                self.vp(f"   ⚠️ 闭环清算：{clo['unsettled']}/"
                        f"{clo['total']} 类张力未交代")
            cov_hist = (list(self.dec_tracker.coverage_history)
                        if self.dec_tracker else [])
            if cov_hist:
                last_cov = cov_hist[-1]
                seg = (f"\n\n## 七、原始问题覆盖率\n"
                       f"研究层可判定通道最近一次覆盖率："
                       f"{last_cov:.2f}"
                       f"（累计 {len(cov_hist)} 次记录）\n")
                view.manifest = (view.manifest or "") + seg

        self._apply_keep(
            self.pools[entry], self._keep.get(entry, "all"))

        if (entry == "1"
                and self.pools["1"].deferrals
                and _action_on(self.config, "settle_research")):
            deferred_count = sum(
                1 for d in self.pools["1"].deferrals
                if d["status"] == "deferred")
            if deferred_count > 0:
                self.vp(f"   📋 B 研究层仍有 {deferred_count} 笔"
                        f"延迟债务，进入终局清算")
            stl = self._settle_research(max(1, state["rounds_n"]))
            if stl["clean"]:
                self.vp("   ✓ B 终局清算完成")
            else:
                view.closure_reason = (
                    f"soft_max_unsettled（{stl['leftover']} 项未清算）")

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

    def _pack_result(self, question, route, keep, rounds, results):
        return {
            "question": question,
            "route": route,
            "keep": keep,
            "rounds": rounds,
            "dispatch": {
                "requested": list(route),
                "order": list(results.keys()),
                "skipped": [],
                "_parallel_mode": self._parallel_mode,
            },
            "channels": list(self.channels),
            "self_text": self.self_text,
            "decidability": self.decidability_result,
            "views": {k: v.to_dict() for k, v in results.items()},
            "pools": {k: p.to_dict() for k, p in self.pools.items()},
            "llm_calls": self.llm.total_calls,
            "llm_tokens": self.llm.total_tokens,
        }

    # ============================================================
    # 分发方法：run
    # ============================================================
    def run(self, question: str,
            route: Optional[List[str]] = None,
            keep: Optional[Dict[str, str]] = None,
            rounds=0,
            channels: Optional[List[str]] = None,
            parallel_mode: str = "auto") -> dict:
        route = route or ["0", "1", "both", "all"]
        keep = keep or {k: "all" for k in route}
        rounds_plan = self._rounds_plan(rounds)
        if channels is not None:
            self.channels = tuple(MemoryChannel.check(c) for c in channels)
        self._mcfg["channels"] = list(self.channels)

        if parallel_mode == "auto":
            decision = self._decide_parallel_mode(question)
            mode = decision["mode"]
            self.vp(f"\n🧵 并行模式自动决策：{mode}"
                    f"（{decision['reason']}，"
                    f"置信 {decision['confidence']:.2f}）")
        else:
            mode = parallel_mode if parallel_mode in ("serial", "A", "B") \
                else "serial"
            self.vp(f"\n🧵 并行模式：{mode}（用户指定）")

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
        else:
            packed = self._run_serial(question, route, keep,
                                      rounds_plan, channels)
        if isinstance(packed, dict) and self._input_sanity:
            packed["input_sanity"] = self._input_sanity
        return packed

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
            "★ 没有问题就返回空数组，这是最常见的情况。\n"
            "严格 JSON：\n"
            '{"issues":[{"term":"≤20字","why":"≤40字"}],'
            '"note":"≤40字"}'
        )
        try:
            d = DGTF("1", self.llm, self.config)
            d.verbose = False
            raw = d.llm.call(system, f"【问题】\n{question}",
                             0.0, 800, json_mode=True)
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
        return {
            "issues": issues,
            "note": str(data.get("note", ""))[:80],
            "checked": True,
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

        dispatch = self._plan_dispatch(route)
        source_cfg = self.config.get("actions", {}).get(
            "decidability_source", "pool")
        assess_on = _action_on(self.config, "assess_decidability")
        has_zero = "0" in dispatch["order"]
        use_pool = assess_on and has_zero and source_cfg in ("pool", "pool_only")

        if use_pool and dispatch["order"][0] != "0":
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

        ext_res: Optional[dict] = None
        if assess_on and source_cfg in ("pool", "external"):
            d_assess = DGTF("1", self.llm, self.config)
            d_assess.verbose = False
            ext_res = d_assess._assess_decidability(question)

        if not use_pool:
            if assess_on:
                self.decidability_result = ext_res or {
                    "decidability": "decidable", "reason": "",
                    "features": [], "decidable_aspects": [],
                    "undecidable_aspects": []}
                self._print_decidability(source="external")
            else:
                self.decidability_result = {
                    "decidability": "decidable", "reason": "动作已关闭",
                    "features": [], "decidable_aspects": [],
                    "undecidable_aspects": []}
                self._print_decidability(source="off")

        for entry in dispatch["order"]:
            if entry == "0" and use_pool:
                self.vp(f"\n{'═'*60}\n【0】修行 DGTF"
                        f"（螺旋上限 {rounds['0']} 圈）\n{'═'*60}")
                self._results["0"] = self._run_layer(
                    "0", self._rounds.get("0", 0))
                pool_res = self._assess_decidability_from_pool_view(
                    question, self._results["0"])
                if source_cfg == "pool" and ext_res is not None:
                    self.decidability_result = self._merge_decidability(
                        pool_res, ext_res)
                    self._print_decidability(source="pool+external")
                else:
                    self.decidability_result = pool_res
                    self._print_decidability(source="pool_only")
                continue

            self.vp(f"\n{'═'*60}\n【{entry}】{_LAYER_LABEL[entry]} DGTF"
                    f"（螺旋上限 {rounds[entry]} 圈）\n{'═'*60}")
            self._results[entry] = self._run_layer(
                entry, self._rounds.get(entry, 0))

        if "all" in self._results:
            with self._pool_lock:
                self._totalize_all_pool()
        self._merge_self_text()

        packed = self._pack_result(question, route, keep, rounds,
                                   self._results)
        packed["dispatch"] = dispatch
        return packed


# ============================================================
# 保存结果
# ============================================================
def save_result(result: dict, save_dir: str = "outputs") -> Path:
    d = Path(save_dir)
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_q = "".join(c for c in result["question"][:20]
                     if c.isalnum() or c in "，。？ ") or "question"
    md = d / f"{ts}_{safe_q}.md"

    with open(md, "w", encoding="utf-8") as f:
        f.write(f"# 元 DGTF · {result['question']}\n\n")
        f.write(f"**时间**: {datetime.now().isoformat()}\n\n")
        disp = result.get("dispatch") or {}
        rounds = result.get("rounds") or {}
        if disp:
            seq = " → ".join(
                f"{_LAYER_LABEL.get(e, e)}({rounds.get(e, '?')}圈)"
                for e in disp.get("order", []))
            f.write(f"**调度**：{seq or '（空）'}\n\n")
            _pm = disp.get("_parallel_mode", "serial")
            _pm_disp = {
                "serial": "严格串行",
                "A": "A · 四层独立并行 + 汇流",
                "B": "B · 轮次并行",
            }.get(_pm, _pm)
            f.write(f"**并行模式**：{_pm_disp}\n\n")
            if disp.get("requested") != disp.get("order"):
                f.write(f"**请求顺序**：{' → '.join(disp['requested'])}\n\n")
            for sk in (disp.get("skipped") or []):
                f.write(f"- ⚠️ 跳过 `{sk['entry']}`：{sk['reason']}\n")
            if disp.get("skipped"):
                f.write("\n")
        else:
            f.write(f"**路由**: {' → '.join(result['route'])}\n\n")
        dec = result.get("decidability") or {}
        if dec:
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
        f.write(f"**保留**: {result['keep']}\n\n")
        f.write(f"**资源**: {result['llm_calls']} 次 LLM | "
                f"{result['llm_tokens']} tokens\n\n")
        san = result.get("input_sanity") or {}
        if san.get("issues"):
            f.write("**⚠️ 输入自检**\n\n")
            for _it in san["issues"]:
                f.write(f"- `{_it['term']}` — {_it['why']}\n")
            if san.get("note"):
                f.write(f"\n{san['note']}\n")
            f.write("\n")
        f.write("---\n\n")

        for key in ("0", "1", "both", "all"):
            v = result["views"].get(key)
            if not v:
                continue
            f.write(f"## {key}\n\n")
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
                f.write(f"- {t.get('desc','')}\n")
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
                    f.write(f"- {u.get('desc','')}（{u.get('source','')}）\n")
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
                for s in v["suspensions"]:
                    f.write(f"- {s.get('target','')}："
                            f"{s.get('reason') or '直觉，无理由'}"
                            f"（{s.get('reason_type','')}）\n")
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
                    f.write("\n")
            if v.get("escalations"):
                f.write("\n**升级为不可判定**：\n")
                for e in v["escalations"]:
                    f.write(f"- 子问题{e.get('sub_id')} {e.get('question','')}"
                            f"（{e.get('from','?')}→{e.get('to','?')}）"
                            f"：{e.get('reason','')}\n")
            if v.get("settlement"):
                stl = v["settlement"]
                _cov = stl.get("coverage")
                _cov_s = f"{_cov:.0%}" if isinstance(_cov, (int, float)) else "N/A"
                f.write(f"\n**终局清算**：clean={stl.get('clean')}，"
                        f"遗留 {stl.get('leftover', 0)} 项，"
                        f"可判定覆盖率 {_cov_s}\n")
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
                        f"未交代 {clo.get('unsettled', 0)} 类\n")
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
                f.write("- 独立结构（计入覆盖率）：\n")
                for sa in (up.get("structural_amps") or []):
                    f.write(f"  - structural_amp：{sa}\n")
                if up.get("aligned_amps"):
                    f.write("- 对齐 und_aspects（另计，不参与覆盖率）：\n")
                    for aa in up["aligned_amps"]:
                        f.write(f"  - aligned_amp：{aa}\n")
            if v.get("distance_to_question", 1.0) < 1.0:
                f.write(f"\n**综合距离**：{v['distance_to_question']:.2f}\n")
                if v.get("covered_aspects"):
                    f.write(f"- covered_aspects："
                            f"{'、'.join(v['covered_aspects'])}\n")
                if v.get("uncovered_aspects"):
                    f.write(f"- uncovered_aspects："
                            f"{'、'.join(v['uncovered_aspects'])}\n")
            if v.get("rounds_run"):
                roles = " → ".join(v.get("roles_run") or [])
                f.write(f"\n**实际走了 {v['rounds_run']} 圈**"
                        f"（上限 {rounds.get(v.get('entry'), '?')} 圈）"
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
                f.write("\n**自省**：\n")
                f.write(f"- 可疑候选：{sc.get('suspicious_candidates', [])}\n")
                f.write(f"- 可疑 &：{sc.get('suspicious_amps', [])}\n")
                f.write(f"- ing 复述：{sc.get('ing_rephrased')}\n")
                f.write(f"- 诚实承认空：{sc.get('honest_about_empty')}\n")
                if sc.get("flow_verdict"):
                    f.write(f"- 整体流程评价：{sc['flow_verdict']}\n")
                if sc.get("view_verdict"):
                    f.write(f"- view 评价：{sc['view_verdict']}\n")
                if sc.get("amp_ratio_verdict"):
                    f.write(f"- amp 占比判断：{sc['amp_ratio_verdict']}\n")
                if sc.get("notes"):
                    f.write(f"- 备注：{sc['notes']}\n")
            f.write("\n---\n\n")

        stxt = MemoryChannel.self_text_of(result.get("self_text"))
        if stxt:
            f.write(f"## 这一次我是谁\n\n{stxt}\n\n---\n\n")

        f.write("## 池\n\n")
        for k, p in result["pools"].items():
            tag = "（总池）" if k == "all" else ""
            f.write(f"### {k} 池{tag}\n\n")
            f.write(f"- & 印记 {len(p['amps'])} 条\n")
            f.write(f"- 悬空线头 {len(p['threads'])} 条\n")
            f.write(f"- 探针 {len(p.get('probes', []))} 条\n")
            f.write(f"- 主动悬置 {len(p.get('suspensions', []))} 条\n")
            if p.get("sub_questions"):
                f.write(f"- 可判定子问题 {len(p['sub_questions'])} 条\n")
            if p.get("deferrals"):
                f.write(f"- 延迟债务 {len(p['deferrals'])} 条\n")
            if p.get("escalations"):
                f.write(f"- 升级留痕 {len(p['escalations'])} 条\n")
            if p.get("duel_suspensions"):
                f.write(f"- 张力悬置 {len(p['duel_suspensions'])} 条\n")
            dc = p.get("decidable_channel") or {}
            uc = p.get("undecidable_channel") or {}
            if dc.get("answers"):
                f.write(f"- 📗 可判定通道：累计 {len(dc['answers'])} 条 answer\n")
            if uc.get("structural_amps"):
                f.write(f"- 📘 不可判定通道：累计 "
                        f"{len(uc['structural_amps'])} 条结构性 &\n")
            if p.get("duel_alignment"):
                _q = p['duel_alignment'].get('quality', '?')
                _qnote = "（合法结果：两侧没有同一件事可对）" \
                    if _q == "unaligned" else ""
                f.write(f"- 四象限对齐 {_q}"
                        f"（匹配率 {p['duel_alignment'].get('match_rate',0):.0%}）"
                        f"{_qnote}\n")
            f.write("\n")

        pools = result.get("pools", {})
        p_susp = pools.get("0", {}).get("suspensions", [])
        r_def = pools.get("1", {}).get("deferrals", [])
        d_susp = pools.get("both", {}).get("duel_suspensions", [])

        f.write("## 悬置总览\n\n")
        f.write("### 修行决定不碰的\n")
        for s in p_susp:
            f.write(f"- {s.get('target','')}（{s.get('status','')}）\n")
        if not p_susp:
            f.write("（无）\n")
        f.write("\n### 研究延迟处理的\n")
        for d in r_def:
            f.write(f"- {d.get('sub_question','')}（{d.get('status','')}）\n")
        if not r_def:
            f.write("（无）\n")
        f.write("\n### 对撞悬置的张力\n")
        for s in d_susp:
            f.write(f"- {s.get('target','')}（{s.get('status','')}）\n")
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

    # [fix-101] route 不含 all 时，A 模式的汇流圈结果也要落盘
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

    print(f"📁 已保存: {md}")
    return md


# ============================================================
# 默认配置
# ============================================================
DEFAULT_CONFIG = {
    "api": {
        "key": "",
        "base_url": os.getenv("DGTF_BASE_URL", "https://api.deepseek.com/v1"),
        "default_model": os.getenv("DGTF_MODEL", "deepseek-chat"),
        "reasoner_model": os.getenv("DGTF_REASONER_MODEL", "deepseek-reasoner"),
        "timeout": 240,
        "max_retries": 3,
        "retry_backoff": 1.8,
    },

    "output": {
        "save_dir": "outputs",
        "verbose": True,
        "show_dual_judge": True,
        "show_ing": False,
        "show_manifest": False,
        "self_check": True,
        "plain_speak": False,
        "layer_summary": False,
        "show_probe_diag": False,
    },

    "actions": {
        "assess_decidability": True,
        "decompose_question": True,
        "decidability_source": "pool",
        "decompose_source": "pool",
        # v1.21.50 并行模式
        "parallel_mode": "auto",
        # v1.21.51 [perf-104] 阴/阳两次展开并行发出（每层每圈省一次往返）
        "parallel_expand": True,
        # v1.21.52 [P1-6] 输入健全性自检：P=PN 这一步就该被说出来
        "input_sanity": True,

        "re_anchor": True,
        "expand_yin": True,
        "expand_yang": True,
        "dual_judge": True,
        "ing": True,
        "he": True,
        "phase_probe": True,
        "manifest": True,
        "self_check": True,

        "plain_speak": False,
        "summarize_views": False,

        "re_evaluate_pool": True,
        "settle_research": True,
    },

    "probe": {
        "min_gain": 0.3,
        "select_n": 3,
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
        "soft_max": 3,
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
        "round_window": 2,
        "round_stall_limit": 2,
        "rehash_similarity": 0.6,
        "stall_streak_limit": 2,
        "min_distance_improvement": 0.03,
        "convergence_window": 2,
        "all_extra_rounds": 1,
        # [P1-4] 极性裁决里 both 占比超过 max_ratio 时要求补裁
        "both_quota": {
            "enabled": True,
            "max_ratio": 0.7,
            "min_items": 2,
        },
        "re_eval_every_n": 1,
        "re_eval_recent_k": 10,
        "min_rounds": {
            "0": 0,
            "1": 2,
            "both": 3,
            "all": 0,
        },
        "per_entry": {
            "0": {"hard_max": 6},
            "1": {"structure_saturation_every_n": 3},
            "both": {"soft_max": 5},
            "all": {
                "stable_layers": 2,
                "structure_saturation_every_n": 3,
            },
        },
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


def load_config(path: str) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if not (HAS_YAML and Path(path).exists()):
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
    """v1.21.50 询问并行模式。"""
    while True:
        try:
            r = input("并行模式 [serial/A/B/auto]> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if r in ("", "auto"):
            return "auto"
        if r in ("serial", "s", "串行"):
            return "serial"
        if r == "a":
            return "A"
        if r == "b":
            return "B"
        print("   ✗ 可选：serial / A / B / auto（回车=auto）")
        print("     serial = 严格串行（最稳）")
        print("     A      = 四层独立并行 + 汇流（快）")
        print("     B      = 轮次并行（迭代）")
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


def _ask_config(cfg=None):
    """v1.21.50：返回值加 parallel_str（4 元组）。"""
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
    return route_str, rounds_str, channels_str, parallel_str


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
        route_str, rounds_str, channels_str, parallel_str = cfg_result

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
            "auto": "auto · 自动决策",
        }.get(parallel_str, parallel_str)

        print(f"\n{'═'*60}")
        print(f"元 DGTF v{__version__} · {question}")
        print(f"{'═'*60}")
        print(f"调度：{' → '.join(route)}")
        print(f"螺旋上限（每层圈数）：{rounds_str}")
        print(f"并行模式：{_mode_disp}")
        print(f"回来通道：{ch_disp}")
        print(f"{'═'*60}")

        meta = MetaDGTF(cfg)
        try:
            result = meta.run(question, route=route, keep={},
                              rounds=rounds_str, channels=channels,
                              parallel_mode=parallel_str)
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
            save_result(result, cfg["output"]["save_dir"])
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
    parser.add_argument("--route", default="0,1,both,all")
    parser.add_argument("--keep", default="")
    parser.add_argument("--channels", default="")
    parser.add_argument("--rounds", default="0")
    # [fix-105] 默认 None：命令行没给时回落到配置文件的
    # actions.parallel_mode。原来硬编码 default="auto"，配置项形同虚设。
    parser.add_argument("--parallel", default=None,
                        choices=["serial", "A", "B", "auto"],
                        help="并行模式：serial / A / B / auto"
                             "（不给则用配置 actions.parallel_mode）")
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
    if args.quiet:
        cfg["output"]["verbose"] = False
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

    channels = None
    if args.channels:
        raw = [x.strip() for x in args.channels.split(",") if x.strip()]
        if raw == ["none"]:
            channels = []
        else:
            channels = [MemoryChannel.check(x) for x in raw]

    route = [x.strip() for x in args.route.split(",") if x.strip()]
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

    _pm = args.parallel or cfg.get("actions", {}).get(
        "parallel_mode", "auto") or "auto"
    _mode_disp = {
        "serial": "严格串行",
        "A": "A · 四层独立并行 + 汇流",
        "B": "B · 轮次并行",
        "auto": "auto · 自动决策",
    }.get(_pm, _pm)

    print(f"\n{'═'*60}")
    print(f"元 DGTF v{__version__} · {question}")
    print(f"{'═'*60}")
    print(f"调度：{' → '.join(route)}")
    if keep:
        print(f"保留：{keep}")
    print(f"螺旋上限（每层圈数）：{args.rounds}")
    print(f"并行模式：{_mode_disp}"
          f"{'' if args.parallel else '（来自配置）'}")
    ch = channels if channels is not None else cfg["memory"].get(
        "channels", ["content", "context", "self"])
    print(f"回来通道：{'、'.join(ch) if ch else '全关（历史不参与本次）'}")
    print(f"{'═'*60}")

    result = meta.run(question, route=route, keep=keep,
                      rounds=args.rounds, channels=channels,
                      parallel_mode=_pm)

    print(f"\n{'═'*60}")
    print(f"完成 | {result['llm_calls']} 次 LLM | "
          f"{result['llm_tokens']} tokens")
    n_err = sum(len(v.get("errors", []))
                for v in result["views"].values())
    if n_err:
        print(f"⚠️  {n_err} 条失败记录（已写入输出）")
    print(f"{'═'*60}")

    save_result(result, cfg["output"]["save_dir"])


if __name__ == "__main__":
    main()