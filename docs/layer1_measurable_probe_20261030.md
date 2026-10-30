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

## 6. 隔离实验仍不稳定 + 温度因素（V2.2.68 后）

用 `--isolate-eml`（playbook off + 独立 dir）对 case1 连跑 2 次：

| 次 | llm_calls | candidates | settle.total | 判定 |
|---|---|---|---|---|
| iso-1 | 31 | 0 | 0 | unmeasured |
| iso-2 | 31 | 0 | 0 | unmeasured |

- 隔离 EML 后仍未见候选（此前一次隔离实验曾见 candidates=2，说明还有其它因素）；
- **温度因素**：引擎 `LLM.call(... temperature=0.6)` 默认温度 0.6，很多阶段未显式传 0，
  本地 0.5B 解码存在随机性——这是候选/措辞波动的重要来源；
- 结论：层1 可测性受 **EML 状态 + 解码温度 + 候选可判定性** 多因素影响；
  当前 probe 对层1 继续如实标「未测出 + 结构化归因」，不伪造成可测。

## 7. 可测性不可重建（V2.2.72 后）

尝试从历史「可测」时刻重建状态：

1. 从 12:09 valued pack 提取 `playbook.applied`（carve_first/rounds_delta 等）；
2. 强行把 `dgtf_memory/behavior_fusion_stats.json` 改为选 `fusion_full`（历史可测时 arm），跑 temp0：
   **arm=fusion_full，但 cand=0、settle=0、unmeasured**；
3. 说明：可测不是单靠 arm 或某组 playbook 条目就能复现，**那次 valued 是瞬态状态**（后又不可复现）；
4. 结论：不再「碰运气」重建；要稳定可测，需要引擎侧**确定性的可判定性度量/输入**设计（后续工作）。


## 7.5 min_rounds / rounds 实验（V2.2.89，零 API 本地链）

为验证「层1 判据样本不足」是否只是圈数问题，用临时配置做两组本地实验：

| 实验 | 配置 | 结果 |
|---|---|---|
| 事实短题（水三态） | soft_max=3/stable_need=3/min_rounds{1:3} + rounds=3 | 事实短题策略把圈数压回 2；settlement.total=0，candidates=6 |
| reasoning（热岛） | 同上，题面非短事实 | **研究层实际跑满 3/3 圈**（min_rounds 拦截生效）；但 settlement.total=0、candidates=8、deferrals/resolutions 均为 0 |

结论：**圈数上限不是层1可测性的唯一瓶颈**——即使跑满 3 圈，本地链路的候选仍未进入
可判定通道（无 deferrals/resolutions），因此 settlement 仍为 0。要真正可测，需要
候选注册/可判定性判定的工程化改动，而不是只加 min_rounds。

证据：docs/min_rounds_probe_20261030.json（零云 API）。


## 7.6 拆解回退修复（V2.2.90，零 API 本地链）

根因：研究层子问题只来自 `_decompose_from_pool` 的 LLM JSON；本地 0.5B 解析失败时
静默返回 `[]` ⇒ `sub_questions=[]` ⇒ settlement.total=0 ⇒ 层1 恒「未测出」（与圈数无关）。

修复：新增 `decompose_fallback.fallback_subquestions()`，从修行层**探针/线头原文**
确定性生成子问题（不调 LLM、不改写，保守标 partial）；引擎在 LLM 结果为空时回退。

实测（同题热岛，本地链）：

| 指标 | 修复前 | 修复后 |
|---|---|---|
| sub_questions | 0 | 2（source P1/P2） |
| settlement.total | 0 | 2 |
| probe case1 | unmeasured | **valued 0.000（判据样本不足）** |

注意：目标仍是「判据样本不足」（2 个逐圈点 < 3），只是从「未测出」变为「有值」；
不宣称层1可达成，回退标签保守、由三态判决/清算继续修正。


## 7.7 拆解回退后的隔离复跑稳定性（V2.2.90，零 API）

回退上线后做隔离复跑（每次只跑目标 case，避免 case 间 EML 状态耦合）：

| 复跑 | calls | settlement/subs | 读数 | 状态 |
|---|---|---|---|---|
| case1 第 1 次 | 38 | 1/1 | **1.000** | 判据样本不足 |
| case1 第 2 次 | 38 | 1/1 | **1.000** | 判据样本不足 |
| both 第 1 次 | 74 | — | **0.500** | 判据样本不足 |
| both 第 2 次 | 74 | — | **0.500** | 判据样本不足 |

结论：**隔离复跑 2/2 完全一致**（calls、读数、状态），层1/both 从「未测出」变为
「可测但判据样本不足」；整跑（4 case 顺序）取值受 EML 状态影响（case1 0.0 / both 0.2917），
但仍为 valued。目标仍未达成（需要 3 个逐圈点）。

