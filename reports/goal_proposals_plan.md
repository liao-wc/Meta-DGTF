# 29 条 pending 提案逐条审计与执行计划（goal_proposals_plan）

> 生成：2026-10-22 · 执行：teammate core-audit · 依据：`team_task_list` 后的 29 条 `pending` 提案
> 范围：**只读审计**（未改提案/源码/配置/运行态；未执行 resolve/reject/apply）
> 数据源：`GET https://127.0.0.1:8765/api/dsh/proposals`、`dgtf_memory/dsh_proposals/*.json`、`_index.json`、`playbook.jsonl`、`元DGTF-V1.30.0.py`、`outputs/*.packed.json`、`CHANGELOG.md`、`smoke_test.py`、`dgtf_v2/agent_bridge.py`、`agent_daemon.log`
> 安全：token 只在本地读 `dgtf_memory/.access_token` 用于 API 鉴权；**本报告与任何输出均不显示 token**

## 0. 结论速览

| 判定 | action | 条数 | 含义 |
|---|---|---:|---|
| 历史已修复 / 已学习已应用 / 历史跑次不复现 | `resolve` | **15** | 关闭（superseded），不再修 |
| 良性读数 / 预期读数 / 夹具噪声 / 无源不可复现 | `reject` | **11** | 关闭（rejected），并注明复现条件 |
| 仍是真问题 / 需新增验证 | `needs_fix` | **3** | 保留 pending，补可执行方案后按验证计划处理 |
| 应应用 EML 候选 | `apply` | **0** | EML 6 条中 4 条已 active+applied、2 条证据不足；按学习闸不人工 force |

- **项目相关 vs 噪声**：18 条仍指向项目真实轨迹（15 条已有结论/已学习 + 3 条待验证）；11 条为良性/预期/夹具/无来源不可复现噪声。
- **优先级分布**：P1 1 条（#11 → 关闭）、P2 22 条（#5 为 needs_fix、其余 resolve/reject）、P3 6 条（EML：#2/#4 needs_fix，#3/#8/#28/#29 resolve）。
- **根因**：29 条全部 `plan_gap=true`（批量自审占位方案未补）；同名任务在本轮前已反复 expired 3–6 次（`pending_ttl_24h` 23、`security_blocked_tool_access` 68、`low_stale_quality` 16、`duplicate_of_confirmed` 22、`low_priority_quality_signal` 5 等）→ 本次应一次性收口，避免第 6 轮循环。

## 1. 审计口径

每条按「**当前代码/当前真跑/学习库状态**」三路对照：
1. **历史已修复**：有提交/代码/CHANGELOG 证据，且（或）当前设计已把该读数改为留痕/良性；
2. **仍是真问题 / 需新增验证**：在 V1.30.0 近期真跑（2026-10-22 11:32，180 calls/1.93M tokens，四层全跑）仍复现，或新候选缺证据；
3. **应关闭**：引擎自身判定良性/预期（裁层、层相关正常值）、夹具/冒烟产物、无 source_run 且不可复现；
4. **EML 候选**：对照 `playbook.jsonl` 的 active/shadow 状态与晋升闸（`_EML_PROMOTE_N=3`、只省成本不升级、需双侧记账）。

## 2. 逐条判定总表（29 条）

