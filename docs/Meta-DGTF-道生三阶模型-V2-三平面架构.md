# Meta-DGTF-道生三阶模型 V2 · 三平面架构设计

**知识面 EML × 控制面调度 × 执行面四层契约**

- 版本：V2.1.0 生产发布
- 生产入口：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.1.0.py
- 生产实现：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.1.0.py + dgtf_engine/dgtf_v2/（纯标准库、无 API、确定性）
- 目标：把“记忆、调度、四层”从同一条流程里的三段代码，改成三个职责分离、可独立验证、可回放的平面。

---

## 0. 一句话主张

四层不是流水线，而是四种**认知模式**；EML 不是向量库，而是**双时态、可修正、带论证状态的知识面**；调度不是 if-else，而是**在契约与预算约束下最大化期望信息价值的控制器**。

三条红线：

1. **记忆只影响调度/停止阈值，不影响答案内容。**
2. **每层只交契约允许的产物；缺项写 undecided，不补空话。**
3. **失败、败方、悬置、冲突都留痕；不删行。**

---

## 1. 现有实现的结构性问题

| 现状 | 结构性问题 |
|---|---|
| EML 是 episodes/playbook/nogoods/bandit 四套 JSONL，写入点分散 | 没有统一事件模型；无法回答“在 T 时刻我们相信什么”；修正是覆盖而不是追加 |
| 调度是 auto_plan + 模式选择 + 若干停止阈值 | 规则与阈值混在一起；没有显式的状态/动作/约束；无法离线回放“为什么选这层” |
| 四层是四个大函数 | 职责靠注释和约定；越权（0 层给答案、all 层重写内容）只能靠人看 |
| 质量读数是事后统计 | 不进入控制回路；下一跑仍凭感觉调参 |
| 记忆与调度是单向的 | 记忆不学“哪种调度在哪种状态下更好”；调度不写回结果 |

V2 不是把这些函数重写一遍，而是先**换控制面**：让每层有契约、让调度有状态、让记忆有双时态。

---

## 2. 三平面总览

    知识面 EML v2          控制面 Scheduler v2          执行面四层契约
    事件溯源/双时态   →     Monitor / Analyze        →   0 修行 · 发散
    语义信念+论证状态       Plan: EVOI + MPC + Pareto     1 研究 · 收敛
    程序性先验        ←     Execute: 契约闸          ←   both 对撞 · 辩证
    检索: BM25/RRF/MMR      outcome → credit             all 元 · 闭合
                              ↓
                    可观测性: calls/tokens/quality/contracts

三个平面各自有**唯一的写入权**：

- 知识面：只接受**事件**（append-only）；修正/击败也是事件。
- 控制面：只产生**动作**（跑哪层、几圈、停不停）；不产生文本。
- 执行面：只产生**契约产物**；越权由 validate_result 直接拒绝。

---

## 3. 四层契约：各司其职

| 层 | 目标 | 必须产出 | 禁止产出 | 退出判据 | 交给下游 |
|---|---|---|---|---|---|
| **0 修行** | 把潜在方面摊开 | aspect_map / suspensions / probe_queue / novelty_curve | answer / decision / closure / final_claim | novelty_stall / Heaps 饱和 / 预算 | 方面图与悬置；不替 1 下结论 |
| **1 研究** | 对可判定子问题给带不确定性的答案 | answer_set / abstentions / coverage / citations / debt_set | closure / action_plan / final_decision / 编造引用 | coverage 达标 / 可判定项全处理 / 预算 | 答案、弃权、债务；冲突不许抹平 |
| **both 对撞** | 在论证场里消解或明确保留张力 | synthesis / argument_graph / tension_set / defeated_claims | final_decision / action_plan / 删除败方 / 强行裁决 | 冲突全标签 / 综合引用双方 / 预算 | 论证图（含 defeated/undecided）；败方不删 |
| **all 元** | 决策级闭合 | decision / actions / not_do / residual_risks / provenance / confidence | 新内容 / 重写前层 / 删旗标 / 编造闭合 | 五件套齐 / 高严重度旗标处理或显式接受 / 预算 | ClosurePackage；缺项写 undecided |

### 3.1 0 修行：质量-多样性探索

**职责**：最大化“方面覆盖 × 新颖性”，不产出答案。

