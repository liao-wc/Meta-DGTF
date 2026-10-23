# -*- coding: utf-8 -*-
"""把 M72 移到 MUTS 末尾（第四次因「插入位置 ≠ 编号」错位）。

★ 结论：**新变异体一律 append** —— 这一条已写进 Skill，但每次补丁仍按
  「锚在 M56 前」的旧习惯写 ⇒ 反复错位。本脚本顺手**检查全部 Mn 是否升序**，
  非升序就报出来（以后一眼可见，不用等 `--only` 跑错靶子才发现）。
"""
import re
from pathlib import Path

P = Path(__file__).resolve().parent / "_mut_v12332.py"
START = "    #   ★ M72 打在**真跑逮到的那处**上"
END = "    #   ★ M56 打在**新规范接线**上"


def main():
    s = P.read_text(encoding="utf-8")
    a, b = s.find(START), s.find(END)
    if a > 0 and b > a:
        blk = s[a:b]
        assert "M72" in blk and "M56" not in blk, "切块不对"
        s = s[:a] + s[b:]
        tail = s.rfind("\n]")
        s = s[:tail] + "\n" + blk.rstrip("\n") + s[tail:]
        print("M72 已移到末尾")
    else:
        print("M72 不在 M56 前（可能已重排）")
    P.write_text(s, encoding="utf-8")

    _order = re.findall(r'"(M\d+) ', s)
    _nums = [int(x[1:]) for x in _order]
    print("MUTS 数 %d；尾 4：%r" % (len(_order), _order[-4:]))
    _bad = [(a2, b2) for a2, b2 in zip(_nums, _nums[1:]) if b2 < a2]
    print("非升序对: %r" % (_bad,))
    assert not _bad, "仍有非升序，`--only` 会跑错靶子"
    assert _order[-1] == "M72", "尾部不是 M72"


main()
