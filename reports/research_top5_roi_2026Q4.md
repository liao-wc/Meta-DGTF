# Top5 ROI 校验方案（配套 docs/research_mechanisms_2026Q4.md）

> 用途：把主报告的 Top5 从「建议」变成「可执行、可验收、可回滚」的试点包。
> 边界：本文件只是方案，**本次调研未执行任何真实 DeepSeek API 调用**（预算 ¥24.84，留给实现阶段）；未改任何代码/配置/数据。文中命令均为建议草案，由实现者在其分支执行。
> 数据基线：`outputs/20261025_064705_为什么城市热岛效应在夜间比白天更明显.packed.json`、`dgtf_memory/quality_predictor.json`、`dgtf_memory/episodes.jsonl`、`docs/remaining_optimization_assessment_20261025.md`。

## 0. 通用度量口径（所有实验共用，避免自欺）

| 指标 | 取值来源 | 说明 |
|---|---|---|
| quality | packed `quality`（综合分）+ `answer_quality`（verified/unverified/needs_evidence） | 主验收指标；B 基线 1.000、serial 0.990、fast 0.930 |
| wall | 任务实际耗时（App run.json / 引擎计时） | 主成本指标；B 基线 1064.3s |
| tokens | packed `llm_tokens.total` + `llm_by_stage[]` | 分 stage 归因，禁止只看总量 |
| API 费 | usage 的 `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` / completion tokens × 官方价 | 必须分别记 hit/miss，否则缓存收益不可见 |
| 本地延迟 | llm env 内计时（load / prefill / decode 分开） | 本地实验必须报 p50/p90，不用单次 |
| 判定一致性 | packed `views[*].candidates[*].position` 与本地草稿对比 | 类别基线：`0` 57.4% / `1` 39.9% / `both` 2.6%（177 packed 实测） |

**纪律**：① 同题 A/B（同一 question、同一引擎版本、同一 mode）；② 每项先做零 API 的离线版，再决定是否花预算；③ 任何触碰 prompt 内容的改动都必须过质量门 1.0（≥0.99 才算不退化）；④ 单次实验 API 预算上限 ¥0.8，超出即停。

## P1. DeepSeek 前缀缓存对齐 + prompt 稳定段前置（Top1）

**现状（本仓库实测）**
- `_dual_judge`（V2.2.2:12234–12400）system 组装顺序：判断者身份 → 层 spec → how → 规则 → **carry 块（本 run 可变）** → JSON schema → **`_self_block()`（动态记忆，10935–10941）**；user = 处境（anchor + 上游 shapes + 背景）→ dec 块 → 候选列表。
- 每次调用约 15.0K tok（225,512/15），其中候选列表只占小部分；**同一 run 内 15 次调用的 system 前缀高度相似，但动态内容把可缓存前缀截断在很靠前的位置**。
- DeepSeek 缓存规则：前缀必须**从 token 0 起完全相同**、64 token 存储单元、命中价 $0.003/M（谷时）vs miss $0.15/M ⇒ **50×**。当前 App 的项目背景由 `server.py:9584-9589` 拼在**用户问题前**，进引擎后落在 user 中段 ⇒ 跨任务无法命中。
- 已有探针：`scripts/run_engine_instrumented.py` 会统计 `prompt_cache_hit_tokens / prompt_cache_miss_tokens / dup_prompts`，并支持 `--prefix` 给 system 前置静态前缀（第 92–100 行）——**从未在本仓库留下读数**（未见 probe 产物），说明命中率目前未知。

**假设 H1**：当前单 run 内 judge/self-check 提示词的「跨调用最长公共前缀」token 占比 <10%；按「稳定→易变」重排后可到 40–60%。
**假设 H2**：重排不改变输出质量（内容集合不变，仅次序变）。

**实验 A（1 小时，零 API）**：写只读脚本从 1 个 packed 重建 30 条 judge/self-check 的 (system,user) 文本（用 `views` 和 `llm_by_stage` 的 calls 数量对齐），用本地 tokenizer（`local_model/models/Qwen2.5-1.5B-Instruct`）统计：
1. 现有顺序下，相邻/全部调用两两最长公共前缀（token）的中位数；
2. 新顺序（system 固定段全部前置；carry/背景/anchor 紧随；候选列表永远最后；`_self_block` 移到 user 末尾）下同样的统计；
3. 结论：可缓存 token 占比从 x% 到 y%。
**实验 B（1–2 小时，API ≤¥0.3）**：选一个 5 分钟级小任务，用 instrumented runner 跑一次，读 probe JSON 的 `cache_hit_ratio`；再加 `--prefix`（把项目背景/固定 spec 前置）复跑一次，比较 hit 比例与 wall。