| # | 提案 id（短） | kind/类别 | 优先级 | 标题 | 判定 | action | 关键证据 |
|---|---|---|---|---|---|---|---|
| 01 | 50346c | quality_flag/probe_quality | P2 | 质量线索：probe_link_dangling(2) | 历史已修复 | **resolve** | E4 探针链接「只留痕不拦」是设计（CHANGELOG.md:2614-2615；元DGTF-V1.30.0.py:14413-14416）；误报硬化提案 024a9e 已 applied（commit 0282bbf，改 元DGTF-V1 |
| 02 | d30bf5 | eml_candidate/eml_experiment | P3 | 验证/应用 EML 候选：web_hint | 需新增验证 | **needs_fix** | playbook 30 条无 web_hint 条目（grep playbook.jsonl）；promote 闸 _EML_PROMOTE_N=3 且「只省成本不升级」（元DGTF-V1.30.0.py:2896, 3378-3408）。 |
| 03 | 4f48c1 | eml_candidate/eml_experiment | P3 | 验证/应用 EML 候选：thinking_hint | 已学习并应用 | **resolve** | playbook L0022（thinking_hint, layer1_adjudication_noise）active n_ev=21；10-22 11:32 真跑 playbook.mode=on 且 used 中 L0022 ap |
| 04 | 1135dd | eml_candidate/eml_experiment | P3 | 验证/应用 EML 候选：action_hint | 需新增验证 | **needs_fix** | playbook L0023（action_hint, all_actions_missing）仍 shadow n_ev=2；晋升需 ≥3 同向证据（元DGTF-V1.30.0.py:2896）。 |
| 05 | a17c3c | quality_flag/quality_signal | P2 | 质量线索：duty_short | 仍是真问题 | **needs_fix** | 10-22 11:32 V1.30.0 真跑（180 calls/1.93M tokens）quality.flags 仍含 duty_short，且 quality.layers 的 both/all 层 duty_short、proce |
| 06 | 60d405 | quality_flag/quality_signal | P2 | 质量线索：position_all_same_structural | 已关闭（良性读数） | **reject** | 引擎判定：池极性全同但 why 多样＝结构性一致、非坍缩（元DGTF-V1.30.0.py:14568-14574）；源跑 20261020_143748 产物已被回收（outputs 0 文件）；同名历史 3 次 expired。 |
| 07 | d2f46d | quality_flag/quality_signal | P2 | 质量线索：candidates_backfilled(sc:5) | 已关闭（无源/不可复现） | **reject** | flag 属自省「候选后补」留痕（元DGTF-V1.30.0.py:1278-1290, 10980-11010）；历史已修「self-check flag 被重算冲掉」（CHANGELOG.md:8531-8535）；无 source_r |
| 08 | c440fb | eml_candidate/eml_experiment | P3 | 验证/应用 EML 候选：config_hint | 已学习并应用 | **resolve** | playbook L0024（config_hint, facet_empty）active n_ev=18；10-22 11:32 used 中 L0024 applied:true。 |
| 09 | ed0929 | quality_flag/quality_signal | P2 | 质量线索：expand_imbalanced | 历史已修复（细化） | **resolve** | V1.30.0 新增 benign 分支并改变判定（元DGTF-V1.30.0.py:14518-14523）；近期真跑只出 expand_imbalanced_benign、不出旧 expand_imbalanced；源产物回收。 |
| 10 | 45d034 | quality_flag/quality_signal | P2 | 质量线索：too_many_amp_candidates(100%) | 已关闭（层相关正常读数） | **reject** | 引擎判定：0/1 层锚点收敛时偏高属正常，both/all 层 >0.5 才留意（元DGTF-V1.30.0.py:14526-14528）；无 source_run；同名历史 3 次 expired(low_priority)。 |
| 11 | 25c91b | api_gap/agent_runtime | P1 | Tool Calls 未触发，排查预检/配置 | 已关闭（当前配置不复现） | **reject** | 10-22 11:32 真跑 api_usage={search_calls:12, tools_calls:4, web_enabled:true}；原 detail web_enabled=false 时 0 调用属预期；同名历史 ex |
| 12 | 261625 | quality_flag/probe_quality | P2 | 质量线索：probe_link_dangling(1) | 历史已修复 | **resolve** | 同 #01：E4 只留痕设计 + 误报硬化已 applied（commit 0282bbf）。 |
| 13 | e97115 | quality_flag/quality_signal | P2 | 质量线索：all_closure_unavailable | 已关闭（裁层预期读数） | **reject** | 条件＝actions.all_v2 且 views 无 all（元DGTF-V1.30.0.py:22679-22683）；10-22 09:19 route=0 真跑即 flags 含 all_closure_unavailable。 |
| 14 | 2ccc48 | quality_flag/quality_signal | P2 | 质量线索：unsaid_overused(4) | 已关闭（诊断读数+已有回写） | **reject** | unsaid_overused 由自省阈值生成（元DGTF-V1.30.0.py:14794-14795），且高置信诊断已提升为可执行动作（CHANGELOG.md:3633-3648）；阈值 unsaid_escape_limit 可配； |
| 15 | 50ce99 | quality_flag/quality_signal | P2 | 质量线索：no_amp_at_all | 已关闭（场景性读数） | **reject** | 引擎判定按原因分派：上游空/开关关/确实无可通约处，均非判断缺陷（元DGTF-V1.30.0.py:14551-14557）；近期 V1.30 真跑未复现。 |
| 16 | 1a8095 | quality_flag/quality_signal | P2 | 质量线索：all_closure_gaps | 历史跑次已不复现 | **resolve** | 10-21 18:31 薄跑 all_closure.cc=0.33、gaps=[缺 actions/not_do/residual/confidence]；10-22 11:32 V1.30 完整预算真跑 all_closure.ok=T |
| 17 | d81190 | quality_flag/quality_signal | P2 | 质量线索：polarity_all_same_structural(1) | 历史已处理（良性） | **resolve** | 引擎判定结构性一致非坍缩（元DGTF-V1.30.0.py:14568-14574）；同题 0 号变体提案 prop-1792647593522-ec379f 已 applied（含 structural_diversity 门禁）；10- |
| 18 | 3526fa | quality_flag/quality_signal | P2 | 质量线索：ing_rephrased_direct(100%) | 历史已修复 | **resolve** | 复述检测已改主判据 _sim3（CHANGELOG.md:2723-2787）并修过 rephrase_ratio 显示吞值（CHANGELOG.md:8235-8259）；无 source_run、近期真跑未复现。 |
| 19 | 2b53a4 | user_task/other | P2 | daemon live probe | 验证完成 | **resolve** | agent_daemon.log 2278 行、cycle≥114（含 triaged/proposals 落盘），agent_results 有消费记录；task-8 已完成；当前 state=stopped 属手动 stop（.stop |
| 20 | 1e9927 | quality_flag/quality_signal | P2 | 质量线索：ing_rephrased_direct(50%) | 历史已修复 | **resolve** | 同 #18（复述检测改 _sim3 + 显示修复）；近期真跑未复现。 |
| 21 | 03e3cf | quality_flag/quality_signal | P2 | 质量线索：unsaid_overused(5) | 已关闭（诊断读数+已有回写） | **reject** | 同 #14；源跑 20261020_143748 产物已回收。 |
| 22 | af4cf4 | quality_flag/quality_signal | P2 | 质量线索：probe_no_target_covered | 历史已修复 | **resolve** | E3 语义双查已接线（元DGTF-V1.30.0.py:14395-14411；CHANGELOG.md:2610-2613 明确「编号对只是必要条件+语义」）；近期 V1.30 真跑未复现；源产物已回收。 |
| 23 | 414c84 | quality_flag/quality_signal | P2 | 质量线索：unsaid_overused(7) | 已关闭（诊断读数+已有回写） | **reject** | 同 #14；源跑 20261020_153113 产物已回收。 |
| 24 | e4bff4 | quality_flag/quality_signal | P2 | 质量线索：expand_imbalanced_benign | 已关闭（引擎判定良性） | **reject** | 引擎 quality_verdict：expand_imbalanced_benign＝另一边输出足够多、可能问题性质决定（非失败）（元DGTF-V1.30.0.py:14518-14520）。 |
| 25 | cb05cb | quality_flag/quality_signal | P2 | 质量线索：action_incomplete | 历史已修复 | **resolve** | schema 接线+硬约束修复见 CHANGELOG.md:4488-4497（三题真跑 action_incomplete 4/4→0/3）与 4612-4618；源跑 20261021_182929 产物已回收；近期 V1.30 真跑未 |
| 26 | a9183d | quality_flag/quality_signal | P2 | 质量线索：not_do_missing | 历史已修复 | **resolve** | not_do schema 接线见 CHANGELOG.md:4430-4438、4612-4618（not_do_missing 定义与硬约束）；近期真跑未复现。 |
| 27 | 566e00 | process_gap/process_gap | P2 | 层 1 过程标准未达标 | 已关闭（夹具噪声） | **reject** | product 文本逐字来自冒烟夹具 smoke_test.py:248/260（「这是一段用于冒烟测试的中文输出文本…」）；队列闸已过滤空/夹具 run（dgtf_v2/agent_bridge.py:10-28），该条为闸前遗留。 |
| 28 | 92f2fc | eml_candidate/eml_experiment | P3 | 验证/应用 EML 候选：carve_first | 已学习并应用 | **resolve** | playbook L0020（carve_first, layer1_citation_low）active n_ev=24；10-22 11:32 used 中 L0020 applied:true。 |
| 29 | 94b3aa | eml_candidate/eml_experiment | P3 | 验证/应用 EML 候选：rounds_delta | 已学习并应用 | **resolve** | playbook L0018（rounds_delta, layer1_duty_short）active n_ev=21；10-22 11:32 used 中 L0018 applied:true（同跑另见 L0028 all round |

