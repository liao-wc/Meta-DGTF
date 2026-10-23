#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P2] triage 触发条件改挂结构标签。

加性改动（不删旧词表、不删旧行）：
1. 保留 `_TRIAGE_KEYS` 四类原样，新增 `_TRIAGE_STRUCTURAL_PREFIXES`（结构标签）
   与 `_TRIAGE_SEMANTIC_KEYS`（旧四类 + 三个同义写法）；
2. 新增 `_is_triage_candidate`（两路并集）与 `_TRIAGE_NEVER_DOWNGRADE` /
   `_is_never_downgrade`（真·自指不许降级）；
3. `_anchor_crosscheck` 的 triage 循环改成：先剔 never-downgrade，再判 candidate。

★ 不许把 `[外]` 塞进旧词表 —— 那是拿一题样本拟合。结构标签立为**第一类**。
★ 锚点整块断言 == 1；CRLF 往返；无新增阈值。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.1-rc1.py"

OLD_HEAD = '''# triage 降级只认这四类理由：它们都指向「缺外部材料」，而不是「问题本身
# 不可判定」。别的理由（例如"概念本身未定义"）不该被一次检索推翻。
_TRIAGE_KEYS = ("信息不足", "需外部动作", "缺数据", "无外部")
'''

NEW_HEAD = '''# triage 降级只认这两类理由：它们都指向「缺外部材料」，而不是「问题本身
# 不可判定」。别的理由（例如"概念本身未定义"）不该被一次检索推翻。
#   · 第一类：引擎自己的**结构标签**前缀（`[外]` 等）；
#   · 第二类：语义关键词（下面 `_TRIAGE_SEMANTIC_KEYS`）。
# [v1.22.1 P2] 旧词表 `_TRIAGE_KEYS` 一字未删，继续做第二类里的一员。
_TRIAGE_KEYS = ("信息不足", "需外部动作", "缺数据", "无外部")

# [v1.22.1 P2] 依据：v1.22.0 阶段 4 实测 —— 真跑里 5 条 undecidable_aspects
#   **全部以 `[外]` 开头**（引擎自己的结构标签），而旧词表 0/5 命中。
#   ★ 不许把 `[外]` 塞进旧词表（那是拿一题样本拟合）；正解是把「结构标签」
#     本身立为第一类触发条件。
_TRIAGE_STRUCTURAL_PREFIXES = ("[外]",)   # 引擎自己的标签，可加 [内] 等

_TRIAGE_SEMANTIC_KEYS = _TRIAGE_KEYS + (  # 语义关键词：旧四类 + 三个同义写法
    "需要外部", "取决于外部", "依赖外部",
)

# 「原则判不出」的那些：锚点无关，**不许降级**（v1.21.59 的定义）。
_TRIAGE_NEVER_DOWNGRADE = ("自指", "自证", "本体论", "无共同参照系")


def _is_triage_candidate(aspect: str) -> bool:
    """[v1.22.1 P2] 该 undecidable 侧面是否属于「缺外部材料」那一类。

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
'''

OLD_LOOP = '''        for _a in _und_aspects:
            if not any(k in str(_a) for k in _TRIAGE_KEYS):
                continue
'''

NEW_LOOP = '''        for _a in _und_aspects:
            # [v1.22.1 P2] 先剔「真·自指」那类（锚点无关，不许降级），
            #   再判是否属于「缺外部材料」（结构标签 或 语义关键词）。
            if _is_never_downgrade(_a):
                continue
            if not _is_triage_candidate(_a):
                continue
'''

REPS = [("常量与判据函数", OLD_HEAD, NEW_HEAD),
        ("crosscheck 触发条件", OLD_LOOP, NEW_LOOP)]


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "TARGET 不是纯 CRLF"
    assert b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")
    for name, old, new in REPS:
        got = s.count(old)
        assert got == 1, f"[{name}] 锚点 {got} 次，期望 1"
        s = s.replace(old, new, 1)
        print(f"  ✓ {name}")
    ast.parse(s)
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    chk = TARGET.read_bytes().decode("utf-8")
    for must in ("_TRIAGE_STRUCTURAL_PREFIXES", "_TRIAGE_SEMANTIC_KEYS",
                 "_TRIAGE_NEVER_DOWNGRADE", "def _is_triage_candidate",
                 "def _is_never_downgrade",
                 '_TRIAGE_KEYS = ("信息不足", "需外部动作", "缺数据", "无外部")'):
        assert must in chk, f"自检缺 {must}"
    assert "for k in _TRIAGE_KEYS)" not in chk, "旧判据没换掉"
    print("✓ P2 补丁完成；ast OK；纯 CRLF")
    return 0


if __name__ == "__main__":
    sys.exit(main())
