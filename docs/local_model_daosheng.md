# 道生专属本地模型（stage LoRA + 本地推理服务）

> 任务：T2 · 本地模型 —— 把本地 Qwen2.5 改造成 Meta-DGTF-道生三阶模型的
> **stage 级适配器**（`self_check` / `dual_judge`，route 复用旧适配器），
> 并提供 **8772 本地推理服务** 供 engine / app 调用。
> 全部离线：只用 `outputs/*.packed.json` 历史产物，不联网、不调用真实 API。
> 底座：**Qwen2.5-0.5B-Instruct**（1.5B 在本机 6GB/持续训练降频条件下不可行，
> 原因与实测见 §4.2；1.5B 路径保留）。

## 0. TL;DR

| 项 | 状态 |
|---|---|
| 数据集 | `llm_sft/dgtf_stage/`：dual_judge 2,966 条（2490/476）、self_check full+min 各 568 条（478/90）；按问题分组留出 29 题（~16% 样本） |
| 训练 | `scripts/local_model/train_dgtf_stage_lora.py`：**Qwen2.5-0.5B-Instruct**（1.5B 在本机持续训练降频，见 §4.1）、fp16 LoRA r=16/α=32、7 个 target module、gradient checkpointing、batch1+accum8、max_len 2048、**fp16 权重 + fp32 GEMM** |
| 适配器 | `llm_sft/adapter_dgtf_selfcheck_05b_v2`（第二轮：min 变体、干净数据）、`llm_sft/adapter_dgtf_judge_05b_v2`（第二轮）；第一轮负结果留档 `llm_sft/adapter_dgtf_*_05b_v1_truncated_bak/`，服务按「v2 优先、v1 兜底」解析 |
| 服务 | `dgtf_local_llm/service.py` → `127.0.0.1:8772`，`GET /health`（p50 16ms）、`POST /generate`（self_check p50 3.9s）、单卡串行队列、LRU 缓存、warmup、结构化 503 |
| 客户端 | `dgtf_local_llm/client.py`（零依赖，失败返回 `{"ok":false,...}`，便于云回退级联） |
| 启动 | `scripts/local_model/start_local_llm.ps1`（后台 + 等 ready）；停止 `stop_local_llm.ps1`；重训编排 `retrain_after_window.ps1` |
| 评测 | 两轮。第一轮 **go/no-go 不通过**（训练数据中段截断，根因见 §5.2）；第二轮修正后：**格式层有信号**（self_check JSON 0.286→0.857，base 0.0），**决策层未达标**（三项全对仍 0、QC 门控不可用）→ 结论见 §5.1 / §9 |

## 1. 目录与文件

```
scripts/local_model/
  build_dgtf_stage_dataset.py   # 从 packed 产物重建 stage 数据集（含统计/防泄漏）
  make_filtered_stats.py        # 过滤后训练集统计（drop-truncated 口径，零 GPU）
  train_dgtf_stage_lora.py      # stage LoRA 训练（fp16 权重 + fp32 GEMM；--dry-run/--drop-truncated）
  eval_dgtf_stage.py            # 离线评测（JSON 合法率/position/self_check 决策字段/QC 门控）
  probe_local_llm.py            # 8772 服务实测探针（health/generate/错误回退/并发）
  start_local_llm.ps1           # 启动服务（后台，等 ready，打印 PID/端口）
  stop_local_llm.ps1            # 按端口停止服务
  retrain_after_window.ps1      # 第二轮重训编排：停服务→训练(sc min/dj)→重启→重评
dgtf_local_llm/
  service.py                    # 本地推理服务（HTTP，127.0.0.1:8772）
  client.py                     # engine/app 侧客户端（stdlib）
llm_sft/dgtf_stage/
  dual_judge_{train,val}.jsonl
  self_check_{train,val}.jsonl          # 11 字段完整自省 JSON
  self_check_min_{train,val}.jsonl      # 3 个决策字段（省 decode）
  dataset_stats.json                    # 样本数/去重/长度分布/按题分组/防泄漏
  dataset_stats_filtered.json           # 过滤后（drop-truncated/计划样本数）统计
  eval_dgtf_stage*.json / service_probe.json
llm_sft/
  adapter_dgtf_selfcheck_05b_v2/        # 第二轮：self_check min 变体
  adapter_dgtf_judge_05b_v2/            # 第二轮：dual_judge
  adapter_dgtf_*_05b_v1_truncated_bak/  # 第一轮负结果留档（截断数据训练）
  _round1_evidence/                     # 第一轮 metrics/loss/eval/probe/日志归档
  train_metrics_dgtf_{selfcheck,judge}.json   # loss 曲线 + 训练指标
  loss_curve_dgtf_{selfcheck,judge}.svg
```

## 2. 硬件与运行环境（实测事实）

| 项 | 值 |
|---|---|
| GPU | NVIDIA GeForce GTX 1660 Ti **6GB**（SM 7.5，24 SM，**无 tensor core**） |
| CPU / RAM | i7-10750H 12 线程 / 32GB |
| Python | `local_model/envs/dgtf_llm_env/Scripts/python.exe`（3.13.15） |
| torch | 2.14.1+cu126，CUDA 12.6，`torch.cuda.is_available()=True` |
| transformers / peft | 5.20.2 / 0.21.2（无 bitsandbytes ⇒ **fp16 LoRA，不做 4bit**） |
| 本地权重 | `local_model/models/Qwen2.5-1.5B-Instruct`（离线 `local_files_only`） |

> 服务启动后显存占用约 **3.4-3.6GB**（< 5GB 余量目标 ✅）；训练时峰值 ~5.2-5.8GB，
> 训练与服务**互斥**（6GB 卡放不下两者同时），切换方式见 §7。

## 3. 数据集构建

```powershell
# 全量（复现）
$env:PYTHONUTF8="1"; $env:HF_HUB_OFFLINE="1"
local_model\envs\dgtf_llm_env\Scripts\python.exe scripts\local_model\build_dgtf_stage_dataset.py `
  --outdir llm_sft/dgtf_stage --shard 6 --sc-cand-max 8 --sc-collision-cap 400 `
  --sc-manifest-cap 300 --sc-amp-max 5 --tokenizer-stats
```

### 3.1 prompt 与引擎同构（不自创格式）

模板不是手抄的，而是 **AST 只读提取** 自
`dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.2.py`：

- `PHASE_PRACTICE/RESEARCH/DUEL/META` 的 `dual_spec`、`view_focus`（按 `entry`
  0/1/both/all 映射：修行/研究/对撞/元）
