#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 打补丁 Step3：新增 BM25 语料统计 + sim3 三级尺子。

铁律：read_bytes -> 断言 CRLF==LF -> 转 LF -> 替换（断言各命中 1 次）
-> 转回 CRLF -> 断言 -> write_bytes。绝不 write_text。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.26.py"

b = SRC.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "源文件不是纯 CRLF"
assert b.count(b"\r\r\n") == 0, "源文件已含 \\r\\r\\n"
txt = b.decode("utf-8").replace("\r\n", "\n")

# ==========================================================
# 插入点：_overlap_coef 结束后（return inter / min(...) 之后）
# ==========================================================
ANCHOR = "    return inter / min(len(ka), len(kb))\n"

assert txt.count(ANCHOR) == 1, f"插入锚点命中 {txt.count(ANCHOR)} 次"

NEW = '''    return inter / min(len(ka), len(kb))


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
    ma, mb = re.fullmatch(r"T?(\\d+)", a), re.fullmatch(r"T?(\\d+)", b)
    if ma and mb:
        return 1.0 if ma.group(1) == mb.group(1) else 0.0

    # L1 字面层：Jaccard（对称，不虚高）
    jac = _jaccard(a, b, top_n)

    # L2 稀疏层：BM25（需要语料）
    bm = 0.0
    if corpus is not None:
        # 把 b 当语料、a 当 query；同时反向，取平均（对称化）
        bm1 = _bm25_best(a, corpus)
        bm2 = _bm25_best(b, corpus)
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
'''

txt = txt.replace(ANCHOR, NEW, 1)

# ---- 断言：新函数就位 ----
for fn in ("_bm25_corpus", "_bm25_best", "_jaccard", "_sim3", "_sim3_pair"):
    assert f"def {fn}(" in txt, f"未插入 {fn}"
assert txt.count("def _sim3(") == 1
assert txt.count("def _bm25_best(") == 1

out = txt.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n")
assert out.count(b"\r") == out.count(b"\r\n")
assert out.count(b"\r\r\n") == 0
SRC.write_bytes(out)

print("OK Step3: 插入 _bm25_corpus / _bm25_best / _jaccard / _sim3 / _sim3_pair")
print("lines =", out.count(b"\n"), "bytes =", len(out))
