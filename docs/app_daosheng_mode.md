# App 道生专属模式（mode）· 契约与实测

生成：2026-10-25（T3 App 集成，teammate: app-mode）
引擎：`dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.3.py`（能力探测自动跟随，不写死版本）
App：`dgtf_app/server.py` + `dgtf_app/daosheng_mode.py` + `configs/道生专属模式.yaml`

## 1. 模式定义

`POST /api/tasks` 新增顶层字段 `mode`（也接受 `opts.mode`），默认 `auto`：

| mode | 含义 | 调度 |
|---|---|---|
| `auto`（默认） | 项目相关题 → `daosheng`；其它 → 既有 `quality_policy` 全自动链路 | 自动分流，理由写进响应 |
| `daosheng` | 道生专属 **质量优先** 档：项目背景 + EML 记忆 + 四层 + parallel B | 预算守卫触发时自动降级 fast 档 |
| `daosheng_fast` | 道生专属 **便宜档**：低圈 + serial + thinking off（预算紧张/显式指定） | 不自动升级回质量档 |
| `standard` | 显式走既有 `quality_policy` 链路（不生成道生 plan） | 与改动前行为一致 |

非法 mode → HTTP 400，响应带 `allowed` 白名单。项目相关性判据与既有
`_project_context_relevant()` 同口径（`_PROJECT_CTX_MARKS`）。

## 2. 响应契约（可审计）

`POST /api/tasks` 201、`GET /api/tasks/<id>`、`GET /api/tasks`（列表为摘要）、
`POST /api/tasks/<id>/retry`（resume）都回显 `mode`：

```jsonc
"mode": {
  "id": "daosheng",              // daosheng | daosheng_fast | standard
  "requested": "daosheng",       // 请求原值（auto/daosheng/daosheng_fast/standard）
  "tier": "quality",             // quality | fast | standard（预算守卫可降级）
  "policy": "daosheng.v1",
  "engine_mode": "B",            // B | serial | fast（M4 预测 + 预算档结果）
  "quality_policy": "auto:verified",
  "reason": "显式 daosheng…；M4 预测首选 B；本地服务不可达→规则回退；已注入 EML 记忆 414 字",
  "context_injected": ["project_context:RAG", "memory:EML(414字)"],
  "budget_guard": {"balance_cny": 20.37, "est_tokens": 550691, "est_cost_cny": 1.1,
                   "decision": "ok", "reason": "余额 ¥20.37 ≥ ¥8：允许质量档", "fail_open": false},
  "engine": {"version": "2.2.3", "supports": {...}, "supports_config": {...}},
  "preset": "…/configs/道生专属模式.yaml",
  "plan": {…完整 plan，见 §3…}
}
```

`GET /api/tasks` 列表只回 mode **摘要**（`id/requested/tier/policy/engine_mode/
quality_policy/budget_decision/reason/has_plan`），完整 plan 走单任务接口
（避免每次轮询把每条任务的 plan 都吐一遍）。mode 同时落在：
`opts._mode_request`/`opts._mode_id`（重试/恢复可复原）、任务活痕迹
`outputs/<tid>.run.json` 与终态归档 `<stamp>.run.json` 的 `mode` 字段。

## 3. plan 字段（`dgtf_app/daosheng_mode.py:build_plan`）

