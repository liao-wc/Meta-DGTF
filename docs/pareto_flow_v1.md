# 全流程帕累托最优先行基线（V1）

日期：2026-10-24
范围：引擎 / App / 本地模型三组件基线 + 三者联动指标定义。
目标第 1 步：把「质量 / 成本 / 时延」变成可复现读数与不靠猜的非支配前沿；
后续迭代用受控 A/B 填充组件内与联动前沿，再做预算内自动选优。

## 1. 指标口径

引擎（产物直读，不猜）：
- quality 0..1：answer_ready 0.35 + verified 0.25 + standard_all 0.20 + coverage×0.10 + 无旗 0.10
- tokens：llm_tokens（成本代理）；calls：llm_calls（时延代理）；elapsed 有则读，无则留空

App：
- 端点 p50/max 时延（health / chats / events / tasks）、静态资源字节、selftest 通过数

本地模型：
- BGE 服务 /health 时延与设备、模型文件可用性、本地环境 pip check、后续 embedding 吞吐

三者联动：
- 统一目标（quality↑, tokens↓, calls↓, app_p50↓, local_embed_p50↓）；
- 配置维度：route / rounds / behavior arm / effort / thinking / web / parallel。

## 2. 引擎前沿基线（20261024 历史真跑，混合版本，仅作方向）

命令：`python scripts/pareto_flow.py`（13 份当日产物，6 个非支配点）

| id | quality | tokens | calls | 行为 arm | 配置摘要 |
|---|---|---|---|---|---|
| 20261024_070234 | 0.830 | 478,123 | 80 | fusion_full | rounds 2/2/2/2，effort high |
| 20261024_074952 | 0.860 | 511,634 | 82 | v2_pareto | rounds 2/2/2/2，effort low |
| 20261024_081519 | 0.917 | 671,144 | 83 | v2_contract | rounds 2/2/2/2，effort high |
| 20261024_082820 | 0.920 | 733,605 | 87 | v2_contract | rounds 2/2/2/2，effort high |
| 20261024_145240 | 0.959 | 1,295,308 | 117 | v1_frontier | auto 2 圈 → 实际 3 圈，thinking/effort auto |
| 20261024_160020（V2.2.2 成本档） | 0.909 | 969,376 | 89 | auto | 1 圈预算 → 2 圈；默认 DeepSeek 官方联网 |
| 20261024_163455（V2.2.2 成本档·无网） | **0.990** | **997,457** | 107 | auto | rounds 0:3/1:2/both:2/all:3；**flags=0**；web off（合法成本档） |
| 20261024_171058（V2.2.2 均衡档·无网） | 0.951 | 1,210,815 | 134 | auto | rounds 0:3/1:4/both:2/all:4；flags=0；被成本档 run7 支配 |
| 20261024_175452（V2.2.2 质量档·官方联网） | 0.980 | 1,844,908 | 154 | auto | rounds 0:3/1:5/both:4/all:5；flags 1；被 run7 支配 |
| 20261024_190707（3层 route 0,1,both） | **不可行** | 545,869 | 74 | auto | all 元层未执行（rounds all=0），answer_ready=false；flags duty_short / all_closure_unavailable / core_audit_gaps |
| 20261024_193452（关思考超省成本档·无网） | **0.930** | **816,983** | 106 | auto | rounds 0:3/1:2/both:2/all:3；flags 2（ing_rephrased_direct）；wall 782.6s；墙钟维度新增前沿点 |
| 20261024_195354（hybrid thinking·关判断环节思考） | 0.946 | 1,131,199 | 115 | auto | rounds 0:2/1:2/both:2/all:5；flags 1；wall 2033.7s；**被 run7 支配**（关判断思考未降墙钟，all 层反而多跑） |
| 20261024_205018（模式 B·动态规划） | **1.000** | 1,269,082 | 119 | **B** | coverage=1.0；**flags=0**；wall **1064.3s**；质量/墙钟双优 |
| 20261024_203201（模式 A·层并行） | **不可行(0.220)** | 868,718 | 121 | A | answer_ready=false、standard_all=false；flags duty_short/probe/unsaid_overused；层并行丢对齐 |
| 20261024_213016（模式 E·DAG） | 0.922 | 993,472 | 99 | E | flags duty_short/unsaid_overused(4)；wall 1513.7s；被 fast 支配 |
| 20261024_215545（模式 B + 官方联网） | 0.933 | 1,062,012 | 99 | B | search=4/fetch=6；flags duty_short/probe；wall 1073.3s；联网最佳档 |

