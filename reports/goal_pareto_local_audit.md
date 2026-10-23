# 目标审计：全自动帕累托决策运行 × 本地模型更多权重参与

> 审计类型：**只读**（源码 / 配置 / 产物 / 只读 API）。本轮**未改任何代码**，未调用写策略接口（auto-apply / apply-* / rebuild / replay / eml-replay / llm-apply / model-apply 均未调用）。
> 写入物：仅本文件 `reports/goal_pareto_local_audit.md`。
> 审计快照：**2026-10-22 17:33–17:40（Asia/Shanghai）**。
> 证据快照哈希见 §7.2；若文件之后变化，以快照哈希为准。

## 0. 结论（TL;DR）

1. **全自动帕累托 = 部分闭环，不是全链路闭环。**
   - **自动的部分**：训练产物 → 候选策略（pareto / best / bandit）→ 自动打分选优 → 写 `dgtf_memory/schedule_policy.json` → 追加 `schedule_auto_apply.jsonl` 审计。触发点有两个：app 启动时策略为空则自动选择（`server.py:8758-8766`），以及打开「Agent 面板」时前端 `bootV2Auto()` 自动 POST（`static/app.js:5858-5864, 5799, 6110`）。
   - **断点**：写进 policy 的 `auto_template/route/rounds` **默认不进引擎**。真实任务默认只应用 `profile=方案F-帕累托最优.yaml`（`server.py:8596-8617`）；engine V1.30.0 **不读** `schedule_policy.json`（只读 config/opts）。要真正用上模板/本地模型，必须显式传 opts `auto_template` / `auto_llm`，UI 默认不发这两个字段。
   - **副作用**：24 小时内自动选择 **114 次**，113 次选 pareto/`0:r7`（选择只变过 2 次）——选择已收敛，但重复写盘/重复审计，说明触发是「打开面板/重启」驱动的，不是一次性收敛，也没有调度周期。
2. **本地模型 = 可用作「建议/预填」，不能当决策权威。**
   - Qwen2.5-0.5B + LoRA 留出 14 条：JSON 合法率 0.857→1.000，route 完全匹配 0.000→**0.429**，rounds MAE 2.625→**1.446**；1.5B 与 DeepSeek 蒸馏基座均不优于 0.5B（route 0.357 / 0.214）。
   - 本地岭回归（非 LLM）：quality MAE 0.11181（基线 0.18037）、R² 0.29343；token 模型 R² 为**负**（-1.26377），应用时已弃用 token 预测、改用经验均值（`server.py:6258` 附近 note）。
   - 当前引擎侧本地模型权重参与度 **≈0**：V2Shadow 用规则调度 + 数值先验（`engine:23913-23961` 的 joint/advisory/takeover 仲裁用的是 proposal_from_engine，不是本地 LLM）；本地 LLM 只在 app 侧写 policy / 任务 opts。
3. **指标现在还不能支撑「扩权」判断。**
   - 同一份 `v2_events.jsonl`，窗口不同推荐不同：末 200 行→`0:r3`；末 2000 行→`0:r7`；全量/5000→`0:r1`；去重后→`0:r2`。
   - 1152 条 schedule_outcome 只有 **680** 个唯一 (run_id, template)；`0:r7` 原始 n=8、去重 n=4，ci95 从 .0064 被压到 .0098（重复样本把置信区间做窄了）。
   - 指标口径：quality = 0.55×coverage + 0.45×tri_ratio（`dgtf_v2/bridge.py:71`），其中 tri_ratio 是**原始一致率**、不是质量（既有文档已声明）；tokens 是 **run 总量 / route 层数摊派**（`bridge.py:97`），不是层级真实成本；template 的 quality 是**整跑 quality**，token 也是摊派值——跨模板比成本不成立。
   - 最新 60 份 packed 的 coverage 均值 0.478、tri_ratio 均值 0.061；duty_short 旗标 59/59，即「有旗标」是常态，`schedule_pareto` 里 `flag_runs=24/24` 不是异常样本，而是口径信号。
