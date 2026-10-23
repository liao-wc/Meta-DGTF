#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段4e] B4 判据随实现更新：抛错从 `_retrieve_anchors` 挪进了检索器。

阶段 4 把「未实现的后端抛错」这件事收口到 `AnchorRetriever.search`（唯一
实现），`_retrieve_anchors` 只负责装配。而 v1.21.76 的 B4 判据是**按函数体
字符串**搜的，功能还在、位置变了 → 判据报红。

这正是「判据过时不是代码错」那一类。处理：判据改成搜**检索链** ——
`_retrieve_anchors` 的函数体 ∪ `AnchorRetriever` 类源码。删掉抛错仍然会被
抓到（两处都没有），判别力不减。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"

OLD = '''    ret = _v76_body("_retrieve_anchors")
    if "尚未实现" not in ret:
'''
NEW = '''    # [v122 P4e] 抛错已收口到 `AnchorRetriever.search`（检索的唯一实现），
    #   `_retrieve_anchors` 只管装配 → 判据改搜**整条检索链**。
    #   抛错被整体删掉时两处都没有，判据照样红（判别力不减）。
    import inspect as _ins4
    _retr_cls = ""
    try:
        _retr_cls = _ins4.getsource(mod.AnchorRetriever)
    except Exception as _e4:
        _retr_cls = ""
    ret = _v76_body("_retrieve_anchors") + "\\n" + _retr_cls
    if "尚未实现" not in ret:
'''


def main() -> int:
    b = SMOKE.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")
    n = s.count(OLD)
    assert n == 1, f"锚点 {n} 次"
    s = s.replace(OLD, NEW, 1)
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    SMOKE.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))
    print("✓ 阶段4e 完成：B4 判据改搜整条检索链")
    return 0


if __name__ == "__main__":
    sys.exit(main())
