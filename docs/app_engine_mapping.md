# 元DGTF → app 完整映射与可靠性审计

生成时间：2026-10-20（goal round 1）
引擎：`元DGTF-V1.30.0.py`（__version__ = 1.30.0）
app：`dgtf_app/`，入口 `server.py --port 8765`

## 1. 四层引擎映射

| 引擎层 | 引擎入口 | app 接口 | app UI |
|---|---|---|---|
| 0 修行 | layers_zero | `/api/tasks`、`/api/tasks/<id>/layers`、`/api/tasks/<id>/log` | 对话运行页、分层日志、四层折叠 |
| 1 研究 | layers_one | 同上 | `#runlog-body` 的 rl-lane |
| both 对撞 | layers_both | 同上 + `/api/outputs` | 对撞段、候选/悬置读数 |
| all 元 | layers_all | 同上 + `/api/chats` | 元层、决策/停止读数 |
| 四层汇总 | `layers.py` | `/api/tasks/<id>/layers`、`/api/outputs/facets` | 读数条、产物库 |

## 2. EML / 自学习反馈映射

| EML 环节 | 引擎/模块 | app 映射 |
|---|---|---|
| self_feedback 收集 | dgtf_v2.self_feedback | `self_feedback` 写入 packed，进入 `/api/tasks/<id>/result` 与产物 JSON |
| EML 候选 | self_feedback.candidates | `agent_bridge.build_tasks` 转成 agent tasks |
| agent 任务队列 | agent_bridge / agent_worker | `/api/agent/tasks`、`/api/agent/results` |
| 修复提案 | agent_repair / dsh proposals | `/api/dsh/proposals`、Agent 面板“修复提案” |
| LLM 反馈 | llm_feedback | packed self_feedback；app 运行产物展示 |
| 在线适配 | online_adapt | 配置建议；app 参数面板可保存 |
| 统一记忆 | unified_memory | 产物/playbook；app 产物库与知识库 |
| V2 影子调度 | dgtf_v2.shadow | 配置 `scheduler.v2.shadow`；当前 app 未单列 UI（仅配置/产物） |

## 3. 调度映射

- 任务级 CLI：`/api/tasks {opts}` → `engine_runner.build_cmd` → 引擎 `--route/--parallel/--rounds/...`。
- 配置级：`/api/params` → user yaml → `--config` 临时副本。
- 优先级：显式 opts ＞ 用户配置 ＞ auto ＞ 出厂默认。
- 动态闭环：`/api/agent/auto/start` + job 轮询；`/api/dsh/proposals/autofix/start` 同理。
- 新增调度预览：`POST /api/schedule/preview`，返回 effective、precedence、CLI、auto/v2/budget 状态。

## 4. 依赖链

```text
engine 元DGTF-V1.30.0.py
  → dgtf_v2.layers_*/orchestrator
  → self_feedback / llm_feedback / online_adapt
  → packed 产物
  → dgtf_app.engine_runner / outputs_index / layers
  → server.py /api/*
  → static app.js UI
```

关键依赖检查见 `GET /api/health` 的 `checks/modules/warnings`。

## 5. 已执行可靠性证据

| 项 | 结果 |
|---|---|
| EML 单测（self_feedback / agent_bridge / llm_feedback / online_adapt / unified_memory） | 59 PASS / 0 FAIL |
| app selftest | 371 / 0 |
| fast_gate | 11 / 0 |
| smoke | 266 / 0 |
| verify | 319 / 0 |
| audit | 70 / 0 |
| 自动闭环后台 task | start → 轮询 done |
| 自动修复/闭环断线 | 改后台 job + 轮询，断线重试 8 次 |

## 6. app 映射接口与证据

### 新增健康 / 调度接口

