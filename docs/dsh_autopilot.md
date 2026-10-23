# DSH Agent Autopilot 设计

## 一句话
DSH Agent 面板的「常驻守护」开关：开启后由 app 管理队列守护与安全自动修复；关闭后手动点「自动修复提案」只修可自动判断的项，其余留人工。

## 开关
- 开关状态持久化：`dgtf_memory/agent_autopilot.json`。
- 开：启动 `agent_daemon.py`（队列消费/提案）+ Autopilot 线程。
- 关：停止线程，写停止文件让队列守护退出；不再自动修复。
- 默认关闭，避免空转和持续 API 消耗。

## 风险分流
`triage.category/priority` + 提案计划质量：
- 自动修复：`agent_runtime / docs / verification / process_gap / quality_signal`，且计划包含文件/验证关键词，非 P0。
- 人工确认：`fact_correctness / input_sanity / probe_quality / eml_experiment / noise / other`、P0、计划过短。
- confirmed 视为人工已确认，可由 Autopilot 自动修复。

## 自动修复闭环
1. 扫描 pending：安全项自动 confirmed；不确定项保留。
2. 对 confirmed：DSH Agent 修复 → `fast_gate.py` → 针对性验收 → **只有验收通过才提交**；失败则把失败输出回灌同一会话继续修（最多 3 轮），仍不过不提交。
3. 自动检索技术知识，作为修复提示的学习材料（仅常驻开启时）。
4. 每次 DSH 调用有 `dshrun-*` 会话，提案记录 `conversation_id`，可追溯。
5. 自动修复串行执行，避免 git 冲突；DSH 会话可并发。

## 常驻期能力
- 每 6 小时：技术知识刷新、项目自主审视提案。
- 队列出现未提案任务：每 6 小时最多自发一条 DSH 提案。
- 所有提案进入自动分诊库（分类/优先级/项目指纹/历史）。
