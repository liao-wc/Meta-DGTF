# App 2.0.81 发布说明（2026-10-30）

> 类型：PATCH（App）；引擎同发 V2.2.63（零行为差）。
> 主题：历史/归档 quality 联动护栏。

## 1. 变更

- selftest 457 → 459：list_chats 每行带 quality_expected/quality_actual；
  archivedTask 携带 quality_expected/quality_actual；
- 无历史数据时不误判（仅在行存在时断言值）。

## 2. 预算使用

本轮零新增 API 花费。

## 3. 判据与验收

- App selftest 459/0；fast_gate 18/18；V2 71/71（1208）；
  一键验收 PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；probe 82/82。
