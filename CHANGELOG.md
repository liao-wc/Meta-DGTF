【V2.2.87（2026-10-30，PATCH · App 透传 flag 对齐门禁；App 2.0.83）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.87.py（__version__=2.2.87；引擎侧零行为差）；
  App 2.0.83 不变。
- ★ 新增 audit_flag_alignment：_ARG_SPEC + _BOOL_FLAGS 共 24 个 flag 必须在当前引擎源码 argparse 中存在；
  gated flag 核对能力探测（未登记能力按源码兜底）；
- ★ fast_gate 新增 flag_alignment（23→24）；acceptance_semantics 同步 24。
- 验收：24 flags violations 0；fast_gate 24/24；acceptance_semantics 45/45；V2 71/71（1210）；
  App selftest；一键验收；e2e 18/18；probe 84/84；发布流程门。零云 API。
- 标签：V2.2.87 / engine-V2.2.87（app-V2.0.83 不变，不移动）。

【V2.2.86（2026-10-30，PATCH · 计划→opts→CLI 全链路契约门禁；App 2.0.83）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.86.py（__version__=2.2.86；引擎侧零行为差）；
  App 2.0.83 不变。
- ★ 新增 audit_plan_pipeline：4 题型 × 4 档 = 16 组合，校验 route/rounds/web、
  profile→--config、结构化值注入后 CLI 非空；violations 0。
- ★ fast_gate 新增 plan_pipeline_contract（22→23）；acceptance_semantics 同步 23。
- 验收：V2 71/71（1210）；App selftest；一键验收；e2e 18/18；probe 84/84；发布流程门。零云 API。
- 标签：V2.2.86 / engine-V2.2.86（app-V2.0.83 不变，不移动）。

【V2.2.85（2026-10-30，PATCH · v2_online 契约门禁；App 2.0.83）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.85.py（__version__=2.2.85；引擎侧零行为差）；
  App 2.0.83 不变。
- ★ 新增 audit_v2_online：ARMS/choose 输出的 route/rounds 必须合法，且经 cli_value 无损转 CLI 串；
  fast_gate 新增 v2_online_contract（21→22）；acceptance_semantics 同步 22。
- ★ 验证：3 臂 + 3 题 choice 全部 OK，violations 0；fast_gate 22/22；acceptance_semantics 45/45。
- 验收：V2 71/71（1210）；App selftest；一键验收；e2e 18/18；probe 84/84；发布流程门。零云 API。
- 标签：V2.2.85 / engine-V2.2.85（app-V2.0.83 不变，不移动）。

【V2.2.84（2026-10-30，PATCH · 动态矩阵预算层级不变式；App 2.0.83）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.84.py（__version__=2.2.84；引擎侧零行为差）；
  App 2.0.83 不变。
- ★ audit_dynamic_matrix 新增两条不变式：紧预算（warn/degrade/critical）必须 fast；
  ok 默认 quality（除非 opt-in prefer_cost）；自检 3→5 个变异体。
- ★ 验证：5/5 mutants caught；36 组合 0 违反；fast_gate 21/21。
- 验收：V2 71/71（1210）；App selftest；一键验收；e2e 18/18；probe 84/84；
  发布流程门 pre/post-tag 全 PASS。零云 API。
- 标签：V2.2.84 / engine-V2.2.84（app-V2.0.83 不变，不移动）。

【V2.2.83（2026-10-30，PATCH · 离线质量门预检预算截断口径；App 2.0.83）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.83.py（__version__=2.2.83；引擎侧零行为差）；
  App 2.0.83 不变。
- ★ 发现：precheck_quality 的 G5 重算不认「体力耗尽（预算截断）」口径，把正确存证误判不一致。
- ★ 修复：重算尊重截断口径；截断产物判 N/A（预算边界不计失败）；正常产物仍 PASS 5/5。
- 验证：截断产物 PASS 4/0/N/A1；正常 verified 产物 PASS 5/0/0；V2 71/71（1210）；fast_gate 21/21。
- 验收：App selftest；一键验收；e2e 18/18；probe 84/84；发布流程门 pre/post-tag 全 PASS。零云 API。
- 标签：V2.2.83 / engine-V2.2.83（app-V2.0.83 不变，不移动）。

【V2.2.82（2026-10-30，PATCH · v2 层质量一致性门禁；App 2.0.83）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.82.py（__version__=2.2.82；引擎侧零行为差）；
  App 2.0.83 不变。
- ★ 脚本巡检：6 个只读校验脚本全 rc=0（含 outputs_retention 3230 files/205 packs/221.4MB）。
- ★ recompute_v2_layer_quality 增加 --check（只读对比层质量，差异 exit 1）；
  fast_gate 新增 v2_quality_consistency（20→21）；acceptance_semantics 同步 21。
- ★ 重算幂等验证：两次执行前后 v2_events SHA256 一致；本轮重算 431 条 schedule_outcome。
- 验收：fast_gate 21/21；acceptance_semantics 45/45；V2 71/71；App selftest；一键验收；
  e2e 18/18；probe 84/84；发布流程门 pre/post-tag 全 PASS。零云 API。
- 标签：V2.2.82 / engine-V2.2.82（app-V2.0.83 不变，不移动）。

【V2.2.81（2026-10-30，PATCH · fast_gate 产物一致性检查；App 2.0.83）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.81.py（__version__=2.2.81；引擎侧零行为差）；
  App 2.0.83 不变。
- ★ 只读脚本冒烟审计：8 个脚本全部 rc=0/PASS（含 app_plan_matrix 19/19、problem_closure fixed 11）。
- ★ fast_gate 新增 outputs_consistency（19→20）：新包矛盾/跨位置 answer_ready 不一致/缺
  flags_normalized 即 FAIL；历史包只记录不改写；acceptance_semantics 期望同步 20。
- 验收：fast_gate 20/20；acceptance_semantics 45/45；V2 71/71；App selftest；一键验收；
  e2e 18/18；probe 84/84；发布流程门 pre/post-tag 全 PASS。零云 API。
- 标签：V2.2.81 / engine-V2.2.81（app-V2.0.83 不变，不移动）。

【V2.2.80（2026-10-30，PATCH · 证据答案关键数字锚优先；App 2.0.83）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.80.py（__version__=2.2.80）；
  evidence.py 增加关键数字锚优先。
- ★ 背景：V2.2.79 语言降权后 404 题改中文泛定义、数字锚缺失、质量门 blocked。
- ★ 修复：含题面数字锚（404/2023）的候选优先；语言偏好保留为同锚点内排序；
  新增 case_answer_key_anchor_preference；tests_evidence 23/23。