4. **建议的扩权顺序：先修尺子，再给权重。**
   P0 指标/样本口径与快照冻结 → P1 置信度门控 + 默认预填 + 失败回退（默认关）→ P2 配对 A/B 与护栏 → P3 才允许 joint/advisory 里引入本地模型先验。**V2 takeover 继续 false。**

---

## 1. 审计范围与快照

| 项 | 值 |
|---|---|
| 引擎 | `元DGTF-V1.30.0.py`（1,536,985 B，2026-10-21 23:00:07） |
| app | `dgtf_app/server.py` 392,683 B，mtime **2026-10-22 17:35:30**，sha256 前缀 `C00656004AA5` |
| app 版本 | /api/health → app 1.4.1，commit `a6a7f0c01bd9` |
| git HEAD | `d5a264c`（工作区有多处未提交改动，审计只看运行态与文件快照） |
| 8765 | 审计期间外部重启一次：pid 16076/26564 → **25212（17:38:33）**；17:39 /api/health=200。本轮未重启 8765 |
| 策略库 | `dgtf_memory/schedule_policy.json` 2,109 B，mtime 17:38:53，sha256 前缀 `afd0e6a75f9f1f55` |
| 审计日志 | `dgtf_memory/schedule_auto_apply.jsonl` 114 条，mtime 17:38:53 |
| 事件库 | `dgtf_memory/v2_events.jsonl` 2,248 行 / 1,088,655 B，mtime 12:30:21 |
| 调度模型 | `models/scheduler_model_v1.json` 2,676 B，mtime 2026-10-21 12:55:28，sha256 前缀 `931838CBE210` |
| LLM 评估 | `llm_sft/eval_base_vs_lora.json` sha256 前缀 `B6477A055B66`（n=14） |
| 产物 | `outputs/` 下 `*.packed.json` 137 份（递归）；其中最近 40 个 output 路径有 **9 个当前用户不可读**（服务账户残留 ACL，见 §6） |

**只读调用清单**：`/api/health`、`/api/consistency`、`/api/schedule/policy`、`/api/schedule/pareto?prefer=balanced|cost|quality`、`/api/schedule/v2`、`/api/schedule/v2/pareto`、`/api/schedule/v2/ab`、`/api/schedule/v2/bandit`、`/api/schedule/v2/context-bandit`、`/api/schedule/model`、`/api/schedule/model/predict`、`/api/schedule/llm/status`、`/api/schedule/profiles`、`/api/tasks`、`/api/dashboard`。
一次 `POST /api/schedule/llm/predict`（只推理、不写策略）在 17:38 与 8765 重启同一分钟被连接重置，**未重试**，记为未验证（§6）。

---

## 2. 闭环现状（逐环节）

链路：**训练产物 → 候选策略 → 自动选优 → policy 文件 → 任务执行 → packed → v2_events → 下一轮候选**。

