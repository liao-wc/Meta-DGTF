# Meta-DGTF 深度优化分析报告（2026-10-24）

目标：对实测数据取长补短，在设计/算法/每环节上继续优化；质量与墙钟优先、成本可放宽；按顶配标准逼近帕累托最优。

## 一、实测数据总览

同题受控真跑（问题：为什么城市热岛效应在夜间比白天更明显？），四层、web 默认关闭，墙钟由作业起止精确记录。

| run | 模式/配置 | quality | tokens | calls | wall(s) | flags |
|---|---|---|---|---|---|---|
| 20261024_205018 | B 动态规划 | **1.000** | 1,269,082 | 119 | 1064.3 | 0 |
| 20261024_221714 | B + 关 self_check | 0.940 | 1,029,966 | 106 | 985.1 | duty_short |
| 20261024_215545 | B + 官方联网 | 0.933 | 1,062,012 | 99 | 1073.3 | duty_short, probe |
| 20261024_193452 | thinking off（fast） | 0.930 | 816,983 | 106 | 782.6 | 2 |
| 20261024_163455 | serial 成本档 | 0.990 | 997,457 | 107 | 1920.6 | 0 |
| 20261024_203201 | A 层并行 | 0.220 | 868,718 | 121 | 1079.3 | duty_short, probe, unsaid |
| 20261024_213016 | E DAG | 0.922 | 993,472 | 99 | 1513.7 | duty_short, unsaid |
| 20261024_195354 | hybrid 关判断思考 | 0.946 | 1,131,199 | 115 | 2033.7 | 1 |
| 20261024_232902 | C 流水线 | 0.9464 | 931,439 | 96 | 1266.5 | 0 |
| 20261024_235215 | D DAG 并行 | 0.9500 | 1,093,196 | 105 | 1402.3 | 1 |

结论：
- 质量/墙钟双优：B（1.000 / 1064.3s / 126.9万 tokens，成本放宽下最优）。
- 时间最优：fast（0.930 / 782.6s / 81.7万 tokens）。
- 低 tokens 质量档：serial（0.990 / 99.7万 tokens / 1920.6s）。
- 联网最优：B+web（0.933 / 1062,012 / 1073.3s），优于旧 serial+web（0.909 / 1889.7s）。
- A/E/C 三种并行模式均未超越 B：A 质量门失败（0.220），E 0.922/1513.7s，C 0.9464/931,439/1266.5s（flags 0）；
  C 作为“低 tokens/零 flags”折中点记录，但不取代 B（质量/墙钟）或 serial（低 tokens 质量档）。
- D DAG 并行：0.9500/1,093,196/1402.3s，flags duty_short，被 B/fast 支配；
- hybrid 关部分思考反而更慢；B-no-selfcheck 质量降 6% 仅换 79s，不采纳。

## 二、阶段级耗时分析（来自 llm_by_stage）

B（20261024_205018）：
| 阶段 | calls | tokens | ms |
|---|---|---|---|
| unknown（核心生成） | 50 | 778,927 | 1,373,351 |
| dual_judge | 12 | 149,254 | 226,619 |
| self_check | 12 | 151,083 | 138,662 |
| re_evaluate_pool | 12 | 14,133 | 22,883 |
| phase_probe | 2 | 13,424 | 21,706 |
| probe_research | 4 | 45,801 | 15,915 |

E（20261024_213016）：unknown 1,334,046ms / dual_judge 177,741ms / self_check 176,837ms。
B+web（20261024_215545）：unknown 1,095,801ms / dual_judge 201,144ms / self_check 125,879ms。

判断：
- 墙钟由 unknown 核心生成主导（约 6 成以上），其次 dual_judge/self_check；阶段开关可以削 100–200s，但会伤质量/停止判据；
- B-no-selfcheck 实验验证：exact 省一次自省调用换来质量 1.000→0.940，不划算；
- 进一步墙钟优化应针对 unknown 的并行/缓存/输出长度，而不是盲关判据阶段。

