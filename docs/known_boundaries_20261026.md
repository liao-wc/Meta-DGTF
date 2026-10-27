# 已知边界清单（2026-10-26，Round 87）

> 原则：**只变好不变坏**；门禁不放宽；失败记录不删除；边界如实冻结。

## 1. 已闭环

| 边界 | 闭环方式 | 证据 |
|---|---|---|
| 成年年龄（8 vs 18 周岁） | 成年 sanity：<18 改取成年人条款，无则拒答 | 0.9575/verified，display=十八周岁（Round 85） |
| 选择题官方源缺失 | 选项题（A./B./C./D.≥2）豁免 no_official_source | **0.9387/verified/ready**（choice auto3，Round 86–87） |
| 全长/分段口径（港珠澳 42 vs 55） | _whole/_tot/_mag 偏好 + display 取总长 | 0.92/verified，display=55公里（Round 48） |
| 双值/范围/列举/地点/命名展示 | display 收窄十法 | A54/A57/A60/A61 等判据 |
| 年份错配/比较年份/历史旧规 | 硬拒答 + 年度口径 + 现行性守卫 | 判据 A24–A43 |

## 2. 阻塞（需改引擎；当前工作树被并发会话占用，不强行编辑）

| 边界 | 具体阻塞 | 记录 |
|---|---|---|
| **dual_judge local 档** | 引擎 `--dual-judge-mode` choices=["llm","cache","auto"]，无 local；引擎文件 git status: M（并发会话） | Round 50/86/87；App 层已防护回退 llm；cache 档已真跑验证（0.9464/verified） |

## 3. 待优化（门禁内）

| 边界 | 现状 | 下一步 |
|---|---|---|
| `probe_no_target_covered` | 「海水为什么咸」auto 0.2435/unverified：答案实质但未覆盖探针目标（引擎侧 flags） | 需引擎探针目标生成/覆盖判定（同被占用）；先冻结 |
| 检索源依赖 | 缺目标年份/现行法/官方页时拒答（宁缺毋假） | 继续 query 扩展与证据优先级（离线可做） |
| 旧 pack 严格拒答 | 124 packs 中 34 条 answered→unknown（旧低质答案被严格门拒） | 有意收紧；如需保留需补官方源 |
| local self_check opt-in | token −12~20%、墙钟 +31~57%、质量噪声级 | 维持 opt-in；v8b 为默认 |

## 4. 并发与成本口径（已治理）

- ab_bench：`cost_window_cny / cost_attribution / cost_note`；`cost_cny` 仅兼容保留；
- `dgtf_memory/real_run.lock`（pid/tag/start/est/ttl=1800s）：活跃锁默认拒绝真跑
  （exit 3），`--force-concurrent` 显式覆盖；
- 单日真跑 ≤3（本日已用尽，暂停）；余额保留 ≥50 CNY。

## 5. Round 90 新增闭环/量化

| 项 | 内容 |
|---|---|
| 地点/排序问句分类 | 已闭环：哪个/哪座/哪里/位于/设在/最大/最高/最长/最小 → fact；App 事实档强制 web on；App 地点 e2e 0.9288/verified/display=纽约市 |
| probe_no_target_covered | 已量化：267 packs 30.3%；verified 中 30.7%（答案正确也扣分）；引擎侧待优化（冻结） |
| App e2e 矩阵 | 9 行（新增 UNHQ 地点行） |

## 6. Round 91 新增闭环

| 项 | 内容 |
|---|---|
| 选项题 App 链路 | 已闭环：选项标记→choice + App 强制 web + uncovered 豁免；App e2e 0.9516/verified |
| 多值/单位展示 | 已闭环：出生人口 App e2e 0.9842/verified，display=954万人 |
| App e2e 矩阵 | 12 行；fast 覆盖 reasoning/fact/choice |

## 7. Round 92 新增闭环

| 项 | 内容 |
|---|---|
| 万亿元单位 | 已闭环：43.85万亿元 fast+web 0.97/verified，display=43.85万亿元 |
| 年限展示 | 已闭环（引擎层）：租赁 20年 display（A68）；App 同题缓存命中，未复跑 |
| 进出口整体量 | 已闭环：「进出口」不再被 pen 当子项（A70） |
| App e2e 端口 | 已支持自动空闲端口（并发会话不冲突） |

## 8. Round 93 新增