- ★ 真 API 复验：日文→中文泛定义(blocked)→英文含404(verified/ready True)；
  锚点与语言两难如实记录；不翻译不改写。证据 docs/diag_answer_language_20261030.json。
- 验收：fast_gate 19/19；V2 71/71（1210 checks）；App selftest；一键验收；e2e 18/18；probe；
  发布流程门 pre/post-tag 全 PASS。云 API 约 ¥2.7（余额 8.49→6.40）。
- 标签：V2.2.80 / engine-V2.2.80（app-V2.0.83 不变，不移动）。

【V2.2.79（2026-10-30，PATCH · 证据答案语言匹配；App 2.0.83）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.79.py（__version__=2.2.79）；
  证据模块 dgtf_engine/dgtf_v2/evidence.py 增加语言匹配。
- ★ 根因：answer_from_evidence 只看相关度/官方性，中文题会把含 404 字面的日文网页片段当答案。
- ★ 修复：中文题下日文假名片段 -0.9 降权、中文证据 +0.25；仅 score>0 生效（保 relevance gate）；
  日文题不降权日文证据；只改排序不改写原文。
- ★ 新增 case_answer_language_preference；tests_evidence 22/22；无回归。
- 验收：fast_gate 19/19；V2 71/71（1208 checks）；App selftest；一键验收；e2e 18/18；probe；
  发布流程门 pre/post-tag 全 PASS。零云 API。
- 标签：V2.2.79 / engine-V2.2.79（app-V2.0.83 不变，不移动）。

【V2.2.78（2026-10-30，PATCH · tier_advice 证据驱动 + kind-aware；App 2.0.83）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.78.py（__version__=2.2.78；引擎侧零行为差）；
  App 2.0.83。
- ★ 真 API A/B：reasoning fast 省 ~3.6%、choice 省 ~2.3%、project fast 多 18.6%（只省墙钟）。
- ★ tier_advice 改为只有 fast.tokens<=quality.tokens 才建议 fast；project 相关题按 project 证据判断，
  建议 current 并写明理由；reasoning/choice 维持 fast。
- ★ test_dynamic_opt 134→138 checks，全 PASS。
- 验收：fast_gate 19/19；V2 71/71（1208 checks）；App selftest；一键验收 --with-service；
  e2e 18/18；四层 probe 84/84；发布流程门 pre/post-tag 全 PASS。零云 API。
- 兼容性：只改 advisory 字段，不改变执行。
- 标签：V2.2.78 / engine-V2.2.78 / app-V2.0.83。

【V2.2.77（2026-10-30，PATCH · 修复 v2_online route/rounds 透传降质；App 2.0.82）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.77.py（__version__=2.2.77；引擎侧零行为差）；
  App 2.0.82。
- ★ 根因：v2_online 返回 route=list、rounds=dict，server 写入 opts，build_cmd 旧实现 str(v)
  把 Python repr 传给引擎 ⇒ 四层全跳过、圈数全忽略、1 次 call、答案靠证据拼、质量门 blocked。
- ★ 修复：engine_runner.cli_value（list→0,1,both,all；dict→0:2,1:2；空/auto→空）；
  server 应用前规范化；test_dynamic_opt D2b/D2c 回归（134/134）。
- ★ 端到端真 API 验证：calls 1→91、tokens 570→699,592、调度日志恢复 0 → 1 → both → all、
  圈数 0:2,1:3,both:2,all:2、answer_quality needs_evidence→verified、answer_ready False→True。
- ★ 遗留：答案文本含日文片假名片段（证据语言/卡片拼装），已记录待查。
- 验收：fast_gate 19/19；V2 71/71（1208 checks）；App selftest；一键验收 --with-service；
  e2e 18/18；四层 probe 84/84；发布流程门 pre/post-tag 全 PASS。
- 标签：V2.2.77 / engine-V2.2.77 / app-V2.0.82。

【V2.2.76（2026-10-30，PATCH · 动态矩阵探测器自检；App 2.0.81 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.76.py（__version__=2.2.76；引擎侧零行为差）；
  App 2.0.81 不变。
- ★ audit_dynamic_matrix.py 抽出 detect_violations 纯函数 + self_test：3 个人为违法行必须被抓，
  否则脚本失败（防「永远 PASS」）。
- ★ 自检 3/3 mutants caught；36 组合 0 违反。
- 验收：fast_gate 19/19；V2 71/71（1208 checks）；App selftest 459/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 84/84；发布流程门 pre/post-tag 全 PASS。零云 API。
- 兼容性：只改测试工具；引擎零行为差；App 不变。
- 标签：V2.2.76 / engine-V2.2.76（app-V2.0.81 不变，不移动）。

【V2.2.75（2026-10-30，PATCH · fast_gate 动态矩阵检查；App 2.0.81 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.75.py（__version__=2.2.75；引擎侧零行为差）；
  App 2.0.81 不变。
- ★ fast_gate 新增 dynamic_matrix 检查（18→19）：36 组合 0 违反才 PASS；
  acceptance_semantics 期望 19。
- ★ 防配置回归：<¥8 fast、≥¥8 quality/B、fact/choice web on、tier↔engine_mode 一致。
- 验收：fast_gate 19/19；V2 71/71（1208 checks）；App selftest 459/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 84/84；发布流程门 pre/post-tag 全 PASS。零云 API。
- 兼容性：只改测试/验证工具；引擎零行为差；App 不变。
- 标签：V2.2.75 / engine-V2.2.75（app-V2.0.81 不变，不移动）。

【V2.2.74（2026-10-30，PATCH · 动态配置决策矩阵审计；App 2.0.81 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.74.py（__version__=2.2.74；引擎侧零行为差）；
  App 2.0.81 不变。
- ★ 新增 scripts/local_model/audit_dynamic_matrix.py：4 题型 × 9 档余额 = 36 组合，
  调用 build_plan 记录 tier/engine_mode/web/parallel 等并检查硬约束；证据
  docs/dynamic_matrix_audit_20261030.json。
- ★ 结果：0 违反；<¥8 一律 fast、≥¥8 quality/B；fact/choice 始终 web on；
  reasoning/project fast 档 web off。
- 验收：fast_gate 18/18；V2 71/71（1208 checks）；App selftest 459/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 84/84；发布流程门 pre/post-tag 全 PASS。零云 API。
- 兼容性：纯审计脚本；引擎零行为差；App 不变。
- 标签：V2.2.74 / engine-V2.2.74（app-V2.0.81 不变，不移动）。

