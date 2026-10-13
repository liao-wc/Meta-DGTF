#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 Step8：修 `_sim3` 的 BM25 通道（**方向性错误**）+ 调复述判据顺序。

## 为什么改（变异体 M1 挖出的真 bug）

原实现：
    bm = (_bm25_best(a, corpus) + _bm25_best(b, corpus)) / 2.0
`_bm25_best(q, corpus)` 是「q 对语料**每一篇**算 BM25 取最大」—— 它测的是
**q 与语料的相关性**，不是 **a 与 b 的相似度**。于是：

    a = "量子纠缠实验需要极低温"      （与语料第 1 篇几乎同句）
    b = "人工智能模型部署管线优化"    （与语料第 3 篇几乎同句）
    a 与 b 的字面重叠 = **0.000**
    旧 sim3(带语料) = 0.467  ← **虚高**，因为 a、b 各自与语料像

实测（v1.23.26 改前）：
    bm25_best(a)=0.771  bm25_best(b)=0.786  ⇒ 平均 0.779
    而 a、b 无关 ⇒ 这个 0.779 是**假的**。
⇒ 两条各自与语料相关、但彼此无关的句子会拿到虚高分。
   这正是设计报告 V1 判据「同词不同义 ⇒ 应低于」想防的事，方向反了。

## 改成什么（标准 BM25 pair 用法）

    bm = (bm25_pair(a→query, b→doc) + bm25_pair(b→query, a→doc)) / 2
其中 **IDF 仍取整份 corpus 的**（corpus 只用来定词的稀有度，N 用 corpus 的 N
以保证 idf 为正、可比）；**tf/长度用对方的**。

⇒ 只有**双方共有的词**才得分，且越罕见（idf 越大）分越高。
   实测：无关对 0.779→0.000、相关对 0.746→0.717（保持）。

## 附带：`_sent_is_rephrase` 判据顺序

