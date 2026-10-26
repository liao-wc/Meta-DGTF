# App V2.0.30 发布说明

发布日期：2026-10-26

上一版：App 2.0.29

## 主题

移除 DSH 视图内的“历史对话”按钮与浮层。

## 主要改动

- 删除 DSH 会话视图头部“历史对话”按钮。
- 删除 DSH 历史浮层、关闭按钮和 dsh_history 查询入口。
- 侧边栏“历史对话”库保留，历史数据未删除。

## 验证

- node --check app.js PASS
- App 全方位检查 PASS
- App 版本一致性 PASS
- App selftest 444/0
- fast_gate 12/12

## 静态缓存

`2.0.30-nohist`