【V2.2.73（2026-10-30，PATCH · sync 方差行自动同步；App 2.0.81 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.73.py（__version__=2.2.73；引擎侧零行为差）；
  App 2.0.81 不变。
- ★ sync_readme_numbers.py 接入四层读数方差两行（读取 variance JSON，按前缀整行重写）；
  --check 报 variance rows updated xN，--write 自动修正。
- ★ 46 次历史：case0 均值 0.36（0.0–1.0）/ both 0.021（0–0.37）/ all 0.582（0.5–0.75）。
- 验收：fast_gate 18/18；V2 71/71（1208 checks）；App selftest 459/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 84/84；发布流程门 pre/post-tag 全 PASS。零云 API。
- 兼容性：只改发布工具；引擎零行为差；App 不变。
- 标签：V2.2.73 / engine-V2.2.73（app-V2.0.81 不变，不移动）。

【V2.2.72（2026-10-30，PATCH · probe baseline 全目录复制；App 2.0.81 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.72.py（__version__=2.2.72；引擎侧零行为差）；
  App 2.0.81 不变。
- ★ probe --baseline-playbook 升级为复制目录顶层全部文件（含 bandit/behavior/quality），仍只读。
- ★ 复现性矩阵：默认温度不可复现；temp=0 可写状态 3 连跑稳定（30/30/30、2/2/2、0/0/0）；
  只读基线 2 连跑稳定（32/32、3/3、0/0）⇒ 可复现达成；可测仍取决于历史状态（历史仅一次 settle=3）。
- 验收：fast_gate 18/18；V2 71/71（1208 checks）；App selftest 459/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 84/84；发布流程门 pre/post-tag 全 PASS。零云 API。
- 兼容性：默认 probe/引擎行为不变。
- 标签：V2.2.72 / engine-V2.2.72（app-V2.0.81 不变，不移动）。

【V2.2.71（2026-10-30，PATCH · playbook 只读基线；App 2.0.81 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.71.py（__version__=2.2.71；默认零行为差）；
  App 2.0.81 不变。
- ★ 引擎 playbook.readonly（默认 false）：跑后 EML 学习不落盘，基线不被改写。
- ★ probe --baseline-playbook DIR（复制顶层文件到私有目录并只读）/ --readonly-playbook；
  meta 记录 baseline_playbook/readonly_playbook。
- ★ 实验：temp0+只读基线两次完全一致（32/32 calls、3/3 cand、0/0 settle，unmeasured）⇒
  可复现性达成；但该基线不可测；可写状态曾 settle=3 但不可复现。
- ★ 下一步：在只读基线中播种可判定候选状态，实现「可复现+可测」。
- 验收：fast_gate 18/18；V2 71/71（1208 checks）；App selftest 459/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 84/84；发布流程门 pre/post-tag 全 PASS。零云 API。
- 兼容性：默认 playbook.readonly=false，生产行为不变。
- 标签：V2.2.71 / engine-V2.2.71（app-V2.0.81 不变，不移动）。

【V2.2.70（2026-10-30，PATCH · probe --fresh-playbook；App 2.0.81 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.70.py（__version__=2.2.70；引擎侧零行为差）；
  App 2.0.81 不变。
- ★ probe --fresh-playbook：每次全新 playbook 目录（保留学习、隔离历史）；meta 记录 fresh_playbook。
- ★ 实验（temp=0）：默认 playbook 状态 42/42 calls、cand 3/3、settle 3/3（可测、该状态稳定）；
  fresh playbook 40/40 calls、cand 4/4、settle 0/0（unmeasured、稳定）；
  未固定温度则波动 ⇒ 温度固定保证确定性，可测性取决于 playbook 历史状态。
- ★ 要「可复现+可测」需冻结/播种 playbook（后续工作）。
- 验收：fast_gate 18/18；V2 71/71（1208 checks）；App selftest 459/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 84/84；发布流程门 pre/post-tag 全 PASS。零云 API。
- 兼容性：默认 probe 行为不变；仅新增实验开关。
- 标签：V2.2.70 / engine-V2.2.70（app-V2.0.81 不变，不移动）。

【V2.2.69（2026-10-30，PATCH · api.temperature 可配 + probe --temperature；App 2.0.81 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.69.py（__version__=2.2.69）；
  App 2.0.81 不变。
- ★ 引擎 api.temperature（默认 None ⇒ 仍 0.6，零行为差）；LLM.call 显式 None 时读
  temperature_default 再回落 0.6。
- ★ probe 新增 --temperature 透传（meta 记录）；temp=0 后层1 两次复跑完全一致：
  42 calls / candidates=3 / settle=3 / main=0.0 ⇒ 层1 可测且可复现。
- ★ 已知限制：目标判定仍「判据样本不足」（引擎 2 圈即收，3 圈门槛未满足，未硬凑）；
  隔离 playbook 反而候选归零（EML 学习对候选有帮助）。
- 验收：fast_gate 18/18；V2 71/71（1208 checks）；App selftest 459/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 84/84；发布流程门 pre/post-tag 全 PASS。零云 API。
- 兼容性：默认温度 0.6 不变；显式配置才改变解码。
- 标签：V2.2.69 / engine-V2.2.69（app-V2.0.81 不变，不移动）。

【V2.2.68（2026-10-30，PATCH · 层1 不可复现根因 + probe --isolate-eml；App 2.0.81 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.68.py（__version__=2.2.68；引擎侧零行为差）；
  App 2.0.81 不变。
- ★ 根因：同配置两次 GDP run 对比（packed）——llm_calls 44→27、candidates 3→0、
  behavior_fusion arm fusion_full→v2_contract、playbook 应用条目不同、freeze 1→0、config_hash 变化；
  即 EML/playbook 跨跑学习状态改变行为。
- ★ 隔离实验：playbook off + 独立 dir 后候选恢复 2，但 settle 仍 0 ⇒ EML 是候选波动主因，
  层1 可测还受候选可判定性影响。
- ★ probe 新增 --isolate-eml（默认关；meta 记录 isolate_eml）。
- 验收：fast_gate 18/18；V2 71/71（1208 checks）；App selftest 459/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 84/84（isolate）；发布流程门 pre/post-tag 全 PASS。零云 API。
- 兼容性：只改 probe/证据；引擎零行为差；App 不变。
- 标签：V2.2.68 / engine-V2.2.68（app-V2.0.81 不变，不移动）。

【V2.2.67（2026-10-30，PATCH · 层1 可测：probe route 0,1 + 可生成候选题面；App 2.0.81 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.67.py（__version__=2.2.67；引擎侧零行为差）；
  App 2.0.81 不变。
