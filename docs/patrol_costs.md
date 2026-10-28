# DSH 巡检成本口径

## 规则

1. ab_bench 打印的 cost=... 是账户余额窗口差，不是单跑成本。
2. 同一时间窗内如有并发真跑、审计、其他 API 调用，窗口差会混入它们的消耗。
3. 因此巡检记录不得直接把窗口差写成“本跑花费”；必须标为：
   - cost_window_cny：账户窗口余额差
   - cost_attribution=not_attributable_concurrent_runs：不可归因
   - tokens/calls：属于该跑自身遥测，可用于相对比较
4. 单跑精确成本需要按请求 usage + 官方单价单独结算；当前未实现，统一标“未知”。
5. 后续 docs/reports/patrol_*.md 必须按此口径写。

## 已修正

- patrol-psych-20261025 记录：3.55 CNY 改为窗口差，不再作为单跑成本。
