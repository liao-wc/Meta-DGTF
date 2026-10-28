# DSH 巡检报告 · 未来 / 社会领域（forecast 修复后复跑）

时间：2026-10-26T08:02:20+08:00
题目：智能体终端会怎样改变工作？
状态：完整真跑完成，质量门通过

## 检查项

- App 2.0.24 / Engine 2.2.3
- DSH 守护 interval=7200，thread=true
- 采用 fast+web 成本档执行完整流程

## 修复项

- 首跑把“会怎样改变工作”判成 fact，quality=0.4131/needs_evidence；
- V2.2.3 的 _FORECAST_CUES 增加“怎样改变/如何改变/会怎样/会如何”；
- 该题归 reasoning，不再走 fact 证据门；
- tests_question_type 22/0。

## 真跑结果

首跑：
- tag: patrol-future-social-20261026
- quality=0.4131 / needs_evidence
- 窗口差约 1.5 CNY（不可归因）

复跑：
- tag: patrol-future-social-rerun-20261026
- exit=0，wall=298.0s
- tokens=997722，calls=131
- quality=0.98，answer_quality=verified，answer_ready=true
- 窗口差约 1.16 CNY（不可归因）
- packed: outputs/20261026_080206_智能体终端会怎样改变工作.packed.json

## 热门话题 / 技术知识

- hot_topics.json：52 个问题 / 9 个领域
- 新增：智能体工时达到人类6倍
- 技术知识库新增 Training the Whole Agent 观察项
- triage：actionable_without_action=0

## 落地决定

- 本轮落地项：forecast 分类修复（已实现并验证）；
- 未新增高风险代码；报告/guard 门禁保持。

## 验证

- tests_question_type：22/0
- fast_gate / V2 / selftest / triage / guard / 报告门禁：PASS
- precheck：FAIL G4（decidability mixed n=6 bad=2），不记 bad

## 风险

- 成本为窗口差，含并发运行
- 未 push；工作区有未提交变更

## 留存

- docs/reports/patrol_20261026_080206_future_society.md
- docs/patrol_runs.jsonl
- dgtf_memory/patrol_state.json
- dgtf_memory/patrol_history.jsonl
