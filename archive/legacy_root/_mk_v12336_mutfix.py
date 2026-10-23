# -*- coding: utf-8 -*-
"""重排 `_mut_v12332.py` 的 MUTS：把 M60~M64 从 M56 之前移到**列表末尾**。

## 为什么要修
`--only N` 用的是**索引**，而名字（M56/M60/…）写在各条目里 —— 我把新条目
插在 M56 之前，导致**索引与编号错位**（`--only 60,61` 实际跑到了 M64/M56）。
⇒ 顺序必须与编号一致，否则以后按编号定位会跑错靶子。
"""
import io
import re
from pathlib import Path

P = Path(__file__).resolve().parent / "_mut_v12332.py"


def main():
    s = P.read_text(encoding="utf-8")
    # 1) 切出 M60~M64 那一块（从它的注释头到 M56 注释头之前）
    _start = s.find("    #   ★ M60 打在**读数的输出通道**上")
    _end = s.find("    #   ★ M56 打在**新规范接线**上")
    assert _start > 0 and _end > _start, "切块定位失败（%d, %d）" % (_start, _end)
    _block = s[_start:_end]
    assert "M60" in _block and "M64" in _block and "M56" not in _block, \
        "切块内容不对"
    s = s[:_start] + s[_end:]

    # 2) 粘到列表末尾（`]` 之前）
    _tail = s.rfind("\n]")
    assert _tail > 0, "找不到列表结尾"
    s = s[:_tail] + "\n" + _block.rstrip("\n") + s[_tail:]

    # 3) 核对顺序：M55 → M60..M64 → M56..M59 里，我们只要 55 之后紧跟 60
    _order = re.findall(r'"(M\d+) ', s)
    print("MUTS 顺序（尾 12 条）:", _order[-12:])
    assert _order[-5:] == ["M60", "M61", "M62", "M63", "M64"], \
        "重排后尾部顺序不对：%r" % (_order[-5:],)
    P.write_text(s, encoding="utf-8")
    print("OK 已重排；MUTS 总数 %d" % len(_order))


main()
