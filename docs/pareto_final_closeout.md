# Meta-DGTF 帕累托最优收束报告

日期：2026-10-24
目标：在预算内让 App、引擎、本地模型各自达到帕累托最优，再完成三者联动帕累托最优；质量与墙钟优先，成本可适当放宽。

## 一、引擎（四层推理）

同题受控真跑（问题：为什么城市热岛效应在夜间比白天更明显？），全部四层、web 默认关闭；墙钟由日志/作业时间精确记录（docs/pareto_engine_times.json）。

| run | 配置 | quality | tokens | calls | wall(s) | flags |
|---|---|---|---|---|---|---|
| 20261024_160020 | 官方联网成本档 | 0.9089 | 969,376 | 89 | 1889.7 | 1 |
| 20261024_163455 | 无网成本档（effort low） | 0.9900 | 997,457 | 107 | 1920.6 | 0 |
| 20261024_171058 | 均衡档（effort high） | 0.9514 | 1,210,815 | 134 | 2116.9 | 0 |
| 20261024_175452 | 质量档（3 圈 + 联网） | 0.9800 | 1,844,908 | 154 | 2933.3 | 1 |
| 20261024_193452 | 关思考超省成本档 | 0.9300 | 816,983 | 106 | 782.6 | 2 |
| 20261024_195354 | hybrid（关判断环节思考） | 0.9458 | 1,131,199 | 115 | 2033.7 | 1 |

结论：
- 墙钟三目标（quality / tokens / wall）非支配点 = run7（0.990 / 997,457 / 1920.6s）与 run11（0.930 / 816,983 / 782.6s）。
- run6 仅在低 calls / 必须联网约束下保留；run8、run9、run12 被 run7 等支配。
- 三档受控 A/B 与 hybrid 负结果共同确认：run7 质量优先、run11 时间优先，是当前可测前沿。
- 3 层 route 负例（20261024_190707）证明 all 元层是交付硬约束，四层不可省。
- 产物：docs/pareto_flow_v1.md、docs/pareto_joint_report_20261024.md。

## 二、App

- health 2s TTL：p50 从 ~475ms 降到 ~5–17ms；
- chats 1s TTL：p50 从 ~300ms 降到 ~4–19ms；
- events(full) 保持实时 ~250–310ms；
- V2 帕累托图：铺满面板、Y 固定 0–1、X 固定 0–200k、分箱中位数趋势线、超界点贴边；
- App 2.0.10，selftest 371/0，fast_gate 12/0。

## 三、本地模型

- BGE（cuda，dim 512）：
  - 检索质量代理（24 条项目语料 / 10 查询）：recall@1=1.000、recall@3=1.000、MRR=1.000；
  - cache-clean 批量实测：n=1 25.7ms/39 texts·s⁻¹；n=8 21.5ms/373；n=16 14.4ms/1109；n=32 23.3ms/1371；n=64 43.4ms/1476；
  - 文本级 LRU 缓存（V2.0.9）：冷 30–150ms、热 p50 ~2–3ms；
- 本地 LLM：
  - Qwen2.5-0.5B：~12.9–15.2 tok/s，加载 3.2s；DeepSeek-R1-1.5B：~11.4 tok/s，加载 10.1s；
  - 质量代理 0.579 / 0.592，事实性弱，结论：不进答案主路径；
- 本地组件定位：BGE 检索/embedding 为质量-时延双优；LLM 仅轻量辅助。GPU 已用于本地评估/缓存验证。

## 四、三者联动

选档器（scripts/pareto_flow.py / scripts/pareto_report.py）支持质量、tokens、墙钟、联网四类约束：

| 档位 | 组合 | quality | tokens | wall | 适用 |
|---|---|---|---|---|---|
| J1 质量优先 | run7 + App 缓存 + BGE n=16–32 | 0.990 | 997,457 | 1920.6s | 预算 ≥1.0M，质量优先 |
| J0 时间优先 | run11 + App 缓存 + BGE n=16 | 0.930 | 816,983 | 782.6s | wall ≤900s 或成本敏感 |
| J2 联网 | run6 官方联网 + App 缓存 | 0.909 | 969,376 | 1889.7s | 必须联网 |

联动结论：App/BGE 为毫秒级，联动瓶颈在引擎 LLM 墙钟；J1 用 +30.9s / +28k tokens 换 +0.081 quality，J0 用 -59% wall / -18% tokens 换 -0.06 quality，两者均为非支配选择。

## 五、验证