- `NO_FILL_JUDGE_RULE`、`AMP_TYPES`、`UNSAID_ESCAPE_LIMIT`
- 拼装顺序对齐 `_dual_judge`（12234-12300）与 `_self_check`（15162-15310）：
  - dual_judge：`system = 你是【对偶判断者】+ dual_spec + how(anchored) + both 约束
    + NO_FILL_JUDGE_RULE + schema`；`user = 【处境】+ _judge_context(inp,anchor)
    + _decidability_block + 【候选列表】`
  - self_check：引擎原文 system（含 `view_focus`）+ `user = 【锚点】【候选】【& 印记】
    【ing 输出】【view】【代码已发现的质量线索】`（+ 深究请求 / ★代码统计块）；
    `_count_unsaid` 复刻引擎实现
- **两处有意偏差**（代码注释已标）：
  1. dual_judge 的 schema 精简为 `{idx,position,why_position}`（任务契约三字段），
     `why_0/why_1` 在引擎解析侧缺失时按空串处理，不影响 `_extract_judgments`；
  2. 省略 `_self_block`（线上无 self_memory 时引擎本来返回空）与
     `_carry_block_text`（carry 是运行期输入，历史产物里没有原值）。
- `is_amp_candidate` 是 `position` 的派生量（标签泄漏），**未作为输入特征**。

### 3.2 两类样本

| stage | 输入 | 目标 |
|---|---|---|
| dual_judge | 锚点（+透传问题/上游 view shape）+ 全局可判定性 + 候选列表 | `{"judgments":[{"idx","position","why_position"}]}`，由 `candidates[].position/why_position` 还原 |
| self_check (full) | 锚点+候选(属性×位置)+& 印记+ing 输出+manifest+质量线索(+未生计数) | `views.*.self_check` 原 JSON（11 键） |
| self_check_min | 同上（同一模板，schema 换成 3 决策字段） | `{"suspicious_candidates","ing_rephrased","unsaid_is_escape"}` |

**dual_judge 分片**：一个 view 的候选 p50=27 / max=60，整包放不进 2048 token；
引擎自身命中率低时也会「候选减半再判」（`_dual_judge` 降级重试），说明该任务
逐候选独立 ⇒ 按顺序切成 `shard=6` 的小批，`idx` 每个样本内从 1 重编号。

**标签清洗**：`why_position` 为空的候选 = 未判/默认 0 噪声，共丢弃 796 条
（4.6%）；候选 desc 去重；全量精确去重（dj 去 20、sc 去 4）。

### 3.3 统计（`llm_sft/dgtf_stage/dataset_stats.json`）

| 指标 | dual_judge | self_check full | self_check min |
|---|---|---|---|
| 样本（train/val） | 2,966（2,490/476） | 568（478/90） | 568（478/90） |
| 来源 view / 候选 | 577 view / 16,623 judged 候选 | 568 view | 568 view |
| 按 phase | 见 `dataset_stats.json` | 见 `dataset_stats.json` | 同 full |
| prompt token p50 / p95 | 1,140 / 1,593 | 1,709 / 1,921 | 1,638 / 1,856 |
| target token p50 | 150 | 212 | **27** |
| total token max | 1,821 | 2,324 | 1,966 |
| over max_len(2048) | 0 | 79（第一轮；第二轮丢弃策略） | 0 |

> 数据快照说明：构建时 `outputs/` 有 179 份 packed（并行 run 会持续新增，
> 数字随快照变化）；上述为第二轮重训所用快照。

**防泄漏**：按「问题」分组（问题字符串全等），53 个唯一问题 → val 29 题 /
train 24 题，val 样本占比 **15.9%**；两个 stage 共用同一 holdout 问题。
同一问题的所有 run / view / 分片只在同一侧。

标签分布（val）：dual_judge `0=54.0% / 1=43.1% / both=2.9%`（多数类基线 54%）；
self_check `suspicious_candidates 非空 86.8%`、`ing_rephrased=True 7.7%`、
`unsaid_is_escape=True 17.6%` —— 都是强多数类基线，因此评测同时报 **F1** 与
**QC 门控 coverage/agreement 曲线**，不只报「一致率」。

## 4. 训练

```powershell
# ── 第一轮（负结果，保留作证据链）──
# self_check full+min 混训 60 条（max_len 1536 → 58 条被截断，详见 §5.2）
local_model\envs\dgtf_llm_env\Scripts\python.exe scripts/local_model/train_dgtf_stage_lora.py `
  --model local_model/models/Qwen2.5-0.5B-Instruct --stage self_check --variant mixed `
  --max-train 60 --max-len 1536 --epochs 1 --val-subset 10 --save-every 20 `
  --lr 1.5e-4 --out llm_sft/adapter_dgtf_selfcheck_05b_v1

# ── 第二轮（Lead 修正方案：干净数据，超长样本直接丢弃）──
# P0 self_check：只用 min 变体（3 字段 target，26 token）
local_model\envs\dgtf_llm_env\Scripts\python.exe scripts/local_model/train_dgtf_stage_lora.py `
  --model local_model/models/Qwen2.5-0.5B-Instruct --stage self_check --variant min `
  --max-train 180 --max-len 2048 --epochs 1 --val-subset 20 --save-every 60 `
  --lr 1e-4 --drop-truncated --out llm_sft/adapter_dgtf_selfcheck_05b_v1
# P1 dual_judge
local_model\envs\dgtf_llm_env\Scripts\python.exe scripts/local_model/train_dgtf_stage_lora.py `
  --model local_model/models/Qwen2.5-0.5B-Instruct --stage dual_judge `
  --max-train 130 --max-len 2048 --epochs 1 --val-subset 20 --save-every 60 `
  --lr 1e-4 --drop-truncated --out llm_sft/adapter_dgtf_judge_05b_v1