证据：docs/layer1_fallback_stability_20261031.json。


## 7.8 可复现 probe 模式：--fresh-playbook（V2.2.90，零 API）

全量四层 probe 用 `--fresh-playbook`（每次全新 playbook 目录）跑两次：

| run | 断言 | case0 | case1 | both | all |
|---|---|---|---|---|---|
| A | 82/82 | 19 calls / achieved 0.0 | 36 / **not_judgeable 0.0** | 82 / **not_judgeable 0.0** | 93 / not_achieved 0.5 |
| B | 82/82 | 19 calls / achieved 0.0 | 36 / **not_judgeable 0.0** | 82 / **not_judgeable 0.0** | 93 / not_achieved 0.5 |

**两次完全一致**（calls/读数/状态逐项相同）⇒ `--fresh-playbook` 可作为
**可复现 probe 模式**（隔离生产 playbook 状态）；默认模式仍跑生产状态（受 EML 耦合，
取值不同但仍 valued）。注意：层1/both 目标仍是「判据样本不足」（2 个逐圈点 < 3）。

证据：docs/layer1_reproducible_probe_20261031.json。


## 7.9 强制 3 圈：层1 目标首次可判定（V2.2.91，零 API）

用 probe 新能力 `--config-set` + `--question` 覆盖：
`--rounds 3 --fresh-playbook --question 为什么城市热岛效应...` +
`spiral.min_rounds.1=3 / soft_max=3 / stable_need=3`。

| 指标 | 结果 |
|---|---|
| 研究层 rounds_run | **3** |
| 逐圈 trace | **3 个点** |
| settlement.total | 2 |
| 目标判定 | **not_achieved（main=0.5）——不再「判据样本不足」** |
| llm_calls | 53（本地） |

结论：层1 目标**可以被判定**（本次判「未达成」），前提是研究层跑满 3 圈；
默认不启用该策略（成本），作为后续「动态 min_rounds」的证据。


## 7.10 强制 3 圈的可判定性复跑（V2.2.91，零 API）

同口径（--rounds 3 + min_rounds.1=3 + soft_max=3 + stable_need=3 + fresh-playbook）复跑：

| run | calls | trace | 目标判定 | main |
|---|---|---|---|---|
| 1 | 53 | 3 | **not_achieved** | 0.5 |
| 2 | 77 | 3 | **not_achieved** | 0.0 |
| 3 | 77 | 3 | **not_achieved** | 0.0 |

结论：**「可判定」本身可复现（3/3 均为 not_achieved、trace 3 点）**；main 取值随状态/缓存
波动（0.5/0.0/0.0），不再出现「判据样本不足」。默认仍不启用强制加圈（成本）。

证据：docs/layer1_judgeable_repeat_20261031.json。


## 7.11 opt-in 自动最小圈数（V2.2.92，零 API）

引擎新增 `spiral.min_rounds_judgeable`（默认 false 零行为差）：开启后研究/对撞层
计划圈数与 min_rounds 自动抬到 target（默认 3）。**仅传该 config-set、不再手传圈数**：

| 指标 | 结果 |
|---|---|
| 研究层 rounds_run | **3**（自动抬圈） |
| trace | 3 点 |
| 目标判定 | **not_achieved（main=0.0）** |
| probe 断言 | 23/23 PASS |
| llm_calls | 55（本地） |

边界：默认不开；开启成本约 ¥0.074/圈/层（按既有校准）；建议 quality+预算 ok 时显式启用。


## 7.12 并行 B 模式同样生效（V2.2.92，零 API）

引擎默认并行模式 B（App 路径）验证 opt-in 自动最小圈数：

- 配置：spiral.min_rounds_judgeable=true（target=3），`--parallel B --rounds 2`（不再手传更高圈数）；
- 结果：研究层 **rounds_run=3**、trace **3 点**、settle=2，
  lga.classify_target 判定 **not_achieved**（settle=0.5 仍在涨）；
- 63 calls / 75,637 tokens（本地）；证据 docs/layer1_parallel_b_judgeable_20261031.json。

结论：串行与并行 B 两条入口都遵守该 opt-in；默认关闭仍零行为差。


## 7.13 字符串 layers 写法修复（V2.2.93，零 API）

旧实现把 `min_rounds_judgeable_layers: "1,both"` 按字符迭代 ⇒ opt-in 静默失效。
修复后按中英文逗号拆分；单测 J11/J12（共 12/12），并行 B 端到端出现
`B 第 3 圈停止`（63 calls / 75,637 tokens，本地）。


