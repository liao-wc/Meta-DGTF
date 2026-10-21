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

## 边界

- 未做 LLM 权重 fine-tune；训练为 EML 数值/调度统计管线。
- 真实 API A/B 需另行按预算执行。
