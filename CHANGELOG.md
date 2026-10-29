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
  发布流程门 pre/post-tag 全 PASS。本轮零新增 API 花费。
- 兼容性：默认 reserve_runs=2 对正常余额几乎无影响；余额未知 fail-open。
- 标签：V2.2.38 / engine-V2.2.38 / app-V2.0.63。

【V2.2.37（2026-10-29，PATCH · quality-retry 决策显式化；同发 App 2.0.62）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.37.py（__version__=2.2.37；引擎侧零行为差）；
  App 2.0.62。
- ★ plan.quality_retry（advisory）：{policy, retry, why}——项目/auto:verified 不允许关闭验证；
  事实/require_web + 预算 ok 建议 auto:web-retry；预算 warn/critical 建议 auto:stable；
  其它 stable。本轮只显式化决策，不改变 server 重试行为。
- ★ budget_cap 拆 context_tokens/base_tokens（项目题 context=5,662，基础量=估算-上下文）。
- ★ dynamic_opt.cache_roi：exact/semantic_capable/expected_saving_pct/note；
  语义缓存命中率未标定 → 只报能力不估算收益。
- 判据：test_dynamic_opt 90→95（fact+ok web-retry、fact+warn stable、项目 verified、
  budget_cap 分解、cache_roi 字段）；回归 fused_optimal 30 / fused_full_chain 16 /
  daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。本轮零新增 API 花费。
- 兼容性：advisory 不改变实际行为；默认四层/预算上限/成本模型沿用前版。
- 标签：V2.2.37 / engine-V2.2.37 / app-V2.0.62。

【V2.2.36（2026-10-29，PATCH · 项目背景注入成本；同发 App 2.0.61）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.36.py（__version__=2.2.36；引擎侧零行为差）；
  App 2.0.61。
- ★ 项目背景 A/B（2 跑约 ¥0.18，route=0/rounds=0:1/web off）：默认注入 48,173 tokens vs
  project_context=false 42,511（+5,662 tokens 约 ¥0.011）；两臂均 unverified。
- ★ 动态 context_cost：_CONTEXT_COST（project 5,662/n=2）；dynamic_config 项目题且未显式
  关闭时候选 token += context 成本，记录 context_tokens；dynamic_opt.context_cost 可审计；
  显式 project_context=false 不计成本（回到 42,798 基础锚点）。
- 判据：test_dynamic_opt 87→90（上下文 A/B 证据、默认 context_cost=5,662、显式关闭不计）；
  回归 fused_optimal 30 / fused_full_chain 16 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：显式 project_context=false 仍可关闭；默认四层/省层判定不变；仅成本估算变化。
- 标签：V2.2.36 / engine-V2.2.36 / app-V2.0.61。

【V2.2.35（2026-10-29，PATCH · rounds 依赖省层收益；同发 App 2.0.60）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.35.py（__version__=2.2.35；引擎侧零行为差）；
  App 2.0.60。
- ★ reasoning 高圈 A/B（2 跑约 ¥0.26，rounds=2/层）：route0 65,608 vs full 62,317 tokens
  （高圈省层收益≈0，full 反而略省），两臂均 unverified；与单圈（route0 39.6-46k vs full
  70.7-74.9k，省约 39%）对比 ⇒ 省层收益 rounds 依赖。
- ★ route_pruning 高圈分支：reasoning 总圈数≥5 ⇒ keep_four_layers（证据 rounds2 JSON）；
  单圈仍 subset_may_save；fact 任意长度 keep；choice may_save（≈40%）。
- ★ 新增 _LONG_RUN_ANCHORS（reasoning、B、总圈数 5-10）：route0 65,608 / full 62,317，
  动态成本 cost_source=measured_long_anchor。
- 判据：test_dynamic_opt 83→87（高圈证据、高圈 keep、高圈 route0/full 锚点、单圈 may_save）；
  回归 fused_optimal 30 / fused_full_chain 16 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：默认四层不变；高圈锚点只影响成本估算；判定仅提示。
- 标签：V2.2.35 / engine-V2.2.35 / app-V2.0.60。

