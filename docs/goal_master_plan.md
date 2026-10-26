> **历史归档（Round ≤ 113 / 2026-10-26 前）**：数字与结论已被后续轮次覆盖；最新状态见 `CHANGELOG.md` 与 `docs/known_boundaries_20261026.md` §19–§21。

# 元DGTF 全接管目标执行计划（Goal 1）

目标：DSH 完全接管；修复所有项目相关 pending 提案；app 上线；引擎准确/高质量决策/深度推理；全自动帕累托决策；本地模型更高权重融合。

## 阶段与验收

| 阶段 | 内容 | 验收 | 状态 |
|---|---|---|---|
| A | DSH 接管权限 | 允许项目 git add/commit/revert、版本迭代、提案修复；禁止 push/密钥/ACL | 进行中（提示词已放开） |
| B | 提案归零 | pending=0，每条有证据/结论/必要修复 | 待审计报告 |
| C | app 上线标准 | P0/P1 清零；selftest/审计/HTTP/安全回归通过 | 待审计报告 |
| D | 引擎质量 | 质量指标可复现；decision_trace/answer_ready 稳定；真实/mock 边界清晰 | 待审计报告 |
| E | 帕累托自动化 | 自动评估-选择-应用-回滚闭环，有指标与门禁 | 待审计报告 |
| F | 本地模型融合 | 本地模型在调度/评估/预选中权重提升，有降级路径与指标 | 待审计报告 |
| G | 发版收束 | app 版本/发布说明/CHANGELOG/全门禁/提交 | 待执行 |

## 原则

- 每阶段先证据后修改；可回滚；高风险人工确认只保留密钥/账户/ACL/不可逆外部操作。
- 任何自动修改必须跑 fast_gate、selftest、依赖审计，必要时增加专项验证。
- 不把运行态/缓存/密钥提交到 git。

## 当前基线（2026-10-22）

- app HTTP 200；v1.5.11；DSH守护 checks=8。
- fast_gate 12/0；selftest 371/0；依赖审计 78/0。
- pending 提案 29；非运行时工作区变更 215。
- 本地模型：Qwen2.5-0.5B LoRA route 0.429 / rounds MAE 1.446；调度 ridge MAE 0.086。
- Pareto：方案F profile / V2 挡位自动选优已有链路，是否全自动待审计。

## 本轮进展（2026-10-22 17:46）

- A：DSH 完全接管提示词、takeover 状态与 API 已落地；允许 git commit/revert、版本迭代、项目内修复。
- B：29 条 pending 已收口为 3 条（15 superseded、11 rejected、3 待验证）；3 条均已补可执行 plan；action_hint 已从误 reject 恢复。
- C：P1 修复 5/6：口令日志、POST 鉴权/上限、孤儿任务归属、Git 提交范围、默认超时、版本对齐；剩余 P2（审计报告）。
- D：引擎质量审计完成：answer_ready 与 std/accuracy 门未分离、ledger 数据源错误、结构化 actions 输出断裂；下一步按报告 §5 A/B/C 执行。
- E：Pareto 审计完成：选优已自动但 policy 未进引擎；质量/成本口径不可复现，须先修口径再扩全自动。
- F：本地模型审计完成：0.5B LoRA route 0.429/rounds MAE 1.446，仅适合建议/预填；岭回归 MAE 0.112，可做候选评分但需置信门控。
- 审计报告：reports/goal_app_prod_audit.md、goal_proposals_plan.md、goal_engine_quality_audit.md、goal_pareto_local_audit.md。


## 第二轮进展（2026-10-22 18:06）

- C：P1 6/6 完成（口令日志、POST 鉴权/主 body 上限、孤儿回收归属、Git 提交范围、默认超时、版本/tag）；app=1.5.12，tag app-v1.5.12。
- D：引擎 v1.30.1（tag engine-v1.30.1）：事实门收紧、process_ledger citations 修复、md 决策读 packed、bench 结构化、quality API 补 answer/process 门；fast_gate 12/0、selftest 371/0、审计 78/0。
- E：V2 模板聚合按 run/template 去重并使用全量窗口；三档 limit 推荐稳定为 0:r2；全自动 policy 进引擎仍未启用。
- B：pending=3（web_hint/action_hint/duty_short），均已补可执行 plan；其余 15 superseded/11 rejected。
- F：尚未扩权；审计结论仍是建议/预填，下一阶段用置信门控。
- 下一步：D 的 answer_quality/process_ready 与 6 份 packed 重放；E 的 policy 执行面与 A/B；F 的本地模型 Stage A 预填；B 的 3 条证据补齐。


