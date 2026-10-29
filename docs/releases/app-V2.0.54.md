# App 2.0.54 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.29（零行为差）。
> 主题：预算层级 → 运行期墙钟硬上限 + dual_judge 热缓存验证。

## 1. 变更

- 预算 warn/critical 时：plan.max_minutes = 估算 tokens/600×1.5 折算分钟（最低 1 分钟），
  apply_plan 透传 --max-minutes；显式 opts.max_minutes 优先，ok 档不设限；
- plan.dynamic_opt.budget_cap 同时记录 max_tokens/max_minutes（可审计）；
- dual_judge 热缓存连续两跑验证：run2 比 run1 +588 tokens、calls 相同（单题无显著收益），
  保留 cache 为可选档，证据 docs/dual_judge_warmcache_20261029.json。

## 2. 预算使用

本轮热缓存验证 2 跑合计约 ¥0.14（每跑 max_tokens=150000）。

## 3. 判据与验收

- test_dynamic_opt 64 项（+4）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 显式任务参数优先；ok/quality 档不设时间/ token 上限；项目/quality_first 不降评审。