- **MAP-Elites 档案**：网格 = 方面 × 极性（阴/阳/both）；每个格子保留一个最清晰的方面与证据。按行为多样性保留，不按单一分数淘汰。
- **Novelty search**：候选新颖度 = 与档案最近邻的语义距离；低新颖度不奖励。
- **Heaps 饱和**：新方面数随圈数接近幂律；斜率趋平 ⇒ 结构饱和，允许停。
- **Thompson sampling 选探针**：探针成功率用 Beta 后验，探索/利用自动平衡。
- **悬置是一等产物**：写明“判断过、决定不碰”的理由与状态；不是失败。

**不许**：把“未生”写成负面结论；把方面图直接当答案。

### 3.2 1 研究：序贯检验 + 保形弃权

**职责**：对可判定子问题给出三态答案；不可判定是合法结果。

- **子问题 DAG**：AND/OR 依赖；前置未完成不展开后继，避免全局重答。
- **e-process / 置信序列**：边跑边看，任意停时有效；达到阈值才判 decidable，否则 partial/undecidable。
- **保形弃权**：用校准集给预测集；预测集大于 1 时输出 undecided；样本不足保守全弃权。
- **证据三角**：外部锚点（tier 门）+ 联网证据（只作参照）+ 内部一致；引用必须可追。
- **VoI 选证据**：下一个检索/锚点按“能否改变判决”排序，而不是按“还能搜什么”。

**不许**：为 decidable 编引用；把 partial 硬写成 decidable；把冲突藏进平均分。

### 3.3 both 对撞：论证场 + 辩证综合

**职责**：把 0 的方面与 1 的答案放进同一个论证场，输出综合与未决。

- **IBIS/Toulmin**：Issue → Position → Argument → Evidence；每个立场可追到证据/方面。
- **Dung 论证**：攻击关系 + grounded 语义；败方标 defeated，未决标 undecided，不删。
- **负担排序**：谁主张谁举证；tier 低的一方负担更高，不能靠“说得响”赢。
- **辩证综合算子**：thesis（1 的答案） × antithesis（0 的方面/反例） → synthesis（条件化结论）；综合必须引用双方。
- **Red team**：专门找“综合在什么条件下会错”，写进 tension_set，不强行消解。

**不许**：删 defeated；为闭环强行选 winner；把综合写成前两层复述。

### 3.4 all 元：决策级闭合

**职责**：把前三层产物变成可执行/可审计的 ClosurePackage。

- **元认知清单**：我漏了什么？哪条是假设？什么会改变判断？
- **Pre-mortem**：假设方案失败，倒推原因，写入 residual_risks。
- **决策理论**：不确定下用稳健性/最小最大遗憾选动作；置信度不是装饰。
- **RACI/责任契约**：每个动作有 owner / deadline / acceptance / rollback；没有回退方案不算动作。
- **STPA 风格控制分析**：识别“控制动作可能不安全”的上下文，写入 not_do。
- **Provenance**：每条结论可追到层/证据/事件；不把记忆当来源。

**不许**：重写前层内容；用“继续保持关注”凑动作；删掉未解决风险。

---

## 4. EML v2：双时态知识面

### 4.1 为什么不是向量库

向量库回答“相似”，Meta-DGTF 需要回答：

- 在某个时刻我们相信什么？（bitemporal）
- 这条信念凭什么成立？（provenance/support）
- 谁击败了它？还保留吗？（defeater/TMS）
- 它现在值得召回吗？（retention/trust）
- 它能不能影响调度而不污染答案？（guard）

### 4.2 事件模型

| 字段 | 含义 |
|---|---|
| id / run_id | 事件与跑次 |
| plane | episodic / semantic / procedural |
| layer / kind / key | 来源层、类型、聚合键 |
| payload | 结构化内容（不含密钥） |
| event_time / ingest_time / tx_time | 事件时间 / 落库时间 / 事务时间 |
| valid_from / valid_to | 有效时间（双时态另一维） |
| provenance / confidence | 来源链与置信 |
| support / defeaters | 支持者 / 击败者 |
| supersedes | 被本事件替代的旧事件（不删旧行） |

**双时态查询**：beliefs(as_of=t) 返回“在事务时间 t 时我们相信的版本”；旧版本仍可在历史查询中复现。