**模式级 A/B（Round 14）**：模式 B（动态规划）quality=1.000、coverage=1.0、flags=0、
tokens=1,269,082、wall=1064.3s，**质量/墙钟双优**；模式 A（层并行）质量门失败（0.220），
层并行丢跨层对齐、不可交付。

**四档受控 A/B 完成**：
- 质量/成本/calls 三目标非支配：run6（0.909@96.9万/calls89）、run7（0.990@99.7万/calls107）、
  run11（0.930@81.7万/calls106）；
- 加入墙钟（quality/tokens/wall）：**run11 支配 run6**（质量更高、tokens 更少、wall 782.6s vs 1889.7s），
  前沿 = **run11（0.930/81.7万/782.6s）与 run7（0.990/99.7万/1920.6s）**；
  run6 仅在「低 calls / 必须联网」约束下保留。
结论：
- **质量/墙钟优先：模式 B（动态规划）**，quality 1.000、wall 1064.3s（tokens 126.9万，成本放宽）；
- **低 tokens 质量档：run7（serial）**，quality 0.990、tokens 99.7万、wall 1920.6s；
- **时间/成本优先：run11（thinking off）**，quality 0.930、wall 782.6s、tokens 81.7万；
- 必须联网：**B+web（20261024_215545，0.933/106.2万/1073.3s）** 优于旧 serial+web（0.909/96.9万/1889.7s），成为联网场景推荐；
- 模式 A（层并行）质量门失败，不保留；C–H 暂无同题实测，不纳入保留模式。
- Hybrid 负结果（run12）：只关 dual_judge/plan 等判断环节思考，quality 0.946、tokens 113.1万、
  wall 2033.7s，被 run7 支配（all 层从 3 圈涨到 5 圈，墙钟反升）——逐环节关思考不是有效的墙钟优化路径。
- 模式 A 负结果（run13）：四层并行 wall 1079.3s 虽快，但 answer_ready=false、standard_all=false、
  flags 3 条（duty_short/probe_no_target_covered/unsaid_overused），质量门失败——并行层之间的对齐/闭合不能省。
注意：这些 run 跨版本且问题不同，只能作方向。V2.2.2 已用 20261024_160020 验证：
质量门 PASS、standard_all=true、flags 仅 probe_no_target_covered、四层 duty 均不 short；
默认官方联网实测 search=11 / fetch=4（抓取生效）。

## 3. App 基线（本机实测，TLS 新连接/次）

| 端点 | 优化前 p50 | 优化后（2s TTL 缓存） |
|---|---|---|
| /api/health | 475 ms（冷 900 ms） | **12–17 ms**（冷 ~460–900 ms） |
| /api/dsh/chats | 306–331 ms | **~19 ms**（1s TTL 缓存；冷 ~565 ms） |
| /api/dsh/current/events?full=1 | 301–320 ms | 301–320 ms |
| /api/agent/tasks | 6.6–20.5 ms | 6.6–20.5 ms |

静态资源：app.js 317,661 B / index.html 35,168 B / style.css 120,527 B。
本轮改进：health 2s TTL（~475ms→~14ms）+ chats 1s TTL（~300ms→~19ms），只影响读数新鲜度（≤2s/≤1s）。

## 4. 本地模型基线

- BGE 服务 127.0.0.1:8771 /health：ok=true、cuda、dim=512、响应 **~2.9 ms**；
  模型目录 `local_model/models/bge-small-zh-v1.5`（服务内路径）。