- ★ 零成本定位：层1 需要上游层0（route=1 单跑 candidates=0）；原题面即使带上游也无候选；
  GDP 题面 + route=0,1 可测（settle 有值）。
- ★ probe case1：route "1"→"0,1"，per-case question 覆盖 GDP 题；支持 per-case rounds；
  证据记录 requested_rounds/question。
- 结果：probe 82/82 PASS；case1 0.000（valued，判据样本不足：2 圈不足 3 圈门槛，未硬凑）。
- 验收：fast_gate 18/18；V2 71/71（1208 checks）；App selftest 459/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；发布流程门 pre/post-tag 全 PASS。零云 API。
- 兼容性：只改测试/证据设计；引擎零行为差；App 不变。
- 标签：V2.2.67 / engine-V2.2.67（app-V2.0.81 不变，不移动）。

【V2.2.66（2026-10-30，PATCH · 发布门证据时序检查；App 2.0.81 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.66.py（__version__=2.2.66；引擎侧零行为差）；
  App 2.0.81 不变。
- ★ release_process_check 新增「证据时序（不早于当前引擎构件）」：V2/fast_gate/acceptance/
  app_selftest 的 ts 与 probe 证据 mtime 均不得早于引擎 mtime-120s，违反即 FAIL 并列出落后秒数。
- 实现后立刻抓到旧证据落后（V2 早 464s / acceptance 早 1285s / app_selftest 早 1540s），
  随后按发布顺序重跑使证据变新。
- 验收：fast_gate 18/18；V2 71/71（1208 checks）；App selftest 459/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 83/83；发布流程门 pre/post-tag 全 PASS。零 API。
- 兼容性：只改发布工具；引擎零行为差；App 不变。
- 标签：V2.2.66 / engine-V2.2.66（app-V2.0.81 不变，不移动）。

【V2.2.65（2026-10-30，PATCH · probe 研究层未测出结构化归因；App 2.0.81 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.65.py（__version__=2.2.65；引擎侧零行为差）；
  App 2.0.81 不变。
- ★ probe 新增 P2g（82→83）：研究层未测出时落盘 settlement.total/answered/decidability/reason，
  并断言 total=0 且原因指向「分母为 0」。
- 修复记录：首版要求 decidability=undecidable，本轮 packed 无该字段（空），改为验证可指认原因。
- 验收：fast_gate 18/18；V2 71/71（1208 checks）；App selftest 459/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 83/83；发布流程门 pre/post-tag 全 PASS。零 API。
- 兼容性：只改进证据可诊断性；引擎零行为差；App 不变。
- 标签：V2.2.65 / engine-V2.2.65（app-V2.0.81 不变，不移动）。

【V2.2.64（2026-10-30，PATCH · stability_guard 扩展文档/README 断言；App 2.0.81 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.64.py（__version__=2.2.64；引擎侧零行为差）；
  App 2.0.81 不变。
- ★ fast_gate stability_guard 扩展：稳定性根因文档必须存在且含关键词
  （串行锁/ffc/未测出/DGTF_SERIAL_LOCK_HELD），README 必须链接该文档。
- 验收：fast_gate 18/18；V2 71/71（1208 checks）；App selftest 459/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；发布流程门 pre/post-tag 全 PASS。零 API。
- 兼容性：只改测试/验证工具；引擎零行为差；App 不变。
- 标签：V2.2.64 / engine-V2.2.64（app-V2.0.81 不变，不移动）。

【V2.2.63（2026-10-30，PATCH · 历史/归档 quality 联动护栏；同发 App 2.0.81）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.63.py（__version__=2.2.63；引擎侧零行为差）；
  App 2.0.81。
- ★ App selftest 457→459：list_chats 每行必须带 quality_expected/quality_actual；
  archivedTask 必须携带 quality_expected/quality_actual（防重构丢失归档联动）。
- 验收：App selftest 459/0；fast_gate 18/18；V2 71/71（1208 checks）；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；发布流程门 pre/post-tag 全 PASS。零 API。
- 兼容性：只加判据；引擎零行为差；无历史数据时跳过值断言。
- 标签：V2.2.63 / engine-V2.2.63 / app-V2.0.81。

【V2.2.62（2026-10-30，PATCH · fast_gate 稳定性护栏；App 2.0.80 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.62.py（__version__=2.2.62；引擎侧零行为差）；
  App 2.0.80 不变。
- ★ fast_gate 新增 stability_guard 检查（17→18 项）：断言 _serial_lock.py 存在且含可重入
  环境变量；10 个重资源脚本（7 判据 + final_acceptance/run_v2_tests/app_selftest_gate）
  都接入 acquire_serial_lock，防止重构静默丢失。
- ★ acceptance_semantics 检查清单期望 18，纳入 stability_guard。
- 验收：fast_gate 18/18；V2 71/71（1208 checks）；App selftest 457/0；一键验收 PASS 30 /
  SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；发布流程门 pre/post-tag 全 PASS。零 API。
- 兼容性：只改测试/验证工具；引擎零行为差；App 不变。
- 标签：V2.2.62 / engine-V2.2.62（app-V2.0.80 不变，不移动）。

【V2.2.61（2026-10-30，PATCH · 判据稳定性根因归档；App 2.0.80 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.61.py（__version__=2.2.61；引擎侧零行为差）；
  App 2.0.80 不变。
- ★ 新增 docs/判据稳定性根因与修复_20261030.md：并发争用 ⇒ 串行锁/可重入；
  ffc 缓存状态耦合（事实题 quality_retry + no_cache 继承）⇒ 主任务 no_cache、D 组非事实题；
  层1 未测出 = decidability=undecidable / settlement.total=0（非回归）。
- ★ 状态快照增加「判据稳定性」条目，维护约定写入文档。
- 验收：fast_gate 17/17；V2 71/71（1208 checks）；App selftest 457/0；一键验收 PASS 30 / SKIP 0 /
  FAIL 0；e2e 18/18；四层 probe 82/82；发布流程门 pre/post-tag 全 PASS。零 API 花费。
- 兼容性：纯文档/状态摘要；引擎零行为差；App 不变。
- 标签：V2.2.61 / engine-V2.2.61（app-V2.0.80 不变，不移动）。

【V2.2.60（2026-10-30，PATCH · 串行锁可重入 + 扩展到验收/V2/App selftest；App 2.0.80 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.60.py（__version__=2.2.60；引擎侧零行为差）；
  App 2.0.80 不变。
