# DSH 全流程闭环（full）执行记录

- 日期：2026-10-24 14:40–15:00
- 阶段标记：**full**
- 执行者：当前 DeepSeek Harness 对话（未启动 headless）
- 边界：只做可安全验证的修复；不删项目数据、不读/外发密钥、不做账户/ACL/系统级改动；
  git commit 由本机 post-commit 钩子自动推送（非显式 push 命令，见剩余风险）。

## 1. 读取（现状快照）

| 面 | 快照 |
|---|---|
| 应用 | health 200；app 2.0.1 / engine 2.2.1 / commit 6275eaf；err 日志 0 行 |
| DSH 守护 | enabled=true、interval=1800s、checks=13、last_error 空；full=1 实时视图正常 |
| 一致性 | ok=True、warnings=[]、engine=2.2.1、v2 事件 658 |
| 队列 | 50 条任务；结果 66 行（closed 21 已含本轮回填）；high 未关闭 0 |
| 提案 | 197 条：superseded 18 / expired 156 / failed 4 / rejected 12 / applied 6 / rolled_back 1，**pending=0** |
| 知识库 | 21 条（本轮前） |
| 依赖/门禁 | fast_gate 12/0、V2 38/38（480 检查）、selftest 371/0、pip check 0 |
| 工作区 | git 干净；origin/main=6275eaf |

## 2. 自我反馈（定位缺口）

- **G1 流程/测试缺口**：队列来源可信度闸（task 940c8d165eed）代码已落地，但缺**可重复验收**，
  该任务一直 open；占位标题历史任务（3b97/8e84）也缺闭环结论。
- **G2 闭环工具缺口**：无「一条命令验收全流程」的检查器（队列闸 + 质量门预检 + App live 视图 + 提案/high 队列）。
- **G3 学习缺口**：知识库缺本轮 V2.2.1 判据修正的外部佐证（raw agreement vs chance-corrected 指标、
  自改进 agent 需要确定性护栏）。
- **G4 质量/依赖缺口**：gates 全绿；最新真跑 precheck 5/5 PASS；无新增依赖缺口。
- **G5 迭代触发**：新检查器首次运行 A2 FAIL（2 条占位标题任务未关闭）→ 转入修复迭代。

## 3. 学习（检索 → 筛选 → 入库）

- 检索 3 个方向：闭环自改进质量门、LLM judge 可靠性（raw agreement vs κ/α）、agent 任务队列卫生。
- 筛选 3 条可复用结论写入知识库（21 → 24 条，追加去重、不重写旧行）：
  1. **LayerLens**：85% raw agreement 仅对应 Cohen's κ≈0.48 ⇒ 原始自一致率会高估质量，
     需 chance-corrected 与 test-retest；直接佐证 V2.2.1 的 tri_ratio → tri_consistency=α 补丁。
  2. **arXiv 2609.02246**：自改进 agent 需要确定性护栏，不能只靠 LLM judge；对应本项目的
     fast_gate / core audit / decidability_audit / precheck_quality。
  3. **arXiv 2607.12790**：评测指标需与人评/交叉视角共同演进；对应 self-check 单源不挂旗（双源才挂）。
- 抓取限制：arxiv 429、github 非公开 IP 被策略拦截 ⇒ 后两条以检索摘要筛选入库（fetched=false，诚实标注）。

## 4. 修复（只做可安全验证项）

1. 新增 `scripts/dsh_loop_check.py`：五面一键验收（A 队列来源闸 / A2 占位标题 / B 质量门预检 /
   C App live 视图 / D 提案与 high 队列），只读 + 临时目录，退出码 0/1，支持 --json。
2. 追加关闭 14 条队列项（agent_results.jsonl 只追加，不删改）：940c8d165eed、3b97b8164147、
   8e84dfd76bc8、duty_short、probe_link_dangling×3、candidates_backfilled×2、
   polarity_all_same_structural×2、all_closure_gaps、core_audit_gaps、all_closure_unavailable。
   依据逐条写入 `docs/queue_closeout_20261024.md` 附录 D。
3. 文档同步：PROJECT_MAP 增加闭环检查入口；README 验证表增加闭环检查行；
   本记录 + 队列关闭附录。

## 5. 验证（门禁）

