#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段5] 机制审计的引擎侧落点 + docs 文档（只标不删，Step 5.2/5.3）。

- 三条 `# [AUDIT-122] 标 pending_fix：<理由>` 注释（对应三处**已知未收口**）
- 两个登记常量 `_AUDIT122_PENDING_FIX` / `_AUDIT122_DUAL_IMPL`
  （与源码注释条数**两向对账**，冒烟会核）
- `save_result` 头部渲染「机制审计：pending_fix N 项，双实现 M 项」
- `docs/机制审计-v122.md`：`## pending_fix` + `## 双实现清单` + `## resolved`
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "元DGTF-V1.22.0-rc1.py"

A_CONST = "def _anchor_tier(cfg) -> str:\n"
B_CONST = '''# [v122 P5 G5.3] 机制审计登记表。**必须与源码里 `# [AUDIT-122]` 注释条数
#   两向对上账**（冒烟 check_v122_phase5 会核）—— 单向登记会腐烂成
#   「写了一次就再没人看」的装饰。
_AUDIT122_PENDING_FIX = 3
_AUDIT122_DUAL_IMPL = 2


# [AUDIT-122] 标 pending_fix：`as_evidence` 的**布尔兼容路径**保留一版。
#   v1.21.75 的 `True/False` 写法仍被 _anchor_tier 认（True→evidence），
#   等外部调用点全部迁到五档字符串后即可删；本版不动。
def _anchor_tier(cfg) -> str:
'''

A_PF1 = "    def _auto_plan(self, question: str) -> dict:\n"
B_PF1 = '''    # [AUDIT-122] 标 pending_fix：与模块级 `auto_plan()` 的**归一化规则**
    #   仍是两份（模式白名单 + 逐层圈数钳位 + 中位数补漏 + 低置信退 serial）。
    #   v1.22 先把「同一个函数」收口（本方法退薄壳），再谈合并归一化 ——
    #   后者要贯通 plan_orientation / plan_resources 的签名，属架构批。
    def _auto_plan(self, question: str) -> dict:
'''

A_PF2 = ("        # [v122 阶段2 G2.2] 三态多票化：开关打开时走多票；关闭时下面这段\n")
B_PF2 = ("        # [AUDIT-122] 标 pending_fix：单票实现整段保留（同签名、可退路）。\n"
         "        #   多票稳定运行若干批后再评估归档 —— 本版**不删**任何机制。\n"
         + A_PF2)

A_PF3 = "def _anchor_tier(cfg) -> str:\n"
B_PF3 = '''# [AUDIT-122] 标 pending_fix：`as_evidence` 的**布尔兼容路径**保留一版。
#   v1.21.75 的 `True/False` 写法仍被 _anchor_tier 认（True→evidence），
#   等外部调用点全部迁到五档字符串后即可删；本版不动。
def _anchor_tier(cfg) -> str:
'''

A_HDR = '''        # [v122 阶段2 G2.5/G2.6] 三态多票 + **冻结**\n'''
B_HDR = '''        # [v122 阶段5 G5.5] 机制审计：pending_fix / 双实现各几项。
        #   数字由登记常量给，冒烟负责核它和源码注释条数是否一致。
        f.write(f"**机制审计**：pending_fix {_AUDIT122_PENDING_FIX} 项，"
                f"双实现 {_AUDIT122_DUAL_IMPL} 项"
                f"（详见 docs/机制审计-v122.md）\\n\\n")
        # [v122 阶段2 G2.5/G2.6] 三态多票 + **冻结**\n'''