【V2.2.34（2026-10-29，PATCH · choice 题型省层收益；同发 App 2.0.59）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.34.py（__version__=2.2.34；引擎侧零行为差）；
  App 2.0.59。
- ★ choice 省层 A/B（4 跑约 ¥0.55）：route0 50,582/50,922 tokens vs full 85,320/85,364
  （省约 40%），两臂均 needs_evidence/ready=false；kind-aware 表补全：
  fact≈0（n=6）、reasoning≈0.39（n=4）、choice≈0.40（n=4）。
- ★ 短程锚点补 choice（full 85,342 / route0 50,752）；route_quality_risk.evidence 按题型
  指向对应 A/B JSON；短程事实分支限定 kind=fact（修复 choice 被覆盖）。
- 判据：test_dynamic_opt 80→83（choice 锚点≈85,342、choice may_save≈40%、choice 风险证据）；
  回归 fused_optimal 30 / fused_full_chain 16 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：默认四层不变；判定只记录/提示，不改变实际 route。
- 标签：V2.2.34 / engine-V2.2.34 / app-V2.0.59。

【V2.2.33（2026-10-29，PATCH · 短程实测成本锚点；同发 App 2.0.58）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.33.py（__version__=2.2.33；引擎侧零行为差）；
  App 2.0.58。
- ★ 问题：动态配置短跑成本用可加模型高估 10 倍以上（fact 四层估 ~785k / B 模式 ~1.27M，
  实测 65,427）。
- ★ 修法：_SHORT_RUN_ANCHORS（B 模式、总圈数<=4）——fact full 65,427 / route0 65,360 /
  route0,1 60,962（n=6）；reasoning full 72,799 / route0 42,798（n=4）。
  dynamic_config 短跑直接使用实测锚点（cost_source=measured_short_anchor，不重复乘 App 开销）；
  显式 opts.rounds 只评估该圈数档；长跑仍用可加模型 + App 开销。
- 效果：短跑成本估算误差降到 <15%，预算可行域/budget_cap/动态选择更贴近真实账单。
- 判据：test_dynamic_opt 75→80（fact/reasoning 短程锚点、预算 ¥10 可行不 fallback、
  长程回退模型、cost_source）；回归 fused_optimal 30 / fused_full_chain 16 /
  daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：默认四层不变；锚点只影响成本估算/可行域；显式 opts 优先。
- 标签：V2.2.33 / engine-V2.2.33 / app-V2.0.58。

【V2.2.32（2026-10-29，PATCH · kind-aware 省层收益；同发 App 2.0.57）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.32.py（__version__=2.2.32；引擎侧零行为差）；
  App 2.0.57。
- ★ reasoning 省层 A/B（4 跑约 ¥0.46）：route0 39,564/46,031 tokens vs full 74,922/70,676
  （省约 39%），两臂均 unverified/ready=false；结合 fact 6 跑（61-67k 无差异）得到
  kind-aware 收益表：fact≈0（n=6）、reasoning≈0.39（n=4）。
- ★ route_pruning 改为题型实测优先：短程事实/fact 任意长度 keep_four_layers（覆盖模型高估）；
  reasoning subset_may_save（仍需质量证据才能自动砍层）；无题型证据退回模型估算。
  route_quality_risk 的 evidence/note 按题型指向对应证据文件。
- 判据：test_dynamic_opt 69→75（I9 reasoning 证据、I10 reasoning may_save≥30%、I11 fact 长程
  实测≈0 覆盖模型 keep）；回归 fused_optimal 30 / fused_full_chain 16 / daosheng_unified 27 /
  auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：默认四层不变；省层判定只记录/提示，不改变实际 route。
- 标签：V2.2.32 / engine-V2.2.32 / app-V2.0.57。

【V2.2.31（2026-10-29，PATCH · 省层收益判定；同发 App 2.0.56）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.31.py（__version__=2.2.31；引擎侧零行为差）；
  App 2.0.56。
- ★ 6 跑多样本 A/B（约 ¥0.77，事实题/rounds=1/web on/预算 50）：route0 2/2 verified 但 0/2 ready
  （tokens 中位 65,360）；route0,1 2/2 verified 但 0/2 ready（66,856）；full 1/2 verified+1/2 ready
  （65,427）。三臂 tokens 无显著差异（61-67k）⇒ 短程事实题省层省不到 token，质量方差主导；
  默认 route_policy=union（四层）继续是保守选择。
