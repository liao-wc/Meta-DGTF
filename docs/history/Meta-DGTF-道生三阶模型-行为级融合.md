# Meta-DGTF-道生三阶模型 · 行为级融合（V2.2.0）

V2.1.0 把历史版本变成能力谱系与 provenance。
V2.2.0 再进一步：历史能力不只被记录，还会改变当前调度行为。

## 五个行为 arm

| arm | 历史来源 | 行为取向 |
|---|---|---|
| v1_spiral | V1.0-V1.22 | 串行、低强度、探索优先 |
| v1_frontier | V1.23.64-V1.23.66 | 前沿内核、契约优先、高强度 |
| v2_contract | V1.24-V2.0 | V2 接管、四层契约优先 |
| v2_pareto | V1.23.65-V2.0 | 质量-成本帕累托、效率优先 |
| fusion_full | V2.1-V2.2 | 17 条能力轴全开、契约优先 |

每个 arm 都带历史时代、provenance、能力轴、默认 mode/rounds/stop/thinking/effort 与 profile。

## 行为融合流程

1. 引擎启动时先做历史谱系融合。
2. 行为融合按题面特征选择候选 arm。
3. 有历史 outcome 时用 UCB 在候选 arm 中选。
4. 只修改 source=auto 的调度项：mode、rounds、stop 阈值、thinking、effort。
5. 显式 CLI 参数不动。
6. packed 写入 behavior_fusion provenance。
7. 跑完记录 outcome：quality/calls/tokens，不含答案文本。
8. 下一跑用 outcome 参与 UCB。

## 创新点

- 行为级：历史 arm 真正改变 mode/rounds/stop/effort。
- 可回滚：behavior-fusion off 立即关闭；显式参数永远优先。
- 不碰答案：只作用于调度与阈值。
- 能力吸收：fusion_full 显式覆盖 17 条能力轴。
- 在线学习：outcome 只存数值，下一跑 UCB 选择。

## 文件

- dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.0.py（内联，单引擎生产实现）
- dgtf_engine/dgtf_v2/tests_inline_fusion.py（12 项单引擎判据）
- dgtf_memory/behavior_fusion_stats.json（运行数据，不入库）

## 判据

tests_inline_fusion.py 共 12 项：arm 目录、17 轴覆盖、事实/决策/开放题选择、显式参数保护、auto 调度变更、配置元数据、packed audit、outcome 累加、stats 路径、markdown 渲染。结果 12/12 PASS。

## 边界

行为 arm 不是旧版本代码副本，而是一组可执行策略预设。行为融合不调用历史模型、不训练模型、不改写答案。四层真跑需要 API 可用，离线门禁与 0 层真跑不替代四层回答验收。