| # | 环节 | 实现（证据） | 自动触发 | 状态 |
|---|---|---|---|---|
| 1 | 数据采集 | `dgtf_v2/bridge.py:57-103`：每跑按四层各写一条 schedule_outcome；quality=`0.55cov+0.45tri`，tokens=`llm_tokens//len(route)` | 每次 packed 双写 | **部分**（重复写入 / 口径有偏，见 §3） |
| 2 | 训练（本地模型） | `train_llm_lora.py`（seed=42、do_sample=False）、`train_scheduler_model.py`（岭回归、按 run_id 切分）、`eval_llm_lora.py`；产物 `llm_sft/`、`models/scheduler_model_v1.json` | 手动命令 | **PASS（有产物）**；复现有条件（§3） |
| 3 | 候选生成 | `server.py:5359-5398` V2 模板 pareto；`6415-6499` auto-apply = pareto/best/bandit 三候选按 `qn-λ·cn` 选优 | — | PASS |
| 4 | 自动选优/写盘 | `6415-6499` 写 policy + 追加审计；启动兜底 `8758-8766`；UI 面板 `app.js:5840` 自动 POST | 启动（策略为空）+ 打开 Agent 面板 | **自动但重复**（114 次 / 24h，选择只变 2 次） |
| 5 | 策略应用到执行 | 真实任务默认 `auto_pareto=true` → 只套 `profile=方案F`（`server.py:8596-8617`）；template/LLM 需显式 opts，UI 默认不发 | 任务创建 | **GAP（闭环断点）**：policy 里的 route/rounds/template 不进引擎 |
| 6 | 引擎执行 | V1.30.0 **不读** schedule_policy.json；scheduler.v2 仲裁默认无 mode，`takeover=false`（engine `29571-29579`）；dgtf_config.yaml 有 `mode: joint`（`dgtf_config.yaml:24-38`），但 **方案F 缺 mode** → 用 F 跑时 joint 仲裁不启用 | — | **部分**（F 配置与当前 dgtf_config 漂移 22 键） |
| 7 | 反馈回 EML | engine `22847-22858` 读统一 V2 先验（`read_v2` 默认 true，只数值）；`/api/consistency` 的 eml/llm/scheduler 检查全 ok | 每跑 | **部分**（先验是数值均值，本地模型权重仍不参与） |
| 8 | 观测/审计 | `schedule_auto_apply.jsonl`（候选+选择+score）；packed.v2_shadow/v2_takeover；`/api/consistency` ok=true/warnings=[] | 自动 | 部分：审计无 request_id / run_id 关联消费端 |

### 2.1 「全自动」的精确定义（现状）

- 自动：**选优 + 写文件 + 审计**。启动时策略为空自动跑一次；打开 Agent 面板时前端自动触发。
- 不自动：**执行消费**。真实任务默认只拿 profile；不自动使用 auto_template/auto_llm。
- 不做：没有 cron / 定时重选；24h 内 114 次写盘来自重启与面板打开（每小时峰值 13 次），选择值稳定在 `0:r7`。
- 结论：**自动选型已经成立，自动执行尚未接线**——这是「全自动帕累托决策运行」当前最大的缺口。

---

## 3. 指标可复现性（本审计最重要的部分）

### 3.1 指标定义（代码口径）

| 指标 | 定义 | 出处 | 问题 |
|---|---|---|---|
| quality（template） | `0.55×quality.coverage + 0.45×quality.tri_ratio`；template 事件每跑每层一条 | `bridge.py:70-71, 94-99` | tri_ratio=原始一致率，不是质量；整跑 quality 记到单层 template 上 |
| tokens（template） | `packed.llm_tokens // len(route)`（每层同值摊派） | `bridge.py:97-98` | 不是层级真实成本；跨 route 组成比较失效 |
| low / ci95 | 对重复观测直接算 sd 与 1.96·sd/√n | `server.py:4811-4825` | 重复事件被当独立样本 → ci 偏窄 |
| n | 事件条数（非唯一 run 数） | 同上 | 重复写入放大 n |
| schedule pareto quality | 四层「有内容」层数 / 4 | `server.py:6693-6777` | 与答案覆盖不同；最新 60 跑 coverage 均值 .478 |

### 3.2 实测：同一份事件库，窗口/去重不同 → 推荐策略不同

（复算脚本：读 `v2_events.jsonl` 末尾 N 行，按 server 同款打分 balanced=qn-0.35·cn；结果与 API 的 `0:r7 n=8 quality .955 low .9486 tokens 158585.2 ci95 .0064` 对齐）

| 窗口（文件末 N 行） | 参与 outcome 数 | 模板数 | 推荐 |
|---|---:|---:|---|
| 200 行（`/api/schedule/v2` 默认 limit=200） | 104 | 21 | `0:r3`，n=8，q=.958，low=.9526，tokens=253,085.9 |
| 2000 行（auto-apply 的 limit=2000） | 1028 | 30 | `0:r7`，n=8，q=.955，low=.9486，tokens=158,585.2 |
| 5000 行 / 全量 2248 行 | 1152 | 30 | `0:r1`，n=121，q=.757，low=.699，tokens=90,977.7 |
| 全量 + 按 (run_id,template) 去重 | 680 | 30 | `0:r2`，n=12，q=.857，low=.7132，tokens=83,211.4 |

