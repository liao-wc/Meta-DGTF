# App V2.0.33 发布说明

发布日期：2026-10-26

上一版：App 2.0.32

## 主题

UI 自动化回归接入，修复热点接口 404。

## 主要改动

- 新增 Edge + Selenium headless UI 回归。
- 覆盖北斗七星、Agent 就绪灯、DSH 历史按钮移除、DSH Agent 点击不自动进对话、模式退出、控制台错误。
- 首次运行发现并修复 /api/dsh/hot-topics 404。
- App 全方位检查接入 UI 自动化回归。

## 验证

- UI 自动化回归 PASS
- App 全方位检查 PASS
- App 版本一致性 PASS
- App selftest 444/0
- fast_gate 12/12

## 静态缓存

`2.0.33-uismoke`