```

配置：LoRA `r=16, alpha=32, dropout=0.05, bias=none`，target modules
`q/k/v/o/gate/up/down_proj`（0.5B 可训练参数 8.80M），`gradient_checkpointing=True`，
`batch=1, accum=8`，AdamW `lr=1e-4`（10 步 warmup + cosine 到 10%），
`max_len=2048`，fp16 + GradScaler，**超长样本丢弃（不中段截断）**。

第一轮训练实测（60 条样本，max_len 1536）：

| stage | train_loss | best_val_loss | 步数 | 耗时 | 峰值显存 | 截断样本 |
|---|---|---|---|---|---|---|
| self_check（mixed） | 2.035 | 1.679 | 60 | 296s | 4.2GB | **58/60** |
| dual_judge | 1.740 | 1.772 | 60 | 282s | 4.2GB | 19/60 |

吞吐约 290-310 tok/s（0.5B + fp32 GEMM 补丁）；loss 曲线见
`llm_sft/loss_curve_dgtf_*.svg` 与 `train_metrics_dgtf_*.json`。

### 4.1 关键适配：fp16 权重 + fp32 GEMM

在 GTX 1660 Ti（SM75，无 tensor core）上实测：

| GEMM | 实测吞吐 |
|---|---|
| `torch.matmul` fp16（1024×1536×1536） | **0.54 TFLOPS** |
| `torch.matmul` fp32（同形状） | **2.47 TFLOPS** |

cuBLAS 12.6 的 HGEMM 在该架构上严重劣化 ⇒ 直接 fp16 训练只有 **55 tok/s**。
训练脚本因此把每个 `nn.Linear` 的 GEMM 换成 fp32 计算、输出转回 fp16
（`enable_fp32_compute`，权重/激活仍是 fp16，显存基本不变）：
**fwd+bwd 提到 110-160 tok/s（2-3x）**，seq1024 8.95s/step、峰值 5.22GB。

**超长截断策略**（第一轮教训 → 第二轮改为丢弃）：
- 第一轮 `max_len=1536` 时 self_check 样本 58/60 超长，`build_token` 会「保留
  prompt 头（system 模板）+ 尾（候选列表末尾/统计块）、丢中间」——结果把候选
  列表中段切掉，模型学到「按残留索引尾部乱喷」的伪规律（详见 §5.2）。
- 第二轮按 Lead 修正：`--drop-truncated`，**超长样本直接丢弃，不切候选**。
  预检（`--dry-run`，08:22）：self_check min 180 条 `dropped=0`、total max
  1,966 < 2,048 ✅；dual_judge 130 条 `dropped=0`、total max 1,821 < 2,048 ✅。

### 4.2 为什么切到 0.5B 底座（如实记录）

任务原始要求 1.5B 底座。实测：
- 1.5B + fp16 LoRA 在 **持续负载**下 GPU 从 1,845MHz 降到 1,530MHz（功耗墙 59W、
  76-81°C），step 时间从 14s 劣化到 **32s/step**（seq 1792）；
- 6GB 卡上 1.5B 训练峰值 5.8GB，几乎没有余量，90 条 × 1 epoch 要 48 分钟，
  08:20 联调时间盒内不可行；
- 按 Lead 授权切 **Qwen2.5-0.5B-Instruct**（本地 env 已验证）：同样 fp32-GEMM
  补丁下 **4.2s/step（seq 1536）/ ~5s（seq 2048）**，可训练样本量提升 3 倍，
  推理 decode 也从 1.5B 的 ~6.5 tok/s 提升到 ~9-10 tok/s。
- 1.5B 路径未删除：`train_dgtf_stage_lora.py --model .../Qwen2.5-1.5B-Instruct`
  即可，但需要数小时独占 GPU（全量 479/2,508 条），非本轮时间盒内可行。

### 4.2 产物

- `llm_sft/adapter_dgtf_selfcheck_15b_v1/`（adapter_config + safetensors + tokenizer）
- `llm_sft/adapter_dgtf_judge_15b_v1/`
- `llm_sft/train_metrics_dgtf_{selfcheck,judge}.json`：loss 曲线（每步）、epoch 汇总、
  best_val_loss、峰值显存、吞吐、截断数、生成冒烟 JSON 合法率
- `llm_sft/loss_curve_dgtf_{selfcheck,judge}.svg`（零依赖 SVG）

## 5. 离线评测

```powershell
local_model\envs\dgtf_llm_env\Scripts\python.exe scripts/local_model/eval_dgtf_stage.py `
  --limit-dj 10 --limit-sc 6 --limit-scmin 16 --base
```
指标定义：

- **JSON 合法率**：生成文本能被 `try_parse_json` 解析出 JSON 对象的比例
- **position 准确率**：按 gold `idx` 对齐，`position ∈ {0,1,both}` 三分类准确率；
  另报 `coverage`（模型真正判了几条）、三分类 **macro-F1**
- **self_check 决策字段一致率**：`suspicious_candidates` 集合完全一致、
  `ing_rephrased`/`unsaid_is_escape` 布尔一致；三项全对 = `all3`；
  另报 `suspicious` 集合 F1 与 `unsaid_count` MAE（full）
- **QC 门控曲线**：置信度 = 生成 token 平均概率（`confidence`），
  τ∈{0.8,0.9,0.95} 报 `coverage`（conf≥τ 的样本占比）与 `agreement`
  （covered 样本上的样本级一致率），用于「本地草稿 + 云校准」级联/conformal 弃权

> 评测生成用与服务相同的 **prefill(fp32 GEMM)+decode(fp16)** 混合路径，
> 因此评测延迟 ≈ 服务单次延迟。

**结果**：见 §5.1（实测数字由 `eval_dgtf_stage.py` 写入
`llm_sft/dgtf_stage/eval_dgtf_stage.json`；下表为本轮实测摘要）。

### 5.1 实测结果（第二轮 v2：干净数据，v2 适配器）

训练侧（val loss，20 条 holdout，1 epoch）：self_check **1.679 → 0.224**、
dual_judge **1.772 → 1.484**（截断修复后同样步数 loss 明显更低）。

| 指标 | dual_judge | self_check_min | self_check (11 字段) | base 0.5B 对照(sc_min) |
|---|---|---|---|---|
| n（val 抽样） | 8 | 14 | 5 | 14 |
| JSON 合法率 | 0.625 | **0.857**（v1 0.286） | **1.0**（v1 0.333） | **0.0** |
| position 准确率 | 0.25（多数类基线 0.54） | — | — | — |
| position coverage | 0.55 | — | — | — |
| 三分类 macro-F1 | 0.115（0=0.344/1=0/both=0） | — | — | — |
| 三项字段全对率 | — | **0.0**（目标 >0.2 未达） | 0.0 | 0.0 |
| suspicious 集合 F1 | — | **0.132**（v1 0.02） | 0.044 | 0.0 |
| ing_rephrased acc | — | 0.786（恒 false 基线 0.923） | 1.0 | 0.0 |
| unsaid_is_escape acc | — | 0.643（恒 false 基线 0.824） | 0.6 | 0.0 |
| 字段级平均 acc | — | **0.476**（v1 0.19） | 0.533 | 0.0 |
| 单次延迟 p50 | 19.1s | 4.8-6.1s | 16.2s | 5.4s |
| QC τ=0.8 coverage/agreement | 0.625 / 0.133 | 0.857 / 0.0 | 1.0 / 0.0 | 0.643 / 0.0 |
| QC τ=0.9 | 0.25 / 0.084 | 0 / — | 0.2 / 0.0 | 0.143 / 0.0 |
| QC τ=0.95 | 0 / — | 0 / — | 0 / — | 0 / — |

