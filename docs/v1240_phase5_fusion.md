# Meta-DGTF-道生三阶模型 Phase 5 · V2 控制面 × 四层执行面融合设计

> **性质**：设计与接入决策记录。本文只定**规则、顺序、门禁、回滚**，不改代码/配置。
> **基线**：`Meta-DGTF-V1.24.0.py`（生产单文件）+ `dgtf_engine/dgtf_v2/`（参考内核，判据 41/41）。
> **时点**：2026-10-19。以下结论只引真实产物，不引方案自述：
> `v1240_ab_pilot.md`、`v1240_core_report.md`、`v1240_phase5_l0.md`、
> `audits/core_duty_20.json`、`audits/v2_replay_20.json`、`audits/l0_v2_replay.json`。

---

## 0. 一句话主张与三条红线

**控制面接管「跑哪层 / 几圈 / 停不停」，执行面接管「这一层必须交什么」；两者之间只有四个接口，Phase 5 的接入顺序必须是「先职责、后质量、最后机制」。**

三条红线：

1. **契约/职责闸没过之前，质量与成本读数只作参考，不作放行依据。**
   否则任何 A/B 波动都会被用来解释一个本可以点名的职责缺口。
2. **一次只动一个平面、一层机制。** 控制面变量（takeover）与执行面变量（层 flag）不得同时翻转。
3. **失败、越权、缺项、回滚全部留痕；回滚只关 flag，不删代码/配置/历史。**

---

## 1. 证据基线：每个平面现在能证明什么

### 1.1 控制面：V2 takeover 已证明「排得完、更便宜」

600k、serial、同题 5 对（`v1240_ab_pilot.md`；配置 `configs/方案G-V2接管-pilot.yaml` takeover=true / `configs/方案G-V1-pilot.yaml` takeover=false）：

| 指标 | V2 takeover | V1 auto_plan | 结论 |
|---|---:|---:|---|
| 闭合率 | **5/5** | **0/5**（全部 600k 内没跑完 all；Q3/Q4 连 both 都没跑完） | 排程闭合 V2 全胜 |
| calls 均值 | **85.0** | **111.8** | **−24.0%** |
| tokens 均值 | **531.1k** | **632.4k** | **−16.0%** |
| 研究覆盖均值 | 90%（100/100/100/100/50） | 86%（80/50/100/100/100） | V2 均值高；V1 仅 Q5 更高 |
| 三态均值 | **.633** | **.447** | V2 高 |
| 决策 rubric | 3/3（Q2 boundary 为 0） | 3/3（Q2 boundary 为 0） | 持平 |
| 2M Q1 追加 | 89 calls / 528k / 闭合 | 128 calls / 882k / both 未完成、手动停 | V1 不是预算不够，是排程没轮到 all |

★ 口径修正：`v1240_ab_pilot.md` §观察写「Q1 覆盖/三态 V2 不占优」，但同文表内 Q1 是 **V2 5/5 / .333，V1 4/5 / .400**——覆盖 V2 更高、三态 V1 更高。**本文引用表内明细**；后续报告不要再把这两项写混。

★ 边界说明：5/5 是**排程闭合**，不是 5/5 过契约。takeover 只接管「串行初始排程」，层内仍是 V1（`Meta-DGTF-V1.24.0.py:21695-21725`；`v1240_报告.md` §四）。

### 1.2 执行面：四层职责有结构性缺口，不是模型波动

20 份历史真实 packed 审计（`audits/core_duty_20.json`；`v1240_core_report.md`）：

| 指标 | 数值 |
|---|---:|
| 四层全过 | **2 / 20** |
| 1 层 action_plan 越权 | **18 / 20** |
| all 缺 decision | **4** |
| all 缺 residual_risks | **4** |
| actions 从 1 迁到 all | 18 |
| 0 层核心失败 | 0 |
| both 核心失败 | 0 |

三处根因已经定位到代码，不是 LLM 波动：

1. `_pack_result` 为报告把 1 层 actions 塞进 `views.1` —— **落盘位置错**，行动属于 all；
2. `views.all.actions` 为空，闭合靠 manifest 文本渲染 —— **all 不是结构化产物**；
3. 旧 bridge 只读 `sub_question.citations`，不认 `decidable_product.evidence` —— **证据映射误报**。

源头已改为 `packed.actions` / `packed.not_do` 与 `views.all.actions`，但**新跑端到端验证未完成**：Q2 600k 跑到 12 calls 后约 20 分钟无快照更新，疑似 API 长挂，已手动停（`v1240_core_report.md` §新跑次验证）。因此当前只能确认「源修改编译通过 + tests_core 9/9」，**不能宣布职责缺口已关闭**。

### 1.3 0 层机制：L0-v2 三个变体全部未过闸

`v1240_phase5_l0.md`、`audits/l0_v2_replay.json`：

