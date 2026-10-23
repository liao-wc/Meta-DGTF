#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 v1.23.25 段插进 CHANGELOG.md（v1.23.24 段之前）。纯 CRLF 往返。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
P = HERE / "CHANGELOG.md"

NEW_SEG = """v1.23.25 相对 v1.23.24

【要解决的问题】上一版把「结构覆盖率」**换了口径并改名成「独立度」**（结构视角：有多**新**）。
改名是对的（旧口径确实跟提示词反着来），但**原名位置就此空着** —— 这说明还有一路
视角没被承载：结构除了「新不新」，还该看「**活不活**」。

  那一路该按什么算？三个「不可判定通道」读数原本视角混乱、读者易混：
  清晰度（模型自评）、独立度（结构与方面重不重合）、对齐覆盖率（方面被对上几成）。
  缺的那一路，问的应是「结构**自己**会不会再被呼回来」。

【改了哪几处】
  1. **结构覆盖率**按本义重设计并加回 ——
     结构覆盖率 = **被研究出自己触及的概率**
     = 后续圈**自己的产物**（线头 / 探针 / 自报触及）里再次呼应到的
       `structural_amps` 条数 ÷ `structural_amps` 总条数。
     · 分子凭据 = `_und_self_touch_texts()`：`threads[].desc` / `threads[].polarity_why`
       / `probes[].question` / `covered_unders[]`。
       ★ **刻意不取** `und_aspects`（会和独立度互为函数 ⇒ 破坏正交）、
         也不取 `evidence[].cite` 的 `A#`（实测引用 **0 次**）。
     · 分母 = 结构条数（**与独立度同分母**，故两者可横向比、可验正交）。
     · 空池记 `None`（不可计算）—— **不印 0.00** 冒充读数。
     · 新增键 `last_sc_ratio` / `last_sc_pool` / `last_sc_touched` / `sc_history`
       / `sc_touched_amps`（`Pool.add_undecidable`）。
     · `Pool._und_self_touch_texts()` 新增方法；`Pool.covered_unders` 新增字段
       （并入 `Pool.to_dict` 白名单 —— 冒烟前向守卫当场抓出漏挂）。
     · `add_undecidable` 加 `covered_aspects: Optional[List[str]] = None`（默认 None ⇒ 旧调用不受影响）。
     · 调用点 `_apply_view_to_pool` 传 `view.covered_aspects`。
  2. **第七节三个读数并列印出**：清晰度 ｜ 独立度 ｜ 对齐覆盖率 ｜ 结构覆盖率，
     每段都写口径来源与「量的是什么」（结构覆盖率那行标注「量的是『结构有多活』，
     不是方面被覆盖几成」）。渲染点：产物 `_und_channel_line`、终端 `_update_trackers`。
  3. 旧键 `last_struct_coverage` / `struct_coverage_history` / `last_struct_hit`
     / `struct_trace` **一字未动**。
  4. **提示词没动** —— 本版只加读数与产物描述，不改任何判定逻辑。

【一轮诊断：六个候选凭据全部实测排除】
  ① `structural_amps` 撞 `und_aspects`：4/5 份 max overlap ≤ 0.17（= 上一版要换掉的那条）
  ② `aligned_amps` 撞方面：已被「对齐覆盖率」占用
  ③ `covered_aspects` 撞方面：实测 `aligned ⊇ covered` ⇒ 是 ② 的子集
  ④ `struct_trace.newly`：**全空**（引用体系已改）
  ⑤ `amp.polarity`：**100% 填充** ⇒ 零判别力
  ⑥ 引用表 `A#`：真产物里 **0 次** ⇒ 分母非零分子恒 0
  ⇒ 由用户给出定义「**是被研究出自己触及的概率**」破局。

【验收】
  · 冒烟 `smoke_test.py`：✓=151 / ✗=0（exit 0）
  · 变异体 `_mut_v12325.py`：**8 / 8 判红 + 正对照判绿**
  · 真产物对照 `_cmp_v12325_structcov.py`：新旧不同 **7/7**；新值范围 **[0.143, 1.000]**
    （有跨度）；独立度范围 [0.800, 1.000]；两者 **Pearson r ≈ 0.13（正交）**
  · 配置同步：164 键 / **0 差异**（本版无新增配置键）
  · 主文件 CRLF 自检：`CRLF=18593 / 裸 LF=0 / lone CR=0 / \\r\\r\\n=0`

★ v1.23.25 收束摘要
  交付物：`元DGTF-V1.23.25.py`（18593 行 / 896053 bytes / 纯 CRLF；上一版 18491 行）。
  改了哪几处：11 处编辑（版本号 ×2 / 新键初始化 / 自触及计算 / `_und_self_touch_texts`
  新方法 / `covered_unders` 累积 / `add_undecidable` 签名 / 产物渲染 / 终端渲染 /
  调用点传参 / `Pool` 字段 / `to_dict` 白名单）+ smoke 4 处同步 + 配置 2 处同步。
  验收数字：冒烟 151✓/0✗；变异体 8/8；真产物 7/7 新旧不同、r ≈ 0.13；配置 0 差异。
  未做：**真跑（full run）** —— 本版改的是读数与描述（喂进模型的是多一行自述式读数），
  真产物对照已在 7 份真实历史上验证新旧口径，故以零成本对照替代单次真跑；
  如需真跑证据，留待下次 `--phase all` 时顺带比对第七节三读数并列的实际输出。

"""


def read_crlf(p: pathlib.Path) -> str:
    b = p.read_bytes()
    return b.decode("utf-8").replace("\r\n", "\n")


def write_crlf(p: pathlib.Path, txt: str) -> None:
    assert "\r" not in txt, "文本里残留 \\r"
    data = txt.replace("\n", "\r\n").encode("utf-8")
    p.write_bytes(data)


txt = read_crlf(P)
anchor = "\nv1.23.24 相对 v1.23.23\n"
n = txt.count(anchor)
print(f"锚点命中 {n} 次（期望 1）")
assert n == 1, "锚点不唯一"

# 负对照 1：段序严格递减（v1.23.25 必须排在 v1.23.24 之前）
assert txt.index("v1.23.24 相对 v1.23.23") < txt.index("v1.23.23 相对 v1.23.22")

txt = txt.replace(anchor, "\n" + NEW_SEG + "v1.23.24 相对 v1.23.23\n", 1)
write_crlf(P, txt)

# 自检
t2 = read_crlf(P)
assert t2.count("v1.23.25 相对 v1.23.24") == 1, "新段没插进去或重复"
assert t2.index("v1.23.25 相对 v1.23.24") < t2.index("v1.23.24 相对 v1.23.23"), "段序错"
assert t2.count("★ v1.23.25 收束摘要") == 1, "收束摘要缺或多"
# 段序严格递减（只查最近 4 段）
import re
vers = re.findall(r"^v(\d+)\.(\d+)\.(\d+) 相对 v", t2, flags=re.M)
nums = [tuple(int(x) for x in v) for v in vers]
assert nums == sorted(nums, reverse=True), f"段序不是严格递减：{nums[:6]}"
assert len(nums) >= 10, f"段数 < 10（{len(nums)}）—— 防「搬出去变删掉」"
b = P.read_bytes()
assert b.count(b"\r\r\n") == 0, "出现 \\r\\r\\n"
assert b.count(b"\r\n") == b.count(b"\n"), "不是纯 CRLF"
print(f"✓ CHANGELOG 已插入 v1.23.25 段；段数 = {len(nums)}；首 5 段 = {nums[:5]}")
print(f"✓ 纯 CRLF 自检通过（CRLF={b.count(b'\\r\\n')}）")
