# App V2.0.44 发布说明

发布日期：2026-10-29

上一版：App 2.0.43

## 主题

取消默认硬截断，优化显式圈数被 EML 抬高的墙钟放大。

## 根因

- 超时跑日志显示螺旋上限 1 圈，实际预热 3 圈、9 波。
- EML 在跑前抬高了圈数计划，显式 --rounds 被覆盖。
- 上游放大后再用 1200/1800s 截断，是治标。

## 改动

- 显式 rounds 计划在 EML apply 后压回用户上限。
- DGTF_TASK_TIMEOUT_S 默认 0，不再硬截断。
- DGTF_TASK_STALL_S=600 停滞看门狗保留。
- 显式 timeout_s 仍可覆盖。

## 验证

- App 全方位检查
- App 版本一致性
- App selftest
- fast_gate
- V2 tests

## 静态缓存

`2.0.44-wallopt`