## 3.1 resolve（15 条）—— 历史已修复 / 已学习已应用 / 历史跑次不复现

### 01. 质量线索：probe_link_dangling(2)
- 提案：`prop-1792647593497-50346c` · quality_flag/probe_quality · P2 · source_run=`20261020_135317`
- 判定：**历史已修复** → action `resolve`
- 证据：E4 探针链接「只留痕不拦」是设计（CHANGELOG.md:2614-2615；元DGTF-V1.30.0.py:14413-14416）；误报硬化提案 024a9e 已 applied（commit 0282bbf，改 元DGTF-V1.30.0.py）。近跑仍出但仅留痕。
- 处理：探针链接误报已修；后续可降噪（只对有效 id 引用计数）

### 03. 验证/应用 EML 候选：thinking_hint
- 提案：`prop-1792647593483-4f48c1` · eml_candidate/eml_experiment · P3 · source_run=`20261020_135317`
- 判定：**已学习并应用** → action `resolve`
- 证据：playbook L0022（thinking_hint, layer1_adjudication_noise）active n_ev=21；10-22 11:32 真跑 playbook.mode=on 且 used 中 L0022 applied:true。
- 处理：无需人工 apply（已在生效面）

### 08. 验证/应用 EML 候选：config_hint
- 提案：`prop-1792647593499-c440fb` · eml_candidate/eml_experiment · P3 · source_run 缺失
- 判定：**已学习并应用** → action `resolve`
- 证据：playbook L0024（config_hint, facet_empty）active n_ev=18；10-22 11:32 used 中 L0024 applied:true。
- 处理：无需人工 apply

