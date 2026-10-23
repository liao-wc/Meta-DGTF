# -*- coding: utf-8 -*-
"""v1.23.16 文案修正：产物表头与注释里的「十二项」→ 十一项（表头改**动态**）。

★ 为什么必须改：产物表头写「十二项逐项来源」，而实际是 11 项 ——
  真跑产物那一行与它下面的 11 行表**自相矛盾**。
  这正是「改了默认语义就要连描述它的文案一起 grep」那条纪律。
★ 按行号**降序**执行（前面插行不影响后面的行号）。
"""
import ast
from pathlib import Path

F = Path("元DGTF-V1.23.16.py")
raw = F.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
N0 = len(lines)


def rline(a, new, what, head):
    assert lines[a - 1].startswith(head), "%s：第 %d 行不符 %r" % (
        what, a, lines[a - 1][:80])
    lines[a - 1] = new
    print("  %-30s 行 %d" % (what, a))


def cut(a, b, new, what, head, tail):
    seg = lines[a - 1:b]
    assert seg[0].startswith(head), "%s：首行不符 %r" % (what, seg[0][:80])
    assert seg[-1].startswith(tail), "%s：末行不符 %r" % (what, seg[-1][:80])
    lines[a - 1:b] = list(new)
    print("  %-30s %d-%d → %d 行" % (what, a, b, len(new)))


EDITS = [
    (18103, 18103,
     ["    # ★ **十一项一次性调度**（显式 ＞ 配置 ＞ auto ＞ 默认）。"],
     "注释 18103", "    # ★ **十二项一次性调度**", None),
    (17378, 17378,
     ["    #   enabled=false ⇒ 十一项一律退回「配置 / 默认」，行为回到上一版。"],
     "注释 17378", "    #   enabled=false ⇒ 十二项一律退回", None),
    (16110, 16111,
     ['    out = ["**自动调度**（%d 项逐项来源；%s，auto 接管 %d 项）\\n\\n"',
      '           % (len(_AUTO_ITEM_ORDER),',
      '              "总开关开" if _on else "总开关**关**", _n_auto)]'],
     "产物表头改动态", '    out = ["**自动调度**（十二项逐项来源；',
     '           % ("总开关开"'),
    (16005, 16005,
     ["    ★ `auto.enabled=false` ⇒ 十一项一律不进 auto 分支（回 v1.23.12 行为）。"],
     "docstring 16005", "    ★ `auto.enabled=false` ⇒ 十二项一律不进", None),
    (16002, 16002,
     ['    """十一项一次算完。返回 dict：每项一个值 + `_items` 逐项来源留痕。'],
     "docstring 16002", '    """十二项一次算完。', None),
    (15824, 15824,
     ["# ③ 十一项策略（各自适应条件）"],
     "注释 15824", "# ③ 十二项策略（各自适应条件）", None),
    (15247, 15247,
     ["# 【本版做法】把十一项收进**一个调度器**，逐项独立："],
     "注释 15247", "# 【本版做法】把十二项收进", None),
]
for a, b, new, what, head, tail in sorted(EDITS, key=lambda x: -x[0]):
    if a == b:
        rline(a, new[0], what, head)
    else:
        cut(a, b, new, what, head, tail)

out = "\n".join(lines) + "\n"
ast.parse(out)
_left = [k + 1 for k, l in enumerate(out.split("\n")) if "十二项" in l]
assert not _left, "仍有「十二项」在行 %s" % _left[:5]
assert "len(_AUTO_ITEM_ORDER)," in out
b = out.replace("\n", "\r\n").encode("utf-8")
assert b.count(b"\r\r\n") == 0 and b.count(b"\r\n") == b.count(b"\n")
F.write_bytes(b)
print("行数 %d → %d；已写" % (N0, out.count("\n")))