### 4.3 修正 / 支持 / 击败（AGM + TMS）

- **Expand**：新增信念（append semantic）。
- **Revise**：新证据与旧信念冲突 → 追加 revision，旧事件保留；supersedes 指向旧事件。
- **Contract**：不需要的信念不物理删除；标 stale/defeated，退出召回。
- **TMS**：support/defeaters 是理由图；击败不删除节点，只改标签。
- **Dung**：多个 defeaters 之间用 grounded 语义算 winner/undecided；平局保持 undecided。

### 4.4 检索：BM25 + 时近 + tier + RRF + MMR

- **BM25**：词面相关；中文用单字 + 二元组。
- **时近**：1/(1+age/halflife)；旧信念降权，不是直接丢。
- **tier**：来源可信度；tier 1 高于 tier 4。
- **RRF**：三路排名融合，避免分数尺度不可比。
- **MMR**：lambda*rel - (1-lambda)*max_sim；防止召回近重复。

### 4.5 巩固与遗忘（CLS / Ebbinghaus）

- micro：单跑事件；meso：同键/同主题聚类；macro：支持数够、surprise 够的语义信念。
- surprise：1 - 平均相似度；越意外越值得巩固。
- retention：exp(-ln2 * age / half_life)；低于阈值只标 stale，不删。
- spacing：重复出现但间隔拉长的条目，half_life 上调。

### 4.6 程序性先验（只给调度）

scheduler_priors() 只返回：

- 每个模板（如 1:r2）的 Beta 后验成功率；
- 平均 calls/tokens/quality；
- 样本数 n（用于探索 bonus）。

**硬闸**：contains_content=False；不包含 answer/claim 文本。测试检查先验 blob 里不出现任何答案词。

### 4.7 信用分配

每次调度动作 → LayerResult → quality/cost：

- 写一条 procedural outcome；
- 用 eligibility trace 把最终质量回传给该模板；
- 用 counterfactual replay（历史 packed）估计“如果当时选另一模板”；
- 先验只影响下一跑，不改本跑已生成答案。

---

## 5. 调度 v2：MAPE-K + EVOI + MPC

### 5.1 状态 / 动作 / 约束

状态：S_t = (layer_states, budget, conflicts, coverage, novelty, flags)

动作：a = (layer ∈ {0,1,both,all}, rounds ∈ {1,2}, evidence_mode)

约束：

- 依赖：1 至少吃到一个 0 圈；both 要 0/1 done；all 要 both done；
- 契约：动作只能落在层允许的职责内；
- 预算：calls/tokens/rounds 三重；
- 安全盾：非法动作直接过滤。

### 5.2 EVOI

EVOI(a) ≈ P(decision changes | a) * V(decision) - lambda * Cost(a)

- P：由 coverage gap / novelty gap / conflicts / closure gap 估计；
- V：层价值权重（0 探索 < 1 收敛 < both 辩证 < all 闭合）；
- Cost：EML 先验的 mean_tokens（冷启动用 fallback）。

选择分数：

score(a) = EVOI(a) / (Cost(a) + eps) + beta / sqrt(n+1)

最后一项是受控探索：新模板给小奖励，避免被旧先验锁死。

### 5.3 MPC

对每个候选动作模拟两步：

a1 = argmax_a [ score(a) + gamma * max_a2 score(a2 | simulate(S,a)) ]

- 视界 2（可配 3）；gamma=0.75；
- 模拟只用于排序，不记账；实际成本以执行结果为准；
- 模型失配由安全盾和事后 credit 修正。

### 5.4 Pareto，而不是加权总分

最终报告同时给 (quality, cost) 两维：

- 只保留非支配动作；
- 在 Pareto 前沿上取膝盖；
- 不用拍脑袋权重把质量和成本混成一个数。

### 5.5 BOCPD 与异常

- 对每层增益序列做 BOCPD；
- 检测到变点 ⇒ 旧先验降权、探索率上调、必要时重开该层；
- 平稳但低增益 ⇒ 允许停，而不是继续烧钱。

### 5.6 安全盾

SafetyShield 在执行前检查依赖/契约/预算/层状态；高风险动作直接拒绝；拒绝原因写进 trace，不静默。

---