- DeepSeek-R1-Distill-Qwen-1.5B 模型目录存在；`local_model/envs/dgtf_llm_env` 环境存在。
- BGE /embed 批量基线（3 次中位）：n=1 31.3ms（32 texts/s）；n=4 65.8ms（61/s）；
  n=8 64.3ms（124/s）；n=16 42.7ms（375/s）。
- BGE 检索质量代理（scripts/local_retrieval_eval.py；24 条项目语料 / 10 查询）：
  recall@1=1.000、recall@3=1.000、MRR=1.000；语料批量 embedding 313.5ms，查询 embedding p50 28.4ms。
  结论：本地检索质量在本语料上达标，配合 n=32 批量 451 texts/s，本地 BGE 是「质量-时延」双优组件；
  但本地 LLM 生成质量弱，不应进答案主路径。
- **BGE 文本级 LRU 缓存（V2.0.9）**：同文本首访冷 ~240ms（含 CUDA 预热），命中 p50 ~13ms；
  3 条批量冷 59.2ms → 热 20.8ms（/health 带 hits/misses/size）。缓存向量与原向量一致，
  属纯时延改进；重复查询场景下本地检索时延下降约 65%（批量）。
- 本地 LLM 生成基线（GTX 1660 Ti 6GB，fp16，scripts/local_llm_bench.py）：
  · Qwen2.5-0.5B-Instruct：加载 3.22s，32 tokens p50=2.11s（15.2 tok/s）；
  · DeepSeek-R1-Distill-Qwen-1.5B：加载 10.06s，16 tokens p50=1.41s（11.4 tok/s）；
  · 结论：本地模型适合短文本/低并发兜底；长生成仍走云端更快（云端单跑 ~0.5–2s/步）。
- 本地模型质量代理（scripts/local_model_quality.py；BGE 相似度+关键词覆盖+长度，非人工评阅）：
  · Qwen2.5-0.5B：proxy 0.579、sim 0.676、kw 0.2、生成 p50 5.05s；
  · DeepSeek-R1-1.5B：proxy 0.592、sim 0.665、kw 0.2、生成 p50 5.37s。
  · 结论：两模型质量代理接近且事实性弱（会泛化/走题），**本地 LLM 不进答案主路径**；
    本地组件的 Pareto 价值在 BGE 检索/embedding（高吞吐低时延），LLM 仅做轻量辅助。

**3 层边界（Round 8 负结果）**：去掉 all 元层省 token 的路线不可行——
all 层 rounds=0、product_chars=0，answer_ready/process_ready=false，standard_all=false，
flags=duty_short/all_closure_unavailable/core_audit_gaps；产物已归档到 outputs/negative_runs/。
结论：四层全跑是「答案可交付 + 元层闭合」的硬约束，不能为省 tokens 去掉 all 层；
引擎 Pareto 优化只能在四层内做（run6/run7）。

## 4.1 组件内帕累托前沿（Round 4 实测）

- App（时延 vs 新鲜度）：health 2s TTL ~14ms（冷 ~475ms）；chats 1s TTL ~19ms（冷 ~300ms）；
  events 保持实时 ~300ms。当前取 2s/1s/实时三档，属于用户可接受的读数新鲜度前沿点。
- 本地 embedding（cache-clean、GPU 空闲实测）：n=1 25.7ms/39 texts·s⁻¹；n=4 24.2ms/166；
  n=8 21.5ms/373；n=16 **14.4ms/1109**；n=32 23.3ms/1371；n=64 43.4ms/1476。
  建议：单条查询 n=1，批量索引 n=16–32（此前旧值含 GPU 争用/缓存干扰，已修正）。
- 本地 LLM（模型 vs 速度）：Qwen0.5 15.2 tok/s、加载 3.22s；DeepSeek1.5 11.4 tok/s、加载 10.06s。
  小模型适合轻量/低延迟兜底，大模型只在需要推理时按需加载。

## 5. 三者联动建议档位（首版，待受控 A/B）

| 档位 | 建议配置 | 依据 |
|---|---|---|
| 省成本 | 全四层、2 圈、v2_pareto、effort low | 074952：0.86 @ 51万 tokens |
| 均衡 | 全四层、2 圈、v2_contract、effort high | 081519：0.917 @ 67万 tokens |
| 质量优先 | 全四层、auto rounds（2→3）、v1_frontier | 145240：0.959 @ 130万 tokens |

