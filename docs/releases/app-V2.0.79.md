# App 2.0.79 发布说明（2026-10-30）

> 类型：PATCH（App）；引擎同发 V2.2.56（零行为差）。
> 主题：历史卡片「预期 vs 实测」。

## 1. 变更

- /api/chats 每条会话附加 quality_expected 与 quality_actual；
- archive 无 output_name 时按问题匹配 packed（120s 时间窗防串档）；
- 前端历史卡片展示「预期 x% · 实测 y」（只读标签）。

## 2. 预算使用

本轮零新增 API 花费。

## 3. 判据与验收

- App selftest 457/0；node --check app.js 通过；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；V2 71/71（1208）；
  fast_gate 17/17；e2e 18/18；probe 82/82。

## 4. 兼容性

- 仅新增只读字段/标签；任务执行不变；无 packed 时 quality_actual 为空。