**验收阈值**：实验 A 显示可缓存占比 ≥40%；实验 B 的 `cache_hit_ratio` ≥0.30 且任务 quality ≥0.99（同一题与基线对照）。
**回滚条件**：任一实验 quality <0.99，或 wall 变长 >10%，立即回滚（重排只在 prompt 组装函数内，改动可局部 revert）。
**预期收益**：输入费 −28~43%【推断】；¥24.84 的 B 跑数 10 → 13~14 次；TTFT 下降（官方示例 13s → 0.5s）。
**注意**：缓存是「尽力而为」，同内容不同机器/不同时间可能 miss；不要用「理论命中」当验收，必须实测。

## P2. Conformal 化 M4 质量预测器（Top2）

**现状**：`dgtf_memory/quality_predictor.json` = kNN(k=3) + 22 特征 + **142 行**（y∈[0.03,1.0]）；`mode_fusion.py:97-133` 用 `pred = 0.5*model_pred + 0.5*mode_low` 硬夹取后与 `min_quality` 比较——**这是经验校准，无保证**；`quality_predictor.py` 只有 `evaluate`（MAE/R²=0.916），无区间。

**方法（CQR 型 split conformal）**
1. 切分：按时间取后 30%（43 行）作校准集，其余 99 行作训练/拟合；kNN 用切分后重拟合（禁止 in-sample 残差）。
2. 分数：`s_i = max(ŷ_i − y_i, 0)`（保守下界）。
3. 分位：`q̂ = ⌈(n+1)(1−α)⌉/n` 分位（n=43、α=0.1 ⇒ 保守分位；α=0.2 才实用，需报两档）。
4. 决策：`LB = ŷ − q̂`；`LB(mode) ≥ min_quality` 才允许选该 mode；否则升级；连 B 都不达 ⇒ 输出弃权标记（`unverified/needs_evidence`），不得静默 verified。
5. 报三个数：留出集 coverage（目标 ≥1−α，允许 −0.05 容差）、平均区间宽度、**与现决策的切换率**。

**1 小时版（零 API）**：只在 142 行上做时间切分 + CQR，输出 coverage/宽度/切换率表；附带做「用 0.5*prior 夹取的现方案」同口径对照。
**验收阈值**：coverage ≥0.95（α=0.1 时），宽度中位数 ≤0.12，切换率 10–40%（切换率 >40% 说明历史分布漂移，需先查特征）。
**回滚条件**：coverage <0.85 或切换率 >50% ⇒ 不接入 `fused_plan`，只保留离线报告。
**落地改动面**：`quality_predictor.py` 增 `residual_q{alpha}` 字段与 `lower_bound()`；`mode_fusion.py:109-133` 用 `LB` 替换经验夹取；`server.py:9708-9723` 增 `quality_prediction_lb` 读数（**改动由实现者做，本次未改**）。
**成本**：2–3 人时，¥0。

## P3. 本地判官草稿 go/no-go（Top3，Lead 最高优先级方向的前置判决）

**为什么先做它**：本地 1.5B 直接替换 judge 在 ¥ 上只值 ~5% 预算，墙钟还要 +1.5–3×【主报告 §0/§2.3】。若「高置信子集本地直判」的覆盖率不够，整条路线应尽早终止，省下 2–4 人日。仓库已有 **17,394 条候选级 position 标签**（177 packed）可零成本验证。

