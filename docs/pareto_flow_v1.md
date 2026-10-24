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

读数：**同题当前非支配点 = 0.909 @ 96.9万（官方联网成本档 run6）与 0.990 @ 99.7万
（无网成本档 run7，flags=0）**；均衡档 0.951 @ 121.1万（run8）被 run7 支配——
**成本档反而质量更高**，故 V2.2.2 的 Pareto 最优引擎配置收敛到 run7（全四层、effort low、web off、
实测 rounds 0:3/1:2/both:2/all:3）。
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
- 本地 LLM 生成基线（GTX 1660 Ti 6GB，fp16，scripts/local_llm_bench.py）：
  · Qwen2.5-0.5B-Instruct：加载 3.22s，32 tokens p50=2.11s（15.2 tok/s）；
  · DeepSeek-R1-Distill-Qwen-1.5B：加载 10.06s，16 tokens p50=1.41s（11.4 tok/s）；
  · 结论：本地模型适合短文本/低并发兜底；长生成仍走云端更快（云端单跑 ~0.5–2s/步）。

## 4.1 组件内帕累托前沿（Round 4 实测）

- App（时延 vs 新鲜度）：health 2s TTL ~14ms（冷 ~475ms）；chats 1s TTL ~19ms（冷 ~300ms）；
  events 保持实时 ~300ms。当前取 2s/1s/实时三档，属于用户可接受的读数新鲜度前沿点。
- 本地 embedding（批量 n vs 时延/吞吐）：n=1 31ms/32 texts·s⁻¹；n=8 64ms/124；n=16 45ms/356；
  n=32 71ms/451；n=64 136ms/472（吞吐更高但时延翻倍）。建议：单条查询 n=1，批量索引 n=32。
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
| J1 推荐 | run7 + App 读数缓存 + BGE 批量 n=32 | 0.990 | 997,457 | health ~14–17ms、chats ~19ms、BGE 451 texts/s | 预算 ≥1.0M 时最优 |
| J2 | run6（官方联网）+ App 缓存 | 0.909 | 969,376 | search=11/fetch=4，联网时延另计 | 预算 <1.0M 且必须联网时 |
| J3 | 均衡档 run8 + App 缓存 | 0.951 | 1,210,815 | flags=0 | 被 J1 支配 |
联合快照：`docs/pareto_joint_snapshot_20261024.json`（引擎前沿 + App health/chats p50 + BGE health）。

## 6. 下一迭代（按优先级）

1. V2.2.2 同题受控 A/B（省成本/均衡/质量优先三档各一次），重画引擎前沿；
2. 把 app 端点 p50、本地 BGE/LLM 时延接入指标行，输出三组件联合非支配前沿；
3. `scripts/pareto_flow.py` 增加 `--recommend --budget-tokens N --min-quality Q` 选档；
4. App：chats/events 端点做 1s 短缓存或合并轮询；本地模型：embedding 批处理与路由缓存；
5. 记录每次真跑的配置→质量→成本映射，逐步收敛到“预算内最优”。
