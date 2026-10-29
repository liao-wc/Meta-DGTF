# App 2.0.74 发布说明（2026-10-30）

> 类型：PATCH（App）；引擎同发 V2.2.49（零行为差）。
> 主题：语义阈值边界标定 + 题型选档建议（advisory）。

## 1. 变更

- 阈值标定（本地 BGE 零 API）：0.98 边界 3 命中/3 不命中；HTTP 变体无误命中；
- plan.quality_retry.tier_advice：verified 0 题型 + 预算 ok → fast（advisory）；
  fact → current；预算已降档 → current；
- quality_forecast 输出 tier_advice（UI 可展示）。

## 2. 预算使用

本轮零新增 API 花费（标定走本地 BGE）。

## 3. 判据与验收

- test_dynamic_opt 126 项（+4）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 456/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- tier_advice 仅建议，不改变实际 tier/route/rounds；旧响应无字段自动不显示。
