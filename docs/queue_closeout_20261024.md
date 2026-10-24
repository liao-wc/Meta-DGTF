# 高严重度队列核验关闭（2026-10-24）

- **执行**：DSH Agent · `precheck-queue`（共享任务 `task-2`，Lead 复核）
- **对象**：`dgtf_memory/agent_tasks.jsonl` 中 **6 条 high**（4 条 `process_gap` + 2 条 `user_task` high）
  + 1 条同类误报 `024a9eadf0dc`（med，与 probe_link_dangling 同主题）→ 共 **7 条核验关闭**
- **结果**：7 条 `status=closed` 已**追加**到 `dgtf_memory/agent_results.jsonl`
  （只追加、不删除旧 `triaged` 记录；45 → 52 行，原 9768 字节前缀逐字节不变）
- **队列现状**：剩余 43 行（unique id 37），**high 归零**；余 16 med / 27 low
  （按 kind：quality_flag 26、eml_candidate 12、user_task 4、api_gap 1）
- **边界**：未 commit/push；未跑全量真跑、未跑全量测试；未改引擎/App/其他文件
- **新增工具**：`scripts/precheck_quality.py`（离线质量门预检，见文末附录 A）

---

## 一、核验手段（离线、可复算、零真跑）

1. **新脚本 `scripts/precheck_quality.py`**：读一份 packed，用引擎同源判据重算五道质量门
   （G1 process_ledger / G2 core audit / G3 meta_closure / G4 研究层判定审计 / G5 quality），
   逐项 PASS/FAIL + 原因，退出码 0/1，支持 `--json`。
2. **最新真跑对照**：`outputs/20261024_134620_为什么城市热岛效应在夜间比白天更明显.packed.json`
   （mtime 13:46:21）→ precheck **PASS 5/5**：
   - G1 `standard_all=True`（0/1/both/all 四层 `standard_ok` 全 true）
   - G2 `audit_packed`：ok=True，gaps=[]、overreach=[]、repairs=[]
   - G3 meta closure：clean=True、unsettled=0、uncovered=[]
   - G4 判定审计：存证 verified(n=6,bad=0)，重算 verified(n=6,bad=0)
   - G5 quality：answer_ready=True、process_ready=True、answer_quality=verified
3. **V2.2.1 源码判据核验**（工作树 `dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.1.py`；
   下文行号以 2026-10-24 14:17 左右的工作树为准，引擎发布收尾时如再改动以字符串判据为准）。
4. **判据回归**：`dgtf_v2/tests_input_sanity.py` 定向跑 → **PASS 22 / FAIL 0**（含 154010 真产物回放）。

---

## 二、逐条关闭依据

### 2.1 四条 `process_gap`：旧夹具跑残留（已被 V2.2.1 真跑覆盖）

| task_id | 标题 | source_run | detail 自证（夹具痕迹） |
|---|---|---|---|
| `566e00a3136b` | 层 1 过程标准未达标 | `""` | rounds=1、product_chars=199、citations=0、decidability=empty；product 正文为「这是一段用于冒烟测试的中文输出文本…」 |
| `b049d4a5b566` | 层 all 过程标准未达标 | `""` | rounds=0、product_chars=0、product="" |
| `a8e87267b942` | 层 both 过程标准未达标 | `""` | rounds=0、product_chars=0、product="" |
| `9597cde03f2c` | 层 0 过程标准未达标 | `"RS4"` | rounds=0、product_chars=0、product=""；RS4 命中夹具前缀 |

**共同核验证据（三条并用）**：

1. **任务自证**：source_run 为空或 `RS4`，detail 里 rounds=0 / product 空 / 冒烟测试文本，
   都是夹具空跑形态，不是真跑四层产物。V2.2.1 `dgtf_v2/agent_bridge.py:11-13` 的
   `FIXTURE_RUN_PREFIXES`、`:20-22` 的 `_is_fixture_run` 对空 run_id 与
   `rs4/fixture/smoke/pytest/E2E_/probe` 等前缀一律判夹具，`:27-29` 直接不入队；
   这些历史条目是旧代码入队后**残留**的存量行。
