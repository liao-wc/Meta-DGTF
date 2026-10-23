#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 收尾二：修正【验收】里配置同步那句（口径要与实测一致）。

原句「166 键 / load_config 逐字差异 0 项」是**早期口径**，实测口径是：
  · 本轮**新增键**（`sim.dedup` / `sim.dedup_susp`）两边完全相等 ⇒ 0 差异；
  · 出厂 yaml 与 `DEFAULT_CONFIG` 本来就有历史差异（v1.23.25 下 30 项，
    本版 **30 → 28**）。把它说成「0 项」是**把基线差异藏起来**，
    属于自欺型表述，必须改成可复现的口径。
"""
from pathlib import Path

CL = Path(__file__).resolve().parent / "CHANGELOG.md"
b = CL.read_bytes()
_is_crlf = b.count(b"\r\n") > 0
txt = b.decode("utf-8")
if _is_crlf:
    txt = txt.replace("\r\n", "\n")

OLD = """  · 配置同步：166 键 / **load_config 逐字差异 0 项**（新增 2 键已显式写入出厂 yaml）
"""
NEW = """  · 配置同步：**本轮新增键 0 差异** —— `sim.dedup` / `sim.dedup_susp`
    在 `DEFAULT_CONFIG` 与出厂 yaml 两侧相等。
    ★ 口径说明：出厂 yaml 与 `DEFAULT_CONFIG` 存在**历史遗留**差异
      （`spiral.*` / `memory.*` / `actions.*`，与相似度无关）；
      v1.23.25 下该差异 = **30 项**，本版 = **28 项**（`sim` 两键由
      「yaml 有、DEFAULT 无」变为「两侧相等」）⇒ 本版是**修掉** 2 项，
      不是引入差异。「0 项」只对本轮新增键成立，不能笼统说成全量 0。
"""
c = txt.count(OLD)
assert c == 1, f"锚点命中 {c} 次"
txt = txt.replace(OLD, NEW, 1)

out = txt.replace("\n", "\r\n").encode("utf-8") if _is_crlf else txt.encode("utf-8")
CL.write_bytes(out)
print("OK 配置同步口径已修正")
print("lines =", out.count(b"\n"), "bytes =", len(out))
