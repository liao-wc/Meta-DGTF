#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.23 判据的**判别力**证明：7 个变异体，每一个都必须让
`smoke_test.check_v12323_view_echo_full()` 判红。

做法（照 SKILL 7c）：读 `smoke_test.py` 源码、只替换 `SRC` 那一行指向**畸形引擎**，
再 `exec` 成独立 module（每个变异体一个 module，互不污染），然后跑**原样的**判据。

    python _probe_v12323_mutants.py
"""
from __future__ import annotations

import re
import shutil
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "元DGTF-V1.23.23.py"
SMOKE = HERE / "smoke_test.py"
TMP = HERE / "_audit_tmp"
TMP.mkdir(exist_ok=True)

SRC_PAT = re.compile(r'SRC = HERE / "元DGTF-V1\.23\.23\.py"')


def _one(text: str, old: str, new: str) -> str:
    n = text.count(old)
    assert n == 1, "变异体锚点命中 %d 次（要求 1）：%r" % (n, old[:60])
    return text.replace(old, new)


# (编号, 说明, 变异函数)
MUTANTS = [
    ("M1", "阴阳正文（单跑）回退成硬砍 raw[:200]",
     lambda s: _one(s, 'self.vp(f"   {_vp_preview(raw)}")', 'self.vp(f"   {raw[:200]}")')),
    ("M2", "阴阳正文（合并）回退成硬砍 (raw or '')[:160]",
     lambda s: _one(s, 'self.vp(f"   {_vp_preview(raw or \'\')}")',
                    'self.vp(f"   {(raw or \'\')[:160]}")')),
    ("M3", "候选清单回退成硬砍 c.desc[:50]",
     lambda s: _one(s, 'self.vp(f"   [{i}] {_vp_preview(c.desc)}")',
                    'self.vp(f"   [{i}] {c.desc[:50]}")')),
    ("M4", "未判子问题回退成硬砍 question[:50]",
     lambda s: _one(s, '{_vp_preview(s[\'question\'])}', "{s['question'][:50]}")),
    ("M5", "回流候选回退成硬砍 d[:40]",
     lambda s: _one(s, '拦下重现候选：{_vp_preview(d)}', '拦下重现候选：{d[:40]}')),
    ("M6", "推进目标回退成硬砍 e['target'][:40]",
     lambda s: _one(s, "{_vp_preview(e['target'])}", "{e['target'][:40]}")),
    ("M7", "`_vp_preview` 改成**按 limit 硬切**（丢掉「切在换行上」）",
     lambda s: _one(s, '''    cut = s.rfind("\\n", 0, limit + 1)''',
                    '''    cut = limit''')),
    ("M8", "`_vp_preview` 去掉上限与痕迹（恒返回原文）",
     lambda s: _one(s, "    if len(s) <= limit:\n        return s",
                    "    return s\n    if len(s) <= limit:\n        return s")),
]


def _load_smoke_for(engine_path: Path, tag: str):
    txt = SMOKE.read_text(encoding="utf-8", newline="")
    txt = txt.replace("\r\n", "\n")
    assert len(SRC_PAT.findall(txt)) == 1, "smoke 的 SRC 行不是 1 行"
    txt = SRC_PAT.sub('SRC = Path(r"%s")' % str(engine_path).replace("\\", "\\\\"), txt)
    m = types.ModuleType("smoke_" + tag)
    m.__file__ = str(SMOKE)
    sys.modules[m.__name__] = m
    exec(compile(txt, str(SMOKE), "exec"), m.__dict__)
    return m


def main() -> int:
    base = ENGINE.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")

    print("── 正对照：原样引擎下判据必须**绿** ──")
    m0 = _load_smoke_for(ENGINE, "base")
    ok0 = m0.check_v12323_view_echo_full()
    print("   正对照 = %s" % ("绿 ✓" if ok0 else "红 ✗"))

    rows = []
    for tag, why, fn in MUTANTS:
        try:
            mutant = fn(base)
        except AssertionError as e:
            rows.append((tag, why, "锚点失效", False))
            print("  ✗ %s %s -> 锚点失效：%s" % (tag, why, e))
            continue
        p = TMP / ("_mut12323_%s.py" % tag)
        p.write_text(mutant, encoding="utf-8", newline="")
        m = _load_smoke_for(p, tag)
        try:
            got = m.check_v12323_view_echo_full()
        except Exception as e:                     # 畸形引擎自己炸了 = 判据没能拦住
            got = "CRASH:%s" % type(e).__name__
        caught = (got is False)
        rows.append((tag, why, str(got), caught))
        print("  %s %s %s -> %s" % ("✓" if caught else "✗", tag, why,
                                    "判红（有判别力）" if caught else "没判红 ★"))

    n_ok = sum(1 for r in rows if r[3])
    print("── 变异体：%d/%d 被判红 ──" % (n_ok, len(rows)))
    for r in rows:
        print("   %s %s | %s" % (r[0], r[1][:36], r[2][:40]))
    print("结果：正对照 %s / 变异体 %d/%d"
          % ("绿" if ok0 else "红★", n_ok, len(rows)))

    # 清理（沙箱 safe-delete 会拦，失败不算错）
    try:
        shutil.rmtree(TMP)
    except OSError:
        pass
    good = ok0 and n_ok == len(rows)
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
