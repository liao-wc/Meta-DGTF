# 本地模型权重 SHA256

计算时间：2026-10-23。权重不随仓库分发。

| 模型目录 | 权重文件 | 大小 (MB) | SHA256 |
|---|---|---:|---|
| bge-small-zh-v1.5 | model.safetensors | 91.4 | 354763b9b1357bc9c44f62c6be2276321081ed2567773608c0d0785b61d5a026 |
| bge-small-zh-v1.5 | pytorch_model.bin | 91.4 | 7c5fe667bbed05dc10e246e229b701ad266fe4d95ab946e9e5aa402056611b88 |
| DeepSeek-R1-Distill-Qwen-1.5B | model.safetensors | 3389.6 | 58858233513d76b8703e72eed6ce16807b523328188e13329257fb9594462945 |
| DeepSeek-R1-Distill-Qwen-1.5B-merged-v1 | model.safetensors | 3389.6 | ea5e4cc2a9a766cdcb4969b11ac6423eb5918968f6ae936181ce549188ad1f14 |
| Qwen2.5-0.5B-Instruct | model.safetensors | 942.3 | fdf756fa7fcbe7404d5c60e26bff1a0c8b8aa1f72ced49e7dd0210fe288fb7fe |
| Qwen2.5-0.5B-Instruct-merged-v1 | model.safetensors | 942.3 | 70f9c79c48c50913064301df031ed15793b91a36bed4c7e2a9bd30056036fc2b |
| Qwen2.5-1.5B-Instruct | model.safetensors | 2944.4 | dd924a11b4c220f385b51ffa522daea7c9f3d850e31b162bb5661df483c6d3ee |

## 校验方法

    Get-FileHash "local_model\models\<模型目录>\<权重文件>" -Algorithm SHA256

## 说明

- 以上哈希是本机当前权重文件的实际值。
- 模型来源和上游许可证见 MODEL_SOURCES.md。
- 重新下载或替换权重后必须重新生成。
