#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""smoke_test 的**只读** harness：不复制文件、不改磁盘，把 SRC 换掉后 exec。

为什么要有它：
- 以前要拿另一份源码跑冒烟，就得复制一份 smoke_test.py，于是 harness 自己分叉。
- 这里只读 `smoke_test.py` 源码 → 正则换 `SRC = HERE / "..."` 那一行 → exec
  成独立 module。判据永远只有一份。

用法：
    from _smoke_harness import load_smoke
    g = load_smoke("_baseline_v12177.py")     # 不传则用 smoke_test 自己的 SRC
    g["check_config_parses"]()                # 单独跑一条
    g["main"]()                               # 跑全套
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_smoke(src: str | None = None) -> dict:
    """返回 exec 后的 globals（不含 __main__ 自启动）。"""
    st = (HERE / "smoke_test.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    pat = re.compile(r'SRC = HERE / "[^"]+\.py"')
    hits = pat.findall(st)
    assert len(hits) == 1, f"SRC 行不唯一：{hits}"
    if src is not None:
        st = pat.sub(lambda _m: 'SRC = HERE / "%s"' % src, st, count=1)
    st = st.replace('if __name__ == "__main__":\n    sys.exit(main())', "")
    g = {"__name__": "smoke_harness", "__file__": str(HERE / "smoke_test.py")}
    exec(compile(st, "smoke_test.py", "exec"), g)
    return g


if __name__ == "__main__":
    import sys
    g = load_smoke(sys.argv[1] if len(sys.argv) > 1 else None)
    only = sys.argv[2] if len(sys.argv) > 2 else None
    if only:
        sys.exit(0 if g[only]() else 1)
    sys.exit(g["main"]())