- **n=8 的 0:r7** 在去重后只剩 **n=4**；ci95 从 .0064 变 .0098（重复样本把区间做窄）。
- 全库 1152 条 outcome 中重复 (run_id,template) 对 384 个（最多 6 条同键）；per-run 事件数为 4/8/12 常见（多来源写入：bridge 每层一条 + replay/rebuild 等）。
- 因此「自动选优 113 次都选 0:r7」**不能理解为结论稳定**：它可能只是窗口固定（2000 行）时的局部极小不稳定点。换窗口即换推荐，属于**不可复现**。

### 3.3 其他口径问题

1. **两种 quality 人群混写**：与 packed 可对照的 292 条 outcome 中，285 条符合 `0.55cov+0.45tri`；**7 条 neither**（例如 `20261019_164402`：事件 q=.458，bridge 公式=.33，`_entry_quality`=.71）——历史 `/api/schedule/v2/rebuild` 用 `_entry_quality` 改写过部分 quality（`server.py:6557-6606`），但事件里**没有 provenance/version 标记**，两套口径混在一起。
2. **文档与模型文件不一致**：`docs/scheduler_model.md:17-19` 写 rows 377 / runs 120 / MAE 0.086 / 基线 0.149 / R² 0.307；当前模型文件是 **385 / 122 / 0.11181 / 0.18037 / 0.29343**（`/api/schedule/model` 与文件一致）。文档陈旧，不能作为复现基线。
3. **packed 不可读会静默丢样本**：训练脚本 `glob(outputs/*.packed.json)` + `try/except continue`，ACL 拒绝的文件（§6）会被跳过且无「跳过数」出口。
4. **模板统计只看末尾窗口**：`/api/schedule/v2` 默认 200 行，auto-apply 2000，bandit/model 5000，schedule pareto 用 packed 120 份——同一系统内四种窗口口径，没有一处声明「当前读数对应哪个快照/窗口」。

### 3.4 可复现命令（在有相同快照时）

    python train_scheduler_model.py --out dgtf_memory/scheduler_model_repro.json --lam 2.0 --holdout 0.2
    D:/元DGTF-多模并行架构/local_model/envs/dgtf_llm_env/Scripts/python.exe eval_llm_lora.py --model D:/元DGTF-多模并行架构/local_model/models/Qwen2.5-0.5B-Instruct --adapter llm_sft/adapter_qwen05b_v1 --max 14 --out llm_sft/eval_repro.json
    # 读数（只读）：
    # GET /api/schedule/policy  /api/schedule/v2/pareto  /api/schedule/model  /api/schedule/llm/status  /api/consistency
    # 复算窗口：见 §3.2 脚本逻辑（读 v2_events.jsonl 末尾 N 行，按模板聚合）

**当前判定：指标不可复现（同一文件不同窗口/去重给出不同推荐），且 lacks 快照哈希与窗口声明。** 在补齐 §5 P0 前，不应据此扩权。

---

## 4. 本地模型适用环节

### 4.1 现有模型与实测

| 模型 | 用途 | 证据 | 结论 |
|---|---|---|---|
| Qwen2.5-0.5B + LoRA | 问题 → route/rounds JSON | `llm_sft/eval_base_vs_lora.json`：JSON .857→1.0；route 0→.429；rounds MAE 2.625→1.446（n=14，7 题） | **可用作建议**；route 不到一半 |
| Qwen2.5-1.5B + LoRA | 同上 | route .357 / MAE 1.923（`eval_base_vs_lora_15b.json`） | 不优，保留实验 |
| DeepSeek-R1-Distill-1.5B + LoRA | rounds 偏好 | route .214 / MAE 1.286（`eval_base_vs_lora_deepseek.json`） | 只适合作 rounds 参考 |
| hybrid | Qwen route + DeepSeek rounds | `server.py:6156-6171`；`/api/schedule/llm/status` backends 全部 ok=true | 值得作为预填候选 |
| 本地岭回归（非 LLM） | template → quality/成本打分 | MAE 0.11181 / R² 0.29343；token R²<0 弃用 | **Pareto 候选的弱先验**，不能单独决策 |

