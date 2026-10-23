#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.29 补丁 · 第 1 阶段：版本号 + C1 口径错位(touch_rate/aspect_carry_rate)
+ C2 DEFAULT_CONFIG 缩进破损。

铁律：read_bytes → 断言 CRLF==LF → 转 LF → 替换（断言命中==1）→ 转回 CRLF
→ write_bytes。一次写盘，行表统一操作。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.29.py"


def _load(p=SRC):
    b = p.read_bytes()
    crlf, lf, crcrlf = b.count(b"\r\n"), b.count(b"\n"), b.count(b"\r\r\n")
    assert crlf == lf, "源文件不是纯 CRLF（CRLF=%d LF=%d）" % (crlf, lf)
    assert crcrlf == 0, "源文件含 CRCRLF %d 处" % crcrlf
    return b.decode("utf-8").replace("\r\n", "\n")


def _save(s, p=SRC):
    assert "\r\r\n" not in s
    out = s.replace("\n", "\r\n")
    p.write_bytes(out.encode("utf-8"))


def repl_text(s, old, new, what, expect=1):
    n = s.count(old)
    assert n == expect, "%s：命中 %d 次（要求 %d）" % (what, n, expect)
    return s.replace(old, new)


def main():
    s = _load()

    # ── 1. 版本号两处 ─────────────────────────────────────────
    s = repl_text(s, "元 DGTF · v1.23.28", "元 DGTF · v1.23.29", "docstring 标题")
    s = repl_text(s, '__version__ = "1.23.28"', '__version__ = "1.23.29"',
                  "__version__")

    # ── 2. C2 DEFAULT_CONFIG 缩进破损（4 空格 → 16 空格）──────
    s = repl_text(
        s,
        '                "adjudicate_sub_tristate": "enabled",\n'
        '    "adjudicate_sub_tristate_multi": "disabled",\n'
        '    "anchor_crosscheck": "disabled",\n'
        '                "dual_judge": "enabled",',
        '                "adjudicate_sub_tristate": "enabled",\n'
        '                "adjudicate_sub_tristate_multi": "disabled",\n'
        '                "anchor_crosscheck": "disabled",\n'
        '                "dual_judge": "enabled",',
        "C2 DEFAULT_CONFIG 缩进")

    # ── 3. C1 touch_rate 口径错位 ────────────────────────────
    old_touch = '''        _rl = getattr(self, "round_log", None) or []
        if _rl:
            _hit = 0
            for _r in _rl:
                try:
                    if int(_r.get("anchor_touched_n", 0) or 0) > 0:
                        _hit += 1
                except (TypeError, ValueError):
                    continue
            return _hit / len(_rl) if _rl else None
        _n = len(self.anchor_touched or [])
        return 1.0 if _n > 0 else 0.0'''
    new_touch = '''        _rl = getattr(self, "round_log", None) or []
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
        return 1.0 if _n > 0 else 0.0'''
    s = repl_text(s, old_touch, new_touch, "C1 touch_rate")

    old_acr = '''        _units = self.aspect_units or []
        if not _units:
            return None
        _hit_ids = set(getattr(self, "_carried_aspect_ids", []) or [])
        if not _hit_ids:
            _ch = getattr(self, "_layer_und_channel", None) or {}
            _hit_ids = set(_ch.get("carry_touched_ids") or [])
        if not _hit_ids:
            return 0.0'''
    new_acr = '''        _units = self.aspect_units or []
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
            return None'''
    s = repl_text(s, old_acr, new_acr, "C1 aspect_carry_rate")

    _save(s)
    print("OK 第 1 阶段完成")
    # 复读校验
    s2 = SRC.read_bytes().decode("utf-8")
    assert "元 DGTF · v1.23.29" in s2
    assert s2.count('\n                "anchor_crosscheck": "disabled"') == 1
    assert "_has_per_round" in s2
    print("复读校验通过 · 行数 %d" % s2.count("\n"))


if __name__ == "__main__":
    main()