## 二（补）、KV 缓存探针（B 模式，不改引擎文件）

- 探针方式：scripts/run_engine_instrumented.py 注入 OpenAI SDK create 钩子；
- 命中：prompt_cache_hit_tokens=77,184；miss=489,340；cache_hit_ratio=13.62%；
- 重复 prompt：0 / 90；=> 响应去重无收益；
- 本次 B 变体：quality 0.9592 / tokens 773,603 / wall 869.7s / flags duty_short；
  说明 B 存在运行间方差（0.959–1.000，wall 870–1064s），质量/墙钟优先仍取 1.000 的 B。
- 优化方向：13.6% 命中偏低，说明多数调用的 system/上下文前缀不稳定；下一步可做静态前缀拆分/稳定化，
  预计提升 KV 命中、降低 unknown 阶段墙钟；响应级去重可直接放弃。

## 二（补2）、静态前缀 KV 实验（Round 7）

- 做法：探针给每条 system 消息前置同一段静态约束（约 140 字），观察缓存命中；
- 结果：cache_hit_ratio 13.62% → 18.46%（+4.8pp），hit_tokens 77,184 → 172,416；
- 但同一配置运行：quality 0.9741、tokens 1,266,323、wall 1442.3s（call 121），
  额外前缀 token 与轮次波动抵消收益；
- 结论：静态前缀不是有效的墙钟/成本优化，不采纳；KV 命中提升不足以覆盖新增 token。

## 三、模式级结论

- serial：历史 152 次，稳定；本次 0.990/99.7万/1920.6s。
- B：本次 1.000/126.9万/1064.3s，质量/墙钟双优；保留为默认质量模式。
- fast：0.930/81.7万/782.6s，时间档。
- A：质量门失败，不保留；E：被 fast 支配，不保留；C/D 未测（E 作为 DAG 代表已给负结果）。
- B+web：联网最佳档；B-no-selfcheck：折中备选，不默认。
- 保留三种模式：B、serial、fast；web 作为必须联网回退。M4 auto-fused 按场景选档，并支持 fast→B 级联。

## 四、已实施升级

1. M4 auto-fused 接入 App 2.0.11：
   - 真实任务默认 auto；GET /api/mode-fusion；POST /api/tasks 支持 fused_min_quality / fused_max_wall / fused_max_tokens / fused_require_web / fused_prefer；
   - 前端运行栏新增模式融合场景下拉；响应带 mode/reason/readout/quality_prediction。
2. 质量预测器：
   - dgtf_engine/dgtf_v2/quality_predictor.py + 训练脚本 + 模型 JSON（已入库）；
   - 特征：题面结构、route 层数、平均圈数、web、模式 one-hot、历史 calls/tokens/tri_rate/cut_rate；
   - 142 样本：随机切分 kNN(k=3,近期加权) R²=0.916 / MAE=0.048；时间切分 kNN R²=0.376（跨版本漂移）；
   - 采用“0.5 模型 + 0.5 模式先验”校准，只在预测明确时用于 fast→B 守卫。
3. App/本地模型：
   - health 2s TTL、chats 1s TTL；V2 帕累托图铺满、Y 0–1、X 0–200k、分箱中位数趋势；
   - BGE 文本级 LRU 缓存；cache-clean 批量 n=16 约 14.4ms/1109 texts/s；检索 recall@1=1.0、MRR=1.0；
   - 本地 LLM 质量代理弱，不进答案主路径。

## 四（补）、App 真实默认链路发现与修复（Round 10）

- 实测：App 默认任务由 M4 选 B（web off / quality 优先），但引擎 behavior_fusion=auto 随后强制
  web=on / thinking=high，实际变成高价联网档，20 分钟仍未完成（已取消）；