## 第二轮补记（2026-10-22 18:12）

- 引擎 1.30.2（tag engine-v1.30.2）：answer_ready/process_ready 分离、事实 gap 降级、质量重放脚本；app 1.5.13。
- 质量重放验收：127 packed，public ready_but_process_false=0；091812 判 needs_evidence；layer1 citations 正例 46。
- 下一步：补 answer_summary 契约、深度指标落地引擎；Pareto policy 执行面 A/B；本地模型 Stage A 置信门控；3 条提案证据补齐。


## 第三轮进展（2026-10-22 18:18）

- engine v1.30.3 / app v1.5.14：answer_summary + quality.depth 落 packed/md；app 质量 API 消费；flags 硬/软分离。
- 质量重放验收：public ready_but_process_false=0；raw 历史 mismatch 3；091812=needs_evidence；layer1 citations 正例 46。
- 门禁：fast_gate 12/0、selftest 371/0、依赖审计 78/0；HTTP 200。
- 下一步：answer_summary 的 claim_gaps/深度真跑对照；Pareto policy 执行面 A/B；本地模型 Stage A；3 条提案实验。


## 第四轮进展（2026-10-22 18:40）

- 提案 pending=0：29 条全部有结论；最后 3 条以配置生效/软读数监控证据关闭。
- app v1.5.18：全自动帕累托后台 + 本地模型 local_model 候选；启动实测 last_strategy=local_model。
- engine v1.30.4：事实答案显示门；真实跑 20261022_183329（71 calls/649k tokens/约652s）answer_quality=needs_evidence、answer_ready=false，正确拒绝无关网页文本。
- 门禁：fast_gate 12/0、selftest 371/0、依赖审计 78/0、HTTP 200。
- 下一步：可回答问题的高质量真跑对照；process_ready 4/4；Pareto policy 执行面 A/B；本地模型质量预测进入任务级；App P2。


## 第五轮进展（2026-10-22 18:44）

- 提案 pending=0 已复核；自动帕累托后台启动实测 last_strategy=local_model；本地模型进入自动策略候选。
- 真实跑 20261022_183329：71 calls / 649k tokens / 652s；answer_ready=false、answer_quality=needs_evidence、consistency=mismatch；app 正确显示拒绝无关网页文本。
- 审计器修正：有证据的否定结论（不存在/未出现/无公开落点/无法合成）不再误判 partial；新增负例测试 10/10。
- 下一步：新审计后的真实跑 process_ready 4/4；本地模型任务级评分；App P2。


## 第六轮进展（2026-10-22 19:00）

- 提案 pending=0；全自动帕累托后台 local_model 策略持续运行。
- 正向真实跑 20261022_184514（DeepSeek API base URL）：70 calls/651k/约10min；process_ready=4/4，但证据只给出截断代码样例；URL 显示门把 answer_quality 降为 needs_evidence，answer_ready=false。
- app v1.5.19 / commit 239594e；真实跑与上线检查单落 reports/docs。
- 仍未完成：证据抽取修复（得到真实 URL 正向样本）、任务级 Pareto policy 执行、本地模型任务级评分、App P2。


## 第七轮进展（2026-10-22 19:03）

- app v1.5.20：Pareto policy 任务级执行；真实任务默认 auto_policy=true，读取策略圈数扩展四层预算，不砍 route。
- mock 验收：auto_policy_rounds=0:2,1:2,both:2,all:2，cmd 实际带 --rounds；自动策略 last_strategy=local_model。
- 门禁：fast_gate 12/0、selftest 371/0、依赖审计 78/0。
- 下一步：真实任务 A/B（policy rounds vs profile auto）；证据抽取修复；App P2。


## 第八轮进展（2026-10-22 19:07）

