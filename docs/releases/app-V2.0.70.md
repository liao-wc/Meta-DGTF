# App 2.0.70 发布说明（2026-10-29）

> 类型：PATCH（App）；引擎同发 V2.2.45（零行为差）。
> 主题：语义候选索引持久化 + 启动预热。

## 1. 变更

- 候选索引落盘 dgtf_memory/semantic_cache_index.json（300s 内跨进程复用）；
- 进程内缓存失效优先读磁盘（0.01s 恢复 120 条候选）；
- 启动后台 warm_semantic_cache（构建索引 + 批量 embedding，等 8771 最多 12s）。

## 2. 预算使用

本轮零新增 API 花费。

## 3. 判据与验收

- test_dynamic_opt 121 项（+3）；一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；
  App selftest 455/0；V2 71/71（1208）；fast_gate 16/16；e2e 18/18；probe 82/82。

## 4. 兼容性

- 8771 不在时预热 ok=False，不影响任务；索引文件缺失/损坏自动回退扫描。