### 09. 质量线索：expand_imbalanced
- 提案：`prop-1792647593504-ed0929` · quality_flag/quality_signal · P2 · source_run 缺失
- 判定：**历史已修复（细化）** → action `resolve`
- 证据：V1.30.0 新增 benign 分支并改变判定（元DGTF-V1.30.0.py:14518-14523）；近期真跑只出 expand_imbalanced_benign、不出旧 expand_imbalanced；源产物回收。
- 处理：关闭；旧信号已被 benign/真不平衡二分取代

### 12. 质量线索：probe_link_dangling(1)
- 提案：`prop-1792647593507-261625` · quality_flag/probe_quality · P2 · source_run 缺失
- 判定：**历史已修复** → action `resolve`
- 证据：同 #01：E4 只留痕设计 + 误报硬化已 applied（commit 0282bbf）。
- 处理：关闭（仅留痕读数）

### 16. 质量线索：all_closure_gaps
- 提案：`prop-1792647593514-1a8095` · quality_flag/quality_signal · P2 · source_run 缺失
- 判定：**历史跑次已不复现** → action `resolve`
- 证据：10-21 18:31 薄跑 all_closure.cc=0.33、gaps=[缺 actions/not_do/residual/confidence]；10-22 11:32 V1.30 完整预算真跑 all_closure.ok=True、gaps=[]（仅 layer1/all standard_ok 偏低）。
- 处理：关闭；保留复现条件：预算截断/薄跑时复现再重开

### 17. 质量线索：polarity_all_same_structural(1)
- 提案：`prop-1792647593519-d81190` · quality_flag/quality_signal · P2 · source_run=`20261020_143748`
- 判定：**历史已处理（良性）** → action `resolve`
- 证据：引擎判定结构性一致非坍缩（元DGTF-V1.30.0.py:14568-14574）；同题 0 号变体提案 prop-1792647593522-ec379f 已 applied（含 structural_diversity 门禁）；10-22 真跑仍出但 quality 明示非坍缩。
- 处理：关闭（不再重复修）

### 18. 质量线索：ing_rephrased_direct(100%)
- 提案：`prop-1792647593512-3526fa` · quality_flag/quality_signal · P2 · source_run 缺失
- 判定：**历史已修复** → action `resolve`
- 证据：复述检测已改主判据 _sim3（CHANGELOG.md:2723-2787）并修过 rephrase_ratio 显示吞值（CHANGELOG.md:8235-8259）；无 source_run、近期真跑未复现。
- 处理：关闭

### 19. daemon live probe
- 提案：`prop-1792647593518-2b53a4` · user_task/other · P2 · source_run 缺失
- 判定：**验证完成** → action `resolve`
- 证据：agent_daemon.log 2278 行、cycle≥114（含 triaged/proposals 落盘），agent_results 有消费记录；task-8 已完成；当前 state=stopped 属手动 stop（.stop 文件）非失败。
- 处理：关闭（常驻消费已验证）

### 20. 质量线索：ing_rephrased_direct(50%)
- 提案：`prop-1792647593517-1e9927` · quality_flag/quality_signal · P2 · source_run 缺失
- 判定：**历史已修复** → action `resolve`
- 证据：同 #18（复述检测改 _sim3 + 显示修复）；近期真跑未复现。
- 处理：关闭

### 22. 质量线索：probe_no_target_covered
- 提案：`prop-1792647593525-af4cf4` · quality_flag/quality_signal · P2 · source_run=`20261020_145244`
- 判定：**历史已修复** → action `resolve`
- 证据：E3 语义双查已接线（元DGTF-V1.30.0.py:14395-14411；CHANGELOG.md:2610-2613 明确「编号对只是必要条件+语义」）；近期 V1.30 真跑未复现；源产物已回收。
- 处理：关闭

### 25. 质量线索：action_incomplete
- 提案：`prop-1792647593529-cb05cb` · quality_flag/quality_signal · P2 · source_run=`20261021_182929`
- 判定：**历史已修复** → action `resolve`
- 证据：schema 接线+硬约束修复见 CHANGELOG.md:4488-4497（三题真跑 action_incomplete 4/4→0/3）与 4612-4618；源跑 20261021_182929 产物已回收；近期 V1.30 真跑未复现。
- 处理：关闭；若 decision 取向再触发，带 packed 证据重开