- ★ acquire_serial_lock 可重入：父进程持锁（DGTF_SERIAL_LOCK_HELD）⇒ 子进程跳过，避免死锁。
- ★ final_acceptance / run_v2_tests / app_selftest_gate 启动取同一把 local_chain 锁，
  与手动 fused_full_chain、probe 等互斥。
- 验证：验收加锁 30/30 无死锁；并发验收+ffc ⇒ 验收 30/30、ffc 25/25（ffc wall 543.6s）。
- 验收：fast_gate 17/17；V2 71/71（1208 checks）；App selftest 457/0；一键验收 PASS 30 / SKIP 0 /
  FAIL 0；e2e 18/18；四层 probe 82/82；发布流程门 pre/post-tag 全 PASS。零 API 花费。
- 兼容性：只改测试/验证工具；引擎零行为差；App 不变。
- 标签：V2.2.60 / engine-V2.2.60（app-V2.0.80 不变，不移动）。

【V2.2.59（2026-10-30，PATCH · 判据串行锁 + ffc 缓存稳健性；App 2.0.80 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.59.py（__version__=2.2.59；引擎侧零行为差）；
  App 2.0.80 不变。
- ★ 新增 scripts/local_model/_serial_lock.py（Windows msvcrt / POSIX flock）：7 个重资源判据
  启动取同一把锁，消除临时 App server + 本地链路 + outputs 并发争用。并发 ffc+fo ⇒ 25/25 + 30/30。
- ★ fused_full_chain 缓存稳健性：主任务 no_cache=True；D 组改用非事实题（热岛题）并去掉继承的
  no_cache、显式 use_cache=True —— 修复预算收紧后 D 组失败（事实题强制 quality_retry 跳过缓存）。
  ffc 串行 25/25。
- 验收：fast_gate 17/17；V2 71/71（1208 checks）；App selftest 457/0；一键验收 PASS 30 / SKIP 0 /
  FAIL 0；e2e 18/18；四层 probe 82/82；发布流程门 pre/post-tag 全 PASS。零 API 花费。
- 兼容性：只改测试/验证工具；引擎零行为差；App 不变。
- 标签：V2.2.59 / engine-V2.2.59（app-V2.0.80 不变，不移动）。

【V2.2.58（2026-10-30，PATCH · 四层 probe 读数方差统计；App 2.0.80 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.58.py（__version__=2.2.58；引擎侧零行为差）；
  App 2.0.80 不变。
- ★ 新增 scripts/probe_variance_stats.py：从审计历史复跑表格抽取 case0/1/both/all 读数，
  统计 n/均值/极差并落盘 docs/probe_variance_20261030.json。
- ★ 结果（40 次历史）：case0 均值 0.415（0.0–1.0）/ both 0.017（0–0.37）/
  all 0.594（0.5–0.75，从未到 1.0）。README 增「四层读数方差」行。
- 验收：fast_gate 17/17；V2 71/71（1208 checks）；App selftest 457/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。零 API 花费。
- 兼容性：只读证据工具；引擎零行为差；App 不变。
- 标签：V2.2.58 / engine-V2.2.58（app-V2.0.80 不变，不移动）。

【V2.2.57（2026-10-30，PATCH · 归档视图实测/预期质量；同发 App 2.0.80）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.57.py（__version__=2.2.57；引擎侧零行为差）；
  App 2.0.80。
- ★ openChat 打开归档时 archivedTask 携带 quality_expected/quality_actual；
  renderMeta 在无 mode 的归档视图追加只读标签「预期 x% · 实测 y」。
- ★ 与历史列表卡片同源（list_chats，120s 时间窗防串档）。
- 验证：node --check app.js 通过；App selftest 457/0。
- 验收：fast_gate 17/17；V2 71/71（1208 checks）；一键验收 --with-service PASS 30 / SKIP 0 /
  FAIL 0；e2e 18/18；四层 probe 82/82；发布流程门 pre/post-tag 全 PASS。零 API 花费。
- 兼容性：仅只读展示；任务执行不变；无实测时保持原样。
- 标签：V2.2.57 / engine-V2.2.57 / app-V2.0.80。

【V2.2.56（2026-10-30，PATCH · 历史卡片预期 vs 实测；同发 App 2.0.79）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.56.py（__version__=2.2.56；引擎侧零行为差）；
  App 2.0.79。
- ★ dashboard.list_chats 每条会话附 quality_expected（run.json plan.quality_retry
  expected_verified_pct）与 quality_actual（packed 的 answer_quality/answer_ready/verified）；
  archive 无 output_name 时按问题匹配 packed，并加 120s 时间窗防同名题串档。
- ★ 前端历史卡片追加「预期 x% · 实测 y」只读标签。
- 验证：list_chats(80) 有 3 条归档匹配到实测（unverified/verified/needs_evidence）；
  App selftest 457/0；node --check app.js 通过。
- 验收：fast_gate 17/17；V2 71/71（1208 checks）；一键验收 --with-service PASS 30 / SKIP 0 /
  FAIL 0；e2e 18/18；四层 probe 82/82；发布流程门 pre/post-tag 全 PASS。零 API 花费。
- 兼容性：仅只读字段/标签；任务执行不变；无 packed 时 quality_actual 为空。
- 标签：V2.2.56 / engine-V2.2.56 / app-V2.0.79。

【V2.2.55（2026-10-30，PATCH · fast_gate 接入 README 数字校验；App 2.0.78 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.55.py（__version__=2.2.55；引擎侧零行为差）；
  App 2.0.78 不变。
- ★ fast_gate 新增 readme_numbers 检查（执行 sync_readme_numbers.py --check）：
  README 实测数字与证据不一致 ⇒ 快速门禁判红（检查项 16→17）。
- ★ sync_readme_numbers.py 增加 fast_gate 数字回写（顶部 fast_gate **N/N**）；
  acceptance_semantics 检查清单期望同步 16→17（含 readme_numbers）。
- 效果：数字漂移在 fast_gate 即暴露；--write 自动修正（本轮自动把 fast_gate 16→17）。
- 判据：fast_gate 17/17；V2 71/71（1208 checks）；App selftest 457/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。零 API 花费。
- 兼容性：只改工具链/文档；引擎零行为差；App 不变。
- 标签：V2.2.55 / engine-V2.2.55（app-V2.0.78 不变，不移动）。

【V2.2.54（2026-10-30，PATCH · README 数字自动同步；App 2.0.78 不变）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.54.py（__version__=2.2.54；引擎侧零行为差）；
  App 2.0.78 不变。
- ★ 新增 scripts/sync_readme_numbers.py：从 evidence JSON 回写/校验 README 实测数字
  （App selftest 行、四层 probe 行、顶部 selftest），--check 不一致 exit 1、--write 自动修正。