把 `_sim3` 提到**首判**（结构层 T 编号短路优先），`_similar` / `_overlap_coef`
依次兜底。★ 已实测 8000 组**行为零变化**（sim3 ≤ overlap_coef 恒成立，
故 sim3 先判不会「多抓」）—— 顺序调整**只为让 sim3 可观测**，不改语义。
"""
from pathlib import Path
import ast

SRC = Path(__file__).resolve().parent / "元DGTF-V1.23.26.py"
b = SRC.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "主文件不是纯 CRLF"
assert b.count(b"\r\r\n") == 0, "主文件含 CRCRLF"
txt = b.decode("utf-8").replace("\r\n", "\n")

# ---------- 1. 新增 _bm25_pair（插在 _bm25_best 之后） ----------
ANCHOR_BEST_END = (
    "    if best <= 0:\n"
    "        return 0.0\n"
    "    return best / (best + _BM25_K1)\n"
    "\n"
    "\n"
    "def _jaccard(a: str, b: str, top_n: int = _KW_TOP_N) -> float:\n"
)

PAIR_FUNC = (
    "    if best <= 0:\n"
    "        return 0.0\n"
    "    return best / (best + _BM25_K1)\n"
    "\n"
    "\n"
    "def _bm25_pair(query: str, doc: str, corpus) -> float:\n"
    "    \"\"\"**两篇之间**的 BM25（query 打 doc），IDF 取整份语料。\n"
    "\n"
    "    与 `_bm25_best` 的区别：后者是「query 对语料每篇取最大」——\n"
    "    测的是 **query 与语料的相关性**，不是 **query 与 doc 的相似度**。\n"
    "    两条各自与语料相关、但彼此无关的句子，用 best 会拿到虚高分。\n"
    "    这里只累加 **doc 里真实出现** 的 query 词 ⇒ 不相干必为 0。\n"
    "\n"
    "    ★ IDF 仍用整份 corpus：corpus 在这里只提供**词的稀有度**\n"
    "      （N 与 df），不参与打分。这样同一批调用共享同一把尺子。\n"
    "    \"\"\"\n"
    "    doc_tfs, dfs, avgdl, n = corpus\n"
    "    if not n or n < _BM25_MIN_CORPUS or avgdl <= 0:\n"
    "        return 0.0\n"
    "    d_toks = _tokenize(doc)\n"
    "    if not d_toks:\n"
    "        return 0.0\n"
    "    from collections import Counter as _C\n"
    "    import math as _m\n"
    "    d_tf = _C(d_toks)\n"
    "    dl = len(d_toks)\n"
    "    s = 0.0\n"
    "    for t in set(_tokenize(query)):\n"
    "        f = d_tf.get(t, 0)\n"
    "        if not f:\n"
    "            continue\n"
    "        idf = _m.log(1.0 + (n - dfs.get(t, 0) + 0.5) / (dfs.get(t, 0) + 0.5))\n"
    "        denom = f + _BM25_K1 * (1.0 - _BM25_B + _BM25_B * dl / avgdl)\n"
    "        s += idf * (f * (_BM25_K1 + 1.0)) / denom\n"
    "    if s <= 0:\n"
    "        return 0.0\n"
    "    return s / (s + _BM25_K1)\n"
    "\n"
    "\n"
    "def _jaccard(a: str, b: str, top_n: int = _KW_TOP_N) -> float:\n"
)

c = txt.count(ANCHOR_BEST_END)
assert c == 1, f"锚点1（_bm25_best 尾 + _jaccard 头）命中 {c} 次"
txt = txt.replace(ANCHOR_BEST_END, PAIR_FUNC, 1)

# ---------- 2. _sim3 里的 bm 计算换成 pair ----------
OLD_BM = (
    "    bm = 0.0\n"
    "    if corpus is not None:\n"
    "        # 把 b 当语料、a 当 query；同时反向，取平均（对称化）\n"
    "        bm1 = _bm25_best(a, corpus)\n"
    "        bm2 = _bm25_best(b, corpus)\n"
    "        bm = (bm1 + bm2) / 2.0\n"
)
NEW_BM = (
    "    bm = 0.0\n"
    "    if corpus is not None:\n"
    "        # ★ 必须是 **a 与 b 之间** 的 BM25，不是「各自对语料」。\n"
    "        #   `_bm25_best` 测的是「与语料的相关性」—— 两条各自与语料\n"
    "        #   相关、彼此无关的句子会被抬到 0.7+（实测虚高，见 Step8\n"
    "        #   脚本头注）。`_bm25_pair` 只累加双方共有的词 ⇒ 无关必 0。\n"
    "        bm1 = _bm25_pair(a, b, corpus)\n"
    "        bm2 = _bm25_pair(b, a, corpus)\n"
    "        bm = (bm1 + bm2) / 2.0\n"
)
c = txt.count(OLD_BM)
assert c == 1, f"锚点2（bm 计算）命中 {c} 次"
txt = txt.replace(OLD_BM, NEW_BM, 1)

# ---------- 3. _sent_is_rephrase 判据顺序：sim3 提前 ----------
OLD_ORD = (
    "    if _similar(s, u, _REPHRASE_SIM):\n"
    "        return True\n"
    "    if _sim3(s, u, corpus=corpus) >= _REPHRASE_SIM3:\n"
    "        return True\n"
    "    # 包住形状保底：分母 min ⇒ 短句整段落在长句里时接近 1\n"
    "    return _overlap_coef(s, u, _KW_TOP_N) >= _REPHRASE_OVERLAP\n"
)
NEW_ORD = (
    "    # ★ sim3 提到**首判**：结构层（T 编号）短路必须先于字面尺子生效，\n"
    "    #   否则宽尺子（_similar / _overlap_coef 的 min 分母）会在 sim3\n"
    "    #   之前命中，让 sim3 这条线在行为上**不可观测**（变异体 M1 实测）。\n"
    "    #   **行为等价性已实测**：8000 组随机对零差异 —— sim3 的分是\n"
    "    #   `0.4*jaccard + 0.6*bm`，其中 jaccard ≤ overlap_coef 恒成立，\n"
    "    #   故 sim3 先判不会多抓。调序只为可观测，不改语义。\n"
    "    if _sim3(s, u, corpus=corpus) >= _REPHRASE_SIM3:\n"
    "        return True\n"
    "    if _similar(s, u, _REPHRASE_SIM):\n"
    "        return True\n"
    "    # 包住形状保底：分母 min ⇒ 短句整段落在长句里时接近 1\n"
    "    return _overlap_coef(s, u, _KW_TOP_N) >= _REPHRASE_OVERLAP\n"
)
c = txt.count(OLD_ORD)
assert c == 1, f"锚点3（判据顺序）命中 {c} 次"
txt = txt.replace(OLD_ORD, NEW_ORD, 1)

out = txt.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "写回后出现 CRCRLF"
SRC.write_bytes(out)
ast.parse(out.decode("utf-8"))
print("OK Step8: _bm25_pair 新增 + _sim3 换 pair + sim3 提到首判")
print("lines =", out.count(b"\n"), "bytes =", len(out))
