# -*- coding: utf-8 -*-
"""v1.23.18 配置同步：头部版本 + 升级段 + external_anchor.enabled false→true
   + 两处当前文档注释（1080 / 505）。

★ 幂等：升级段用 MARK 判重。
★ 历史升级段（如 v1.21.55 段里那句「external_anchor 保持 enabled: false」）
  **不改** —— 那是当时版本的历史记录。
"""
from pathlib import Path

HERE = Path(".").resolve()
YML = HERE / "dgtf_config.yaml"

MARK = "# 【v1.23.17 → v1.23.18】"

UP = '''# 【v1.23.17 → v1.23.18】外部锚点默认打开（并把「未挂文件」做成独立干净态）
#   ★ 本版**改变默认行为**：`external_anchor.enabled` 由 false 改成 **true**。
#     · 通道默认打开后，**配了** `path` 就自动接入 —— 不再需要手动开开关；
#     · **没配** `path` 是「开（未挂锚点文件）」这个**独立状态**：零调用、
#       **不记 error**（改前会写「enabled=True 但没有给 path」并渲染成
#       「⚠️ 接入失败」—— 那样每次默认运行都会报一个假故障）；
#     · 显式写 `enabled: false` 可完全关闭（关闭时产物不写该通道状态）。
#   ★ 三处连带改动（「改了默认值要连带改的东西」）：
#     ① 产物头部的文本通道从两态变**四态**：`**关**` /
#        `**开（未挂锚点文件）**` / `**开** —— 已接入 N 条` /
#        `**开** —— ⚠️ 接入失败`；★ 缺席态文案由「无」改成「**关**」
#        （与联网通道对称：两条通道缺席时都写「关」）。
#     ② 产物头部「锚点明细」在未挂文件时**不再写五行零**
#        （原先写「结论 0 条 / 印证 0 / 冲突 0 / 无对应 0 / 入池 0」——
#         读者会以为对照做过、只是结果全是 0）；改成一行
#        「**锚点对照**：未做 —— 通道开着但**没有挂锚点文件**」。
#     ③ 事实题的「本次未接入外部校验」留痕改成按**两条通道各自的实际状态**
#        发言（改前写「两条通道都关：锚点文件无、联网检索关」—— 锚点默认
#        开着之后这句就不成立了）。
#   ★ 对你的影响：**不改本文件也能跑**（默认值已改）。已有锚点快照 JSON 的，
#     只需把 `path` 指过去即自动接入；想完全关闭就写 `enabled: false`。
#   ★ 判据：`check_v12318_anchor_default_on`（出厂值 + 干净态 + 负对照 +
#     渲染四态 + 产物不写零行）+ 4 个变异体；另更新两组旧判据的夹具与文案断言。
#
'''

raw = YML.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")


def repl(old, new, what, expect=1):
    o, n = old.split("\n"), new.split("\n")
    hits = [i for i in range(len(lines) - len(o) + 1) if lines[i:i + len(o)] == o]
    assert len(hits) == expect, "%s：命中 %d 次（要求 %d）" % (what, len(hits), expect)
    for i in reversed(hits):
        lines[i:i + len(o)] = n
    print("%-42s 改 %d 处" % (what, len(hits)))


# ① 头部版本
repl("# 元 DGTF · v1.23.17 配置文件", "# 元 DGTF · v1.23.18 配置文件", "头部版本")

# ② 升级段（幂等）
if MARK in "\n".join(lines):
    print("%-42s 已存在，跳过" % "升级段")
else:
    ANCHOR = "# 【v1.23.16 → v1.23.17】三个停止阈值/门槛"
    _hit = [k for k, l in enumerate(lines) if l.startswith(ANCHOR)]
    assert len(_hit) == 1, "升级段锚点命中 %d 次" % len(_hit)
    i = _hit[0]
    lines[i:i] = UP.split("\n")
    print("%-42s 已插入" % "升级段")

# ③ enabled + 默认说明
repl('''  # 【默认】false —— 关闭时行为与 v1.21.72 逐字相同，不花额外调用。''',
     '''  # 【默认】**true（v1.23.18 起）** —— 通道默认打开。
  #   没配 `path` 时是「开（未挂锚点文件）」这个**独立干净态**：零调用、
  #   不记 error；配了 `path` 才真读文件（可能多一次收尾对照调用）。
  #   显式 `false` = 完全关闭（关闭时产物不写该通道状态）。''',
     "enabled 默认说明")

repl('''  enabled: false

  # 【用途】锚点快照 JSON 路径（相对工作目录，或绝对路径）。''',
     '''  enabled: true

  # 【用途】锚点快照 JSON 路径（相对工作目录，或绝对路径）。''',
     "enabled false→true")

# ④ 当前文档「修改心法」那行
repl('''#   调"接不接外部事实"   → 改 external_anchor.*（默认全关，不花调用）''',
     '''#   调"接不接外部事实"   → 改 external_anchor.*（v1.23.18 起默认**开**；
#                              没配 path 时零调用，「未挂文件」是干净态）''',
     "修改心法那行")

out = "\n".join(lines)
enc = out.replace("\n", "\r\n").encode("utf-8")
assert enc.count(b"\r\r\n") == 0
YML.write_bytes(enc)
import yaml
d = yaml.safe_load(enc.decode("utf-8"))
print("yaml 语法 OK；enabled =", d["external_anchor"]["enabled"],
      "| path =", repr(d["external_anchor"].get("path")), "| 行数", out.count("\n"))