**结论（本轮收口）**

1. **格式/结构层：v2 有明确信号 ✅**。丢弃截断样本后，self_check_min JSON 合法率
   0.286 → **0.857**、11 字段 full 到 **1.0**，而 base 0.5B 为 **0.0**；说明
   「训练数据被截断」的根因判断正确、适配器确实学到了 stage 输出格式。
2. **决策语义层：未达标 ⛔**。三项全对仍为 0（目标 >0.2）；失败模式是
   `suspicious_candidates` 退化成常量先验（几乎总输出 `[1,2]`），并没有逐候选判；
   `ing_rephrased`/`unsaid_is_escape` 的 acc 低于「恒填 false」多数类基线
   （0.923 / 0.824）；dual_judge position acc 0.25 < 多数类基线 0.54。
3. **QC 门控：不可用 ⛔**。τ∈{0.8,0.9,0.95} 下 agreement 不随 τ 上升（≈0），
   `confidence`（生成 token 平均概率）与正确性不相关，不能做 conformal 弃权阈值。
4. **最终判定**：本地模型（0.5B + 180/110 条 × 1 epoch）**仅可用于叙述/联调/
   格式草稿，不可接管决策字段**；工程链路（8772 服务、4 stage 契约、串行队列、
   超时/失败结构化 503、JSON 抢救、p50 ~4s、显存 1.04GB）已可交付。
   要接管决策需要 1.5B + 数小时全量训练（数据与训练/评测管线已就绪，见 §4.2）。

### 5.2 负结果与根因（截断训练数据）—— 项目证据链

| 项 | 内容 |
|---|---|
| 现象 | self_check_min 输出 `suspicious_candidates` 出现 `[10,11,…,39]` 一路喷到 token 上限；JSON 非法率 ~71%；决策三项全错。dual_judge 格式基本学会（0.875 合法）但 position 0.45 ≈ 基线。 |
| 根因 | 第一轮 self_check 训练 60 条样本在 `max_len=1536` 下 **58 条被截断**：`build_token` 的截断策略是「保 prompt 头（system 模板）+ 保尾（候选列表末尾/统计块）、丢中间」，导致**候选列表中段被切掉**。模型能看到的是候选索引的“尾部”，于是学到「按看到的索引区间喷 suspicious_candidates」。评测 prompt 完整（1,700 tok），与训练分布不一致 ⇒ 全错。 |
| 证据 | ①训练日志 `truncated=58/60`（selfcheck）/ `19/60`（judge）；②生成冒烟样例 `[10..39]` 与训练里被切后残留的尾部索引一致；③`self_check` 的 prompt p50=1,709 + target 212 > 1536；min 变体总长 p95=1,892 > 1536 同样被切。 |
| 结论 | 在 6GB 卡上，**不能靠“中段截断”省 token** 去喂结构敏感任务；要么把 prompt 压到 max_len 内，要么直接丢弃超长样本。这也解释了为什么「60 样本 + 截断」是负结果——不是模板/字段错（demo 字段还原 100% 通过），是训练数据被破坏。 |
| 修正（第二轮，已执行 ✅） | `--drop-truncated`（超长样本直接丢弃，不切候选）+ `max_len=2048` + self_check 只用 **min 变体**（target 26 tok）+ `lr=1e-4`、180 条 × 1 epoch；dual_judge 把 `why_position` 截到 30 字缩短 target 后 130 条 × 1 epoch。评测目标：JSON 合法率 > 0.9、三项全对 > 0.2 即算「有信号」；结果见 §5.1（格式达标、决策未达标）。 |
| 本轮价值 | go/no-go 结论明确：**本地 0.5B + 60 样本 + 截断数据不可用于决策**；但服务链路（/health 秒回、/generate 3.9s、串行队列、503 回退、JSON 抢救）已可联调，engine/app 集成不被质量结论阻塞。 |

## 6. 本地推理服务（127.0.0.1:8772）

### 6.1 启动 / 停止

```powershell
# 启动（后台，等 ready，打印 PID/端口；日志 llm_sft/local_llm/service.{out,err}.log）
powershell -ExecutionPolicy Bypass -File scripts/local_model/start_local_llm.ps1
# 前台调试
powershell -ExecutionPolicy Bypass -File scripts/local_model/start_local_llm.ps1 -Foreground
# 停止
powershell -ExecutionPolicy Bypass -File scripts/local_model/stop_local_llm.ps1
```

冷启动：加载 1.5B fp16（~10-15s）+ 3 个适配器 + warmup ⇒ **ready < 90s**（实测见 §6.3）。
模型在后台线程加载，`/health` 立刻可访问（`status=loading`），不阻塞。

### 6.2 接口契约

**GET /health** → 200（永远秒回）

```json
{"ok": true, "status": "ready", "model": ".../Qwen2.5-1.5B-Instruct",
 "adapter": ["self_check", "self_check_min", "route"],
 "adapters": {"self_check": true, "self_check_min": true, "dual_judge": false, "route": true},
 "gpu_mem_mb": 3500, "queue_depth": 0, "uptime_sec": 42.1,
 "load_sec": 14.2, "warmup_ms": 820.0, "error": null}
```

**POST /generate**

| 字段 | 说明 |
|---|---|
| `stage` | `self_check` \| `self_check_min` \| `dual_judge` \| `route`（必填） |
| `text` | 用户内容。若为 JSON 对象字符串，服务按引擎模板拼装结构化 prompt（见下） |
| `messages` | 完整 messages（可含 system）；与 `text` 二选一 |
| `entry` | `0/1/both/all`，选层模板（默认 `1`=研究） |
| `variant` | `full/min`，仅 `self_check` 用（默认 full） |
| `max_new_tokens` | 默认：self_check 320 / self_check_min 64 / dual_judge 320 / route 96 |
| `temperature` | 0=贪心（默认 0） |
| `timeout` | 秒，默认 60，上限 120 |

`text` 传 JSON 对象可自动结构化（引擎/App 最省事）：

