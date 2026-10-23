# -*- coding: utf-8 -*-
"""[v1.22.2] 定稿：版本号两处 + changelog 段（只动 docstring 与版本字面量）。
幂等：哨兵串。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.2.py"
SENTINEL = "v1.22.2 ── 收尾补充"

src = TARGET.read_bytes().decode("utf-8")
assert src.count("\r\n") == src.count("\n"), "源文件不是纯 CRLF"
src = src.replace("\r\n", "\n")
if SENTINEL in src:
    print("== 已定稿，跳过 =="); sys.exit(0)


def sub_once(text, old, new, tag):
    n = text.count(old)
    assert n == 1, f"[{tag}] 锚点出现 {n} 次（应为 1）"
    return text.replace(old, new)


# 1 标题
src = sub_once(src, "\n元 DGTF · v1.22.1\n", "\n元 DGTF · v1.22.2\n", "标题")

# 2 __version__
src = sub_once(src, '__version__ = "1.22.1"\n', '__version__ = "1.22.2"\n',
               "版本号")

# 3 changelog 段（插在 v1.22.1 段之前）
CHANGELOG = """v1.22.2 ── 收尾补充 + W 系列前置（任务书核验 / P4 口径统一 / not_do / answers 长度 / W 清单）

  ★ 本版是**最后一个单文件版** —— W 系列（核心联网）启动后代码结构会变。
  性质：v1.22.1 的收尾补充 + W 系列的前置。四阶段全部是**收口**，不新增能力。

  【阶段 0】任务书核验（新范式）
    · 把「前提不成立 / 骨架 bug / 判据不可达 / 授权不清」前移到**执行前**。
    · 本轮实测发现 **9 处**（`_taskbook_audit_v1222.md`），其中 8 处改了设计。
    · 最有价值的一条：任务书只描述了「入口」（prompt schema），
      没描述「出口」——`dec_norm` 是显式白名单 dict，不列新键就**静默吞掉**
      模型产出，现象与「模型不产」一模一样。凡加新产出字段，必须同时核
      **prompt schema → 归一化白名单 → 抽取函数 → 渲染点**四处。

  【阶段 1】P4 OFF 臂口径统一
    · 根因：`stability` 只有多票路径写；单票（OFF）臂连键都没有，
      而头部却按 `stability` 统计 → 印出「三态多票 high 0 / medium 0 /
      low 0　一致率 0% ⚠️ unstable」——**非读数被当成测量值**。
    · 新增模块级 `_single_vote_stability(sq)`：单票口径 = 单票 vs 拆解原标签
      （一致 high / 不一致 low / 有判无原标签 medium / **未被判到 = abstained**）。
    · 新增 `MetaDGTF._write_tri_stability(subs, mode, from_votes)`，
      并在**每个出口前**调用（单票实现有 5 处早退 `return 0, 0`，只写尾部
      会让「判决失败」这一情形在产物里彻底读不到 —— 那正是同一个 bug 的形态）。
    · 头部改成**按 `_vote_mode` 分口径**印：`三态判决（单票/多票）` +
      `口径=单票 vs 拆解原标签 / 三票之间`；分母**只数已判条**，弃权条单列。
      **不再把单票路径印成「三态多票」**。
    · 两臂的 `stability` **不是同一把尺子**（多票量的是「三票之间」），
      拿两臂的数直接比会得到错结论 —— 所以口径必须印在标题里。

  【阶段 2】schema 加 not_do（decision 取向的第三分）
    · `_he` 的 `decidable_product` schema 加 `not_do[]`（what ≤40 字 / why ≤40 字）
      + 约束段（「至少 1 条，最多 3 条；不硬凑」）。
    · ★ `dec_norm` 白名单同步加 `"not_do": _norm_schema_not_do(...)` ——
      不加这一行，模型产了也进不了 `view.decidable_product`。
    · 新增 `_norm_schema_not_do`（空 what 丢弃、最多 6 条，与
      `_norm_schema_actions` 同款）；`_extract_not_do` 改成 schema 优先 +
      词法兜底（原实现整体改名 `_extract_not_do_lexical`，正文一字未动）。
    · `not_do_missing` 语义更新：= **模型没按 schema 产出 not_do**，
      不是「词法没抽到」；只认 `_source == "schema"`。
    · rubric **判据一字未改**（`score_actions` 早已 `if nd: s += 1`）——
      改的是「能不能拿到这个量」。上限 2/3 → 3/3 由 schema 打通带来。

  【阶段 3】answers 最短长度约束
    · 动机：`_overlap_coef` 分母取 `min`，2 字 answer 被长 aspect 包住
      就是 1.000（假命中）—— W 系列自动生成 short answer 会放大它。
    · `external_anchor` 加 `answers_min_len: 6` / `answers_max_n: 5`
      （后者原先是硬编码 `[:5]`，本版提成配置，值不变 = 行为不变）。
    · `_load_anchors` 过滤并留痕 `anchors.<id>._answers_dropped`。
    · ★ **两条告警必须分开**：`_anchor_answers_warning`（「全部 N 条锚点
      **未声明** answers」）已被 v1.22.1 P2b 占用，任务书原本要复用它 ——
      直接赋值会静默摧毁既有留痕，且过滤后 answers 全空会**反向**触发它、
      说出假话。本版新增独立属性 `_anchor_answers_filtered`，
      并把「已声明但被过滤」从「未声明」里刨掉。
    · 产物头部加「⚠️ **锚点 answers 警告**」一行；packed 加 `answers_filtered`。
    · 阈值一律没动：`_overlap_coef` 分母仍是 min、0.6 一字未改。

  【阶段 4】W 系列启动检查清单（只出清单，不出代码）
    · `docs/W系列启动检查清单-v1222.md` 六类 A~F：前置 / W 任务书核验 /
      四条宪法级特性（每条带冒烟断言路径）/ 独立通道 / 配额三层 /
      锚点与联网的边界。
    · 结论二选一（可以启动 / 不启动），每条带断言或命令依据。

  【配置同步】`dgtf_config.yaml` → v1.22.2：头部版本 + 升级段 +
    补 `answers_min_len` / `answers_max_n`（按默认值写。
    `load_config` 前后逐字对比为 **True** = 行为不动）。

  【怎么退回旧行为】
    · P4 单票口径：`actions.tri_multi_vote` 置 false → 走单票路径（口径仍会印）。
    · not_do：`_extract_not_do` 自动回落词法（老产物 / 未升级 schema 的跑批）。
    · answers 长度：`external_anchor.answers_min_len` 置 0 → 不过滤。

  【未做 / 遗留】
    · 全量 20 题跑批未做（本轮口径：**主要做检查**，每题只跑 2 次）。
      P4 的两臂对照证据以**离线 mock E2E**（确定性、可复现）为主，
      真跑仅作分布量级观察。
    · W 系列本体未启动（本版只出清单）。

"""
src = sub_once(src, "\nv1.22.1 ── 三档收尾", "\n" + CHANGELOG + "v1.22.1 ── 三档收尾",
               "changelog")

out = src.replace("\n", "\r\n")
b = out.encode("utf-8")
assert b.count(b"\r\n") == b.count(b"\n")
assert b.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert b.count(b"\r") == b.count(b"\r\n"), "出现裸 CR"
TARGET.write_bytes(b)
print("OK: v1.22.2 定稿（标题 / __version__ / changelog 段）")