2. **最新真跑复核**：`outputs/20261024_134620` 重算 `process_ledger.standard_all=True`、
   四层 `standard_ok` 全 true；`core_duty.audit_packed` gaps=[] / overreach=[] / repairs=[]；
   precheck G1、G2 均 PASS。即 V2.2.1 真跑已不再产生这四类"过程标准未达标"。
3. **真跑未再入队**：2026-10-23~24 新增队列项只有 low 级 `quality_flag`，
   没有新的 high `process_gap`。

> 结论：4 条 process_gap 均非当前引擎真跑的活跃缺口，关闭。

### 2.2 `e6073923cb88`：事实摘要把「更新日」写成「发布日期」（high）

**修复前存证**（历史产物 `outputs/20261020_154010_DeepSeek-V41-Flash-.packed.json`）：
`decision_trace.reasoning.answer` 开头写「已核实事实：发布日期 2026-10-17（官方源）」，
同一段却又自认「但「发布」动作的时点在官方文档中无记录位，无法给出」——谓词与证据动词不对齐。

**V2.2.1 落点（源码核验）**：

- `Meta-DGTF-V2.2.1.py:22949-22956`：事实卡 answered 时，推理摘要改为
  「已核实事实：**官方记录日期 %s（发布/更新口径见正文）**。%s」，不再无条件前置「发布日期」。
- `:29030-29034`：报告头印「**事实日期（官方记录）**: …（官方源 N 条；发布/更新口径见正文）」。
- `:29060-29062`：检索/推理日期口径差异标为「➖ 日期口径差异（不阻断事实答案）」。

> 关闭判据：**谓词-证据对齐**——证据里没有「发布/release」动词时，只称「官方记录日期」并把
> 发布/更新口径交给正文，不再把 10-17 断言成发布日。
> 降级说明：原提案的「09-10 备选显式可见」未作为独立字段落地（属降级实现），
> 但「发布日期 vs 更新日」的越权断言已由上述口径消除，故按 V2.2.1 判据关闭。

### 2.3 `2cbe2168e82e`：输入自检无证据断言型号「不存在」（high）

**修复前存证**（历史产物 `outputs/20261020_154010`）：
`input_sanity.issues[0].why` =「形似标准模型版本号，但**该型号不存在，属虚构记号**」，
与同一包 `fact_contract.ok_all=true`、官方事实答案 2026-10-17 互相打架。

**V2.2.1 判据（`dgtf_v2/input_sanity.py`）**：

- `neutralize_negative_claims`：`NEGATIVE_CLAIM_RE` 命中「不存在/虚构/捏造/伪造/未发布…」时，
  一律降级为「本地先验未识别，待证据核验」（`NEUTRAL_WHY`），写 `negative_claim_rewritten`、
  `evidence_required` 留痕；`term` 本身是否定断言则整条剔除（`term_dropped`）。
- `reconcile`（检索后对账）：官方证据命中 → `resolved` 并移出告警区；官方证据明确否认 →
  「官方源对该型号的命名/存在性有冲突」；有官方检索但未命中 → 只写
  「检索到的官方源中**未见**该记号，存在性待核」（`RETRIEVED_MISS_WHY`），仍不是「不存在」；
  fact_contract 已确认且 answer_hit → 按提案兜底清除。
- `negative_gate`：出口互斥闸（规则名「否定断言需证据」），对账后仍含否定断言即强制中性化。

**判据回归**：`python -c "import dgtf_v2.tests_input_sanity as t; raise SystemExit(t.main())"`
→ **PASS 22 / FAIL 0**。其中含 `outputs/20261020_154010` **真产物回放**（source=real）：
issue 被清除、`resolved_n>=1`、对账后无否定断言、事实答案 2026-10-17 不回退、
`negative_gate.ok=True`；另覆盖「查无实据只能用『未见』」「官方源冲突」「短记号不误命中」
「否定 term 整条剔除」「answer_hit 兜底」等。

> 结论：无证据的存在性断言与跨段互斥问题已由确定性判据 + 回归用例关闭。

