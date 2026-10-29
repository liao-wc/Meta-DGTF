# App 2.0.49 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.24（零行为差）。
> 主题：全链路动态配置优化 + 动态依赖调整（route 闭包）。

## 1. 变更

- daosheng plan 新增 route 依赖闭包：both 补 0/1，all 补 both/0/1；单层不强加依赖；
  plan 记录 route_dependency_added，补依赖写 warnings。
- 新增 dynamic_config（daosheng_mode）：余额 × 质量下限 × 成本多目标枚举与选择，
  按 budget_level（ok/degrade/warn/critical）自动降圈；plan 落 dynamic_opt，
  mode_summary 带 budget_level + dynamic 摘要。
- applied 仅覆盖 rounds（显式 opts.rounds 优先）；web=auto 不落 opts（交给引擎自决）。

## 2. 判据与验收

- test_dynamic_opt 28 项（进一键验收 strict）；
- 一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；App selftest 455/0；
  V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 81/81。

## 3. 兼容性

- 显式任务参数优先；余额未知 fail-open；预算只降圈/降档，不砍层；
- 旧引擎能力门控/参数通道不变（V2.2.24 引擎零行为差）。
