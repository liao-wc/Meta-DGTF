# App 2.0.53 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.28（零行为差）。
> 主题：预算层级 → 运行期 token 硬上限 + dual_judge 阶段路由 A/B 校准。

## 1. 变更

- 预算 warn/critical 时：plan.max_tokens = 动态配置估算 tokens × 1.5（最低 20k，千位取整），
  apply_plan 透传到 --max-tokens；显式 opts.max_tokens 优先，ok 档不设限；
- plan.dynamic_opt.budget_cap 记录上限依据（可审计）；
- dual_judge=cache 冷缓存单题 A/B：与 llm 臂 tokens 差 +665（≈+2%），无显著节省；
  保留为缓存热/预算极紧备选，证据 docs/dynamic_dual_judge_ab_20261029.json。

## 2. 预算使用

本轮 2 臂 A/B 合计约 ¥0.12（每臂 max_tokens=150000）。

## 3. 判据与验收

- test_dynamic_opt 60 项（+6）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 显式任务参数优先；ok/quality 档不设 token 上限；项目/quality_first 不降评审。
