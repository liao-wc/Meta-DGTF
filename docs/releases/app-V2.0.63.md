# App 2.0.63 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.38（零行为差）。
> 主题：余额续航预测 + 续航不足自动降级。

## 1. 变更

- dynamic_opt.budget_forecast：balance/est_cost/balance_after/safe_runs/reserve_runs/advice；
- budget.reserve_runs 默认 2；quality 档在 safe_runs < reserve_runs 时自动降 fast；
- 余额未知 fail-open（forecast=None，不降级）。

## 2. 预算使用

本轮零新增 API 花费（余额约 ¥1.46 保留给下一轮语义缓存/retry 验证）。

## 3. 判据与验收

- test_dynamic_opt 99 项（+4）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 默认 reserve_runs=2 对正常余额几乎不改变行为（续航充足不降级）；
- 余额未知 fail-open；成本/上限/省层判定沿用前版。
