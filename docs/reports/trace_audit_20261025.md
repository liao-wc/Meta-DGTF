# DSH 巡检痕迹审计 · 2026-10-25

## 审计结论

下列痕迹原先缺失或不完整，已补齐：

| 痕迹 | 原状态 | 当前 |
|---|---|---|
| AI/科技巡检报告 | 只有对话记录，无报告文件 | 已补 docs/reports/patrol_20261025_165943_ai_tech.md |
| 巡检事件历史 | 只有 dsh_guard.json 的 last_result | 已建 dgtf_memory/patrol_history.jsonl，并补 4 条事件 |
| 巡检报告索引 | 无 | 已建 docs/reports/README.md |
| 热门话题抓取历史 | 只有问题/来源/链接 | 已补 query/content/fetched/confidence 字段；历史 34 条 |
| 热门话题抓取正文 | 未保存正文 | 字段已就位；历史条目多为 only-search，后续巡检要求写入 content |
| 技术知识置信度 | high/medium 字符串导致 UI 显示 NaN% | 已归一为 0~1 数值；历史 31 条已迁移 |
| 宇宙领域知识记录 | 通用知识文档缺少分领域记录 | 已补 docs/patrol_knowledge_20261025_universe.md |
| 守护每轮 dispatch 记录 | 无 | 已新增 patrol_history 追加逻辑（下一轮开始自动记录） |
| 报告留存要求 | 无强制 | 已写入 DSH 守护任务：每轮必须生成 docs/reports/patrol_*.md |

## 仍缺 / 待补

1. 旧 34 条热门话题历史大部分只有元数据与链接；已补抓 2 条正文（中国天眼活三体、土星合月），其余后续巡检继续补。
2. 宇宙领域真跑因余额不足未执行，暂无该领域新 packed 产物与真跑报告。
3. 历史更早的巡检（本机制建立前）没有逐轮报告，只能从 packed/ab_results 重建部分证据。
4. 本轮未提交 git，未推送。

## 留存文件

- dgtf_memory/patrol_state.json
- dgtf_memory/patrol_history.jsonl
- docs/patrol_runs.jsonl
- docs/reports/*.md
- dgtf_memory/hot_topics.json
- dgtf_memory/hot_topics_crawl.jsonl
- dgtf_memory/agent_knowledge.jsonl