- ★ 省层收益判定：plan.dynamic_opt.route_pruning = {advice, saved_tokens_estimate,
  saved_pct_estimate, evidence, note}。短程事实（require_web 且总圈数≤6）⇒ keep_four_layers；
  长程高圈且模型估算省≥10% ⇒ subset_may_save（仍需质量证据）；判定只记录/提示，不改实际 route。
- ★ 风险标注更新：route_quality_risk.evidence 改为多样本 JSON（保留单题 A/B 为 evidence_prev），
  note 明确"方差主导，不能据此判断省层安全"。
- 判据：test_dynamic_opt 69→73（短程 keep、证据路径、full 无判定、长程 may_save）。
  回归 fused_optimal 30 / fused_full_chain 16 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：默认四层不变；省层判定不改变实际 route。
- 标签：V2.2.31 / engine-V2.2.31 / app-V2.0.56。

【V2.2.30（2026-10-29，PATCH · 层子集质量风险标注；同发 App 2.0.55）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.30.py（__version__=2.2.30；引擎侧零行为差）；
  App 2.0.55。
- ★ 3 臂有界 A/B（约 ¥0.42，事实题/rounds=1/web on/预算 50）：route0=verified（12 calls/
  67,087 tokens/¥0.134）；route0,1=needs_evidence（11 calls/60,962 tokens/¥0.122）；
  full=verified+answer_ready（12 calls/79,534 tokens/¥0.159）。层子集质量不单调，
  full 是唯一 verified+ready ⇒ 默认 route_policy=union（四层）继续成立；省层保留但风险标注。
- ★ 风险标注：有效 route 缺层且事实/项目/verified 策略时，plan.dynamic_opt.route_quality_risk
  = {level(high/info), missing, evidence, note}，warnings 提示；默认四层不触发，显式省层可审计。
- 判据：test_dynamic_opt 64→69（A/B 证据、项目 high、事实 info、四层无风险、warnings）。
  回归 fused_optimal 30 / fused_full_chain 16 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：默认行为不变（四层）；成本模型/预算上限/阶段路由沿用前版。
- 标签：V2.2.30 / engine-V2.2.30 / app-V2.0.55。

【V2.2.29（2026-10-29，PATCH · 预算层级→运行期墙钟硬上限；同发 App 2.0.54）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.29.py（__version__=2.2.29；引擎侧零行为差）；
  App 2.0.54。
- ★ 墙钟硬上限：warn/critical 档 plan.max_minutes = ceil(估算 tokens/600×1.5/60)（最低 1），
  apply_plan 透传 --max-minutes；显式 opts.max_minutes 优先，ok 档不设限；
  plan.dynamic_opt.budget_cap 同时记录 max_tokens/max_minutes（与 V2.2.28 成对）。
- ★ dual_judge 热缓存验证（约 ¥0.14）：同配置连续两跑 run1 冷 29,848 tokens / run2 热
  30,436 tokens（+588、calls 相同）——该题型下单题 token 收益不显著，如实记录；
  保留 cache 为可选档，不再默认期待单题收益。
- 判据：test_dynamic_opt 60→64（warn 墙钟上限/ok 不设限/显式优先/apply_plan+build_cmd）；
  回归 fused_optimal 30 / fused_full_chain 16 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：显式参数优先；ok 档不设时间/token 上限；项目/quality_first 不降评审。
- 标签：V2.2.29 / engine-V2.2.29 / app-V2.0.54。

【V2.2.28（2026-10-29，PATCH · 预算层级→运行期 token 硬上限；同发 App 2.0.53）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.28.py（__version__=2.2.28；引擎侧零行为差）；
  App 2.0.53。
- ★ 预算依赖闭环：warn/critical 档 plan.max_tokens = 动态配置估算 tokens × 1.5
  （最低 20k，千位取整），apply_plan 透传 --max-tokens；显式 opts.max_tokens 优先，
  ok/quality 档不设限；plan.dynamic_opt.budget_cap 记录依据（可审计）。
