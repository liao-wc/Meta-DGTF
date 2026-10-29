# App 2.0.64 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.39（零行为差）。
> 主题：预算紧张时复用未验证产物（省整单）。

## 1. 变更

- plan.allow_unverified_cache（预算 warn/critical）+ dynamic_opt.cache_policy；
- _find_cached_pack 支持 allow_unverified：同题精确匹配复用 unverified 产物；
  语义回退仍只 verified；响应 cache_unverified；
- apply_plan 透传；no_cache/force_rerun 仍强制重跑。

## 2. 预算使用

本轮零新增 API 花费（全链路用本地链路验证缓存复用）。

## 3. 判据与验收

- test_dynamic_opt 102 项（+3）；fused_full_chain 21 项（+5：D0–D4 缓存复用全链路）；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；App selftest 455/0；
  V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 只在预算 warn/critical 时启用；预算充足仍只复用 verified；
- 显式 no_cache/force_rerun 强制重跑；质量门/产物格式不变。