## 6. 合并：闭环怎么跑

    1. Monitor：读层状态与预算
    2. Analyze：novelty/coverage/conflict/closure 四类旗标
    3. Plan：候选动作 → EVOI → MPC → Pareto
    4. 执行前过安全盾
    5. 执行后先验契约，再记账
    6. 结果写回 EML；下一轮只读先验

**记忆与答案的隔离**：EML 的出口只有 scheduler_priors()（数值）；答案文本不进入调度器；调度器也不把内容写回 EML 的语义层，只写 outcome。

---

## 7. 学科融合与创新点

| 学科 | 借用的概念 | 落在哪 |
|---|---|---|
| 控制论 | MPC、可观测性、安全盾 | 调度 |
| 自主计算 | MAPE-K 闭环 | 调度 |
| 强化学习 | 上下文 bandit、信用分配、受控探索 | 调度 + EML |
| 信息论 | EVOI、MDL、熵、Heaps | 调度 + 0 层 |
| 认知科学 | CLS（海马/皮层）、ACT-R 激活、双过程、元认知 | EML + all |
| 认识论 | AGM 修正、可击败推理、Dung、Toulmin/IBIS | EML + both |
| 数据库 | 事件溯源、双时态、provenance | EML |
| 组织理论 | RACI、契约网、责任边界 | 四层契约 |
| 安全工程 | STPA、pre-mortem、red team | all |
| 因果推断 | 反事实回放、do 干预 | 调度评估 |

**创新点**：

1. **契约驱动三平面**：层职责从注释变成可执行闸门；越权直接 ContractViolation。
2. **双时态 EML**：能回答“当时信什么”，保留 defeated 行；不是覆盖式 JSONL。
3. **EVOI-MPC 调度**：按信息价值选层，Pareto 保留质量/成本两维。
4. **责任感知记忆**：EML 只输出数值先验，结构上切断“记忆污染答案”。
5. **真实 packed 反事实回放**：不用重跑 API，就能用历史 36 份产物校准先验。

---

## 8. 参考实现

    dgtf_engine/dgtf_v2/
      contracts.py     # 四层契约 + LayerState/Budget/LayerResult + validate_result
      memory.py        # 双时态 EML + BM25/RRF/MMR + AGM/TMS + 巩固/遗忘/先验
      scheduler.py     # MAPE-K + EVOI + MPC + 安全盾 + credit
      orchestrator.py  # 确定性四层 mock + 端到端
      replay.py        # 真实 outputs/*.packed.json 回放
      tests.py         # 41 项判据

运行：

    python dgtf_engine/dgtf_v2/tests.py
    python -m dgtf_v2.replay --limit 5

参考实现是**设计验证器**，不是生产替换：它不调 LLM、不写 outputs、不改 V1 引擎。

> 2026-10-19：Phase 1–4 已落 V1.24.0——影子建议、EML 双写、契约 warn；takeover 可 opt-in 接管串行初始排程，层内仍是 V1。

回放 20 份真实 packed 的结果（证据 audits/v2_replay_20.json）：

- 20 份 / 5 种 route；16 个层-圈先验；
- 平均质量读数 0.5055（历史口径，不等同新跑质量）；
- V2 策略给出 7 步轨迹（0:r1 → 1:r1 ×2 → 0:r2 → both:r1 ×2 → all:r1），最终闭合；
- 记忆事件 113 条（procedural 61 / semantic 52），先验不含内容。

---

## 9. 接入 V1 的迁移路线

### Phase 0 · 影子回放（零风险）

用 replay.py 读历史 packed，生成先验；对比“V2 会选的动作”与“V1 实际动作”；不改生产，不花钱。

### Phase 1 · 调度影子（feature flag）

V1.24 增加 scheduler.v2.enabled=false；开启也只旁路记录建议，不改变执行；记录建议/实际/结果。

### Phase 2 · EML 双写

V1 的 episodes/playbook 继续写；EML v2 同步追加事件（不迁移、不删除）；用 as_of 做审计；先验只读。

### Phase 3 · 契约闸（先告警后拒绝）

adapter 把 View/Pool 映射成 LayerResult；先 warn 越权，统计 1–2 周；再 raise；任何拒绝写 trace。

### Phase 4 · 接管调度

scheduler.v2.enabled=true 且 shadow=false；先只接管层顺序/圈数，层内 prompt 不动；A/B 质量不降、成本 Pareto 不劣；不达标自动回滚 V1 auto_plan。

