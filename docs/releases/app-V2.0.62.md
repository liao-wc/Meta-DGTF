# App 2.0.62 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.37（零行为差）。
> 主题：quality-retry 决策显式化 + 上下文预算分解 + 缓存 ROI。

## 1. 变更

- plan.quality_retry（advisory）：项目/verified 不建议关闭；事实题+预算 ok 建议 web-retry；
  预算 warn/critical 建议 stable；其它 stable；
- budget_cap 拆 context_tokens / base_tokens（项目题 5,662 context）；
- dynamic_opt.cache_roi：exact/semantic_capable/expected_saving_pct/note。

## 2. 预算使用

本轮零新增 API 花费（余额约 ¥1.46，保留给下一轮预算驱动 retry 的云验证）。

## 3. 判据与验收

- test_dynamic_opt 95 项（+5）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- advisory 字段不改变 server 实际重试行为；默认四层/预算上限/成本模型沿用前版。