- 修复：M4 选档显式落 behavior_fusion=off、web/thinking/effort；auto_fused 时跳过 auto_policy 的
  0:4 圈数覆盖；runner 增加 --behavior-fusion 透传；
- 验证：真实任务启动后 cmd = --parallel B --web off --behavior-fusion off，无 0:4 强制圈数，随后取消；
- 2.0.13 复跑（无项目背景、rounds 提示 0:1...）：完成 310.7s、588,205 tokens、90 calls、2/2/2/2 圈、
  quality 0.8374、answer_ready=true、answer_quality=unverified、duty_short；
- 对照修复前（带项目背景）：1800s 超时、1.38M+ tokens、154 calls、5/6/4/7 圈、quality 0.9598；
- 结论：默认通用任务墙钟从超时降到 5.2min，代价是通用事实题答案质量标记 unverified；
  涉及项目的问题仍注入背景，质量优先可显式传 project_context/rounds。

## 五、剩余优化空间（下一轮候选）

- unknown 阶段的 DeepSeek KV cache 命中率追踪与稳定前缀优化（最大墙钟块）；
- dual_judge/self_check 的更细粒度替换（只对低风险候选调用），而非全局关闭；
- 模式 C/D 的同题实测（本轮只测代表 E）；
- M4 质量预测的跨版本校准（时间切分仍负 R²）；
- App 端到端首条产物时延测量与 UI 场景参数默认值调优。

## 五（补）. App 端到端编排基线（mock）

- POST /api/tasks：265.6ms；
- 首条日志可见：408.6ms；
- 完成：3478.3ms；
- 说明：App 编排本身为亚秒级，真实任务墙钟仍由引擎 LLM 主导。

## 六、验证

- fast_gate 12/0；V2 tests 39/39（534 项检查）；App selftest 371/0；pip check 0 broken（两环境）；project paths PASS；loop check 6/0；最新真跑预检 5/5；
- 提交与运行态：app 2.0.11 / engine 2.2.2；origin/main 已推送（见 git log）。

## 七、结论

按质量/墙钟优先、成本可放宽的顶配口径：
- 引擎：B 为质量/墙钟最优；fast 为时间最优；serial 低 tokens；B+web 联网最优；
- App/本地模型：缓存、图表、BGE 检索与缓存已到当前可测前沿；
- 联动：M4 auto-fused + 质量预测守卫已接入 App 并可解释选档；
- 尚无同方向实验能改进 B 的质量/墙钟，剩余优化集中在 unknown 阶段缓存与细粒度判据，已列入下一轮。

- M4 预测再加“历史区间”约束：模式质量取 [quality_low, quality]（B=0.959–1.000，fast=0.930，serial=0.990），
  校准后裁剪进区间，避免小样本/跨版本预测过度乐观；预测不明确时保持静态选档。


## 四（补2）、App 默认链路质量-墙钟取舍（2026-10-25 复跑）

| 变体 | wall | tokens | quality | answer_quality |
|---|---|---|---|---|
| 无背景、无联网 | 310.7s | 588,205 | 0.8374 | unverified |
| 无背景、显式联网 | 320.8s / 330.9s | 765,619 / 747,263 | 0.9783 / 0.9263 | verified |
| 无背景、默认联网失败样本 | 280.4s | 731,619 | 0.4900 | needs_evidence（no_official_source） |
| 有项目背景、无联网 | 约1800s 超时 | 1.92M | 0.9598 | verified |

- 事实题显式联网可 verified 且墙钟仅比无联网多约 10-20s，但官方源抓取有波动（一次失败样本）；
- 结论：App 2.0.14 把事实题联网接地做成 opt-in（fused_ground_web=true），默认仍 web off；
- 若强制通用任务 verified，可显式传 web=on/fused_ground_web，或接受项目背景长墙钟。

- 剩余优化空间评估：docs/remaining_optimization_assessment_20261025.md（dual_judge/self_check、C/D/E 外并行、App 取舍）。
