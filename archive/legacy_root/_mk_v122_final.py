#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 F.2] 定稿：从 rc1 派生 `元DGTF-V1.22.0.py`。

三处改动，除此之外与 rc1 **逐字相同**（这样 Step 6.4 的产物对照才有意义：
它排除的是「定稿时顺手改了行为」）：
  1. 标题行 `元 DGTF · v1.22.0-rc1` → `元 DGTF · v1.22.0`
  2. `__version__ = "1.22.0-rc1"` → `"1.22.0"`
  3. changelog 顶部插入 `v1.22.0 ── ...` 六段

★ docstring 里**零反斜杠**（宪法级约束 08）。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RC = HERE / "元DGTF-V1.22.0-rc1.py"
FINAL = HERE / "元DGTF-V1.22.0.py"

CHANGELOG = '''v1.22.0 ── 六阶段改造（目标分层 / 效果可测 / 外部可对账 / 机制精简）
  本版是 v1.21.77 的六阶段**加性**改造。红线守住：不删任何机制代码
  （纯删除行 0；AST 符号消失 0 项；新增 27 项逐条有解释，见
  _v122_ast_registry.json）。逐阶段报告见 v122_phase1~6_报告.md。

  一、Bench 骨架 + 目标函数分层（本版目标 1+5）
    · bench/questions 20 题 / bench/gold 3 题；
      bench_run / bench_score / bench_diff / bench_report / bench_calibrate
    · Phase.objective 四层：manifest / truth / collision / closure
    · coverage_of / coverage_parts 加 entry 形参：entry 不是 "1" 就返回
      None —— 修行层不再被覆盖率评价（那是用错的尺）
    · _classify_unsaid（real / lazy，View 与 dict 两形态都吃）
      + 修行层 stop_reason 追加「本轮显形 / 未生质量」
    · 产物头部四行「分层目标」（**计数**口径，objective 折进括号）
  二、三态多票 + 冻结 + 人工校准（本版目标 3）
    · _TRI_VOTE_PROMPTS 三票独立（严格 / 宽松 / 中立），多数票定标签
    · 无多数票 → partial + unstable + 进校准队列。不落 undecidable ——
      那会把分母砍一截，正是 v1.21.62 修过的形态
    · DecidabilityFreeze：签名覆盖 id / 当前标签 / 当前可答性 /
      冻结布尔 / 冻结标签五元组
      ★ 走过的弯路：早先签名里 is_answerable 是**由当前标签现推**的，
        于是「只翻 _frozen_answerable、不动标签」改不动签名。任务书
        Step 3.3 的冒烟标的正是这一刀；探针实测返回「未判红」，已修，
        并把这条收进冒烟当负对照。
    · bench_calibrate export / import（人在「人工 verdict」列填）
  三、decision 模式强制行动闭环（本版目标 4）
    · actions.landing_decision 开关；render_landing 退成分流壳，
      原实现整体改名 _render_landing_boundary（一行没删）
    · _render_landing_decision 六段模板；_extract_actions 六字段
      （verb / object / owner_role / deadline_hint / acceptance / fallback）
      + _extract_not_do
    · 硬约束：action_incomplete（行动 < 3 条）/ not_do_missing
    ★ 判据随实现更新：v64 A 那条「落地层顶部池级留痕」在新模板上丢了。
      修法不是把判据改宽，而是把那段抽成 _pool_meta_summary 给两个模板
      共用 —— 本项目头号复发问题就是「同一条逻辑两条通道各写一份」。
  四、外部锚点变真证据（本版目标 2）
    · as_evidence 五档（off / record / crosscheck / evidence / gate）
      + tier_floor / api_key_env / cache_ttl_hours / retriever；
      旧布尔写法仍被 _anchor_tier 认（True → evidence）
    · AnchorRetriever：snapshot 零调用；tavily 真检索 + 24h 落盘缓存
    · X# 进引用表加 tier 门（tier ≤ tier_floor 才收）
    · 冲突留痕：view.errors + pool.meta；gate 档进 blocked_conclusions
    · triage 降级清单（**只出建议，不自动改判定** —— 无证据的自动降档
      正是本版要避免的事）
    ★ 踩到的坑：往 DEFAULT_CONFIG["external_anchor"] 加 as_evidence 时，
      那个键**已经存在** —— dict 字面量后者胜，新值被静默丢掉，直到
      验收报「as_evidence=False ∈ 五档」才暴露。为此加了全文件 AST 判据
      「dict 字面量不许有重复常量键」（check_v122_dup_dict_keys）。
  五、机制审计（本版目标 6A，只标不删）
    · _audit_v122_dead_mechanisms.py → audit_v122_dead_mechanisms.md（13 项）
    · docs/机制审计-v122.md：## pending_fix 3 项（与源码 # [AUDIT-122]
      注释**两向对账**）+ ## 双实现清单 + ## resolved
    · 产物头部渲染「机制审计：pending_fix N 项，双实现 M 项」
  六、双实现收口（本版目标 6B）
    · auto_plan 收口：唯一实现在模块级。给了 llm 走**单调用**路径
      （原 _auto_plan 的正文原样搬入并**内联**，不新增函数节点）；
      不给 llm 走 plan_orientation + plan_resources 两段（对外 API）。
      MetaDGTF._auto_plan 退成薄壳
    · _compute_rephrase_streak：串行 _run_layer 与并行 _b_check_stop
      各写一份的那行数合并为唯一实现（AST 定义数 = 1）
    ★ 行为对照：_probe_v122_phase6.py 的 before / after 快照里，
      A（方法入口）/ B（模块两调用入口）/ D（复述圈数结果）三格逐字相同；
      唯一差异是新增的 C 入口（auto_plan(..., llm=)）与 D 的实现标签。

  未采纳项（如实记，不假装做过）：
    · 拆模块（6C）只出方案不落地 —— docs/拆模块方案-v122.md
    · auto_plan 的**归一化规则**仍是两份（模式白名单 + 逐层钳位 +
      中位数补漏 + 低置信退 serial）：合并要贯通 plan_resources 的签名，
      列入 pending_fix #1
    · as_evidence 的布尔兼容路径保留一版 → pending_fix #3
    · 单票 _adjudicate_sub_tristate 整段保留作退路 → pending_fix #2

'''


