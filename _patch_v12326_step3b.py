#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 打补丁 Step3b：复述检测切到 sim3（新增 _sim3 语料 + 判定）。

改动点：
  1) `_sent_is_rephrase` 新增可选 corpus 参数；主判据换成 sim3，
     保留 `_overlap_coef >= _REPHRASE_OVERLAP` 作为**包住形状**的保底
     （docstring 写明它管什么，不是复用滥用）。
  2) `_detect_ing_rephrase` 内部编一次 BM25 语料（上游句子集合），
     传给每一句判定 —— 语料共享，保证同一圈内所有判定用**同一把尺子**。

铁律：read_bytes -> 断言 CRLF==LF -> 转 LF -> 替换（断言各命中 1 次）
-> 转回 CRLF -> 断言 -> write_bytes。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.26.py"

b = SRC.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n")
assert b.count(b"\r\r\n") == 0
txt = b.decode("utf-8").replace("\r\n", "\n")

# ---------- 替换 1：_sent_is_rephrase ----------
OLD1 = '''def _sent_is_rephrase(s: str, u: str) -> bool:
    """一句 ing 输出是不是这句上游话的复述。

    [P2-3] 原来只用一个判据：_similar(s, u, 0.75)，
    分母是 max(|kw(A)|, |kw(B)|)。一句 20 字上游话被扩写成 60 字，
    关键词交集不变、分母变大 → 相似度掉到阈值以下 → 换说法抓不到。
    补上 overlap coefficient（分母取 min）：短句被长句整段包住时
    它接近 1，正是"换个说法再说一遍"的形状。
    """
    if _similar(s, u, _REPHRASE_SIM):
        return True
    return _overlap_coef(s, u, _KW_TOP_N) >= _REPHRASE_OVERLAP
'''

NEW1 = '''def _sent_is_rephrase(s: str, u: str, corpus=None) -> bool:
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
    if _similar(s, u, _REPHRASE_SIM):
        return True
    if _sim3(s, u, corpus=corpus) >= _REPHRASE_SIM3:
        return True
    # 包住形状保底：分母 min ⇒ 短句整段落在长句里时接近 1
    return _overlap_coef(s, u, _KW_TOP_N) >= _REPHRASE_OVERLAP
'''

assert txt.count(OLD1) == 1, f"_sent_is_rephrase 命中 {txt.count(OLD1)} 次"
txt = txt.replace(OLD1, NEW1, 1)

# ---------- 替换 2：_detect_ing_rephrase 内部编语料并传下去 ----------
OLD2 = '''    if not upstream_sents:
        return None
    hits = 0
    for s in ing_sents:
        if any(_sent_is_rephrase(s, u) for u in upstream_sents):
            hits += 1
    return hits / len(ing_sents)
'''

NEW2 = '''    if not upstream_sents:
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
'''

assert txt.count(OLD2) == 1, f"_detect_ing_rephrase 尾段命中 {txt.count(OLD2)} 次"
txt = txt.replace(OLD2, NEW2, 1)

# ---------- 新增常量 _REPHRASE_SIM3 ----------
OLD3 = '''_REPHRASE_SIM = 0.75
_REPHRASE_OVERLAP = 0.62
'''
NEW3 = '''_REPHRASE_SIM = 0.75
_REPHRASE_OVERLAP = 0.62
# sim3 的复述线。定在 0.62 —— 与 _REPHRASE_OVERLAP 同档，但 sim3 的
# 分母是并集、且 BM25 补权，同一档位下**误报显著少**（已由探针量化）。
_REPHRASE_SIM3 = 0.62
'''
assert txt.count(OLD3) == 1, f"常量区命中 {txt.count(OLD3)} 次"
txt = txt.replace(OLD3, NEW3, 1)

# ---------- 断言 ----------
assert "_sim3(s, u, corpus=corpus) >= _REPHRASE_SIM3" in txt
assert "corpus = _bm25_corpus(upstream_sents)" in txt
assert "def _sent_is_rephrase(s: str, u: str, corpus=None)" in txt
assert txt.count("_REPHRASE_SIM3") == 2

out = txt.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n")
assert out.count(b"\r") == out.count(b"\r\n")
assert out.count(b"\r\r\n") == 0
SRC.write_bytes(out)

print("OK Step3b: 复述检测切 sim3（_sent_is_rephrase + _detect_ing_rephrase + _REPHRASE_SIM3）")
print("lines =", out.count(b"\n"), "bytes =", len(out))
