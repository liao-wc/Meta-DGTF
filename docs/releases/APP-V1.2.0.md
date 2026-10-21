# 元DGTF app V1.2.0 发布说明

日期：2026-10-21
类型：minor

## 新增

- 真实 LLM LoRA fine-tune：Qwen2.5-0.5B-Instruct，元DGTF 调度 JSON SFT；
- adapter：llm_sft/adapter_qwen05b_v1；
- /api/schedule/llm/status、/predict、/apply；
- 任务 opts.auto_llm；
- Agent V2 面板“采用LLM”。

## 评估

- base route 0% / JSON 85.7% / rounds MAE 2.625；
- LoRA route 42.9% / JSON 100% / rounds MAE 1.446。

## 边界

- 本地小模型仅作调度建议/预填，不替代 DeepSeek API 的四层推理；
- 不是 DeepSeek 权重微调。