| 项 | 内容 |
|---|---|
| 命名题数值劫持 | 已闭环：命名问句不走数值答案（A71/A72）；最高高原 0.9776/verified |
| App 精确缓存 | 同题复跑会命中缓存（tok=0）⇒ App e2e 需新题；缓存不自动失效（已知限制） |
| 本地 v8b self_check | A/B：出生人口 0.99/＋2.27pp/−5.3% tokens；光速 tokens +5% ⇒ 默认 llm、local opt-in；v9b 已完成（Round 123；v9 已归档） |
| App e2e 端口 | 自动空闲端口（8800+），并发会话安全 |

## 9. Round 95 更新

| 项 | 内容 |
|---|---|
| dual_judge local | **已实现（worktree 分支，可控）**：失败回退 llm 真跑 verified；超时调参中；主引擎待合并 |
| v9 训练 | 暂停（为双判本地验证让位 GPU）；之后重启 |

## 10. Round 99–100 维护态

| 项 | 内容 |
|---|---|
| 本地服务 | 训练期间暂停（8772/8771），训练后重启；App 自检 444/0（fail-open 已验证） |
| v9 训练 | ep1 step 20/460，ETA ~5.8h；完成即 held-out 对比 |
| 真实跑次 | 暂停（余额 50.76 近保留线） |
| dual_judge local | 补丁就绪（Round 85 历史）；已于 60b0e81 合并 |

## 11. Round 110–111 维护态

| 项 | 内容 |
|---|---|
| 真实跑次 | **停止**（余额 ¥9.48 < 10；保留硬底线） |
| v9 训练 | 运行中（step ~120/460，外部并发使 ETA 拉长；GPU 满载） |
| dual_judge local | 补丁就绪（0001–0003，T1–T8 8/8），等主引擎合并窗口（Round 111 历史；已合并） |
| 验收 | 无服务 **8/8 PASS**；探针复审 29.3% flagged |

## 12. Round 113 更新

| 项 | 内容 |
|---|---|
| v9 训练 | 外部 GPU 长时竞争 → **中止归档**（partial adapter 保留）；GPU 空闲可重启 |
| 最终综合报告 | docs/最终综合报告-20261026.md（Round 1–113） |

## 13. Round 114 更新

| 项 | 内容 |
|---|---|
| 本地服务 | 已恢复（8771/8772，v8b ready）；一键验收 --with-service **9/9 PASS**（Round 114 历史；最新 16/16） |
| v9 | 归档不变：GPU 6GB 卡无法同时容纳训练(5.8GB)+服务(2GB)，需专用窗口 |

## 14. Round 116 更新

| 项 | 内容 |
|---|---|
| v9 归档原因（更正） | 命令漏传 --model → 用了默认 1.5B base；adapter 不可用于 0.5B 服务 |
| 防错训守卫 | out 名含 05b 但模型非 0.5B ⇒ 拒绝训练（已实测 reject/allow） |
| 正确重训命令 | 见 `llm_sft/adapter_dgtf_selfcheck_05b_v9_aborted_ep1step120/ABORTED.md` |

## 15. Round 117 更新

| 项 | 内容 |
|---|---|
| v9b 重训 | 条件：专用 GPU 窗口（0.5B 训练峰值 ~4.9GB + 本地服务 ~1.9GB > 6GB 卡）；当前 8771/8772 服务由并发会话持有，不宜强停 → 等待窗口 |
| 防错训守卫 | 已验证（reject/allow 两路径）；正确命令见 ABORTED.md |
| 本地模型结论 | 当前 **v8b 为可验证最优**（质量=v6、p50/p95 更快；self_check local opt-in 收益 0.99/+2.27pp 于出生人口题） |

## 16. Round 121 阻塞快照（最终）

| 阻塞项 | 具体条件 | 已持续 |
|---|---|---|
| 真实跑次预算 | 余额 ¥6.26 < 真跑最低门槛（10；硬底线 4） | Round 110 起 |
| dual_judge local 合并 | 主引擎工作树 M（并发会话未提交）；合并器与补丁已全量校验（T1–T8） | Round 49 起 |
| v9b 重训 | GPU 6GB 卡：0.5B 训练 ~4.9GB + 本地服务 ~1.9GB（并发会话持有）超容 | Round 113 起 |
| 剩余可做 | 仅零成本文档/验收维护；（Round 121 历史）矩阵 57→60、V2 835→841、验收 10/10→15/15 | — |

## 17. Round 123 更新（合并完成 + v9b）

