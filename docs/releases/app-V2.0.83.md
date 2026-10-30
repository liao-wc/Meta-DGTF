# App 2.0.83 发布说明（2026-10-30）

> 类型：PATCH（动态配置优化）。

## 1. 变更

- `daosheng_mode.py` 的 tier_advice 改为**证据驱动 + kind-aware**：
  - 只有实测 `fast.tokens <= quality.tokens` 才建议 fast；
  - project 相关题使用 project 证据（fast 实测多 18.6% tokens）⇒ 建议 **current**；
  - reasoning/choice 维持 fast 建议（分别省 ~3.6% / ~2.3% tokens）。
- 新增 `_TIER_ADVICE_EVIDENCE` 的 choice/project 条目（真 API A/B 证据）。

## 2. 不改变执行

- 只改 advisory（建议）字段，实际 tier/执行不变；默认行为一致。

## 3. 判据

- `test_dynamic_opt` 134→138 checks，全 PASS；
- App 静态资源查询串 2.0.83-quality-guard。
