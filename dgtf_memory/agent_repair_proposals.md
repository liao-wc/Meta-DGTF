# Agent 修复提案（只提案，不自动 apply）

## 验证/应用 EML 候选：rounds_delta
- kind: `eml_candidate`
- severity: `med`
- source_run: `20261020_135317`
- detail: {"kind": "schedule", "cond": {"issue": "both_unresolved"}, "action": {"key": "rounds_delta", "layer": "both", "delta": 1}, "readings": {"before": {"both_threads": 4, "unstable": 3}, "after": {"both_threads": "期望收敛"}}, "why": "both 仍有未裁定张力/未稳定悬置", "confidence": 0.4586, "evidence": ["20261020_134230"], "source": "engine/both-all"}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 验证/应用 EML 候选：thinking_hint
- kind: `eml_candidate`
- severity: `med`
- source_run: `20261020_135317`
- detail: {"kind": "probe", "cond": {"issue": "both_tension_high"}, "action": {"key": "thinking_hint", "stages": ["ing", "adjudicate_sub_tristate"], "value": "enabled"}, "readings": {"before": {"both_threads": 4}, "after": {"tension": "期望下降"}}, "why": "both 张力多 ⇒ 加深对撞/裁决思考", "confidence": 0.399, "evidence": ["20261020_134230"], "source": "engine/both-all"}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 验证/应用 EML 候选：carve_first
- kind: `eml_candidate`
- severity: `med`
- source_run: `20261020_135317`
- detail: {"kind": "probe", "cond": {"issue": "all_residual"}, "action": {"key": "carve_first", "layers": ["all"]}, "readings": {"before": {"residual": 6, "core_gap": false}, "after": {"residual": "期望下降"}}, "why": "all 有残余风险/核心缺口", "confidence": 0.3547, "evidence": ["20261020_134230"], "source": "engine/both-all"}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 验证/应用 EML 候选：thinking_hint
- kind: `eml_candidate`
- severity: `med`
- source_run: `20261020_135317`
- detail: {"kind": "guard", "cond": {"issue": "self_channel_noisy"}, "action": {"key": "thinking_hint", "stages": ["self_check", "manifest"], "value": "enabled"}, "readings": {"before": {"self_flags": ["duty_short", "probe_link_dangling(2)"]}, "after": {"flags": "期望下降"}}, "why": "self 通道出现复述/职责/停滞线索 ⇒ 加深自检与清单", "confidence": 0.2681, "evidence": ["20261020_134230"], "source": "engine/both-all"}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 验证/应用 EML 候选：rounds_delta
- kind: `eml_candidate`
- severity: `med`
- source_run: `20261020_135317`
- detail: {"kind": "schedule", "cond": {"issue": "layer1_duty_short"}, "action": {"key": "rounds_delta", "layer": "1", "delta": 1}, "readings": {"before": {"duty_S": 0.1778}, "after": {"duty_S": "期望上升"}}, "why": "1 层职责不足 ⇒ 研究层多一圈逼近", "confidence": 0.2405, "evidence": ["20261020_134230"], "source": "engine/both-all"}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 验证/应用 EML 候选：carve_first
- kind: `eml_candidate`
- severity: `med`
- source_run: `20261020_135317`
- detail: {"kind": "probe", "cond": {"issue": "layer0_duty_short"}, "action": {"key": "carve_first", "layers": ["0"]}, "readings": {"before": {"duty_S": 0.1739}, "after": {"duty_S": "期望上升"}}, "why": "0 层职责不足 ⇒ 优先雕修行层", "confidence": 0.2404, "evidence": ["20261020_134230"], "source": "engine/both-all"}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 验证/应用 EML 候选：carve_first
- kind: `eml_candidate`
- severity: `med`
- source_run: `20261020_135317`
- detail: {"kind": "probe", "cond": {"issue": "layer1_citation_low"}, "action": {"key": "carve_first", "layers": ["1"]}, "readings": {"before": {"citations": 0}, "after": {"citations": "期望上升"}}, "why": "1 层子问题无引用 ⇒ 研究层优先补证", "confidence": 0.2362, "evidence": ["20261020_134230"], "source": "engine/both-all"}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 验证/应用 EML 候选：thinking_hint
- kind: `eml_candidate`
- severity: `med`
- source_run: `20261020_135317`
- detail: {"kind": "guard", "cond": {"issue": "layer0_self_noise"}, "action": {"key": "thinking_hint", "stages": ["self_check", "phase_probe"], "value": "enabled"}, "readings": {"before": {"flags": ["probe_link_dangling(2)", "duty_short"]}, "after": {"flags": "期望下降"}}, "why": "0 层自检/复述线索 ⇒ 加深自检与阶段探针", "confidence": 0.2194, "evidence": ["20261020_134230"], "source": "engine/both-all"}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 验证/应用 EML 候选：thinking_hint
- kind: `eml_candidate`
- severity: `med`
- source_run: `20261020_135317`
- detail: {"kind": "guard", "cond": {"issue": "layer1_adjudication_noise"}, "action": {"key": "thinking_hint", "stages": ["assess_decidability", "adjudicate_sub_tristate"], "value": "enabled"}, "readings": {"before": {"flags": ["probe_link_dangling(2)", "duty_short"]}, "after": {"flags": "期望下降"}}, "why": "1 层裁决/可判定噪声 ⇒ 加深该环节思考", "confidence": 0.2194, "evidence": ["20261020_134230"], "source": "engine/both-all"}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 验证/应用 EML 候选：action_hint
- kind: `eml_candidate`
- severity: `med`
- source_run: `20261020_135317`
- detail: {"kind": "guard", "cond": {"issue": "all_actions_missing"}, "action": {"key": "action_hint", "name": "landing_decision", "value": true}, "readings": {"before": {"actions": 0, "decision": true}, "after": {"actions": "期望 >0"}}, "why": "all 有决策但无动作 ⇒ 打开落地决策", "confidence": 0.2008, "evidence": ["20261020_134230"], "source": "engine/both-all"}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：duty_short
- kind: `quality_flag`
- severity: `low`
- source_run: `20261020_135317`
- detail: duty_short
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：probe_link_dangling(2)
- kind: `quality_flag`
- severity: `low`
- source_run: `20261020_135317`
- detail: probe_link_dangling(2)
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 验证/应用 EML 候选：web_hint
- kind: `eml_candidate`
- severity: `med`
- source_run: ``
- detail: {"kind": "guard", "cond": {"issue": "context_web_on_demand"}, "action": {"key": "web_hint", "stages": ["research_evidence", "research_precedent", "duel_arbitration"], "value": true}, "readings": {"before": {"context_score": 0}, "after": {"context": "期望上升"}}, "why": "context 通道无证据 ⇒ 按需放开取证/先例/仲裁联网", "confidence": 0.1823, "evidence": [], "source": "engine/both-all"}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 验证/应用 EML 候选：config_hint
- kind: `eml_candidate`
- severity: `med`
- source_run: ``
- detail: {"kind": "probe", "cond": {"issue": "facet_empty"}, "action": {"key": "config_hint", "key_name": "external_input.facet_queries", "value": 4}, "readings": {"before": {"facets": 0}, "after": {"facets": "期望 >0"}}, "why": "0 层侧面为空 ⇒ 下一跑提高侧面检索数", "confidence": 0.1823, "evidence": [], "source": "engine/both-all"}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 层 1 过程标准未达标
- kind: `process_gap`
- severity: `high`
- source_run: ``
- detail: {"rounds": 1, "product_chars": 199, "product": "这是一段用于冒烟测试的中文输出文本，长度足够通过各类检查。它不需要有真实含义，只要不触发解析分支的异常即可。\n\n## 七、原始问题覆盖率\n无 decidable 子问题（可判定通道不适用）。\n研究层不可判定通道：清晰度 0.00（模型自评，累计 1 次记录）｜独立度 —（无独立结构，不可计算）｜对齐覆盖率 0.00（代码实算，已对上 0/1 个不可判定方面）｜结构覆盖率 —（无结构，不可计算）\n", "standard_ok": false, "fact_ok": true, "citations": 0, "decidability": "empty", "decidability_bad": 0, "external_refs": 0, "external_reference": 0, "evidence_ids": [], "deps": ["0", "external_facets"], "inputs": ["0", "external_facets"]}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 层 all 过程标准未达标
- kind: `process_gap`
- severity: `high`
- source_run: ``
- detail: {"rounds": 0, "product_chars": 0, "product": "", "standard_ok": false, "fact_ok": true, "citations": 0, "decidability": null, "decidability_bad": 0, "external_refs": 0, "external_reference": 0, "evidence_ids": [], "deps": ["0", "1", "both"], "inputs": ["0", "1", "both"]}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：candidates_backfilled(sc:5)
- kind: `quality_flag`
- severity: `low`
- source_run: ``
- detail: candidates_backfilled(sc:5)
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：expand_imbalanced
- kind: `quality_flag`
- severity: `low`
- source_run: ``
- detail: expand_imbalanced
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：no_amp_candidates
- kind: `quality_flag`
- severity: `low`
- source_run: ``
- detail: no_amp_candidates
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：position_all_same_structural
- kind: `quality_flag`
- severity: `low`
- source_run: ``
- detail: position_all_same_structural
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：probe_link_dangling(1)
- kind: `quality_flag`
- severity: `low`
- source_run: ``
- detail: probe_link_dangling(1)
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：too_many_amp_candidates(100%)
- kind: `quality_flag`
- severity: `low`
- source_run: ``
- detail: too_many_amp_candidates(100%)
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：unsaid_overused(4)
- kind: `quality_flag`
- severity: `low`
- source_run: ``
- detail: unsaid_overused(4)
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：all_closure_unavailable
- kind: `quality_flag`
- severity: `low`
- source_run: ``
- detail: all_closure_unavailable
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## Tool Calls 未触发，排查预检/配置
- kind: `api_gap`
- severity: `med`
- source_run: ``
- detail: {"search_calls": 0, "fetch_calls": 0, "fetch_fails": 0, "fetch_used": 0, "vision": false, "tools_calls": 0, "tools_text": false, "web_enabled": false}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：ing_rephrased_direct(100%)
- kind: `quality_flag`
- severity: `low`
- source_run: ``
- detail: ing_rephrased_direct(100%)
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：no_amp_at_all
- kind: `quality_flag`
- severity: `low`
- source_run: ``
- detail: no_amp_at_all
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：all_closure_gaps
- kind: `quality_flag`
- severity: `low`
- source_run: ``
- detail: all_closure_gaps
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 层 both 过程标准未达标
- kind: `process_gap`
- severity: `high`
- source_run: ``
- detail: {"rounds": 0, "product_chars": 0, "product": "", "standard_ok": false, "fact_ok": true, "citations": 0, "decidability": null, "decidability_bad": 0, "external_refs": 0, "external_reference": 0, "evidence_ids": [], "deps": ["0", "1"], "inputs": ["0", "1"]}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：ing_rephrased_direct(50%)
- kind: `quality_flag`
- severity: `low`
- source_run: ``
- detail: ing_rephrased_direct(50%)
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：core_audit_gaps
- kind: `quality_flag`
- severity: `low`
- source_run: `E2E_1792476024`
- detail: core_audit_gaps
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 层 0 过程标准未达标
- kind: `process_gap`
- severity: `high`
- source_run: `RS4`
- detail: {"rounds": 0, "product_chars": 0, "product": "", "standard_ok": false, "fact_ok": true, "citations": 0, "decidability": null, "decidability_bad": 0, "external_refs": 0, "external_reference": 0, "evidence_ids": [], "deps": ["external_facets"], "inputs": ["external_facets"]}
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## app ????
- kind: `user_task`
- severity: `med`
- source_run: `app_user`
- detail: ?? Tool Calls ??
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## daemon live probe
- kind: `user_task`
- severity: `low`
- source_run: `None`
- detail: 验证常驻消费
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：polarity_all_same_structural(1)
- kind: `quality_flag`
- severity: `low`
- source_run: `20261020_143748`
- detail: polarity_all_same_structural(1)
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：unsaid_overused(5)
- kind: `quality_flag`
- severity: `low`
- source_run: `20261020_143748`
- detail: unsaid_overused(5)
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：polarity_all_same_structural(0)
- kind: `quality_flag`
- severity: `low`
- source_run: `20261020_145244`
- detail: polarity_all_same_structural(0)
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：probe_link_dangling(3)
- kind: `quality_flag`
- severity: `low`
- source_run: `20261020_145244`
- detail: probe_link_dangling(3)
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：probe_no_target_covered
- kind: `quality_flag`
- severity: `low`
- source_run: `20261020_145244`
- detail: probe_no_target_covered
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 质量线索：unsaid_overused(7)
- kind: `quality_flag`
- severity: `low`
- source_run: `20261020_153113`
- detail: unsaid_overused(7)
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 根据生成的提案执行任务
- kind: `user_task`
- severity: `med`
- source_run: `app_user`
- detail: 根据生成的提案执行任务
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 修正事实摘要把“更新日”写成“发布日期”的越权断言
- kind: `user_task`
- severity: `high`
- source_run: `dsh_auto`
- detail: 队列里两条 high 过程缺口来自 source_run 为 RS4/空 的夹具跑，最新真跑 outputs/20261020_154010 四层 standard_ok 已全通过，真正该修的是它的结论越权：摘要写“事实答案：2026-10-17（官方源 18 条）”，但同一跑 claim 表承认 W8 只记 only upgrades、W11 是 is here 而非 release、W13/W14 是“已更新至/已同步变更”，无任何官方源出现“发布”动词，且 0 层仍留着 2026-09-10 权重上线/API GA 的未决备选日。根因在 元DGTF-V1.30.0.py 约 21562-21567 无条件前置“已核实事实：发布日期 %s”，save_result 约 27397 又直接渲染“事实答案”，谓词未与证据动词对齐。请加谓词-证据一致性闸：证据无发布/上线/release 动词时，改为“官方于 2026-10-17 更新/升级至该版本，发布时间无官方记录”，并把 09-10 备选与口径差异写进结论；补 smoke 回归（仅“已升级至”证据的 fact 卡不得渲染“发布日期”）。验收：同题重跑，摘要不再称 10-17 为发布日、09-10 备选可见、四层事实达标不回退。
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 给 Agent 队列加来源可信度闸：夹具跑与空标题任务不得入队
- kind: `user_task`
- severity: `med`
- source_run: `dsh_auto`
- detail: 证据：队列 42 条中两条 high 过程缺口（层 both、层 0）的 source_run 为 RS4，detail 里 rounds=0、product=""，属夹具空跑；而最新真跑 outputs/20261020_154010 四层 standard_ok 全为 True。另有 source_run=app_user 的 "app ???? / ?? Tool Calls ??" 占位任务，以及重复的「根据生成的提案执行任务」。根因：dgtf_v2/agent_bridge.py 的 build_tasks（约 35-45 行）对所有 packed 无条件产出 process_gap，未复用 dgtf_v2/bridge.py:65 的 TEST_RUN_PREFIXES 过滤；append_task（约 76-82 行）只追加、不去重、不校验 title；dgtf_app/server.py 1064-1075 接受空标题，_auto_submit_task（578-601）解析失败时回落成通用任务。建议：1) 在 build_tasks/enqueue 统一判定 run 来源（复用 TEST_RUN_PREFIXES + 显式夹具 id 表），夹具来源的 process_gap 不入主队列，改写 fixture_tasks 旁路日志；2) append_task 拒绝空标题或纯 ? 占位符并返回明确错误，按 kind+title 去重；3) _auto_submit_task 解析失败时不再写入队列。验收：重放 RS4 与 E2E_ 的 packed 不再产生 high 过程缺口；面板提交空标题被拒；队列中不再出现 ????；20261020_154010 的真跑缺口仍能正常入队。
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 修正 probe_link_dangling 误报，并让 standard_ok 反映线索闭合
- kind: `user_task`
- severity: `med`
- source_run: `dsh_auto`
- detail: 证据：最新真跑 outputs/20261020_154010_DeepSeek-V41-Flash-.packed.json 的 process_ledger.standard_all=True、四层 standard_ok 全为 True，报告第 49 行据此印出「四层标准 ✅」，第 9 行印出「事实答案 2026-10-17（官方源 18 条）」；但同一个结果包的 quality.flags 仍有 duty_short、polarity_all_same_structural(1)、probe_link_dangling(2)、probe_link_dangling(3)、unsaid_overused(7)，报告第 268/276 行还自己承认「4 条不可判定（其中 1 条无池内追溯）」「理由不成立，但留在了产物里」。其中 probe_link_dangling 是系统性误报：元DGTF-V1.30.0.py 13611-13625 用 probe.link 文本里是否出现池内 id 来判定悬空，而 0 层 3 条、1 层 2 条 probe 的 link 全是散文（“对照两处文体…”“直接定 T4/T11…”），计数恰好等于探针数 3/2，并非真悬空。根因：dgtf_v2/process_ledger.py 38-67 的 standard_ok 只看 product 非空、fact_ok（1 层再加 citations/audit），完全不看 quality.flags 与无追溯项；dgtf_v2/agent_bridge.py 35-41 又只按它产出 process_gap，于是「绿标」与未闭合线索并存。建议：1) E4 只校验显式 id 引用（新增 link_ids 或复用 covers），散文 link 不记 dangling；2) 新增 closure
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。

