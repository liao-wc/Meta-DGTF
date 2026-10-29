# App 2.0.80 发布说明（2026-10-30）

> 类型：PATCH（App）；引擎同发 V2.2.57（零行为差）。
> 主题：归档视图显示实测/预期质量。

## 1. 变更

- 归档视图 archivedTask 携带 quality_expected / quality_actual；
- renderMeta 在无 mode 时追加「预期 x% · 实测 y」只读标签；
- 与历史列表卡片标签同源（list_chats，120s 时间窗）。

## 2. 预算使用

本轮零新增 API 花费。

## 3. 判据与验收

- App selftest 457/0；node --check app.js 通过；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；V2 71/71（1208）；
  fast_gate 17/17；e2e 18/18；probe 82/82。

## 4. 兼容性

- 仅只读展示；任务执行不变；无实测时保持原样。