| 字段 | 说明 |
|---|---|
| `policy` | 固定 `daosheng.v1` |
| `mode_id` / `requested` / `mode_source` | 实际档位 / 请求原值 / explicit·auto-rule |
| `tier` / `engine_mode` / `mode_reason` | quality·fast / B·serial·fast / M4+预算理由 |
| `route` / `rounds` / `parallel` / `web` / `thinking` / `effort` | 落 opts 的调度值（setdefault，显式 opts 优先）；质量档 `rounds=auto` 交引擎自适应 |
| `self_check_mode` / `dual_judge_mode` / `history_fusion` + `*_via` | V2.2.3 新机制键；`via=config`（预设 `output.*_mode`）或 `cli` 或 `engine-default`/null（引擎不支持=缺省） |
| `quality_policy` | project→`auto:verified` / fact→`auto:web-retry` / other→`auto:stable` |
| `project_related` / `project_context` / `context_injected` | 是否项目题 / 是否注入背景 / **真实注入清单**（防双份注入） |
| `memory` | EML 摘要：text/chars/injected/truncated/cache/lessons/playbook/sources |
| `local_llm` | available/source(http·subprocess·rules)/route/rounds/latency_ms/attempts |
| `m4` | enabled/ok/first_mode/first_reason/quality_prediction/quality_guard |
| `history` | n/mode_counts/tokens_med/calls_med/cut_rate/web_ratio/tri_rate/latest_run_id |
| `cache` | 精确命中预判 exact/exact_from + semantic_capable/semantic_min_similarity |
| `budget_guard` | balance_cny/balance_source/est_tokens/est_cost_cny/decision/fail_open/reason |
| `engine` | path/version/supports(CLI flag)/supports_config(config 键) |
| `applied_opts` | 实际落进 opts 的键（未落=被显式 opts 覆盖） |
| `warnings` / `elapsed_ms` / `reason` | 告警 / 计划耗时 / 一句话理由 |

## 4. 三体动态最优与回退链

- **App（本模块）**：mode 判定 → plan → setdefault 落 opts；显式 opts 永远优先。
- **本地模型**（local-smith 的 `127.0.0.1:8772`）：
  1. `GET /health`（0.6s 超时，成功/失败都缓存 30s）；
  2. `POST /generate {stage:"route", text, messages, max_new_tokens, temperature, timeout}`；
     响应容错解析：顶层 `route/rounds`、`parsed/result/json` 子对象、
     `text/output/content` 里的 JSON 字符串；
  3. **总预算 1.5s**，超时/不可达 → 子进程 `llm_predict.py`（当前仓库已移除该文件 ⇒ 快速失败）→
     **规则回退**（`quality_predictor.question_features` + 预设 route）。
  全程 fail-open：本地模型永远不会拖慢/失败任务创建；mock 任务直接跳过探测。
- **引擎**：能力探测（源码字符串 + mtime/size 缓存）决定新机制键走
  config（预设 `output.self_check_mode/dual_judge_mode: auto`）、CLI（flag 存在且值非 auto）
  或缺省；`build_cmd` 对不支持的 gated flag 直接跳过，避免旧引擎 argparse 崩任务。
- **缓存**：精确缓存（同题 done 任务）与语义缓存可用性进入 plan（只读预判，不触发 embedding）。
- **项目自进化记忆**：`MEMORY.md`（active 经验索引）+ `playbook.jsonl`（玩法）
  + `episodes.jsonl`（近 80 次跑次聚合：mode/tokens 中位/砍层率/web 率/圈数中位）；
  仅**项目相关题**注入，词面相关条目优先，无命中时只给「经验索引 + 玩法库计数 +
  近 N 次聚合」连续性摘要；上限 1600 字，mtime 缓存，**只读 dgtf_memory/，不写回**。

## 5. 预算守卫（Lead 决策 3）

```
balance_cny  = 显式传参 > DGTF_DAOSHENG_BALANCE_CNY > runner.current_balance()
               （mock 任务跳过网络，balance_source="mock-skip"，fail-open）
est_tokens   = min(episodes.tokens_med 或默认 1.3M, 最新 packed 的 budget.raw_max_tokens × 0.97)
est_cost_cny = est_tokens/1M × cny_per_million_tokens（默认 2.0 元/M，预设可调）
decision     = ok(余额 ≥8) / degrade(4≤余额<8, 自动降 fast 档) / warn(余额<4, 仍可建任务+明确告警)
```
余额查询失败/未知 ⇒ `fail_open=true, decision=ok`，reason 写明「不拒绝任务」。
mock 任务余额为 `null` 是**设计如此**（不查网络）；真实任务可读到真实 CNY
（本机实测 `balance_cny=20.37, balance_source="runner", decision="ok"`）。

## 6. 预设 `configs/道生专属模式.yaml`

