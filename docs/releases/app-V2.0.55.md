# App 2.0.55 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.30（零行为差）。
> 主题：层子集质量风险标注（3 臂 A/B 证据）。

## 1. 变更

- 当有效 route 缺层且题目属于事实/项目/verified 策略时：
  plan.dynamic_opt.route_quality_risk 记录 {level, missing, evidence, note}；
  项目/verified 为 high，事实等为 info；warnings 同步提示；
- 默认 route_policy=union（四层）不触发；显式省层保留但风险可审计；
- 3 臂 A/B 证据：route0 verified / route0,1 needs_evidence / full verified+ready，
  层子集质量不单调（单题单次），默认四层更稳。

## 2. 预算使用

本轮 3 臂 A/B 合计约 ¥0.42（每臂 max_tokens=150000）。

## 3. 判据与验收

- test_dynamic_opt 69 项（+5）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 默认行为不变（四层）；显式省层仅增加风险标注与 warnings；
- 成本模型/预算上限/阶段路由均沿用前版。
