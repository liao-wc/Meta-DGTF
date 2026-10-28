# App V2.0.39 发布说明

发布日期：2026-10-28

上一版：App 2.0.38

## 主题

人工确认提案不再自动过期，恢复已确认待执行项。

## 根因

旧 proposal triage 规则：

- pending 超 24h 自动 expired
- confirmed 超 72h 自动 expired

导致用户确认前 8 条人工项已全部过期，无法直接执行。

## 修复

- 移除 pending/confirmed 自动过期。
- 人工项必须显式 reject/superseded 才关闭。
- 恢复 7 条为 confirmed；G5 当前 precheck PASS，关闭为 superseded。

## 验证

- pending=0 / confirmed=7 / G5 superseded
- App 全方位检查
- App 版本一致性
- App selftest
- fast_gate

## 静态缓存

`2.0.39-proposalttl`