### 2.4 `024a9eadf0dc`：`probe_link_dangling` 误报（med，同主题并案关闭）

**修复前**：旧引擎把散文形式的 `probe.link`（如「对照两处文体…」「直接定 T4/T11…」）也当悬空，
按探针数挂 `probe_link_dangling(N)` 质量旗（false positive）。

**V2.2.1 落点（源码核验）**：

- `Meta-DGTF-V2.2.1.py:14878-14882`：只有确实带 id 形态的 `link`（`A1/T2/probe#3/amp#4` 等）
  才做编号反查，散文 link 直接跳过，不再误报。
- `:14890-14899`：target 不在池内 ⇒ 记 `link_original`、`link` 置空，`view.meta` 写
  「[QC] 探针 link 悬空 N 条：target 不在池内，**已置空留痕（不挂旗；未对齐合法）**」。
- 静态核验：V2.2.1 全文已无 `flags.append("probe_link_dangling")`
  （`Meta-DGTF-V2.2.0.py:14762` 仍有）→ 误报旗不再产生。

**留痕说明**：历史产物 `outputs/20261024_134620`（13:46，早于当前工作树该修复）仍带
`probe_link_dangling(1)/(2)` 旧旗，属修复前置产物；待下一次 V2.2.1 真跑确认消失。

> 遗留观察（不阻塞本条的误报部分）：原提案的「`standard_ok = struct_ok AND closure_ok`」
> 第二部分未落地——`process_ledger` 仍只判结构/证据/判定审计，未纳入线索闭合。
> 该部分建议另立条目跟踪。

---

## 三、仍开放项（关闭后队列）

- **`940c8d165eed`（med，user_task）给 Agent 队列加来源可信度闸**：**保持开放**（Lead 指定）。
  现状：`dgtf_v2/agent_bridge.py` 已有 `FIXTURE_RUN_PREFIXES/_is_fixture_run`（build_tasks 夹具跳过）、
  `append_task` 已拒绝空标题/占位/重复；但**缺少夹具过滤的回归用例**、面板提交空标题路径
  （`dgtf_app/server.py`）与「重放 RS4/E2E_ packed 不再产生 high 缺口」的验收尚未做，故不关闭。
- **`25c91baef5ec`（med，api_gap）**：Tool Calls 未触发，待 API 配置/触发条件排查（本次不动引擎）。
- **`3b97b8164147` / `8e84dfd76bc8`（med，user_task 占位/自指）**：`append_task` 现已拒绝该类标题，
  存量行保留观察。
- **`2b53a4418035`（low，daemon live probe）**：守护消费验证已完成过，历史结论见
  `reports/goal_proposals_plan.md`；不在本任务范围。
- **12 行 `eml_candidate`（med）**：待候选验证/应用闭环（EML 调度候选，非质量问题）。
- **26 行 `quality_flag`（low）**：线索留痕，按 V2.2.1 口径「留痕不拦截」，交后续真跑观察。

---

## 附录 A：`scripts/precheck_quality.py` 四份真跑正负对照

| packed（outputs/） | 预期 | 实测 | 主失败门与关键读数 |
|---|---|---|---|
| `20261024_113505_*.packed.json` | FAIL | **FAIL**（PASS 2/FAIL 3） | G5 fact 硬缺口 `uncovered:` → answer_quality=needs_evidence、ready=False（why 题 fact 未覆盖题面）；G1 层1 未达标（存证判定审计 unverified bad=1）；G4 存证 bad=1（重算 verified，旧产物口径不一致） |
| `20261024_122709_*.packed.json` | FAIL | **FAIL**（PASS 2/FAIL 3） | G3 meta closure clean=False、unsettled=1、未交代「夜间风与稳定度阈值判据」、flags `all_closure_gaps`（all 闭合假缺口）；G1 all 层未达标；G5 ready=False |
| `20261024_130547_*.packed.json` | FAIL | **FAIL**（PASS 2/FAIL 3） | G4 研究层判定审计存证 mixed(n=6,bad=3)：`undecidable_but_evidence_exists` ×2 + 旧口径把 `partial_without_evidence` 记 bad ×1；G1 层1 未达标；G5 ready=False |
| `20261024_134620_*.packed.json` | PASS | **PASS**（5/5） | G1 standard_all=True；G2 gaps/overreach/repairs=[]；G3 clean=True；G4 verified bad=0；G5 ready=True / verified |

