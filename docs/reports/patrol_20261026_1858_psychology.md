# DSH 巡检报告 · 心理领域

时间：2026-10-26T18:58:00+08:00
题目：缓解社交焦虑，AI效果接近人类治疗师，这说明什么？
状态：完整真跑完成，answer_quality=needs_evidence，answer_ready=false

## 检查项

- App 2.0.33 / Engine 2.2.3
- App 全方位检查（含 UI 自动化回归）
- 全产物库审计
- 提案复评与新增
- 技术知识 triage
- 热门话题九领域更新
- 依赖/门禁与工作区变更

## 修复项

- 本轮无 App 代码修改
- 热点库更新至 69 条
- 提案 audit 标题按最新指标复评
- 未自动关闭高风险提案

## 真跑结果

- tag: patrol-psych-20261026
- run_id: 20261026_184903_b721f5
- exit=0，wall=351.2s
- tokens=758256，calls=92
- coverage=0.9579，answer_quality=needs_evidence，answer_ready=false
- flags: probe_no_target_covered
- packed: outputs/20261026_185454_缓解社交焦虑AI效果接近人类治疗师这.packed.json
- 成本窗口：不可读（start_balance=¥91.51；不做单跑归因）

## App / 产物库

- App 检查 PASS；版本一致性 PASS；UI 自动化 PASS
- packed 354 / md 839 / verified 144
- needs_evidence=30，unverified=50，answer_ready_false=81，missing_quality=36
- 配对/重复/异常 run 仍需人工确认

## 技术知识

- triage 48 条：actionable=5，already_applied=8
- actionability 均已有提案，未重复新增
- 本轮热点库 69 条，九领域覆盖

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

- 本轮真跑 needs_evidence，覆盖 0.9579，probe_no_target_covered
- 产物质量/配对/重复题仍需人工确认
- 异常 run 仍需人工确认
- 成本窗口不可读
- _audit_tmp 约 108MB，未删除
- 未执行 git push
