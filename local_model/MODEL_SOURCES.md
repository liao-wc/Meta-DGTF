# 本地模型来源与校验

本地权重不入 Git；本文件记录来源、上游许可证和核验方法。

## 已核对的上游模型

| 用途 | 本地目录 | 上游模型 | 上游许可证 | 核对 revision |
|---|---|---|---|---|
| BGE 检索 | bge-small-zh-v1.5 | BAAI/bge-small-zh-v1.5 | MIT | 7999e1d3359715c523056ef9478215996d62a620 |
| 轻量路由 | Qwen2.5-0.5B-Instruct | Qwen/Qwen2.5-0.5B-Instruct | Apache-2.0 | 7ae557604adf67be50417f59c2c2f167def9a775 |
| 本地生成 | Qwen2.5-1.5B-Instruct | Qwen/Qwen2.5-1.5B-Instruct | Apache-2.0 | 989aa7980e4cf806f80c7fef2b1adb7bc71aa306 |
| 推理蒸馏 | DeepSeek-R1-Distill-Qwen-1.5B | deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B | MIT | ad9f0ae0864d7fbcd1cd905e3c6c5b069cc8b562 |
| 微调适配器 | *-merged-v1 / llm_sft/adapter_* | 本项目微调产物 | 继承对应上游模型许可证 | 本地训练产物 |

许可证信息于 2026-10-23 通过 Hugging Face 模型元数据核对。上游可能更新许可证，使用前请再次确认 model card。

## 本地权重校验

每个权重文件的 SHA256 见 [MODEL_CHECKSUMS.md](MODEL_CHECKSUMS.md)。

校验命令：

    Get-FileHash "local_model\models\bge-small-zh-v1.5\model.safetensors" -Algorithm SHA256

## 规则

- 只从可信来源下载。
- 记录 revision / commit 与 SHA256。
- 不在公开仓库提交权重。
- 合并 LoRA 产物前确认上游许可证允许再分发。
- 不使用 trust_remote_code=True 加载不可信模型。
- 分发 merged 模型时，必须同时遵守上游模型许可证。
