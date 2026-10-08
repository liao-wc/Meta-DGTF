#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.4] 修生成器守卫的**非幂等**。

症状（本轮的幂等自检抓到）：在**当前** smoke 上重跑注入链，守卫从 92 涨到 97
（多 5 行）。也就是同一条守卫会被重复插入 —— 每次重跑多 5 行，永远增长。

真因：生成器里
    GUARD_RE = re.compile(r"^    if not (check_v123_\\w+)\\(\\):\\n        return 1\\n", re.M)
只能匹配 `check_v123_w1` / `check_v123_w2` / `check_v123_pool_export` /
`check_v123_left` 这 4 个；而 `GUARD_BLOCK` 里有 **9** 个
（v1.23.2 起陆续加的 `check_v1232_audit` / `check_v1232_tier` /
`check_v1232_retry` / `check_v1233_vote_ids` / `check_v1234_runtime` 都不匹配
—— 因为 `check_v123_` 要求 `123` 后面紧跟下划线）。
于是「先剥旧、再插新」里的**剥**没剥干净 ⇒ 那 5 个每跑一次多一份。

修法：把 `check_v123_\\w+` 放宽成 `check_v123\\d*_\\w+`（既匹配 `v123_w1`，
也匹配 `v1232_audit` / `v1233_vote_ids` / `v1234_runtime`）。

★ 教训：**「先剥后插」的脚本，剥的那一侧必须覆盖「插的那一侧全集」**，
  否则每次重跑都在累积。而且它**不报错**（`n_after >= n_before` 那条断言
  方向就是错的：它只保证不减，不保证不加）。
"""
from pathlib import Path
import ast

P = Path("_mk_v1230_smoke_checks.py")
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "生成器不是纯 CRLF"
s = b.decode("utf-8").replace("\r\n", "\n")

OLD = "check_v123_\\w+"
NEW = "check_v123\\d*_\\w+"
n = s.count(OLD)
assert n == 1, "锚点命中 %d 次（应 1）" % n
s = s.replace(OLD, NEW, 1)

# 顺手把那条「方向错了」的断言补成两向：既不许减，也不许加。
O2 = ('assert n_after >= n_before, "守卫数掉了：%d -> %d" % (n_before, n_after)')
N2 = ('assert n_after == n_before, (\n'
      '    "守卫数变了：%d -> %d（非幂等！剥的那侧没覆盖插的那侧全集）"\n'
      '    % (n_before, n_after))')
assert s.count(O2) == 1, "断言锚点命中 %d 次" % s.count(O2)
s = s.replace(O2, N2, 1)

ast.parse(s)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
P.write_bytes(out)
print("生成器已修：剥离正则放宽 + 断言改为「必须相等」")
