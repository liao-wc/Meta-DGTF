# APP V1.5.24 发布说明

## 主题

verified 答案不再被软读数压成 D。

## 改动

- answer_quality=verified 且 answer_ready/process_ready 均为 true 时，质量分下限 85、grade=A。
- 保留 depth/过程层/证据字段；软 flags 仍返回，但不覆盖对外质量结论。
- 版本/静态资源 1.5.24。

## 验证

- fast_gate 12/0；selftest 371/0；依赖审计 78/0。
- 正向真跑 len：answer_ready=true / process_ready=4/4 / answer_quality=verified / score=85 A。