### Phase 5 · 重写层内机制

按 3.1–3.4 逐层替换；每层独立 feature flag；每层独立判据（契约 + 质量 + 成本）。

2026-10-19 收口：L0-v2 以 archive 只读默认恢复（不裁剪、不注入 prompt）；F2/F3/F4/F5 契约层默认开；F3/F4 四层 full-4 通过；F5 已完成生成+只读审计/novelty，生成机制延期。

---

## 10. 验收协议

| 维度 | 指标 | 通过线 |
|---|---|---|
| 契约 | ContractViolation | 0（生产） |
| 质量 | coverage / tri / closure 完整度 | 不低于 V1 基线 |
| 成本 | calls / tokens | Pareto 不劣；允许 ±10% 换质量 |
| 校准 | 三态 ECE / 弃权率 | 不恶化 |
| 记忆 | 先验不含内容 | 100% 测试通过 |
| 可回放 | 同 packed 输入 → 同决策 | 确定性（固定 seed） |
| 安全 | 非法动作被拒 | 100% |

---

## 11. 风险与红线

- **契约过严**：真实 LLM 产物可能缺字段；adapter 先宽容映射，契约闸先告警后拒绝。
- **冷启动**：36 份 packed 样本少；先验只做弱先验，探索 bonus 保底。
- **模型失配**：MPC 的模拟不是真实引擎；安全盾 + 事后 credit 修正。
- **记忆污染**：结构上只给数值先验；测试检查先验不含答案文本。
- **双时态成本**：事件只增；需要定期归档/压缩，但不删历史。
- **不删行**：defeated/stale 仍保留；召回排除，审计可见。

---

## 12. 参考（按机制）

- e-process / 置信序列：Ramdas et al., 2023；Howard et al., 2021
- 保形预测：Vovk et al., 2005；Angelopoulos & Bates, 2021
- BOCPD：Adams & MacKay, 2007
- Dung 论证：Dung, 1995；Baroni et al., 2018
- AGM 信念修正：Alchourrón, Gärdenfors & Makinson, 1985
- MAPE-K：Kephart & Chess, 2003
- MPC：Rawlings, Mayne & Diehl, 2017
- 上下文 bandit / Thompson：Chapelle & Li, 2011
- CLS：McClelland, McNaughton & O'Reilly, 1995
- ACT-R：Anderson et al., 2004
- Generative Agents 的 recency/importance：Park et al., 2023
- Heaps 定律：Heaps, 1978
- MDL：Rissanen, 1978
- IBIS：Rittel & Webber, 1973；Toulmin, 1958
- STPA：Leveson, 2011
- RACI：组织治理通用实践

---

## 13. 结论

V2 的核心不是“更多机制”，而是**把职责变成契约、把记忆变成双时态事件、把调度变成可解释的控制器**。

- 0 层负责发散，用质量-多样性而不是分数；
- 1 层负责收敛，用序贯检验/保形弃权而不是硬答；
- both 负责辩证，用论证场而不是调和；
- all 负责闭合，用责任/风险/来源而不是总结；
- EML 负责记住并修正，但只给调度数值先验；
- 调度负责在约束下选择，用 EVOI/MPC/Pareto，不用拍脑袋权重。

这四件事合起来，才是整体架构的重设计；单改任何一层，都会被另外三层拉回旧行为。

---

## 10. V2.1.0 历史谱系融合层

V2.1.0 在三平面之上增加一层**只读 provenance**：

- 输入：V1.0 → V1.30.4 的 178 个历史快照 + V2.0.0；
- 结构：17 条能力轴（起源版本 / V2 实现 / 测试判据 / native|bridged）；
- 运行时：每次 run 选择 contract-first 或 exploration-first 作业剖面；
- 输出：packed.history_fusion（版本数、readiness、profile、能力轴覆盖）；
- 边界：只写元数据，不生成/改写答案，不修改历史归档。

实现：dgtf_engine/dgtf_v2/history_fusion.py + history_manifest.json；
判据：tests_history_fusion.py（12 项）。

融合层的价值不是“再加一个模块”，而是让 V2 能回答：
**当前能力从 V1 的哪一版来、有没有在演化中丢失、这次跑实际覆盖了哪些。**

