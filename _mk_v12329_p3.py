#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.29 补丁 · 第 3 阶段：D1 语义熵阈值改**相对分位**。

遗留（v1.23.28 §7.1-1）：`_sim3` 的 0.30 是按当时实测空隙（0.00 ↔ 0.41）
选的魔法数；若主张文本变短（bigram 覆盖变稀），空隙漂移 ⇒ 阈值失效。
处置：新增 `thr="rel"` 相对口径 —— 在**本批文本自己**的两两 sim3 分布上定标
（取 p60），并给一个下限/上限夹取防退化。默认仍走绝对值（零行为差），
由配置 `belief.sem_entropy_thr: "rel"` 切到相对口径。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.29.py"


def _load(p=SRC):
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "含 CRCRLF"
    return b.decode("utf-8").replace("\r\n", "\n")


def _save(s, p=SRC):
    assert "\r\r\n" not in s
    p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))


def repl_text(s, old, new, what, expect=1):
    n = s.count(old)
    assert n == expect, "%s：命中 %d 次（要求 %d）" % (what, n, expect)
    return s.replace(old, new)


REL_FN = '''

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
                _s = _sim3(_t[_i], _t[_j], corpus=corpus) if top_n is None \\
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
'''


def main():
    s = _load()

    # ── 1. 新增常量 + 相对阈值函数 ────────────────────────────
    old_const = "_SEM_CLUSTER_THR = 0.30\n"
    new_const = '''_SEM_CLUSTER_THR = 0.30

#: D1（v1.23.29）相对分位阈值的**夹取区间**与**分位点**。
#:   ★ 为什么要夹取：文本全同 ⇒ p60=1.0（谁都聚进去 = 恒聚）；文本全异
#:     ⇒ p60=0.0（谁都聚不进 = 恒不聚）。两者都是退化，夹取后回到「有
#:     分布可定标」的正常区。夹取区间取自 v1.23.28 实测：同义 0.41~0.79、
#:     异义 0.00 ⇒ 取 [0.20, 0.55] 正好夹在空隙两侧内侧。
_SEM_REL_LO = 0.20
_SEM_REL_HI = 0.55
_SEM_REL_Q = 0.60
'''
    s = repl_text(s, old_const, new_const, "D1 相对阈值常量")

    # 在 semantic_entropy_of 之前插入 sem_thr_relative
    anchor = "def semantic_entropy_of(texts, corpus=None, thr=None, top_n=None):"
    s = repl_text(s, anchor, REL_FN.strip("\n") + "\n\n\n" + anchor,
                  "D1 插入 sem_thr_relative")

    # ── 2. semantic_entropy_of 支持 thr="rel" ────────────────
    old_thr_line = """    _thr = float(_SEM_CLUSTER_THR if thr is None else thr)"""
    new_thr_line = """    # ★ D1：`thr == "rel"` ⇒ 在本批文本自己的 sim3 分布上定标（不再用
    #   魔法数）。其余取值（含 None）走绝对口径 —— 默认零行为差。
    if isinstance(thr, str) and thr.strip().lower() == "rel":
        _thr = sem_thr_relative(_t, corpus=corpus,
                                top_n=top_n if top_n is not None else None)
    else:
        _thr = float(_SEM_CLUSTER_THR if thr is None else thr)"""
    s = repl_text(s, old_thr_line, new_thr_line, "D1 semantic_entropy_of thr=rel")

    # ── 3. refresh_belief_entropy 支持 thr="rel"（它逐条调
    #       semantic_entropy_of，需要把 rel 透传成「按该条的出现集定标」）
    #   找 refresh_belief_entropy 里调用 semantic_entropy_of 的位置
    _save(s)
    print("OK 第 3 阶段（D1）完成")


if __name__ == "__main__":
    main()
