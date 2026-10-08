#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 P2b] triage 第二条路径：answers 匹配（补丁脚本）。

任务书：https://chat.deepseek.com/share/e3uqm2wh5a7jzpuzlr
改前 `元DGTF-V1.22.1-rc1.py` → 改后 `元DGTF-V1.22.1-rc1b.py`（本脚本就地改 rc1b）。

四处改动（全部**加性**，唯一整块锚点，命中数必须 == 1）：
  ① `_hit_by_answers` / `_hit_by_claim` 两个函数（插在 `_citation_table` 之前）
  ② `_load_anchors` 的锚点字典加 `"answers"` 键
  ③ `_load_anchors` 尾部加「answers 全缺」留痕（不阻断）
  ④ `_anchor_crosscheck` 的 `_hit` 改双路径（answers OR claim）
另加：`__init__` 与 `_load_anchors` 头部的属性初始化；`base` 里加留痕键。

★ 宪法级约束：不动 claim 路径的 `0.6`；不塞 `[外]` 进 `_TRIAGE_KEYS`；
  answers 路径复用 `_UNTRACED_OVERLAP`（= 0.6），不新造阈值。

幂等：已改过则打印「已应用」并退出 0。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

TARGET = Path("元DGTF-V1.22.1-rc1b.py")
SENTINEL = "_hit_by_answers"

# ---------------------------------------------------------------- ① 两个函数
NEW_FUNCS = '''# ============================================================
# [v1.22.1 P2b] triage 第二条路径：answers 匹配
# ============================================================
# P2a 实测：`_similar(und_aspect, anchor.claim, 0.6)` 对「缺什么材料」型侧面
#   命中率为 0（14 条侧面最高词重叠 0.167 / 中位 0.000）—— 因为
#   `und_aspect` 说的是「缺什么」，`anchor.claim` 说的是「是什么事实」，
#   两类文本的关键词几乎不相交。
#
# 本版**不改匹配算法的阈值**，只**换匹配对象**：让锚点自己声明
#   「我能回答哪些侧面」（`answers`），拿「缺什么」与「我能回答什么」比。
#
# ★ 为什么用 `_overlap_coef`（分母取 min）而不是 `_similar`（分母取 max）：
#   `und_aspect` 通常比一条 answer 长，「短 answer 被长 aspect 包住」是
#   常见形态；min 分母对这种形态给出接近 1 的值，max 分母会被长分母压低。
# ★ 阈值复用 `_UNTRACED_OVERLAP`（= 0.6，v1.21.61 起就有），**不新造阈值**。
# ★ 向后兼容：锚点没声明 `answers` → 回落 `_hit_by_claim`，与 P2a 逐字同行为。

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
    """[v1.22.1 P2b] 老路径，P2a 一字不动（阈值 0.6 也不许动）。

    ★ 保留它的意义：① 向后兼容（老锚点无 answers 时不崩）；
      ② 与 answers 路径**取 OR**，两条都能命中，不是替换关系。
    """
    return _similar(aspect, claim, 0.6)


'''

# ------------------------------------------------------------ ② 字典加 answers
OLD_DICT = '''                        "claim": claim[:400],
                        "source": str(a.get("source") or "")[:200],
'''
NEW_DICT = '''                        "claim": claim[:400],
                        # [v1.22.1 P2b] answers：该锚点能回答的侧面（可选）。
                        #   缺省 [] → 匹配时回落 claim 路径，行为不变。
                        "answers": [str(x)[:60] for x in
                                    (a.get("answers") or [])][:5],
                        "source": str(a.get("source") or "")[:200],
'''

