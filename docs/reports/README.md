# DSH 巡检报告索引

本目录保留每轮巡检报告；原始数据在：

- dgtf_memory/patrol_state.json（当前轮换/最后结果）
- dgtf_memory/patrol_history.jsonl（巡检事件历史）
- docs/patrol_runs.jsonl（真跑记录）
- dgtf_memory/hot_topics.json（当前热门话题）
- dgtf_memory/hot_topics_crawl.jsonl（热门话题检索/抓取历史及链接）
- dgtf_memory/agent_knowledge.jsonl（技术知识库，含置信度/适用性/落地动作）
- docs/patrol_knowledge_YYYYMMDD*.md（技术知识巡检笔记）
- docs/patrol_costs.md（成本口径）

成本口径：真跑记录里的 cost_window_cny 是账户窗口差，可能含并发运行，
不是单跑成本；单跑成本未知，tokens/calls 才属于单跑遥测。

## 报告

- patrol_20261025_165943_ai_tech.md — AI/科技真跑、预测题误判修复
- patrol_20261025_171901_universe.md — 宇宙，余额不足跳过
- patrol_20261025_172406_universe.md — 宇宙，余额不足跳过；热点/知识库修复
- patrol_20261025_183900_universe.md — 宇宙完整真跑，解释型题误判修复
- patrol_20261025_201440_life_health.md — 生命/健康完整真跑，verified
- patrol_20261025_213606_psychology.md — 心理完整真跑，verified
- patrol_20261025_230757_history.md — 历史完整真跑，unverified（题目无指代）
- patrol_20261025_235138_history_rerun.md — 历史换题复跑，verified
- patrol_20261026_020417_environment.md — 环境完整真跑，verified
- patrol_20261026_033229_philosophy.md — 哲学完整真跑，verified
- patrol_20261026_045200_future_society_skip.md — 未来/社会，余额不足跳过
- patrol_20261026_062100_future_society_skip.md — 未来/社会，余额不足跳过
- patrol_20261026_080206_future_society.md — 未来/社会复跑 verified
- patrol_20261026_100307_ai_tech.md — AI/科技 fast+web 复跑 verified
- trace_audit_20261025.md — 痕迹留存审计