- `self_check*`：`{"anchor","candidates":[{desc,attribute,position}],"amps":[...],
  "collision","manifest","quality_flags":[...]}` → 按 `_self_check` user 模板拼装
- `dual_judge`：`{"anchor","question","candidates":[{desc,kind}],"decidability":{...}}`

成功 → 200：

```json
{"ok": true, "stage": "self_check_min", "text": "{\"suspicious_candidates\":[3],...}",
 "json": {"suspicious_candidates":[3],"ing_rephrased":false,"unsaid_is_escape":false},
 "ms": 6120.5, "adapter": "llm_sft/adapter_dgtf_selfcheck_15b_v1",
 "confidence": 0.87, "gen_tokens": 27, "prompt_tokens": 1650,
 "gpu_mem_mb": 3542, "cached": false, "queue_ms": 0.4}
```

失败 → 503/400（结构化，不崩进程）：

```json
{"ok": false, "error": {"code": "TIMEOUT|UNAVAILABLE|BAD_REQUEST|INTERNAL",
                        "message": "..."}}
```

**客户端**（engine/app 直接用，失败返回 dict 不抛异常，便于云回退）：

```python
from dgtf_local_llm.client import LocalLLMClient
cli = LocalLLMClient()                     # 127.0.0.1:8772
r = cli.generate("self_check", text=view_json, timeout=60)
if r["ok"] and r["confidence"] >= 0.9:
    use_local(r["json"])                   # 高置信走本地
else:
    fallback_cloud()                       # 低置信/不可用走云校准
```

实现要点：

- **单卡串行队列**：所有生成进单 worker 队列（`queue.Queue`），GPU 不并发；
  请求按 `timeout` 截止（生成循环内检查 deadline）。
- **启动 warmup**：ready 前跑一次短生成预热 CUDA kernel。
- **LRU 缓存**：`(stage, entry, variant, prompt hash, max_new_tokens, temperature)`
  → 200 条（重复请求 0 GPU 开销）。
- **错误回退**：loading/error → 503 `UNAVAILABLE`；超时 → 503 `TIMEOUT`；
  参数错 → 400 `BAD_REQUEST`；内部异常 → 503 `INTERNAL`（进程不退出）。

### 6.3 实测（`scripts/local_model/probe_local_llm.py`）

实测（`probe_local_llm.py --reps 2`，0.5B + **v2 适配器**，服务 PID 22256，2026-10-25 10:07）：

| 项 | 结果 |
|---|---|
| 冷启动 | load **7.6-8.7s** + warmup **726-1196ms**（ready < 90s ✅） |
| GET /health | p50 **1.8ms**（max 1.9ms），秒回 ✅ |
| POST /generate `self_check`（默认 min schema，**v2 适配器**） | p50 **3.90s**，JSON 合法 2/2 |
| POST /generate `self_check_min` | p50 **4.26s**，JSON 合法 2/2 |
| POST /generate `route`（旧 0.5B route 适配器） | p50 **3.85s**，JSON 2/2，confidence 0.947 |
| 错误回退 | bad stage → **400** `BAD_REQUEST`；`timeout=1` → **503** `TIMEOUT`（1.08s 返回）；缺 `text/messages` → **400** `BAD_REQUEST` |
| 并发 3 请求 | 串行排队：wall 7.26s，3/3 200，无 OOM/崩溃 ✅ |
| 显存 | 服务常驻 **1,042MB**（< 5GB 余量 ✅） |
| 缓存 | 相同请求 `cached=true`，`ms` ~1ms 级（LRU 200 条） |

> dual_judge / self_check(full) 因 0.5B decode 只有 ~6-7 tok/s、目标较长，
> 单次 **16-20s**（v2 target 更短，比 v1 的 33-41s 快约 2 倍），仍**不建议**
> 放进秒级链路；需要全量字段时给足 timeout（≤60s）。
> 服务冷启动 7.2s + warmup 786ms（v2），远低于 90s 要求。

### 6.4 服务实现要点（gf）

- **prompt 所有权**：`stage` 决定 system prompt（引擎 V2.2.2 模板）；调用方传
  `messages` 时**默认保留其 user 内容、替换 system 为服务模板**（本地适配器只
  认自己训练过的模板）；要原样透传自己的 system 传 `"preserve_system": true`。
- **JSON 抢救**：输出被截断/带杂音时用正则抠出三个决策字段（`salvaged: true`），
  保证结构化返回；调用方应按 `confidence` + `salvaged` 决定是否回退云。
- **混合精度**：prefill 用 fp32 GEMM（0.5B 实测 ~1200 tok/s），decode 用 fp16
  （M=1 带宽瓶颈，~9-10 tok/s）；`_set_fp32` 开关在有/无 patch 的 forward 间切换。
- **失败不崩**：所有 handler 包 try/except，异常 → 结构化 503；worker 线程常驻。

## 7. GPU 占用与训练/服务切换

- **训练**：独占 GPU，峰值 ~5.2-5.8GB；**训练时不要起服务**（会 OOM/爆显存）。
- **服务**：常驻 ~3.4-3.6GB（<5GB 余量目标）。
- 切换：`stop_local_llm.ps1` → 训练 → 训练进程退出显存自动释放 →
  `start_local_llm.ps1`。
- 训练完成后**释放显存**的方式就是让训练进程结束（本脚本训练结束即退出，
  不常驻）。

## 8. 已知限制与下一步

1. **底座为 0.5B（非任务原始 1.5B）**：1.5B 在 6GB 卡持续训练降频到 32s/step，
   时间盒内跑不出可用适配器（§4.2 有实测证据）。0.5B 在同时间预算下可多训
   3 倍数据、推理快 2-3 倍；1.5B 路径保留，需要数小时独占 GPU。
2. **决策质量不达标（两轮负结果收口）**：第一轮根因是训练数据中段截断（§5.2），
   第二轮修复后格式达标（JSON 0.857/1.0）但决策仍不达标（三项全对 0）；
   结论见 §5.1 / §9 —— 本地模型仅可用于叙述/联调，不可接管决策。
3. **decode 慢**：0.5B fp16 decode 实测 ~9-10 tok/s（M=1 带宽/内核瓶颈），
   `self_check_min`（3 字段、27 token）单次 ~4s 可接受；11 字段全量（~212 token）
   单次 20-40s，生产建议只走 min 变体，需要解释性 verdict 时再让云补。
