# -*- coding: utf-8 -*-
"""修：① 把 M65~M68 移到 MUTS 末尾（编号与索引一致）；② 输出带索引。

## 为什么要修
`--only N` 用的是**索引**，而条目名字里写着 `M65` —— 我把新条目插在 M56 之前
⇒ 索引整体前移 ⇒ `--only 65,66,67,68` 实际跑到了 **M61~M64**。
★ 根因是「**插入位置**」与「**编号**」两套东西必须同步；更稳的做法是让
  输出**带索引**，这样跑错靶子当场可见（本轮已两次踩到这个）。
"""
import io
import re
from pathlib import Path

P = Path(__file__).resolve().parent / "_mut_v12332.py"

START = "    #   ★ M65 打在**心跳的触发条件**上"
END = "    #   ★ M56 打在**新规范接线**上"

OLD_PRINT = '''        print(("OK" if not green else "X"),
              "%s %s" % (name, "红(判别力OK)" if not green else "绿(假绿!)"))'''
NEW_PRINT = '''        # ★ 输出**带索引**：`--only N` 用的是索引，名字自带 `Mn` ——
        #   两者不一致时（插入导致偏移）当场可见（本轮栽过两次）。
        print(("OK" if not green else "X"),
              "[%d] %s %s" % (i, name,
                              "红(判别力OK)" if not green else "绿(假绿!)"))'''


def main():
    s = P.read_text(encoding="utf-8")

    # ① 重排
    a = s.find(START)
    b = s.find(END)
    if a > 0 and b > a:
        blk = s[a:b]
        assert "M65" in blk and "M68" in blk and "M56" not in blk, "切块不对"
        s = s[:a] + s[b:]
        tail = s.rfind("\n]")
        assert tail > 0
        s = s[:tail] + "\n" + blk.rstrip("\n") + s[tail:]
        print("M65~M68 已移到末尾")
    else:
        print("M65~M68 不在 M56 前（可能已重排）")

    # ② 输出带索引
    if "[%d] %s %s" in s:
        print("输出已带索引（跳过）")
    else:
        assert s.count(OLD_PRINT) == 1, "输出锚点命中 %d 次" % s.count(OLD_PRINT)
        s = s.replace(OLD_PRINT, NEW_PRINT, 1)

    P.write_text(s, encoding="utf-8")
    _order = re.findall(r'"(M\d+) ', s)
    print("MUTS 总数 %d；尾 10 条：%r" % (len(_order), _order[-10:]))
    assert _order[-4:] == ["M65", "M66", "M67", "M68"], "尾部顺序仍不对"


main()
