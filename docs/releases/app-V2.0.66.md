# App 2.0.66 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.41（零行为差）。
> 主题：语义缓存命中预判 + verified TTL 放宽 + dashboard 容错。

## 1. 变更

- verified 产物缓存 TTL 6h → 168h（事实稳定）；未验证仍受 max_age_h 新鲜度门；
- cache_prediction 用本地 BGE 8771 对最近 verified 产物做近重复预判（≥0.98）；
- dynamic_config：语义命中按 10% 成本计（cache_kind=semantic），cache_roi 可审计；
- dashboard._to_ts：created_at 兼容字符串，修复 /api/chats ValueError 与 App selftest 断连。

## 2. 预算使用

本轮零新增 API 花费（标定走本地链路 + 已有 verified 产物）。

## 3. 判据与验收

- test_dynamic_opt 109 项（+4）；App selftest 455/0；fused_full_chain 23/23；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；V2 71/71（1208）；
  fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 8771 未运行 ⇒ 语义预判 fail-open（无折扣），真实缓存同样不命中；
- 未验证复用仍受预算等级+新鲜度门；no_cache 强制重跑。
