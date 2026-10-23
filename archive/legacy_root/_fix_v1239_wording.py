# -*- coding: utf-8 -*-
"""v1.23.9 修（第三轮）：把「auto = 按 decision」的旧措辞改到新语义。

★ 这是本版自己造成的不一致：改了 `render_landing` 里 auto 的语义（按题面分流），
  但产物与终端里的文案还写着「按 decision」—— 真跑产物第 19 行与第 66 行当场
  自相矛盾（**取向**：auto（未指定时按 decision），而落地层实际是 boundary 模板）。
★ 只改**取向/模板**语境的那几处；`_route_by_decidability` 里路由层的 auto
  行为**未变**（仍等价 decision 砍层），它的 docstring 保留原样。
"""
from pathlib import Path

p = Path(__file__).resolve().parent / "元DGTF-V1.23.9.py"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

PAIRS = [
    ('"auto": "auto（未指定，按 decision）",',
     '"auto": "auto（未指定：按题面有无决策语境分流）",'),
    ('out.append("未指定，按 decision 处理。\\n")',
     'out.append("未指定：落地层按题面有无决策语境分流'
     '（无决策语境走 boundary 模板）。\\n")'),
    ('"auto": "auto（未指定时按 decision）",',
     '"auto": "auto（未指定：按题面有无决策语境分流）",'),
    ('self.vp("\\n   ⚠️ 取向未指定，按 decision 取向处理"\n'
     '                    "（可显式传 orientation=boundary 保留全四层）")',
     'self.vp("\\n   ⚠️ 取向未指定：路由按 decision 处理"\n'
     '                    "（可显式传 orientation=boundary 保留全四层）；"\n'
     '                    "落地层模板另按题面有无决策语境分流")'),
    ('"auto（未指定时按 decision）")',
     '"auto（未指定：按题面有无决策语境分流）")'),
]
for old, new in PAIRS:
    n = s.count(old)
    assert n == 1, f"{old[:40]!r} 命中 {n} 次（要求 1）"
    s = s.replace(old, new, 1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
p.write_bytes(out)

import ast  # noqa: E402
chk = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
ast.parse(chk)
left = [i + 1 for i, ln in enumerate(chk.split("\n"))
        if "按 decision 处理" in ln or "未指定时按 decision" in ln
        or "未指定，按 decision" in ln]
print("残留旧措辞行号（应只剩 _route_by_decidability 的 docstring）：", left)
print("ast OK |", len(chk.split("\n")) - 1, "行")