**DDV 协议规范（建议实现契约）**
```
输入：view 上下文摘要 ctx（≤1200 字，抽取式）+ 候选列表 [{idx, kind, desc}]
本地模型输出（严格 JSON）：{"p":[{"idx":1,"position":"0|1|both","conf":0..1}]}
conformal 集合：C_i = { 构造满足 s_i ≤ q̂ 的标签集合 }，s 用 1−conf 或 top-k 概率
接受规则：|C_i| == 1 → 本地直判；否则 → 弃权（含全部 both 候选）
云端验证（仅弃权项）：user = ctx 摘要 + 弃权候选子集，要求输出 {"p":[{"idx":..,"position":..}]}
                       云端只判正确性，不做与草稿的逐字对齐（依据 Judge Decoding, 2501.19309）
保守性：单候选 P(真值 ∉ C_i) ≤ α；对 m 条被接受判定，错误率上界 mα（union bound）
        ⇒ 取 α = α0/m（α0 = 目标「整轮无错」概率，例如 0.05）
回退：弃权率 >70% ⇒ 整次调用退回原全量云端判官（无质量损失，只损一点本地算力）
```
**实验（零 API，分两级）**
- L0（1 小时）：抽 50 条候选（覆盖 5 个 view/run），零样本本地判 position；报「多数类基线 57.4%」「整体一致率」「按 conf 分箱后的条件一致率」。
- L1（4–6 小时）：抽 500 条，做 LoRA 微调前/后对比；用 conformal 阈值搜 α=0.05 下的覆盖率与条件错误率。
**判死条件（任一满足即停）**：conf 最高分箱（top 20%）条件一致率 <80%；或 α=0.05 下可直判覆盖率 <15%；或单次本地草稿 p50 > 30s（本地 prefill 太贵）。
**通过后的验收**：可直判覆盖率 ≥40% 且条件错误率 ≤5% ⇒ 才进入引擎改造（`_dual_judge` 返回结构加 `source: local|cloud`，位置来源留痕，便于审计）。
**风险**：GPU 当前被其他 bench 占用（实测 free 67–107 MiB）⇒ 必须排队/串行，或先跑 CPU（0.5B）拿下限估计；`both` 仅 2.6%，建议直接不本地判。

## P4. self_check / dual_judge 可计算判据下沉 + 上下文压缩（Top4）

**现状**：self_check 15 次、199,717 tok（13.3K/call）；dual_judge 15 次、225,512 tok（15.0K/call）；两者合计 25.1% tokens、37% 阶段耗时。引擎已把「未生计数」下沉为代码（`_count_unsaid` + 双源闸 P2-4/P2-8），但第 3 问（ing 近义复述比）仍靠模型；user 里塞了 `collision[:1500]`、`manifest`、候选/& 全量。
**假设**：① 复述比可由 BGE（服务 8771）余弦 ≥0.95 近似替代，与模型判断一致率 ≥85%；② 把上游 shapes 从 1200 字压到 400 字（抽取式）后 quality 不变。
**实验（零 API 先行）**
1. 离线：对 30 条 packed 的 self_check 输入重算「代码复述比」，与 packed 中 `ing_rephrased` 字段比对一致率（混淆矩阵）。
2. 离线：统计 judge prompt 中「候选列表 / 上游 shapes / 背景 / 规则」四类字符占比，给出压缩上界。
3. 在线 A/B（API ≤¥0.8）：同题跑「截断 1200→400 + collision 1500→600」一版，比 quality/tokens/wall。
**验收**：离线一致率 ≥85%；在线 quality ≥0.99 且 tokens −6~10%（−100~170K/跑）。
**回滚**：quality <0.99 或 `needs_evidence` 比例异常上升 ⇒ 回滚截断参数。
**注意**：不要动 `unsaid` 阈值逻辑（`_unsaid_escape_limit`），V2.2.2 的双源闸刚修好；与本项无关。
**成本**：3–5 人时 + ≤¥0.8。

## P5. 6GB 推理栈收口：常驻服务 + QLoRA 蒸馏（Top5）

**现状缺口（实测）**
- `server.py:6154` 指向 `<root>/llm_predict.py`，该文件**已不存在**（在 `archive/legacy_root/`），`_llm_predict_local`（6895–6939）在 `auto_llm`/`/api/schedule/llm/*` 路径必失败；默认任务不受影响。
- 每次调用 spawn 进程加载 fp16 权重（3.09GB），p50 3–5s 冷加载【推断】；GPU 实测空闲 67–107 MiB（桌面 989MiB + 并发 bench 4.7GB）。
- 无 tensor core（GTX 1660 Ti / SM 7.5）：vLLM 兼容表 Turing 支持 AWQ/GPTQ/INT8/GGUF、不支持 Marlin/FP8；另有 issue 称 fp16 在本卡 batch decode 反而慢【外部，未复现】。

