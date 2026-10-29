# App 2.0.61 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.36（零行为差）。
> 主题：项目背景注入成本计入动态配置。

## 1. 变更

- 项目题 RAG+EML 注入实测 +5,662 tokens（约 ¥0.011，A/B 2 跑约 ¥0.18）；
- _CONTEXT_COST 表 + dynamic_config 候选 context_tokens；dynamic_opt.context_cost 可审计；
- build_plan 在项目题且未显式 project_context=false 时计入上下文成本；
- 显式关闭上下文时不计成本（基础锚点 42,798）。

## 2. 预算使用

本轮 2 跑 A/B 合计约 ¥0.18。

## 3. 判据与验收

- test_dynamic_opt 90 项（+3）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 显式 project_context=false 仍可关闭；默认四层/省层判定不变；
- 仅成本估算变化，不改变实际注入决策。