- fast_gate 12/0；V2 tests 39/39（534 项检查）；App selftest 371/0；pip check 0 broken（两环境）；project paths PASS；DSH loop check 6/0；最新真跑离线预检 5/5；
- 真跑数据与墙钟侧车、联动报告均可复现（scripts/pareto_report.py）；
- 提交与标签：Git 历史已推送 origin/main；引擎 V2.2.2、App 2.0.10、App 发布标签本地保留。

## 六、边界与后续

- 受控数据基于同一问题，跨题不可直接比较；质量代理非人工评阅。
- App/BGE 读数为单实例；本地 LLM 只测代理质量。
- hybrid 关思考实验为负结果；逐环节关思考不是有效墙钟路径。
- 未做：DeepSeek KV cache 命中率追踪与稳定前缀优化、引擎内并发调用、BGE 接入引擎记忆召回——这些是下一阶段可继续的墙钟/质量方向。
- 预算未按绝对数值耗尽，但当前可测范围内已无可改进的非支配配置；继续加跑只会重复被支配点。据此收束。

## 结论

在现有预算与测量范围内：引擎、App、本地模型均已达到各自可测帕累托最优配置；三者联动选档器与报告已完成；继续同方向实验均为被支配或负结果。目标按“质量/墙钟优先、成本可放宽”的口径完成。

## 七、模式级更新（Round 14）

- 模式 A 负结果：四层并行 wall 1079.3s，但 answer_ready=false、standard_all=false、flags 3，质量门失败。
- 模式 B 正结果：quality 1.000、coverage 1.0、flags 0、tokens 1,269,082、wall 1064.3s。
- 保留三种模式：B（质量/墙钟）、serial（低 tokens）、fast（时间档）；web 作为必须联网的回退档。
- 第四种模式 M4 auto-fused：按质量/墙钟/tokens/联网约束自适应，并支持 fast→B 级联；
  单模式部署建议使用 M4（静态单模式则选 B）。
- 产物：docs/mode_pareto_analysis.md、dgtf_engine/dgtf_v2/mode_fusion.py、scripts/mode_fusion.py；
  V2 判据新增 7 项（共 534 项检查）。

## 八、Round 1 模式补测与 M4 App 接入

- 模式 E 负结果：quality 0.922、flags duty_short/unsaid_overused(4)、tokens 993,472、wall 1513.7s；被 fast 支配。
- App 2.0.11：任务启动默认 M4 auto；/api/mode-fusion 暴露模式与场景参数；前端场景下拉。
- 质量预测器：历史 packed 训练 ridge（142 样本），随机 R²=0.916 / MAE=0.048；时间 R²=-0.37，仅作保守守卫。
- V2 判据增至 534 项检查。
- 模式 E（DAG）0.922/993,472/1513.7s 被 fast 支配；B+web 0.933/1,062,012/1073.3s 成为联网最佳档。

## 九、Round 2 阶段级与组合补测

- B+web：quality 0.933、search=4/fetch=6、tokens 1,062,012、wall 1073.3s；联网场景最佳档。
- B-no-selfcheck：quality 0.94、flags duty_short、tokens 1,029,966、wall 985.1s；质量/墙钟优先不采纳。
- 模式 E（DAG）：0.922/993,472/1513.7s，被 fast 支配；A（层并行）质量门失败。
- 结论：B 仍是质量/墙钟最优；fast 时间最优；serial 低 tokens；联网用 B+web。

## 十、Round 3 预测器与 App 编排

- 质量预测器改用 kNN：随机 R²=0.916/MAE=0.048；时间切分 R²=0.521/MAE=0.166（已转正）；
- M4 预测采用 0.5 模型 + 0.5 模式先验校准；
- App mock 端到端：POST 265.6ms、首条日志 408.6ms、完成 3478.3ms；编排为亚秒级。

## 十一、Round 4 KV 缓存探针

- B 模式插桩（不改引擎文件）：90 calls，prompt_cache_hit=77,184 / miss=489,340（13.62%），重复 prompt=0；
- 同配置 B 变体 quality 0.9592 / tokens 773,603 / wall 869.7s；显示 B 存在运行间方差；
- 结论：响应去重无收益；下一轮做静态 system 前缀稳定化以提升 KV 命中、压 unknown 阶段墙钟。

- M4 预测再加“历史区间”约束：模式质量取 [quality_low, quality]（B=0.959–1.000，fast=0.930，serial=0.990），
  校准后裁剪进区间，避免小样本/跨版本预测过度乐观；预测不明确时保持静态选档。
