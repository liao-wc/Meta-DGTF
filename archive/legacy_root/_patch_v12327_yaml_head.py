#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.27：只把 dgtf_config.yaml 的头部版本改到 v1.23.27。

★ 为什么提前做：冒烟的「整体审计」判据 C3 要求
  `yaml 头部版本 == __version__`，不一致会**中断后续判据**
  （实测 ✓ 从 219 掉到 151）。所以这是跑全套冒烟的前置条件。
★ 升级段与新增键留到 Step12 一起做。
"""
from pathlib import Path
import re

CFG = Path(__file__).resolve().parent / "dgtf_config.yaml"
b = CFG.read_bytes()
_is_crlf = b.count(b"\r\n") > 0
txt = b.decode("utf-8")
if _is_crlf:
    txt = txt.replace("\r\n", "\n")

m = re.search(r"^# 元 DGTF · v([\d.]+) 配置文件$", txt, flags=re.M)
assert m, "找不到 yaml 头部版本行"
v_old = m.group(1)
assert v_old == "1.23.26", f"头部版本不是预期的 1.23.26，而是 {v_old}"

txt = txt.replace(m.group(0), "# 元 DGTF · v1.23.27 配置文件", 1)

out = txt.replace("\n", "\r\n").encode("utf-8") if _is_crlf else txt.encode("utf-8")
CFG.write_bytes(out)
assert "# 元 DGTF · v1.23.27 配置文件" in out.decode("utf-8")
print(f"OK yaml 头部：v{v_old} -> v1.23.27")
print("lines =", out.count(b"\n"), "bytes =", len(out))