## 7.14 全不可判定补 provisional partial（V2.2.96，零 API）

V2.2.95 复跑发现：LLM 拆解成功但子问题**全判 undecidable** ⇒ settlement.total=0 ⇒ 仍未测出。
修复：`answerable_fallback()` 在「有子问题但无一条 decidable/partial」时，用探针/线头补 1-2 条
provisional partial（source 前缀 `FB:`），**不修改原判定**；有可答子问题时完全不介入。

验证：tests_decompose_fallback **9/9**（F7/F8/F9）；probe case1 复跑 valued 0.0（48 calls，subs=2 partial P1/T1）。
证据：docs/layer1_answerable_fallback_20261031.json。


### 7.14 附：V2.2.96 复跑残留（2026-10-31 04:40）

- 全量 probe：84/84 PASS，但 case1 仍 **unmeasured**（32 calls）；
- 产物：subs=0，且 **probes=0 / threads=0 / amps=0**（层0 仅 2 个 candidates）⇒
  V2.2.90/V2.2.96 回退都**没有可用来源**；
- 结论：V2.2.96 修复的是「全不可判定」路径，**未覆盖**「拆解输出为空且探针/线头也为空」路径；
- 下一步：为回退增加候选（candidates）来源（V2.2.97 候选）。


## 7.15 candidates 兜底（V2.2.97，零 API）

V2.2.96 残留：拆解空输出 + 探针/线头/amps 全空 ⇒ 回退无来源 ⇒ 整跑 unmeasured（层0 仅 candidates）。
修复：fallback 增加 candidates 来源（题面 `候选判定：`，source `C#`）。

验证：tests_decompose_fallback **11/11**（F10/F11）；probe case1 **valued 0.0**
（46 calls；subs=2 partial，source **T1 + C1**——本次 e2e 实际命中 candidates 分支）。
证据：docs/layer1_candidates_fallback_20261031.json。


## 7.16 全量 probe 稳定 valued（V2.2.98，零 API）

V2.2.97 全量 probe **三次**（各 82/82 PASS）：

| run | case0 | case1 | both | all |
|---|---|---|---|---|
| A | 23/achieved 0.0 | 33 / **valued 0.0** | 80 / **valued 0.0** | 109 / not_achieved 0.5 |
| B | 23/achieved 0.0 | 33 / **valued 0.0** | 80 / **valued 0.0** | 109 / not_achieved 0.5 |
| C | 23/achieved 0.0 | 44 / **valued 0.5** | 86 / **valued 0.0** | 117 / not_achieved 0.5 |

结论：层1 **状态稳定 valued（3/3）**，不再出现 unmeasured；但 **main 取值与调用数随状态/缓存波动**
（0.0/0.0/0.5；33/33/44 calls），整跑数值复现仍有限。目标仍判据样本不足（2 点<3），**不宣称达成**。
证据：docs/layer1_stable_valued_20261031.json。


## 7.17 opt-in 自动最小圈数：可判定性稳定（V2.2.98，零 API）

配置：仅加 `spiral.min_rounds_judgeable=true`（默认关），case1、fresh playbook，
两次复跑：

| run | 断言 | calls | trace | 目标判定 | main |
|---|---|---|---|---|---|
| A | 23/23 | 59 | 3 | **not_achieved（可判定）** | 0.0 |
| B | 23/23 | 59 | 3 | **not_achieved（可判定）** | 0.0 |

结论：开启该 opt-in 后，研究层**两次复跑逐项一致**（calls/状态/main 全同），目标从
「判据样本不足」变为**稳定可判定**；默认仍关闭（成本考虑，单次多约 1 圈/层）。
证据：docs/layer1_auto_judgeable_stable_20261031.json。


## 7.18 both 层 opt-in 可判定且达成（V2.2.98，零 API）

配置：`spiral.min_rounds_judgeable=true`（默认关），probe `--only both` + fresh，两次：

| run | 断言 | calls | trace | 目标判定 | main |
|---|---|---|---|---|---|
| A | 24/24 | 98 | 3 | **achieved** | 0.0 |
| B | 24/24 | 98 | 3 | **achieved** | 0.0 |

结论：补到 3 个逐圈点后，both 层的「fuse 连续不涨」判据可判定并**达成**（fuse=0.0 且 3 点不涨）；
默认 2 圈时它只能停在「判据样本不足」。这是原语判定（非质量宣称）：fuse 不涨 = 对撞层停止融合出新层面。
证据：docs/layer1_auto_judgeable_stable_20261031.json。


## 7.19 preset 入口：方案Q·可判定优先（V2.2.99）

