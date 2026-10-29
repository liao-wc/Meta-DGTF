# App 2.0.65 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.40（零行为差）。
> 主题：未验证缓存复用的新鲜度门。

## 1. 变更

- plan.cache_policy.max_age_h（warn 24h / critical 72h / ok 0）+ plan.cache_max_age_h 透传；
- _find_cached_pack(max_age_h)：未验证产物超过年龄上限不命中；verified 不受限；
- 响应 cache_age_h；
- 全链路 D5（拒绝）/D6（放行）验证，并在测试结束清理 root 产物。

## 2. 预算使用

本轮零新增 API 花费（全链路用本地链路验证）。

## 3. 判据与验收

- test_dynamic_opt 105 项（+3）；fused_full_chain 23 项（+2）；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；App selftest 455/0；
  V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- verified 复用逻辑不变；未验证复用仅在预算 warn/critical 且新鲜时生效；
- no_cache/force_rerun 仍强制重跑。
