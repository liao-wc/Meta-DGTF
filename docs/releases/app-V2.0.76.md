# App 2.0.76 发布说明（2026-10-30）

> 类型：PATCH（App）；引擎同发 V2.2.51（零行为差）。
> 主题：opt-in「verified 0 题型优先成本」降档。

## 1. 变更

- configs/道生专属模式.yaml + 内置预算：prefer_cost_when_unverified（默认 false）；
- 开启后 reasoning/choice/project（verified 0）在预算 ok 时自动降 fast；
  fact（verified 2/2）不降；
- plan.prefer_cost_when_unverified / tier_downgraded_by 可审计；默认行为不变。

## 2. 预算使用

本轮零新增 API 花费。

## 3. 判据与验收

- test_dynamic_opt 132 项（+3）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 456/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 默认关：不改变既有 tier；显式开启才降档；fact 永不因此降档。
