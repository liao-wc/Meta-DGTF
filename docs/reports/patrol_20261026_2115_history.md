# DSH 巡检报告 · 历史领域

时间：2026-10-26T21:15:00+08:00
题目：河南挖红薯窖挖出的大遗址意味着什么？
状态：本轮新真跑超时取消，复用上一轮 verified 历史真跑作为领域证据

## 检查项

- App 2.0.33 / Engine 2.2.3
- App 全方位检查（含 UI 自动化）
- 全产物库审计
- 提案复评与新增
- 技术知识 triage
- 热门话题九领域更新
- 依赖/门禁与工作区变更

## 修复项

- 本轮无 App 代码修改
- 热点库更新至 70 条
- audit 提案指标复核
- 未自动关闭高风险提案

## 真跑结果

- 本轮新跑：20261026_204803_d3fa5b，题目“河南挖红薯窖挖出的大遗址意味着什么？”
- 新跑状态：超过 24 分钟未完成，已取消；不记为 verified
- 复用历史领域上一轮 verified 结果：
  - tag: patrol-history-rerun-20261025
  - question: 中字形西汉大墓的墓主是谁？
  - quality: 0.9495 / verified
  - tokens: 1013050 / calls: 99 / wall: 1125.8s
  - packed: outputs/20261025_235138_中字形西汉大墓的墓主是谁.packed.json
  - 原报告: docs/reports/patrol_20261025_235138_history_rerun.md
- 成本：复用旧跑窗口 ¥3.55，不可归因本轮

## App / 产物库

- App 检查 PASS；版本一致性 PASS；UI 自动化 PASS
- packed 354 / md 839 / verified 144
- needs_evidence=30，unverified=50，answer_ready_false=81，missing_quality=36
- 配对/重复/异常 run 仍需人工确认

## 技术知识

- triage 48 条：actionable=5，already_applied=8
- 5 条 actionable 均已有提案
- 热点库 70 条

## 验证

- app_full_check PASS
- app_version_check PASS
- dependency audit RESULT PASS
- fast_gate PASS 12/0
- V2 tests PASS 51/51，836 checks
- App selftest PASS 444/0
- guard_policy_check PASS
- UI 自动化 PASS

## 风险

- 本轮历史真跑超时取消：新任务未形成 verified 产物，当前领域证据为复用旧跑
- 产物质量/配对/重复题仍需人工确认
- 异常 run 仍需人工确认
- _audit_tmp 约 108MB，未删除
- 未执行 git push
