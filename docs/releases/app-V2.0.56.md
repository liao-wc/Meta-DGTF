# App 2.0.56 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.31（零行为差）。
> 主题：省层收益判定（6 跑多样本 A/B）。

## 1. 变更

- 6 跑 A/B（route0/0,1/full ×2）：tokens 61-67k 无显著差异，verified/ready 方差主导；
- plan.dynamic_opt.route_pruning = {advice, saved_tokens_estimate, saved_pct_estimate,
  evidence, note}；短程事实 keep_four_layers，长程高圈可 subset_may_save（仍需质量证据）；
- route_quality_risk.evidence 更新为多样本 JSON（保留单题证据为 evidence_prev）；
- 判定只记录/提示，不改变实际 route。

## 2. 预算使用

本轮 6 跑合计约 ¥0.77（每跑 max_tokens=150000）。

## 3. 判据与验收

- test_dynamic_opt 73 项（+4）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 默认 route_policy=union（四层）不变；省层判定不改变实际 route；
- 成本模型/预算上限/阶段路由沿用前版。
