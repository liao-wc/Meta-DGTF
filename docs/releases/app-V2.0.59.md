# App 2.0.59 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.34（零行为差）。
> 主题：choice 题型省层收益 + 锚点/风险证据。

## 1. 变更

- choice 4 跑 A/B：route0 50.6-50.9k vs full 85.3k（省约 40%），两臂均 needs_evidence；
- kind-aware 表补 choice（saved_pct=0.40，n=4）；短程锚点补 choice
  （full 85,342 / route0 50,752）；
- route_quality_risk.evidence 按题型指向对应证据文件；
- 短程事实分支限定 kind=fact（修复 choice 被事实分支覆盖的问题）。

## 2. 预算使用

本轮 4 跑 A/B 合计约 ¥0.55。

## 3. 判据与验收

- test_dynamic_opt 83 项（+3）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 默认 route_policy=union（四层）不变；判定只记录/提示，不改变实际 route。
