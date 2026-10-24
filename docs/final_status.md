# 接管目标完成状态（2026-10-22）

## 核心目标

- [x] DSH 接管：源码/文档/配置/测试可读写；git add/commit/tag/版本迭代；push/密钥/ACL 保持人工确认。
- [x] 提案：pending=0；全部有结论与证据。
- [x] App 可上线：HTTPS/鉴权/CSRF/Host/上传与 JSON 上限/超时/401/孤儿任务/原子写/日志保留/scratch 清理/前端错误提示/上线检查单。
- [x] 引擎准确与深度：fact gate、process/answer 分离、answer_summary/depth、否定结论审计、答案相关性/URL 门。
- [x] 全自动帕累托：后台自动选优 + 任务级 auto_policy 圈数执行。
- [x] 本地模型更多权重：自动策略实测 last_strategy=local_model，并影响任务圈数预算。
- [x] 正向真实跑：len 69 calls/652846 tokens/约12min；answer_ready=true、process_ready=4/4、answer_quality=verified、gaps=[]；app score=85 A。
- [x] 门禁：fast_gate 12/0、selftest 371/0、依赖审计 78/0、HTTP 200。

## 版本

- app：2.0.0（app-V2.0.0）
- engine：2.0.0（V2.0.0；F5 生成完成）
- 最新提交：8da4977
- pending 提案：0
- auto_strategy：local_model

## 人工/外部边界

- git push / 远端仓库 / 凭据 / ACL / 生产部署 / 服务账户：仍需人工确认。
- 真实联网质量受搜索源影响；算法层已用答案门/相关性门兜底，不再把噪声冒充事实。

## 用户复核项完成记录（2026-10-23）

- [x] 本机打开 App：已通过 show_access_url 打开；认证页面关键控件存在，dgtf_app/selftest.py PASS 371/0。
- [x] 浏览器 favicon 与桌面快捷方式图标统一为 dgtf_app/static/dgtf.ico；桌面 .lnk 与快速 .url 均指向该图标。
- [x] python scripts/cleanup_runtime.py --apply：删除 4 个 **pycache**，未动 outputs/dgtf_memory。
- [x] auto_policy vs profile A/B：auto_policy 90 calls/881364 tokens/1164.7s，verified 4/4；profile auto 116 calls/1073702 tokens，1201.6s 超时无 packed。报告 reports/goal_ab_auto_policy_20261023.md。
- [ ] git push：远端 github.com:443 连接失败（无法访问），未推送。
- [ ] 生产部署：无远端部署目标；本机 App 继续运行在生产入口 <https://127.0.0.1:8765/。>

---

## V2.1.0 收束状态（2026-10-23）

- 版本：V2.1.0（历史谱系融合）
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.0.py
- App：2.1.0
- 历史融合：178 个版本 / 17 条能力轴 / readiness 1.00
- 门禁：fast_gate 12/0、V2 tests 33/33、App selftest 371/0、pip check 0 broken
- 文档：docs/history/、docs/releases/V2.1.0.md、V2.1.0-收束报告.md
- 历史仓库名：GitHub 仓库名仅 ASCII，使用 Meta-DGTF；完整中文名用于描述和文档

---

## V2.2.0 行为融合状态（2026-10-23）

- 引擎：Meta-DGTF-V2.2.0.py
- App：2.0.0（本次未改动）
- 行为 arm：5 个（v1_spiral / v1_frontier / v2_contract / v2_pareto / fusion_full）
- 行为融合：auto mode/rounds/stop/thinking/effort；显式 CLI 优先
- 判据：V2 tests 34/34、单引擎内联融合 13/13（含 history + behavior）
- 文档：docs/history/行为级融合、V2.2.0-收束报告

---

## 2026-10-24 推理题质量门迭代（V2.2.0 补丁）

- 修复提交：`d12140d`（why→reasoning + 研究层判定审计并入池内子问题）、`27bbe5c`（元层闭环清算汇总后刷新）、`c8d43d5`（判定审计只拦越权断言 + 纯数字过滤）。
- 新增判据：tests_question_type.py（10 项）、tests_meta_closure_refresh.py（7 项）、tests_decidability_audit.py +4 项。
- 门禁：fast_gate 12/0；V2 tests 37/37；App selftest 371/0；pip check 0 broken。
- 随机真跑（城市热岛昼夜差异）4 轮迭代后：answer_ready/process_ready/verified、standard_all=true、研究层判定审计 verified、元层闭环 clean、core audit gaps/overreach=[]；最终 138 calls / 1,581,220 tokens。
- 详见 `docs/real_run_V2.2.0.md` §4.7、`docs/verification_reasoning_gate.md`。

---

## V2.2.1 补丁发布状态（2026-10-24）

- 版本：V2.2.1（PATCH：质量门闭环 + 职责读数 + 质量线索降噪 + 覆盖率/三态读数 + App DSH 实时视图）
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.1.py（V2.2.0 保留可回滚）
- App：2.0.1
- 门禁：fast_gate 12/0、V2 tests 38/38（480 项检查）、App selftest 371/0、pip check 0 broken
- 真实跑复核：最新真跑 answer_ready/process_ready/verified、standard_all=true、core audit gaps/overreach=[]
- 成本：本轮未新增真跑；新增离线质量门预检（scripts/precheck_quality.py）验收既有产物；
  4 份历史真跑正负对照 4/4 符合预期（FAIL/FAIL/FAIL/PASS）
- 队列：7 条高严重度项核验关闭（docs/queue_closeout_20261024.md），high 归零
- 文档：docs/releases/V2.2.1.md、V2.2.1-发布报告.md、V2.2.1-收束报告.md、CHANGELOG.md


---

## V2.2.2 补丁发布状态（2026-10-24）

- 版本：V2.2.2（职责终局刷新 + 部分覆盖 C + unsaid 双源闸 + DeepSeek 官方联网默认 + 帕累托先行模块）
- 生产引擎：dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.2.py（V2.2.1/V2.2.0 保留可回滚）
- App：2.0.3（health/chats 读数缓存）
- 门禁：fast_gate 12/0、V2 tests 39/39（522 项检查）、App selftest 371/0、pip check 0 broken
- 真实跑复核：20261024_160020 官方联网 search=11/fetch=4；20261024_163455 成本档 quality=0.99、flags=0、997,457 tokens/107 calls；20261024_171058 均衡档 quality=0.951、flags=0、1,210,815 tokens（被成本档支配）；20261024_190707 3层负结果不可行（all 元层未执行，归档 outputs/negative_runs）
- 帕累托：scripts/pareto_flow.py（预算选档/联动快照）+ scripts/local_model_bench.py；基线 docs/pareto_flow_v1.md
- 文档：docs/releases/V2.2.2.md、V2.2.2-发布报告.md、V2.2.2-收束报告.md、docs/releases/app-V2.0.3.md