新增 `configs/方案Q-可判定优先.yaml`（= 方案 D 高质量 + 显式 opt-in）：
`min_rounds_judgeable=true / layers ["1","both"] / target 3`。
App 的 profile 列表可直接选择；默认配置不变。验证：App `profile_path` 可解析、
引擎 `_spiral_for` 读到 min_rounds 1:3、24 preset 陈旧键 0。


## 7.20 preset Q 端到端验证（V2.2.99，零 API）

用方案Q preset（quality + opt-in）替换本地端点后真实跑一题（热岛，route 0,1，rounds 2）：

- 研究层跑满 **3/3 圈**（serial 模式，min_rounds=3 拦截生效），43 calls / 52,896 tokens（本地）；
- settlement.total=1（有值）；preset Q 与方案 D 的差异**仅 3 个 opt-in 键**；
- 证据：docs/preset_q_verify_20261031.json。
注：本次本地验证产物落在 outputs/，会被 dsh_loop_check B 当作「最新真跑」抽查
（answer_quality=unverified ⇒ 预检 FAIL）；验证后已删除该本地产物，发布门恢复 PASS。
今后本地 e2e 应写到临时目录，勿污染输出目录。



## 7.21 preset Q 在 App 可见（V2.2.99）

App 调度配置列表 `_schedule_profiles()` 实测返回 24 项，含 **方案Q-可判定优先**
（parallel_mode=serial）；用户可在 App 中选择该 preset 获得「研究/对撞层至少 3 圈」的可判定模式。
证据：docs/preset_q_app_visibility_20261031.json。


## 7.22 方案Q：serial vs parallel B 成本对照（V2.2.99，零 API）

同题同配置（方案Q 本地端点、route 0,1、rounds 2）本地单次：

| 模式 | 墙钟 | llm_calls | tokens |
|---|---|---|---|
| serial（方案Q 继承） | 248.1s | 57 | 79,670 |
| parallel B | **182.0s** | **46** | **66,864** |
| 变化 | −26.6% | −19.3% | −16.1% |

初步结论：B 模式在该题上更快、更省调用/token；但并行轮次语义与 serial 不同，
**质量未对比、不宣称等价**。可作为「方案Q 是否改 parallel_mode」的下一轮决策依据。
证据：docs/preset_q_parallel_ab_20261031.json。


## 7.23 方案Q serial vs B：结构读数与冷/热跑（V2.2.99，零 API）

同题同配置（route 0,1、rounds 2）对照：

| 维度 | serial | parallel B |
|---|---|---|
| 冷跑墙钟 | 248.1s | 182.0s |
| 热缓存墙钟 | 10.1s | 11.2s |
| llm_calls / tokens | 43 / 52,896 | 46 / 66,864 |
| views.1 candidates | 0 | 13 |
| settle.total / main | 1 / 0.0 | 0 / null（unmeasured） |

结论：
- 冷跑墙钟 B 更快（−26.6%），但**热缓存后墙钟不可比**（同样 calls/tokens，10s 级）；
- 两种模式**结构读数不同**（candidates/settle），质量未 verified，**不宣称等价**；
- 本地链结果受缓存/状态影响，不能单独作为模式优劣结论；真 API A/B 仍需预算。
证据：docs/preset_q_parallel_quality_20261031.json。


## 7.24 判定语义收敛（V2.2.99，避免误读）

| 判定 | 含义 | **不是** |
|---|---|---|
| valued | 读数可算（分母存在/有值），通道健康 | 质量达标 |
| achieved | **原语判据**成立（如 both：fuse 连续 2 圈不涨） | 产品质量/答案更好 |
| not_achieved | 原语判据未成立（如 settle 仍在涨） | 系统故障 |
| not_judgeable | 逐圈点不足（需 3 点、实有 2 点） | 未测出 |
| unmeasured | 分母为 0（无可判定子问题/无来源） | 判据不成立 |
| blocked | 结构性受阻（如语义停滞达阈） | 普通未达成 |

原则：**"可判定"只说明判据可执行；"achieved"只说明原语阈值命中**。质量结论必须另看
verified/ready 与人工审阅，二者不可互换。

## 8. 后续建议（需预算或明确方向）

- 方案 A（有预算）：1 个 web on 的层1 小样本（单跑约与既有 A/B 同量级），验证能否产生 candidates>0；
- 方案 B（零成本但改引擎）：让研究层候选生成不依赖 web（需设计 + V2 测试 + 发布），风险较高；
- 方案 C（零成本/小改）：为可复现实验提供确定性解码开关（temperature=0 显式透传），
  先在 probe 内有界验证，再决定是否进生产；
- 在此之前，probe 对层1 保持「未测出 + 结构化归因」，不伪造成可测。