### 26. 质量线索：not_do_missing
- 提案：`prop-1792647593530-a9183d` · quality_flag/quality_signal · P2 · source_run=`20261021_182929`
- 判定：**历史已修复** → action `resolve`
- 证据：not_do schema 接线见 CHANGELOG.md:4430-4438、4612-4618（not_do_missing 定义与硬约束）；近期真跑未复现。
- 处理：关闭

### 28. 验证/应用 EML 候选：carve_first
- 提案：`prop-1792647593482-92f2fc` · eml_candidate/eml_experiment · P3 · source_run=`20261020_135317`
- 判定：**已学习并应用** → action `resolve`
- 证据：playbook L0020（carve_first, layer1_citation_low）active n_ev=24；10-22 11:32 used 中 L0020 applied:true。
- 处理：无需人工 apply

### 29. 验证/应用 EML 候选：rounds_delta
- 提案：`prop-1792647593481-94b3aa` · eml_candidate/eml_experiment · P3 · source_run=`20261020_135317`
- 判定：**已学习并应用** → action `resolve`
- 证据：playbook L0018（rounds_delta, layer1_duty_short）active n_ev=21；10-22 11:32 used 中 L0018 applied:true（同跑另见 L0028 all rounds_delta）。
- 处理：无需人工 apply

## 3.2 reject（11 条）—— 良性 / 预期 / 夹具 / 无源不可复现

### 06. 质量线索：position_all_same_structural
- 提案：`prop-1792647593505-60d405` · quality_flag/quality_signal · P2 · source_run 缺失
- 判定：**已关闭（良性读数）** → action `reject`
- 证据：引擎判定：池极性全同但 why 多样＝结构性一致、非坍缩（元DGTF-V1.30.0.py:14568-14574）；源跑 20261020_143748 产物已被回收（outputs 0 文件）；同名历史 3 次 expired。
- 处理：关闭；若 future both/all 层出现真塌缩（_all_same 非 structural）再开新提案

### 07. 质量线索：candidates_backfilled(sc:5)
- 提案：`prop-1792647593503-d2f46d` · quality_flag/quality_signal · P2 · source_run 缺失
- 判定：**已关闭（无源/不可复现）** → action `reject`
- 证据：flag 属自省「候选后补」留痕（元DGTF-V1.30.0.py:1278-1290, 10980-11010）；历史已修「self-check flag 被重算冲掉」（CHANGELOG.md:8531-8535）；无 source_run、近期 V1.30 真跑未见。
- 处理：关闭（观察类）；无需代码改动

### 10. 质量线索：too_many_amp_candidates(100%)
- 提案：`prop-1792647593508-45d034` · quality_flag/quality_signal · P2 · source_run 缺失
- 判定：**已关闭（层相关正常读数）** → action `reject`
- 证据：引擎判定：0/1 层锚点收敛时偏高属正常，both/all 层 >0.5 才留意（元DGTF-V1.30.0.py:14526-14528）；无 source_run；同名历史 3 次 expired(low_priority)。
- 处理：关闭；若 both/all 层复现再带 layer 证据重开

### 11. Tool Calls 未触发，排查预检/配置
- 提案：`prop-1792647593511-25c91b` · api_gap/agent_runtime · P1 · source_run 缺失
- 判定：**已关闭（当前配置不复现）** → action `reject`
- 证据：10-22 11:32 真跑 api_usage={search_calls:12, tools_calls:4, web_enabled:true}；原 detail web_enabled=false 时 0 调用属预期；同名历史 expired=not_reproducible_current_config。
- 处理：关闭；可另立小改进：api_gap 仅在 web_enabled=true 时入队

### 13. 质量线索：all_closure_unavailable
- 提案：`prop-1792647593510-e97115` · quality_flag/quality_signal · P2 · source_run 缺失
- 判定：**已关闭（裁层预期读数）** → action `reject`
- 证据：条件＝actions.all_v2 且 views 无 all（元DGTF-V1.30.0.py:22679-22683）；10-22 09:19 route=0 真跑即 flags 含 all_closure_unavailable。
- 处理：关闭；建议仅在 route 含 all 但产物缺失时才报警

### 14. 质量线索：unsaid_overused(4)
- 提案：`prop-1792647593509-2ccc48` · quality_flag/quality_signal · P2 · source_run 缺失
- 判定：**已关闭（诊断读数+已有回写）** → action `reject`
- 证据：unsaid_overused 由自省阈值生成（元DGTF-V1.30.0.py:14794-14795），且高置信诊断已提升为可执行动作（CHANGELOG.md:3633-3648）；阈值 unsaid_escape_limit 可配；无源产物、近期未复现。
- 处理：关闭（观察项）；如需调阈值单独提配置类提案

