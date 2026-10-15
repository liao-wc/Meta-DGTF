# -*- coding: utf-8 -*-
"""[修复] _mut_v12332.py：M84 锚点里混进了**真换行**（把字面量劈成两行）。

★ 症状：M84 报「锚点命中 0 次（失效）」—— 锚点本身在主文件里是对的。
★ 根因：构造 M84 时把 `\\n` 写成了**真换行**（我拼 block 时用的 `+ NL`
  拼进了字面量内容）⇒ `_mut` 里的字符串字面量被劈成两行，中间多一个
  真换行 ⇒ 与主文件（单行）不匹配。
★ 修法：字面量里用**单反斜杠的转义序列** `\\n`（落盘后 Python 解析成换行），
  而不是把换行直接写进引号内。
"""
from pathlib import Path

P = Path(__file__).resolve().parent / "_mut_v12332.py"

raw = P.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n"), "_mut 不是纯 CRLF"
s = raw.decode("utf-8").replace("\r\n", "\n")

lines = s.split("\n")
i84 = next(i for i, l in enumerate(lines) if l.strip().startswith('("M84'))
print("[info] M84 块：行 %d 起" % (i84 + 1))
for k in range(i84, i84 + 6):
    print("   %4d | %s" % (k + 1, lines[k][:78]))

# ── 重建 M84 块（用「单反斜杠 + n」的转义序列，不含真换行）──
BS = chr(92)
A = ('        if not bool(self.cfg.get("enabled", False)):' + BS + 'n'
     '            return False, "web_search 未启用（默认关）"')
B = ('        if False:' + BS + 'n'
     '            return False, "web_search 未启用（默认关）"')

block = [
    '    #   ★ M84 打在**成本闸门**上：总闸检查被短路 ⇒ 按需路径在',
    '    #     web_search.enabled=False 时也放行（按需=无上限 ⇒ 成本失控）。',
    '    ("M84 按需短路总闸（关了也能查）",',
    "     '" + A + "',",
    "     '" + B + "'),",
]
# 找到 M84 块的结束（以 `),` 结尾的那行）
j = i84
while not lines[j].rstrip().endswith("),"):
    j += 1
print("[info] M84 块结束：行 %d" % (j + 1))

new_lines = lines[:i84] + block + lines[j + 1:]
s2 = "\n".join(new_lines)
out = s2.replace("\n", "\r\n").encode("utf-8")
assert b"\r\r\n" not in out
P.write_bytes(out)

# ── 回读自检：M84 的两个字面量必须是**单行**（不含真换行）──
chk = P.read_bytes().decode("utf-8")
import ast
ast.parse(chk)
_l = chk.split("\n")
_i = next(i for i, l in enumerate(_l) if l.strip().startswith('("M84'))
_seg = _l[_i:_i + 3]          # 只取 M84 三行（不含随后的 `]`）
print("")
for x in _seg:
    print("   | %s" % x[:88])
# 判据：字面量所在行**必须单行闭合**（引号成对出现在同一行）
_lit = [x for x in _seg if x.strip().startswith("'")]
assert len(_lit) == 2, "M84 应有 2 个字面量行，实得 %d" % len(_lit)
assert all(x.count("'") == 2 for x in _lit), "M84 字面量引号不成对（仍有真换行）"
print("[ok] AST OK | M84 字面量已单行闭合 | 纯 CRLF =",
      P.read_bytes().count(b"\n") == P.read_bytes().count(b"\r\n"))

# ── 直接验锚点在主文件里能命中 ──
src = Path(__file__).resolve().parent.joinpath("元DGTF-V1.23.39.py") \
    .read_bytes().decode("utf-8").replace("\r\n", "\n")
a_val = A.replace(BS + "n", chr(10))
b_val = B.replace(BS + "n", chr(10))
print("[ok] M84 锚点在主文件命中：", src.count(a_val), "(要求 1)")
assert src.count(a_val) == 1