# ABORTED（Round 116 归档说明）

本目录是 v9 训练的中止产物，**不可用于 0.5B 服务体系**：

- 启动命令漏传 `--model`，而训练脚本 `DEFAULT_MODEL` 是 **Qwen2.5-1.5B-Instruct**；
- 因此本 adapter 是 **1.5B** LoRA（hidden 1536），与 0.5B（hidden 896）不兼容
  （eval 加载时报 size mismatch）；
- Round 116 已加防错训守卫：out 名含 `05b` 但模型非 0.5B ⇒ 训练脚本直接拒绝
  （除非 `--allow-model-mismatch`）。

正确 0.5B 训练命令（等专用 GPU 窗口）：
```powershell
local_model\envs\dgtf_llm_env\Scripts\python.exe scripts/local_model/train_dgtf_stage_lora.py `
  --model local_model\models\Qwen2.5-0.5B-Instruct `
  --stage self_check --variant min --max-train 230 --epochs 2 --max-len 1900 `
  --lr 6e-5 --seed 7 --val-subset 16 --save-every 100 `
  --out llm_sft/adapter_dgtf_selfcheck_05b_v9b
```