### 4.2 建议参与/不参与的环节

| 环节 | 是否适用 | 建议权限 |
|---|---|---|
| 问题类型分桶（fact / decision / boundary） | ✅ 适用 | 只展示/预填 |
| route 子集建议 | ⚠ 有限 | 只建议；**禁止砍层**（v1.26.0 已固定全四层，`engine:27438-27449`；profile F 的 `allow_route_trim: true` 已被引擎忽略，见 `engine:27446-27448`） |
| 每层 rounds 建议 | ✅ 适用（MAE 1.446） | 预填，允许 ±1；fact 短题以 `auto.fact_flow.rounds_max` 为准 |
| 停止/预算阈值 | ❌ 不适用 | 无稳定训练信号；不参与 |
| 冲突/证据/答案判断 | ❌ 不适用 | 需 DeepSeek API 语义能力；本地模型只会「格式模仿」 |
| 数值先验（Pareto arm 先验） | ✅ 适用 | 以 `read_priors` 形式进 V2/EML；不进 schedule_policy 的 executed 字段 |
| 直接写 policy / 接管执行 | ❌ 当前禁止 | 必须经过 §5 门控与 A/B |

---

## 5. 安全扩权方案（置信度门控 / 默认预填 / 失败回退 / Pareto 评估）

### 5.1 置信度门控（G0–G4，全部通过才允许预填）

- **G0 数据量**：template 唯一 n≥10 且来自 ≥5 个 run；全局推荐样本 ≥20 个唯一 run。
- **G1 稳定性**：`low = quality - 1.96·sd/√n_unique ≥ baseline_low + 0.01`；ci95≤0.05。
- **G2 一致性**：本地模型 top1 == 规则/岭回归 top1（或 route 相同且 rounds 差≤1）；不一致 → 只展示两个建议，不自动预填。
- **G3 成本**：预测 tokens（用经验均值，不用已弃用的 token 模型）≤ 同题基线 ×1.10。
- **G4 安全**：route 必须是完整四层子集且不删层；rounds∈[1, hard_max]；任何越权直接丢弃并记 fallback。
- 门控结果落盘：`policy_source + model_version + gate 明细 + 数据快照 hash + window`，写入 policy/审计，便于事后归因。

### 5.2 默认预填（两级，默认关）

- **Stage A（先做，风险最低）**：只做 UI 预填/展示——把本地模型/auto-template 建议显示在参数或任务面板，用户确认才写 opts；后端记录来源。**不改变任何自动执行路径。**
- **Stage B（A 稳定后再开）**：服务端在真实任务创建时，仅当 G0–G4 全过 且 prefer=balanced 且 n_unique≥20 时，设置 opts.route/rounds（等价 auto_template）并把 `auto_pareto` 的 profile 作为回退；默认由 `DGTF_LOCAL_MODEL_PREFILL=0` 关闭，实验组显式打开。
- **本轮不建议**：直接让本地模型决定 all 层 actions/decision；fact 类问题仍走 `auto.fact_flow` 与规则停止。

### 5.3 失败回退（必须零阻塞）

- 本地模型不可用（adapter/model 路径不存在、`D:/元DGTF-多模并行架构/local_model/envs/dgtf_llm_env` 不存在、GPU/OOM、子进程 180s 超时）→ 立即回退到 **profile=方案F** 或规则 auto，不重试、不阻断任务（`server.py:6121-6153` 已有 ok/error 结构，可复用）。
- 非法输出（JSON 不合法 / route 越权 / rounds 越界）→ 丢弃建议，fallback，记录原因。
- Pareto 无候选/样本不足 → 保持旧 policy，不写空策略；自动选优写盘前做**幂等检查**（chosen+candidates hash 未变则只更新心跳，不追加审计，避免 24h 114 条噪声）。
- V2 仲裁异常 → engine 已 fallback_v1（`engine:23962-23967`）；takeover 保持 false。

