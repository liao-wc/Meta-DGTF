# App 2.0.58 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.33（零行为差）。
> 主题：短程实测成本锚点（修正短跑成本估算）。

## 1. 变更

- 新增 _SHORT_RUN_ANCHORS（B 模式，总圈数 <=4）：fact 四层 65,427 / route0 65,360 /
  route0,1 60,962；reasoning 四层 72,799 / route0 42,798；
- dynamic_config 短跑用实测锚点（cost_source=measured_short_anchor），不重复乘 App 开销；
- 显式 opts.rounds 时只评估该圈数档；长跑仍用可加模型 + App 开销；
- 修正短跑成本 10 倍高估，预算可行域/上限更贴近真实账单。

## 2. 预算使用

本轮为已有 A/B 证据的复用（无新增 API 花费）；余额留待下轮多样本验证。

## 3. 判据与验收

- test_dynamic_opt 80 项（+5）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 默认 route_policy=union（四层）不变；锚点只影响成本估算/可行域；
- 显式 opts 优先；长跑估算沿用可加模型。
