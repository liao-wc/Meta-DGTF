# App V2.0.40 发布说明

发布日期：2026-10-28

上一版：App 2.0.39

## 主题

App 任务默认超时收紧，遏制真跑无限长跑。

## 改动

- DGTF_TASK_TIMEOUT_S 默认 3600 → 1200 秒。
- 未显式设置 timeout_s 的任务最长 20 分钟。
- 显式 timeout_s 仍优先；环境变量可覆盖。
- 已验证真跑最大 1125s，不受影响。

## 验证

- App 全方位检查
- App 版本一致性
- App selftest
- fast_gate

## 静态缓存

`2.0.40-timeoutcap`
