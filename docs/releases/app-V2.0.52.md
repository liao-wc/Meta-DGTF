# App 2.0.52 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.27（含 route 依赖闭包实际变更）。
> 主题：App 全流程开销校准 + 有效 route 成本 + 阶段动态路由。

## 1. 变更

- App 路径开销系数 1.10（1 臂有界云实测 34,727/31,620=1.098）计入动态成本估算；
- 成本估算改用"有效 route"（显式 opts.route 优先），省层任务不再被高估；
- 阶段动态路由：warn/critical 非项目/非 quality_first 时 dual_judge=cache，
  plan.dynamic_opt.applied/stage_routing 可审计；ok 档/项目题保持原评审档。

## 2. 预算使用

本轮 1 臂 App 路径校准约 ¥0.07（max_tokens=150000）；
证据：docs/app_path_cost_calibration_20261029.json。

## 3. 判据与验收

- test_dynamic_opt 54 项（+8）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 81/81。

## 4. 兼容性

- 显式任务参数优先；余额未知 fail-open；项目题/quality_first 不降评审；
- 引擎 V2.2.27 route 依赖闭包只补缺，不改既有四层 intent。
