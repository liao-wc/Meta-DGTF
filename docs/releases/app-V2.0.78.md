# App 2.0.78 发布说明（2026-10-30）

> 类型：PATCH（App）；引擎同发 V2.2.53（零行为差）。
> 主题：预期 vs 实测（quality_actual）。

## 1. 变更

- 任务 GET（done）附加 quality_actual（answer_quality/answer_ready/verified/packed）；
- 解析顺序：output_name → 自定义 save_dir → log 推导 → outputs 递归按问题+时间匹配；
- 前端 rl-qf 标签追加「实测 xxx」，与预期验证率并列。

## 2. 预算使用

本轮零新增 API 花费。

## 3. 判据与验收

- App selftest 457 项（+1）；fused_full_chain 25 项（+C10）；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；V2 71/71（1208）；
  fast_gate 16/16；e2e 18/18；probe 81/81。

## 4. 兼容性

- 仅新增查询字段；任务执行不变；解析失败 fail-open（source=none）。
