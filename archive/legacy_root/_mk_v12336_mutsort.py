# -*- coding: utf-8 -*-
"""根治：把 `_mut_v12332.py` 的 MUTS **按 Mn 编号排序**（升序）。

## 为什么
「新变异体 append 到末尾」这条纪律我已经**写了四次**，但每次补丁仍按
「锚在 M56 前」的旧习惯插到中间 ⇒ `--only N`（用索引）四次跑错靶子。
**与其继续靠纪律，不如让文件自己保持有序**。

## 怎么切块
逐行扫描，遇到 `    ("Mn ` 就开始一个新条目；**把它前面连续的注释行**
（`    #   …`）归给这个条目（注释是条目的说明，必须跟着走）；
其余行（列表头 `MUTS = (`、结尾 `]`、以及列表后的代码）原样保留。

## 安全
只在**全文件里 Mn 唯一**时才重排；排序后校验「严格升序」。
"""
import re
from pathlib import Path

P = Path(__file__).resolve().parent / "_mut_v12332.py"


def main():
    lines = P.read_text(encoding="utf-8").split("\n")
    # 找 MUTS 列表区间
    _start = next(i for i, l in enumerate(lines) if l.startswith("MUTS = ["))
    _end = next(i for i in range(_start, len(lines)) if lines[i].rstrip() == "]")

    head = lines[:_start + 1]
    body = lines[_start + 1:_end]
    tail = lines[_end:]

    # 切块：条目 = 前导注释 + 元组行
    # ★ **注释归属**：紧挨在 `("Mn ` **之前**的连续注释行，是**这一条**的说明
    #   ⇒ 必须从上一块的尾部**摘下来**给它。
    #   第一版没做这一步 ⇒ 注释留在了**前一个条目**下面（错位；M56 的注释
    #   就跑到了 M55 下面）。内容没丢，但可读性毁了 ⇒ 已从 git 恢复重做。
    blocks, cur = [], []
    for l in body:
        if re.match(r'\s+\("M\d+ ', l):
            _tail_cmt = []
            while cur and cur[-1].strip().startswith("#"):
                _tail_cmt.insert(0, cur.pop())
            if cur:
                blocks.append(cur)
            cur = _tail_cmt + [l]
        elif l.strip() == "" and cur and cur[-1].rstrip().endswith("),"):
            blocks.append(cur)
            cur = []
        else:
            cur.append(l)
    if cur:
        blocks.append(cur)

    def _num(b):
        m = re.search(r'\("M(\d+) ', b[0])
        return int(m.group(1)) if m else 10 ** 6
    blocks = [b for b in blocks if _num(b) < 10 ** 6]
    _nums = [_num(b) for b in blocks]
    assert len(set(_nums)) == len(_nums), "Mn 有重复 ⇒ 停手"
    _before = list(_nums)
    blocks.sort(key=_num)

    # 重建（每块之间保留一个空行，与原风格一致）
    out = list(head)
    for i, b in enumerate(blocks):
        out.extend(b)
        if i < len(blocks) - 1:
            out.append("")
    out.extend(tail)
    P.write_text("\n".join(out), encoding="utf-8")

    _after = [_num(b) for b in blocks]
    print("MUTS %d 条" % len(blocks))
    print("排序前尾 6：%r" % (_before[-6:],))
    print("排序后尾 6：%r" % (_after[-6:],))
    assert _after == sorted(_after), "排序后仍非升序"
    print("OK 已严格升序（`--only N` 从此不会跑错靶子）")


main()