- ★ dual_judge=cache 冷缓存单题 A/B（约 ¥0.12）：cache 臂 10 calls/30,622 tokens 约 ¥0.061，
  llm 臂 10 calls/29,957 tokens 约 ¥0.060；cache 略高 +665（无显著节省）——如实记录，
  保留为热缓存/预算极紧备选，下轮验证热缓存。
- 判据：test_dynamic_opt 54→60（warn 上限/ok 不设限/显式优先/apply_plan/build_cmd/budget_cap）；
  回归 fused_optimal 30 / fused_full_chain 16 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 82/82；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：显式参数优先；ok 档不设 token 上限；项目/quality_first 不降评审。
- 标签：V2.2.28 / engine-V2.2.28 / app-V2.0.53。

【V2.2.27（2026-10-29，PATCH · App 全流程开销校准 + 有效 route 成本 + 阶段动态路由；同发 App 2.0.52）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.27.py（__version__=2.2.27）；
  App 2.0.52。
- ★ App 全流程开销：1 臂有界云校准（约 ¥0.07）：App 实际 34,727 tokens vs 引擎模型
  31,620 → app_overhead≈1.10，已计入 dynamic_config 候选 token/成本。
- ★ 有效 route 成本：成本估算改用显式 opts.route（优先）而非预设 route；省层任务不再被
  四层口径高估；plan.dynamic_opt.route 记录实际生效 route。
- ★ 阶段动态路由：预算 warn/critical 且非项目/非 quality_first 时 dual_judge=cache，
  plan.dynamic_opt.applied/stage_routing 可审计；ok 档/项目题/quality_first 保持原评审档。
- ★ 引擎 V2.2.27 实际变更：显式 --route 出现 both 缺 0/1、all 缺 both/0/1 时自动补全
  并打印"层依赖闭包"；单层/无 both/all 的省层 route 不受影响。
- 判据：test_dynamic_opt 46→54（App 开销证据、有效 route、阶段路由、引擎闭包 helper/main）；
  回归 fused_optimal 30 / fused_full_chain 16 / daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 81/81；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：显式 opts 优先；余额未知 fail-open；项目/quality_first 不降评审。
- 标签：V2.2.27 / engine-V2.2.27 / app-V2.0.52。

【V2.2.26（2026-10-29，PATCH · route 子集感知动态成本模型；同发 App 2.0.51）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.26.py（__version__=2.2.26；引擎侧零行为差）；
  App 2.0.51。
- ★ 问题：V2.2.25 动态配置按整单四层估算成本，显式 route=0 / rounds=0:1 会被高估 2-20 倍，
  低余额误判不可行。
- ★ 修法：3 臂有界云实测校准（合计约 ¥0.32）：R1 route=1/rounds=1=37,119 tokens；
  R2 route=0,1/rounds 1+1=62,180（可加预测误差 0.05%）；R3 route=0/rounds=2=63,240。
  拟合 u0=31,620/圈、u1=37,119/圈；两层重叠系数 0.905；both/all 由整单 816,983 反解
  （uB=137,654/uA=183,539）；其他 mode 按 MODES 比例；事实题 web on ×1.12。
  dynamic_config 候选成本改用该模型（route/rounds 取自候选本身），
  plan.dynamic_opt 标注 cost_model=route_subset_rounds.v1，可行域保留 ±10% 容差。
- 判据：test_dynamic_opt 36→46（单层/两层/整单/B 模式/web 增量、校准证据、route=0 接线、
  cost_model）；回归 fused_optimal 30 / fused_full_chain 16 / daosheng_unified 27 /
  auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 81/81；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：显式 opts 优先；余额未知 fail-open 只审计；quality 档不受影响。
- 标签：V2.2.26 / engine-V2.2.26 / app-V2.0.51。

【V2.2.25（2026-10-29，PATCH · 动态配置细化 + 缓存命中感知；同发 App 2.0.50）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.25.py（__version__=2.2.25；引擎侧零行为差）；
  App 2.0.50。
- ★ 多圈档多目标：fast 档枚举 fast/economy/critical 三档圈数，在成本约束（余额×预留）内
  选质量最高者；质量随圈数线性折扣；fast 档质量下限对齐实测 0.90（项目 quality 仍 0.95）；
  quality 档不受低圈候选干扰。