| 组 | calls | tokens | 覆盖 | 三态 | 判定 |
|---|---:|---:|---|---|---|
| Q2 基线（V2 takeover） | 89 | 584,607 | **4/4** | **1.000** | 对照 |
| L0-v2 v1 硬裁剪 | 90 | 554,805 | 2/6 | .500 | 否 |
| L0-v2 v2 guide 无三态约束 | 90 | 551,826 | 2/2 | .333 | 否 |
| L0-v2 v2 guide 加三态约束 | 89 | 576,285 | 5/6 | .500 | 否 |
| Q1 L0-on vs 基线 | 89 vs 79 | 545,889 vs 477,478 | 5/5 vs 5/5 | .333 vs .333 | 否（calls +12.7% / tokens +14.3%） |

离线回放：10 份真实 0 层产物、467 候选 → 80 精英，novelty .92–.95，档案 4–8 格 / 32。判据 tests_l0 16/16，但**回放不是 A/B，不能替代真实生成质量**。

结论：`actions.l0_v2_curate` 保持 false（引擎默认 `Meta-DGTF-V1.24.0.py:26865-26868`），0 层机制冻结；方案H 配置仅作实验留档（`configs/方案H-L0v2-实验.yaml` 首行自述）。

### 1.4 仓库级门禁能证明什么、不能证明什么

冒烟 266/0、跨档验收 319/0、工程审计 70/0、前端 371/0、变异体 3/3、内核 24/0、V2 41/41、L0 16/16、核心职责 9/9（`v1240_core_report.md` §职责修复后的门禁；`v1240_报告.md` §七）。

这些证明**代码改动能编译、判据没有退化、内核行为可复现**；它们**不证明**真实跑次的四层产物合规。Phase 5 的放行证据必须来自「新跑 packed + bench」，不能拿仓库门禁代替。

---

## 2. 两个平面怎么组合：四个接口、七条规则

### 2.1 接口（保持单向，禁止互相越界）

| # | 接口 | 方向 | 现有实现 | 硬规则 |
|---|---|---|---|---|
| I1 | dispatch plan | 控制面 → 执行面 | `V2Shadow.propose()` → `rounds_plan` / `_dispatch_plan`（`Meta-DGTF-V1.24.0.py:21695-21725`） | 提案必须覆盖全部 route，否则整体回退 V1，不混跑；只接管 `mode=serial` |
| I2 | 层状态读数 | 执行面 → 控制面 | `_initial_state` / `_state_from_packed`（`dgtf_engine/dgtf_v2/shadow.py:46-118`） | 只读结构计数与质量数，不读答案正文；**done 必须以层完成状态为准**（当前实现见 §2.3 S3） |
| I3 | 契约/职责报告 | 执行面 → 控制面/报告 | `V2MemoryBridge.contract_report`（`bridge.py:202-217`）+ `core_duty.audit_packed`（`core_duty.py:89-177`） | 必须分「修复前 / 修复后」两栏；只有修复前干净才算过 |
| I4 | credit / 先验 | 执行面 → EML → 控制面 | `record_packed`（`bridge.py:57-106`）→ `scheduler_priors`（`scheduler.py:151-158`） | 先 validate/audit 再 credit；outcome 必须带 contract_ok/core_ok；先验只数值 |

### 2.2 组合规则

- **R1 控制面不产文本，执行面不选层。** 调度器只拿到数值先验（`docs/Meta-DGTF-道生三阶模型-V2-三平面架构.md` §2、§4.6）；层内机制只拿到 rounds/预算/上游产物。
- **R2 依赖以契约为单一来源。** `contracts.legal_actions` 已写死：1 至少吃 1 圈 0、both 要 0/1 done、all 要 both done（`contracts.py:226-248`）。`Scheduler._legal` 目前**复制了一份同样逻辑**（`scheduler.py:191-211`）——语义当前一致，但两套实现会漂移；F1 必须收敛到一处（控制面调用契约函数，或反过来）。
- **R3 credit 必须晚于校验。** 当前 `V2Shadow.finish` 的顺序是：at_end → **写 EML outcome**（`shadow.py:169-174`）→ priors → core 审计 → 契约（`shadow.py:181-186`）；且 `record_packed` 的 outcome **无条件 success=True**（`bridge.py:94-99`）。后果：越权产物会被当作成功样本学进先验。F1 必须先校验再 credit，或给 outcome 加 `contract_ok/core_ok` 并由先验读取。
- **R4 closure 定义统一。** 调度器判断「可闭合」必须等于 `validate_result(all)` 通过；当前 `_state_from_packed` 的 closure 是 stub：`decision_actions>0 且 not_do>0` 就造一个假闭包（`shadow.py:103-118`）；`Scheduler.quality` 的 closure 只查 5 个键且仅用于 mock/replay（`scheduler.py:291-303`）。**生产质量读数只认 bench，不认 mock quality。**
- **R5 一次只翻一个变量。** takeover 与层 flag 正交；A/B 期间 route、预算、模型、serial 全部固定。takeover 的对照变量只允许在控制面 A/B 里翻。
- **R6 记忆与答案隔离。** EML 出口只有 `scheduler_priors()`（数值）；答案文本不进调度器；`contains_content=False` 由测试守（`docs/Meta-DGTF-道生三阶模型-V2-三平面架构.md` §4.6）。
- **R7 repair 只做兼容，不作通过证据。** `repair_packed` 是「搬已有内容 + 换字段名」，明确不造新句子（`core_duty.py:34-86`）。审计必须用**修复前** overreach（`core_duty.py:89-103`）；新跑必须源干净。

