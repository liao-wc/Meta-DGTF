# App 2.0.50 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.25（零行为差）。
> 主题：动态配置细化（多圈档多目标 + 缓存命中感知）+ 剩余预算有界 A/B。

## 1. 变更

- dynamic_config：fast 档枚举 fast/economy/critical 三档圈数，按成本约束+质量估算选择；
  质量随圈数线性折扣；fast 档质量下限对齐实测 0.90（项目 quality 档仍 0.95）。
- 缓存命中感知：精确命中按 10% 成本计入可行域，低余额也能选质量更高档；
  动态配置前移缓存预判，复用同一份结果。
- plan.dynamic_opt 增加 route / cache_hit 读数；fail-open（余额未知）只审计不改配置。

## 2. 剩余预算 A/B（真实云端 2 臂）

同题同 route/rounds，仅预算不同：ok 档选 quality B，warn 档选 fast+economy 圈；
两臂均 done 且 answer_quality=verified；实际约 ¥0.15/¥0.13（合计约 ¥0.28）。
证据：docs/dynamic_budget_ab_20261029.json。

## 3. 判据与验收

- test_dynamic_opt 36 项（多圈档/缓存/fail-open/route/变异体）；
- 一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；App selftest 455/0；
  V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 81/81。

## 4. 兼容性

- 显式任务参数优先；余额未知 fail-open；quality 档不受低圈候选影响；
- 成本估算仍整单口径（route 子集感知下一轮）。