### 5.4 Pareto 评估（先把尺子修好）

1. **冻结快照**：每次评估把 `v2_events.jsonl + outputs 清单` 的 sha256 写入报告；评估只读快照副本。
2. **去重**：按 (run_id, template) 去重，保留最后一次写入；唯一 run 数作为样本量。
3. **口径分层**：quality 用**真实答案质量**（或至少明确声明它是 coverage proxy）；token 改成层级真实累计差（修 `bridge.py:97` 的摊派）；禁止跨 route 组成比较 token。
4. **双门**：quality_low ≥ baseline_low（同题/同配置）且 cost ≤ baseline+10%；coverage/tri/flag 率作护栏（任一显著变差即红）。
5. **配对 A/B**：同题、随机分组、每臂 ≥10 次真实跑；用已有 `/api/schedule/v2/ab` 的 Welch 近似（当前示例 1:r2 vs both:r2：n=45/35，diff .008，p≈.475，**无显著差异**）。
6. **回滚演练**：关 `DGTF_LOCAL_MODEL_PREFILL` / 清空 policy → 回到 profile F + 规则 auto，逐字对比 route/rounds/产物。

---

## 6. 验收方式与优先级

| 优先级 | 内容 | 验收判据 | 预计 |
|---|---|---|---|
| **P0** | 修指标口径与样本（dedupe、窗口声明、token 真实成本、mixed quality、快照 hash） | 固定快照+去重+固定窗口后，重复计算**推荐唯一**；任一读数带 snapshot/window/n_unique；旧读数标「不可比较」 | 1–2 天 |
| **P1** | 置信度门控 + Stage A 预填 + 失败回退 + 幂等写盘 | 合成事件上 G0–G4 判定正确；adapter 缺失/超时→fallback（无任务失败）；重复打开面板不再追加审计；app selftest 371/0、fast_gate 12/0、依赖审计 58/0 不退化 | 3–5 天 |
| **P2** | 配对 A/B + 护栏 + Stage B 默认预填（默认关） | ≥10 对/臂真实跑；quality 不低于基线、cost ≤+10%、decision rubric 不退；p<0.05 且效应量达标；回滚演练通过 | 1–2 周 |
| **P3** | 才允许 joint/advisory 内引入本地先验（不接管、不砍层） | P2 通过 + 5 跑滚动 ok + 关 flag 回基线 | P2 后 |

**取舍理由**：当前推荐会随窗口/去重翻转（§3.2），先扩权等于把不可复现的选型写进执行路径——违反「先职责、后质量、最后机制」的既定顺序。P0 是前置；P1 只在「展示/预填」层接线；P3 才碰执行面。

---

## 7. 未验证 / 边界（不写成通过）

1. **`POST /api/schedule/llm/predict` 未验证**：17:38 调用时连接被重置，同一分钟 8765 外部重启（pid 26564→25212）；未重试；8765 现 200。该接口本轮**未验证**。
2. **无新真实 A/B**：本轮只读，未跑 LLM/引擎真实任务；所有模型指标来自已有 llm_sft / scheduler_model 文件与既有 events。
3. **ACL 不可读文件**：最近 40 个 output 路径中 9 个当前用户拒绝访问（如 `20261022_123029_…` 的全部产物、`repairs/`、`_run_ckpt/`），这些跑次无法纳入复算；写审计/重算时必须显式排除。
4. **并发写**：审计期间 17:38:53 policy 与审计日志被外部（UI bootV2Auto/并发操作）再写两次（114 条），非本审计调用；快照以 17:39 哈希为准。
5. **joint 仲裁未在真实任务上观察**：本快照 3 个 live 任务均为 mock；生产配置有 `mode: joint`，但方案F 缺该键，实际用 F 的路径不会启用 joint——需要在 P1/P2 用一份更新后的 profile 验证。
6. **审计触发归因缺 request_id**：`schedule_auto_apply.jsonl` 无调用来源/run_id，无法区分「启动」「UI 面板」「外部脚本」；只知频率与时间分布（每小时峰值 13 次、选择只变 2 次）。
7. **静态资源/前端本轮未逐项回归**：不属本审计范围（另有验收任务覆盖）；本文只涉及 schedule/llm/pareto/v2 与 /api/consistency。

