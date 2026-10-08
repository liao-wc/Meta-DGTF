# -*- coding: utf-8 -*-
"""[v1.23.3] 修 v1233 注入器的 CHECKS 尾锚点（要带空行）。

★ 反斜杠一律用 chr(92) 拼 —— 本机 heredoc 会吞一层反斜杠（本项目第 8 次）。
"""
from pathlib import Path
import ast

BS = chr(92)
P = Path(__file__).resolve().parent / "_mk_v1233_smoke_checks.py"
s = P.read_text(encoding="utf-8")
lines = s.split("\n")
hit = []
for k, l in enumerate(lines):
    if 'O = "        return False' in l and "end v123 checks" in l:
        hit.append(k)
assert len(hit) == 1, "锚点行命中 %d 处" % len(hit)
k = hit[0]
print("原行:", repr(lines[k]))
lines[k] = ('    O = "        return False' + BS + 'n' + BS + 'n'
            + '# <<<end v123 checks>>>"')
# 顺带把断言口径也写清
for j in range(k, min(k + 4, len(lines))):
    if lines[j].strip().startswith("assert s.count(O) == 1"):
        lines[j] = ('    # ★ 锚点必须带**空行**：v1.23.2 的注入器在 '
                    '`return False` 与 MARK 之间留了一个空行。')
        lines.insert(j + 1,
                     '    assert s.count(O) == 1, "CHECKS 尾锚点 %d 次" '
                     '% s.count(O)')
        break
s2 = "\n".join(lines)
ast.parse(s2)
P.write_text(s2, encoding="utf-8")
print("新行:", repr(lines[k]))
print("已修（parse OK）")