- ★ 事实来源：app_selftest / probe / v2_tests / fast_gate / acceptance / app_version /
  引擎目录最高版。
- 判据：脚本 --check PASS（App selftest 457、probe 82/82/179 calls/415.2s、V2 71/71、
  fast_gate 16、acceptance 30）。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 457/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。零 API 花费。
- 兼容性：只改文档/工具链；引擎零行为差；App 不变。
- 标签：V2.2.54 / engine-V2.2.54（app-V2.0.78 不变，不移动）。

【V2.2.53（2026-10-30，PATCH · 预期 vs 实测 quality_actual；同发 App 2.0.78）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.53.py（__version__=2.2.53；引擎侧零行为差）；
  App 2.0.78。
- ★ 任务 GET（done 时）附加 quality_actual（answer_quality/answer_ready/verified/packed）：
  从 packed 读取实测质量；解析 output_name → save_dir → log 推导 → outputs 递归按问题+时间匹配；
  失败 fail-open（source=none）。
- ★ 前端 rl-qf 标签追加「实测 unverified / 实测 verified」，与预期验证率并列展示。
- 判据：App selftest 456→457（+1 server/前端判据）；fused_full_chain 24→25（C10 与 packed 一致）；
  test_dynamic_opt 132 不变；回归 fused_optimal 30 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；一键验收 --with-service PASS 30 / SKIP 0 /
  FAIL 0；e2e 18/18；四层 probe 81/81；发布流程门 pre/post-tag 全 PASS。零 API 花费。
- 兼容性：仅新增查询字段；任务执行不变。
- 标签：V2.2.53 / engine-V2.2.53 / app-V2.0.78。

【V2.2.52（2026-10-30，PATCH · rl-qf 修复 + tier_advice 提示；同发 App 2.0.77）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.52.py（__version__=2.2.52；引擎侧零行为差）；
  App 2.0.77。
- ★ 修复 V2.2.48 rl-qf 标签 bug：模板字符串拼接把 单引号+esc(_qtext)+单引号 当字面量写进
  data-qf/title 属性；改为纯字符串拼接并正确转义。
- ★ quality_forecast.tier_advice=fast 时追加「建议 fast」；App selftest 前端判据要求
  tier_advice 渲染（456/0）。
- 判据：App selftest 456/0；node --check app.js 通过；回归 fused_optimal 30 /
  fused_full_chain 24 / daosheng_unified 27 / auto_mode_local 12 / dynamic_opt 132。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；一键验收 --with-service PASS 30 / SKIP 0 /
  FAIL 0；e2e 18/18；四层 probe 82/82；发布流程门 pre/post-tag 全 PASS。零 API 花费。
- 兼容性：纯前端修复/展示；任务执行不变。
- 标签：V2.2.52 / engine-V2.2.52 / app-V2.0.77。

【V2.2.51（2026-10-30，PATCH · opt-in 优先成本降档；同发 App 2.0.76）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.51.py（__version__=2.2.51；引擎侧零行为差）；
  App 2.0.76。
- ★ budget.prefer_cost_when_unverified（默认 false）：开启 + 预算 ok + tier=quality +
  该题型 expected_verified_pct=0 ⇒ 自动降 fast；fact（verified 2/2）不降；
  预算 warn/critical 已降档不变。
- ★ plan.prefer_cost_when_unverified / tier_downgraded_by 可审计；默认关闭 ⇒ 既有行为不变。
- 判据：test_dynamic_opt 129→132（X1 默认关、X2 开启 reasoning 降 fast、X3 fact 不降）；
  回归 fused_optimal 30 / fused_full_chain 24 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 456/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。本轮零 API 花费。
- 兼容性：默认关；显式开启才降档；fact 永不因此降档。
- 标签：V2.2.51 / engine-V2.2.51 / app-V2.0.76。

【V2.2.50（2026-10-30，PATCH · tier_advice A/B 证据；同发 App 2.0.75）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.50.py（__version__=2.2.50；引擎侧零行为差）；
  App 2.0.75。
- ★ tier_advice 有界 A/B（真 API 约 ¥0.27）：reasoning 同题 full rounds=1/层 web off——
  quality/B 69,359 tokens/124.6s vs fast 66,869/67.4s，两臂均 unverified；fast 省 ~3.6% tokens、
  墙钟约减半、质量未劣化。
- ★ _TIER_ADVICE_EVIDENCE 接入：plan.quality_retry.tier_evidence 指向
  docs/tier_advice_ab_20261030.json，tier_advice_why 附实测 note；fact（current）不携带。
- 判据：test_dynamic_opt 126→129（W1 A/B 数据、W2 evidence/note、W3 fact 不携带）；
  回归 fused_optimal 30 / fused_full_chain 24 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 456/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。本轮 A/B 花费约 ¥0.27。
- 兼容性：仍为 advisory，不改变实际 tier；证据字段仅审计/展示。
- 标签：V2.2.50 / engine-V2.2.50 / app-V2.0.75。

【V2.2.49（2026-10-30，PATCH · 语义阈值标定 + 选档建议；同发 App 2.0.74）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.49.py（__version__=2.2.49；引擎侧零行为差）；
  App 2.0.74。
- ★ 语义阈值标定（本地 BGE 零 API）：0.98 边界成立——0.9960/0.9869/0.9856 命中，
  0.9682/0.9675/0.9576 不命中；HTTP 变体 421/425 为同题 verified 包 exact 命中（非误命中），
  432 相似度 0.8916 未命中；证据 docs/semantic_threshold_calibration_20261030.json。
- ★ 选档建议（advisory）：该题型 expected_verified_pct=0 + 预算 ok + tier=quality ⇒
  quality_retry.tier_advice=fast（理由：质量档未带来验证收益，fast 更省 tokens）；
  fact → current；预算 warn 已降 fast → current；quality_forecast 同步输出。
- 判据：test_dynamic_opt 122→126（V1 阈值边界、V2 reasoning fast、V3 fact current、
  V4 预算 warn current）；回归 fused_optimal 30 / fused_full_chain 24 / daosheng_unified 27 /
  auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 456/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。本轮零 API 花费。
- 兼容性：tier_advice 仅建议，不改变 tier/route/rounds。
- 标签：V2.2.49 / engine-V2.2.49 / app-V2.0.74。

【V2.2.48（2026-10-29，PATCH · 前端展示创建前预期；同发 App 2.0.73）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.48.py（__version__=2.2.48；引擎侧零行为差）；
  App 2.0.73。