### 7.2 证据文件哈希（快照）

- `dgtf_memory/schedule_policy.json`：sha256 前缀 `afd0e6a75f9f1f55`（mtime 17:38:53）
- `dgtf_memory/v2_events.jsonl`：sha256 前缀 `4BE1A90AB075`（mtime 12:30:21）
- `dgtf_memory/schedule_auto_apply.jsonl`：sha256 前缀 `0FE9C7D7D326`（mtime 17:38:53，114 条）
- `models/scheduler_model_v1.json`：sha256 前缀 `931838CBE210`
- `llm_sft/eval_base_vs_lora.json`：sha256 前缀 `B6477A055B66`
- `dgtf_app/server.py`：sha256 前缀 `C00656004AA5`（mtime 17:35:30）

### 7.3 现场读数速查（审计时点）

- /api/consistency：`ok=true, warnings=[]`；checks engine/eml_modules/eml_memory/v2_paired/schedule_policy/job_persistence/layer_mapping/llm_lora/context_trace/rag_policy/scheduler_model **全 true**。
- /api/schedule/policy：`auto_strategy=pareto, auto_template=0:r7, auto_score=0.8302`；候选：pareto `0:r7 .8302` / best `0:r6 .8` / bandit `0:r7 .715`；@llm_route=0,1`、@llm_rounds=0:3,1:3`、@model_template=0:r2`、@context_template=0:r2`（后两者为早期人工应用留下的字段，非当前 auto 结果）。
- /api/schedule/v2/pareto：30 点 / frontier 3，推荐 `0:r7 n=8 q=.955 low=.9486 tokens=158,585.2 ci95=.0064`。
- /api/schedule/v2/ab：默认 `1:r2 vs both:r2`，n=45/35，diff_quality=.008，p_approx=.475，winner=1:r2（无显著差异）。
- /api/schedule/pareto（schedule 级）：37 点 / frontier 5；balanced 与 quality 均推荐「全四层、24 跑、tokens=542,253.5、coverage=1.0、flag_runs=24/24」；cost 档推荐「1 跑、coverage=.5、tokens=64,385」——**cost 档只有 1 个样本**，不能用于决策。
- /api/schedule/model/predict（示例问题）：bucket=howto；选 `0:r2 pred=.9195 tokens=72,376.9`；注意它的 token 是模板经验均值，non-token 模型已被弃用。
- 自动选优审计：114 条（10-21 17:39 → 10-22 17:38）；策略分布 pareto 113 / bandit 1；模板分布 0:r7 113 / 0:r2 1；prefer balanced 111 / quality 2 / cost 1；选择序列只变 2 次；top1-top2 分差 0.001–0.0302（小分差需谨慎）。
- v2_events：2,248 行，其中 schedule_outcome 1,152 条 / 213 runs / 30 templates；唯一 (run,template) 680；重复对 384（max 6）；quality mean .6417（0–1），tokens mean 134,431（900–734,742，摊派值）。
- 最新 60 份 packed：coverage 均值 .478（min 0）、tri_ratio 均值 .061；flags：duty_short 59/59、probe_link_dangling(3) 49、all_closure_unavailable 8、core_audit_gaps 11。
- 方案F 与 dgtf_config 差异 22 键：F 有 `auto.allow_route_trim: true`（引擎 v1.26.0 已忽略，不砍层）；F **缺** `scheduler.v2.mode`（→ joint 仲裁不启用）、`scheduler.v2.core_gate`、`auto.fact_flow.rounds_max` 等新键（回落到引擎默认，fact_flow 默认 2 圈）。这是「全自动 + 本地权重」在执行面之前必须先对齐的配置漂移。