三份负对照恰好是 V2.2.1 三处修复（研究层判定审计并入池内子问题、元层汇总后刷新 meta_closure、
判定审计只拦越权断言）**之前**的历史产物，可当回归负样本；134620 为修复后的全绿真跑。

## 附录 B：复现命令

```powershell
cd D:\Meta-DGTF-道生三阶模型
$env:PYTHONPATH = "$PWD;$PWD\dgtf_engine"

# 离线质量门（缺省取 outputs/ 最新 packed）
python scripts/precheck_quality.py
python scripts/precheck_quality.py --packed "outputs/20261024_113505_为什么城市热岛效应在夜间比白天更明显.packed.json"
python scripts/precheck_quality.py --packed "outputs/20261024_122709_为什么城市热岛效应在夜间比白天更明显.packed.json"
python scripts/precheck_quality.py --packed "outputs/20261024_130547_为什么城市热岛效应在夜间比白天更明显.packed.json"
python scripts/precheck_quality.py --packed "outputs/20261024_134620_为什么城市热岛效应在夜间比白天更明显.packed.json" --json

# 输入自检判据回归（定向，不跑全量测试）
python -c "import dgtf_v2.tests_input_sanity as t; raise SystemExit(t.main())"

# 源码判据静态核验
Select-String -Path dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.1.py -Pattern '官方记录日期|置空留痕|link_original'
Select-String -Path dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.1.py -Pattern 'flags\.append\(\"probe_link_dangling'
```

## 附录 C：账本与边界核对

- `dgtf_memory/agent_results.jsonl`：45 行 / 9768 B → **52 行 / 17203 B**；
  追加前后前 9768 字节逐字节相同（只追加）；仍为 UTF-8 无 BOM、CRLF、行尾换行。
- 7 条关闭记录均保留 `task_id/kind/title/source_run`，`status=closed`，
  `action` 写明核验证据与判据/文件行号，`ts` 记录关闭时刻。
- 本次仅新增/修改：`scripts/precheck_quality.py`、`docs/queue_closeout_20261024.md`、
  `dgtf_memory/agent_results.jsonl`（追加）。未 commit/push，未改引擎/App/其他文件。
---

## 附录 D：DSH 全流程闭环追加关闭（2026-10-24 14:44）

> 触发：DSH 接管「全流程闭环」任务（full）。新增一键验收器
> `scripts/dsh_loop_check.py`，先跑出 A2 FAIL（2 条占位标题任务未关闭），
> 按失败信息补齐关闭后复跑 **PASS 5 / FAIL 0 / N/A 0**。

### 本次追加关闭 14 条（agent_results.jsonl 追加，不删旧行）

| task_id | 原线索/任务 | 关闭依据 |
|---|---|---|
| 940c8d165eed | 队列来源可信度闸 | V2.2.1 build_tasks 夹具过滤 + append_task 空/占位标题拒绝与去重；`scripts/dsh_loop_check.py` A/A2 验收 PASS |
| 3b97b8164147 | 占位任务「app ????」 | append_task invalid_title 拒绝；A2 复核队列无未关闭占位项 |
| 8e84dfd76bc8 | 自指任务「根据生成的提案执行任务」 | append_task 显式拒绝清单命中；A2 PASS |
| a17c3c28a05d | duty_short | V2.2.1 按层交付面 + 问项实词 R + floor 0.15 + 元层闭合门；最新真跑离线复算 S=0.36/0.27/0.16/0 |
| 50346c43b03e / 26162523b4d0 / 84871886623d | probe_link_dangling(1/2/3) | V2.2.1 悬空 link 置空 + link_original 留痕，不挂质量旗 |
| d2f46d091b80 / 84797cf9bb0f | candidates_backfilled(sc:5/6) | 收尾复核阈值 0.75 + self-check 单源降为留痕（双源才挂旗） |
| d81190c3ce7f / ec379fc0b563 | polarity_all_same_structural(1/0) | 结构性一致（非坍缩）改 view.meta 留痕，不挂质量旗 |
| 1a809523846f | all_closure_gaps | 元层闭环在池汇总后刷新；最新真跑 meta_closure clean=true |
| 445c639646f8 | core_audit_gaps | 最新真跑 core audit gaps=[]/overreach=[]（precheck G2 PASS） |
| e97115b223a3 | all_closure_unavailable | route 全四层时不再置旗；闭合可审计（precheck PASS） |