4. **route 适配器**沿用旧任务 `llm_sft/adapter_qwen05b_v1`（route_exact 0.357，
   旧基线），本轮未重训（P2）；但在 8772 服务里实测可用（p50 3.6s，JSON 2/2）。
5. **QC 门控不可用**：两轮 confidence 均不区分对错（τ=0.8/0.9/0.95 下
   agreement 不上升，见 §5.1），不能作为 conformal 弃权阈值；级联需另设规则。
6. **训练数据规模**：全量可用 2,490（judge）/ 478（sc_min）条，本轮时间盒只用
   180/110 条 × 1 epoch；要逼近云标签需要数小时全量训练 + 更多 epoch。
7. **数据快照会漂移**：并行 run 持续往 `outputs/` 写 packed，数据集每次重建的
   样本数会变（当前快照 179 份）；`dataset_stats.json` 记录构建时间与统计口径。

## 9. 本轮结论（给 Lead 的取舍依据）

- **服务层：可交付 ✅**。8772 四 stage 接口、`/health` 秒回（p50 1.8ms）、
  `self_check`/`self_check_min` 单次 3.9-4.3s、`route` 3.9s、GPU 常驻 1.04GB、
  冷启动 7.2s + warmup 786ms、单卡串行队列（3 并发 wall 7.3s 不崩）、
  超时/错误结构化 503、JSON 抢救兜底——全部实测通过，engine/app 可联调
  （低置信/salvaged 时回退云）。
- **模型层（第二轮 v2，干净数据训练）：格式有信号 ✅ / 决策未达标 ⛔**。
  - 格式：self_check_min JSON 合法率 **0.286 → 0.857**，11 字段 full 到 **1.0**，
    base 0.5B 为 **0.0**；sc 适配器 val loss 1.679 → **0.224**，
    dj val loss 1.772 → **1.484**。⇒「截断训练数据」根因判断正确。
  - 决策：三项全对仍 **0**（目标 >0.2 未达）；`suspicious_candidates` 退化为
    常量先验（几乎总输出 `[1,2]`），`ing_rephrased`/`unsaid_is_escape` acc 低于
    「恒 false」多数类基线（0.923/0.824），dual_judge position acc 0.25 < 0.54。
  - **QC 门控不可用 ⛔**：τ∈{0.8,0.9,0.95} 下 agreement 不随 τ 上升（≈0），
    confidence 不区分对错，不能当 conformal 弃权阈值。
- **收口判定**：本地模型（0.5B + 180/110 条 × 1 epoch，6GB 卡时间盒内）
  **仅可用于叙述/联调/格式草稿，不可接管决策字段**。该结论已足够支撑
  「本地草稿 + 云校准」级联的工程决策：级联中的本地档只做预填/草稿，
  决策与自省判定仍走云。
- 第一轮全部证据归档 `llm_sft/_round1_evidence/`；第一轮适配器留档
  `llm_sft/adapter_dgtf_*_05b_v1_truncated_bak/`；第二轮为
  `llm_sft/adapter_dgtf_*_05b_v2/`。
- **后续若要接管决策**：1.5B 底座 + 全量 2,490/478 条 × 2-3 epochs（6GB 卡约
  6-10 小时独占 GPU）+ 更大 eval 集；数据/训练/评测管线已就绪，直接改
  `--model/--max-train/--epochs` 即可。

## 5.3 1.5B 适配可行性（Round 3，2026-10-25）

目标：验证「换 1.5B 底座能否让本地模型接管决策」。结论：**当前 6GB 显卡不可行**。

训练尝试（	rain_dgtf_stage_lora.py）：
- A：1.5B + fp16 权重 + **fp32 GEMM** + max_len 2048 + 120 样本：显存峰值 **6.78GB > 6.44GB**
  → CUDA allocator 反复 OOM 重试，实测 **~100s/step**（22 分钟只走到 step 10）⇒ 中止。
- B：1.5B + **fp16 GEMM** + r=8 + 80 样本 + max-steps 20：943s / 47s/step 完成 20 步
  （仍伴随 OOM 重试告警），适配器 llm_sft/adapter_dgtf_selfcheck_15b_v1；
  est_val_loss=Infinity（OOM 下验证未算完）⇒ 只能算「半成品」。

评测（scripts/local_model/eval_15b_adapter.py，held-out self_check_min 12 条，含 base 对照）：

| 指标 | 1.5B+适配器(20步) | 1.5B base | 0.5B v2 适配器（对照上表） |
|---|---|---|---|
| JSON 合法率 | 1.000 | 1.000 | 0.857 |
| 三项全对率 | 0.000 | 0.000 | 0.000 |
| suspicious F1 | 0.213 | 0.042 | 0.132 |
| ing_rephrased acc | 0.833 | 0.917 | 0.786 |
| unsaid_is_escape acc | 0.417 | 0.583 | 0.643 |
| p50 延迟 | **15.4s** | 13.4s | **6.1s** |

判读：
- 1.5B base 的 JSON 格式能力本身就好（1.0），但**语义决策仍全错**；20 步适配器只在
  suspicious F1 上略优于 base，其余更差 ⇒ 训练量远不够（且被 OOM 拖到 47s/step）。
- 1.5B 推理 p50 15.4s ≈ 0.5B 的 2.5 倍，却拿不到更好的决策质量 ⇒ 在本机没有部署价值。
- **收口**：生产保持 0.5B 服务（仅叙述/格式草稿，不接管决策）；要真正接管决策，
  需要 ≥12GB 显存 + 2~3 小时以上训练 + 更大评测集。1.5B 适配器与 metrics 留档为负证据。


## 5.4 第三轮重训（478 样本）中止记录（Round 4）

目标：把 self_check 训练从前两轮 180 条扩到 478 条，提升 JSON/字段质量。

实测（2026-10-25 12:54~13:40）：
- 启动时 GPU 被并发 app/BGE 进程部分占用；2048 序列的 fp32 logits 分配约 1.2GB，
  训练反复触发 CUDA OOM 重试，step/s 掉到 **0.05（≈20s/step）**，ETA 115min ⇒ 中止；
- 已保存 step-120 适配器（本地留档 _05b_v3_step120，权重不入库）；
- 评测（held-out self_check_min 12 条，base 0.0 JSON）：
  v3_120 JSON 0.833 / 三项全对 0 / susp F1 0.231 / ing 0.75 / esc 0.333 / p50 8.4s；
  v2_180 JSON 0.857 / 三项全对 0 / susp F1 0.132 / ing 0.786 / esc 0.643 / p50 6.1s；
  ⇒ 样本更少 + 并发干扰，v3 未超过 v2；**服务默认保持 v2**。
