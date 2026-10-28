# App V2.0.41 发布说明

发布日期：2026-10-28

上一版：App 2.0.40

## 主题

任务停滞看门狗，配合 20 分钟总超时治理真跑卡死。

## 改动

- 新增 DGTF_TASK_STALL_S，默认 600 秒。
- 任务日志超过阈值无增长，判定停滞并自动终止。
- 记录 stalled/timeout/error，便于审计。
- 保留 DGTF_TASK_TIMEOUT_S=1200 总超时。

## 验证

- App 全方位检查
- App 版本一致性
- App selftest
- fast_gate

## 静态缓存

`2.0.41-stallwatch`
