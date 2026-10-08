#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.4] 报告补丁 5：第 9 处发现（生成器守卫**非幂等**）+ 教训 10（幂等）。"""
from pathlib import Path

P = Path("v1234_报告.md")
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n")
s = b.decode("utf-8").replace("\r\n", "\n")

KEY = "生成器的守卫剥离正则"
if KEY not in s:
    ROW9 = ("| 9 | ★ 生成器 `_mk_v1230_smoke_checks.py` 的守卫**非幂等**："
            "剥离正则 `check_v123_\\w+` 只能匹配 4 个守卫，而插入的 `GUARD_BLOCK` "
            "有 **9** 个 ⇒ 每次重跑多 5 行（92 → 97 → …），且原断言方向是 "
            "`n_after >= n_before`（只保证不减、不保证不加），**永远不会报错** | "
            "在**当前** smoke 上重跑注入链的**幂等自检** | 剥离正则放宽成 "
            "`check_v123\\d*_\\w+`；断言改成 `n_after == n_before`（必须相等） |")
    O = "## 七、经验教训"
    assert s.count(O) == 1, "§七 锚点 %d 次" % s.count(O)
    s = s.replace(O, ROW9 + "\n\n" + O, 1)
    print("已补 §六 第 9 行")

KEY2 = "「先剥后插」的脚本"
if KEY2 not in s:
    T = "\n".join([
        "10. ★ **「先剥后插」的脚本，剥的那一侧必须覆盖「插的那一侧的全集」。**",
        "    本轮生成器的守卫剥离正则只认 `check_v123_*`（4 个），而插入的块里有",
        "    9 个 ⇒ 每重跑一次多 5 行，**永远在增长**。更坏的是它的自检断言写成",
        "    `n_after >= n_before` —— **方向错的断言比没有断言更危险**",
        "    （它把「一直在加」判成了合格）。",
        "    ★ 配套做法：**幂等自检 = 在当前产物上连跑两轮，`cmp` 必须逐字节相同**。",
        "      这一条是零成本的，而且本轮就是它抓到的。",
        "",
        "## 八、附录：交付物",
    ])
    O2 = "## 八、附录：交付物"
    assert s.count(O2) == 1, "§八 锚点 %d 次" % s.count(O2)
    s = s.replace(O2, T, 1)
    print("已补 §七 教训 10")

P.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("行数：", s.count("\n") + 1)
