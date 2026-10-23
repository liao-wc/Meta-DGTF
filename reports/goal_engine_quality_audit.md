# 引擎质量审计报告：准确回答 / 高质量决策 / 深度对话推理

> 审计对象：`元DGTF-V1.30.0.py`（__version__=1.30.0，mtime 2026-10-21 15:00）、app `dgtf_app/`、bench/、outputs/ 最近 packed。
> 审计方式：**只读**。未改代码、未跑真实 API 长任务；所有数字来自磁盘 packed/md + 本地 bench 打分 + 只读 API/脚本。
> 审计时点：2026-10-22 18:00 左右。生产 app 8765 未停未重启。

## 0. 结论摘要

1. **"answer_ready" 不是质量门，是结构/流程门**：当前 127 份可读 packed 里 answer_ready=true 的 25 份只来自 **3 个不同问题**（其中 23 份是同一道 "DeepSeek-V4.1-Flash-1017 发布时间" 的重复跑）；25 份中 8 份 `standard_all=false`、21 份 flags≥5。V1.30.0 的 6 次真跑里 ready=2/6，且这 2 次 `standard_all` 都为 false。
2. **"准确回答"缺少真值/相关性门**：事实卡 answered 的判据是「官方源≥1 **或** 独立域名≥2」，不检查证据是否覆盖题面。实锤：run `20261022_091812`（问"元DGTF 修行层作用"）的事实答案是**修仙境界介绍**（来自 CSDN/知乎等，官方源 0，gaps 含 `no_official_source`+`uncovered:…`），`fact_contract.ok_all=true`，同一段错误答案被注入四层并标"四层事实达标"；answer_ready 仅因 route=0/四层标准未达标才为 false。
3. **"高质量决策"在输出与度量两处失真**：packed 里 actions 完整（如 113206 有 5 条、六字段齐），但 md 落地层仍从 `views.1` 取 actions（v1.24 已把 actions 迁到 all/顶层）⇒ md 只渲染出 1 条残缺 action（负责人/时限/验收/回退全部"（未指定）"）、not_do 渲染成"未指定"；bench 决策 rubric 因此只给 2/3（或 0/3），而按 packed 结构本应 ≥3/3。`/api/quality` 只暴露替代分，不暴露 answer_ready/std_all/证据缺口。
4. **"深度对话推理"无契约、无指标**：引擎是单跑四层，packed 无多轮对话状态；质量块没有深度读数（claim 数/引用密度/章节覆盖/未支持断言），md 大小（37–185KB）与结构化产品字符（1.4k–4.3k）严重脱节；历史回声会把既往答案文本（含错误答案）注入 prompt，无核实门。
5. **mock/门禁通过数不能证明质量**：最近 200 份 mock smoke packed 的 coverage 全为 null（0/200），answer_ready 只 16/200（来自同一道冒烟题、官方源 0 的宽松事实卡）；"冒烟 266/0、跨档 319/0、自检 371/0"只证明接线，不证明回答准确或决策质量。当前 benchmark 集（20 题）里只有 3 题有 gold rubric，且最后一批 bench 报告是 v1.22 时代，V1.30 没有基准跑分。

---

## 1. 样本与口径

