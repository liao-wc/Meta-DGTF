# APP V1.5.20 发布说明

## 主题

Pareto policy 任务级执行。

## 改动

- 真实任务默认 auto_policy=true：读取自动策略圈数，扩展为四层相同圈数预算，不砍 route。
- 支持显式 auto_policy=false、route/rounds 覆盖。
- 响应新增 auto_policy / auto_policy_rounds。
- 版本/静态资源 1.5.20。

## 验证

- fast_gate 12/0；selftest 371/0；依赖审计 78/0。
- mock 任务实测：auto_policy_rounds=0:2,1:2,both:2,all:2，cmd 带 --rounds。