- ★ 运行读数行（renderMeta）在「模式 · 道生」旁新增只读标签 rl-qf：预期验证率 /
  续航（safe_runs）/ 缓存省（expected_saving_pct），数据来自 V2.2.46 quality_forecast。
- ★ 无新按钮/新面板；无数据不显示；纯前端展示，API/引擎/任务执行不变。
- 判据：App selftest 455→456（新增前端 quality_forecast 判据）；node --check app.js 通过；
  回归 fused_optimal 30 / fused_full_chain 24 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 456/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。本轮零 API 花费。
- 兼容性：纯前端；旧响应无字段自动不显示。
- 标签：V2.2.48 / engine-V2.2.48 / app-V2.0.73。

【V2.2.47（2026-10-29，PATCH · project 质量证据 + 预判结果持久化；同发 App 2.0.72）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.47.py（__version__=2.2.47；引擎侧零行为差）；
  App 2.0.72。
- ★ project 加圈+上下文 A/B（真 API 约 ¥0.25）：full、rounds=2/层、web off——ctx on
  61,457 tokens / ctx off 62,566 tokens，两臂均 unverified；project 累计 0/4。
  _QUALITY_EXPECTATION.project → 0/4，证据含 project_context_rounds2_ab JSON。
- ★ 语义预判结果跨进程落盘 dgtf_memory/semantic_probe_index.json（120s/300 条）：
  重启后 0 次 embedding 复用（与候选索引持久化配套）。
- 判据：test_dynamic_opt 121→122（U3 4 跑证据、S6 结果落盘/0 新 embed）；
  回归 fused_optimal 30 / fused_full_chain 24 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。本轮 A/B 花费约 ¥0.25。
- 兼容性：仅缓存/证据变化；预判结果 120s 过期自动重算；索引缺失/损坏回退扫描。
- 标签：V2.2.47 / engine-V2.2.47 / app-V2.0.72。

【V2.2.46（2026-10-29，PATCH · 创建前综合预期；同发 App 2.0.71）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.46.py（__version__=2.2.46；引擎侧零行为差）；
  App 2.0.71。
- ★ 任务创建响应 mode.quality_forecast：kind / expected_verified_pct / evidence /
  budget_forecast（safe_runs/balance_after）/ cache_roi（semantic_hit/similarity/
  expected_saving_pct）/ quality_retry（policy/retry）；全部来自既有 plan 字段。
- ★ 不改变服务器行为；标准链路 fail-open 时为空 dict；客户端可忽略。
- 判据：fused_full_chain 23→24（B6 响应含 quality_forecast 三维字段）；
  test_dynamic_opt 121 不变；回归 fused_optimal 30 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。本轮零 API 花费。
- 兼容性：仅新增响应字段；任务执行不变。
- 标签：V2.2.46 / engine-V2.2.46 / app-V2.0.71。

【V2.2.45（2026-10-29，PATCH · 语义候选索引持久化；同发 App 2.0.70）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.45.py（__version__=2.2.45；引擎侧零行为差）；
  App 2.0.70。
- ★ 候选清单落盘 dgtf_memory/semantic_cache_index.json（ts+items，300s 内跨进程复用）；
  进程内缓存失效时优先读磁盘；实测清空后 0.01s 恢复 120 条候选。
- ★ App 启动后台 warm_semantic_cache：构建索引并批量 embedding（等 8771 就绪最多 12s；
  失败不影响主流程）。
- 判据：test_dynamic_opt 118→121（S3 索引落盘、S4 磁盘恢复 <0.5s、S5 预热结构）；
  回归 fused_optimal 30 / fused_full_chain 23 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。本轮零 API 花费。
- 兼容性：索引 300s 有效；8771 不在预热 ok=False；缺失/损坏自动回退扫描。
- 标签：V2.2.45 / engine-V2.2.45 / app-V2.0.70。

【V2.2.44（2026-10-29，PATCH · 题型 verified 期望矩阵；同发 App 2.0.69）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.44.py（__version__=2.2.44；引擎侧零行为差）；
  App 2.0.69。
- ★ choice 加圈 A/B（真 API 约 ¥0.31）：rounds1 86,858 / rounds2 67,540 tokens，
  两臂均 needs_evidence ⇒ 加圈未提升质量且 rounds2 更省。
- ★ _QUALITY_EXPECTATION 矩阵：fact（web on）2/2 verified；reasoning 0/6；choice 0/6；
  project 0/2（证据 quality_retry_ab / route_subset_reasoning / route_subset_choice /
  choice_rounds / project_context_ab）。
- ★ plan.quality_retry 输出 expected_verified_pct/evidence/evidence_note；
  plan.quality_expectation 输出完整矩阵（可审计）。
- 判据：test_dynamic_opt 114→118（U1 reasoning、U2 choice、U3 project、U4 矩阵）；
  回归 fused_optimal 30 / fused_full_chain 23 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。本轮 A/B 花费约 ¥0.31。
- 兼容性：仅新增可审计字段，不改变 server/引擎行为。
- 标签：V2.2.44 / engine-V2.2.44 / app-V2.0.69。

【V2.2.43（2026-10-29，PATCH · fact+web on 质量证据；同发 App 2.0.68）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.43.py（__version__=2.2.43；引擎侧零行为差）；
  App 2.0.68。
- ★ 质量重试 A/B（真 API 约 ¥0.31）：fact 题 full route web on——rounds1 85,362 tokens/15 calls、
  rounds2 67,753/12 calls，两臂均 verified；加圈未提升质量且 rounds2 更省 ⇒ 对 fact+web on
  不实现质量 retry/加圈。
- ★ plan.quality_retry 增加 expected_verified_pct=1.0/evidence/evidence_note（advisory）；
  证据 docs/quality_retry_ab_20261029.json。
- ★ fact 高圈锚点：_LONG_RUN_ANCHORS 增加 fact（web on、总圈数 5-10）full 67,753（n=2），
  dynamic_config 对 fact 高圈 full 使用实测锚点。
- 判据：test_dynamic_opt 111→114（T1 2/2 verified、T2 高圈锚点≈67,753、T3 rounds2 更省）；
  回归 fused_optimal 30 / fused_full_chain 23 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：quality_retry 仍 advisory；高圈锚点仅成本估算；默认四层不变。
- 标签：V2.2.43 / engine-V2.2.43 / app-V2.0.68。

【V2.2.42（2026-10-29，PATCH · 语义预判双层缓存；同发 App 2.0.67）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.42.py（__version__=2.2.42；引擎侧零行为差）；
  App 2.0.67。