- ★ 缓存命中感知：精确命中按 10% 成本计入可行域；缓存预判前移复用；plan.dynamic_opt
  增加 route / cache_hit 读数；余额未知 fail-open 只审计不改配置（不再误改 rounds）。
- ★ 剩余预算有界 A/B（真实云端 2 臂，合计约 ¥0.28）：同题同 route=0/rounds=0:1/web off，
  ok 档（¥50 假设）→ quality B / auto 圈，实际 13 calls / 76,306 tokens 约 ¥0.15，verified；
  warn 档（¥3）→ fast + economy 圈，实际 11 calls / 64,907 tokens 约 ¥0.13，verified。
  结论：资源收紧自动降档且仍 verified；实际成本远低于整单估算（为 route 子集成本模型留证据）。
- 判据：test_dynamic_opt 28→36 项；回归 fused_optimal 30 / fused_full_chain 16 /
  daosheng_unified 27 / auto_mode_local 12。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 81/81；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：显式 opts 永远优先；余额未知 fail-open 只审计；quality 档不受影响。
- 标签：V2.2.25 / engine-V2.2.25 / app-V2.0.50。

【V2.2.24（2026-10-29，PATCH · 全链路动态配置优化 + 动态依赖调整；同发 App 2.0.49）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.24.py（__version__=2.2.24；引擎侧零行为差）；
  App 2.0.49。
- ★ 动态依赖调整：route 依赖闭包（both 补 0/1，all 补 both/0/1；单层不强加依赖）；
  plan 新增 route_dependency_added，补依赖写 warnings。
- ★ 全链路动态配置：dynamic_config 在每次规划时按 余额/预留/预算层级（ok/degrade/warn/critical）
  × 质量下限（项目/quality_first 0.95，其它 0.90）× 成本（MODES 实测 + web 增量 + 圈数缩放）
  枚举候选，选可行解中质量最高、成本最低者；plan 落 dynamic_opt（candidates/chosen/applied/why）；
  budget_level 降档：ok 质量档、degrade 实测 fast 档、warn economy、critical 全 1 圈；
  applied 只覆盖 rounds（显式 opts 优先），web=auto 不落 opts。
- 判据：新增 scripts/local_model/test_dynamic_opt.py（28 项，进一键验收 strict）：
  route 闭包、多目标可行域/预留比例/层级降档/单调降本/fail-open、plan 接线、
  apply_plan→build_cmd、变异体。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 30 / SKIP 0 / FAIL 0；fused_optimal 30/30；
  fused_full_chain 16/16；daosheng_unified 27/27；e2e 18/18；四层 probe 81/81；
  发布流程门 pre/post-tag 全 PASS。
- 兼容性：显式 opts 永远优先；余额未知 fail-open；预算只降圈/降档不砍层。
- 标签：V2.2.24 / engine-V2.2.24 / app-V2.0.49。

【V2.2.23（2026-10-29，PATCH 修复 · route 安全门；同发 App 2.0.48）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.23.py（__version__=2.2.23；引擎侧零行为差）；
  App 2.0.48。
- ★ 真实运行复盘：任务 20261029_113643_e25f29（「极端天气为什么越来越频繁」，mode=auto→daosheng）
  只调度了研究层。根因链：本地 0.5B route 适配器预测 route=["1"]（source=http，无置信度）→
  build_plan 直接采用 → plan.route="1" → apply_plan 落 opts.route="1" → 引擎显式 --route 1
  → dispatch ran=["1"]，其余层只有占位产物。旧 standard 默认四层。
- ★ 修法：route 安全门。configs/道生专属模式.yaml + _BUILTIN_DS 新增 route_policy：
  union（默认；预设 ∪ 预测，预设四层时结果恒四层，预测只作审计/补充，不砍层）、
  preset（忽略预测）、predict（旧砍层行为，显式实验用）；非法值回落 union；
  plan 新增 route_policy/route_source/route_prediction 读数，拦下时写 warnings。