### 2.3 当前实现里必须先补的六个接缝（不改层内机制）

这六项是「融合」真正的工作量，不补就会让 Phase 5 的 A/B 数字失真：

| # | 接缝 | 现状 | 后果 | F1 处置 |
|---|---|---|---|---|
| S1 | credit 早于契约 | `shadow.py:169-186`；`bridge.py:94-99` | 越权/缺项被当成功样本 | 先 validate+audit，再 record；outcome 带 contract_ok/core_ok |
| S2 | 契约报告先 repair 再 validate | `bridge.py:112-115` | 18/20 的 1 层越权在契约报告里可能「通过」 | 双栏输出 `violations_raw` / `violations_repaired`；只有 raw=0 才过 |
| S3 | done 判定 = view 存在 | `shadow.py:82-101` | 被截断层若已有 view 会被当 done，预测「可闭合」 | 读 packed 层完成状态 / `pending_layers` / stop reason |
| S4 | closure stub | `shadow.py:103-118` | `at_end` 的「可闭合」不是契约闭合 | closure_ready = `validate_result(all)` 通过 |
| S5 | 每层成本是摊派 | `bridge.py:96-99`：`llm_tokens // len(route)` | 层级 Pareto 与 EML 先验 cost 不可信 | 用层完成时的累计差记真实 calls/tokens |
| S6 | exit_tests / quality_metrics 无执行出口 | `contracts.py` 的 `LAYER_CONTRACTS` 声明了这两组字段；`validate_result` 不评估 | 契约写着「何时算完成」「怎么量」，但没人执行 | G3/G5 补读数出口，或逐条写明豁免理由 |

★ 注意 S2 与 R7 的关系：契约闸看到的是**修复后形态**，core_duty 看到的是**修复前越权**——所以两者不能互相替代，必须并列成 G1 / G2 两道门。

---

## 3. 每层先接什么：结构 → 读数 → 机制

**接入深度固定三档，不许跳档**：

1. **先接结构**：把 V1 现有产物映射成该层契约允许的 `LayerResult`，跑 `validate_result`；缺字段就补映射/改源头，不补空话。
2. **再接读数**：把契约里的 `quality_metrics` / `exit_tests` 变成 packed/bench 里能读到的字段。
3. **最后接机制**：只有前两档在真实新跑上稳定，才允许开该层的 Phase 5 flag。

| 层 | 先接：契约产物（结构） | 再接：读数出口 | 最后：机制 | 当前状态 |
|---|---|---|---|---|
| **0 修行** | aspect_map / suspensions / probe_queue / novelty_curve；禁 answer/decision | aspect_coverage / novelty_rate / suspension_quality（**均无出口**；novelty_curve 目前恒 `[]`，`bridge.py:132-135`） | L0-v2 MAP-Elites/novelty/Heaps/Thompson | 契约：0/20 核心失败；读数缺；机制**冻结** |
| **1 研究** | answer_set / abstentions / coverage / citations / debt_set；禁 closure/action_plan/final_decision | coverage / tri_state / citation_precision（coverage+tri 已有；citation_precision 无出口） | 三态 / 序贯检验 / 保形弃权 | 落盘已修但新跑未验证；历史 18/20 越权 |
| **both 对撞** | synthesis / argument_graph（defeated+undecided）/ tension_set / defeated_claims；禁 final_decision/action_plan/删败方 | conflict_resolution / argument_groundedness / synthesis_novelty（**均无出口**） | Dung / Toulmin / red team | 桥接是拼的；core 0/20 失败只说明「有综合/张力」 |
| **all 元** | decision / actions / not_do / residual_risks / provenance / confidence；动作必须有 owner/deadline/acceptance/rollback | closure_completeness / action_quality / risk_transparency（decision_actions/not_do 有质量字段；其余无出口） | RACI / pre-mortem / STPA / 决策理论 | 历史 2/20 全过；4+4 缺项；actions 从 1 迁入；新跑未验证 |

### 3.1 0 层：只接契约，不接机制

- **现状**：`bridge` 把 `candidates+amps` 映射成 aspect_map、`probes` 映射成 probe_queue、`suspensions` 映射成 suspensions；`novelty_curve` 恒空。`core_duty` 判定靠「aspects>0 且 (probes>0 或 suspensions>0)」，20 份历史 0 失败。
- **先接什么**：保持契约映射与审计；把 novelty_curve / 悬置质量接成读数。**不接 L0-v2**（§6.3 重启条件）。
- **为什么冻结**：L0-v2 三种变体均未过 Q2 门槛（§1.3）；且「给 0 层加 novelty 方向」不能保证研究覆盖/三态，novelty 目标与 research coverage 未对齐（`v1240_phase5_l0.md` §最终判定）。

### 3.2 1 层：契约收口优先于机制重写

- **现状**：`bridge` 按真实产物 `decidable_product`（answer + evidence）映射，而不是逐 sub_question 硬找 citations（`bridge.py:137-165`）；`core_duty` 把 `evidence` 回退为 `citations`（只换字段，不造证据）。
- **先接什么**：`answer_set` 三态标签、coverage∈[0,1]、decidable 必须带 citations；**1 层不得出现 actions/not_do**（源头 `_pack_result` 已上移，但要新跑证明）。读数沿用 `packed.quality.coverage` / `tri_ratio`。
- **为什么不能先改机制**：1 层的输出是 both/all 的输入；在 1 层越权未清零前重写 1 层算法，both/all 的读数会同时被「1 的新算法」和「1 的旧落盘」污染（F3 排在 F2 之后，理由见 §6.1）。