- 教训（写入上表 §5.2 同类）：6GB 卡训练必须 **GPU 独占**（先停 BGE 服务与
  本地推理服务），并先观察 step/s 再放大样本；下一轮用独占窗口跑 180~240 条。
- 证据：llm_sft/eval_dgtf_stage_05b_v3_step120.json、
  llm_sft/_round4_evidence/v3_training_partial.log。


## 5.5 第四轮重训（197 样本 / fp16 compute / max_len 1792）：未超过 v2（Round 7）

目标：绕开 2048 序列的 fp32 logits 显存瓶颈，用 fp16 compute + 1792 序列把样本量
从前两轮 180 条提到 240 条（drop-truncated 后实际 **197 条**）。

训练：train_loss 0.2848 / **val_loss 0.2331**（v2 0.22379），197 steps，58 分钟，
峰值显存 4.71GB（fp16 compute；仍有零星 OOM 重试但不致命）。

held-out 评测（self_check_min 12 条，base 0.5B JSON=0.0）：

| 指标 | v4（197 样本, fp16 compute, 1792） | v2（180 样本, fp32 GEMM, 2048） |
|---|---|---|
| JSON 合法率 | 0.583 | **0.857** |
| 三项全对率 | 0 | 0 |
| suspicious F1 | 0.099 | **0.132** |
| ing_rephrased acc | 0.583 | **0.786** |
| unsaid_is_escape acc | 0.167 | **0.643** |
| 字段平均 acc | 0.250 | **0.476** |
| p50 延迟 | 8.65s | **6.10s** |

判读：**v4 未超过 v2**（各字段一致更差；样本 n=12 有噪声，但方向一致）。
可能原因：① fp16 compute 训练数值精度/梯度质量下降；② max_len 1792 仍裁掉
43 条长样本，且截断策略对候选完整性有损；③ 0.5B 容量已到语义决策上限。
⇒ **服务默认保持 v2**（`adapter_dgtf_selfcheck_05b_v2`）。v4 适配器、metrics、
loss 曲线与评测结果作为负证据留档；6GB 卡上继续堆样本/换训练精度不解决问题，
本地模型定位维持「叙述/格式草稿，不接管决策」。


## 5.6 第五轮（v5）：240 样本 / max_len 1900 / fp32 GEMM —— 全面 ≥ v2，切换为服务默认（Round 21）

训练：0.5B self_check_min（min 变体），240 样本保留 **230 条**（drop-truncated），
1900 max_len，fp32 GEMM（GPU 独占，峰值 4.92GB），lr 1e-4，75 分钟：
train_loss 0.2789 / **val_loss 0.2352**（v2 0.2238）。

**30 条 held-out 同批 A/B（apply_self_check_min，脚本 eval_15b_adapter）**：

| 指标 | v2（180 样本） | **v5（230 样本）** | 判读 |
|---|---|---|---|
| JSON 合法率 | 0.967 | **1.000** | v5 全合法，解析失败归零 |
| 字段平均 acc | 0.367 | **0.378** | +1.1pp |
| suspicious F1 | 0.161 | **0.165** | +0.4pp |
| ing_rephrased acc | 0.900 | **0.933** | +3.3pp |
| unsaid_is_escape acc | 0.200 | 0.200 | 持平 |
| p50 / p95 延迟 | 6.02s / 7.42s | 6.73s / 9.41s | 略慢（narration 可接受） |

⇒ **v5 在全部质量指标上 ≥ v2**（「只变好不变坏」），延迟略增；决策：
`ADAPTER_CANDIDATES` 默认改为 **v5 优先、v2 兜底**；新增 `DGTF_LOCAL_ADAPTER`
环境变量可覆盖（A/B/灰度），默认行为由候选顺序决定。

服务验证（8772，重启后）：
- `/health.adapter_paths`：self_check/self_check_min = **adapter_dgtf_selfcheck_05b_v5**；
- `/generate`（self_check_min 样例）：4463ms，输出合法 JSON
  `{"suspicious_candidates":[1,2],"ing_rephrased":false,"unsaid_is_escape":false}`；
- 证据：`llm_sft/eval_dgtf_stage_05b_v{2,5}_limit30.json`、
  `llm_sft/eval_dgtf_stage_05b_v5.json`、`llm_sft/train_metrics_dgtf_selfcheck_05b_v5.json`、
  `llm_sft/service_probe_v5_health.json`。


## 5.7 本地 v5 接管 self_check：端到端三跑次（Round 22）

服务默认已切 v5（Round 21）；本轮用 `--self-check-mode local` 让引擎把 self_check
阶段交给本地 8772 服务（v5），与云端 llm 模式对照（同题、web off/on 按题）：

| 跑次 | 模式 | quality | aq/ready | total tokens | self_check tokens | wall |
|---|---|---|---|---|---|---|
| 推理·热岛 | llm（基线） | 0.9465 | verified | 723,064 | 75,023 | 586s |
| 推理·热岛 | **local(v5)** | 0.9279 | verified | 690,443 | **49,656（−34%）** | 725s |
| 推理·静电 | llm（基线） | 0.9400 | verified | 718,020 | — | 585s |
| 推理·静电 | **local(v5)** | 0.9297 | verified | 649,563 | **47,827** | 777s |
| 事实·HTTP404 | llm（v17） | 0.9062 | verified/ready | 992,929 | 101,929 | 958s |
| 事实·HTTP404 | **local(v5)** | **0.9274** | verified/ready | 916,468 | **73,430（−28%）** | 1063s |

判读：
1. **能力已验证**：本地模式稳定接管（服务日志 27 次 generate 200，无超时/回退），
   事实题与推理题均 verified；
2. **省钱幅度有限**：self_check 占全量 ~10%，替换后 stage tokens −28~34%，
   总成本约 −4~8%；墙钟 +11~33%（本地生成 ~4-5s/次叠加）；
3. **质量在噪声内 ±2pp**（事实题本样本 +2.1pp、推理题 −1~2pp）；
4. **决策：不设为默认**（墙钟与质量不确定性 > 成本收益），保留为 opt-in
   （`--self-check-mode local`）；默认仍 llm 模式。


## 5.8 本地服务可观测性 `/metrics` + 并发实测（Round 25）

### 5.8.1 新增能力

`dgtf_local_llm/service.py` 新增：
- `GET /metrics`：返回 `state/model/adapter_paths/stats/avg_ms`；
  stats = `{requests_total, by_stage, errors, total_ms, max_ms, last_ms,
  last_stage, last_adapter, busy_now}`（线程安全）；
