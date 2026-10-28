# DSH 巡检报告 · 心理领域

时间：2026-10-25T21:36:22+08:00
题目：为什么越刷手机越焦虑？
状态：完整真跑完成，质量门通过

## 真跑

- tag: patrol-psych-20261025
- exit=0，wall=914.9s
- 账户窗口余额差=3.55 CNY（含并发运行，不可归因单跑）
- 单跑可归因成本：未知；tokens/calls 为单跑遥测
- tokens=1111603，calls=123
- quality=0.9548，answer_quality=verified，answer_ready=true
- packed: outputs/20261025_213606_为什么越刷手机越焦虑.packed.json

## 热门话题

- hot_topics.json：40 个问题 / 9 个领域
- 新增心理：沉迷短剧焦虑、全国心理卫生学术大会
- 抓取历史：40 条

## 技术知识

- 新增 Guardrails as Scapegoats、RAIL Guard 两条论文记录
- 技术知识库 dgtf_memory/agent_knowledge.jsonl 约 35 条

## 修复

- 状态信息加载慢：/api/config 产物统计 5s 缓存、/api/health 30s 缓存、启动预热；
- 实测 config 1405ms→59ms，health 645ms→45ms。

## 风险

- 未 push；工作区有未提交变更
- 成本口径：3.55 CNY 只是账户窗口差，包含并发真跑/其他调用，不能当作本跑成本

## 留存

- docs/reports/patrol_20261025_213606_psychology.md
- docs/patrol_runs.jsonl
- dgtf_memory/patrol_state.json
- dgtf_memory/patrol_history.jsonl
