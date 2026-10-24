# V2.2.0 事实题四层真跑与质量门

## 4. 事实题四层真跑与质量门

- 主题：Python 中 len 函数的作用是什么？
- route：0 → 1 → both → all；四视图齐全
- rounds：0/1/both/all 各 2 圈
- llm_calls：83
- llm_tokens：671,144
- process_ready：true
- raw_answer_ready：true
- answer_ready：true
- answer_quality：verified
- coverage：0.67（answered 3 / answerable_total 3）
- behavior_fusion：v2_contract（capabilities_total=5）
- history_fusion：178 版本 / 17 轴 / readiness=1.0
- 产物：outputs/20261024_082341_Python中len函数的作用是什.packed.json

## 4.1 事实门修复

- 修复 evidence.detect_conflicts 的“裸数字 number”误判：1..30 页面计数不再被当成事实数值冲突。
- 事实卡恢复 answered；官方证据 E19/E20/E21/E22/E38/E57/E66；gaps 为空。
- 新增负对照回归：裸数字两段不同任务列表不得报冲突。
- 事实题仍要求官方证据；不造假 verified。

## 4.2 启动与弹窗修复

- 根因：scripts/*.ps1 是 UTF-8 无 BOM，PowerShell 5 按 GBK 解析中文直接 ParserError，导致 APP 启动不了。
- 已把所有 scripts/*.ps1 转为 UTF-8 with BOM；PS5 解析和 start_app 复用通过。
- BGE embedding 冷启动改为后台线程，不再阻塞 HTTP 启动（避免启动器健康检查超时杀 app）。
- start_app.ps1 默认健康超时 120s；已有实例不健康时自动停止并重启。
- engine_runner/App 引擎子进程加 CREATE_NO_WINDOW，避免每跑一题弹黑窗。

## 4.3 本地模型

- BGE 8771 /health 200，cuda，dim=512；/embed 返回 512 维向量。
- local_model env pip check 0 broken；torch 2.14.1+cu126；transformers 5.20.2。


## 4.4 App 全链路真跑

- App 任务：20261024_082813_b7348f，status=done，exit_code=0。
- App→engine→本地 BGE：任务由 App 队列启动，engine_runner 调 Meta-DGTF-V2.2.0.py；子进程无控制台窗口。
- llm_calls：87；llm_tokens：733,605；route 0,1,both,all；每层 2 圈。
- process_ready=true；raw_answer_ready=true；answer_ready=true；answer_quality=verified；coverage=0.5。
- 产物：outputs/20261024_083648_Python中len函数的作用是什.packed.json
- App 冷启动：stop→hidden start，6.8s 后 health 200；PID 13196；App 2.0.0 / Engine 2.2.0。

## 4.7 推理题四层真跑与质量门（2026-10-24 补丁迭代）

- 主题（随机领域）：**为什么城市热岛效应在夜间比白天更明显？**
- 出发点：守护巡检后随机真跑，首轮暴露 4 类缺陷（why 题误判 fact、研究层判定审计假失败、元层清算 stale、判定审计口径过严）。
- 迭代 4 轮（route 0,1,both,all；实际圈数按需 2~5 圈）：

| 轮 | calls | tokens | 质量门 | 卡点 |
|---|---|---|---|---|
| 1 | 92 | 1,014,870 | ❌ | why 题判成 fact ⇒ 事实卡未 answered ⇒ needs_evidence |
| 2 | 145 | 1,793,098 | ❌ | all.meta_closure 在 `_totalize_all_pool()` 之前计算 ⇒ 假缺口 |
| 3 | 118 | 1,359,159 | ❌ | 判定审计 mixed/bad=3（纯数字命中 + partial 被判 bad） |
| 4 | 138 | 1,581,220 | ✅ | — |

- 第 4 轮最终指标：question_type=reasoning；answer_ready=true、raw_answer_ready=true、process_ready=true、answer_quality=verified；
  process_ledger.standard_all=true（四层 standard_ok 全 true）；研究层判定审计 verified（6/6）；元层闭环 clean=true（unsettled=0/3）；
  core_duty 审计 audit_ok=true、gaps=[]、overreach=[]；V2 memory bridge contract ok。
- 产物：outputs/20261024_134620_为什么城市热岛效应在夜间比白天更明显.md / .packed.json
- 修复提交：`d12140d`（why→reasoning + 判定审计入参）、`27bbe5c`（元层清算汇总后刷新）、`c8d43d5`（审计只拦越权 + 纯数字过滤）。
