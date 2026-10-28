# DSH 巡检报告 · 生命 / 健康领域

时间：2026-10-26T17:05:00+08:00
题目：部分血液蛋白水平与前列腺癌风险相关，这项研究说明了什么？
状态：完整真跑完成，质量 verified，answer_ready=true

## 检查项

- App 2.0.26 → 2.0.31 版本同步与发布检查
- App 全方位检查
- 全产物库审计
- 提案复评与新增
- 技术知识 triage
- 热门话题九领域更新
- 依赖/门禁与工作区变更

## 修复项

- 修正普通模式 / DSH 模式视图串台（App 2.0.31）
- 移除 DSH 视图历史对话按钮（App 2.0.30）
- 产物活动灯改为真实落盘触发（App 2.0.29）
- 提案复评标题同步实时指标
- 本轮未自动关闭高风险提案

## 真跑结果

- tag: patrol-life-20261026
- run_id: 20261026_165546_0da7c3
- exit=0，wall=553.0s
- tokens=761106，calls=108
- coverage=0.8475，answer_quality=verified，answer_ready=true
- flags: duty_short
- packed: outputs/20261026_170458_部分血液蛋白水平与前列腺癌风险相关，这项.packed.json
- 成本窗口：不可读（启动余额 ¥3.52；未做单跑归因）

## App / 产物库

- App 检查 PASS；版本一致性 PASS
- 当前产物审计：packed 350 / md 835 / verified 144
- needs_evidence=29，unverified=50，answer_ready_false=80，missing_quality=36
- md 无 packed=486，packed 无 md=1，重复题目=64，error run=4，interrupted=5

## 技术知识

- triage 48 条：actionable=5，already_applied=8
- 5 条 actionable 均已有提案，未重复新增
- 本轮热点库更新至 68 条，九领域均有覆盖

## 验证

- app_full_check PASS
- app_version_check PASS
- dependency audit RESULT PASS
- fast_gate PASS 12/0
- V2 tests PASS 51/51，835 checks
- App selftest PASS 444/0
- guard_policy_check PASS

## 风险

- 产物质量/配对/重复题仍需人工确认
- 异常 run：error=4，interrupted=5
- 真跑成本窗口不可读，仅记录启动余额 ¥3.52
- _audit_tmp 约 108MB，未删除
- 未执行 git push