| 项 | 内容 |
|---|---|
| dual_judge local | **已合并主引擎**（60b0e81）；App 自动透传；（Round 123 历史）验收 10/10 PASS |
| v9b 训练 | 0.5B base（正确命令），专用 GPU 窗口，~6s/步，ETA ~43min |
| 本地服务 | 训练期间暂停；训练/评测后恢复 |

## 18. Round 124 最终状态

| 项 | 状态 |
|---|---|
| dual_judge local | **已合并**（60b0e81）；App 自动透传；默认仍 opt-in（本地 judge 吞吐） |
| 本地模型默认 | **v9b**（val 0.1989；held-out 质量=v8b、更快；v8b/v6/v5/v2 兜底） |
| 验收 | **16/16（有服务）/ 15/15（无服务）**（Round 132 最新；本表为 Round 124 快照） |
| 剩余边界 | probe_no_target_covered（引擎侧扣分，29.3% packs）；App 精确缓存；旧 pack 严格拒答；检索依赖 |

## 19. Round 126 更新

| 项 | 内容 |
|---|---|
| probe_no_target_covered | **已加词面近义 AND 兜底**（R7：sim3≥.25 且 overlap≥.30），救回约 9.8% flagged；其余仍如实报 |
| dual_judge 吞吐 | **忙时 503 BUSY 快失败**（17.7ms 回退信号）；引擎毫秒级回退 llm；计数可审计 |
| App 缓存 | **no_cache/force_rerun 显式绕过**（缓存+去重），e2e 可用 `DGTF_E2E_NO_CACHE=1` |
| 预算覆盖面 | 仍阻塞：余额 ¥0.74（<4）；充值后可恢复真跑清单 |
| 验收 | **16/16（有服务）/ 15/15（无服务）**（Round 132） |

## 20. Round 127 收束

| 项 | 内容 |
|---|---|
| dual_judge local | 合并后主引擎真跑 0.9857 verified；本地 judge 吞吐仍限（8 次回退）⇒ opt-in |
| self_check 槽位 | 回 **v8b**（v9b local A/B 两题更低）；self_check_min 保持 v9b |
| 外汇冲突 | 时间锚定消解已落地（A86；离线 answered/32024 亿美元），待有预算时复跑确认 |
| probe 覆盖 | R7 兜底已落地（9.8% flagged 翻正，语义样例相关）；其余仍如实报 |
| 真实跑次 | 用户限定 ¥10；已用约 ¥4.8，**停止真实跑次**，进入收束维护 |
| 版本 | App **2.0.35**（收束版） |

## 21. Round 128：产物问题审计

- 完整审计报告：docs/产物问题审计_20261027.md（359 packs / 145 A/B 行 / 文档全文一致性 / 仓库与运行态）；
- 本次已修：当前面文档过期数字（README/交付说明/综合报告/known_boundaries/local_model/app_release_process）、
  budget_ledger 重写（编码修复）、gitignore 增加 !docs/probe_cover_audit_*.json、本报告与指针；
- 未做（建议）：outputs 保留策略/清理、未使用 merged 模型（约 4.4GB）、陈旧 worktree、_audit_tmp 清理、
  ab_results cost 字段迁移、configs 预设过期注释（文件被并发会话持有）。

## 22. Round 130 更新（授权处理审计项）

| 项 | 内容 |
|---|---|
| 历史包一致性 | 7 条矛盾/错误包已修复（2+2→4；备份+修复说明）；一致性护栏 legacy=0 |
| 资产清理 | 释放约 4.6GB（merged 模型 4.35GB、worktree 154MB、_audit_tmp 103MB）；双判分支保留 |
| duty_short | 新增 `flags_info`/`process_flags` 分类（不改打分）；阈值调整需真跑验证 |
| 配置注释 | `configs/道生专属模式.yaml` local 注释已同步（并发 WIP 已 stash 保护） |
| 验收 | **15/15（有服务）/ 14/14（无服务）**；V2 52/842 |

## 23. Round 131：基于产物的项目问题分析

- 报告：docs/项目问题分析_20261027.md；脚本：scripts/project_analysis.py；数据：docs/project_analysis_20261027.json；
- 关键读数：359 packs / 累计 2.40 亿 tokens（重复问题额外 64.2%）；verified 趋势 28.6%→73.3%；
  coverage 均值 0.56；tri_alpha 不可靠 87.6%；fact_card ok 38.7%；display 32.3%；
  duty_short 76.6%、probe_link_dangling 46.8%；0/359 版本指纹；A/B 97/145 缺 cost；