## 禁止输入自检在无证据时断言型号“不存在”，并与事实卡对账
- kind: `user_task`
- severity: `high`
- source_run: `dsh_auto`
- detail: 证据：outputs/20261020_154010_DeepSeek-V41-Flash-.packed.json 的 input_sanity.issues[0] 写「DeepSeek-V4.1-Flash-1017 — 形似标准模型版本号，但该型号不存在，属虚构记号」；同一包的 fact_contract.ok_all=true，四层 answer=2026-10-17、ledger.source=official_preflight，报告第 9/22 行给出「事实答案 2026-10-17（官方源 18 条）」，第 270 行却又判该型号为虚构记号；而官方 10-17 条目正文本身即写 upgraded to DeepSeek-V4.1-Flash-1017。根因：元DGTF-V1.30.0.py 第 23148 行在检索前调用第 24201 行的 _check_input_sanity，该步只把问题串交给 LLM 先验判断（24213-24239 的提示还专门要求抓「形似标准记号的非标准记号」），结果原样写入 packed 并由 27994-28003 无条件渲染，全程不与检索后的 fact_contract/官方证据对账，于是「预检没认出」被升级成「不存在」的存在性断言。建议：1) 预检措辞降级为「本地先验未识别，待证据核验」，禁止输出「不存在/虚构」这类存在性断言；2) 检索后加对账：fact_contract.ledger.known 且官方证据命中该 term（或 answer_hit）时，把该 issue 标记为 resolved 并从告警区移除；证据冲突时改写为「官方源对该型号的命名/存在性有冲突」；3) 报告出口加互斥闸：同一产物不得同时出现「不存在/虚构」与「官方事实答案」。回归验收：重放 154010，input_sanity 不再称其不存在、报
- 建议: 先复现/补证据，再由 DSH Agent 生成 patch 并跑门禁。