### 15. 质量线索：no_amp_at_all
- 提案：`prop-1792647593513-50ce99` · quality_flag/quality_signal · P2 · source_run 缺失
- 判定：**已关闭（场景性读数）** → action `reject`
- 证据：引擎判定按原因分派：上游空/开关关/确实无可通约处，均非判断缺陷（元DGTF-V1.30.0.py:14551-14557）；近期 V1.30 真跑未复现。
- 处理：关闭

### 21. 质量线索：unsaid_overused(5)
- 提案：`prop-1792647593520-03e3cf` · quality_flag/quality_signal · P2 · source_run=`20261020_143748`
- 判定：**已关闭（诊断读数+已有回写）** → action `reject`
- 证据：同 #14；源跑 20261020_143748 产物已回收。
- 处理：关闭

### 23. 质量线索：unsaid_overused(7)
- 提案：`prop-1792647593526-414c84` · quality_flag/quality_signal · P2 · source_run=`20261020_153113`
- 判定：**已关闭（诊断读数+已有回写）** → action `reject`
- 证据：同 #14；源跑 20261020_153113 产物已回收。
- 处理：关闭

### 24. 质量线索：expand_imbalanced_benign
- 提案：`prop-1792647593527-e4bff4` · quality_flag/quality_signal · P2 · source_run=`20261021_142945`
- 判定：**已关闭（引擎判定良性）** → action `reject`
- 证据：引擎 quality_verdict：expand_imbalanced_benign＝另一边输出足够多、可能问题性质决定（非失败）（元DGTF-V1.30.0.py:14518-14520）。
- 处理：关闭

### 27. 层 1 过程标准未达标
- 提案：`prop-1792647593500-566e00` · process_gap/process_gap · P2 · source_run 缺失
- 判定：**已关闭（夹具噪声）** → action `reject`
- 证据：product 文本逐字来自冒烟夹具 smoke_test.py:248/260（「这是一段用于冒烟测试的中文输出文本…」）；队列闸已过滤空/夹具 run（dgtf_v2/agent_bridge.py:10-28），该条为闸前遗留。
- 处理：关闭；可另立闸增强：过滤 mock/smoke 文本产物

## 3.3 needs_fix（3 条）—— 真问题或需新增验证（保留 pending）

### 02. 验证/应用 EML 候选：web_hint
- 提案：`prop-1792647593498-d30bf5` · eml_candidate/eml_experiment · P3 · source_run 缺失
- 判定：**需新增验证** → action `needs_fix`
- 证据：playbook 30 条无 web_hint 条目（grep playbook.jsonl）；promote 闸 _EML_PROMOTE_N=3 且「只省成本不升级」（元DGTF-V1.30.0.py:2896, 3378-3408）。
- 处理：同题 baseline vs 打开 web stages【research_evidence/research_precedent/duel_arbitration】各 ≥3 跑，比 context_score/成本/质量；过 gate_check+双侧记账后再入库，不直接改默认

### 04. 验证/应用 EML 候选：action_hint
- 提案：`prop-1792647593485-1135dd` · eml_candidate/eml_experiment · P3 · source_run=`20261020_135317`
- 判定：**需新增验证** → action `needs_fix`
- 证据：playbook L0023（action_hint, all_actions_missing）仍 shadow n_ev=2；晋升需 ≥3 同向证据（元DGTF-V1.30.0.py:2896）。
- 处理：再补 1-2 次含 all_actions_missing 的同题/近题真跑，令 evidence≥3 且 quality/cost 双侧不降，让学习闸自然 shadow→active；验证 all_closure.actions>0

### 05. 质量线索：duty_short
- 提案：`prop-1792647593496-a17c3c` · quality_flag/quality_signal · P2 · source_run=`20261020_135317`
- 判定：**仍是真问题** → action `needs_fix`
- 证据：10-22 11:32 V1.30.0 真跑（180 calls/1.93M tokens）quality.flags 仍含 duty_short，且 quality.layers 的 both/all 层 duty_short、process_ledger 层1/all standard_ok=False。
- 处理：对照验证：playbook.mode on/off + rounds_delta(L0001/L0018)/carve_first(L0006/L0007) 生效组 vs 关闭组，指标 duty_S、process_ledger.standard_ok、交付覆盖，成本不得变差

## 4. EML 候选专项（6 条）

