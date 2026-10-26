# App V2.0.32 发布说明

发布日期：2026-10-26

上一版：App 2.0.31

## 主题

点击 DSH Agent 只切换模式，不自动进入 DSH 对话。

## 主要改动

- 新增 dshViewActive，只有显式发起或打开 DSH 会话后才显示 DSH 视图。
- 点击 DSH Agent 不再自动调用 renderDshView，也不再自动启动视图轮询。
- 进入 DSH 模式停留在当前页面，等待用户发送消息。
- 退出 DSH 模式恢复普通任务视图并停止 DSH 轮询。

## 验证

- node --check app.js PASS
- App 全方位检查 PASS
- App 版本一致性 PASS
- App selftest 444/0
- fast_gate 12/12

## 静态缓存

`2.0.32-dshclick`
