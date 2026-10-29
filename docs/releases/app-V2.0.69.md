# App 2.0.69 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.44（零行为差）。
> 主题：题型 verified 期望矩阵。

## 1. 变更

- choice 加圈 A/B（真 API 约 ¥0.31）：rounds1/rounds2 均 needs_evidence
  （86,858/67,540 tokens），加圈未提升质量；
- _QUALITY_EXPECTATION 汇总 fact/reasoning/choice/project 真跑证据；
- plan.quality_retry 输出 expected_verified_pct/evidence；plan.quality_expectation 输出矩阵。

## 2. 预算使用

本轮 A/B 合计约 ¥0.31。

## 3. 判据与验收

- test_dynamic_opt 118 项（+4）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 仅新增可审计字段，不改变 server/引擎行为；默认四层/省层判定不变。