| # | 候选 key / cond | 提案证据 | playbook 现状 | 判定 → action |
|---|---|---|---|---|
| 02 | web_hint / context_web_on_demand | 证据 0 条 / 无 run | 无该 key（0 条） | 需新增验证 → **needs_fix** |
| 03 | thinking_hint / layer1_adjudication_noise | run 20261020_135317 | L0022 **active** n_ev=21 | 已学习并应用 → **resolve** |
| 04 | action_hint / all_actions_missing | run 20261020_135317 | L0023 **shadow** n_ev=2 | 需新增验证 → **needs_fix** |
| 08 | config_hint / facet_empty | 证据 0 条 / 无 run | L0024 **active** n_ev=18 | 已学习并应用 → **resolve** |
| 28 | carve_first / layer1_citation_low | run 20261020_135317 | L0020 **active** n_ev=24 | 已学习并应用 → **resolve** |
| 29 | rounds_delta / layer1_duty_short | run 20261020_135317 | L0018 **active** n_ev=21 | 已学习并应用 → **resolve** |

- 关键事实：V1.30.0 真跑（2026-10-22 11:32）`playbook.mode="on"`，`playbook.used` 中 L0022/L0024/L0020/L0018 **全部 `applied:true`** ⇒ 这 4 条候选已在生效面，无需人工 apply。
- L0023（action_hint）仍是 shadow（n_ev=2 < promote_n=3）：补 1–2 次同题真跑让同向证据累到 ≥3，且 quality/cost 双侧不降，即可按 `eml_promote` 自然升 active（不要人工 force）。
- `web_hint` 未入库且证据 0 条：先做同题 A/B（打开 research_evidence/research_precedent/duel_arbitration 三个联网 stage）再决定是否入库；直接 apply 会拉高联网成本，违反项目「单变量、先验证」门禁。

## 5. 建议执行顺序（需用户授权后再动提案状态）

1. **先关噪声（reject 11）**：`POST /api/dsh/proposals/<id>/resolve` `{"action":"reject","reason":"<本报告对应行证据摘要>"}`；预期 pending 29→18。
2. **再关已解决（resolve 15）**：同端点 `{"action":"superseded","reason":"已修复/已学习/历史跑次不复现：<证据>"}`；预期 pending 18→3。
3. **只留 3 条 needs_fix**（#2/#4/#5）：先 `POST .../plan` 补 ≥40 字非占位方案（本报告 3.3 已给验证方案），按计划跑验证；验证通过再 `confirm`/`approve`，EML 两条交给学习闸自然晋升。
4. **不建议**：对 4 条已 active 的 EML 重复 apply（会重复写控制面、污染学习库）；对 benign/夹具类提案 `approve`（浪费 DSH 修复额度且必然 failed）。

> 当前 `dgtf_memory/agent_autopilot.json` 为 `enabled=false`，自动闭环不会自行执行上述状态变更；`approve` 会真实调用 DSH 修复 + 门禁（Fast Gate/acceptance），本轮审计不触发。

## 6. 未决 / 风险 / 另立小改进

1. **源产物缺失**：5 个 source_run 的产物已被回收（`outputs` 下 0 文件）：`20261020_143748`、`20261020_145244`、`20261020_153113`、`20261021_142945`、`20261021_182929`。相关条目的判定依据是「引擎代码语义 + 历史队列结果 + 2026-10-22 V1.30 真跑」而非逐字节复核原跑次；如需更强证据，重跑同题即可。
2. **批次循环风险**：29 条同名任务均已 expired 3–6 次；本次若不一次性 reject/resolve，仍会按 TTL 再过期重进。
3. **另立小改进（不在本 29 条内）**：a) `agent_bridge.build_tasks` 的 `api_gap` 仅在 `web_enabled=true` 时入队（当前 web=false 的跑次必然 0 tools_calls）；b) `process_ledger` 任务入队前过滤 mock/smoke 文本并强制保留 `source_run`（`smoke_test.py:248/260` 的夹具文本曾进队列，见 #27）。

## 7. 只读复现命令（token 不会打印）

```powershell
# 1) 拉 29 条 pending（token 仅从文件读入请求头参数，不 echo）
python - <<PY
import json, ssl, urllib.request
tok = open("dgtf_memory/.access_token", encoding="utf-8").read().strip()
ctx = ssl._create_unverified_context()
url = "https://127.0.0.1:8765/api/dsh/proposals?t=" + tok
d = json.loads(urllib.request.urlopen(url, timeout=20, context=ctx).read())
print(len([p for p in d["proposals"] if p["status"] == "pending"]), "pending")
PY
# 2) 学习库/代码证据
#    python -c "import json;print([ (e.get("id"),e.get("status")) for e in map(json.loads, open("dgtf_memory/playbook.jsonl",encoding="utf-8"))])"
#    rg -n "probe_link_dangling|expand_imbalanced_benign|all_closure_unavailable" 元DGTF-V1.30.0.py
```

## 附录 A · 29 条完整提案 ID 对照