### 3.3 both 层：先要原生论证图，再谈机制

- **现状最弱**：`bridge` 的 argument_graph 是**拼出来的**——`synthesis = manifest/collision`、`defeated = adjudications`、`undecided = threads`（`bridge.py:166-174`）；`validate_result` 只要求两个键存在且 synthesis 非空（`contracts.py:204-209`）。
- **结论**：契约**形式通过 ≠ 语义通过**。20 份历史 both 0 核心失败，只能说明「有综合/张力」，不能说明「论证图是真的」。
- **先接什么**：让 V1 产物真正输出 defeated/undecided（或明确标注这是桥接合成，不算原生）；接 conflict_resolution 读数；在此之前 both 机制不启动。

### 3.4 all 层：闭合必须结构化，且 repair 不算过

- **现状**：`bridge` 读 `views.all.actions`，动作字段映射 `owner_role→owner`、`deadline_hint→deadline`、`fallback→rollback`（只换名，`bridge.py:176-196`）；`provenance` 缺省 `["v1:packed"]`、`confidence` 缺省 `tri_ratio`。
- **历史 4 份缺 decision/residual 的真相**：集中在**没有产出 all 的跑次**（预算/裁层），不是模型没写（`v1240_core_report.md` §20 份结果说明）。takeover 解决了「跑得到 all」，但没解决「all 交得对」。
- **先接什么**：新跑必须源头上六件套齐；动作四字段 100%；`not_do`/`residual_risks`/`provenance` 非空；**不得用 `repair_packed` 补齐后的结果宣告通过**。
- **读数**：closure_completeness（新加）、action_quality、risk_transparency；bench 的 decision rubric 继续用。

---

## 4. core_gate 顺序：七道门，前一道不过，后一道的数不作数

core_gate 是本设计定义的**四层核心职责闸序列**（当前只有 G1/G2 部分落地，G3–G7 需要补接线或流程）：

| 门 | 只回答一个问题 | 检查方式 | 现在在哪 | 通过线 | 不过时 |
|---|---|---|---|---|---|
| **G0 证据** | 这是真实新跑吗？ | run_id / route / packed / 非 mock / 非回放；API 正常 | 人工+日志 | 真实 packed + bench | 标「证据缺失」，**不判通过也不判失败** |
| **G1 结构** | 每层交的是契约允许的产物吗？ | `validate_result`（**修复前原始产物**）；contract_gate=raise 挂影子 | `bridge.contract_report`（默认 warn） | 逐层 0 violations | 停该层机制，不进 G2 |
| **G2 职责** | 有没有越权/缺项？ | `core_duty.audit_packed`：overreach=0、gaps=0（route 内层） | `packed.v2_shadow.core` | 逐层 0/0 | 停 Phase 5，先修落盘 |
| **G3 质量** | 有没有损害交付质量？ | bench coverage / tri / decision rubric + 层级读数 | `bench/bench_report.py`（离线） | §5.2 | 回滚该层 flag |
| **G4 成本** | 值不值？ | calls/tokens Pareto + ±10% 规则 | bench + packed | §5.3 | 回滚 |
| **G5 闭合** | all 真的闭合了吗？ | 六件套 + 动作四字段 + not_do/residual/provenance + `exit_tests` | contract + bench | 全部非空且合法 | 不算闭合；闭合率不计 |
| **G6 复现** | 同输入同决策吗？ | replay / tests 固定 seed；packed→决策 | `dgtf_engine/dgtf_v2/replay.py`、`tests.py` 41/41 | 确定 | 冻结 flag |
| **G7 回滚** | 关掉 flag 能逐字回基线吗？ | flag off 跑同题，对比 route/order/calls | 方案G 配置 + A/B | 行为回基线 | 不许改默认值 |

### 4.1 为什么必须是这个顺序

- **G1 在 G3 之前**：契约不完整的产物，其 coverage/tri 数字没有可比性。旧 bridge 的「误报 1 层无引用」就是例子——测量口径错了，后面所有质量比较都白做。
- **G2 在 G3 之前**：18/20 的 1 层越权是落盘错位，不是模型差；不先修这个，A/B 的差异里混着「越权产物被下游忽略」的效应，无法归因。
- **G5 在 G3/G4 之后**：闭合是交付物；只有质量和成本都站得住，闭合才有意义。反过来，闭合率也不能拿来掩盖 G1/G2（V2 5/5 闭合 ≠ 5/5 过契约）。
- **G6/G7 是放行前置**：不能复现的机制、不能回滚的机制，不允许改默认值。

### 4.2 当前缺口（F1 要补的）

