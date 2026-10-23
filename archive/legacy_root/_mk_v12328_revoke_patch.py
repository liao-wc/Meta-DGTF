#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.28 补丁 ②：D2 `revoked` 规则重新设计（**与 stable 对称化**）。

【问题】改前规则：`if _atk and len(_atk) >= len(_sup): return "revoked"`
  · `_sup` 每圈**恒 +1**（每层都算一个来源）；
  · `_atk` 每圈**至多 +1**。
  ⇒ 真实入口下该条件**只在「每一圈都带攻击」时成立** ——
    「攻击面 ≥ 支持面」实际退化成「攻击从未缺席」。
    v1.23.27 因登记被守卫吞掉（条目恒 0 个）从未暴露；
    v1.23.28 修好登记后它立刻变成「只要一直被骂就推翻」，
    与 DGTF「对撞」语义（双方都要**独立复现**才算数）不符。

【重新设计】对称化 —— **攻击与支持用同一把尺子（独立性，不是次数）**：
  · `stable`  = 支持被 ≥2 个**不同来源**、跨 ≥2 圈独立复现；
  · `revoked` = 攻击被 ≥2 个**不同来源**、跨 ≥2 圈独立复现（镜像规则）。
  ⇒ 实现：`attack_sources` 与 `support` 同为**来源标签列表**，
    由 `upsert_belief(sources=...)`（层名）同时驱动两侧。

★ 为什么符合整体机制：对撞的判据从来不是「谁说得次数多」，而是
  「谁经得起独立复现」。支持方如此，反对方亦然 —— 对称才是同一把尺子。
★ 为什么更好：① 真实入口可达（不同层都提出攻击即可）；
  ② 不再是「一直骂就赢」；③ 与 stable 完全对称 ⇒ 可做负对照
  （同一层反复贡献攻击不许 revoked）。

★ CRLF 往返：read_bytes → 断言 CRLF==LF → 转 LF → 替换 → write_bytes。
★ 每处替换前断言命中 == 1。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TGT = HERE / "元DGTF-V1.23.28.py"

raw = TGT.read_bytes()
n_crlf = raw.count(b"\r\n")
n_lf = raw.count(b"\n")
if n_crlf != n_lf:
    sys.exit("❌ 不是纯 CRLF：CRLF=%d LF=%d" % (n_crlf, n_lf))
text = raw.decode("utf-8").replace("\r\n", "\n")

applied = []


def repl(old, new, tag):
    global text
    n = text.count(old)
    if n != 1:
        sys.exit("❌ [%s] 锚点命中 %d 次（须 == 1）" % (tag, n))
    text = text.replace(old, new)
    applied.append(tag)


# ── ① 常量：新增攻击侧门槛 ────────────────────────────────
repl('''#: `active → stable` 需要的**不同来源数**（D2 的 ≥2 个独立来源）。
_BELIEF_STABLE_SOURCES = 2
''',
     '''#: `active → stable` 需要的**不同来源数**（D2 的 ≥2 个独立来源）。
_BELIEF_STABLE_SOURCES = 2
#: `* → revoked` 需要的**不同攻击来源数**（与 stable 的**镜像门槛**）。
#   ★ 为什么是「不同来源数」而不是「攻击次数」：见 `belief_transition`
#     ② 号注 —— 次数口径在真实入口会退化成「一直骂就赢」。
_BELIEF_REVOKE_SOURCES = 2
''',
     "const")

# ── ② belief_transition：签名加 attack_sources ─────────────
repl('''def belief_transition(item, *, round_no=0, sources=None, attack=None,
                      resolved_by=None):''',
     '''def belief_transition(item, *, round_no=0, sources=None, attack=None,
                      resolved_by=None, attack_sources=None):''',
     "sig")

repl('''      · `attack`      本圈新出现的攻击证据标签列表 —— 进 `attack`
      · `resolved_by` 非空 ⇒ 被 decidable_channel 回答 ⇒ `resolved`''',
     '''      · `attack`      本圈新出现的攻击证据标签列表 —— 进 `attack`
      · `attack_sources` 本圈**提出攻击的来源标签**（层名）—— 进
                      `attack_sources`。★ 与 `sources` 对称：判决用
                      「独立性」这一把尺子量两侧，不用次数。
      · `resolved_by` 非空 ⇒ 被 decidable_channel 回答 ⇒ `resolved`''',
     "doc")