| 口径 | 数值 | 说明 |
|---|---:|---|
| outputs/*.packed.json | **128** | mtime 2026-10-09 到 2026-10-22 |
| 可读 / 不可读 | **127 / 1** | 不可读：`20261022_123029_…`（独立服务账户跑的产物，当前用户 EPERM） |
| 含 quality 块 | 91 | 其余 36 份是旧版/测试跑 |
| 含 decision_trace | 40 | V1.25+ 才落该块 |
| 四层全进入+全跑完 | 67 | route/ran 均 4 层 |
| 真跑（时间戳 id） | 94 | 另有 33 份测试/探针 id |
| 不同问题数 | **40** | 127 份中前两名问题重复 33+26 次 |
| **V1.30.0 已完成真跑** | **6** | run.json engine=元DGTF-V1.30.0.py；另 1 份服务账户产物不可读、1 份第 5 次真跑无产物（见 §6） |
| 最近 mock smoke packed | 200 | 2026-10-21 至 10-22 冒烟产物 |

V1.30.0 六次真跑明细（`outputs/`）：

| run_id | 题类 | route/实际 | coverage | answered | ready | std_all | core_ok | flags | calls/tokens | quality_alt |
|---|---|---|---:|---:|---|---|---|---:|---|---:|
| 20261021_124215 | decision | 4 / 0,1（预算截断） | .5318 | 5/5 | false | false | false | 7 | 60 / 341k | 3.2 D |
| 20261021_142945 | decision | 4 / 4 | .7706 | 4/5 | false | false | false | 11 | 139 / 1.17M | 0 D |
| 20261021_155109 | decision | 4 / 4 | **.9766** | 4/4 | **true** | false | true | 2 | 179 / 1.49M | **78.34 B** |
| 20261021_182929 | decision | 4 / 4（1圈×4） | null | 0/0 | false | false | false | 6 | 10 / 64k | unmeasured |
| 20261022_091812 | fact | 1 / 0 | null | 0/0 | false | false | false | 4 | 10 / 58k | unmeasured |
| 20261022_110809 | decision | 4 / 4 | .9333 | 3/3 | **true** | false | true | 3 | 180 / 1.93M | 75.33 B |

> 注：`20261022_110809` 的 md/packed 文件名是 113206，run.json id 为 110809_0d0aa3；下同以 id 指代。

---

## 2. 指标现状

### 2.1 当前引擎（V1.30.0，n=6）能证明什么

- **结构**：四层全跑完 4/6；core_ok 2/6；all_closure.ok 2/6；fact_contract 仅 1/6（且该 1 次是错误答案，见 §3-G1）。
- **质量**：coverage 有读数 4/6（中位 .9333）；quality_alt 可算 4/6（中位 75.33，两个 B、两个 D/0）；**tri_quality 6/6 = unmeasured**（test-retest 默认关）；consistency **6/6 = not_comp**（5/6 次 retrieval n=0；2 次有 18/37 条"web_results"但 official=0）。
- **成本**：均值 96.3 calls / 843k tokens；md 中位 146KB；结构化产品字符合计 17,133；引用数 **0**；tokens/KB 1.1k–11.7k（同质量带成本差 >5 倍，无成本-质量门）。
- **可复算**：`/api/quality/20261021_155104_950be7` 返回 78.34 / B，与本报告按 `dgtf_app/server.py:_quality_alt` 公式复算一致。

### 2.2 全库聚合（127 份可读 packed）

| 指标 | 数值 |
|---|---|
| coverage 有读数 | 76/127，中位 **.569** |
| coverage=null | 51/127（其中 fact 路径 7 份） |
| answer_ready=true | **25**（fact 23 / decision 2；**仅来自 3 个不同问题**） |
| ready 但 std_all=false | 8 |
| ready 但 flags≥5 | 21 |
| ready 但 coverage=null | 4 |
| standard_all=true | 18/127 |
| core_ok=true | 64/127 |
| all_closure/one/both/zero 通过 | 36/41、45/49、42/48、42/42 |
| consistency | 87 无该块、13 not_comp、**27 mismatch、0 match** |
| tri_quality | unmeasured 65、unreliable 3、reliable 3、undefined 56 |
| quality_alt（可算 76） | 中位 **10.27**；grade A1/B5/C5/**D65** |

**quality_alt 对 flag 过敏**：公式为 `100×coverage×answer_rate×(0.7+0.3×closure)−6×flags`。`duty_short` 出现在 91/127、`probe_link_dangling` 90/127，这些是常规读数而非缺陷，却每条扣 6 分。只对"硬缺口"（core_audit_gaps / all_closure_gaps / all_closure_unavailable / action_incomplete / not_do_missing）扣分时，76 份的中位从 **10.27 → 43.51**，分布从 A1/B5/C5/D65 变为 A10/B7/C8/D51——说明当前分数主要在测 flag 数量，不是质量。

### 2.3 mock vs real

| 指标 | 最近 200 份 mock smoke | V1.30 真跑 n=6 |
|---|---:|---:|
| coverage 有读数 | **0/200** | 4/6 |
| answer_ready=true | 16/200（8%） | 2/6 |
| standard_all=true | 16/200 | **0/6** |
| all_closure.ok | 0/200 | 2/6 |
| core_ok | 0（V2 影子未开，不写） | 2/6 |
| 平均 flags | 9.52 | 4.5 |
| tri_quality | 无有效读数 | 6/6 unmeasured |

mock 的 16 份 ready 全部来自同一道冒烟题（"CLI 冒烟问题：这件事的边界在哪里"），事实卡答案是"什么是冒烟测试"的网页定义，official=0、coverage=null——即 **mock 也能产出 answer_ready=true，但质量不可用**。结论：266/319/371 这类 mock 门禁不能用于回答"准确率/决策质量"。

### 2.4 bench 与决策 rubric 现状

- bench 数据集在仓库里：20 题（`bench/questions`）、3 题 gold rubric（`bench/gold`）、历史 run 目录 9 个，但最近报告是 `bench/reports/v122*.md`（v1.22 时代），**V1.30 没有跑过 bench**。
- 对 V1.30 产物跑只读 `bench/bench_score.py`：
  - practice 6/6 = 1.0（objective=manifest 模板在）；
  - research 6/6 = 1.0（只判 objective=truth；coverage 解析 4/4=100%、3/3=100%、4/5=80%，低预算跑为 null）；
  - **decision rubric：155109/110809 只有 2/3，124215/142945/182929 为 0/3**；boundary 只有短事实题 091812 得 1.0。
  - 2/3 的直接原因：md 只解析出 **1 条 action**（且字段"未指定"），而 packed 里分别有 **6、5 条**六字段完整的 actions（见 §3-G3）。
- 结论：bench 的 research 分=模板分，decision 分被渲染层 bug 拖低；当前没有可用于"准确/决策"的基准分。

### 2.5 深度与对话推理

- 引擎 `run(question,…)` 是**单次四层**，packed 无对话/轮次状态；app 的 DSH 会话是独立 agent 层，与引擎质量块不连。
- 深度可观测项：md 37–185KB（含日志/附录），但 `process_ledger` 结构化产品字符仅 1.4k–4.3k，cite **0**；quality 块没有 claim 数、引用密度、章节覆盖、未支持断言、对话一致性任何指标。
- 历史回声（`dgtf_v2/recall_memory.py`）会把既往答案文本拼进 prompt_hint（最多 300 字，带"不得照抄"提示）。实锤：110809（"元DGTF是什么"）的 `packed.recall` 收录了 091812 的错误修仙答案，且该 run answer_ready=true——错误记忆可进入后续 prompt，但没有核实/降权门。

---

## 3. 主要缺口（按影响排序）

**G1｜answer_ready 与"准确"脱钩（P0）**
- fact 路径判据（`元DGTF-V1.30.0.py:22422-22436`）：`all4 && card.status=="answered" && _led_ok`；**不要求** `official≥1`、不要求 gaps 为空、不要求 consistency=match/partial（mismatch 只置 advisory）。
- decision 路径的 `standard_all` 门只在 fact 分支后补（24288-24295），所以 155109/110809 可以 ready=true 同时 std_all=false；md 同屏出现"answer_ready=True"与"四层标准 ⚠ 未达标"。
- 实证：091812 事实卡 answered（官方 0、独立域名 8、gaps 含 `no_official_source`/`uncovered`），答案是修仙境界；`fact_contract.ok_all=true`。若该题四层齐且 ledger 修好，当前逻辑会给 answer_ready=true。
- 25/127 ready 只覆盖 3 个问题（23 次同一题），无法外推"准确回答"。

**G2｜process_ledger/standard_all 数据源错误，导致 0/6 真跑达标（P0）**
- `dgtf_v2/process_ledger.py` 从 **views** 读 layer-1 citations，但 citations 在 `pools["1"].sub_questions`（113206 的 6 条子问题每条都有 citations），所以 `cites` 恒为 0；
- layer-1 标准要求 `decidability_audit` 状态 ∈ {verified, mixed}；当前真跑该块 status="empty" ⇒ 6/6 判 false；
- both/all 标准依赖 `meta_closure.clean`；155109 all_closure.ok=true 但 meta_closure.clean=false ⇒ std false。结果 `standard_all=0/6`，而 md/API 只报"未全达标"，无法定位到哪条判据。
- 这也是 091812 的 answer_ready 被拦住的唯一原因（"四层过程标准未全达标"）——靠错误门挡住错误答案，不是靠准确门。

**G3｜输出契约断裂：packed 结构化、md 消费旧路径（P0）**
- 决策渲染器 `_render_landing_decision`（25676-25705）从 `views["1"].decidable_product` 取 actions/not_do；v1.24 起 actions/not_do 已迁到 `views.all` 与 packed 顶层（113206: 顶层 actions=5、六字段完整、not_do=3），views.1 不再有 ⇒ md 只渲染出 1 条词法兜底 action，负责人/时限/验收/回退全"（未指定）"、not_do 显示"未指定"。
- 连带：bench decision rubric 读 md ⇒ 2/3 或 0/3；用户看不到真实决策质量；`/api/quality` 不含 answer_ready/std_all/证据缺口/answer_summary。
- `answer_summary` 字段不存在（全库 grep 0 命中）；md 只有"结论摘要"渲染，质量块只有 coverage/tri/decision_actions/not_do 一行。

**G4｜质量替代分未校准（P1）**
- 平权 −6×flags 把常规读数当缺陷（§2.2 敏感性实验：中位 10.27→43.51）；closure 用 stop 文本匹配 `token/预算/截断`，分母是"出现过的层"而非 route 长度，"体力耗尽（5 圈走满）"这类 cap 截断若不带"截断"字会被算作自然收尾；coverage=null 一律 unmeasured（51/127），面板/报告大面积空白、且与 answer_ready=true 并存（4 份 ready&cov=null）。
- 无用例说明分数与人工 rubric 的相关性；README 的质量/成本表是 v1.23.65 历史值（129 calls/1.16M/100%/60%），不是 V1.30 实测。

**G5｜准确率/校准证据缺失（P0）**
- V1.30 六次真跑 tri_quality 全 unmeasured；tri_state 多 [0,0]，但 tri_alpha 有 .13–1.0——字段共存但无 test-retest 放行，不能当质量；
- consistency 6/6 not_comp：5 次 retrieval n=0（web=false 或用工具结果代替），2 次有 web_results 但 official=0；全库 0 次 match；
- `claim_gap` 在 yaml 里 enabled=true，但 V1.30 真跑 packed 无 claim_gaps 块（真实跑多 `--web off` 或工具检索路径绕过），逐 claim 证据缺口未在真跑生效；
- 事实卡 answered 不检查题面覆盖（G1），"官方事实卡"在 official=0 时仍用该措辞。

**G6｜证据广度与完整性不足（P1）**
- 127 份=40 个问题，前两名问题 33+26 次；answer_ready 证据只覆盖 3 个问题；bench 20 题/3 gold 未用于 V1.30。
- docs/real_run_20261021.md 的第 5 次真跑（20261021_183508，160 calls/1.4M、coverage .5169）在 outputs/ 里**没有 packed/md/run.json**；第 1 次"被打断"却有 packed（124215，60 calls/341k，ran=0,1）；
- 独立服务账户真跑（20261022_122854/123029，route=0）产物被 ACL 限制，当前用户不可读；
- 取消任务无 packed（091642），无法参与质量统计。→ 验证报告里的"质量"数字不可由第三方复算。

**G7｜深度/多轮无指标（P1）**
- 无对话轮次/上下文保持契约；recall 注入历史答案正文无核实（§2.5）；无 claim 数/引用密度/未支持断言/章节覆盖等深度指标；md 大而结构化产出小，无法判断"深度"来自推理还是日志。

**G8｜mock 门禁与质量证据混淆（P1）**
- mock coverage 全 null、ready 依赖宽松事实卡；266/319/371 绿灯与质量无关；README 声明"只写能验证的事"，但质量表述/版本记录缺 V1.26–1.30 CHANGELOG（CHANGELOG 最新是 v1.25.0），当前质量基线未重测。

---

## 4. 改进方案（≤3 个，高杠杆、低风险、可离线验收）

### 方案 A（P0）：把"答案门"和"过程门"分开，并修 ledger 数据源

**改什么（只动读数/门禁，不改生成算法）**
1. `answer_ready` 拆两字段：`process_ready`（四层齐+契约/ledger 标准）与 `answer_quality`（事实：official≥1 或（independent≥2 且 gaps 为空且 consistency≠mismatch）；决策：coverage≥.9 且 actions 完整）。只有两者都满足才对外报"已核实"；`answer_ready_reason` 输出结构化 code + 文本。
2. `process_ledger`：layer-1 citations 改读 `pools["1"].sub_questions[].citations/evidence`；`decidability_audit.status=="empty"` 视为"未运行"（不判红，或显式要求 n>0）；meta_closure 缺失不作 false；both/all 的 stop/cap 截断按 stop code 判定（禁止字符串匹配）。
3. 事实卡 gaps 中 `no_official_source/uncovered/conflict_unresolved` 参与 `fact_contract` 与 answer_quality 判定；`fact_contract` 只认"证据命中题面 token/关键项"的注入，不能把同一段外部文本注入四层后自证。
**为什么低风险**：只改判据/读数，不改 prompt、不改生成与采样；失败时只影响标签，不影响已有正文。
**预期收益**：091812 这类"检索到无关文本即 answered"会被标为 needs_evidence/unverified；155109/110809 的 ready 不再与"四层标准⚠"同屏矛盾；standard_all 从 0/6 变为可解释（预计 2–4/6 可恢复，需重放验证）。
**验收**：重放 6 份 V1.30 packed：① 0 份出现 ready=true 且 std_all=false；② 091812 的 fact_contract.ok_all=false 且 answer_quality=needs_evidence；③ 有证据的跑次 layer-1 citations>0；④ 每份跑次给出 per-layer 不达标 code（≤3 条）。

### 方案 B（P0）：统一"结构化产物"消费面（md / bench / API / 摘要）

**改什么**
1. `_render_landing_decision` 优先读 packed 顶层 `actions`/`not_do`（其次 `views.all`，最后才 views.1 词法兜底）；行动段落按六字段渲染，缺字段显式标 `[缺]` 而不是"（未指定）"。
2. `bench/bench_score.py` 决策 rubric 改为"优先读 packed.actions 结构化，md 仅兜底"；新增 `--packed` 入口，输出 action 完整率/not_do/边界。
3. `/api/quality` 增加 `answer_ready/answer_quality/process_ready/process_ready_reason/standard_all/coverage_missing/evidence_gaps/tri_quality/tri_alpha`；新增 `answer_summary` 契约块（question_type/answer/evidence_ids/consistency/answer_ready/gaps/stop_reason），md"结论摘要"与 app 展示消费同一份。
4. claim_gap 在真实跑默认走 web 的条件下产出 `claim_gaps`，并计入 answer_summary 的"未支持断言"读数（无 web 时显式写"未测"）。
**为什么低风险**：纯输出/读数层，不改推理；有 packed 原字段可回滚。
**预期收益**：155109/110809 的 md 行动清单从 1 条恢复为 6/5 条且字段齐，bench rubric 从 2/3 恢复 ≥3/3（按 packed 复算）；决策质量第一次在用户界面可读；answer_summary 让 app/报告不再各拼一套。
**验收**：对 155109/110809：md action 数=packed decision_actions（6/5）、字段完整率≥90%、not_do 渲染 3 条；bench rubric 3/3；`/api/quality` JSON 含上述字段；对 6 份跑次做快照回归（无字段缺失、无 500）。

### 方案 C（P1）：质量分与固定基准回归

**改什么**
1. `_quality_alt` 校准：flags 分"硬缺口/软读数"两级（硬缺口才扣分，软读数只展示）；closure 按 route 层数（4）与 stop code 判，cap 截断不算自然收尾；coverage=null 分 `no_answerable`（合法，标 n/a）与 `missing`（缺陷）两种。
2. 深度读数：从 process_ledger 增加结构化产品字符、claim 数、引用密度、未支持断言数（claim_gaps）、章节覆盖；输出 `quality.depth`。
3. 固定基准：用 `bench/questions` 中 3 个 gold 题（biz_001/eng_001/tech_001）跑 release 基准（预算 600k 起，可用 mock 先验；真跑按需≤2M/题），用 `bench_score --packed` 出分；把"最近 6 次真跑 + 3 gold"的分数记入 `reports/`，不再用单次精选跑次当基线。
**为什么低风险**：只改打分/报告与新增基准跑；不影响引擎行为；旧分数保留 raw 字段可回溯。
**预期收益**：76 份历史分数从"flag 计数"变为可比质量分；README/报告能给出当前 V1.30 的真实质量-成本点，而不是 v1.23.65 历史表。
**验收**：同一 76 份 packed 重算：grade 分布改变但每份给出 basis；硬缺口/软读数分离后 A/B 档不再被 duty_short 拉成 D；3 gold 题有一份可复算报告（coverage/decision rubric/边界），并与 155109 基线对比"不劣"。

---

## 5. 验收标准（汇总）

| 项 | 通过线 |
|---|---|
| answer 门一致性 | 6 份 V1.30 与后续新跑：ready=true 且 process_ready=false 的条数 = 0；每个 ready 都带 answer_quality=basis + evidence ids |
| 事实正确性门 | 091812 重放：fact_contract.ok_all=false，answer_quality∈{needs_evidence,unverified}，理由含 uncovered/no_official_source |
| ledger 可解释 | 每份跑次 std_all 为 false 时给出 ≤3 条 per-layer code；有证据的 layer-1 citations>0 |
| 决策输出 | 155109/110809：md actions=packed actions（6/5），字段完整率≥90%，not_do=3；bench rubric=3/3 |
| 质量分 | 76 份重算：grade 不再由软 flag 主导；每份 score 有 basis；硬缺口为 0 的跑次不因 duty_short 掉档 |
| 深度/对话 | quality.depth 落 packed+md；≥1 个双跑对照（同题两次）深度指标可复算；recall 注入的既往答案必须带来源+核验状态（未核验降权/不注入正文） |
| mock 定位 | mock 门禁仍绿，但质量报告不引用 mock 分数；质量结论只来自真实跑/bench gold |

**离线回归命令（不花 API 费用）**

    # 1) 重放 6 份 V1.30 packed 走新 ledger/answer 门（只读脚本）
    python scripts/replay_quality.py   # 方案落地时新增；本轮不改代码
    # 2) 重算 quality_alt 76 份（硬/软 flag 两套口径对比）
    python bench/bench_score.py outputs/20261021_162051_元DGTF项目权威背景内置本地文.md
    # 3) mock 回归（不调真实 API）
    python smoke_test.py               # 期望 266/0
    # 4) bench gold（3 题；先 mock 后小预算真跑）
    python bench/bench_run.py --help   # 按现有参数确认；gold 评分用 bench_score --packed

---

## 6. 未做与限制（如实说明）

- **未跑真实 API 长任务**（按任务要求）；因此"准确率"只有结构/证据侧证据，没有人工标注真值集。
- **样本小**：V1.30 完成真跑仅 6 次、3 个不同问题；历史 127 份中大量是重复问题/旧版引擎，不能做统计显著性。
- **1 份产物不可读**：`outputs/20261022_123029_…packed.json` 属独立服务账户，当前用户 EPERM；docs/validation_report §9.1 的该次真跑（route=0）无法纳入审计。
- **1 次真跑无产物**：docs/real_run 第 5 次（20261021_183508，160 calls/1.4M、coverage .5169）在 outputs/ 未找到 packed/md/run.json，只有文档记录。
- 任务运行中（`20261022_173902_87b111.run.json`，17:39 起，0 字节 log）未触碰、未纳入统计。
- CHANGELOG 最新只到 v1.25.0，V1.26–V1.30 的质量相关改动无版本记录；README 质量/成本表为 v1.23.65 历史值。
- 本报告只读审计，未修改任何代码、配置或产物。

## 7. 证据索引

- 引擎：`元DGTF-V1.30.0.py`（`_quality_report` 22097；`_build_decision_trace` 22204；answer 门 22422-22436；post-pack 门 24288-24295；decision 渲染 25676；packed 组装 23399+）
- 内核：`dgtf_v2/process_ledger.py`（layer/citations 43-96）、`dgtf_v2/evidence.py`（detect_gaps 528、FactCard 规则）、`dgtf_v2/fact_flow.py`（build_fact_card 289-346）、`dgtf_v2/fact_contract.py`、`dgtf_v2/recall_memory.py`（prompt_hint 64-71）
- app：`dgtf_app/server.py:6016 _quality_alt`；`bench/bench_score.py` 决策 rubric 106-165
- 数据：`outputs/` 128 packed；`docs/real_run_20261021.md`；`docs/validation_report_2026-10-22.md`；`smoke_outputs/` 最近 200 mock packed
- 关键样本：091812（错误事实卡）、155109 / 110809（ready 但 std=false）、142945（11 flags、alt 0）