联动当前结论：质量从 0.86→0.96 的成本约 **+153%**（51万→130万）；若目标质量 ≤0.92，
均衡档在成本上明显占优。下一迭代把 App p50 与本地模型时延并入目标，做预算约束下的选优。

（Round 4 更新）预算选档实测：`--budget-tokens 1100000 --min-quality 0.9`
→ 推荐 `20261024_163455`：quality=0.990、997,457 tokens、107 calls（flags=0，全四层）。

| 联动档位 | 组合 | 质量 | 引擎 tokens | 组件读数 | 结论 |
|---|---|---|---|---|---|
| J1b 质量/墙钟优先 | **模式 B** + App 缓存 + BGE n=16–32 | **1.000** | 1,269,082 | wall 1064.3s；flags=0 | 质量/墙钟双优，成本放宽 |
| J1 推荐 | run7 + App 读数缓存 + BGE 批量 n=16–32 | 0.990 | 997,457 | health ~5–17ms、chats ~4–19ms、BGE 1109–1371 texts/s | 预算 ≥1.0M 时最优 |
| J0（时间优先） | run11（关思考成本档）+ App 缓存 | 0.930 | 816,983 | wall 782.6s；flags 2 | wall 最低，质量 0.93 |
| J2 | **B+web（官方联网）** + App 缓存 | 0.933 | 1,062,012 | search=4/fetch=6，wall 1073.3s | 必须联网时（质量/墙钟最佳联网档） |
| J3 | 均衡档 run8 + App 缓存 | 0.951 | 1,210,815 | flags=0 | 被 J1 支配 |
| J4 | 质量档 run9（官方联网）+ App 缓存 | 0.980 | 1,844,908 | search=13/fetch=5 | 被 J1 支配，质量未过 0.99 |

- **墙钟维度（Round 10/13）**：`docs/pareto_engine_times.json` 记录真跑墙钟（秒）——
  run6=1889.7、run7=1920.6、run8=2116.9、run9=2933.3、**run11=782.6**；App/BGE 为毫秒级，可忽略。
  三目标（quality↑ / tokens↓ / wall↓）下非支配点 = **run11（0.930/81.7万/782.6s）与 run7（0.990/99.7万/1920.6s）**；
  run6 被 run11 支配（仅低 calls/必须联网时保留）。
  选档器支持 `--elapsed-json docs/pareto_engine_times.json --max-wall-seconds N`。

联动选档器（Round 5）：`scripts/pareto_flow.py --budget-tokens 1000000 --min-quality 0.9 --with-components --joint-select`
→ 选中 run7（0.990/997,457/107，无网档）；加 `--require-web` 且预算 <1.0M 时自动退到 run6 官方联网档，
无可行候选时返回原因（不静默换算法）。
联合快照：`docs/pareto_joint_snapshot_20261024.json`（引擎前沿 + App health/chats p50 + BGE health）。

- **三组件联动报告（Round 12）**：`docs/pareto_joint_report_20261024.md` / `.json`，
  由 `scripts/pareto_report.py` 只读生成（引擎真跑 + 墙钟 + App 端点 + BGE 冷热读数 + 联动选档）。
  本机实测：health ~5ms、chats ~4ms、events(full) ~313ms、BGE embed 冷 107ms / 热 1.9ms。

## 6. 下一迭代（按优先级）

1. V2.2.2 同题受控 A/B（省成本/均衡/质量优先三档各一次），重画引擎前沿；
2. 把 app 端点 p50、本地 BGE/LLM 时延接入指标行，输出三组件联合非支配前沿；
3. `scripts/pareto_flow.py` 增加 `--recommend --budget-tokens N --min-quality Q` 选档；
4. App：chats/events 端点做 1s 短缓存或合并轮询；本地模型：embedding 批处理与路由缓存；
5. 记录每次真跑的配置→质量→成本映射，逐步收敛到“预算内最优”。
