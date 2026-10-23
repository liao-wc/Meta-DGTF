# -*- coding: utf-8 -*-
"""[v1.23.27 Step5b] 清掉 Step3/Step4/Step5 自己引入的 16 处版次批注。

红线（v1.23.6 起）：**代码正文（模块 docstring 之外）不留版次标记**。
本轮的补丁注释里写了 `[v1.23.27 A1]` 这类标记 —— 被
`check_v1236_no_version_tags()` 判红（15 行成块 + 1 处 docstring 前导）。

★ 这不是「放宽阈值」也不是「改判据」：判据是对的，是**我的补丁违反了自己的红线**。
  正确修法 = **改注释本身**，把版次标记换成不带版次的语义标签
  （`[A1 方面单元]` / `[D1 信念条目]` / `[A2 符号对账]` / `[A3 双读数]`），
  这样既留住「这个注释属于哪一块改动」的信息，又不触碰红线。

★ 铁律：不能整行删掉 —— 那些注释里有**设计理由**（为什么双写、为什么
  resolved 优先级最高），删了等于把设计意图从代码里抹掉。只剥标记。
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.27.py"

raw = SRC.read_bytes()
txt = raw.decode("utf-8")
assert txt.count("\r\n") == txt.count("\n"), "源文件不是纯 CRLF"
assert "\r\r\n" not in txt

lf = txt.replace("\r\n", "\n")

# ── 剥标记映射：带版次的块标记 → 不带版次的语义标签 ──────────────
# ★ 逐条手写而非正则泛化：泛化正则很容易连「文档里提到 v1.23.26 的
#   行文」一起吃掉（那类是**允许**的，v1.23.6 判据只抠 docstring 之外的
#   注释；而我们要改的恰好就是这批注释）。
PAIRS = [
    ("[v1.23.27 A1] ", "[A1 方面单元] "),
    ("[v1.23.27 A2] ", "[A2 符号对账] "),
    ("[v1.23.27 A3] ", "[A3 双读数] "),
    ("[v1.23.27 A2/A3] ", "[A2/A3 符号对账] "),
    ("[v1.23.27 D1] ", "[D1 信念条目] "),
    ("[v1.23.27 D1/D2] ", "[D1/D2 信念四态] "),
    ("[v1.23.27 D2] ", "[D2 迁移规则] "),
    # 行内形态（`# [v1.23.27 A1] 带 id 前缀：…` 已在上面覆盖）
]

n_before = lf.count("[v1.23.27 ")
for _old, _new in PAIRS:
    lf = lf.replace(_old, _new)
n_after = lf.count("[v1.23.27 ")

# 还有没有漏网的？（只允许出现在模块 docstring 里，此处已排除在外）
assert n_after == 0, "仍有 %d 处 [v1.23.27 未剥（漏了映射）" % n_after
assert lf != txt.replace("\r\n", "\n"), "没有任何改动"

# ── 顺带修 docstring 前导标记（`[D1 信念条目] …` 本身也必须不带版次）──
#   上面已经把它换成 `[D1 信念条目]`，不含 `v\d` ⇒ 前导判据自然过。
#   自证：
_TAG = re.compile(r"\[v\d[^\]]*\]|(?<![A-Za-z0-9_\-])v\d+(?:\.\d+)*(?![A-Za-z0-9_\-])")
_lines = lf.split("\n")
_i = lf.index('"""')
_j = lf.index('"""', _i + 3)
_de = lf[: _j].count("\n")
_hit = [k + 1 for k in range(_de + 1, len(_lines))
        if _lines[k].lstrip().startswith("#") and _TAG.search(_lines[k])]
_trail = [k + 1 for k in range(_de + 1, len(_lines))
          if not _lines[k].lstrip().startswith("#") and "#" in _lines[k]
          and _TAG.search(_lines[k].split("#", 1)[1])]
assert not _hit and not _trail, "剥完后仍有批注：成块=%s 行尾=%s" % (_hit, _trail)

import ast as _ast
_lead = []
for _n in _ast.walk(_ast.parse(lf)):
    if isinstance(_n, _ast.Constant) and isinstance(_n.value, str):
        if _n.lineno > _de + 1 and _TAG.match(
                _n.value, re.match(r"\s*", _n.value).end()):
            _lead.append(_n.lineno)
assert not _lead, "剥完后仍有 docstring 前导标记：%s" % _lead

out = lf.replace("\n", "\r\n")
assert "\r\r\n" not in out
SRC.write_bytes(out.encode("utf-8"))

chk = SRC.read_bytes().decode("utf-8")
assert chk.count("\r\n") == chk.count("\n")
assert "\r\r\n" not in chk

print("STEP5b OK —— 剥掉版次标记 %d 处（%d 条映射）" % (n_before, len(PAIRS)))
print("  自证：成块注释 0 / 行尾批注 0 / docstring 前导 0")
print("  size %d -> %d bytes" % (len(raw), len(chk.encode('utf-8'))))
