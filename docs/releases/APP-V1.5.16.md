# APP V1.5.16 发布说明

## 主题

全自动帕累托调度后台。

## 改动

- 新增 schedule-auto 后台线程，启动后自动评估 V2 候选并写入最优策略。
- 新增 GET/POST /api/schedule/auto 状态/开关接口；默认 enabled=true、interval=3600s。
- 启动实测：8s 内自动执行，last_strategy=bandit，无错误。
- 版本/静态资源 1.5.16。

## 验证

- API 状态正常；fast_gate 12/0；selftest 371/0；依赖审计 78/0。
- 实跑：startup auto 8s 内写入策略，last_strategy=bandit。
