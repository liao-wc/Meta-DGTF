# App 2.0.77 发布说明（2026-10-30）

> 类型：PATCH（App）；引擎同发 V2.2.52（零行为差）。
> 主题：前端 rl-qf 标签修复 + tier_advice 提示。

## 1. 变更

- 修复 rl-qf 标签模板拼接 bug（data-qf/title 不再出现源码文本）；
- tier_advice=fast 时在标签内追加「建议 fast」；
- App selftest 前端判据要求 tier_advice 渲染。

## 2. 预算使用

本轮零新增 API 花费。

## 3. 判据与验收

- App selftest 456/0；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 纯前端修复/展示；API/引擎/任务执行不变。
