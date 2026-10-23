#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.21.71 · docstring 收尾补丁（**只动 docstring**）

用法：
    python _mk_v71_doc_patch.py

铁律（本项目固定流程第 10 条）：
  · 只改 docstring：改前 / 改后「抠掉 docstring 的源码」必须**逐字相同**；
  · docstring 里不许有单反斜杠（否则那条断言会静默失效）；
  · 主文件纯 CRLF，走双向断言。
"""
import sys
from pathlib import Path

F = Path(__file__).resolve().parent / "元DGTF-V1.21.71.py"
raw = F.read_bytes().decode("utf-8")
assert raw.count("\r\n") == raw.count("\n"), "不是纯 CRLF"
assert raw.count("\r") == raw.count("\r\n"), "有裸 CR"
s = raw.replace("\r\n", "\n")

_i = s.index('"""')
_j = s.index('"""', _i + 3)
DOC = s[_i:_j + 3]
EXEC_BEFORE = s[:_i] + s[_j + 3:]
assert DOC.count("\\") == 0, "docstring 里有反斜杠，抠-扫断言会失效"

BAR = "\u2550" * 60
LINE = "\u2500" * 60

# ---- 1. 把「真跑验收」那句改成**实际做了什么** ----
OLD_PLAN = """  **真跑验收**：serial 一次（四层各 1 圈，专门验 F1 的单圈收尾）、
  B 模式一次（验并行通道的同一处），`--rounds "0:1,1:1,both:1,all:1"`
  与默认四层 2 圈各跑，逐层核对【螺旋停止】与【收尾留痕】。
"""
NEW_PLAN = """  **真跑验收**（结果见下面的收束摘要）：同题（老城区内涝）跑两次，
  都是 `--route 0,1,both,all --rounds "0:1,1:1,both:1,all:1"`：
    · V71S（serial）10.3min / 49 calls；
    · V71B（B 模式）7.3min / 52 calls。
  两跑都满足 F1 的判据：日志 **4 段**「收尾留痕」（圈数 1/1/1/2、
  角色记录齐）、**4 条** ⏹ 停止交代；产物 md **4 处**`**螺旋停止**`、
  **4 处**`**实际走了`、**4 张** round_log 表，头部调度
  `修行(1圈) → 研究(1圈) → 对撞(1圈) → 元(2圈)`。
  ★ **没有**跑「默认四层 2 圈」的真跑 —— 那条路径被改动的只是**条件
    变宽**（`rounds_n > 1` → 恒真），`rounds_n > 1` 时的行为逐字未变；
    它由冒烟矩阵（各模式 2 圈全跑通）+ 离线 2 圈复核（4 段收尾留痕、
    圈数 2/2/2/3）覆盖，花钱再跑一次买不到新信息。
"""
assert s.count(OLD_PLAN) == 1, f"真跑计划段命中 {s.count(OLD_PLAN)} 次"
s = s.replace(OLD_PLAN, NEW_PLAN, 1)

# ---- 2. 追加收束摘要 ----
ANCHOR = "  与默认四层 2 圈各跑，逐层核对【螺旋停止】与【收尾留痕】。\n"
if ANCHOR not in s:
    ANCHOR = ("  它由冒烟矩阵（各模式 2 圈全跑通）+ 离线 2 圈复核（4 段收尾留痕、\n"
              "    圈数 2/2/2/3）覆盖，花钱再跑一次买不到新信息。\n")
assert s.count(ANCHOR) == 1, f"收束摘要插入锚点命中 {s.count(ANCHOR)} 次"