1. G1 只在影子里 raise，引擎兜住异常、**不阻断 V1**（`v1240_报告.md` §三）；生产契约闸仍是 warn。
2. G2 只有包审计，没有滚动 ok-rate；20 份历史是静态样本，不能当新跑通过证据。
3. G3/G4 靠 bench 离线算，未进 packed 的自动门。
4. G5 的 `exit_tests` 没有执行出口（S6），all 的「高旗标处理或显式接受」目前无人检查。
5. G6 只在 tests 层，不是逐跑门；G7 还没做过回滚演练。

---

## 5. 质量 / 成本门禁

### 5.1 基线固定

| 项 | 规定 | 原因 |
|---|---|---|
| 对照基线 | **V2 takeover**（`configs/方案G-V2接管-pilot.yaml` 600k 筛选；`configs/方案G-V2接管.yaml` 2M 正式） | 执行面 A/B 必须只隔离层变化；拿 V1 auto 当对照会把控制面差异混进来 |
| V1 auto 的用途 | 只用于控制面 A/B（已完成：5/5 vs 0/5） | 不再混用 |
| 固定条件 | 同题、同模型、同预算、serial、route 恒为 `0,1,both,all` | 变量唯一 |
| 筛选样本 | 5 题（Q1–Q5，沿用 pilot） | 与已有证据同口径 |
| 正式样本 | 2M ≥2 题；改默认值需 n≥10、两批独立窗口 | pilot n=5 无统计显著性（`v1240_ab_pilot.md` §局限） |

### 5.2 质量门

| 检查 | 通过线 | 依据/先例 |
|---|---|---|
| 回归题 Q2 | coverage **4/4** 且 tri **≥ .8** | L0 重启门槛（`v1240_phase5_l0.md` 末段）；Q2 是覆盖/三态最敏感题（基线 4/4 / 1.000） |
| 单题 coverage | 不低于基线；掉 ≥1 个可判定子问题 = 黄，关键题 = 红 | L0 Q2 4/4→2/6 判红 |
| 单题 tri | 不低于基线 −0.05；掉 ≥0.15 = 红 | L0 1.000→.500 判红 |
| 5 题均值 | coverage ≥基线；tri ≥基线 −0.05；decision rubric 不低于基线（Q2 boundary 除外） | pilot 表 |
| 1 层 | decidable 100% 带 citations；三态合法；coverage∈[0,1] | `contracts.validate_result` |
| both 层 | defeated/undecided 显式；synthesis 引用双方；无 final_decision/action_plan | `contracts` + G5 |
| all 层 | 六件套 100%；动作四字段 100%；not_do/residual/provenance 非空；decision rubric 3/3（非 boundary） | `contracts` + bench |
| 0 层 | aspect_map 非空；probe 或 suspension ≥1；无 answer/decision | `core_duty` |

### 5.3 成本门

- 5 题均值 calls/tokens ≤ 基线 **+5%**；
- 单题任一 > 基线 **+10%** 时，必须有质量收益（coverage 多 1 个子问题 **或** tri +0.10，且其余主指标不降），否则判红；
- Pareto：不得被基线支配；同质量下成本必须更低才算改善；
- **先例即判据**：L0 v1 Q1 calls +12.7% / tokens +14.3% 无质量收益 → 红；Q2 成本 −5% 但覆盖 4/4→2/6 → 红。两个方向都算「没通过」。
- 不允许用「boundary 题 decision=0」调整质量均值口径；boundary 单列。

### 5.4 放行与样本量

1. 层机制 flag false→true：G0–G7 全过 + 5 题筛选 + 2M ≥2 题 + 回滚演练。
2. 改生产默认值：n≥10、两批独立窗口、报告归档；不满足就保持 opt-in。
3. 门禁顺序固定：**G1/G2/G5 硬门先判；G3/G4 软门后判。硬门红不看 A/B 数字。**

---

## 6. 接入顺序与 1/both/all 的前置条件

### 6.1 顺序

| 阶段 | 内容 | 现在能否开始 | 关键依据 |
|---|---|---|---|
| **F0 现状冻结** | control plane 用 takeover 推荐 preset；contract warn；l0 flag false；主配置 takeover=false 不动 | 已在此状态 | `v1240_报告.md` §八结论 |
| **F1 职责收口** | 四层契约/职责/闭合定义/credit 顺序 + 新跑验证；**不改层内机制** | **可立即开始（编译/判据）**；新跑验证受 API 窗口限制 | §1.2、§2.3 |
| **F2 all 层机制** | 闭合结构化、RACI/pre-mortem/STPA | **已完成**：四层 5/5，成本 5/5 在 600k | all_v2 默认 true |
| **F3 1 层机制** | AnswerSet 契约（三态/coverage/citations） | **已完成**：分层 5/5 + full-4 204700 | one_v2 默认 true |
| **F4 both 层机制** | 原生论证图/defeated/undecided | **已完成**：分层 6/6 + full-4 204724 | both_v2 默认 true |
| **F5 0 层重启** | 生成 + 只读审计/novelty | **已完成（V2.0.0）** | zero_v2 默认 true；F5 生成已接，保留审计 |

**为什么 all 排在 1 前面**：all 的契约**禁止引入新内容**，它的失败可归因于「闭合没接住」，而不是「上游生成变了」；1 层一改，both/all 的输入同时变，后续读数就分不清是 1 变了还是 all 没接住。先把「闭合」这把尺子做稳，再改上游生成，是唯一能把 A/B 变量收敛到一条的顺序。