repl('''    _sup = list(item.get("support") or [])
    _atk = list(item.get("attack") or [])
    _rnd = [r for r in (item.get("rounds_seen") or [])]''',
     '''    _sup = list(item.get("support") or [])
    _atk = list(item.get("attack") or [])
    _atk_src = list(item.get("attack_sources") or [])
    _rnd = [r for r in (item.get("rounds_seen") or [])]''',
     "accum-init")

repl('''    for _a in (attack or []):
        _a = str(_a).strip()
        if _a and _a not in _atk:
            _atk.append(_a)
    if _rn and _rn not in _seen:
        _rnd.append(_rn)''',
     '''    for _a in (attack or []):
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
        _rnd.append(_rn)''',
     "accum-atk-src")

# ── ③ 规则本体：对称化 ─────────────────────────────────────
repl('''    # ② revoked：有攻击且攻击面 ≥ 支持面（「质疑者胜出」）
    if _atk and len(_atk) >= len(_sup):
        return "revoked"
''',
     '''    # ② revoked：**攻击被独立复现**（与 stable 的镜像规则）
    #   ★ 旧规则 `len(_atk) >= len(_sup)` 的致命退化：`_sup` 每圈恒 +1、
    #     `_atk` 至多 +1 ⇒ 该条件**只在「每圈都攻击」时成立** ——
    #     「攻击面 ≥ 支持面」被读成「攻击从未缺席」。
    #   ★ 新规则要求攻击**跨 ≥2 个不同来源**出现 —— 与 stable 用同一把
    #     尺子（独立性，不是次数）。「同一个来源反复骂」不再算数。
    if _atk:
        _atk_rounds = sorted(_seen | ({_rn} if _rn else set()))
        if (len(_atk_src) >= _BELIEF_REVOKE_SOURCES
                and len(_atk_rounds) >= _BELIEF_STABLE_K):
            return "revoked"
        # 攻击不足以推翻（非单调：由 stable 掉回 active，可再被推翻）
        if _cur == "stable":
            return "active"
        return _cur
''',
     "rule")

# ── ④ 删掉旧的 ④ 号分支（已被并入 ②） ─────────────────────
repl('''    # ④ 有攻击但不占多数 ⇒ 从 stable 掉回 active（非单调，可被推翻）
    if _atk and _cur == "stable":
        return "active"

    return _cur
''',
     '''    return _cur
''',
     "drop-old-4")

# ── ⑤ upsert_belief：调用点传 attack_sources ──────────────
repl('''        _new = belief_transition(_tgt, round_no=round_no, sources=sources,
                                 attack=attack, resolved_by=resolved_by)''',
     '''        _new = belief_transition(_tgt, round_no=round_no, sources=sources,
                                 attack=attack, resolved_by=resolved_by,
                                 attack_sources=(
                                     sources if attack else None))''',
     "upsert-call")

repl('''        _tgt["support"] = _sup
        _tgt["attack"] = _atk
        _tgt["rounds_seen"] = _rnd''',
     '''        _atk_src = list(_tgt.get("attack_sources") or [])
        if attack:
            for _as_ in (sources or []):
                _as_ = str(_as_).strip()
                if _as_ and _as_ not in _atk_src:
                    _atk_src.append(_as_)
        _tgt["support"] = _sup
        _tgt["attack"] = _atk
        _tgt["attack_sources"] = _atk_src
        _tgt["rounds_seen"] = _rnd''',
     "upsert-store")

out = text.replace("\n", "\r\n").encode("utf-8")
if out.count(b"\r\r\n"):
    sys.exit("❌ 产出含 \\r\\r\\n")

TGT.write_bytes(out)

print("已应用 %d 项：%s" % (len(applied), ", ".join(applied)))
print("主文件：%d 行 / %d bytes / CRCRLF=%d"
      % (out.count(b"\n"), len(out), out.count(b"\r\r\n")))