SUMMARY = """
  @@LINE@@
  ★ v1.21.71 收束摘要
  @@LINE@@

  **交付物**：元DGTF-V1.21.71.py（纯 CRLF，18524 → 行数见下）；
    smoke_test.py 加 **11 条** `check_v71_*`（每条带负对照 / 反方向）；
    `_probe_v71.py`（F1~F11 改前 / 改后同一支探针）；
    `_probe_v71_render.py`（F1 的**出口** E2E：日志 + 产物两侧）；
    `_mk_v71_patch.py` / `_mk_v71_smoke_patch.py`（27 + 3 处替换，
    每处断言命中恰好 1 次）；`v71_报告.md`；真跑 sidecar
    （`verif_V71S.*` / `verif_V71B.*`）。

  **改了 11 处代码**（F1~F11），**没动任何阈值 / 常量**：
    · F1 两处 `> 1` 门（serial + B/C/D-H）去掉；
    · F2 `main()` 的 save_result 包 try/except + `sys.exit(1)`；
    · F3 `_build_inp_meta` 上游 view 与池**配对过滤** + 三处留痕；
    · F4 `load_config` 加 `not path` 短路；
    · F5 两处早退补 `_dispatch_for_pack`（模式名取实际变量）；
    · F6 加运行内缓存 `_ext_assess_cache` + 薄壳 `_cached_ext_assess`，
      两处调用点改走它，`run()` 开头重置；
    · F7 池评估加性带出 `_evidence_full`，兜底重算改用它；
    · F8 只加**漂移检测器**（docstring 标注 + 一致性冒烟），不合并实现；
    · F9 `_STOPWORDS` 拆成 `_STOPCHARS`（保留）+ 21 个多字停用词；
    · F10 `coverage_parts` 的 `cfg` 改可选，调用点传真配置；
    · F11 `_quality_check` 加 `write_diag` 开关，收尾复核传 False
      （压制时打 `logger.info`，不静默）。

  **改前 / 改后量化对照**（`_probe_v71_before.txt` / `_after.txt`）：
    · [A] 四层各 1 圈：0/1/both 三层 roles_run·rounds_cap·round_log
      从 0/0/0 → 1/1/1；`_b_finalize_layer(total_rounds=1)` 从空 → 有；
    · [B] 保存失败：从「异常冲出 main()」→ 「SystemExit(1) + 打印」；
    · [C] 非法 entry：`KeyError: '9'` → 剔除 + 留痕；
    · [D] `load_config("")`：警告 True → False，坏 yaml 仍 True；
    · [E] 空 active：dispatch 键集 `[]` → 8 键（含四个守卫键、模式名 C/G）；
    · [F] 一次 run 的外部评估：**2 → 1**（站点计数 1+1 → 1+0）；
    · [G] 缓存 / 兜底 `_und_untraced`：不一致 → 一致；
    · [H] `_tokenize`：12 → 7 个词，多字停用词被挡、内容词保留；
    · [I] `coverage_parts(pool)`：TypeError → 可用（cfg 默认 None）；
    · [J] 收尾站点的 dump 尝试：4 → 0（圈内站点仍写，反向锁成立）；
    · [K] 两实现三组输入逐字一致；把一份改坏立刻判不一致。

  **出口 E2E**（`_probe_v71_render.py`，四层各 1 圈，离线）：
    · v1.21.70：serial「收尾留痕 0 段 / md 螺旋停止 1 处 / round_log 表 0 张」，
      B「1 段 / 1 处 / 1 张」；
    · v1.21.71：两种模式都是「4 段 / 4 处 / 4 张」。
    ⇒ F1 不只是"字段回填了"，**两个出口都通了**。

  **冒烟**：exit 0 / **0 个 ✗**；11 条新 check 全 ✓。调用次数的间接证据：
    同一套 mock 作业里 **9 个模式的 LLM 调用数一律 −1**（78→77、91→90、
    38→37）—— 正是 F6 省掉的那一次重复外部评估（没有别的改动会改计数）。

  **真跑**：V71S（serial，四层各 1 圈）10.3min / 49 calls / 0 异常 /
    views 四层齐、views_errors 全空、meta_closure clean=True（by_id=2）；
    V71B（B 模式，同参数）7.3min / 52 calls / 0 异常 / 同上。
    两跑都满足「4 段收尾留痕 + 4 条停止交代 + md 4/4/4」。

  **零触发的项（如实记，不当成"生效"）**：
    · F11 在两跑里**都没触发**收尾站点的压制（两跑各只有 1 个诊断文件、
      且来自圈内站点，抑制日志 0 条）——它的有效性由定点探针与冒烟证明；
      价值在**预防**：F1 之后单圈层也进收尾，若不同时加这个开关，
      单圈跑会**新增 4 份**收尾诊断。
    · F3 / F4 / F5 / F7 / F8 / F10 都是边角路径，正常真跑不经过；
      证据全在探针 + 冒烟。
    · F9 是运行期可见变化（分词变了），但两跑没有可归因的差异读数，
      不作"生效"宣称。

  **未采纳 / 留存项**：
    · F9 的 `_STOPCHARS` 保留但已无引用（加性优先，不删旧行）；
    · F11 的替代做法「按**内容**去重、两个站点都留」比关一张更精确，
      但要多一个内容指纹键；归可观测性批；
    · F8 的方案 B（统一成唯一实现）未做，见上。

  **纪律**：先量后改（before/after 同一支探针）；加性优先（新键
    `_evidence_full` / 新参数默认值 / 新方法，不删旧行）；失败必须留痕
    （F2 打印 + 退出码、F3 三处、F9 注释、F11 的 logger.info）；
    不改任何阈值 / 常量；docstring 里零反斜杠。
"""

SUMMARY = (SUMMARY.replace("@@LINE@@", LINE))
s = s.replace(ANCHOR, ANCHOR + SUMMARY, 1)

# ---- 3. 抠 docstring 后必须逐字相同 ----
_i2 = s.index('"""')
_j2 = s.index('"""', _i2 + 3)
DOC2 = s[_i2:_j2 + 3]
assert DOC2.count("\\") == 0, "新 docstring 里出现了反斜杠"
EXEC_AFTER = s[:_i2] + s[_j2 + 3:]
assert EXEC_AFTER == EXEC_BEFORE, "可执行语句被改动了 —— 本补丁只许动 docstring"

out = s.replace("\n", "\r\n")
assert out.count("\n") == out.count("\r\n"), "回写后有裸 LF"
assert out.count("\r") == out.count("\r\n"), "回写后有裸 CR"
F.write_bytes(out.encode("utf-8"))
print(f"✓ docstring 补丁已写：{F.name}")
print(f"  docstring 字符数 {len(DOC)} → {len(DOC2)}（+{len(DOC2) - len(DOC)}）")
print(f"  可执行部分逐字未变（{len(EXEC_BEFORE)} 字符）")
print(f"  文件 {out.count(chr(10))} 行（按 LF 计）/ "
      f"{len(out.encode('utf-8'))} 字节")
sys.exit(0)