- ★ 判据：fused_optimal 24→30 项（route 安全门 A9–A12：默认 union、预测=["1"] 时实际四层、
  predict/preset/非法值三种策略、真实本地预测复现「极端天气」问题修复）。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 29 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 81/81；
  发布流程门 pre/post-tag 全 PASS（N/A 带原因）。
- 兼容性：默认 union 是修复（四层不再被 0.5B 预测静默裁掉）；要省层需显式 route_policy: predict。
- 标签：V2.2.23 / engine-V2.2.23 / app-V2.0.48。

【V2.2.22（2026-10-29，PATCH · 动态最优配置全流程可达 + 融合模式"更优"判据；同发 App 2.0.47）】
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.22.py（__version__=2.2.22）；App 2.0.47。
- ★ 问题：MetaDGTF.run() 支持 max_minutes/max_tokens，但 main() 从不传 ⇒ 墙钟/令牌预算
  只能从代码调用，CLI/App 全链路不可达；dynamic_adjust 的预算降档在真实任务里无法触发。
- ★ 修法：引擎新增 --max-minutes / --max-tokens 并传入 meta.run()；App engine_runner
  _ARG_SPEC 新增 max_minutes/max_tokens 映射 + 能力门控（旧引擎不透传）。
  预算到达 ⇒ 层/波边界 dynamic_adjust 降档 fast（质量下限允许时）；rounds_locked
  场景只调 thinking/web、不改圈。
- ★ 判据：新增 scripts/local_model/test_fused_optimal.py（24 项，进一键验收 strict）：
  能力对等（质量策略/缓存/预算/背景注入/web 规则/失败回退 + 道生能力）；
  更优（MEASURED_SCENARIOS 同题真跑：成本档质量 ±0.02 内、tokens 省 ≥15%，3 场景至少
  2 个成立；质量优先档 B 不降）；动态配置（引擎 _auto_mode_tick 真代码三场景：锁定不压圈 /
  未锁定压圈 / fast 质量代理低升 B）；变异体（删预算 CLI / 忽略 rounds_locked / 丢质量策略）。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 29 / SKIP 0 / FAIL 0；fused_full_chain 16/16；
  e2e 18/18；四层 probe 81/81；发布流程门 pre/post-tag 全 PASS。
- 兼容性：不传预算参数行为与 V2.2.21 逐字相同；旧引擎能力门控自动不透传新 flag。
- 标签：V2.2.22 / engine-V2.2.22 / app-V2.0.47。

【V2.2.21（2026-10-29，PATCH · 道生模式与标准模式融合；同发 App 2.0.46）】
- 生产引擎：`dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.21.py`（__version__=2.2.21；引擎侧零行为差，
  参数通道沿用 V2.2.20）；App 2.0.46。
- ★ 融合：道生模式 = 标准模式。resolve_mode：auto → daosheng（auto-fused；project_related
  只决定背景注入，不改链路）；standard → daosheng（fused-standard，requested 保留）；
  全项目单一链路 = 道生 plan（preset + M4 + 预算守卫 + MODE_CONFIGS）→ --mode 透传 →
  运行期 dynamic_adjust（rounds 锁定语义）→ 产物/回显。旧 standard 链路仅作计划生成
  失败时的 fail-open 回退保留。
- ★ 回显：mode 新增 fused / fused_from；前端标签"标准·道生"；App selftest 三处判据更新为
  融合语义（总数不变）。
- ★ 全链路打通：新增 `scripts/local_model/test_fused_full_chain.py`（服务型零 API）：
  自起临时 App server → POST /api/tasks（auto 默认）→ 引擎真跑本地 0.5B →
  校验 mode.id=daosheng/fused、plan.policy=daosheng.v1、engine_mode∈{B,fast}、
  packed.provenance=V2.2.21、auto_mode.plan/adjustments、answer_gates/calls；
  一键验收新增 fused_full_chain 步骤。
- 验收：fast_gate 16/16；V2 71/71（1208 checks）；App selftest 455/0；
  一键验收 --with-service PASS 28 / SKIP 0 / FAIL 0；e2e 18/18；四层 probe 81/81；
  发布流程门 pre/post-tag 全 PASS（N/A 带原因）。
- 兼容性：显式 mode=standard 调用方无感（201；id=daosheng/requested=standard）；