- `app_daosheng:`：App 计划唯一数据源（route `0,1,both,all`；`rounds=auto`；
  `rounds_quality=0:3,1:3,both:4,all:4`（仅预算 ok 且 `quality_first=true` 用）；
  `rounds_fast=0:2,1:3,both:2,all:2`；parallel B；web/thinking/effort auto；
  新机制键 auto；质量策略映射；budget/memory/local_llm 参数）。
- 引擎可识别子集：`runtime.{web,thinking,effort}: auto`、`actions.parallel_mode: B`、
  `output.{self_check_mode,dual_judge_mode}: auto`（V2.2.3 读取；旧引擎忽略未知键）。
- `l0_v2_* / merge_expand / all_v2 / one_v2 / both_v2 / zero_v2` **刻意不写** =
  保持 `dgtf_config.yaml` 出厂默认（不打扰已验证跑批行为）。
- 实测（V2.2.3 `load_config`）：
  `output.self_check_mode=auto, output.dual_judge_mode=auto, actions.parallel_mode=B,
  runtime.web=auto, runtime.thinking=auto, actions.l0_v2_mode=archive（出厂默认）`。

## 7. 测试与实测证据（2026-10-25）

| 项 | 结果 |
|---|---|
| `python dgtf_app/selftest.py`（基线 371） | **PASS 443 / FAIL 0**（新增 ★T3 检查 72 条） |
| `python scripts/app_daosheng_check.py`（mock 契约） | **PASS 10 / FAIL 0** |
| mock 端到端 `POST /api/tasks mode=daosheng` | **201**；mode/plan/reason/context_injected/budget_guard 全含 |
| GET 单任务 / GET 列表 / retry(resume) | 三处均回显 mode（列表为摘要 `has_plan=true`；retry 后新任务带完整 plan） |
| 本地模型三级回退 | fake 8772 HTTP → `source=http`；不可达 → `http→subprocess→rules`（0.62s）；负缓存第二次 0.000s |
| 引擎能力门控 | V2.2.2：CLI flag 不透传；V2.2.3：探测自动翻转，preset config 键生效 |
| 真实 API | **0 次**（全程 mock；余额读数仅为本地已有缓存/一次免费余额查询） |

## 8. 风险与回退

1. **默认路径影响面**：仅项目相关题 auto→daosheng；非项目题完全走既有链路
   （selftest mock 题 "应用端到端自检 mock" 证明 mode=standard、quality_policy 不变）。
2. **新机制键**：旧引擎忽略 config 键 + CLI 能力门控双保险；V2.2.3 默认 `llm` 零行为差，
   只有显式使用道生预设时才变 `auto`。
3. **本地模型未就绪**：1.5s 内 fail-open 规则回退，不阻塞建任务；8772 契约若调整，
   只需改 `daosheng_mode.local_llm_route()` 的解析层。
4. **预算守卫误判**：估算 tokens 用历史中位，偏差会导致早降级/晚降级；阈值在预设
   `budget` 段可调，`DGTF_DAOSHENG_BALANCE_CNY` 可离线注入测试。
5. **回退开关**：`mode=standard` 完全不启用道生 plan；或删 `configs/道生专属模式.yaml`
   （内置兜底仍可用，只会丢自定义阈值）。回退不动任何引擎/配置出厂值。

## 附：实测场景矩阵接入（Round 4）

道生模式 plan 的 m4.scenario 现在由 mode_fusion.kind_of_question() +

ecommend_scenario() 生成（实测矩阵 3 场景 7 行，见
docs/ab_evidence_20261025.md §9）：

- 
easoning（推理/机制）→ uto（B 并行 + thinking auto + rounds auto）；
- choice（选择/决策）→ uto；
- act（事实/数值）→ web_on_auto，且 
equire_web=true、orbid 含
  web_off_auto/web_on_fast（事实题必须联网 + 保留 thinking，否则质量 0.44~0.47）。

该字段只进 plan 审计与展示，不改变既有 opts 决策路径（失败即忽略）；
App 的事实题联网仍由 quality_policy 的 auto:web-retry 执行。
