#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.3] 修 D：**空票被重复计成「越界弃票」**。

`_normalize_judgment_ids({}, n)` 对空 dict 返回 `(None, "空")`；而多票路径写的是
`elif _jb is None: _id_bad += 1` —— 于是**一张空票被数两次**（`_empty_votes`
一次、`_id_bad` 一次），池级留痕印出「1/3 票可用（空票 1 张；id 越界弃票 1 张）」，
而实际只有 1 张空票、0 张越界。**可用票数因此被少数一张**。

（发现路径：`_probe_v1231_left.py` 的 `L4.2` 判据立刻判红 —— 那条判据量的正是
「留痕有没有写清可用几票」，属于「判据随实现更新」之外的真错。）
"""
from pathlib import Path
import ast

P = Path(__file__).resolve().parent / "元DGTF-V1.23.3.py"
raw = P.read_bytes().decode("utf-8")
assert raw.count("\r\n") == raw.count("\n")
s = raw.replace("\r\n", "\n")

O = '''            if _jk == "0起+1":
                _id_shift += 1
            elif _jb is None:
                _id_bad += 1
                logger.warning("三态多票：第 %d 票 id 档位=%s → 弃票",
                               _vi + 1, _jk)
                continue'''
N = '''            if _jk == "0起+1":
                _id_shift += 1
            elif _jb is None and _jk == "越界":
                _id_bad += 1
                logger.warning("三态多票：第 %d 票 id 档位=越界 → 弃票",
                               _vi + 1)
                continue
            # ★ 「空」档**不在这里计数** —— 空票已经由 `_empty_votes` 计过
            #   （上面 `if not (data.get("judgments") or [])` 那条分支）。
            #   第一版把 `_jb is None` 一律记成「越界弃票」⇒ 同一张空票被
            #   数两次，池级留痕印出「1/3 票可用（空票 1；越界弃票 1）」，
            #   可用票数因此**少数一张**。判据 `L4.2` 当场判红。'''
assert s.count(O) == 1, "锚点命中 %d 次" % s.count(O)
s = s.replace(O, N)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
ast.parse(s)
P.write_bytes(out)
print("已修：空票不再重复计成越界弃票")
