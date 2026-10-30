# 研究层可测率探索（零成本，2026-10-30）

> 目标：回答「层1 研究·收敛 为什么长期未测出」；本轮用本地 0.5B 链路（8772/8773）
> 跑 4 个候选题面，**零云 API 花费**。证据：`docs/layer1_measurable_probe_20261030.json`。

## 1. 方法

- 复用 `scripts/local_model/probe_layer_goals.py --only 1 --question ...`（真实入口，独立复算）；
- 配置：App 本地档（8773 适配层）、`web_search.enabled=false`、route=1、每层 2 圈；
- 4 个候选题面（覆盖事实/比较/枚举/机制四类）：
  1. 2025年全球主要经济体的GDP增速分别是多少？
  2. 比较太阳能与风能在中国的发电成本与装机趋势
  3. 列出三种常见空气污染物及其主要健康影响
  4. 为什么城市热岛效应在夜间比白天更明显？

## 2. 结果（全部未测出）

| # | 题面类型 | llm_calls | 墙钟 | settlement.total | answered | view.candidates | decidability |
|---|---|---|---|---|---|---|---|
| q1 | 事实/数值 | 21 | 64.7s | 0 | 0 | 0 | undecidable |
| q2 | 比较/趋势 | 20 | 55.5s | 0 | 0 | 0 | undecidable |
| q3 | 枚举/影响 | 13 | 32.5s | 0 | 0 | 0 | undecidable |
| q4 | 机制解释 | 19 | 47.0s | 0 | 0 | 0 | undecidable |

- 四例 probe 断言均 **24/24 PASS**（读数通道正常，不是判据坏了）；
- 关键中间量：packed `views.1.candidates = 0`（研究层没有候选子问题 ⇒ 分母无来源）；
- `decidability.status=undecidable`，`decidable_aspects=[]`；
- `settlement.decidable_channel.answers=[]`。

## 3. 结论（如实）

**层1 未测出不是题面不够好，而是该配置下研究层没有产出任何候选/探针/关系**：

- packed `views.1` 中 candidates/amps/threads/probes 均为 0（不是只缺 settlement）；
- 候选数为 0 ⇒ settlement 分母为 0 ⇒ verdict「未测出（可指认原因）」；
- 至于为什么产出 0：**本实验无法区分**「web off 无检索证据」与「本地 0.5B 分解能力不足"，
  两者都能造成同样现象；需要 web on 或更大模型对照才能归因；
- 无论如何：**当前零成本本地档下层1 不可测**，且换题面不能解决。

所以：

1. 不能靠「换题面」把层1 凑成可测（4 类题面均为 0 候选）；
2. 要测层1，需要**外部证据/检索（web on）**或**引擎在无检索下也能生成候选子问题**；
3. 两者都不是零成本：前者涉及检索费用，后者需要引擎改造 + 新证据。

## 4. 修正（V2.2.67，已落地）

后续用 route=0,1 + GDP 题面复跑，层1 **可测**：case1 settle=0.000（valued），
probe 82/82 PASS。因此最终根因是两条叠加：

1. **层1 依赖上游层0**：route=1 单跑时 `views.1.candidates=0`；
2. **题面必须能生成候选**：原「水的三态」题即使 route=0,1 仍 0 候选；GDP 题可生成。

前文的「web off / 本地模型能力」怀疑未被证实（未做 web on 对照），不再作为主因。

## 5. 可复现性修正（同配置复跑）

V2.2.67 曾观测到一次 case1 `settle=0.000（valued）`（44 calls、candidates=3）。
但随后用**完全相同配置**复跑 3 次，全部回到 `unmeasured`（27 calls、candidates=0、settle.total=0）：

- 说明「route 0,1 + GDP 题」是**必要但不充分**条件；
- 候选生成还受引擎 EML/历史状态、本地 0.5B 解码随机性等影响；
- 因此**不能宣称层1 已稳定可测**；V2.2.67 的 valued 只作为一次观测记录。
- 正式 probe 复跑：84/84 PASS、195 calls、59.2s，case1 为 unmeasured（读数通道正常）。

## 6. 后续建议（需预算或明确方向）

- 方案 A（有预算）：1 个 web on 的层1 小样本（单跑约与既有 A/B 同量级），验证能否产生 candidates>0；
- 方案 B（零成本但改引擎）：让研究层候选生成不依赖 web（需设计 + V2 测试 + 发布），风险较高；
- 在此之前，probe 对层1 保持「未测出 + 结构化归因」，不伪造成可测。