# ------------------------------------------------------- ③ answers 全缺留痕
OLD_TAIL = '''        self._anchors = out
        if not out:
'''
NEW_TAIL = '''        self._anchors = out
        # [v1.22.1 P2b §2.6] answers 全缺时的留痕（**不阻断**）：提醒调用者
        #   triage 只能走 claim 路径 —— 历史实测该路径对「缺什么」型侧面
        #   命中率 ≈ 0。字段缺失与「字段在但没用上」必须能分开读。
        _n_no_ans = sum(1 for x in out if not x.get("answers"))
        if out and _n_no_ans == len(out):
            self._anchor_answers_warning = (
                "全部 " + str(len(out)) + " 条锚点未声明 answers，triage 只能走"
                " claim 路径（历史实测：claim 路径对「缺什么」型侧面命中率"
                " ≈ 0）")
            logger.warning("锚点 answers 全部缺失：%s",
                           self._anchor_answers_warning)
        if not out:
'''

# --------------------------------------------------------------- ④ _hit 双路
OLD_HIT = '''            _hit = next((x for x in (self._anchors or [])
                         if int(x.get("tier", 3) or 3) <= _floor_c
                         and _similar(str(_a), str(x.get("claim", "")), 0.6)),
                        None)
'''
NEW_HIT = '''            # [v1.22.1 P2b] 双路径取 OR：answers（锚点自声明能回答什么）
            #   或 claim（老路径，阈值 0.6 一字不动）。两路都在 **tier 门之内**。
            _hit = next((x for x in (self._anchors or [])
                         if int(x.get("tier", 3) or 3) <= _floor_c
                         and (_hit_by_answers(str(_a), x.get("answers") or [])
                              or _hit_by_claim(str(_a),
                                               str(x.get("claim", ""))))),
                        None)
'''

# ------------------------------------------------- ⑤ 属性初始化 + base 留痕键
OLD_INIT = '''        self._anchor_source: Dict[str, str] = {}
'''
NEW_INIT = '''        self._anchor_source: Dict[str, str] = {}
        # [v1.22.1 P2b] answers 全缺时的告警（"" = 无告警）。不阻断，只留痕。
        self._anchor_answers_warning: str = ""
'''

OLD_LOAD_INIT = '''        self._anchors = []
        self._anchor_err = ""
'''
NEW_LOAD_INIT = '''        self._anchors = []
        self._anchor_err = ""
        self._anchor_answers_warning = ""
'''

OLD_BASE = '''            "retriever": (self._anchor_source or {}).get("retriever", ""),
'''
NEW_BASE = '''            "retriever": (self._anchor_source or {}).get("retriever", ""),
            # [v1.22.1 P2b] answers 全缺 → True（产物侧留痕，不阻断）。
            "answers_all_missing": bool(getattr(
                self, "_anchor_answers_warning", "")),
'''

REPS = [
    ("_hit_by_answers/_hit_by_claim 两个函数",
     "def _citation_table(view, pool) -> List[tuple]:", NEW_FUNCS + "def _citation_table(view, pool) -> List[tuple]:"),
    ("_load_anchors 字典加 answers 键", OLD_DICT, NEW_DICT),
    ("_load_anchors 尾部 answers 全缺留痕", OLD_TAIL, NEW_TAIL),
    ("_anchor_crosscheck 的 _hit 改双路径", OLD_HIT, NEW_HIT),
    ("__init__ 属性初始化", OLD_INIT, NEW_INIT),
    ("_load_anchors 头部属性初始化", OLD_LOAD_INIT, NEW_LOAD_INIT),
    ("base 加 answers_all_missing 留痕键", OLD_BASE, NEW_BASE),
]


def main() -> int:
    raw = TARGET.read_bytes()
    s = raw.decode("utf-8")
    if SENTINEL in s:
        print("  · 已应用（幂等跳过）")
        return 0
    assert s.count("\r\n") == s.count("\n"), "rc1b 行尾不纯（CRLF 混杂）"
    assert b"\r\r\n" not in raw, "rc1b 含 CRCRLF"
    s = s.replace("\r\n", "\n")

    for name, old, new in REPS:
        got = s.count(old)
        assert got == 1, f"[{name}] 锚点命中 {got} 次，期望 1"
        s = s.replace(old, new, 1)
        print(f"  ✓ {name}")

    ast.parse(s)

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n")
    assert "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    print(f"  ✓ 写回 {TARGET.name}（纯 CRLF）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
