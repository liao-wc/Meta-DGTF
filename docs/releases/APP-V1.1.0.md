# 元DGTF app V1.1.0 发布说明

日期：2026-10-21
类型：小版本（minor）升级
引擎：元DGTF-V1.30.0.py（引擎版本不变）

## 新增

- EML + DSH 全流程闭环：知识刷新 → 引擎跑次 → 消费者/任务 → 自审提案。
- 技术知识刷新：DeepSeek Search 优先，arXiv API 兜底；入库去重。
- 训练数据管线：EML 纯数值训练集导出（647 条 / 202 runs / 29 模板）。
- V2 模板质量-成本帕累托、UCB、上下文 UCB 与策略持久化。
- 自洽审计与历史记录。

## 可靠性

- 后台 auto/autofix job 持久化与刷新恢复轮询。
- 关键写盘前备份：V2 回放、V2 重建、策略。
- 网络中断重试与优雅降级。

## 验证

- fast_gate 12/0
- app selftest 371/0
- smoke 22/0
- verify 319/0
- audit 70/0
- 集成探针 64/0

## 全流程闭环

- 知识刷新（DeepSeek Search 优先，arXiv 兜底）→ 引擎跑次（默认 mock）→ 消费者/任务 → 提案。
- UI/API：Agent 面板“全流程闭环”，POST /api/agent/auto/start {stage:"full"}。

## 本地调度模型

- train_scheduler_model.py 使用 EML/V2 + packed 上下文训练岭回归。
- 权重：models/scheduler_model_v1.json。
- 留出：quality MAE 0.112 / 基线 0.180，R² 0.293；token 模型 R² 为负，不采用。
- 应用：GET /api/schedule/model/predict、POST /apply、UI“采用学习模型”。

## 针对性真跑

- 2026-10-21：60 calls / 341K tokens / 758.9s / 四层 route 但预算在 1 层截断。
- 产物：outputs/20261021_125449_EML事件记忆如何提升元DGTF多模调.md。
- 本次成本约 ¥0.76；前一次被打断约 ¥1.02。

## 边界

- 未做 LLM 权重 fine-tune；训练为 EML 数值/调度统计管线。
- 真实 API A/B 需另行按预算执行。
