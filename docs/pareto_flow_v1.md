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

读数：**当前质量-成本前沿在 0.86@51万 tokens 到 0.96@130万 tokens 之间**。
注意：这些 run 跨 V2.2.0→V2.2.1 版本且问题不同，只能作方向；V2.2.2（职责/unsaid 修复 +
官方联网默认）需要用同题受控 A/B 重画前沿（后续迭代）。

## 3. App 基线（本机实测，TLS 新连接/次）

| 端点 | 优化前 p50 | 优化后（2s TTL 缓存） |
|---|---|---|
| /api/health | 475 ms（冷 900 ms） | **16–18 ms**（冷 900 ms） |
| /api/dsh/chats | 306–331 ms | 306–331 ms（未缓存） |
| /api/dsh/current/events?full=1 | 301–320 ms | 301–320 ms |
| /api/agent/tasks | 6.6–20.5 ms | 6.6–20.5 ms |

静态资源：app.js 317,661 B / index.html 35,168 B / style.css 120,527 B。
本轮改进：health 读数 2s TTL 缓存（最多滞后 2s），高频轮询成本从 ~475ms 降到 ~17ms。

## 4. 本地模型基线

- BGE 服务 127.0.0.1:8771 /health：ok=true、cuda、dim=512、响应 **~2.9 ms**；
  模型目录 `local_model/models/bge-small-zh-v1.5`（服务内路径）。
- DeepSeek-R1-Distill-Qwen-1.5B 模型目录存在；`local_model/envs/dgtf_llm_env` 环境存在。
- 待补：embedding 批量吞吐、本地 LLM 首 token/总时延、失败率（下一迭代）。

## 5. 三者联动建议档位（首版，待受控 A/B）

| 档位 | 建议配置 | 依据 |
|---|---|---|
| 省成本 | 全四层、2 圈、v2_pareto、effort low | 074952：0.86 @ 51万 tokens |
| 均衡 | 全四层、2 圈、v2_contract、effort high | 081519：0.917 @ 67万 tokens |
| 质量优先 | 全四层、auto rounds（2→3）、v1_frontier | 145240：0.959 @ 130万 tokens |

联动当前结论：质量从 0.86→0.96 的成本约 **+153%**（51万→130万）；若目标质量 ≤0.92，
均衡档在成本上明显占优。下一迭代把 App p50 与本地模型时延并入目标，做预算约束下的选优。

## 6. 下一迭代（按优先级）

1. V2.2.2 同题受控 A/B（省成本/均衡/质量优先三档各一次），重画引擎前沿；
2. 把 app 端点 p50、本地 BGE/LLM 时延接入指标行，输出三组件联合非支配前沿；
3. `scripts/pareto_flow.py` 增加 `--recommend --budget-tokens N --min-quality Q` 选档；
4. App：chats/events 端点做 1s 短缓存或合并轮询；本地模型：embedding 批处理与路由缓存；
5. 记录每次真跑的配置→质量→成本映射，逐步收敛到“预算内最优”。
