# App 2.0.68 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.43（零行为差）。
> 主题：fact+web on 质量证据 + fact 高圈锚点。

## 1. 变更

- 质量重试 A/B（真 API 约 ¥0.31）：fact+web on rounds1/rounds2 均 verified
  （85,362/67,753 tokens）；加圈未提升质量且 rounds2 更省；
- plan.quality_retry 增加 expected_verified_pct/evidence/evidence_note（advisory）；
- fact 高圈 full 锚点 67,753（总圈数 5-10）接入动态成本。

## 2. 预算使用

本轮 A/B 合计约 ¥0.31。

## 3. 判据与验收

- test_dynamic_opt 114 项（+3）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- quality_retry 仍为 advisory；fact+web on 质量证据只用于决策说明；
- 高圈锚点只影响成本估算；默认四层不变。