### 6.2 两类共同前置（1/both/all 都必须满足）

| # | 前置 | 通过线 | 当前状态 |
|---|---|---|---|
| P1 | 真实新跑证据 | 5 题 × 真实 API 跑，packed 带 run_id；非回放、非 mock | **已满足**：F2/F3/F4/F5 均有真实跑 |
| P2 | 源干净契约 | `violations_raw = 0`（不依赖 repair） | 历史 18/20 不达标；源修改待新跑验证 |
| P3 | 职责审计 | `core_duty`：该层 overreach=0、gaps=0，5 跑滚动 | 待 P1 |
| P4 | 读数出口 | 该层 `quality_metrics` 与 per-layer calls/tokens 可读 | 缺（S5/S6） |
| P5 | 基线固定 | 同 route / 同预算 / takeover=true / serial | 可立即固定 |
| P6 | 回滚演练 | flag off 行为回基线（G7） | **已做**：F3/F4 flag off 通过；F2/F5 可回退 |
| P7 | 单变量 | 同期不翻 takeover / 其它层 / route / EML | 流程约束 |

### 6.3 各层专属前置

**1 层（研究）**
- 1 层不得出现 actions/not_do（源头修复的新跑证明）；
- decidable 100% 带 citations（`decidable_product.evidence` 或逐条 citation 二选一，bridge 已按真实产物映射）；
- 三态标签只能是 decidable/partial/undecidable；coverage∈[0,1]；
- both/all 的输入不因 1 的变化而失去可比性 → 1 的机制 A/B 必须在 all 闭合门稳定之后。

**both 层（对撞）**
- 原生 argument_graph（defeated/undecided 是产物，不是 bridge 从 adjudications/threads 拼的）；若短期做不到，必须在报告里标「桥接语义，形式通过」，**不得据此开机制**；
- 无 final_decision / action_plan / 删败方；
- 冲突标签完整、综合引用双方（G5 的内容级检查，当前无自动出口，需人工/新脚本）；
- V2 takeover 已保证 both 能跑完（V1 曾在 Q3/Q4 both 截断），但「跑完」不等于「论证图原生」。

**all 层（元）**
- 新跑六件套齐：decision / actions / not_do / residual_risks / provenance / confidence；
- 动作四字段 100%：owner / deadline / acceptance / rollback；
- `not_do` 非空、`residual_risks` 非空、`provenance` 非空；
- 不得用 repair 后的 packed 宣告通过；4 份历史缺项是「没产出 all」，不是「模型没写」；
- 闭合率只统计「过 G5 的闭合」，不是「takeover 跑完了」的 5/5。

**0 层（重启条件，F5）**
1. 换生成机制：候选显式覆盖子问题/极性，与 research 分解对齐；不再用「后置过滤/提示注入」；
2. novelty 目标与 research coverage/三态对齐；
3. Q2 达到 **4/4 + ≥.8 三态**，再扩 5 题；
4. 可选换 embedding novelty（若成本允许）；
5. 只在 F1–F4 完成、且 0 层单层 A/B n≥5 通过后，才允许把 `actions.l0_v2_curate` 打开；**调 quota / 换 prompt 不算重启**（`v1240_phase5_l0.md` §下一步）。

### 6.4 F1 的具体交付（代码改动，不在本文实施）

1. `shadow.finish`：contract/core 校验前移，先校验后 credit（S1）；
2. `contract_report`：双栏 raw / repaired（S2）；
3. `_state_from_packed`：done 读层完成状态，非 view 存在（S3）；
4. closure_ready 改为 `validate_result(all)`（S4）；
5. 每层真实 calls/tokens（S5）；
6. `exit_tests` / `quality_metrics` 接出口或逐条豁免（S6）；
7. 依赖判定收敛到 `contracts.legal_actions`（R2）；
8. outcome 带 `contract_ok/core_ok`，先验只读通过样本（R3）。

Exit：5 题新跑 `violations_raw=0`、`overreach=0`、`gaps=0`、all 六件套 100%；否则不进 F2。

---

## 7. 回滚条件与回滚方法

### 7.1 回滚矩阵

| # | 触发 | 维度 | 动作 | 证据 |
|---|---|---|---|---|
| C1 | G1 raise 下任一 violation ≥1（该层） | 执行面 | 该层 flag → false | packed.v2_shadow.contracts |
| C2 | G2 新跑 overreach ≥1 或 gap ≥1 | 执行面 | 冻结 Phase 5；当前层 flag off；查落盘 | packed.v2_shadow.core |
| C3 | 回归题 Q2 coverage <4/4 或 tri <.8 | 质量 | 该层 flag off | bench |
| C4 | 单题 coverage 掉 ≥1 且 tri 掉 ≥0.15 | 质量 | 该层 flag off | bench（L0 先例） |
| C5 | calls/tokens 均值 >+5%，或单题 >+10% 无质量收益 | 成本 | 该层 flag off | bench |
| C6 | 闭合率低于 takeover 基线（5/5） | 闭合 | 下游层 flag off；若未开任何层 flag → 查控制面 | packed + bench |
| C7 | `v2_takeover.applied=false` 连续 ≥2 次 / 提案不覆盖 route | 控制面 | `takeover=false`，回 V1 auto_plan | packed.v2_takeover |
| C8 | priors 含内容或 n 异常（0/暴增） | 记忆 | 关 EML 双写，查 v2_events.jsonl | 测试 + 事件库 |
| C9 | 同 packed → 不同决策（G6 红） | 复现 | 冻结所有 flag | replay / tests |
| C10 | API 长挂、无新 packed | 证据 | **标「证据缺失」，不判通过/失败**；不调参 | 日志 |