### 仍开放（不强行关闭，列人工确认）

- `25c91baef5ec`（api_gap：Tool Calls 未触发）——需联网真跑/配置侧复核，保留；
- 10 条 eml_candidate / 2 条 user_task / 若干 quality_flag 低危观察项（unsaid_overused、too_many_amp_candidates、ing_rephrased_direct 等）——属真实读数或待验证提案，保留观察；
- 本附录不改引擎/App 源码；仅新增 `scripts/dsh_loop_check.py` 与文档，运行数据（agent_results/knowledge）为本地追加。

### 复跑命令

```powershell
$env:PYTHONPATH="$PWD\dgtf_engine"
python scripts/dsh_loop_check.py
```
---

## 附录 E：继续优化（2026-10-24 14:52）——api_gap 复核 + EML 候选对账

### E1. api_gap 25c91baef5ec 复核关闭

- 旧任务 detail：`web_enabled=false, tools_calls=0, search_calls=0`（旧跑未开网，不是链路故障）。
- 最新真跑 `20261024_134620` 的 `api_usage`：**web_enabled=true、tools_calls=4、search_calls=10、tools_text=true**。
- 新增 `scripts/dsh_loop_check.py` **E 检查**（联网/工具调用遥测）：复跑 **PASS**；
  `web_enabled` 为假或 tools/search 全零才判 FAIL。该任务按「前提已不成立」关闭。

### E2. EML 候选对账（12 行 / 6 个 id）

| 候选 id | 条件 | 对账结论 | 处置 |
|---|---|---|---|
| 1135dd11cd09 | all_actions_missing | 最新真跑 all 层 actions=4 ⇒ 条件已不成立 | **closed** |
| d30bf5383297 | context_web_on_demand | web_enabled=true/search=10/tools=4 ⇒ 条件已不成立 | **closed** |
| 94b3aa6d4624 | rounds_delta（both_unresolved / layer1_duty_short） | layer1_duty_short 已由 V2.2.1 duty 修正消除；both_unresolved 需 A/B 真跑验证 | 保留观察 |
| 4f48c1b90872 | thinking_hint（both_tension_high / 3 条 flags 噪声） | flags 类条件已被 V2.2.1 消除；both_tension_high 需 A/B | 保留观察 |
| 92f2fc613a41 | carve_first（all_residual / layer0_duty_short / layer1_citation_low） | duty 条件已消除；all_residual、citation_low 仍成立 | 保留观察 |
| c440fb190a44 | config_hint facet_empty | 需下一跑 facet 读数复核（不允许未验证改配置） | 保留观察 |

### E3. 低危质量读数（保留观察，不伪装关闭）

| 线索 | 生成判据（Meta-DGTF-V2.2.1.py） | 结论 |
|---|---|---|
| unsaid_overused(N) | `_self_check` 中「未说」标记数 > `_lim`（默认阈值）⇒ 探针没真往里推 | 真实自省信号，保留观察 |
| too_many_amp_candidates(P) | 候选→& 转化比 > 该层 `_amp_ratio_max` 上限 | 真实结构信号，保留观察 |

- 这两类线索只在 `quality.flags` 留痕，不拦截质量门（precheck/loop check 均 PASS）；
  若强行关闭会丢失真实读数，因此保留并在本附录登记，不做静默清洗。


