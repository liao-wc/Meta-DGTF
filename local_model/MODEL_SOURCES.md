# 本地模型来源与校验

本地权重不入 Git；本文件记录来源和核验方法。

| 用途 | 模型目录 | 上游来源（请按实际下载地址核对） | 许可证 |
|---|---|---|---|
| BGE 检索 | bge-small-zh-v1.5 | BAAI/bge-small-zh-v1.5 | 以上游仓库为准（通常 MIT） |
| 轻量路由 | Qwen2.5-0.5B-Instruct | Qwen/Qwen2.5-0.5B-Instruct | 以上游仓库为准（通常 Apache-2.0） |
| 本地生成 | Qwen2.5-1.5B-Instruct | Qwen/Qwen2.5-1.5B-Instruct | 以上游仓库为准（通常 Apache-2.0） |
| 推理蒸馏 | DeepSeek-R1-Distill-Qwen-1.5B | deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B | 以上游仓库为准（通常 MIT） |
| 微调适配器 | *-merged-v1 / llm_sft/adapter_* | 本项目微调产物 | 继承上游模型许可证 |

## 校验命令

    Get-FileHash "local_model\models\bge-small-zh-v1.5\model.safetensors" -Algorithm SHA256
    Get-FileHash "local_model\models\Qwen2.5-0.5B-Instruct\model.safetensors" -Algorithm SHA256

## 规则

- 只从可信来源下载。
- 记录 revision / commit 与 SHA256。
- 不在公开仓库提交权重。
- 合并 LoRA 产物前确认上游许可证允许再分发。
- 不使用 trust_remote_code=True 加载不可信模型。