★ C7 的已有实现是「自动回退但静默」：提案不覆盖 route 时只写 `v2_takeover.applied=false`，控制台不打印（`Meta-DGTF-V1.24.0.py:21722-21725`）。回滚条件要求补一条显式告警，否则「回退了」和「没接管」在终端上无法区分。

### 7.2 回滚方法（统一）

1. **只改配置 flag**，不改代码、不删配置、不删历史产物；
2. 回滚记录必须含：run_id 列表、触发门、当时读数、回滚时间、重入条件；
3. 被回滚的实验配置保留（如 `configs/方案H-L0v2-实验.yaml` 首行标注「仅供复现」的写法）；
4. **重入不是「再试一次」**：必须重新跑 G0–G7，样本量与回滚前相同；
5. 每层一个独立 flag；`actions.<layer>_v2` 已默认 true，可独立关闭回滚；不得复用 `actions.l0_v2_curate` 代替层 flag。

### 7.3 不用 A/B 波动掩盖职责缺口的四个判例

1. **L0 Q1「覆盖持平」不等于通过**：calls +12.7% / tokens +14.3% 且无质量收益，按成本门判红——不能拿「质量持平」当免死金牌。
2. **L0 Q2「覆盖掉一半」不能归因波动**：同题同配置同基线，4/4→2/6、1.000→.500；先例即 C4 阈值来源。
3. **18/20 的 1 层越权不是模型波动**：是 `_pack_result` 的落盘位置（`v1240_core_report.md` §问题）；凡把职责缺口说成「模型有时写不好」，先看审计口径。
4. **4/20 all 缺项不是 all 偷懒**：是没产出 all（预算/截断）——这正说明 takeover 解决的是「跑得到」，契约解决的是「交得对」，两者不能互相替功。

---

## 8. 观测指标

### 8.1 逐跑（packed 内，已有）

| 指标 | 出口 | 告警线 | 用途 |
|---|---|---|---|
| `v2_takeover.applied/order/rounds/why` | packed | applied=false 连续 2 次 | 控制面回滚 C7 |
| `v2_shadow.at_start.agreement` | packed | 连续 3 次与 V1 首层不一致 | 排程合理性 |
| `v2_shadow.at_end.v2_next/reason` | packed | 四层完成却仍选层 | 停止判据 |
| `v2_shadow.contracts.gate/violations/checked/ok` | packed | 任一 violation | G1 |
| `v2_shadow.core.layers/gaps/overreach/repairs/ok` | packed | overreach/gap ≥1 | G2 |
| `v2_shadow.priors`（n） | packed | n=0 或异常暴增 | 先验质量 |
| `quality.coverage/tri_ratio/answered/answerable_total` | packed | §5.2 | G3 |
| `quality.decision_actions/not_do` | packed | 0 | G5 |
| `llm_calls/llm_tokens`、`route/rounds` | packed | §5.3 | G4 |
| `v2_shadow.hypothetical` | packed | — | **只看，不当质量**（mock） |

### 8.2 批级（bench + audits）

- bench：coverage / tri / decision rubric / calls / tokens（`bench/bench_report.py`、`bench/bench_score.py`）；
- 审计：`audits/core_duty_20.json` 的历史口径（2/20、18/20、4+4）只作回归基线，**不作新跑证据**；
- 「新跑 ok-rate」= 最近 5 跑中 G1/G2/G5 全过的比例，建议落 `audits/phase5_fusion_rollup.json`（**待建**）。

### 8.3 需要补的读数出口

| 指标 | 现状 | 补法 |
|---|---|---|
| per-layer calls/tokens | 摊派（S5） | 层完成时累计差 |
| violations_raw vs repaired | 只有修复后（S2） | contract_report 双栏 |
| closure_completeness / exit_tests | 无（S6） | validate 后置检查或独立函数 |
| both 的冲突标签完整率 / 综合引用双方 | 无 | 内容级检查（新脚本） |
| 校准（三态 ECE / 弃权率） | 无 | arch doc §10 验收项，Phase 5 前补 |
| novelty_curve | 恒 `[]` | 0 层重启时再接，冻结期不补 |

### 8.4 滚动窗口

- 固定 **5 跑滑窗**：契约 ok 数、职责 ok 数、闭合过 G5 数、calls/tokens 均值、回归题 quality；
- 每批 A/B 报告必须含：run_id 清单、配置 diff（一行 flag）、bench 表、audits 文件、回滚演练结果；
- 读数缺出口时写「未测」，不写 0（0 会被当「测了且为零」）。

---

## 9. 明确不做什么