- 结论（P0）：erified 语义分叉（事实 vs 过程合同）+ tri_alpha 不可靠；64.2% tokens 浪费在重复问题、
  29 条截断跑次。Round 129–130 已修算术/一致性/flags 分类；**语义拆分与成本效率为下一步优先**。

## 24. Round 132 更新（按项目问题改进）

| 项 | 内容 |
|---|---|
| 验证语义 | 新增 `quality.verification`（事实正确性 vs 过程合同分离）；tri_alpha 不再冒充事实正确性 |
| 展示/截断门 | 事实 verified 无 display ⇒ ready=False；体力耗尽截断 ⇒ ready=False |
| 重复成本 | `ab_bench` 同题 verified 默认拒绝（`--allow-repeat` 覆盖）；历史重复 tokens 64.2% 可止 |
| 溯源 | 新产物带 `provenance`（git SHA/config hash/app version）+ `question_hash` |
| 告警分级 | `quality.alert`：process→info / coverage→warn / core_audit_gaps→block |
| A/B schema | 97 条旧行回填 cost 字段（不可归因标注）；新行成本+provenance 关联 |
| 验收 | **16/16（有服务）/ 15/15（无服务）**；V2 54/854；真跑验证 0.975 verified |
| 遗留 | duty_short/probe 校准、legacy 19+57、输出保留策略、矩阵 2 行 pending live、本地模型质量增量 |

## 25. Round 133 更新（遗留项清零）

| 项 | 内容 |
|---|---|
| legacy 修复 | 31 条（19 truncated_ready + 12 fact verified_no_display）→ ready=False（含理由）；矛盾判定收窄后 legacy=0 |
| 输出归档 | fact 包全保留；非 fact 每问题留 2 份；117 包/235 文件 → `outputs/_archive_20261027/`；packs 360→243 |
| A/B 口径 | 146 行加 `quality_band`（high 103/low 43）+ `baseline_role`；`docs/ab_summary_20261027.md` |
| 矩阵锚点 | 2 行显式 `anchor_status=pending_live`（guard 打印，不伪造） |
| 文档索引 | `docs/README.md` 当前必读/历史归档/维护约定 |
| 验收 | **16/16（有服务）/ 15/15（无服务）**；V2 54/854；真跑验证 0.975 |
| 遗留 | duty_short/probe 校准、local self_check 质量增量、dual_judge 吞吐、fact 保留策略、tri_alpha 测量学 |

## 26. Round 134 更新（保留策略定稿）

| 项 | 内容 |
|---|---|
| 输出保留 | 非 fact 每问题 2 份 + fact 每问题最新 6 份；**360→230 packs**；重放基线 PASS（120/22/124 试算，135/27/137 定稿） |
| 归档 | `outputs/_archive_20261027/`（可 `--restore`）；fact-keep=2/4/6 三档已实测 |
| 分析刷新 | 230 packs：truncated_but_ready=0、fact verified_no_display=0；非 fact 34（设计内） |
| 验收 | 16/16（有服务）/ 15/15（无服务）；V2 54/854 |

## 27. Round 134：dual_judge 本地吞吐评测（证据）

- `docs/dual_judge_tokens_eval.json`：12 条 val × 5 档 token（320/224/160/96/64）；
- 320：json 0.75 / position_acc 0.279 / p50 25.5s / p95 58.7s；
- 缩 token 只降延迟不救质量（64：json 0.083 / pos 0.033）；
- 决策：**不改服务默认**（质量优先 + 503 快失败）；下一步重训 judge 适配器 v3（数据扩充 + held-out 选型）。

## 28. Round 135：judge_v3 + pareto 修复

| 项 | 内容 |
|---|---|
| judge_v3 | val 1.3649（v2 1.4836）；held-out json 0.833/0.750、pos 0.475/0.279、macroF1 0.273/0.127、p95 35.3s/58.7s ⇒ 默认 v3，v2 兜底 |
| 端到端 | HTTP304 dual local：0.9732 verified；本地双判 8/8 回退（1 timeout + 6 503 + 1 非 JSON）⇒ 吞吐仍是瓶颈 |
| pareto | process flag（duty_short）不再扣质量分；230 packs 179 上调 / 0 下调（F5） |
| 验收 | 16/16（有服务）/ 15/15（无服务）；V2 54/855 |
| 遗留 | judge 本地吞吐适配层、self_check 质量增量、tri_alpha、legacy unknown 55 包 |
