# App V2.0.16 发布说明（补丁）

日期：2026-10-25
类型：PATCH（App；引擎 V2.2.2 不变）

## 新机制：事实题联网 + 失败自动重试（web-retry）

- quality_policy 新增 web-retry：
  - 首次任务按 web 接地（通用事实题 web=on）；
  - 任务完成后若 answer_quality 为 unverified/needs_evidence，自动补跑一次同题 web 任务；
  - 首个任务记录 retry_task_id / quality_retry，响应 quality_retry=true；
- 默认仍不启用，只在用户显式选择 web-retry 时生效；
- 适用于官方源抓取有波动的场景（实测首次失败样本 quality 0.49，需要在第二次重试争取 verified）。

## 验证

- py_compile 0；
- 策略 cmd：web-retry 落 --web on / --behavior-fusion off / --rounds 0:1...；
- 创建后立即取消，watcher 不触发补跑；
- 策略 cmd 已验证：web-retry → --web on / --behavior-fusion off / --rounds 0:1...；
- 创建后立即取消：watcher 不触发补跑，任务正常取消；
- 成功/失败重试路径需在真实失败样本上继续追踪（代码已就绪）。
