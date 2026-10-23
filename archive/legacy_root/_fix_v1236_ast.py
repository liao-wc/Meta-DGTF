#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修 v1.23.6 注入判据里的 NameError：smoke_test.py 模块级没 import ast。
改成函数内 `import ast as _ast`（与既有风格一致，如 `import inspect as _ins`）。
两个文件一起修：smoke_test.py（已生成）与 _mk_v1236_smoke_checks.py（生成器）。
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = ("    leads = []\n"
       "    for node in ast.walk(ast.parse(src)):\n"
       "        if isinstance(node, ast.Constant) and isinstance(node.value, str):\n")
NEW = ("    leads = []\n"
       "    import ast as _ast\n"
       "    for node in _ast.walk(_ast.parse(src)):\n"
       "        if isinstance(node, _ast.Constant) and isinstance(node.value, str):\n")

for name in ("smoke_test.py", "_mk_v1236_smoke_checks.py"):
    p = HERE / name
    raw = p.read_bytes()
    crlf = raw.count(b"\r\n") > 0
    t = raw.decode("utf-8").replace("\r\n", "\n")
    n = t.count(OLD)
    if n == 0:
        if NEW in t:
            print("%-32s [skip] 已修过" % name)
            continue
        raise SystemExit("★ %s 里锚点命中 0 次，且不是已修状态" % name)
    assert n == 1, "%s 锚点命中 %d 次" % (name, n)
    t = t.replace(OLD, NEW, 1)
    out = t.replace("\n", "\r\n").encode("utf-8") if crlf else t.encode("utf-8")
    assert out.count(b"\r\r\n") == 0
    p.write_bytes(out)
    print("%-32s 已修（CRLF=%s）" % (name, crlf))

sk = (HERE / "smoke_test.py").read_bytes().decode("utf-8").replace("\r\n", "\n")
print("\nsmoke_test.py 模块级 import ast ？",
      any(l.strip() == "import ast" for l in sk.split("\n")))
print("注入函数里还有裸 ast. ？",
      "ast.walk(ast.parse" in sk or "isinstance(node, ast." in sk)
