# App 2.0.75 发布说明（2026-10-30）

> 类型：PATCH（App）；引擎同发 V2.2.50（零行为差）。
> 主题：tier_advice 有界 A/B 证据接入建议原因。

## 1. 变更

- reasoning quality vs fast A/B（真 API 约 ¥0.27）：69,359 vs 66,869 tokens，
  124.6s vs 67.4s，均 unverified；
- plan.quality_retry.tier_evidence 指向 docs/tier_advice_ab_20261030.json；
  tier_advice_why 附实测 note；fact（current）不携带。

## 2. 预算使用

本轮 A/B 合计约 ¥0.27。

## 3. 判据与验收

- test_dynamic_opt 129 项（+3）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 456/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 仍为 advisory，不改变实际 tier；证据字段仅审计/展示。