- 每次 `/generate` 记录阶段耗时/适配器/错误；`busy_now` 可直接用于 App 动态降级；
- 新增 `scripts/check_local_service.py`（health/metrics/单发/并发 可复现检查）。

### 5.8.2 实测（v5 服务，script 复现）

- 单发：`self_check_min` 3.7–4.1s，adapter=v5；
- 并发 4 请求：**串行化**（total wall 15.58s ≈ 4×3.9s；单项 wall 4.1/7.9/11.7/15.6s，
  生成 ms 稳定 3.8–4.1s）——GPU 生成受全局锁保护，排队时间计入请求 wall；
- 统计正确：`requests_total=8, by_stage={self_check_min:8}, errors=0,
  avg_ms=10913.9`（avg 含排队；`ms` 字段仍为纯生成时间，可区分）；
- 健康检查：`/health` state=ready，adapter_paths self_check/self_check_min=v5。

### 5.8.3 判读与用途

1. App/引擎可用 `/metrics.busy_now` 与 `avg_ms` 做「本地忙 → 走云端 / 降档」决策，
   避免并发排队把任务 wall 拉长；
2. 单任务（引擎串行调用）不受影响；多任务并发时建议 App 侧限制本地 self_check 并发
   或按 busy 自动回退云端（fail-open）；
3. 证据：`llm_sft/service_metrics_round25.json`、`scripts/check_local_service.py`。


## 5.9 v6 训练与切换（Round 38，230 样本 × 2 epochs）

### 5.9.1 训练

`train_dgtf_stage_lora.py`：230 样本（min 变体、max_len 1900、fp32 GEMM、lr 8e-5、
`--epochs 2`、save-every 60）。结果：epoch2 train_loss 0.23294 / val_loss 0.23382，
**best_val_loss 0.22212**（v5 为 0.23518），steps 442，训练 7715s，峰值显存 4.92GB。
（收尾评测阶段 OOM 与 v5 相同：仅影响脚本末尾附加评测，适配器与指标已保存。）

### 5.9.2 30 条 held-out A/B（同集）

| 指标 | v5 | **v6** | 判读 |
|---|---|---|---|
| json_valid_rate | 1.000 | 1.000 | 持平（已饱和） |
| decision_field_mean_acc | 0.378 | **0.589** | +21.1pp |
| unsaid_is_escape_acc | 0.200 | **0.800** | +60pp |
| decision_all3_acc / set_acc | 0.0 / 0.0 | **0.033 / 0.033** | 首次破零 |
| susp_f1 | 0.165 | 0.153 | −0.012（噪声级） |
| ing_rephrased_acc | 0.933 | 0.933 | 持平 |
| 延迟 p50 / p95 | 6.73s / 9.41s | **6.27s / 7.47s** | 更快 |

### 5.9.3 决策与落地

综合显著更优（字段/escape/all3/延迟全面提升，仅 suspF1 噪声级回落）⇒
**服务默认适配器切 v6**（`ADAPTER_CANDIDATES`：v6 → v5 → v2 → v1 兜底），
`train_metrics_dgtf_selfcheck_05b_v6.json` 归档；实测 `/health.adapter_paths`
self_check(self_check_min)=v6；`scripts/check_local_service.py` 单发生成通过；
并发/排队特性不变（单一 GPU 锁）。


## 5.10 v6 服务侧 A/B（local self_check opt-in，Round 39）

引擎真实跑次（fast+web，`--self-check-mode local`，服务默认 v6）：

| 题 | self_check | quality | tokens | calls | wall |
|---|---|---|---|---|---|
| 光速 | llm（基线） | 0.9508 | 727,103 | 98 | 276s |
| 光速 | **local v6** | **0.9814** | **583,161（−19.8%）** | 89 | 360s（+30.6%） |
| 出生人口 | llm（基线） | 0.9673 | 705,691 | 108 | 263s |
| 出生人口 | **local v6** | 0.9250（−4.2pp） | **622,434（−11.8%）** | 100 | 412s（+56.5%） |

判读：
1. **质量**：一题 +3.1pp、一题 −4.2pp（均值 −0.6pp，噪声级；两题均 verified/ready）；
2. **token**：−11.8% ~ −19.8%（v6 self_check 判断更准，减少重试/回环）；
3. **墙钟**：+31% ~ +57%（本地 0.5B 单发 ~6s × 16 次 self_check 的固有开销）；
4. 服务 `/metrics` 记录 self_check 16 次全走 v6（by_stage 可审计）。

**结论：v6 local 自检维持 opt-in（默认仍 llm）**——质量不显著变差、token 明显省，
但墙钟代价大；仅建议预算敏感且可等待的场景显式开启。与 v5 时代策略一致，
符合「只变好」：默认路径质量未变，opt-in 路径 token 更省。


## 5.11 v8b（mixed 配方）评测与切换（Round 79）

- 训练：mixed 变体，168 样本 ×2 epochs，val_loss 0.9895（不同 val 子集，偏高）；
- 30 条 held-out：字段 0.589 / escape 0.800 / JSON 1.0 / all3 0.033 —— **与 v6 完全持平**；
  suspF1 0.141 vs 0.153（噪声内）；**p50 5858 vs 6271ms、p95 6340 vs 7474ms（更快）**；
- 判定：SWITCH_CANDIDATE；服务默认切 **v8b**（v6/v5/v2/v1 兜底，val_loss 偏高保留回退）；

## 5.12 v9b（0.5B 纠错重训）评测与切换（Round 123）

- 根因纠错：v9 漏传 `--model` 误用 1.5B base（不兼容 0.5B 服务），已归档并加防错训守卫；
- v9b：`--model Qwen2.5-0.5B-Instruct`，min 230×2、lr 6e-5、seed 7、max-len 1900；
  最佳 **val_loss 0.1989**（v6 0.2221、v8b 0.9895）；peak 4.93GB、训练 3255s（专用 GPU 窗口）；
- 30 条 held-out：JSON 1.0 / 字段 0.589 / escape 0.800 / suspF1 0.141 / all3 0.033，
  **与 v8b 完全持平**；p50 **4774ms** / p95 **5690ms**（v8b 5858/6340）⇒ SWITCH_CANDIDATE；
- 服务默认切 **v9b**（self_check_min；self_check 槽位 v8b；v8b→v6→v5→v2 兜底）；/metrics 单发 3.66s、errors=0；验收 **17/17**（最新）。
