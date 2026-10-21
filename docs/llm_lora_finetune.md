# 元DGTF LLM LoRA Fine-tune（app V1.2.0）

## 目标

用元DGTF真实/历史 packed 产物训练一个本地 LLM 调度规划器：
问题 → route/rounds JSON。

## 数据

- 来源：outputs/*.packed.json 的 question/route/rounds；
- 目标：严格 JSON（route 子集 + 每层圈数 + 短理由）；
- 规模：122 条 / 35 个问题；训练 108 / 留出 14；
- 切分：按问题分组，避免同题泄漏；
- 文件：llm_sft/train.jsonl、val.jsonl、manifest.json。

## 基座与训练

- 基座：Qwen2.5-0.5B-Instruct（开源、中文、6GB 可 LoRA）；
- 方法：LoRA r=8 / alpha=16，fp16，gradient checkpointing；
- 可训练参数：4,399,104 / 498,431,872（0.88%）；
- batch=1，grad accumulation=8，max_len=512，epochs=5；
- 训练脚本：train_llm_lora.py；
- 最佳 val loss 0.106（epoch 4）；
- adapter：llm_sft/adapter_qwen05b_v1。

## 留出评估

| 指标 | base | +LoRA |
|---|---:|---:|
| JSON 合法率 | 0.857 | 1.000 |
| route 完全匹配 | 0.000 | 0.429 |
| rounds MAE | 2.625 | 1.446 |

评估脚本：eval_llm_lora.py；结果：llm_sft/eval_base_vs_lora.json。

## app/引擎接入

- POST /api/schedule/llm/predict：本地子进程推理，返回 route/rounds；
- POST /api/schedule/llm/apply：写入 schedule_policy 的 llm_route/llm_rounds；
- GET /api/schedule/llm/status：adapter 路径、训练/评估读数；
- 任务 opts.auto_llm=true：自动把 LLM 结果写入 runner 的 route/rounds；
- UI：Agent V2 面板“采用LLM”。

## 验证

- app selftest 371/0；
- 集成探针 70/0（含 LLM status/predict/apply）；
- 实测 auto_llm mock 任务 opts = route:0,1 / rounds:0:3,1:3，任务 done。


## 1.5B 升级评估（实验，不接管默认）

- Qwen2.5-1.5B-Instruct fp16：加载 3.09GB，LoRA+前向峰值 3.17GB，6GB 可训；
- 4 epochs：val 0.1599 → 0.1064 → 0.1205 → 0.1202（最佳 epoch2）；
- 留出 base vs LoRA：
  - route 完全匹配：base 0.0 / LoRA 0.357；
  - rounds MAE：base 2.232 / LoRA 1.923；
- 结论：1.5B 在 route 与 rounds 上均不如 0.5B（0.429 / 1.446），默认不切换；
- adapter 保留：llm_sft/adapter_qwen15b_v1；对比：llm_sft/eval_base_vs_lora_15b.json。

## adapter merge

- merge_lora.py 将 0.5B adapter 合并进基座，导出 D:/dgtf_models/Qwen2.5-0.5B-Instruct-merged-v1（约 988MB）；
- 实测 merged 模型输出合法 JSON route/rounds；
- 默认 app 仍加载 adapter（便于切换/回滚），merge 产物用于自包含部署。

## 上下文与命名

- 项目上下文通过 opts._prompt_prefix 只进引擎 argv；任务标题/run.json 保留原问题；
- 引擎现有产物仍按 argv 问题命名，因此真实跑的 md 文件名可能包含背景前缀；这是待修边界。

## 边界

- 0.5B + 122 条只能学格式与浅层调度，不是强领域模型；
- route 42.9% 只能做建议/预填，不应直接替代 API 调度；
- 不是 DeepSeek LLM 微调；基座是开源 Qwen；
- 真实跑/长文四层分析仍由 DeepSeek API 承担。