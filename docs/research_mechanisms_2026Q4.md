# 前沿机制调研（2026Q4）：可落地到 Meta-DGTF-道生三阶模型的机制清单

> 角色：researcher（task-4）。只读代码/只读产物，只写本文件与 `reports/research_top5_roi_2026Q4.md`；未改任何代码、配置、数据，未触碰 `dgtf_memory/`。
> 证据分级：【证据】= 论文/官方文档/本仓库实测；【推断】= 本调研的推算或判断，未经本机验证。
> 基准引擎：`dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.2.py`（31616 行）。Top5 明细校验方案见 [reports/research_top5_roi_2026Q4.md](../reports/research_top5_roi_2026Q4.md)。

## 0. 结论先行（与任务假设有冲突的部分必须说清）

1. **「本地 1.5B 直接替换/分担 dual_judge、self_check」在本机硬件上不划算，除非改成「本地直判 + 云端只判弃权子集」**【推断，基于本仓库实测成本 + 硬件规格】。理由：这两类调用是**输入主导**（实测 15.0K tok/call、13.3K tok/call），而它们的云端费用只占单次 B 跑的 **≈4.5%**（本仓库实测 token 结构 + DeepSeek 官方价）；单靠在本地重读 13K 上下文来省这 5% 预算，会额外付出 15–35s/call 的本地 prefill【推断：5.4 TFLOPS FP32 / 288 GB/s 上限推算】，墙钟反而变差。
2. 真正的大钱在**输入端缓存**：DeepSeek 官方 cache hit 输入 **$0.003/M** vs miss **$0.15/M（均为谷时）**，差 **50 倍**【证据，官方定价页】。把 judge/self-check 的 prompt 前缀按「稳定→易变」重排，是零质量风险的省钱项，也是本次 Top1。
3. 风险可控弃权（conformal）最适合的落点**不是**本地小模型，而是**已有的 M4 质量预测器**（kNN+ridge，142 条标注、22 特征，`dgtf_memory/quality_predictor.json`）。它零 GPU、零 API、已有历史数据，能给出「预测下界 ≥ 目标质量」的分布无关保证，直接替换 `mode_fusion.py` 里 `0.5*pred+0.5*先验` 的经验校准。这是 Top2。
4. 本地模型方向仍值得一次性小额投资去**证伪/证实**：仓库已有 **17,394 条候选级 position 标签**（177 个 packed 跑）可做**零 API 成本**的 go/no-go 实验（Top3）。先花 1–4 人时决定要不要投 2–4 人日，而不是直接开工。
5. **预算纪律优先于机制**：官方定价页明确 peak 时段为 UTC 01:00–04:00 / 06:00–10:00（= 北京时间 09:00–12:00 / 14:00–18:00，周一至五），其余时间与周末按谷时半价【证据，官方定价页】。真实跑排到北京时间 18:00 后或周末，等效于所有机制优化再加成 50%，零代码改动。

## 1. 基线数据与硬约束（全部来自仓库实测/官方规格）

### 1.1 引擎成本结构【本仓库实测，`outputs/20261025_064705_为什么城市热岛效应在夜间比白天更明显.packed.json`】
| stage | calls | tokens | ms | tok/call |
|---|---:|---:|---:|---:|
| unknown（展开/生成主链） | 56 | 1,054,126 | 1,783,198 | 18,824 |
| dual_judge | 15 | 225,512 | 234,258 | 15,034 |
| self_check | 15 | 199,717 | 156,871 | 13,314 |
| probe_meta/duel/research/phase | 14 | 147,502 | 67,069 | — |
| re_evaluate_pool | 14 | 16,544 | 25,971 | 1,182 |
| check_structure_saturation | 7 | 5,058 | 7,088 | 723 |
| **合计** | **136** | **1,696,406** | — | — |

- dual_judge + self_check = **425,229 tok（25.1%）**、**391s 阶段耗时（37% of B 的 1064.3s）**【本仓库实测 + mode_fusion 实测墙钟】。
- 并行模式实测（`dgtf_v2/mode_fusion.py:18-35`）：B = quality 1.000 / 1,269,082 tok / 1064.3s；serial = 0.990 / 997,457 / 1920.6s；fast = 0.930 / 816,983 / 782.6s；web = 0.933 / 1,062,012 / 1073.3s。
- 负结果（`docs/remaining_optimization_assessment_20261025.md:3-36`）：B + 全局关 self_check = 0.940 / 1,029,966 / 985.1s（只省 79s，质量 −6%）；C/D/E 并行架构质量受损。**不要重复这些方向。**