- ★ 问题：V2.2.41 语义预判每次 build_plan 扫描 300 packed 并重算 embedding，acceptance 的
  dynamic_opt 从 2s 涨到 97s。
- ★ 修法：verified 候选清单缓存 300s（最多 200 条）+ 命中结果缓存 120s；
  命中时只 embed 当前问题 + ≤8 候选（batch 1 次）。
- ★ 效果：test_dynamic_opt 109→111 且整套 97s→6.5s；acceptance dynamic_opt 6.5s。
- ★ 语义标定扩展（本地链路零 API）：精确 sim=1.0；近重复 0.996 / 0.9971 / 0.9907
  全部 cache_hit、0 次新 LLM 调用（证据 docs/semantic_cache_hit_20261029.json）。
- 判据：test_dynamic_opt 111（+2：S1 候选缓存、S2 结果缓存；Q4 扩到 3 语义臂）；
  回归 fused_optimal 30 / fused_full_chain 23 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。本轮零 API 花费。
- 兼容性：8771 未运行 ⇒ 语义预判 fail-open；缓存只影响预判，真实缓存不变。
- 标签：V2.2.42 / engine-V2.2.42 / app-V2.0.67。

【V2.2.41（2026-10-29，PATCH · 语义缓存命中预判；同发 App 2.0.66）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.41.py（__version__=2.2.41；引擎侧零行为差）；
  App 2.0.66。
- ★ 语义缓存标定（本地链路零 API）：精确命中 sim=1.0；近重复问法 sim=0.996 命中同一
  verified 产物，均 cache_hit=true 且 0 次新 LLM 调用；证据 docs/semantic_cache_hit_20261029.json。
- ★ verified 产物 TTL 6h → 168h（此前所有 verified 均过期、缓存实际无法命中）；
  未验证仍受 V2.2.40 新鲜度门（warn 24h / critical 72h）。
- ★ cache_prediction 用本地 BGE 8771 对最近 verified 产物批量 embedding（扫描 300/收 8），
  余弦 ≥0.98 ⇒ semantic_hit；dynamic_config 语义命中成本按 10% 计（cache_kind=semantic），
  cache_roi 输出 semantic_hit/similarity/from/expected_saving_pct=0.9；8771 不可用 fail-open。
- ★ dashboard created_at 兼容字符串（_to_ts），修复 /api/chats ValueError 导致
  App selftest 断连的问题。
- 判据：test_dynamic_opt 105→109（Q1–Q4）；App selftest 455/0；fused_full_chain 23/23；
  回归 fused_optimal 30 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；一键验收 --with-service PASS 30 / SKIP 0 /
  FAIL 0；e2e 18/18；四层 probe 82/82；发布流程门 pre/post-tag 全 PASS。本轮零 API 花费。
- 兼容性：8771 未运行 ⇒ 语义预判 fail-open；未验证复用仍受预算+新鲜度门；no_cache 强制重跑。
- 标签：V2.2.41 / engine-V2.2.41 / app-V2.0.66。

【V2.2.40（2026-10-29，PATCH · 未验证缓存新鲜度门；同发 App 2.0.65）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.40.py（__version__=2.2.40；引擎侧零行为差）；
  App 2.0.65。
- ★ 问题：V2.2.39 未验证复用未限制产物年龄，旧产物复用会放大质量风险。
- ★ 修法：plan.cache_policy.max_age_h（warn 24h / critical 72h / ok 0）+ plan.cache_max_age_h
  透传；server._find_cached_pack(max_age_h) 对未验证产物按年龄过滤（verified 不受限）；
  响应 cache_age_h。
- ★ 全链路本地验证（零 API）：fused_full_chain 21→23——D5 max_age_h≈0 ⇒ cache_hit=False；
  D6 max_age_h=24 ⇒ cache_hit=True；D 段结束清理 root 产物避免污染发布门。
- 判据：test_dynamic_opt 102→105（P1 warn 24h、P2 ok 0、P3 apply_plan 透传）；
  回归 fused_optimal 30 / fused_full_chain 23 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。本轮零新增 API 花费。
- 兼容性：verified 复用不变；未验证复用仅预算 warn/critical 且新鲜；no_cache 强制重跑。
- 标签：V2.2.40 / engine-V2.2.40 / app-V2.0.65。

【V2.2.39（2026-10-29，PATCH · 预算紧张复用未验证产物；同发 App 2.0.64）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.39.py（__version__=2.2.39；引擎侧零行为差）；
  App 2.0.64。
- ★ 问题：产物缓存只复用 verified+answer_ready；本环境多数产出 unverified ⇒ 同题重复提交
  仍整单重跑、重复计费。
- ★ 修法：plan.allow_unverified_cache（预算 warn/critical）+ dynamic_opt.cache_policy；
  server._find_cached_pack(allow_unverified=True) 对同题精确匹配可复用
  unverified/needs_evidence 产物；语义回退仍只 verified；响应 cache_unverified；
  no_cache/force_rerun 仍强制重跑；apply_plan 透传。
- ★ 全链路本地验证（零 API）：fused_full_chain 16→21（D0 seed 完成、D1 cache_hit、
  D2 cache_unverified、D3 继承 output、D4 0 新 packed/0 次新 LLM 调用）。
- 判据：test_dynamic_opt 99→102（O1 ok=False、O2 warn=True+policy、O3 apply_plan 透传）；
  回归 fused_optimal 30 / fused_full_chain 21 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。本轮零新增 API 花费。
- 兼容性：仅预算 warn/critical 启用；预算充足仍只 verified；显式 no_cache 强制重跑。
- 标签：V2.2.39 / engine-V2.2.39 / app-V2.0.64。

【V2.2.38（2026-10-29，PATCH · 余额续航预测；同发 App 2.0.63）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.38.py（__version__=2.2.38；引擎侧零行为差）；
  App 2.0.63。
- ★ dynamic_opt.budget_forecast：{balance_cny, est_cost_cny, balance_after_cny, safe_runs,
  reserve_runs, advice}；safe_runs=floor(balance/chosen 成本)，用最终动态选择成本
  （含上下文/缓存折算）；余额未知 ⇒ None。
- ★ budget.reserve_runs 默认 2：quality 档在安全续航 < reserve_runs 时自动降 fast
  并写明 mode_reason（默认余额 10/估 0.13 → safe_runs≈76，不降级）。
- 判据：test_dynamic_opt 95→99（续航字段/safe_runs/balance_after、reserve=500 触发 fast、
  默认不降级、余额未知 None）；回归 fused_optimal 30 / fused_full_chain 16 /
  daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；