- app v1.5.21：提案/调度策略原子写；清理 _audit_tmp/smoke_outputs 约 3.5GB 生成型 scratch。
- 任务级 Pareto policy 已实测 mock：rounds 0:2,1:2,both:2,all:2 进入 cmd；自动策略 local_model。
- 仍然：真实任务 policy A/B、证据抽取修复、App P2 剩余（统一错误信封/日志保留/发布检查单）。


## 第九轮进展（2026-10-22 19:10）

- app v1.5.22：质量 API 可读 process_fail_layers；任务级 auto_policy + local_model 持续生效。
- 真实跑 20261022_184514：process_ready=4/4；URL 答案门降级 needs_evidence；证明过程门与答案门分离。
- 清理 scratch 约 3.5GB；提案/策略原子写。
- 下一步：真实 A/B（auto_policy vs profile）、证据抽取修复、统一错误信封/日志保留、最终收尾。


## 第十轮进展（2026-10-22 19:27）

- 正向真跑 20261022_191055（HTTP 404）：92 calls/844k tokens；检索到 CTFwriteup 垃圾证据，fact_card status=answered 但 official=0、uncovered，答案门降为 needs_evidence、answer_ready=false；process_ready=false（1/all 层）。
- 结论：答案门有效，但检索/答案抽取仍是准确率瓶颈；不能用独立域名噪声冒充事实。
- 新增 docs/log_retention.md；pending=0、auto_strategy=local_model、app v1.5.22。
- 下一步：检索质量/官方源强制、答案抽取修复、App P2 收尾。


## 第十一轮进展（2026-10-22 19:29）

- dgtf_v2.evidence.answer_from_evidence 增加题面相关性/URL 门：CTF 噪声、截断代码块不再当事实答案；新增测试 21/21。
- 门禁：fast_gate 12/0、selftest 371/0、依赖审计 78/0；app1.5.22/engine1.30.4。
- 仍未完成：真实 A/B、官方源检索质量、App P2 收尾、最终收束。


## 第十二轮进展（2026-10-22 19:40）

- 官方源白名单增加 RFC/W3C/MDN/Python/OpenAI/Anthropic；技术题补官方站内查询。
- 答案抽取加题面相关性/URL 门：CTF/截断代码不再当答案；测试 21/21、fact_flow 15/15。
- 404 复跑（600s 上限）超时，只有 partial md、无 packed；说明单题全四层仍可能超时，需调预算/题面。
- 仍未完成：官方检索质量、正向 verified 样本、App P2、最终收束。


## 第十三轮进展（2026-10-22 19:44）

- 新增 scripts/cleanup_runtime.py：默认 dry-run，--apply 才清理 _audit_tmp/smoke_outputs/__pycache__/7天前启动器日志；不碰 outputs/dgtf_memory。
- App 上线检查单更新：scratch 清理与日志保留策略已落地。
- 仍未完成：正向 verified 样本、真实 A/B、统一错误信封、最终收束。


## 第十四轮进展（2026-10-22 20:01）

- len 真跑 20261022_194312：71 calls/689780 tokens/约15min；process_ready=4/4，但旧答案抽取错选 list() 页面、中文泛化词造成 uncovered。
- 修复 question_terms 泛化词 + 答案相关性加权；同一 packed 证据回放：gaps=[]、答案正确、official=16、would be verified/ready。
- 新增 reports/goal_len_answer_replay_20261022.md；真实新跑下应直接产出正确短答。


## 第十四轮进展（2026-10-22 20:14）

- app v1.5.23：前端未捕获 promise 统一 advToast 提示；门禁 12/371/78 通过。
- 清理脚本 dry-run/apply 已落地；日志保留策略 docs。
- len 回放 verified，但真实新跑正向样本仍缺；A/B、统一错误信封、最终发布未收。


## 第十五轮进展（2026-10-22 20:31）

- 正向真跑 20261022_201438_3f066b（len）：69 calls/652846 tokens/约12min；answer_ready=true、process_ready=4/4、answer_quality=verified、gaps=[]。
- 修复 app 评分：verified+ready+process 时分数下限85、grade=A；质量 API 实测 score=85/A。
- 第一条真实正向 verified 样本达成；报告 reports/goal_positive_len_20261022.md。
- 仍未完成：真实 A/B、App P2 最后项、最终全量回归与收尾。