### 1.2 预算换算【证据：官方定价 + 本仓库 token 结构；汇率按 1 USD ≈ 7.1 CNY 假设】
- deepseek-flash 谷时：input miss $0.15/M、cache hit $0.003/M、output $0.6/M；峰值翻倍【[官方定价](https://api-docs.deepseek.com/quick_start/pricing/)】。
- 单次 B 跑 ≈ 1.55M 输入 + 0.15M 输出、全 miss ⇒ **$0.32 ≈ ¥2.3**；¥24.84 余额 ≈ **10 次 B 跑**。
- 其中 dual_judge+self_check ≈ $0.08 ≈ **¥0.57（占单跑 4.5%、余额 2.3%）** ⇒ 全部本地化也只多出 **~0.2 次跑**的预算【推断】。
- **输入端缓存才是主项**：若 40–60% 输入命中共前缀，单跑省 $0.09–0.14 ⇒ **−28~43% API 费**，等效多出 3–5 次 B 跑【推断，取决于命中率】。

### 1.3 硬件实况【本仓库实测 `nvidia-smi` + 规格】
- GTX 1660 Ti：6144 MiB 总显存；**桌面基线已占 989 MiB**；调研时段另一条本地训练 bench 任务占 ~4.7GB，实测 **free 仅 67–107 MiB** ⇒ 本地模型必须做**显存准入控制**（单实例串行 + 队列），否则与 App/引擎并行时直接 OOM。
- **GTX 16 系属无 Tensor Core 的 Turing（SM 7.5）**【规格】；vLLM 官方量化兼容表：Turing 支持 AWQ/GPTQ/INT8/GGUF，**不支持 Marlin、FP8**【[vLLM Supported Hardware](https://docs.vllm.ai/en/v0.7.0/features/quantization/supported_hardware.html)】。
- 已知陷阱：vLLM issue 报告「`--dtype half` 在无 Tensor Core 的 Turing（GTX 16 系）上是性能陷阱，batch decode 下 fp32 反而快至 9 倍」【外部 issue，未独立复现，[vllm#54950](https://github.com/vllm-project/vllm/issues/54950)】。
- 环境实况（`local_model/envs/dgtf_llm_env`）：torch 2.14.1+cu126、transformers 5.20.2、peft 0.21.2、accelerate 1.15.0；**未装 vllm / llama-cpp-python / autoawq / bitsandbytes / flash-attn**。
- Qwen2.5-1.5B 结构（`local_model/models/Qwen2.5-1.5B-Instruct/config.json`）：28 层、hidden 1536、12 heads、**2 KV heads（GQA）**、vocab 151,936 ⇒ KV cache ≈ **28 KB/token（fp16）**，13.5K 上下文 ≈ 387 MB。【推断】fp16 权重 3.1GB + KV 0.4GB + 框架开销 ⇒ 单实例约 3.8GB，仅够**单任务独占**。
- 带宽/算力上限（规格推算）：288 GB/s ÷ 3.1GB ⇒ fp16 decode 理论 ≤93 tok/s；外部参考实测 DeepSeek-R1-Distill-1.5B 在本卡约 **21 tok/s**【外部数据，[willitrunai](https://willitrunai.com/can-run/deepseek-r1-distill-qwen-1.5b-on-gtx-1660-ti-6gb)】。输出 300 tok 的判定 ≈ 14s；13.5K 上下文 prefill 上限 5.4 TFLOPS FP32 ⇒ 理论 7.5s、现实 20–35s【推断】。**结论：本地不适合承担 13K 上下文的判官调用。**

## 2. 投机执行与级联

### 2.1 Speculative decoding（Leviathan / Chen）
- 要点：小模型串行起草 k 个 token，大模型一次并行验证，接受则跳过；**输出分布与目标模型逐字一致**，2–3× 加速。
- 证据：[Leviathan et al., ICML'23 Oral](https://arxiv.org/abs/2211.17192)（"without changing the distribution"）、[Chen et al. 2302.01318](https://arxiv.org/abs/2302.01318)。
- 集成点：**不可直接用于本引擎**——DeepSeek API 不返回目标模型 logits/top-k，无法做逐 token 拒绝采样；引擎 `_dual_judge`（V2.2.2:12234）是黑盒调用。→ 结论：**技术不适用**，只在「本地自建目标模型」时才成立。
- 收益/风险/成本/重复：无（不适用）/ — / 0 / 否。

### 2.2 LLM Cascade 与路由（FrugalGPT / RouteLLM）
- 要点：按置信度或学习到的路由器决定「小模型直出 / 升级大模型」；FrugalGPT 报告在匹配 GPT-4 质量下最多省 98% 成本。
- 证据：[FrugalGPT](https://arxiv.org/abs/2305.05176)、[RouteLLM](https://arxiv.org/abs/2406.18665)。
- 集成点：**已有雏形**——`dgtf_v2/mode_fusion.py:81-142` 的 `fused_plan`（fast→B 级联）+ `quality_predictor` 守卫；`dgtf_app/server.py:9655-9727` 已把选档落成引擎参数。缺的是**校准过的弃权阈值**（见 §3）。
- 收益：把「先跑 fast 再升级」的浪费（每次错误升级 +282s，fast 782.6s vs B 1064.3s）显式用风险上界控制。
- 风险：路由特征漂移；阈值过保守 ⇒ 全走 B，墙钟回升。
- 成本：2–3 人时（在现有 predictor 上做 conformal 化）/ 重复度：**部分重复**（不重复造路由器，只补保证）。

### 2.3 Draft-Defer-Verify（DDV）协议：本地判官草稿 + 云端只判弃权子集【本调研提出，非论文原样】
- 要点：本地 1.5B 给每个候选判 position ∈ {0,1,both} 并出置信度；用 conformal 预测集决定「集合为单元素 ⇒ 本地直判；否则弃权」；云端只对弃权候选判一次（候选列表变短，保留原 idx 映射）。**保守性来自 conformal，不来自 token 级对齐。**
- 证据支撑：[Conformal Cascade](https://arxiv.org/abs/2607.25018)（"accept when the calibrated set collapses to a single answer, defer otherwise"，给出 1−Kα 的有限样本精度保证、零训练、黑盒 API）；[Judge Decoding](https://arxiv.org/abs/2501.19309) 证明「按与草稿的对齐度验证会大量误拒正确续写，验证应判断正确性而非对齐」⇒ 云端验证要做**正确性判定**（短输出 agree/correct），不要做逐字比对。
- 集成点：`Meta-DGTF-V2.2.2.py` `_dual_judge`（12234–12400，LLM 调用在 12292）/ `_extract_judgments`（12208）/ `_judge_context`（12193）；候选位置写入在 12372–12392。离线可先不改引擎，用 packed 标签验证（Top3）。
- 收益【推断】：若 40–60% 候选可本地直判，judge 调用输入 −40~60%、输出 −30%，单跑省 $0.02–0.04（¥0.15–0.3）——**省不了大钱**；真正收益是 **GPU 空闲算力被用起来 + 高置信子集少发云调用**，以及为「离线/无网可用」铺路。
- 风险：① 候选级可交换性不成立（同 view 内相关、跨圈漂移）⇒ 必须做分层（Mondrian）校准；② 本地 20–35s/call 的 prefill 若不在并行流水里隐藏，墙钟变差 1.5–3×；③ 类别极不平衡（both 仅 2.6%，见 §3.4），模型易塌缩到 "0"。
- 成本/重复：先验证 4–6 人时；若通过，落地 2–4 人日 / 与现有机制不重复。

### 2.4 self_check 的「不可计算项才上云」（投机式裁剪）
- 要点：self_check 的 7 问里，第 3 问（ing 近义复述比）与第 7 问（未生计数）**可用代码/本地 BGE 算出**；引擎已实测「模型自报计数与实际不符」，V2.2.2 已改为代码计数（`:15227-15239` `_count_unsaid` + 双源闸）。剩下不可计算项可用**短 prompt**（只给候选/&/ing 摘要，不给 1500 字 collision）。
- 证据：本仓库 `_self_check`（15162–15310）注释 P2-4/P2-8；BGE 服务常驻 `127.0.0.1:8771`（`dgtf_app/rag_embed_service.py:9`）。
- 集成点：`_self_check` 15175–15219（system/user 组装）、15250（LLM 调用）；`_count_unsaid` 与 `_unsaid_flag_gate`；`_judge_context`（12193）对 upstream shapes 的 1200 字截断。
- 收益【推断】：self_check 单次 13.3K tok 中，collision+manifest+候选列表占大头 ⇒ 目标 −30~50% 输入；judge 侧上下文压缩同理，合计 **−6~10% 总 tokens**（≈ −¥0.15~0.3/跑）。
- 风险：质量门要求 1.0；缩短 prompt 可能让模型漏报逃避（负结果 `docs/remaining_optimization_assessment_20261025.md:11-16` 就是这一类）。必须 A/B + 回滚。
- 成本/重复：3–5 人时 / **部分重复**（计数已下沉，增量在复述率与上下文压缩）。

## 3. 风险可控弃权：给「本地判定跳过云端」一个错误率上界

### 3.1 机制与保证
- **Split conformal**：给定校准集与不满足度分数 s，取 q̂ = ⌈(n+1)(1−α)⌉/n 分位数，则新样本 P(s ≤ q̂) ≥ 1−α（仅需可交换性，分布无关、有限样本）【[Gentle Intro](https://arxiv.org/abs/2107.07511)、[Conformal Risk Control](https://arxiv.org/abs/2208.02814)】。
- **Conformal risk control（CRC）**：把覆盖率换成任意单调损失期望上界（如「被接受的判定错误率」E[L] ≤ α），且松紧仅差 O(1/n)【2208.02814】。
- **Conformal Cascade（2026）**：以**预测集大小**作为弃权规则，接受条件为「集合塌缩为单答案」，多层 union bound 给 1−Kα；无训练、黑盒 API 可用【[2607.25018](https://arxiv.org/abs/2607.25018)】。
- **Conformal Abstention（2026）**：对开放式生成用置信度而非不可计算的非一致性分数，给「参与率」与「参与时正确率」双保证【[2604.27914](https://arxiv.org/abs/2604.27914)】；**选择性分类**是同一族思想的前身【[Geifman & El-Yaniv](https://arxiv.org/abs/1705.08500)】。
- **语义熵**：采样语义聚类估不确定度，可用于「判官草稿是否值得直判」的本地廉价信号【[2302.09664](https://arxiv.org/abs/2302.09664)】。

### 3.2 本项目的校准流程（可 1 小时内跑完的离线版）
1. 数据：`dgtf_memory/quality_predictor.json`（kNN k=3、**142 行 × 22 特征**、y∈[0.03,1.0]）；`dgtf_memory/episodes.jsonl`（137 行）；候选级标签 **17,394 条**（177 个 packed，见 §3.4）。
2. 切分：**按时间切分**（后 30% 作校准集），避免同题泄漏；kNN 必须用留一/切分残差，不能用 in-sample 残差（否则保证失效）。
3. 分数：CQR 型 s = max(ŷ−y, 0) 或 |ŷ−y|；取 q̂(α)。
4. 决策：`LB = ŷ − q̂`；`LB(fast) ≥ min_quality` ⇒ 选 fast；`LB(B) < min_quality` ⇒ 不承诺，输出 `answer_quality = unverified/needs_evidence`（弃权），而不是静默接受。
5. 复核：在留出集报 coverage、平均区间宽度、**决策改变率**；每次改 prompt/模式需重校准（非平稳会破坏可交换性）。
- 现有实现位置：`quality_predictor.py:240 evaluate`（只有 MAE/R²，无区间）→ 需加 `residual_quantile` 字段；`mode_fusion.py:109-117` 的 `0.5*pred+0.5*prior` 硬夹取替换为 conformal 下界；`server.py:9708-9723` 的 `_fused_info.quality_prediction` 增列 `lb`。

### 3.3 保证的适用边界（必须写进文档，避免过度承诺）
- 保证是**边际的（marginal）**，不是条件保证；对「项目背景类」长尾问题覆盖率可能低于 1−α。
- 只在**可交换性**下成立：换模型、换模式、换 prompt 顺序后必须重校准；DeepSeek 模型版本升级（定价页显示 Flash 已到 V4.1-1017）也算分布变化。
- n 很小时临界分位数粗：n=42、α=0.1 时保守分位数会显著偏大 ⇒ 下界偏紧变松（更保守）【推断】。

### 3.4 候选级判定的现实难度（本仓库实测，用于给 DDV 定基线）
- 177 个 packed 的候选标签分布：`0` = 9,991（57.4%）、`1` = 6,948（39.9%）、`both` = 455（**2.6%**）。
- 推论【推断】：无脑全填 `0` 就有 57.4% "准确率"，所以 **DDV 的验收指标不能是 accuracy，必须是「高置信子集上的条件错误率 + 覆盖率」**；`both` 因极稀有，建议直接不本地直判（全部交云）。

## 4. Test-time compute scaling 与 verifier：映射到圈数/分支

- **Self-consistency**（多数投票）：同一题多次采样取多数，显著提升推理正确率【[2203.11171](https://arxiv.org/abs/2203.11171)】→ 可映射为「同层同圈多采样一次 dual_judge，位置取多数」，用 **+1 次云调用**换位置稳定性；但本引擎已有「同构重采样/结构复检」机制（`_dual_judge` 的 `diversity_hint`/`allow_retry`，12241–12245），**部分重复**。
- **Best-of-N / verifier 引导搜索**：用打分器在 N 个候选里选最优，增益随 N 亚线性【2408.03314 摘要】。
- **Process reward model（PRM）**：对推理步骤逐步打分，比 outcome 监督更有效【[Let's Verify Step by Step](https://arxiv.org/abs/2305.20050)】→ 映射为「对每圈产物打小分，决定是否加圈」，但需要过程标签；本仓库 `episodes.jsonl/playbook.jsonl`（137/64 行）+ `quality_predictor` 可作为弱 PRM 起点【推断】。
- **Compute-optimal 分配**：不同难度题用不同 TTC 手段，效率可比 best-of-N 高 4×；FLOPs 匹配下小模型 + TTC 可胜 14× 大模型【[Snell et al. 2408.03314](https://arxiv.org/abs/2408.03314)】→ 这是「按题型自适应圈数」的直接证据支撑：`server.py:9640-9653` 的 `_auto_policy_rounds` 现在是常数 2–6 圈，可改为**按预测难度 + 边际收益停止**。
- 本仓库已有：`check_structure_saturation`（7 calls，5,058 tok，7s）、`self_check` 停止判据、`unsaid` 双源闸 → **加圈/停圈机制已存在**，新增价值在「用校准过的边际收益估计决定是否加第 N 圈」；负结果提示简单砍 self_check 会掉质量（0.94）。
- 集成点：`_auto_policy`（`server.py:9640-9653`）、`rounds` 参数；`_self_check` 返回的 `flow_verdict`；`quality_predictor.featurize` 的 `rounds_avg` 特征。
- 收益/风险/成本：【推断】−10~20% 墙钟（少跑 1 圈 ≈ −15%），质量风险中高（必须 A/B）/ 4–6 人时 / 与 UCB 行为融合、M4 预测器部分重复。

## 5. 小模型适配与 6GB 推理加速（本机可执行选型）

### 5.1 训练侧（已有基础：LoRA r=8/α=16、122 样本/35 题，`docs/llm_lora_finetune.md`）
- **QLoRA**（4bit NF4 基座 + LoRA）：把 1.5B 训练显存从 ~3.2GB（实测 fp16 峰值 3.17GB）压到 ~1.5GB，可把 `max_len 512 → 2048`、batch>1【[QLoRA 2305.14314](https://arxiv.org/abs/2305.14314)】→ 对「判官草稿」这种 13K 上下文任务才可能训练（否则 512 截断必然失效）。**这是 DDV 路线的前置条件**。
- **DoRA / LoRA+**：同等预算下小幅提升拟合质量（DoRA 分解幅值/方向，LoRA+ 分层学习率）【[DoRA 2402.09353](https://arxiv.org/abs/2402.09353)、[LoRA+ 2402.12354](https://arxiv.org/abs/2402.12354)】→ 低成本试一次即可，不要当主线。
- **从云轨迹蒸馏**：本仓库已有最佳语料——177 个 packed 的 `views[*].candidates`（**17,394 条带 position/why_position 的判定**）+ `llm_by_stage` 成本画像；比现有 122 条调度样本大两个量级【本仓库实测】。蒸馏目标建议：`candidates+处境摘要 → {idx, position, why≤30字}`，与 `_dual_judge` 输出契约一致（V2.2.2:12252-12255）。

### 5.2 推理侧选型（6GB、Turing SM7.5、无 Tensor Core）
| 方案 | 可行性 | 依据 | 建议 |
|---|---|---|---|
| transformers fp16（现状） | ✅ 已跑通，1.5B 加载 3.09GB | 本仓库 `docs/llm_lora_finetune.md:53` | 保留为基线；**冷加载 3–5s/次**，仅适合离线批处理 |
| **llama.cpp + GGUF（Q4_K_M/Q5_K_M）常驻** | ✅ sm_75 支持（vLLM 表 GGUF 对 Turing ✅；llama.cpp 自带 CUDA 后端） | [vLLM 兼容表](https://docs.vllm.ai/en/v0.7.0/features/quantization/supported_hardware.html) | **首选**：1.0–1.4GB 权重，decode 预期 45–70 tok/s【推断】，可留 ~4GB 给 KV/其他 |
| vLLM + AWQ/GPTQ | ⚠️ Turing 支持但**无 Marlin 内核**（表：Marlin Turing ✗），且 fp16 在无 TC 卡上有性能陷阱 | [vLLM 表](https://docs.vllm.ai/en/v0.7.0/features/quantization/supported_hardware.html)、[vllm#54950](https://github.com/vllm-project/vllm/issues/54950) | 不推荐（安装重、收益不确定） |
| PagedAttention + Automatic Prefix Caching | ✅ 原理通用（KV 分页 + 共享前缀复用，避免重复 prefill） | [PagedAttention 2309.06180](https://arxiv.org/abs/2309.06180)、[vLLM APC](https://docs.vllm.ai/en/latest/design/prefix_caching/) | llama.cpp 侧对应 **slot 复用 / prompt cache**；对「同一 run 内 15 次 judge」价值最大 |
| torch.compile / 动态批 | ⚠️ 单请求小模型收益小，编译期在 6GB 卡上有 OOM 风险 | — | 暂缓；先把常驻服务做起来 |
| KV cache 量化（Q8/Q4 KV） | ⚠️ 需 llama.cpp 支持；13K 上下文 KV 仅 387MB，收益小 | 本仓库 config 推算 | 不必做 |
| **显存准入控制** | 🔴 必需 | 实测 free 67–107 MiB（桌面 989MiB + 并发任务 4.7GB） | 单实例 + 队列 + 失败快速降级 |

### 5.3 现状缺口（必须先修，否则任何本地机制都没有落点）
- `dgtf_app/server.py:6154` 的 `_LLM_SCRIPT = <root>/llm_predict.py`，但**该文件已移入 `archive/legacy_root/`，根目录不存在**（本仓库实测 `Test-Path` = False）⇒ `_llm_predict_local`（6895–6939）在 `opts.auto_llm=true` 或 `/api/schedule/llm/*` 路径上会失败；默认任务不受影响。三个 adapter 目录均存在。
- 冷启动架构：每次调用 spawn 一个 Python 进程重新加载 3GB 权重（6895–6939），p50 进程开销 3–5s【推断，含 import torch】。→ 换成常驻服务是 §5.2 的确定性收益。

## 6. RAG 与记忆（映射到 `dgtf_memory/`）

- **DeepSeek 上下文硬盘缓存**（官方）：前缀完全相同（从 token 0 起）才命中，64 token 为存储单元，命中价 $0.003/M（谷时），128K 输入首 token 延迟可从 13s 降到 0.5s【证据：[官方新闻](https://api-docs.deepseek.com/zh-cn/news/news0802/)、[定价页](https://api-docs.deepseek.com/quick_start/pricing/)】。**集成点**：项目背景现在由 `server.py:9584-9589` 以 `_prompt_prefix` 拼在**用户问题前**，进引擎后落在 `_judge_context` 中段 ⇒ 跨任务同背景**无法命中**；把项目背景提升为「system 首段 + 固定不变」即可跨任务命中（Top1 的一部分）。
- **Self-RAG**（自反思检索，按需检索 + 反思 token 判断相关性/支撑度，[2310.11511](https://arxiv.org/abs/2310.11511)）→ 现有 `rag_index.json`（719KB）+ `references.jsonl`（554KB）+ `unified_memory.py` 可加「检索前先判需不需要检索」，省的是 web/RAG 调用而不是 LLM token；价值中等。
- **CRAG**（检索质量差时纠正/回退，[2401.15884](https://arxiv.org/abs/2401.15884)）→ 对应 App 的 web-retry（`quality_policy=web-retry`，`server.py:9561/9965`）**已实现**，重复。
- **GraphRAG**（实体图 + 社区摘要，[2404.16130](https://arxiv.org/abs/2404.16130)）→ 对「单文件引擎 + 项目背景」收益低、构建成本高，**不建议**（除非要做跨文档全局问答）。
- **上下文压缩 LLMLingua**（token 级压缩，最高 20× 压缩率，[2310.05736](https://arxiv.org/abs/2310.05736)）→ 用在 `_judge_context` 的上游 view shapes（现 1200 字/个）与 `collision`（现 1500 字）；可用本地 0.5B 做压缩器（短 prompt、低延迟）⇒ 与 §2.4 合并。
- **Lost in the middle**（长上下文中间信息衰减，[2307.03172](https://arxiv.org/abs/2307.03172)）→ 支持「把关键约束放首尾、候选列表放最后」的重排方案，同时利好 prefix cache ⇒ Top1 的第二条论据。
- **记忆分层**：现有 `episodes.jsonl`（137，情景）、`playbook.jsonl`（64，程序性）、`references.jsonl`（语义）、`nogoods.jsonl`；MemGPT 式分页/换入换出【[2310.08560](https://arxiv.org/abs/2310.08560)】目前规模不需要，**不重复造轮子**；建议只补「校准元数据」（conformal q̂、校准时间、样本量）到 `dgtf_memory/quality_predictor.json` 的旁挂文件（新增文件不在本次范围）。

## 7. 多智能体/推理范式（both/all 层与 App Agent）

- **Multiagent debate**：多实例互相批判提升事实性【[2305.14325](https://arxiv.org/abs/2305.14325)】、[divergent-thinking MAD 2305.19118](https://arxiv.org/abs/2305.19118) → 本引擎 both 层已有「对撞/裁决/冲突/线头」（`_dual_judge` + adjudicate 系列），**高度重复**；增量只在「同题多判官投票」= §4 self-consistency，成本 +N 云调用，**不建议**（负结果已显示关 self_check 掉质量，但加调用同样贵）。
- **Reflexion**（语言化反思记忆，[2303.11366](https://arxiv.org/abs/2303.11366)）与 **Self-Refine**（[2303.17651](https://arxiv.org/abs/2303.17651)）→ 与 `self_check` + `playbook`/`nogoods` 同类，**重复**；若要增强，方向是「把 self_check 的 verdict 结构化写入 playbook 并在下一圈注入」——现有 `_self_block`（10935）已在做「上一次是谁」的注入，属重复。
- **LLM-as-judge 可靠性**：GPT-4 判官与人类一致率约 80%【[MT-Bench/Chatbot Arena 2306.05685](https://arxiv.org/abs/2306.05685)】**这是双刃**：既说明「云判官也不是金标准」，也说明 DDV 的验收不能要求与云标签 100% 一致，只能要求「弃权后整体质量不降 + 高置信子集条件错误率 ≤ α」。
- **Agent memory / tool use**：App 已有 `agent_knowledge.jsonl`、DSH agent、tool calls（`api_usage.tools_calls`）⇒ 不新增。

## 8. Top5 建议清单（按 ROI 排序；明细校验方案见 reports 文档）

| # | 机制 | 集成点（文件/函数/层） | 预期收益 | 主要风险 | 人时 | 1 小时验证动作 |
|---|---|---|---|---|---|---|
| 1 | **DeepSeek 前缀缓存对齐 + prompt 稳定段前置**（官方缓存 50× 价差） | 引擎 `_dual_judge` system 组装 12270–12284、`_self_check` 15175–15210、`_self_block` 10935（动态记忆移到 user 末尾）、`_judge_context` 12193；App `server.py:9584-9589`（背景前置到 system 首段）；复用 `scripts/run_engine_instrumented.py`（21–26、92 `--prefix`）做命中率探针 | 输入费 −28~43%【推断】；¥24.84 可用 B 跑 10→13~14 次；TTFT 下降 | 次序改变可能掉质量（须 A/B，质量门 ≥0.99）；缓存"尽力而为" | 3–4 | 零 API：写只读脚本，从 1 个 packed 的 views 重建新旧两版 judge/self-check prompt，用本地 tokenizer 统计「跨 15 次调用的最长公共前缀 token 占比」；旧版 vs 新版对比，命中率预期从 <10% 提到 40–60% |
| 2 | **Conformal 化 M4 质量预测器（带保证的升/降档与弃权）** | `dgtf_v2/quality_predictor.py:240 evaluate`（加残差分位）、`dgtf_v2/mode_fusion.py:97-133`（替换 0.5/0.5 硬夹取）、`server.py:9708-9723`（输出 lb） | ¥0/GPU 0；避免错误 fast→B（每次 −282s 墙钟）+ 避免无谓 B；把 unverified 变成显式弃权 | 可交换性/分布漂移；小 n 分位偏保守 | 2–3 | 零 API：142 行按时间切 70/30，CQR 校准 α=0.1，报留出 coverage、区间宽度、模式决策改变率；若 coverage<0.85 或决策改变 >40% ⇒ 先查特征漂移 |
| 3 | **本地判官草稿 go/no-go（17,394 条已有标签，零 API）** | 只读 `outputs/*.packed.json` 的 `views[*].candidates`；本地 `local_model/envs/.../python.exe` + `Qwen2.5-1.5B-Instruct`（+可选 LoRA）；结论回写 §2.3 协议 | 1–4 人时决定是否投 2–4 人日；若通过，judge 输入 −40~60%、GPU 闲置算力被利用 | GPU 现被其他 bench 占用（free 67–107MiB）；both 仅 2.6% 需排除；本地 20–35s/call 可能拉长墙钟 | 4–6（1h 可出初测） | 抽 50 条候选（含归属 view 摘要），零样本让 1.5B 判 position，报「多数类基线 57.4% / 高置信子集覆盖率 / 条件错误率」；若高置信覆盖 <20% 直接判死 |
| 4 | **self_check/dual_judge 可计算判据下沉 + 上下文压缩** | `_self_check` 15175–15219/15250；`_count_unsaid`（已存在）；BGE 服务 8771 算复述率；`_judge_context` 12193（1200 字 → 抽取式摘要） | judge/self tok −25~40% ⇒ 总 token −6~10%、墙钟 −5~8%、¥ −0.15~0.3/跑 | 质量门 1.0 严格；漏报逃避；与既有双源闸部分重复 | 3–5 | 零 API：离线重建 30 条 self_check 的「代码判据版」结果，与 packed 中已有模型输出比对一致率（复述率判据、未生计数） |
| 5 | **6GB 推理栈收口：常驻 GGUF 服务 + QLoRA 蒸馏云轨迹** | `server.py:6154/6895-6939`（补回/重写 `llm_predict.py` 或改常驻 HTTP）；`local_model/envs` 装 llama-cpp-python(CUDA) 或复用 transformers 常驻；`scripts/local_model/train_llm_lora.py` 改 QLoRA + 2048 上下文；数据 = packed 17,394 条判定 | 本地短任务 p50 3–5s → 0.3–0.8s；为 Top3 落地提供训练/推理基础；显存准入可控 | 无 TC 卡不要指望 vLLM 加速；编译/驱动成本；显存争用 | 5–8 | 用现有 transformers：同一短 prompt 连续 10 次调用，分别测「每进程冷加载 vs 进程内常驻」的 p50 延迟差（不改 app，只在 llm env 里跑），得到替换收益上界 |

### 8.1 不做什么（已由本仓库负结果或证据否定）
- 全部关掉 dual_judge / self_check（已实测质量 1.0→0.94）；C/D/E 等新并行架构（质量受损）；跨 API 的 token 级 speculative decoding（拿不到 logits）；GTX 1660 Ti 上的 vLLM fp16/AWQ-Marlin 加速（无 TC/Marlin）；GraphRAG（与单文件引擎不匹配）；再加一层 debate/reflexion（与 both 层重复）。

## 9. 证据强度与未覆盖
- 强证据（论文/官方/本仓库实测）：§1 全部数字、§2.1–2.2、§3.1–3.4、§5.2 兼容表、§6 缓存规则与价格、§7 judge 一致率。
- 中证据（外部单源/issue，未复现）：GTX 16 系 fp16 性能陷阱（vllm#54950）、1.5B 本卡 ~21 tok/s（willitrunai）、Turing 无 Tensor Core（规格常识，未逐页引官方规格书）。
- 纯推断（必须在实施前实测）：所有「本地 20–35s/call prefill」「GGUF 45–70 tok/s」「缓存命中 40–60%」「省 28–43% API 费」「墙钟 −5~8%」。
- 未覆盖：MoE/稀疏化（不适用 1.5B）、RLVR/可验证奖励（无训练预算）、多卡/显存外溢（单卡 6GB 无空间）、企业级 KV 复用（Mooncake/LMCache，规模不匹配）。