| 门禁 | 结果 |
|---|---|
| `scripts/dsh_loop_check.py` | **PASS 5 / FAIL 0 / N/A 0** |
| fast_gate | PASS 12 / FAIL 0 |
| V2 全量测试 | 38/38 PASS · 480 项检查 |
| App selftest | PASS 371 / FAIL 0 |
| 依赖 pip check | App / local_model 0 broken |
| 项目路径校验 | RESULT PASS |
| 最新真跑离线预检 | PASS 5/5（134620） |

## 6. 迭代记录

- t0：新增检查器 → **A2 FAIL**（未关闭占位标题 2 条）。
- t1：按失败信息追加 14 条核验关闭（含 940c/占位/已修复线索）。
- t2：复跑 → **PASS 5 / FAIL 0**；其余门禁全绿，停止迭代。

## 6.1 继续优化（2026-10-24 15:00–15:20，用户点开运行中会话无内容反馈）

- **App 2.0.2**：修复「DSH 会话」列表点开正在运行/当前会话时只显示空壳的问题——
  `dsh-current-*` 会话直接打开「DSH 本对话」整段实时镜像；localStorage 不再恢复空壳；
  Agent 面板读库对瞬时 `Failed to fetch` 自动重试 1 次并点名失败库。
  验证：py_compile/node --check 0；health app=2.0.2/engine=2.2.1；页面缓存串 2.0.2-dshlive；selftest 371/0。
- **会话独立记录（用户补充要求）**：每个 `dsh-current-*` 会话按 `start_seq → end_seq`
  （下一会话起点）从 DSH 事件流切出**自身时段**内容；会话列表去重同时段重复记录；
  运行中的会话保持 600ms 轮询实时刷新。实测 20 个当前会话窗口：0 条事件越界、
  0 对窗口重叠，运行会话事件数随轮询更新（仅显示当时那段）。
- **api_gap 25c91baef5ec 复核关闭**：最新真跑 api_usage 显示 web_enabled=true、
  tools_calls=4、search_calls=10；`dsh_loop_check.py` 新增 E 检查（联网/工具调用遥测）PASS。
- **EML 候选对账**：`1135dd11cd09`（all_actions_missing）与 `d30bf5383297`
  （context_web_on_demand）由最新真跑证伪 ⇒ 关闭；其余 4 个 id 的混合条件保留观察。
- **低危质量读数**（unsaid_overused / too_many_amp_candidates）：逐条核对生成判据
  （self-check 未说标记超阈值 / 候选→& 比超该层上限），属真实读数，保留观察，不做静默清洗。
- 第五次四层真跑（2026-10-24 15:27 完成，`20261024_152709`，117 calls / 1,295,308 tokens）：
  * 质量门全绿：answer_ready/process_ready/verified、standard_all=true、core audit OK；
  * 覆盖读数 **0.7857**（basis=decidable_weighted，不再 null）；tri_state=[0,0]（本轮无三态单元，读数为空而非 0.1667）；
  * 质量线索从 5 条降到 **2 条**：`duty_short`、`unsaid_overused(3)`；
    `candidates_backfilled / polarity_all_same_structural / probe_link_dangling` 已消失；
  * api_usage：web_enabled=true、tools_calls=4、search_calls=8；
  * 职责读数：both S=0.304 通过；0/1 层 C=0（交付面用「强度/城乡温差」等同义表述，未逐字覆盖问句
    ⇒ 规则 C 的已知局限，duty_short 保留观察）；all 层 runtime 读数在产物落定前计算（下一步可做
    终局刷新，但需新引擎补丁版本，见剩余风险）；
  * `dsh_loop_check.py` 复跑 **PASS 6 / FAIL 0**（B 用新 packed、E 用新遥测）。

## 7. 剩余风险 / 人工确认

1. `25c91baef5ec`（api_gap：Tool Calls 未触发）需联网真跑/配置侧复核，保留开放。
2. eml_candidate（web_hint/config_hint/action_hint/rounds_delta/thinking_hint/carve_first）等提案
   与 unsaid_overused/too_many_amp_candidates 等低危质量读数保留观察，不强行关闭。
3. 发布标签 V2.2.1 / engine-V2.2.1 / app-V2.0.1 仍未推远端（需人工 push）。
4. 本轮未新增真实 LLM 真跑（成本优化）；判据修正以离线重算 + 单测 + 既有真跑复核为准。
5. post-commit 钩子会自动 push main（本次 commit 如触发，属既定仓库自动化而非显式 push 命令）。
6. DSH 高风险配置（public + danger-full-access + effort=max）未改。
