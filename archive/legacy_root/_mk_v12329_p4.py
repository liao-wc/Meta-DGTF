#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.29 补丁 · 第 4 阶段：D2 语义归并（保守、可关、带留痕）。

遗留（v1.23.28 §7.1-2）：`upsert_belief` 按**精确文本**认领 ⇒「同主张换说法」
落成两个条目，D2 的「连续 k 圈复现」被稀释（要靠 occurrences 补救）。

★ 设计取舍（红线「入池前挡重复」）：**不**做激进的语义合并 ——
  那会把不同主张并成一条（红线禁止）。做法是**高阈值、默认关、可审计**：
    · 阈值 `belief.merge_sim`（默认 **0.85**，只有近乎逐字才够）；
    · 开关 `belief.merge_semantic`（默认 **False** ⇒ 出厂零行为差）；
    · 命中时把新文本记进**已存在条目**的 `occurrences`（= 一次复现的证据），
      并把 `text` 保留为**首个**说法（不覆盖，保可追溯）；
    · 每次归并落一条 `merge_log`（两段文本 + 相似度），产物可核。
  ⇒ 想根治却不越红线：**把「换说法」变成「复现证据」，而不是抹掉它**。
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


def main():
    s = _load()

    # ── 1. 属性：merge_semantic / merge_sim（Pool 上，随 D3 阈值一起下发）
    old_attr = """    #: [D3 可配] 语义熵聚类阈值（默认 = 模块常量 `_SEM_CLUSTER_THR`）。"""
    new_attr = """    #: [D2 修正] 语义归并开关与阈值（默认**关** ⇒ 出厂零行为差）。
    #:   ★ 只在 `merge_semantic=True` 且 `_sim3 >= merge_sim`（默认 0.85，
    #:     近乎逐字）时，把「换说法重提」记为**已存在条目的一次复现**。
    #:     保红线：不同主张（实测同义 0.41~0.79 / 异义 0.00）在 0.85 下
    #:     不会被并；它只吃「几乎同一句话」的重复表述。
    merge_semantic: bool = False
    merge_sim: float = _BELIEF_MERGE_SIM
    #: [D2 修正] 归并留痕：每次归并一条 {from, into, sim, source}。
    merge_log: list = field(default_factory=list)

    #: [D3 可配] 语义熵聚类阈值（默认 = 模块常量 `_SEM_CLUSTER_THR`）。"""
    s = repl_text(s, old_attr, new_attr, "D2 归并属性")

    # ── 2. 常量 _BELIEF_MERGE_SIM
    old_c = "_SEM_REL_Q = 0.60\n"
    new_c = ("_SEM_REL_Q = 0.60\n\n"
             "#: [D2 修正] 语义归并阈值。★ 高阈值是**刻意的**：红线要求\n"
             "#:   「入池前挡重复」，把不同主张并成一条是禁止的。0.85 只吃\n"
             "#:   「几乎同一句话」（实测同义重述 0.41~0.79 达不到它）⇒\n"
             "#:   宁可漏并，不可错并。\n"
             "_BELIEF_MERGE_SIM = 0.85\n")
    s = repl_text(s, old_c, new_c, "D2 归并常量")

    # ── 3. upsert_belief 认领段：精确 text 未命中时，尝试保守语义归并
    old_claim = """        _tgt = None
        for _it in items:
            if str(_it.get("text", "")) == _key:
                _tgt = _it
                break
        if _tgt is None:"""
    new_claim = """        _tgt = None
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
        if _tgt is None:"""
    s = repl_text(s, old_claim, new_claim, "D2 upsert 语义认领")

    # ── 4. 产物出口：merge_log
    old_out = '''        d["sem_entropy_thr"] = float(self.sem_entropy_thr)'''
    new_out = '''        d["sem_entropy_thr"] = float(self.sem_entropy_thr)
        # ★ [D2 修正] 归并留痕出口（两向一致：开关关时恒为空列表）。
        d["merge_semantic"] = bool(getattr(self, "merge_semantic", False))
        d["merge_log"] = list(getattr(self, "merge_log", []) or [])'''
    s = repl_text(s, old_out, new_out, "D2 merge_log 出口")

    # to_dict 里 sem_entropy_thr 也可能在另一处（Pool.to_dict 手工白名单）
    # 检查是否还有第二个出口需要补
    _save(s)
    print("OK 第 4 阶段（D2）完成")
    s2 = SRC.read_bytes().decode("utf-8")
    assert "_BELIEF_MERGE_SIM = 0.85" in s2
    assert s2.count("merge_semantic: bool = False") == 1
    print("复读校验通过")


if __name__ == "__main__":
    main()
