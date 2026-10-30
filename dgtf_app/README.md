# Meta-DGTF-道生三阶模型 工作台（App 名称：Meta-DGTF）

给Meta-DGTF 引擎套的一层人用界面：**提问 → 后台跑 → 实时进度 → 读产物**，
外加一个可检索的**历史产物库**。

零额外依赖（Python 标准库 + 原生前端），**不改动引擎主文件**。

**当前 app 版本：V2.0.83**（DSH 本对话实时视图对齐 DSH GUI 当前会话；引擎生产入口 V2.2.3 / `dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.3.py`，引擎发布说明见 docs/releases/V2.2.3.md）。

### 新增能力

- **DSH 本对话实时镜像（V2.0.1 引入；V2.0.2/2.0.3 修复：会话列表点开运行中会话直接显示实时内容、每个会话按自身时段独立记录/渲染、读库瞬时失败自动重试并点名失败库）**：实时视图直接读 DSH GUI 当前会话（`full=1` 整段会话、首屏最近约 200 条、700ms 增量、顶部「载入更早」向上回看），用户/助手文本、思考、工具调用与结果、轮次状态同构渲染，头部标注「与 DSH GUI 同一会话 · <session 前 8 位>」。
- **V2 帕累托图清晰化（V2.0.4–2.0.8）**：轴/刻度/网格/图例/点标签、分箱中位数趋势曲线、真实数据脚注、自适应铺满；Y 固定 0–1、X 固定 75k–200k，超界点贴边标注。
- **健康读数缓存（V2.0.3）**：/api/health 2s TTL（冷 ~900ms，命中 ~17ms），高频轮询成本显著下降。
- **EML + DSH 全流程闭环**：知识刷新 → 引擎跑次 → 消费者/任务 → 自审提案；Agent 面板只保留“DSH 全流程闭环”一个按钮。
- **产物时间标注**：技术知识分别标检索/爬取时间；产物库、资料库、检索库、DSH 产物、修复提案、审计与 V2 事件均带对应时间。
- **本地 LLM LoRA 调度建议**：Qwen2.5-0.5B-Instruct，问题→route/rounds；接口 /api/schedule/llm/*，任务 opts.auto_llm。
  链路走常驻推理服务 127.0.0.1:8772（`dgtf_local_llm/service.py`，stage=route）；旧根目录 `llm_predict.py` 已归档，不再作为首选回退。
- **V2 自动选优**：Agent 面板只保留挡位选择；切换挡位自动评估帕累托/最佳模板/UCB 并写入最优策略。
- **神经 RAG v2**：本地 BGE 语义检索 + BM25 + 引用 + 分层索引 + 上下文追溯；
- **本地资料库**：导入文件解析/分块为 anchors 证据，参与 RAG；原文留档，不训练、不外发，可删除。
- **技术知识库**：Agent 面板“知识检索”统一入口，经 DSH 知识检索会话筛选官方/权威/最新/高置信/高相关条目；按钮与查询框共用同一会话流程。
- **DSH 多会话**：历史/当前会话、续聊、实时事件、按会话取消、读写工作区（安全边界）。
- **质量替代分**：/api/quality/<task> 覆盖×回答率×收尾完整度−flags。
- **三本地底座**：Qwen2.5-0.5B / 1.5B / DeepSeek-R1-Distill-Qwen-1.5B（LoRA）。
- **自洽审计**：/api/consistency + 审计历史 + 面板。
- **项目背景内置**：真实任务默认注入Meta-DGTF权威背景，融合本地资料库与 app 本地导入文件（RAG v2：BM25 重排/引用/隐私策略/追溯）；/api/project/context 可查看，无前端按钮。
- **针对性真跑**：60 calls / 341K tokens / 758.9s（见 docs/real_run_20261021.md）。

边界：本地 LLM 只做调度建议，不替代 DeepSeek API 的四层推理。

---

## 快速开始

```bash
# 1) 启动服务（默认 http://127.0.0.1:8765）
python dgtf_app/server.py

# 2) 浏览器打开
#    http://127.0.0.1:8765
```

**先试演练模式**：勾选「演练模式（mock）」再点「开始深究」——
几秒出结果、不花钱，用来确认界面与链路可用。

---

## 真实运行

- 需要项目根 `.env` 里有 `DGTF_API_KEY`（联网检索/抓取默认走 DeepSeek 官方，复用同一 Key）。
- 真实一次跑 **约 30–45 分钟、几十万 token、约 ¥4–9**（DeepSeek 计价）。
  启动前界面会弹确认；任务在服务端后台跑，**可以关掉页面**，回来再看。
- 引擎取项目根下**版本号最高**的 `Meta-DGTF-V*.py`；用环境变量
  `DGTF_APP_ENGINE` 可指定某个版本，`DGTF_APP_MAX_CONCURRENT` 调并发上限（默认 3）。

---

## 目录结构

```
dgtf_app/
  server.py          # HTTP 服务（仅监听 127.0.0.1）
  engine_runner.py   # 任务管理器：启动/监控引擎子进程、增量读日志、定位产物
  outputs_index.py   # 产物索引：扫描 outputs/*.md，解析头部元数据，检索
  mock_engine.py     # 演练引擎：模拟分层日志 + 产物，零花费
  selftest.py        # 端到端自检（跑完自动清理自己的 mock 产物）
  static/            # 前端（index.html / app.js / style.css）
  runs/              # 每个任务的运行日志 <id>.log
```

---

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET  | `/` | 应用首页 |
| GET  | `/api/config` | 引擎版本、凭据状态（不泄露值）、产物统计 |
| GET  | `/api/tasks` | 任务列表 |
| POST | `/api/tasks` | 新建任务 `{question, opts}` |
| GET  | `/api/tasks/<id>` | 单任务状态 |
| GET  | `/api/tasks/<id>/log?offset=N` | 日志增量（按字节偏移） |
| POST | `/api/tasks/<id>/cancel` | 取消任务 |
| GET  | `/api/tasks/<id>/result` | 产物正文 |
| GET  | `/api/outputs?q=&body=&days=&decidability=&orientation=` | 历史产物检索 |
| GET  | `/api/outputs/facets` | 筛选项集合 |
| GET  | `/api/outputs/<name>` | 单份产物正文 |

---

## 统一决策与证据闭环 · 展示标签（v1.26）

工作台把「决策怎么下的、事实与证据从哪来、经验记了什么」拆成四个**只读块**。
中文字段叫法统一放在 `dgtf_app/params.py` 的 `DISPLAY_BLOCK_CN` / `DISPLAY_FIELD_CN`，
`GET /api/params` 会附带一份 `display_blocks`（只有标签、没有值，也**不是配置项**）。

| 块 | 中文标签 | 数据来源 | 在哪看 |
|---|---|---|---|
| `decision_trace` | 统一决策回执 | 引擎 `packed["decision_trace"]`（只读 packed，不重跑） | 总产物 md 的「结论摘要」；packed JSON |
| `fact_flow` | 事实流 | `dgtf_engine/dgtf_v2/fact_flow.py` 确定性读数；开关 `auto.fact_flow.rounds_max` | 接入后随产物 / packed 落盘；缺读数写「未测」 |
| `evidence` | 证据链 | `dgtf_engine/dgtf_v2/evidence.py` 证据指纹 / 引用 | 同上 |
| `unified_eml` | 统一 EML 记忆 | V1 `playbook` + V2 `v2_events` 合并读数 | 产物 md「本次记忆（EML 经验回路）」；packed |

### 统一决策回执（decision_trace）怎么读

这一块已经随引擎产物落盘，总产物 md 的「## 结论摘要」就是同一组标签：

| 字段 | 标签 | 读法 |
|---|---|---|
| `question_type` | 问题类型 | `fact`（事实）/ `decision`（决策）/ `boundary`（边界） |
| `retrieval` | 检索结论 | 官方源直接答案 + 官方源条数 / URL；没有则「无官方直接答案」 |
| `reasoning` | 四层推理结论 | 研究层 `decidable_product.answer`（截前 400 字） |
| `consistency` | 检索/推理一致性 | ✅ 一致 / ❌ 冲突 / ⚠ 部分 / ➖ 不可比 |
| `layers` | 四层产物 | 每层：进入 / 圈数 / 停止 / 主要产出 |
| `answer_ready` | 答案就绪 | 四层齐 + coverage ≥ 0.9 + 无阻断旗标 |
| `stop_reason` | 停止判据 | 如 `question_answered_four_layers` 或 all 层停止原因 |

另附 `route`（实际路线）、`rounds`（每层圈数）、`artifacts.run_id`（产物定位）。

### 另外三块（接入口径）

- **fact_flow（事实流）**：触发分类（fact / decision / boundary）、官方源优先、事实状态
  （answered / no_record / conflict / unknown）、四层固定不砍层、圈数建议、预算去重。
  配置只有一个开关 `auto.fact_flow.rounds_max`（事实短题每层圈数上限，**四层仍全跑、
  只砍圈不砍层**，0 = 不钳制）；参数面板里的标签是「事实流 · 事实短题每层圈数上限」。
- **evidence（证据链）**：证据指纹（同一条证据只算一次）、可回查引用、官方源标记，
  以及「检索结论 vs 推理结论」的 match / partial / mismatch / not_comp。
- **unified_eml（统一 EML 记忆）**：V1 playbook 与 V2 events 按 source 去重后合并读；
  只读**数值先验**，`contains_content` 恒 `False`（答案正文不进记忆）。

> 这三块的**展示读数当前尚未进 packed**（fact_flow 已先接入圈数开关
> `auto.fact_flow.rounds_max`；evidence / unified_eml 尚未接入默认跑次）。
> 展示层对缺失读数统一写「未测」，不写 0（0 会被当成「测了且为零」）；
> 接入前后本目录的自检都应为 `371 / 0`。

> `decision_trace` / `evidence` / `unified_eml` 是只读读数，**不是**
> `dgtf_config.yaml` 的配置键：不会出现在「高级参数」面板，也不参与保存 / 恢复出厂。
> `fact_flow` 的展示块同样是只读读数；但它目前有一个真实配置开关
> `auto.fact_flow.rounds_max`（在「自适应调度」组里）。相关的既有开关（EML 路径、
> 证据引用授权）在面板里的说明已带「统一 EML」「证据链」前缀，便于按块找参数。

---

## 本地全链路（两段：8772 推理服务 + 8773 OpenAI 适配层）

本地链路是**两段**服务：127.0.0.1:8772（dgtf_local_llm/service.py，Qwen2.5-0.5B + LoRA）
与 127.0.0.1:8773（scripts/local_model/openai_shim.py，把引擎 /v1/chat/completions
映射到 8772 /generate 的 OpenAI 协议适配层）。**8773 死掉 = 整条链断路**
（引擎熔断、llm_calls=0），所以 App 现在把两段纳入同一守护：

- **守护**：失败 2 次后按指数退避（120/300/600/900/1800s）重启；loading（模型加载中）
  不重启（进程活着，重启只会多抢一份显存）；日志节流，写
  outputs/_lead_audit/local_chain_watchdog.log。
- **开关**：--local-chain-watchdog auto|on|off（默认 auto = 首次读数后按需守护，
  与旧 8772-only 的懒启动同节奏）；env DGTF_APP_LOCAL_CHAIN_WATCHDOG 同义。
  off = 关闭守护，**读数仍可用**（只探不重启）。
- **读数**：GET /api/health 新增 local_chain 字段（service_ok / shim_ok /
  service_status / service_queue_depth / service_gpu_mem_mb / shim_stage_channel /
  engine_path / engine_version / endpoint_kind；读不到给 null + reasons，
  不写 0 冒充读数）。侧栏 /api/status/sidebar 的 llm.chain 同源（旧键保留）。
- **本地全链路档预设**：configs/本地模型-全链路.yaml（生成源 = dgtf_app/local_chain.py
  的 LOCAL_PRESET_OVERRIDES，生成命令见文件头；勿手改）。选档走**既有**
  profile/_config 通道：POST /api/tasks {"question":"…","opts":{"profile":
  "本地模型-全链路.yaml","route":"1","rounds":"1"}}；/api/schedule/preview 可先看命令行。
- **判据**：python dgtf_app/test_local_chain.py（43 项 + 8 变异体，不需起 server，
  不碰真实 8772/8773）。
- 起停脚本：scripts/local_model/start_local_llm.ps1 -Shim / stop_local_llm.ps1 -Shim
  （默认行为不变，只有加 -Shim 才管 8773）。

★ 云档默认行为不变：不改 dgtf_config.yaml、不改云端点；守护只探活/重启进程、不碰配置。

---

## 自检

```bash
python dgtf_app/server.py &        # 先起服务
python dgtf_app/selftest.py        # 全量端到端断言（当前 455 项；mock 全链路）
```

---

## 说明

- **产物库只读** `outputs/`，不写、不改。
- **安全**：服务只绑 `127.0.0.1`；`.env` 里的密钥只注入子进程环境，
  不返回给前端、不落日志。
- **不碰引擎**：本目录是独立的应用层，引擎主文件的 CRLF / 补丁流程与它无关。
- **后台日志只看进度**：引擎自 **v1.23.20** 起就把「全量留痕」与「ing·view 全文」
  两类大块**默认关掉**（`output.dump_rounds` / `show_ing` / `show_manifest`），
  stdout 只留进度；应用层再叠一层折叠做**兜底**（对旧版引擎同样有效）。
- **运行中 vs 跑完**：运行中显示原始日志（看得见过程），跑完自动收成折叠版；
  日志面板右下角有「展开 / 收起日志」按钮切换高度。
- **运行归档**：每次任务结束（成功 / 失败 / 取消）会把**完整运行日志**写为
  `outputs/<产物名>.run.log`、**运行元信息**写为 `outputs/<产物名>.run.json`，
  任务卡上可直接点开查看。
- **自检残留**：`selftest.py` 会自动清理自己产生的 mock 产物；但在沙箱隔离环境
  运行时，清理可能不落真实盘，必要时手工删 `outputs/*自检*` 与 `outputs/*.run.log|json`。

## 联网检索后端

- **默认 web_search.backend = deepseek**（DeepSeek 官方）；可选 tavily / snapshot；
- 检索走官方 POST https://api.deepseek.com/v1/tools/search，请求 query/count/need_content，Bearer Key；
- 抓取走官方 POST https://api.deepseek.com/v1/tools/fetch（单页转 Markdown）；
- Key 优先 web_search.api_key_env（默认 DGTF_API_KEY），DeepSeek 后端缺省回退 api.key。
- 工作台「联网」状态显示 DeepSeek 官方；旧 TAVILY_API_KEY 仅在显式把 backend 切回 tavily 时需要。

### v1.28 展示块

- `process_ledger`：每层 rounds / 标准 / 事实 / 引用 / 依赖，soul 形状与数据；
- `fact_contract`：四层事实命中与修复；
- `decidability_audit`：研究层可判定/不可判定是否真有证据；
- `recall`：既往产物历史回声，带 run_id。

这些块只读 packed，不是配置项。
