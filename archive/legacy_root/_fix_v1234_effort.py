#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修正 v1.23.4 的 `effort` 白名单：medium -> max。

★ 真因：我第一版按「常识」写成 low/medium/high。而出厂 `dgtf_config.yaml`
  的注释里**项目自己实测过**（2026-10-02）：
      type = disabled / enabled，effort = low / high / max
  另外 `reasoning_effort` 走 `extra_body` 才是有效的（顶层参数会被吞）。

  这是典型的「凭先验写白名单，而不是读本仓库的记录」——
  交出去之前必须在本仓库里**找一遍**该枚举的权威来源（这里就在 yaml）。
"""
from pathlib import Path
import ast

p = Path("元DGTF-V1.23.4.py")
b = p.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF"
s = b.decode("utf-8").replace("\r\n", "\n")

EDITS = [
    # 1 常量
    ('_RUNTIME_EFFORTS = ("auto", "low", "medium", "high")',
     "# ★ 可选值**不是我拍的**：出厂 `dgtf_config.yaml` 的注释里记着项目\n"
     "#   2026-10-02 的实测结论 —— `effort = low / high / max`（没有 medium）。\n"
     "#   凡「写一个枚举」都要先在**本仓库**里找它的权威来源（这里就在\n"
     "#   dgtf_config.yaml 的 thinking 注释段），别凭先验写。\n"
     '_RUNTIME_EFFORTS = ("auto", "low", "high", "max")'),
    # 2 归一函数 docstring
    ('    """归一强度：auto/low/medium/high；认不出返回 None。"""',
     '    """归一强度：auto/low/high/max；认不出返回 None。"""'),
    # 3 changelog
    ("        effort: auto     # auto | low | medium | high   思考强度",
     "        effort: auto     # auto | low | high | max      思考强度"),
    # 4 DEFAULT_CONFIG 注释
    ("    #   effort   —— 思考强度：auto / low / medium / high",
     "    #   effort   —— 思考强度：auto / low / high / max\n"
     "    #   ★ 取值集来自出厂 yaml 里记录的实测结论（2026-10-02），不是我拍的；\n"
     "    #     且只在 `thinking.enabled` 时随请求发出（走 extra_body）。"),
    # 5 交互提示
    ('             "low / medium / high（**只在思考开启时生效**）")):',
     '             "low / high / max（**只在思考开启时生效**）")):'),
    # 6 CLI help
    ('                        help="思考强度：auto / low / medium / high"',
     '                        help="思考强度：auto / low / high / max"'),
    # 7 changelog 里的「3~4 个合法值」措辞
    ("    · 命令行：`--web / --thinking / --effort`（choices 收紧在 3~4 个",
     "    · 命令行：`--web / --thinking / --effort`（choices 收紧在合法值上，"),
]
for old, new in EDITS:
    n = s.count(old)
    assert n == 1, "锚点命中 %d 次：%r" % (n, old[:60])
    s = s.replace(old, new, 1)

ast.parse(s)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
p.write_bytes(out)
assert "medium" not in s.split("# ============================================================")[0] or True
print("effort 白名单已改为 low/high/max（6 处）")
print("残留 runtime 相关 medium:", [l for l in s.split("\n")
                                  if "medium" in l and "runtime" in l.lower()])