| # | 不做 | 理由（证据） | 什么时候可以重开 |
|---|---|---|---|
| N1 | **不接 L0-v2、不在 0 层调 quota/prompt** | v1/v2 三个变体均未过 Q2（4/4/1.0 基线；2/6/.5、2/2/.333、5/6/.5） | 满足 §6.3 的 0 层重启五条 |
| N2 | **不用 A/B 波动解释职责缺口** | 18/20 越权是落盘、4/20 缺项是没产出 all；不是模型波动 | G1/G2 全绿后才有资格谈波动 |
| N3 | **不同时翻控制面与执行面** | 一次只动一个平面，否则 takeover 与层机制不可归因 | 单变量 A/B 流程建立后 |
| N4 | **不做动态重规划 / 逐圈 replan** | takeover 仍是 initial serial（`v1240_报告.md` §四） | F1–F4 完成、G6 复现过 |
| N5 | **不为质量调 route / 砍层** | route 是 A/B 的固定条件；砍层会把「没跑」洗成「不差」 | 不在本设计范围 |
| N6 | **不把 mock hypothetical / 回放 0.5055 当新跑质量** | `shadow.py` 已标 mock；`audits/v2_replay_20.json` 的 quality_mean 是历史口径 | 永不作为放行依据 |
| N7 | **不用 repair 后的 packed 当职责通过证据** | repair 只搬内容/换字段；审计用修复前 overreach | 永不 |
| N8 | **不把契约形式通过当语义通过** | both 的 argument_graph 是桥接拼的（`bridge.py:166-174`）；all 的 provenance 有缺省兜底 | both 出原生论证图后 |
| N9 | **不让 EML 内容进答案/调度** | priors 只数值；contains_content=False 由测试守 | 永不 |
| N10 | **不删机制/配置/失败记录；回滚不删代码** | 项目红线「失败留痕」；方案H 保留实验档 | 永不 |
| N11 | **不在 n<5 或未做 2M 正式跑时改默认值** | pilot n=5 无统计显著性 | n≥10 + 两批窗口 |
| N12 | **不把「5/5 闭合」当质量结论** | 5/5 是排程闭合；core_duty 2/20 是契约口径的反例 | G5 通过后重新统计 |
| N13 | **不在 API 长挂时判通过/失败** | 上次 600k Q2 无快照、手动停；证据缺失不是质量信号 | 有新 packed 再判 |

---

## 10. 可执行清单（下一个窗口）

### 10.1 现在就能做（不依赖 API）

```bash
python dgtf_engine/dgtf_v2/tests.py        # 期望 41/41
python dgtf_engine/dgtf_v2/tests_core.py   # 期望 9/9
python dgtf_engine/dgtf_v2/tests_l0.py     # 期望 16/16（0 层冻结，仅回归）
python -m dgtf_v2.replay --limit 5
```

- 读 `audits/core_duty_20.json`，按 §7.3 四个判例写进 F1 报告；
- 按 §6.4 列 F1 代码改动清单（S1–S6 + R2/R3），逐项配判据；
- 固定 F2–F4 的 A/B 模板：run_id、配置 diff、bench 表、audits、回滚演练（§8.4）。

### 10.2 需要 API 窗口才能做

1. F1 新跑：`configs/方案G-V2接管-pilot.yaml`（600k，takeover=true）+ `contract_gate: raise`（待 F1 代码就绪），跑 Q1–Q5；
2. 每跑后核 packed：`violations_raw`、`overreach`、`gaps`、all 六件套、`v2_takeover.applied`；
3. 通过后按 F2（all）→ F3（1）→ F4（both）逐层开 flag，每层独立 G0–G7。

### 10.3 放行记录模板

```
层 / 阶段：F? · <layer>
run_id：...
配置 diff：仅 actions.<layer>_v2=false→true
G0 证据：...   G1 契约：raw=0 / repaired=...
G2 职责：overreach=0 / gaps=0   G5 闭合：六件套 ...
G3 质量：Q2=4/4, tri=..., 均值...   G4 成本：calls ..., tokens ...
G6 复现：...   G7 回滚演练：...
结论：放行 / 回滚（写触发门）
```

---

## 11. 结论

- **控制面已经证明自己**：600k 5 对里 takeover 5/5 闭合、V1 0/5；calls −24%、tokens −16%。这是排程层面的结论，不是质量的结论。
- **执行面还没接住**：20 份历史 packed 只有 2 份四层全过；18 份 1 层 actions 错位、4+4 份 all 缺项。根因已定位到落盘与映射，不在模型。
- **0 层机制已完成**：V2.0.0 用问题/研究分解生成 aspect/probe/suspension；不再依赖 L0-v2 三个未过闸变体。
- **Phase 5 已完成**：F1 职责收口 → F2 all → F3 1 → F4 both → F5 0（生成+审计）。
- **门禁顺序固定**：G0 证据 → G1 契约 → G2 职责 → G3 质量 → G4 成本 → G5 闭合 → G6 复现 → G7 回滚；前一道不过，后一道的数不作数。
- **回滚只关 flag**：C1–C10 任一触发即回滚，保留全部证据；重入必须重跑全门。
- 本文只定设计；**没有改任何代码/配置**。F1 的八项代码交付列在 §6.4，落地时按 G0–G7 验收。
