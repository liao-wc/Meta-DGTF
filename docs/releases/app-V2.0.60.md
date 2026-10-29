# App 2.0.60 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.35（零行为差）。
> 主题：rounds 依赖的省层收益 + reasoning 高圈锚点。

## 1. 变更

- reasoning 高圈 A/B（rounds=2/层，约 ¥0.26）：route0 65,608 vs full 62,317 tokens
  （高圈省层收益≈0，full 略省），两臂均 unverified；
- route_pruning 增加高圈分支：reasoning 总圈数≥5 ⇒ keep_four_layers（证据 rounds2 JSON）；
- 新增 _LONG_RUN_ANCHORS（reasoning 总圈数 5-10）：route0 65,608 / full 62,317，
  动态成本用 cost_source=measured_long_anchor。

## 2. 预算使用

本轮 2 跑 A/B 合计约 ¥0.26。

## 3. 判据与验收

- test_dynamic_opt 87 项（+4）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 默认 route_policy=union（四层）不变；高圈锚点只影响成本估算；
- 省层判定只记录/提示，不改变实际 route。
