# 模式级 Pareto 分析与融合模式 M4

日期：2026-10-24
目的：从引擎所有并行模式中选出最优三种保留，创造融合优点的第四种模式（M4 auto-fused），覆盖不同场景的帕累托最优。

## 一、模式盘点

引擎并行模式：serial、A、B、C、D、E、F、G、H、auto。

| 模式 | 证据 | 结论 |
|---|---|---|
| serial | 历史 152 次真跑；同日 run7：quality 0.990 / 997,457 tokens / wall 1920.6s | 保留（低 tokens 质量档） |
| B | 历史 1 次；同日 run14：quality 1.000 / coverage 1.0 / flags 0 / 1,269,082 tokens / wall 1064.3s | 保留（质量/墙钟双优） |
| A | 历史 3 次（旧版本）；同日 run13：quality 0.220、answer_ready=false、standard_all=false、flags 3 | 不保留（质量门失败，层并行丢跨层对齐） |
| C–H | 无同题实测；设计上为 pipeline / 阶段 DAG 并行 | 暂不纳入保留模式（缺证据） |
| auto | 调度器按题面自动选择 | 作为外层入口保留，底层仍落到 B/serial 等 |

## 二、保留的三种模式

1. M1 质量/墙钟优先：模式 B（动态规划）
   - quality 1.000、coverage 1.0、flags 0、wall 1064.3s、tokens 1,269,082；
   - 适用：质量与墙钟权重优先、成本可放宽。
2. M2 低 tokens 质量档：serial
   - quality 0.990、tokens 997,457、wall 1920.6s；
   - 适用：tokens 预算紧、可接受更长墙钟。
3. M3 时间/成本档：thinking off
   - quality 0.930、tokens 816,983、wall 782.6s；
   - 适用：墙钟 <=900s 或快速草稿。

联网场景保留 web 档（serial + 官方联网，0.909 / 969,376 / 1889.7s）作为约束回退，不占三种模式的常规席位。

## 三、第四种模式：M4 auto-fused

设计：按场景在 B / serial / fast 中自适应选择；需要更高保证时先跑 fast，实测质量低于目标再升级 B（时间换质量）。

场景表（scripts/mode_fusion.py --scenarios）：

| 场景 | 选中 | quality | tokens | wall(s) |
|---|---|---|---|---|
| 质量/墙钟优先 | B | 1.000 | 1,269,082 | 1064.3 |
| 墙钟 <=900s | fast | 0.930 | 816,983 | 782.6 |
| tokens <=1.0M | serial | 0.990 | 997,457 | 1920.6 |
| 必须联网 | web | 0.909 | 969,376 | 1889.7 |
| 最快 | fast | 0.930 | 816,983 | 782.6 |

结论：
- 若允许部署多种模式：保留 B、serial、fast 三种，各覆盖质量/成本/时间场景；
- 若只保留一种最优模式：部署 M4 auto-fused，由它自动落到底层三种模式；
- 若必须静态单模式：选 B（质量/墙钟综合最优，成本可放宽）。

## 四、实现与验证

- 模块：dgtf_engine/dgtf_v2/mode_fusion.py（MODES / select_mode / fused_plan / scenario_table）；
- CLI：scripts/mode_fusion.py（--min-quality / --max-wall / --max-tokens / --require-web / --cascade / --scenarios / --json）；
- 判据：tests_pareto_flow.py 新增 7 项，V2 全量 39/39、529 项检查；
- 联动报告：docs/pareto_joint_report_20261024.md（含模式 B 行）。

## 五、边界

- B 的 quality=1.0 来自单个受控问题；跨题需更多样本。
- C–H 未做同题实测，不能仅凭设计宣称更优。
- M4 的级联依赖“实测质量”判定；强依赖质量预测/二次评估。
- B + 官方联网组合尚未实测（web 模式仍是 serial+web）。

## 六、下一步

1. 若预算允许，补测 C/D/E 中一个代表模式与 B+web 组合，验证是否还能前移前沿；
2. 把 M4 auto-fused 接入 App 的任务启动选项（默认 auto），暴露场景参数；
3. 为 M4 增加质量预测（用历史 packed 训练轻量模型），减少级联触发次数。

## 七、Round 1 新目标进展（模式 E / App / 预测器）

- 模式 E（DAG 双起+串行收元，run 20261024_213016）：quality 0.922、coverage 0.42、flags duty_short/unsaid_overused(4)、
  tokens 993,472、wall 1513.7s；被 fast（0.930/816,983/782.6s）支配，DAG 并行仍损跨层对齐，不保留。
- 模式 A/E 均失败，说明 C/D/E 代表模式（层并行/流水/DAG）当前版本质量不达标；保留 B/serial/fast 不变。
- App 2.0.11：任务启动默认 auto，GET /api/mode-fusion 暴露模式/场景/参数；POST /api/tasks 支持 fused_min_quality、
  fused_max_wall、fused_max_tokens、fused_require_web、fused_prefer；前端新增“模式融合”场景下拉。
- 质量预测器（dgtf_engine/dgtf_v2/quality_predictor.py + 模型 JSON）：历史 142 样本；随机切分 R²=0.916/MAE=0.048，
  时间切分 R²=-0.37（跨版本漂移）。只在预测明确时用于 fast→B 守卫，不替代实测。
- 模式 E（DAG，run 20261024_213016）：quality 0.922、flags duty_short/unsaid_overused(4)、tokens 993,472、wall 1513.7s，被 fast 支配。
- **B+web 组合（run 20261024_215545）**：quality 0.933、search=4/fetch=6、tokens 1,062,012、wall 1073.3s；
  成为联网场景最佳档（优于旧 serial+web 的 0.909/1,889.7s），但被 B 的质量/墙钟支配，仅在必须联网时使用。
- 结论：C/D/E 代表模式（层并行/流水/DAG）当前版本质量不达标，保留 B/serial/fast 不变；web 档更新为 B+web。

- 阶段级 B-no-selfcheck（run 20261024_221714，关 output.actions.self_check）：quality 0.94、flags duty_short、
  tokens 1,029,966、wall 985.1s。相对 B（1.000/1064.3s）质量降 6%、墙钟降 79s、tokens 降 24 万；
  按质量/墙钟优先不采纳（self_check 保留），仅作为“更快折中档”备选记录。

## 八、KV 缓存探针（Round 4）

- B 模式插桩：90 calls，prompt_cache_hit=77,184 / miss=489,340（命中率 13.62%），重复 prompt=0；
- 同一配置 B 变体：0.9592 / 773,603 / 869.7s；B 质量/墙钟存在运行间方差（0.959–1.000，870–1064s）；
- 结论：响应级去重无收益；下一步做静态 system 前缀拆分以提升 KV 命中。

- M4 预测再加“历史区间”约束：模式质量取 [quality_low, quality]（B=0.959–1.000，fast=0.930，serial=0.990），
  校准后裁剪进区间，避免小样本/跨版本预测过度乐观；预测不明确时保持静态选档。

## 九、静态前缀 KV 实验（Round 7）

- 前置约 140 字静态约束：命中率 13.62%→18.46%，但 tokens 1,266,323 / wall 1442.3s、quality 0.9741；
- 结论：新增前缀 token 与运行方差抵消收益，不采纳。
