#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段3b] 把「池级留痕」汇总抽成两个落地层模板共用的一份实现。

怎么发现的：阶段 3 引入分流壳之后，**旧判据红了** ——
`smoke_test.py::check_v64_landing` 里那条
「落地层顶部的池级留痕汇总缺失」。它喂的 fixture 是 `orientation="auto"`，
按新壳子走 decision 模板，而那段汇总原本只写在 `_render_landing_boundary`
里 → 新模板把这一行**丢了**。

这不是「判据过时」，是真的信息丢失。但正确修法也不是把判据改宽，而是
**把那段代码抽成一份共用实现**：两个模板都调它，于是
  · 老判据在两个分支上都成立；
  · 「同一条逻辑两条通道各写一份」没有新增（这是本项目的第 1 号公敌）。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

OLD_BLOCK = '''    _pools_meta = (res.get("pools") or {})
    _meta_total = sum(len(pp.get("meta") or []) for pp in _pools_meta.values())
    if _meta_total:
        _meta_kinds = {"P1-6 拦截": 0, "自省回流未生效": 0, "自省反馈": 0,
                       "其它": 0}
        for _pp in _pools_meta.values():
            for _m in (_pp.get("meta") or []):
                _s = str(_m)
                if _s.startswith("[P1-6]"):
                    _meta_kinds["P1-6 拦截"] += 1
                elif _s.startswith("[自省回流未生效]"):
                    _meta_kinds["自省回流未生效"] += 1
                elif "self-check" in _s or "上一圈" in _s:
                    _meta_kinds["自省反馈"] += 1
                else:
                    _meta_kinds["其它"] += 1
        _parts = " / ".join(f"{k} {v}"
                            for k, v in _meta_kinds.items() if v)
        out.append(f"**池级留痕**：{_meta_total} 条（{_parts}）\\n\\n")
'''

NEW_BLOCK = '''    out.append(_pool_meta_summary(res))
'''

HELPER = '''
def _pool_meta_summary(res: dict) -> str:
    """[v122 P3] 池级留痕一句汇总（无留痕时返回空串）。

    ★ 为什么抽出来：这段原来只写在 `_render_landing_boundary` 里。
      阶段 3 加了分流壳之后，`orientation="auto"` 会走 decision 模板，
      于是这一行在新模板上**凭空丢了** —— 旧判据（v64 A）当场判红。
      修法不是把判据改宽，而是让两个模板调**同一份**实现：
      「同一条逻辑两条通道各写一份」是本项目的头号复发问题，不加第 8 例。
    """
    _pools_meta = (res.get("pools") or {})
    _meta_total = sum(len(pp.get("meta") or []) for pp in _pools_meta.values())
    if not _meta_total:
        return ""
    _meta_kinds = {"P1-6 拦截": 0, "自省回流未生效": 0, "自省反馈": 0,
                   "其它": 0}
    for _pp in _pools_meta.values():
        for _m in (_pp.get("meta") or []):
            _s = str(_m)
            if _s.startswith("[P1-6]"):
                _meta_kinds["P1-6 拦截"] += 1
            elif _s.startswith("[自省回流未生效]"):
                _meta_kinds["自省回流未生效"] += 1
            elif "self-check" in _s or "上一圈" in _s:
                _meta_kinds["自省反馈"] += 1
            else:
                _meta_kinds["其它"] += 1
    _parts = " / ".join(f"{k} {v}" for k, v in _meta_kinds.items() if v)
    return f"**池级留痕**：{_meta_total} 条（{_parts}）\\n\\n"

'''

# decision 模板：在标题行之后也挂同一份汇总
A_DEC = ('    out.append("## 落地层（decision 模式）\\n\\n")\n')
B_DEC = ('    out.append("## 落地层（decision 模式）\\n\\n")\n'
         '    # [v122 P3b] 与 boundary 模板共用同一份池级留痕汇总。\n'
         '    out.append(_pool_meta_summary(res))\n')


def main() -> int:
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")

    n = s.count(OLD_BLOCK)
    assert n == 1, f"池级留痕块锚点 {n} 次"
    s = s.replace(OLD_BLOCK, NEW_BLOCK, 1)
    print("  ✓ 抽出 _pool_meta_summary（boundary 改为调用）")

    anchor = "def _render_landing_decision(res: dict) -> str:\n"
    assert s.count(anchor) == 1, "decision 模板锚点不唯一"
    s = s.replace(anchor, HELPER.lstrip("\n") + "\n" + anchor, 1)
    print("  ✓ 插入 helper")

    n = s.count(A_DEC)
    assert n == 1, f"decision 标题锚点 {n} 次"
    s = s.replace(A_DEC, B_DEC, 1)
    print("  ✓ decision 模板也挂汇总")

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))
    print(f"✓ 阶段3b 补丁完成；行数 {len(out.splitlines())}；ast.parse OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