DOC = """# 机制审计 · v1.22

> 来源：`_audit_v122_dead_mechanisms.py`（明细表见根目录
> `audit_v122_dead_mechanisms.md`）。本文件是**人读**的那一份：写清
> 每一项为什么留着、下一步该谁动、动了怎么验。

## 一、审计口径

三列命中数：源码 / 日志 / 产物。**日志侧与产物侧的标记串必须分别数** ——
本项目已知的坑是同一件事两侧写法不同（日志 `【螺旋停止】…` vs 产物
`**螺旋停止**：…`），照一侧数另一侧会数出 0，然后被误读成「出口没通」。

判定三档：`可达` / `仅源码` / `需核对`。**「零触发」不等于「没用」**：
要分清 ①条件不可达（真该死）②条件窄但在特定情形成立（留着）
③机制压根没工作（重写）—— 分不开就必须做**负对照**。

## 二、13 项机制一览（判定见 `audit_v122_dead_mechanisms.md`）

| # | 机制 | 触发条件 |
|---|---|---|
| 1 | `escalate_starve_rounds` | 连续 N 圈无进展 + 名下有账 |
| 2 | `no_push_when_idle` | 空转类判据 + 未深入方向 |
| 3 | `_reopen_closed_debt` | 分类被推翻 + 曾有 escalated |
| 4 | `stable_layers` | 悬置连续 N 圈同批 |
| 5 | `both_quota.max_ratio` | both 占比超阈值 |
| 6 | `both_tighten_ratio` | 同上，改判 |
| 7 | `_all_settle_streak` | 元层清算未下降 |
| 8 | `min_rounds` | layer_no < min_r |
| 9 | `structure_saturation` | 每 N 圈无新维度 |
| 10 | `_budget_exhausted` | 调用数超预算 |
| 11 | `DecidabilityFreeze.verify` | 签名不匹配 |
| 12 | `triage_downgrades` | 信息不足型 und + 锚点命中 |
| 13 | `_anchor_crosscheck.conflict` | 结论与锚点相反 |

## pending_fix

登记表与源码里 `# [AUDIT-122]` 注释**两向对账**（冒烟 `check_v122_phase5`）。
本版**只标不删**。

| # | 机制 | 为什么 pending | 下一步 | 怎么验「修好了」 |
|---|---|---|---|---|
| 1 | `_auto_plan` 与模块级 `auto_plan` 的**归一化规则两份** | v1.22 已收口「同一个函数」（方法退薄壳），但模式白名单 + 逐层钳位 + 中位数补漏 + 低置信退 serial 这段规则仍是两份 | 贯通 `plan_orientation` / `plan_resources` 的签名，把归一化抽成唯一实现 | 同一 mock 输入喂两条路径，mode 与（按 route 裁剪后的）rounds 逐字相同；负对照把其中一份改坏必须判不一致 |
| 2 | `_adjudicate_sub_tristate` 单票实现整段保留 | 多票刚上线，需要一条可退路；本版不删任何机制 | 多票稳定运行若干批后评估归档 | 关闭 `actions.tri_multi_vote` 时行为与 v1.21.77 逐字相同（已有冒烟核） |
| 3 | `as_evidence` 的**布尔兼容路径** | v1.21.75 的 `True/False` 写法仍被 `_anchor_tier` 认（True→evidence）；外部调用点未知 | 外部调用点全部迁到五档字符串后删兼容分支 | grep 全库无 `as_evidence: True/False` 用法；`_anchor_tier` 可只认字符串 |

## 双实现清单

| 机制 | 实现 A | 实现 B | 行为相同? | 处理 |
|---|---|---|---|---|
| `auto_plan` | 模块级 `auto_plan`（`plan_orientation` + `plan_resources`，两次调用） | `MetaDGTF._auto_plan`（一次调用定 mode+rounds） | **已收口**：方法退薄壳，函数唯一；内部归一化仍两份 | 归一化合并列入 `pending_fix` #1 |
| `_rephrase_streak` | `_run_layer` 串行侧的 `max(meta_idle_streak, _mi_from_view)` | `_b_check_stop` 并行侧的 `max(state[...], _mi_from_view)` | **已收口**：两处都调 `_compute_rephrase_streak`（`def` 计数 = 1） | 已解决，见 `## resolved` |

## resolved

（v1.22 阶段 6 收口后回填。）

- `auto_plan` 双实现：**函数级已收口** —— `MetaDGTF._auto_plan` 退成薄壳
  `return auto_plan(question, self.config, llm=self.llm)`，模块级 `auto_plan`
  是唯一实现；行为对照（`_probe_v122_phase6.py` before/after）见
  `v122_phase6_报告.md`。
- `_rephrase_streak` 双实现：**已收口** —— 新增模块级
  `_compute_rephrase_streak(view, state)`，`def` 计数 = 1，串行/并行两个
  调用点都改调它。
"""


def main() -> int:
    b = ENGINE.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")
    for name, old, new, want in [
            ("dual_comment", A_PF1, B_PF1, 1),
            ("single_vote_comment", A_PF2, B_PF2, 1),
            ("header", A_HDR, B_HDR, 1)]:
        got = s.count(old)
        assert got == want, f"[{name}] 锚点 {got} 次"
        s = s.replace(old, new, want)
        print(f"  ✓ {name}")
    # 常量 + bool 兼容注释一起插在 _anchor_tier 之前
    got = s.count(A_CONST)
    assert got == 1, f"_anchor_tier 锚点 {got} 次"
    s = s.replace(A_CONST, B_CONST, 1)
    print("  ✓ 登记常量 + tier pending 注释")

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    ENGINE.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))

    n_pf = out.count("# [AUDIT-122]")
    assert n_pf == 3, f"pending 注释 {n_pf} 条，登记常量写的是 3"
    (HERE / "docs").mkdir(exist_ok=True)
    (HERE / "docs" / "机制审计-v122.md").write_bytes(DOC.encode("utf-8"))
    print(f"✓ 阶段5 完成：pending 注释 {n_pf} 条；行数 {len(out.splitlines())}；"
          f"docs/机制审计-v122.md 已写")
    return 0


if __name__ == "__main__":
    sys.exit(main())
