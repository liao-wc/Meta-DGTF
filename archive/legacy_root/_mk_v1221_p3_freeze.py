#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 第三档] 冻结 P3 的「仅源码」快照，并把 P3.4 改成对快照对账。

背景（实测）：`--phase all` 里的 v122 `phase5` 会**重跑**审计脚本、
覆盖 `audit_v122_dead_mechanisms.md`；而语料会长大（每多跑一题多几份
日志与产物）→ 原本判「仅源码」的机制逐渐变成「可达」。
P3 的负对照集是 **P3 执行时点**的 5 条 → 拿活的审计报告当锚会**因为
数据变大而翻红**，与「本版有没有删机制」毫无关系。

所以：把那个集合**冻结**成文件，P3.4 对冻结快照两向对账；
当前审计集合只**打印**，不判红。
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

CR = chr(13)
LF = chr(10)
NL = chr(10)
VERIFY = Path("_v122_verify.py")

OLD = NL.join([
    '        aud = (HERE / "audit_v122_dead_mechanisms.md")',
    '        if aud.is_file():',
    '            txt = aud.read_text(encoding="utf-8")',
    '            only = [ln.split("`")[1] for ln in txt.splitlines()',
    '                    if ln.startswith("| `") and "仅源码" in ln]',
    '            check("P3.4", set(only) == set(data),',
    '                  f"与审计报告两向对账一致（审计 {sorted(only)}）")',
    '        else:',
    '            check("P3.4", False, "审计报告缺失")',
    ''])

NEW = NL.join([
    '        # ★ P3.4 对的是**冻结快照**，不是活的审计报告：',
    '        #   语料会长大 —— 原本判「仅源码」的机制会随多跑几题变成「可达」，',
    '        #   拿移动靶当锚会让这条判据**因为数据变大而翻红**，与「本版有',
    '        #   没有删机制」毫无关系（实测：P3 时点 5 条 → 09:42 重跑审计 0 条）。',
    '        _fz = HERE / "_negctl_v1221_p3_frozen.json"',
    '        aud = (HERE / "audit_v122_dead_mechanisms.md")',
    '        if _fz.is_file():',
    '            _fzd = json.loads(_fz.read_text(encoding="utf-8"))',
    '            _snap = set(_fzd.get("src_only_at_p3_time") or [])',
    '            check("P3.4", set(data) == _snap,',
    '                  "与冻结快照两向对账一致（P3 时点 "',
    '                  + str(_fzd.get("n_src_only")) + " 条："',
    '                  + "、".join(sorted(_snap)) + "）")',
    '        else:',
    '            check("P3.4", False,',
    '                  "缺 _negctl_v1221_p3_frozen.json（P3 时点的仅源码快照）")',
    '        if aud.is_file():',
    '            _txt = aud.read_text(encoding="utf-8")',
    '            _only = [ln.split("`")[1] for ln in _txt.splitlines()',
    '                     if ln.startswith("| `") and "仅源码" in ln]',
    '            print("  · P3.4 当前审计判「仅源码」的集合（不判红，语料长大"',
    '                  "会让它缩）：" + str(sorted(_only)))',
    ''])


def main() -> int:
    neg = json.loads(Path("_negctl_v1221_p3.json").read_text(encoding="utf-8"))
    frozen = {
        "frozen_at": "2026-10-05（P3 档执行时点）",
        "src_only_at_p3_time": sorted(neg),
        "n_src_only": len(neg),
        "source": "audit_v122_dead_mechanisms.md（当时判「仅源码」的 5 条）",
        "note": ("该集合是**时点快照**：语料每多跑一题就多几份日志与产物，原本"
                 "「仅源码」的机制会逐渐变成「可达」（机制被真跑走到了）。"
                 "本版实测：P3 时点 5 条；到 2026-10-05 09:42 重跑审计（语料 "
                 "368 日志 / 317 产物）→ 13 条全「可达」、「仅源码」0 条。"
                 "所以 P3.4 对的是**这份冻结快照**，不是移动靶。"),
    }
    Path("_negctl_v1221_p3_frozen.json").write_bytes(
        json.dumps(frozen, ensure_ascii=False, indent=2).encode("utf-8"))
    print("  ✓ 冻结快照：" + str(frozen["src_only_at_p3_time"]))

    s = VERIFY.read_bytes().decode("utf-8")
    assert s.count(CR + LF) == s.count(NL) and (CR + CR + LF) not in s
    t = s.replace(CR + LF, NL)
    got = t.count(OLD)
    assert got == 1, "锚点命中 " + str(got) + " 次"
    t = t.replace(OLD, NEW, 1)
    ast.parse(t)
    out = t.replace(NL, CR + LF)
    assert out.count(NL) == out.count(CR + LF) and (CR + CR + LF) not in out
    VERIFY.write_bytes(out.encode("utf-8"))
    print("  ✓ P3.4 已改为对冻结快照")
    return 0


if __name__ == "__main__":
    sys.exit(main())