| 接口 | 作用 |
|---|---|
| `GET /api/health` | 引擎版本、四层、EML 模块、Fact/Evidence、调度、凭据、DSH、常驻 daemon、输出目录依赖检查 |
| `GET /api/schedule/profiles` | 列出 `configs/*.yaml` profile；`方案F-帕累托最优.yaml` 标记 recommended |
| `POST /api/schedule/preview` | 输入 question/opts/profile，返回 effective、precedence、CLI、auto/v2/budget、层集合 |
| `GET /api/schedule/pareto` | 从真实 `outputs/*.packed.json` 聚合 route/rounds 的 token 与四层覆盖面，返回非支配前沿与推荐点 |
| `GET /api/agent/auto/jobs` | 列出持久化的 auto/autofix job；服务重启后 running 自动标记 interrupted |
| `GET /api/agent/eml` | EML 映射读数：playbook 25 条、V2 shadow 事件 544 条、agent tasks/results/knowledge/proposals 与提案状态分布 |
| `POST /api/agent/eml/replay` | EML 反馈回放：历史 packed → schedule outcome 先验；默认 dry-run，不写生产 playbook |
| `GET /api/schedule/v2` | V2 shadow 事件读数：按 kind/layer 聚合 + 最近 5 条 + 路径 |
| `POST /api/tasks {opts.auto_pareto:true}` | 自动选用方案F-帕累托最优 profile，并在响应返回 profile |

### 实测（goal round 1 集成探针）

```text
PROBE PASS 39 / FAIL 0
```

覆盖：

- health / 引擎层 / EML 模块 / 依赖链；
- 调度 preview 默认、opts 覆盖、profile 选择、非法 opts 400/降级；
- 12 个只读 API；
- 空任务 400、空 DSH chat 400、知识库去重幂等；
- 自动闭环 job start→poll done；
- mock 任务跑完、四层规范 id `0/1/both/all` 映射、产物正文；
- EML 5 个单测套件全部 PASS。

### 层名映射

`/api/tasks/<id>/layers` 现在同时返回：

- `layers`：中文层名（修行/研究/对撞/元），保持前端兼容；
- `layers_by_id` / `layer_ids` / `stats_by_id`：规范 id `0/1/both/all`，供外部 API 与健康检查使用。


## 8. 引擎可靠性增强（goal round 1）

| 增强 | 验证 |
|---|---|
| 候选回填留痕：原因 + 来源层/轮次/相 + 去重键 + 置信/评估 | `_probe_v130_backfill.py` 30 PASS / 0 FAIL |
| AMP 占比上限配置化：`spiral.amp_ratio_max` + `amp_ratio_max_by_entry` | 同步 `dgtf_config.yaml` / 方案F；smoke 配置同步检查通过 |
| input_sanity 官方证据回放：18 条官方证据、升级条目清除、短记号防误命中 | `dgtf_v2/tests_input_sanity.py` 22 PASS / 0 FAIL |
| AST 登记：5 个新符号逐条解释 | verify 6.6 已过 |

## 9. 本轮 goal 结论

- 已完成：引擎→app 映射基座、健康检查、调度 profile/preview、标准层 id、EML/接口集成探针、回填留痕可靠性增强。
- 未完成（goal 保持 active）：真正的离线训练/微调管线、V2 shadow 对比 UI、基于实测延迟/质量/成本的帕累托前沿自动选择、后台 job 持久化。

## 7. 残留缺口（不掩盖）

1. **增强训练**：当前没有可离线执行的模型训练/微调管线；本审计把 EML 反馈、自检、提案闭环作为“训练替代”验证，而不是权重训练。
2. **V2 影子调度**：配置开启且产物可读，app 已能 preview V2 状态，但没有独立对比面板。
3. **帕累托最优**：app 现在支持通过 `profile` 选择 `方案F-帕累托最优.yaml`，但默认仍走 `dgtf_config.yaml`；尚未用实测延迟/质量/成本自动计算帕累托前沿。
4. **后台 job**：进程内存态；app 服务重启会丢失进行中的 auto/autofix job。
5. **健康检查**：`/api/health` 已复测 `ok=true`，模块 12/12。