def main() -> int:
    b = RC.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")

    n = s.count("元 DGTF · v1.22.0-rc1\n")
    assert n == 1, f"标题锚点 {n} 次"
    s = s.replace("元 DGTF · v1.22.0-rc1\n", "元 DGTF · v1.22.0\n", 1)
    n = s.count('__version__ = "1.22.0-rc1"')
    assert n == 1, f"__version__ 锚点 {n} 次"
    s = s.replace('__version__ = "1.22.0-rc1"', '__version__ = "1.22.0"', 1)

    anchor = "v1.21.77 ── 两处未完成项收口"
    assert s.count(anchor) == 1, f"changelog 锚点 {s.count(anchor)} 次"
    i = s.index(anchor)
    s = s[:i] + CHANGELOG + s[i:]
    print("  · changelog 六段已插入")

    assert "\\" not in CHANGELOG, "changelog 里出现了反斜杠（违反约束 08）"
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    FINAL.write_bytes(out.encode("utf-8"))
    ast.parse(out.replace("\r\n", "\n"))
    print(f"✓ F.2 完成：{FINAL.name}；行数 {len(out.splitlines())}；ast.parse OK")

    # rc1 与定稿的差异应当**只有**版本号与 changelog
    import difflib
    la = RC.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    lb = out.replace("\r\n", "\n").split("\n")
    blocks = [x for x in difflib.SequenceMatcher(None, la, lb).get_opcodes()
              if x[0] != "equal"]
    print(f"  · rc1 → 定稿：{len(blocks)} 个差异块（期望 3：标题 / 版本号 / changelog）")
    assert len(blocks) == 3, blocks
    return 0


if __name__ == "__main__":
    sys.exit(main())
