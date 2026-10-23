# APP V1.5.17 发布说明

## 主题

本地调度模型进入自动帕累托候选，答案显示门接入。

## 改动

- 自动帕累托候选新增 `local_model`（岭回归本地调度模型），可被自动策略选中。
- 引擎 v1.30.4：事实答案仅在 verified 时展示；needs_evidence 显示降级说明。
- 真实跑验证：20261022_183329 输出 answer_quality=needs_evidence、answer_ready=false。
- 版本/静态资源 1.5.17。

## 验证

- 待跑 fast_gate/selftest/审计。
