# App 2.0.71 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.46（零行为差）。
> 主题：创建前综合预期随响应下发。

## 1. 变更

- 任务创建响应 mode.quality_forecast：kind / expected_verified_pct / evidence /
  budget_forecast / cache_roi / quality_retry；
- 数据来自现有 plan 字段，不改变服务器行为；
- 标准链路 fail-open 时为空 dict。

## 2. 预算使用

本轮零新增 API 花费。

## 3. 判据与验收

- fused_full_chain 24 项（+B6）；test_dynamic_opt 121 项；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；App selftest 455/0；
  V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 仅新增响应字段；引擎/任务执行不变；客户端可忽略。