| # | id | 判定 → action |
|---|---|---|
| 01 | `prop-1792647593497-50346c` | 历史已修复 → `resolve` |
| 02 | `prop-1792647593498-d30bf5` | 需新增验证 → `needs_fix` |
| 03 | `prop-1792647593483-4f48c1` | 已学习并应用 → `resolve` |
| 04 | `prop-1792647593485-1135dd` | 需新增验证 → `needs_fix` |
| 05 | `prop-1792647593496-a17c3c` | 仍是真问题 → `needs_fix` |
| 06 | `prop-1792647593505-60d405` | 已关闭（良性读数） → `reject` |
| 07 | `prop-1792647593503-d2f46d` | 已关闭（无源/不可复现） → `reject` |
| 08 | `prop-1792647593499-c440fb` | 已学习并应用 → `resolve` |
| 09 | `prop-1792647593504-ed0929` | 历史已修复（细化） → `resolve` |
| 10 | `prop-1792647593508-45d034` | 已关闭（层相关正常读数） → `reject` |
| 11 | `prop-1792647593511-25c91b` | 已关闭（当前配置不复现） → `reject` |
| 12 | `prop-1792647593507-261625` | 历史已修复 → `resolve` |
| 13 | `prop-1792647593510-e97115` | 已关闭（裁层预期读数） → `reject` |
| 14 | `prop-1792647593509-2ccc48` | 已关闭（诊断读数+已有回写） → `reject` |
| 15 | `prop-1792647593513-50ce99` | 已关闭（场景性读数） → `reject` |
| 16 | `prop-1792647593514-1a8095` | 历史跑次已不复现 → `resolve` |
| 17 | `prop-1792647593519-d81190` | 历史已处理（良性） → `resolve` |
| 18 | `prop-1792647593512-3526fa` | 历史已修复 → `resolve` |
| 19 | `prop-1792647593518-2b53a4` | 验证完成 → `resolve` |
| 20 | `prop-1792647593517-1e9927` | 历史已修复 → `resolve` |
| 21 | `prop-1792647593520-03e3cf` | 已关闭（诊断读数+已有回写） → `reject` |
| 22 | `prop-1792647593525-af4cf4` | 历史已修复 → `resolve` |
| 23 | `prop-1792647593526-414c84` | 已关闭（诊断读数+已有回写） → `reject` |
| 24 | `prop-1792647593527-e4bff4` | 已关闭（引擎判定良性） → `reject` |
| 25 | `prop-1792647593529-cb05cb` | 历史已修复 → `resolve` |
| 26 | `prop-1792647593530-a9183d` | 历史已修复 → `resolve` |
| 27 | `prop-1792647593500-566e00` | 已关闭（夹具噪声） → `reject` |
| 28 | `prop-1792647593482-92f2fc` | 已学习并应用 → `resolve` |
| 29 | `prop-1792647593481-94b3aa` | 已学习并应用 → `resolve` |

## 附录 B · 关键证据索引

- 引擎判定/生成点：`元DGTF-V1.30.0.py` — probe_link E4 `14413-14416`；E3 covers `14395-14411`；结构性一致 `14568-14574`；expand benign `14518-14523`；too_many_amp `14526-14528`；no_amp `14551-14557`；unsaid `14794-14795`；action_incomplete/not_do `20793-20825`；all_closure flags `22679-22687`；duty_short `20767-20773`；EML applier `22948-23135`；promote 闸 `2896, 3378-3408`；candidates_backfilled `1278-1290, 10980-11010`。
- 学习库：`dgtf_memory/playbook.jsonl`（30 条；active：L0001/L0003/L0004/L0006-L0012/L0014-L0022/L0024/L0027/L0028）。
- 近期真跑：`outputs/20261022_113206_元DGTF是什么？.packed.json`（V1.30.0；flags=duty_short/polarity_all_same_structural(0)/probe_link_dangling(1)；api_usage.tools_calls=4；playbook.mode=on）；`outputs/20261022_091935_…packed.json`（route=0 → all_closure_unavailable 例证）；`outputs/20261021_183125_…packed.json`（薄跑 closure gaps 例证）。
- 历史提案：`dgtf_memory/dsh_proposals/_index.json`（197 条总账，29 pending；同名 expired 3–6 次）；已 applied 证据：`prop-1792498929255-024a9e`（probe_link 误报，commit 0282bbf）、`prop-1792647593522-ec379f`（polarity structural 已 applied，含 structural_diversity 门禁）。
- 队列闸：`dgtf_v2/agent_bridge.py:10-28`（fixture/空 run 过滤）；夹具文本源：`smoke_test.py:248,260`。
- 常驻消费：`dgtf_memory/agent_daemon.log`（2278 行，cycle≥114，含 triaged/proposals 落盘）。