**实验（1 小时，零 API）**
1. 在 llm env 里对同一短 prompt 连跑 10 次：模式 A = 每进程冷加载 + 生成；模式 B = 进程内常驻 + 10 次生成。报 p50/p90 的 load/generate 占比 ⇒ 得到「常驻化」收益上界。
2. 同时记录显存峰值（`torch.cuda.max_memory_allocated`）与是否触发共享内存回退。
**验收**：常驻化 p50 延迟 ≤1s（短 prompt、输出 ≤100 tok）；显存峰值 ≤4.5GB（给桌面留 1GB）。
**后续（5–8 人时，择一）**：① 装 CUDA 版 llama-cpp-python + GGUF Q4_K_M（1.0–1.4GB），起常驻服务，`_llm_predict_local` 改成 HTTP 调用；② 或先把 transformers 常驻化（改动最小，但显存仍 3.8GB 级别）。推荐 ①，理由：权重小一倍、留出显存给 KV 与并发；llama.cpp 自带前缀复用，天然适配「同一 run 多次 judge 草稿」。
**QLoRA/蒸馏（4–6 人时）**：`scripts/local_model/train_llm_lora.py` 改 4bit + `max_len` 512→2048，数据从 122 条扩到 packed 派生的判定样本（17,394 条候选级标签，注意按 run/问题分组防泄漏）；训练目标与 `_dual_judge` JSON 契约一致。
**验收**：JSON 合法率 ≥0.99、position 一致率（高置信子集）≥ 目标、训练峰值显存 ≤4.5GB。
**风险**：编译/toolchain 失败；显存争用导致 OOM；QLoRA 在 2048 上下文 + 6GB 上仍需 gradient checkpointing 与 batch=1。

## 6. 排期与预算（建议）

| 阶段 | 内容 | API 预算 | 人时 | 决策点 |
|---|---|---|---|---|
| D0 | P1 实验 A、P2、P4 离线、P5 延迟对照（全零 API，可并行） | ¥0 | 6–8 | 是否进入 D1 |
| D1 | P1 实验 B + P4 在线 A/B（谷时执行） | ≤¥1.0 | 3–4 | 缓存命中率与质量是否达阈 |
| D2 | P3 L1（本地，零 API）+ P3 判死/放行 | ¥0 | 4–6 | 本地草稿方向 go/no-go |
| D3 | 落地 P5 常驻服务 + QLoRA（若 P3 放行） | ¥0 | 9–14 | 是否引擎化改造 |

**执行纪律**：真实跑排北京时间 18:00 后或周末（官方谷时半价）；每阶段先跑 1 个短题试水再放量；任何一项超预算立即停并复盘。

## 7. 风险登记（Top 项）

| 风险 | 触发条件 | 处置 |
|---|---|---|
| 显存争用 OOM | 桌面占用 + 并发 bench（实测 free 67–107 MiB） | 单实例锁 + 队列；跑本地模型前先探测 free ≥3.5GB，否则降级 CPU/0.5B |
| 质量门不达标 | A/B quality <0.99 | 只回滚该项 prompt/截断参数，不动引擎主干 |
| 分布漂移使 conformal 失效 | 换模型/换模式/换 prompt 后 coverage 掉 | 每次改动后重校准；把 `校准时间/样本量/α` 写进模型旁挂元数据 |
| 命中率无法复现 | 缓存「尽力而为」 | 以 probe 实测 `cache_hit_ratio` 为唯一验收口径；不达标则只保留 prompt 瘦身收益 |
| 本地草稿拖慢墙钟 | 单次 >30s 或并行无法隐藏 | 只在高置信子集用；否则整次退回云；记录 `source` 以便审计 |
| 归档脚本误用 | `llm_predict.py` 已移入 archive | 恢复前先确认与 `_LLM_BACKENDS`/adapter 契约一致；不要直接 cp 旧脚本（旧默认路径还指向 D:/元DGTF-多模并行架构） |

## 8. 附：建议命令草案（实现者执行，本次未运行）

```powershell
# P1 实验 B：带用量探针的小任务（先确保 quality_policy=stable、单题）
& local_model\envs\dgtf_llm_env\Scripts\python.exe scripts\run_engine_instrumented.py `
  --probe-out reports\research_probe_prefix.json `
  -- dgtf_engine\dgtf_v2\engine\Meta-DGTF-V2.2.2.py --question "1+1=?" --web off --parallel serial

# P5 延迟对照：同一短 prompt 冷加载 vs 常驻（10 次）
& local_model\envs\dgtf_llm_env\Scripts\python.exe -c "import time,torch;from transformers import AutoModelForCausalLM,AutoTokenizer;..."
```
> 注：`run_engine_instrumented.py` 的 `--probe-out` 会在 `finally` 中写 JSON，即使引擎提前退出也会落盘；判读时以 `usage_has_cache_fields` 为准——若为 false 说明该端点/版本未返回缓存字段，此时只能靠 `dup_prompts/unique_prompts` 做下限估计。
