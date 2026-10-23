# -*- coding: utf-8 -*-
"""把 M69~M71 移到 MUTS 末尾（`--only N` 的索引必须与编号一致）。

★ 这已经是**第三次**因「插入位置 ≠ 编号」而错位了 —— 所以这次连**制造者**
  （`_mk_v12336_emlwire_chk.py` 那样的补丁）也应该直接 append。
  本脚本顺手把「校验」写进输出：尾 3 条必须是 M69/M70/M71。
"""
import re
from pathlib import Path

P = Path(__file__).resolve().parent / "_mut_v12332.py"
START = "    #   ★ M69 打在**「学了要做」**上"
END = "    #   ★ M56 打在**新规范接线**上"


def main():
    s = P.read_text(encoding="utf-8")
    a, b = s.find(START), s.find(END)
    if a > 0 and b > a:
        blk = s[a:b]
        assert "M69" in blk and "M71" in blk and "M56" not in blk, "切块不对"
        s = s[:a] + s[b:]
        tail = s.rfind("\n]")
        s = s[:tail] + "\n" + blk.rstrip("\n") + s[tail:]
        print("M69~M71 已移到末尾")
    else:
        print("不在 M56 前（可能已重排）")
    P.write_text(s, encoding="utf-8")
    _order = re.findall(r'"(M\d+) ', s)
    print("MUTS 数 %d；尾 6：%r" % (len(_order), _order[-6:]))
    assert _order[-3:] == ["M69", "M70", "M71"], "尾部顺序仍不对"


main()
