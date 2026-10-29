# App 2.0.51 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.26（零行为差）。
> 主题：route 子集感知动态成本模型。

## 1. 变更

- dynamic_config 成本估算改为 层子集 × 圈数 可加模型（3 臂云实测校准）；
- 单层 0/1、两层 0/1、整单四层、B/serial 比例、事实题 web 增量均有校准点；
- 候选成本按自身 route/rounds 估算（显式省层/低圈任务不再被整单口径高估）；
- 可行域保留 ±10% 估算容差；plan.dynamic_opt 标注 cost_model。

## 2. 预算使用

本轮 3 臂校准合计约 ¥0.32（有界 max_tokens=150000/臂）；
证据：docs/dynamic_cost_calibration_20261029.json。

## 3. 判据与验收

- test_dynamic_opt 46 项；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 81/81。

## 4. 兼容性

- 显式 opts 优先；余额未知 fail-open 只审计；quality 档不受影响；
- App 路径额外开销（自省/质量门）尚未纳入模型（下轮 App 路径校准）。
